# accounts/admin.py

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.html import format_html
from .models import User, Education, WorkExperience, Skill, ShareableLink, ProfileView


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    model = User
    list_display = ['id', 'membership_id', 'email', 'full_name', 'status_badge', 'phone', 'created_at']
    list_filter = ['is_verified', 'is_blocked', 'is_staff', 'created_at']
    search_fields = ['email', 'first_name', 'last_name', 'membership_id', 'phone']
    ordering = ['-created_at']

    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Personal Info', {'fields': ('first_name', 'last_name', 'phone', 'profile_photo', 'resume')}),
        ('Membership', {'fields': ('membership_id', 'is_verified', 'is_blocked')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions',
                                    'initial_onboarding')}),
        ('Important dates', {'fields': ('last_login', 'date_joined', 'created_at', 'updated_at')}),
    )

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'password1', 'password2', 'is_staff', 'is_superuser', 'is_active', 'is_verified')}
        ),
    )

    readonly_fields = ['membership_id', 'created_at', 'updated_at', 'last_login', 'date_joined']

    def full_name(self, obj):
        return obj.get_full_name()
    full_name.short_description = 'Full Name'

    def status_badge(self, obj):
        status = obj.status
        colors = {
            'active': 'green',
            'pending': 'orange',
            'blocked': 'red'
        }
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; border-radius: 3px;">{}</span>',
            colors.get(status, 'gray'),
            status.upper()
        )
    status_badge.short_description = 'Status'

    actions = ['block_users', 'unblock_users', 'verify_users']

    def block_users(self, request, queryset):
        queryset.update(is_blocked=True, is_active=False)
        self.message_user(request, f"{queryset.count()} users blocked successfully.")
    block_users.short_description = "Block selected users"

    def unblock_users(self, request, queryset):
        for user in queryset:
            user.is_blocked = False
            if user.is_verified:
                user.is_active = True
            user.save()
        self.message_user(request, f"{queryset.count()} users unblocked successfully.")
    unblock_users.short_description = "Unblock selected users"

    def verify_users(self, request, queryset):
        queryset.update(is_verified=True, is_active=True)
        self.message_user(request, f"{queryset.count()} users verified successfully.")
    verify_users.short_description = "Verify selected users"


@admin.register(Education)
class EducationAdmin(admin.ModelAdmin):
    list_display = ['user', 'degree', 'institution', 'field_of_study', 'start_date', 'end_date', 'is_current']
    list_filter = ['is_current', 'start_date']
    search_fields = ['user__email', 'user__first_name', 'user__last_name', 'institution', 'degree']
    date_hierarchy = 'start_date'
    ordering = ['-start_date']


@admin.register(WorkExperience)
class WorkExperienceAdmin(admin.ModelAdmin):
    list_display = ['user', 'position', 'company', 'start_date', 'end_date', 'is_current']
    list_filter = ['is_current', 'start_date']
    search_fields = ['user__email', 'user__first_name', 'user__last_name', 'company', 'position']
    date_hierarchy = 'start_date'
    ordering = ['-start_date']


@admin.register(Skill)
class SkillAdmin(admin.ModelAdmin):
    list_display = ['user', 'name', 'proficiency']
    list_filter = ['proficiency']
    search_fields = ['user__email', 'name']


# @admin.register(Language)
# class LanguageAdmin(admin.ModelAdmin):
#     list_display = ['user', 'name', 'proficiency']
#     list_filter = ['proficiency']
#     search_fields = ['user__email', 'name']


@admin.register(ShareableLink)
class ShareableLinkAdmin(admin.ModelAdmin):
    list_display = ['user', 'token', 'created_at', 'expires_at', 'is_active', 'is_valid', 'view_count']
    list_filter = ['is_active', 'expiry_days', 'created_at']
    search_fields = ['user__email', 'user__first_name', 'user__last_name', 'token']
    readonly_fields = ['token', 'created_at', 'expires_at']
    date_hierarchy = 'created_at'
    ordering = ['-created_at']

    def view_count(self, obj):
        return obj.views.count()
    view_count.short_description = 'Views'


@admin.register(ProfileView)
class ProfileViewAdmin(admin.ModelAdmin):
    list_display = ['get_user', 'viewer_ip', 'viewed_at']
    list_filter = ['viewed_at']
    search_fields = ['shareable_link__user__email', 'viewer_ip']
    readonly_fields = ['shareable_link', 'viewer_ip', 'viewer_user_agent', 'viewed_at']
    date_hierarchy = 'viewed_at'
    ordering = ['-viewed_at']

    def get_user(self, obj):
        return obj.shareable_link.user.get_full_name()
    get_user.short_description = 'User'