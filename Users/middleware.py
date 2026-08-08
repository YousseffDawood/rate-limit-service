import json

from django.conf import settings
from django.contrib.auth import get_user_model
from django.http import JsonResponse
from django.utils import timezone

from Users.models import Roles, UserPlan


class PlanAccessMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if self._should_bypass(request):
            return self.get_response(request)

        if request.method == 'POST' and request.path == getattr(settings, 'LOGIN_URL', '/api/login/'):
            user = self._resolve_login_user(request)
            if user and user.role != Roles.ADMIN and self._plan_invalid(user):
                return self._forbidden(user)

        if request.user.is_authenticated and request.user.role != Roles.ADMIN:
            if self._plan_invalid(request.user):
                return self._forbidden(request.user)

        return self.get_response(request)

    def _should_bypass(self, request):
        for prefix in ('/admin/', '/static/', '/media/'):
            if request.path.startswith(prefix):
                return True
        return False

    def _resolve_login_user(self, request):
        try:
            data = json.loads(request.body)
        except (ValueError, AttributeError):
            return None
        username = data.get('username')
        if not username:
            return None
        return get_user_model().objects.filter(username=username).first()

    def _plan_invalid(self, user):
        user_plan = UserPlan.active_for(user)
        if user_plan is None:
            return True
        return user_plan.end_date < timezone.now().date()

    def _forbidden(self, user):
        user_plan = UserPlan.active_for(user)
        if user_plan is None:
            return JsonResponse({'detail': 'No active plan.'}, status=403)
        return JsonResponse(
            {'detail': f'Your plan expired on {user_plan.end_date}. Please renew to regain access.'},
            status=403,
        )
