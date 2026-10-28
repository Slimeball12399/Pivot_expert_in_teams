from django import forms
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.forms import AdminUserCreationForm, UserChangeForm
from django.contrib.auth.models import Group

from .models import AdminProfile, Consent, SpeakerProfile, User


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

    list_display = ["email", "first_name", "last_name",
                    "role", "is_active", "is_superuser"]
    list_filter = ["role", "is_active", "is_superuser"]
    search_fields = ["email", "first_name", "last_name"]
    ordering = ["email"]

    # Edit page. groups and user_permissions are left out on purpose (we use `role`).
    fieldsets = [
        (None, {"fields": ["email", "password"]}),
        ("Personal info", {"fields": [
         "first_name", "last_name", "phone_number"]}),
        ("Role and access", {"fields": [
         "role", "is_active", "is_staff", "is_superuser"]}),
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


@admin.register(SpeakerProfile)
class SpeakerProfileAdmin(admin.ModelAdmin):
    list_display = ["user", "birth_date", "height_cm", "admin"]
    list_filter = ["admin"]
    search_fields = ["user__email", "user__first_name", "user__last_name"]
    list_select_related = ["user", "admin__user"]
    raw_id_fields = ["user"]


@admin.register(AdminProfile)
class AdminProfileAdmin(admin.ModelAdmin):
    list_display = ["user"]
    search_fields = ["user__email", "user__first_name", "user__last_name"]
    list_select_related = ["user"]
    raw_id_fields = ["user"]


@admin.register(Consent)
class ConsentAdmin(admin.ModelAdmin):
    """Read-only: consents are proof of what a user agreed to, so they are
    never added or edited by hand. Delete stays allowed, because Django's admin
    needs it to delete a user (their consents are removed with them)."""

    list_display = ["user", "purpose", "notice_version", "granted_at", "withdrawn_at"]
    list_filter = ["purpose", "notice_version", "withdrawn_at"]
    search_fields = ["user__email"]
    list_select_related = ["user"]
    date_hierarchy = "granted_at"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


admin.site.unregister(Group)
