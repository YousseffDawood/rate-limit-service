from django.utils import timezone
from rest_framework.permissions import BasePermission

from Users.models import Roles, UserPlan


class HasAdminRole(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == Roles.ADMIN


class HasValidPlan(BasePermission):
    message = 'No active plan.'

    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        user_plan = UserPlan.active_for(request.user)
        if user_plan is None:
            self.message = 'No active plan.'
            return False
        if user_plan.end_date < timezone.now().date():
            self.message = f'Your plan expired on {user_plan.end_date}. Please renew to regain access.'
            return False
        self._user_plan = user_plan  # cache for subclasses — avoids a second DB query
        return True


class HasAIAccess(HasValidPlan):
    message = 'AI access is not enabled on your plan.'

    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        return self._user_plan.plan.ai_access


class HasTokenBudget(HasValidPlan):
    message = 'Token limit reached for this plan period.'

    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        user_plan = self._user_plan
        # token_limit == 0 means this plan has no token feature at all
        if user_plan.plan.token_limit == 0:
            return False
        return user_plan.tokens_used < user_plan.plan.token_limit
