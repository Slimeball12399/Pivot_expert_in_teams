from django import forms
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.forms import AdminUserCreationForm, UserChangeForm
from django.contrib.auth.models import Group

from .models import AdminProfile, SpeakerProfile, User


# The default user forms are built around `username`, so point them at our model.
class UserCreationForm(AdminUserCreationForm):
    class Meta:
        model = User
        fields = ["email", "first_name", "last_name", "role"]


class UserEditForm(UserChangeForm):
    class Meta:
        model = User
        fields = "__all__"


class AdminProfileInline(admin.StackedInline):
    model = AdminProfile
    can_delete = False
    verbose_name_plural = "Admin profile"


class SpeakerProfileInline(admin.StackedInline):
    model = SpeakerProfile
    fk_name = "user"
    can_delete = False
    verbose_name_plural = "Speaker profile"


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    form = UserEditForm
    add_form = UserCreationForm

    list_display = ["email", "first_name", "last_name", "role", "is_active", "is_superuser"]
    list_filter = ["role", "is_active", "is_superuser"]
    search_fields = ["email", "first_name", "last_name"]
    ordering = ["email"]

    # Edit page. groups and user_permissions are left out on purpose (we use `role`).
    fieldsets = [
        (None, {"fields": ["email", "password"]}),
        ("Personal info", {"fields": ["first_name", "last_name", "phone_number"]}),
        ("Role and access", {"fields": ["role", "is_active", "is_staff", "is_superuser"]}),
        ("Dates", {"fields": ["last_login", "date_joined"]}),
    ]
    # Create page.
    add_fieldsets = [
        (None, {
            "classes": ["wide"],
            "fields": [
                "email", "first_name", "last_name", "role",
                "usable_password", "password1", "password2",
            ],
        }),
    ]
    readonly_fields = ["last_login", "date_joined"]
    filter_horizontal = []

    def get_inlines(self, request, obj):
        # Only show the profile that matches the user's role, and none on the create page.
        if obj is None:
            return []
        if obj.role == User.Role.ADMIN:
            return [AdminProfileInline]
        return [SpeakerProfileInline]

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        # Admins created or edited here get their profile automatically, like createsuperuser.
        if obj.role == User.Role.ADMIN:
            AdminProfile.objects.get_or_create(user=obj)


admin.site.unregister(Group)
