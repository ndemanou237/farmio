from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class DashboardConfig(AppConfig):
    """Configuration de l'app dashboard : tableaux de bord personnalisés par rôle."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "farmio.dashboard"
    verbose_name = _("Tableau de bord")
