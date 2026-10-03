from django.urls import path

from . import views

app_name = "users"

urlpatterns = [
    # Vues standard cookiecutter-django
    path("~redirect/", view=views.user_redirect_view, name="redirect"),
    path("~update/", view=views.user_update_view, name="update"),
    path("<int:pk>/", view=views.user_detail_view, name="detail"),
    # Inscription
    path("signup/", views.SignupLandingView.as_view(), name="signup"),
    path("signup/buyer/", views.BuyerSignupView.as_view(), name="signup-buyer"),
    path(
        "signup/producer/",
        views.ProducerSignupView.as_view(),
        name="signup-producer",
    ),
    # OTP
    path("otp/verify/", views.OtpVerifyView.as_view(), name="otp-verify"),
    path("otp/resend/", views.OtpResendView.as_view(), name="otp-resend"),
    # Connexion / déconnexion
    path("login/", views.FarmioLoginView.as_view(), name="login"),
    path("logout/", views.FarmioLogoutView.as_view(), name="logout"),
    path(
        "post-login/",
        views.PostLoginRedirectView.as_view(),
        name="post_login_redirect",
    ),
    path(
        "pending-approval/",
        views.PendingApprovalView.as_view(),
        name="pending_approval",
    ),
    path(
        "account-blocked/",
        views.AccountBlockedView.as_view(),
        name="account_blocked",
    ),
    # Profil
    path("profile/", views.ProfileDetailView.as_view(), name="profile-detail"),
    path("profile/edit/", views.ProfileUpdateView.as_view(), name="profile-update"),
    # Mot de passe
    path(
        "password/change/",
        views.PasswordChangeView.as_view(),
        name="password-change",
    ),
    path(
        "password/reset/",
        views.PasswordResetRequestView.as_view(),
        name="password-reset-request",
    ),
    path(
        "password/reset/done/",
        views.PasswordResetDoneView.as_view(),
        name="password-reset-done",
    ),
    path(
        "password/reset/confirm/<uidb64>/<token>/",
        views.PasswordResetConfirmView.as_view(),
        name="password-reset-confirm",
    ),
    path(
        "password/reset/complete/",
        views.PasswordResetCompleteView.as_view(),
        name="password-reset-complete",
    ),
    # Approbation producteur (admin)
    path(
        "admin/producers/",
        views.ProducerReviewListView.as_view(),
        name="producer-review-list",
    ),
    path(
        "admin/producers/<uuid:pk>/",
        views.ProducerReviewDetailView.as_view(),
        name="producer-review-detail",
    ),
    path(
        "admin/producers/<uuid:pk>/suspend/",
        views.ProducerSuspendView.as_view(),
        name="producer-suspend",
    ),
]
