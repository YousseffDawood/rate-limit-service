from datetime import timedelta

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models import Q


class Roles(models.TextChoices):
    ADMIN = 'admin', 'Admin'
    USER = 'user', 'User'
    CLIENT = 'client', 'Client'


class DurationType(models.TextChoices):
    WEEK = 'week', 'Week'
    MONTH = 'month', 'Month'
    YEAR = 'year', 'Year'


class User(AbstractUser):
    role = models.CharField(max_length=10, choices=Roles.choices, default=Roles.USER)
    owner = models.ForeignKey(
        'self',
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='owned_clients',
    )

    def save(self, *args, **kwargs):
        self.is_staff = self.is_superuser or self.role == Roles.ADMIN
        super().save(*args, **kwargs)


class Plan(models.Model):
    DURATION_DAYS = {
        DurationType.WEEK: 7,
        DurationType.MONTH: 30,
        DurationType.YEAR: 365,
    }

    name = models.CharField(max_length=100, unique=True)
    duration_type = models.CharField(max_length=10, choices=DurationType.choices)
    client_limit = models.PositiveIntegerField()
    ai_access = models.BooleanField(default=False)
    token_limit = models.BigIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def end_date_from(self, start_date):
        return start_date + timedelta(days=self.DURATION_DAYS[self.duration_type])


class UserPlan(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='user_plans')
    plan = models.ForeignKey(Plan, on_delete=models.PROTECT, related_name='user_plans')
    is_active = models.BooleanField(default=True)
    start_date = models.DateField()
    end_date = models.DateField()
    tokens_used = models.BigIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['user'],
                condition=Q(is_active=True),
                name='one_active_plan_per_user',
            ),
        ]

    def save(self, *args, **kwargs):
        if self.is_active:
            UserPlan.objects.filter(user=self.user, is_active=True).exclude(pk=self.pk).update(is_active=False)
        super().save(*args, **kwargs)

    @classmethod
    def active_for(cls, user):
        return cls.objects.filter(user=user, is_active=True).first()
