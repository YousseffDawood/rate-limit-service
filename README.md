# API Limiter

A Django REST Framework backend that enforces **subscription plan access control** for multi-tenant SaaS APIs. It manages users, plans, token budgets, and client seat limits — all checked at the middleware and permission layers before a request ever reaches a view.

---

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Data Models](#data-models)
- [Access Control](#access-control)
  - [Middleware](#middleware)
  - [DRF Permissions](#drf-permissions)
  - [Service Layer](#service-layer)
- [Project Setup](#project-setup)
- [Running the Dev Server](#running-the-dev-server)
- [Seeding Test Data](#seeding-test-data)
- [Configuration](#configuration)
- [Roles](#roles)
- [Plans](#plans)

---

## Overview

API Limiter is a **reusable access-control layer** intended to sit in front of any Django API. It answers three questions before a request is processed:

1. **Does this user have an active, non-expired plan?** (Middleware + `HasValidPlan`)
2. **Is their plan allowed to use AI features?** (`HasAIAccess`)
3. **Have they consumed their token budget for this period?** (`HasTokenBudget` + `consume_tokens`)

Admins bypass all plan checks. Regular users and their client accounts are always gated.

---

## Architecture

```
Request
  │
  ▼
PlanAccessMiddleware          ← global gate: blocks expired/missing plans early
  │
  ▼
DRF View
  │
  ├── HasValidPlan            ← re-checks plan validity per-view
  ├── HasAIAccess             ← checks ai_access flag on the plan
  └── HasTokenBudget          ← checks tokens_used < token_limit
        │
        ▼
      consume_tokens()        ← atomically increments tokens_used
      enforce_client_limit()  ← checks client seat count before adding a client
```

---

## Data Models

### `User` (extends `AbstractUser`)

| Field    | Type        | Description                                      |
|----------|-------------|--------------------------------------------------|
| `role`   | CharField   | `admin`, `user`, or `client`                     |
| `owner`  | FK → self   | Set on `client` users — points to their `user`   |

- `is_staff` is automatically synced to `True` for `admin` role users on every `save()`.

---

### `Plan`

| Field           | Type            | Description                                        |
|-----------------|-----------------|----------------------------------------------------|
| `name`          | CharField       | Unique plan name (e.g., `Basic`, `Pro`, `Premium`) |
| `duration_type` | CharField       | `week`, `month`, or `year`                         |
| `client_limit`  | PositiveInteger | Max number of client accounts allowed              |
| `ai_access`     | BooleanField    | Whether AI endpoints are accessible                |
| `token_limit`   | BigInteger      | Token budget per plan period (`0` = no AI access)  |

**Duration mapping:**

| `duration_type` | Days |
|-----------------|------|
| `week`          | 7    |
| `month`         | 30   |
| `year`          | 365  |

---

### `UserPlan`

Links a `User` to a `Plan` for a specific period.

| Field         | Type        | Description                                    |
|---------------|-------------|------------------------------------------------|
| `user`        | FK → User   |                                                |
| `plan`        | FK → Plan   | Protected from deletion while in use           |
| `is_active`   | BooleanField| Only one active plan per user (DB constraint)  |
| `start_date`  | DateField   |                                                |
| `end_date`    | DateField   |                                                |
| `tokens_used` | BigInteger  | Running total of tokens consumed this period   |

**Key behaviors:**
- `UserPlan.save()` automatically deactivates all other plans for the same user when `is_active=True`.
- `UserPlan.active_for(user)` returns the current active plan or `None`.
- A DB-level `UniqueConstraint` enforces the one-active-plan rule at the database layer.

---

## Access Control

### Middleware

**`PlanAccessMiddleware`** — registered globally in `MIDDLEWARE`.

Runs on every request **after** authentication. It:

1. **Bypasses** `/admin/`, `/static/`, `/media/` paths.
2. **Pre-checks login requests** (`POST /api/login/`): resolves the username from the request body and blocks the login if the plan is already expired/missing — before credentials are even validated.
3. **Blocks any authenticated non-admin** whose plan is missing or expired with a `403 JSON` response.

```json
// No plan
{"detail": "No active plan."}

// Expired plan
{"detail": "Your plan expired on 2026-07-01. Please renew to regain access."}
```

> **Note:** The login pre-check (step 2) is a defense-in-depth measure. It's not the primary gate — step 3 handles all authenticated requests anyway.

---

### DRF Permissions

Import from `Users.permissions` and combine on your views:

```python
from Users.permissions import HasAdminRole, HasValidPlan, HasAIAccess, HasTokenBudget

class MyView(APIView):
    permission_classes = [HasValidPlan]           # basic plan gate
    permission_classes = [HasAIAccess]            # AI endpoints
    permission_classes = [HasAIAccess, HasTokenBudget]  # AI + token budget
    permission_classes = [HasAdminRole]           # admin-only
```

| Permission      | What it checks                                           |
|-----------------|----------------------------------------------------------|
| `HasAdminRole`  | `user.role == 'admin'`                                   |
| `HasValidPlan`  | Active plan exists and `end_date >= today`               |
| `HasAIAccess`   | Extends `HasValidPlan` + `plan.ai_access == True`        |
| `HasTokenBudget`| Extends `HasValidPlan` + `token_limit > 0` and `tokens_used < token_limit` |

---

### Service Layer

#### `consume_tokens(user, amount=1)`

Atomically increments `tokens_used` on the user's active plan inside a `SELECT FOR UPDATE` transaction. Raises:

- `NoActivePlan` — user has no active plan
- `TokenLimitExceeded` — plan has no token budget (`token_limit = 0`), or adding `amount` would exceed `token_limit`

**Usage:**
```python
from Users.services import consume_tokens, TokenLimitExceeded, NoActivePlan

try:
    consume_tokens(request.user, amount=500)
except TokenLimitExceeded:
    return Response({"detail": "Token limit reached."}, status=429)
```

#### `enforce_client_limit(user)`

Checks that the user hasn't exceeded their plan's `client_limit` before creating a new client account. Raises:

- `NoActivePlan`
- `ClientLimitExceeded`

Returns the active `UserPlan` on success (so you don't need to fetch it again).

**Usage:**
```python
from Users.services import enforce_client_limit, ClientLimitExceeded

try:
    enforce_client_limit(request.user)
except ClientLimitExceeded:
    return Response({"detail": "Client seat limit reached."}, status=403)
# safe to create the client now
```

---

## Project Setup

**Requirements:** Python 3.10+, pip

```bash
# 1. Clone the repo
git clone <repo-url>
cd API_Limiter

# 2. Create and activate a virtual environment
python -m venv env
# Windows:
env\Scripts\activate
# macOS/Linux:
source env/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Apply migrations
python manage.py migrate

# 5. (Optional) Seed test data
python manage.py seed_data
```

---

## Running the Dev Server

```bash
python manage.py runserver
```

API is available at `http://127.0.0.1:8000/api/`.  
Admin panel is at `http://127.0.0.1:8000/admin/`.

---

## Seeding Test Data

```bash
python manage.py seed_data
```

Creates the following out of the box:

| Username  | Role  | Plan    | Status           | Notes                        |
|-----------|-------|---------|------------------|------------------------------|
| `admin`   | admin | —       | —                | Password: `adminpass123`     |
| `user1`   | user  | Basic   | Active           | 3 clients                    |
| `user2`   | user  | Pro     | Active           | 150,000 tokens used          |
| `user3`   | user  | Premium | Active           | 5 clients                    |
| `user4`   | user  | Pro     | Active           | 2 clients                    |
| `user5`   | user  | Basic   | **Expired**      | Plan ended 2 days ago        |
| `user6`   | user  | —       | **No plan**      |                              |
| `user7`   | user  | Pro     | Active           | 200,000 tokens used (at cap) |
| `user8`   | user  | Premium | Active           | 3 clients                    |
| `user9`   | user  | Basic   | Active           | 1 client                     |
| `user10`  | user  | Pro     | Active           | 2 clients                    |

All regular users have password: `testpass123`  
Client accounts are named `client1`, `client2`, … up to `client20`.

---

## Configuration

Key settings in [`API_Limiter/settings.py`](API_Limiter/settings.py):

| Setting       | Value            | Description                                      |
|---------------|------------------|--------------------------------------------------|
| `LOGIN_URL`   | `/api/login/`    | Used by middleware to detect login requests      |
| `USE_TZ`      | `True`           | Timezone-aware datetimes — required for correctness |
| `TIME_ZONE`   | `UTC`            | Server timezone                                  |

**Authentication classes (DRF):**
- `SessionAuthentication`
- `TokenAuthentication`

---

## Roles

| Role     | Description                                              |
|----------|----------------------------------------------------------|
| `admin`  | Full access, bypasses all plan checks, `is_staff=True`   |
| `user`   | Subject to plan limits; owns client accounts             |
| `client` | Belongs to a `user` via the `owner` FK; no direct plan   |
