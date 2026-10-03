from django.contrib import admin
from django.contrib.auth import admin as auth_admin
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _

from .forms import UserAdminChangeForm
from .forms import UserAdminCreationForm
from .models import BuyerProfile
from .models import Location
from .models import OtpCode
from .models import ProducerProfile

User = get_user_model()


@admin.register(User)
class UserAdmin(auth_admin.UserAdmin):
    form = UserAdminChangeForm
    add_form = UserAdminCreationForm
    ordering = ["id"]
    list_display = [
        "email",
        "name",
        "is_producer",
        "is_buyer",
        "is_email_verified",
        "is_approved",
        "is_active",
    ]
    list_filter = [
        "is_producer",
        "is_buyer",
        "is_email_verified",
        "is_approved",
        "is_active",
    ]
    search_fields = ["name", "email"]
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        (
            _("Informations personnelles"),
            {"fields": ("name", "phone_number", "location")},
        ),
        (
            _("Rôles & statut"),
            {"fields": ("is_producer", "is_buyer", "is_email_verified", "is_approved")},
        ),
        (
            _("Permissions"),
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                ),
            },
        ),
        (_("Dates importantes"), {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (None, {"classes": ("wide",), "fields": ("email", "password1", "password2")}),
    )

    actions = ["approve_producers", "suspend_accounts", "reactivate_accounts"]

    @admin.action(description=_("Approuver les producteurs sélectionnés"))
    def approve_producers(self, request, queryset):
        queryset.filter(is_producer=True).update(is_approved=True)

    @admin.action(description=_("Suspendre les comptes sélectionnés"))
    def suspend_accounts(self, request, queryset):
        queryset.update(is_active=False)

    @admin.action(description=_("Réactiver les comptes sélectionnés"))
    def reactivate_accounts(self, request, queryset):
        queryset.update(is_active=True)


@admin.register(ProducerProfile)
class ProducerProfileAdmin(admin.ModelAdmin):
    list_display = ["company_name", "user", "reviewed_by", "reviewed_at"]
    search_fields = ["company_name", "user__email"]
    autocomplete_fields = ["user", "reviewed_by"]


@admin.register(BuyerProfile)
class BuyerProfileAdmin(admin.ModelAdmin):
    list_display = ["user", "organization_name"]
    search_fields = ["user__email", "organization_name"]
    autocomplete_fields = ["user"]


@admin.register(Location)
class LocationAdmin(admin.ModelAdmin):
    list_display = ["city", "region", "country"]
    search_fields = ["city", "region"]


@admin.register(OtpCode)
class OtpCodeAdmin(admin.ModelAdmin):
    list_display = [
        "user",
        "purpose",
        "created_at",
        "expires_at",
        "is_used",
        "attempts",
    ]
    list_filter = ["purpose", "is_used"]
    readonly_fields = [f.name for f in OtpCode._meta.fields] # noqa: SLF001
    search_fields = ["user__email", "code"]
