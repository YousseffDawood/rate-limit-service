from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from Users.models import DurationType, Plan, Roles, User, UserPlan


PLAN_SPECS = [
    {'name': 'Basic', 'duration_type': DurationType.WEEK, 'client_limit': 50, 'ai_access': False, 'token_limit': 0},
    {'name': 'Pro', 'duration_type': DurationType.MONTH, 'client_limit': 200, 'ai_access': True, 'token_limit': 200_000},
    {'name': 'Premium', 'duration_type': DurationType.YEAR, 'client_limit': 1000, 'ai_access': True, 'token_limit': 2_000_000},
]

USER_SPECS = [
    {'username': 'user1', 'plan': 'Basic', 'clients': 3},
    {'username': 'user2', 'plan': 'Pro', 'clients': 2, 'tokens_used': 150_000},
    {'username': 'user3', 'plan': 'Premium', 'clients': 5},
    {'username': 'user4', 'plan': 'Pro', 'clients': 2},
    {'username': 'user5', 'plan': 'Basic', 'clients': 0, 'expired': True},
    {'username': 'user6', 'plan': None, 'clients': 0},
    {'username': 'user7', 'plan': 'Pro', 'clients': 2, 'tokens_used': 200_000},
    {'username': 'user8', 'plan': 'Premium', 'clients': 3},
    {'username': 'user9', 'plan': 'Basic', 'clients': 1},
    {'username': 'user10', 'plan': 'Pro', 'clients': 2},
]

PASSWORD = 'testpass123'


class Command(BaseCommand):
    def handle(self, *args, **options):
        for spec in PLAN_SPECS:
            Plan.objects.get_or_create(name=spec['name'], defaults=spec)

        admin_user, created = User.objects.get_or_create(
            username='admin',
            defaults={'role': Roles.ADMIN, 'is_superuser': True, 'is_staff': True, 'email': 'admin@example.com'},
        )
        if created:
            admin_user.set_password('adminpass123')
            admin_user.save()

        client_index = 1
        today = timezone.localdate()
        for spec in USER_SPECS:
            user, created = User.objects.get_or_create(
                username=spec['username'],
                defaults={'role': Roles.USER, 'email': f"{spec['username']}@example.com"},
            )
            if created:
                user.set_password(PASSWORD)
                user.save()
            self._assign_plan(user, spec, today)

            for _ in range(spec['clients']):
                username = f'client{client_index}'
                client, created = User.objects.get_or_create(
                    username=username,
                    defaults={'role': Roles.CLIENT, 'owner': user, 'email': f'{username}@example.com'},
                )
                if created:
                    client.set_password(PASSWORD)
                    client.save()
                client_index += 1

    def _assign_plan(self, user, spec, today):
        plan_name = spec['plan']
        if plan_name is None:
            return
        plan = Plan.objects.get(name=plan_name)
        if spec.get('expired'):
            start = today - timedelta(days=30)
            end = today - timedelta(days=2)
        else:
            start = today
            end = plan.end_date_from(start)
        UserPlan.objects.update_or_create(
            user=user,
            is_active=True,
            defaults={'plan': plan, 'start_date': start, 'end_date': end, 'tokens_used': spec.get('tokens_used', 0)},
        )
