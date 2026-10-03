from django.conf import settings
from django.conf.urls.i18n import i18n_patterns
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.staticfiles.urls import staticfiles_urlpatterns
from django.urls import include
from django.urls import path
from django.views import defaults as default_views
from drf_spectacular.views import SpectacularAPIView
from drf_spectacular.views import SpectacularSwaggerView
from rest_framework.authtoken.views import obtain_auth_token

from farmio.core.views import HomeView  # nouvelle vue, voir plus bas

# --------------------------------------------------------------------------
# URLs NON traduisibles (admin, media, API technique)
# --------------------------------------------------------------------------
urlpatterns = [
    path(settings.ADMIN_URL, admin.site.urls),
    *static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT),
]

# --------------------------------------------------------------------------
# URLs traduisibles — UNE SEULE inclusion de chaque app, jamais en double.
# prefix_default_language=False : le français (langue par défaut) n'a pas
# de préfixe /fr/, seul l'anglais aura /en/.
# --------------------------------------------------------------------------
urlpatterns += i18n_patterns(
    path("", HomeView.as_view(), name="home"),
    path(
        "about/",
        HomeView.as_view(template_name="common/pages/about.html"),
        name="about",
    ),
    path("accounts/", include("farmio.users.urls", namespace="users")),
    path("dashboard/", include("farmio.dashboard.urls", namespace="dashboard")),
    path("catalog/", include("farmio.catalog.urls", namespace="catalog")),
    path("cart/", include("farmio.cart.urls", namespace="cart")),
    path("orders/", include("farmio.orders.urls", namespace="orders")),
    path("payments/", include("farmio.payments.urls", namespace="payments")),
    path("reviews/", include("farmio.reviews.urls", namespace="reviews")),
    path(
        "notifications/",
        include("farmio.notifications.urls", namespace="notifications"),
    ),
    path("messages/", include("farmio.messaging.urls", namespace="messaging")),
    prefix_default_language=False,
)

if settings.DEBUG:
    urlpatterns += staticfiles_urlpatterns()

# --------------------------------------------------------------------------
# API (non traduisible : pas de sens à préfixer /fr/api/)
# --------------------------------------------------------------------------
urlpatterns += [
    path("payments/stripe/webhook/", include("farmio.payments.webhook_urls")),
    path("api/", include("config.api_router")),
    path("api/auth-token/", obtain_auth_token, name="obtain_auth_token"),
    path("api/schema/", SpectacularAPIView.as_view(), name="api-schema"),
    path(
        "api/docs/",
        SpectacularSwaggerView.as_view(url_name="api-schema"),
        name="api-docs",
    ),
]

if settings.DEBUG:
    urlpatterns += [
        path(
            "400/",
            default_views.bad_request,
            kwargs={"exception": Exception("Bad Request!")},
        ),
        path(
            "403/",
            default_views.permission_denied,
            kwargs={"exception": Exception("Permission Denied")},
        ),
        path(
            "404/",
            default_views.page_not_found,
            kwargs={"exception": Exception("Page not Found")},
        ),
        path("500/", default_views.server_error),
    ]

if "debug_toolbar" in settings.INSTALLED_APPS:
    import debug_toolbar

    urlpatterns = [path("__debug__/", include(debug_toolbar.urls)), *urlpatterns]

handler403 = "farmio.core.views.csrf_failure"
