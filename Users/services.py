from django.db import transaction

from Users.models import Roles, User, UserPlan


class TokenLimitExceeded(Exception):
    pass


class ClientLimitExceeded(Exception):
    pass


class NoActivePlan(Exception):
    pass


def consume_tokens(user, amount=1):
    with transaction.atomic():
        user_plan = UserPlan.objects.select_for_update().filter(user=user, is_active=True).first()
        if user_plan is None:
            raise NoActivePlan
        if user_plan.tokens_used + amount > user_plan.plan.token_limit:
            raise TokenLimitExceeded
        user_plan.tokens_used += amount
        user_plan.save(update_fields=['tokens_used'])


def enforce_client_limit(user):
    user_plan = UserPlan.active_for(user)
    if user_plan is None:
        raise NoActivePlan
    used = User.objects.filter(role=Roles.CLIENT, owner=user).count()
    if used >= user_plan.plan.client_limit:
        raise ClientLimitExceeded
    return user_plan
