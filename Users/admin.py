from django.contrib import admin

from Users.models import Plan, User, UserPlan


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ('username', 'email', 'role', 'is_staff', 'is_active')
    list_filter = ('role', 'is_active')


@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display = ('name', 'duration_type', 'client_limit', 'ai_access', 'token_limit')


@admin.register(UserPlan)
class UserPlanAdmin(admin.ModelAdmin):
    list_display = ('user', 'plan', 'is_active', 'start_date', 'end_date', 'tokens_used')
    list_filter = ('is_active', 'plan')
    search_fields = ('user__username',)
