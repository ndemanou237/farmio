from __future__ import annotations

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth import login as auth_login
from django.contrib.auth import logout as auth_logout
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.tokens import default_token_generator
from django.contrib.messages.views import SuccessMessageMixin
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.urls import reverse
from django.urls import reverse_lazy
from django.utils import timezone
from django.utils.encoding import force_bytes
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode
from django.utils.http import urlsafe_base64_encode
from django.utils.translation import gettext_lazy as _
from django.views import View
from django.views.generic import DetailView
from django.views.generic import FormView
from django.views.generic import RedirectView
from django.views.generic import TemplateView
from django.views.generic import UpdateView

from farmio.utils.enums import OtpPurpose
from farmio.utils.enums import SecurityEventType
from farmio.utils.otp import OtpService
from farmio.utils.security import LoginThrottle
from farmio.utils.security import get_client_ip
from farmio.utils.security import log_security_event

from .forms import BuyerSignupForm
from .forms import FarmioLoginForm
from .forms import FarmioPasswordChangeForm
from .forms import OtpVerifyForm
from .forms import PasswordResetConfirmForm
from .forms import PasswordResetRequestForm
from .forms import ProducerProfileUpdateForm
from .forms import ProducerReviewForm
from .forms import ProducerSignupForm
from .forms import ProfileUpdateForm
from .models import OtpCode
from .models import ProducerProfile
from .permissions import AdminRequiredMixin
from .tasks import send_account_locked_email_task
from .tasks import send_otp_email_task
from .tasks import send_password_changed_notice_task
from .tasks import send_password_reset_email_task
from .tasks import send_producer_decision_email_task
from .tasks import send_welcome_email_task

User = get_user_model()

OTP_SESSION_KEY = "pending_otp_user_id"


# ==============================================================================
# Vues standard cookiecutter-django (conservées)
# ==============================================================================
class UserDetailView(LoginRequiredMixin, DetailView):
    model = User
    slug_field = "id"
    slug_url_kwarg = "id"


user_detail_view = UserDetailView.as_view()


class UserUpdateView(LoginRequiredMixin, SuccessMessageMixin, UpdateView):
    model = User
    fields = ["name"]
    success_message = _("Informations mises à jour.")

    def get_success_url(self):
        return self.request.user.get_absolute_url()

    def get_object(self):
        return self.request.user


user_update_view = UserUpdateView.as_view()


class UserRedirectView(LoginRequiredMixin, RedirectView):
    permanent = False

    def get_redirect_url(self):
        return reverse("users:detail", kwargs={"pk": self.request.user.pk})


user_redirect_view = UserRedirectView.as_view()


# ==============================================================================
# 1) INSCRIPTION
# ==============================================================================
class SignupLandingView(TemplateView):
    template_name = "users/pages/signup_landing.html"


class BuyerSignupView(FormView):
    template_name = "users/pages/signup_buyer.html"
    form_class = BuyerSignupForm
    success_url = reverse_lazy("users:otp-verify")

    def form_valid(self, form):
        with transaction.atomic():
            user = form.save()
        log_security_event(self.request, SecurityEventType.SIGNUP, user=user)
        return _start_email_verification(self.request, user)


class ProducerSignupView(FormView):
    """Inscription producteur"""

    template_name = "users/pages/signup_producer.html"
    form_class = ProducerSignupForm
    success_url = reverse_lazy("users:otp-verify")

    def form_valid(self, form):
        with transaction.atomic():
            user = form.save()
        log_security_event(self.request, SecurityEventType.SIGNUP, user=user)
        return _start_email_verification(self.request, user)


def _start_email_verification(request, user):
    """Génère un OTP (DB) """
    otp = OtpCode.generate_for(user, purpose=OtpPurpose.EMAIL_VERIFICATION)
    OtpService.start_cooldown(
        user.pk,
        OtpPurpose.EMAIL_VERIFICATION,
        _otp_cooldown_seconds(),
    )

    send_otp_email_task.delay(
        user_id=user.pk,
        code=otp.plaintext_code,
        purpose=OtpPurpose.EMAIL_VERIFICATION,
        validity_minutes=_otp_validity_minutes(),
    )
    log_security_event(request, SecurityEventType.OTP_REQUESTED, user=user)

    request.session[OTP_SESSION_KEY] = str(user.pk)
    messages.info(
        request,
        _("Un code de vérification a été envoyé à %(email)s.") % {"email": user.email},
    )
    return redirect("users:otp-verify")


def _otp_validity_minutes() -> int:
    return getattr(settings, "OTP_VALIDITY_MINUTES", 10)


def _otp_cooldown_seconds() -> int:
    return getattr(settings, "OTP_RESEND_COOLDOWN_SECONDS", 60)


# ==============================================================================
# 2) VÉRIFICATION EMAIL PAR OTP
# ==============================================================================
class OtpVerifyView(FormView):
    template_name = "users/pages/otp_verify.html"
    form_class = OtpVerifyForm

    def dispatch(self, request, *args, **kwargs):
        if not request.session.get(OTP_SESSION_KEY):
            messages.error(
                request,
                _("Aucune vérification en cours. Merci de vous inscrire."),
            )
            return redirect("users:signup")
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = get_object_or_404(User, pk=self.request.session[OTP_SESSION_KEY])
        ctx["email"] = user.email
        ctx["resend_cooldown"] = OtpService.remaining_cooldown_seconds(
            user.pk,
            OtpPurpose.EMAIL_VERIFICATION,
        )
        return ctx

    def form_valid(self, form):
        user = get_object_or_404(User, pk=self.request.session[OTP_SESSION_KEY])
        otp = (
            OtpCode.objects.filter(
                user=user,
                purpose=OtpPurpose.EMAIL_VERIFICATION,
                is_used=False,
            )
            .order_by("-created_at")
            .first()
        )

        if otp is None:
            messages.error(
                self.request,
                _("Aucun code actif. Merci d'en demander un nouveau."),
            )
            return redirect("users:otp-verify")

        success, error = otp.verify(form.cleaned_data["code"])
        if not success:
            log_security_event(self.request, SecurityEventType.OTP_FAILED, user=user)
            messages.error(self.request, error)
            return self.form_invalid(form)

        log_security_event(self.request, SecurityEventType.OTP_VERIFIED, user=user)

        user.is_email_verified = True
        user.save(update_fields=["is_email_verified"])
        del self.request.session[OTP_SESSION_KEY]

        auth_login(
            self.request,
            user,
            backend="django.contrib.auth.backends.ModelBackend",
        )
        log_security_event(self.request, SecurityEventType.LOGIN_SUCCESS, user=user)

        if user.is_producer and not user.is_approved:
            messages.success(
                self.request,
                _(
                    "Votre email est vérifié."
                    "Votre profil producteur est en cours d'examen.",
                ),
            )
        else:
            send_welcome_email_task.delay(
                user_id=user.pk,
                dashboard_url=self.request.build_absolute_uri(
                    user.get_post_login_redirect_url(),
                ),
            )
            messages.success(
                self.request,
                _("Votre compte est activé, bienvenue sur Farmio !"),
            )

        return redirect(user.get_post_login_redirect_url())


class OtpResendView(View):
    """Renvoie un OTP — protégé par le cooldown Redis (anti-spam)."""

    def post(self, request, *args, **kwargs):
        user_id = request.session.get(OTP_SESSION_KEY)
        if not user_id:
            return redirect("users:signup")

        if OtpService.is_on_cooldown(user_id, OtpPurpose.EMAIL_VERIFICATION):
            log_security_event(
                request,
                SecurityEventType.OTP_RATE_LIMITED,
                email="",
                metadata={"user_id": user_id},
            )
            messages.warning(
                request,
                _("Merci de patienter avant de redemander un code."),
            )
            return redirect("users:otp-verify")

        user = get_object_or_404(User, pk=user_id)
        otp = OtpCode.generate_for(user, purpose=OtpPurpose.EMAIL_VERIFICATION)
        OtpService.start_cooldown(
            user.pk,
            OtpPurpose.EMAIL_VERIFICATION,
            _otp_cooldown_seconds(),
        )

        send_otp_email_task.delay(
            user_id=user.pk,
            code=otp.plaintext_code,
            purpose=OtpPurpose.EMAIL_VERIFICATION,
            validity_minutes=_otp_validity_minutes(),
        )
        log_security_event(request, SecurityEventType.OTP_REQUESTED, user=user)
        messages.success(request, _("Un nouveau code vous a été envoyé."))
        return redirect("users:otp-verify")


# ==============================================================================
# 3) CONNEXION / DÉCONNEXION — avec protection anti-brute-force
# ==============================================================================
class FarmioLoginView(FormView):
    """Vue de connexion custom """

    template_name = "users/pages/login.html"
    form_class = FarmioLoginForm

    def get(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect(request.user.get_post_login_redirect_url())
        return super().get(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["request"] = self.request
        return kwargs

    def form_valid(self, form):
        email = form.cleaned_data.get("username", "")

        ip_address = get_client_ip(self.request)
        if LoginThrottle.is_locked(email, ip_address):
            remaining = LoginThrottle.remaining_lockout_seconds(email, ip_address)
            log_security_event(
                self.request,
                SecurityEventType.LOGIN_LOCKED,
                email=email,
            )
            messages.error(
                self.request,
                _("Trop de tentatives échouées. Réessayez dans %(minutes)d minute(s).")
                % {"minutes": max(remaining // 60, 1)},
            )
            return self.form_invalid(form)

        user = form.get_user()
        auth_login(self.request, user)
        LoginThrottle.reset(email, ip_address)
        log_security_event(self.request, SecurityEventType.LOGIN_SUCCESS, user=user)
        return redirect(user.get_post_login_redirect_url())

    def form_invalid(self, form):
        email = form.data.get("username", "")
        if email and "__all__" in form.errors:
            # Échec de connexion (mauvais mot de passe) → on incrémente le compteur.
            attempts = LoginThrottle.register_failure(
                email,
                get_client_ip(self.request),
            )
            log_security_event(
                self.request,
                SecurityEventType.LOGIN_FAILED,
                email=email,
            )

            if attempts >= settings.LOGIN_MAX_ATTEMPTS:
                log_security_event(
                    self.request,
                    SecurityEventType.LOGIN_LOCKED,
                    email=email,
                )
                send_account_locked_email_task.delay(
                    email=email,
                    ip_address=get_client_ip(self.request),
                )
        return super().form_invalid(form)


class FarmioLogoutView(LoginRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        log_security_event(request, SecurityEventType.LOGOUT, user=request.user)
        auth_logout(request)
        messages.info(request, _("Vous avez été déconnecté."))
        return redirect("users:login")

    def get(self, request, *args, **kwargs):
        return self.post(request, *args, **kwargs)


class PostLoginRedirectView(LoginRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        return redirect(request.user.get_post_login_redirect_url())


class PendingApprovalView(LoginRequiredMixin, TemplateView):
    template_name = "users/pages/pending_approval.html"

    def get(self, request, *args, **kwargs):
        if request.user.can_sell:
            return redirect("dashboard:producer")
        return super().get(request, *args, **kwargs)


class AccountBlockedView(LoginRequiredMixin, TemplateView):
    template_name = "users/pages/account_blocked.html"


# ==============================================================================
# 4) PROFIL
# ==============================================================================
class ProfileDetailView(LoginRequiredMixin, TemplateView):
    template_name = "users/pages/profile_detail.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["producer_profile"] = getattr(self.request.user, "producer_profile", None)
        ctx["buyer_profile"] = getattr(self.request.user, "buyer_profile", None)
        return ctx


class ProfileUpdateView(LoginRequiredMixin, UpdateView):
    model = User
    form_class = ProfileUpdateForm
    template_name = "users/pages/profile_form.html"
    success_url = reverse_lazy("users:profile-detail")

    def get_object(self, queryset=None):
        return self.request.user

    def form_valid(self, form):
        messages.success(self.request, _("Votre profil a été mis à jour."))
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        if self.request.user.is_producer:
            ctx["producer_form"] = ProducerProfileUpdateForm(
                instance=self.request.user.producer_profile,
            )
        return ctx

    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        if request.user.is_producer and self.object:
            producer_form = ProducerProfileUpdateForm(
                request.POST,
                request.FILES,
                instance=request.user.producer_profile,
            )
            if producer_form.is_valid():
                producer_form.save()
        return response


# ==============================================================================
# 5) MOT DE PASSE
# ==============================================================================
class PasswordChangeView(LoginRequiredMixin, FormView):
    template_name = "users/pages/password_change.html"
    form_class = FarmioPasswordChangeForm
    success_url = reverse_lazy("users:profile-detail")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def form_valid(self, form):
        user = form.save()
        update_session_auth_hash(
            self.request,
            user,
        )  # évite la déconnexion involontaire
        log_security_event(self.request, SecurityEventType.PASSWORD_CHANGED, user=user)
        send_password_changed_notice_task.delay(user.pk)
        messages.success(self.request, _("Votre mot de passe a été modifié."))
        return super().form_valid(form)


class PasswordResetRequestView(FormView):
    template_name = "users/pages/password_reset_request.html"
    form_class = PasswordResetRequestForm
    success_url = reverse_lazy("users:password-reset-done")

    def form_valid(self, form):
        email = form.cleaned_data["email"]
        user = User.objects.filter(email__iexact=email).first()
        if user is not None:
            uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
            token = default_token_generator.make_token(user)
            reset_url = self.request.build_absolute_uri(
                reverse(
                    "users:password-reset-confirm",
                    kwargs={"uidb64": uidb64, "token": token},
                ),
            )
            send_password_reset_email_task.delay(
                user_id=user.pk,
                reset_url=reset_url,
            )
            log_security_event(
                self.request,
                SecurityEventType.PASSWORD_RESET_REQUESTED,
                user=user,
            )
        # Même comportement qu'un compte existe ou non (anti-énumération de comptes).
        return super().form_valid(form)


class PasswordResetDoneView(TemplateView):
    template_name = "users/pages/password_reset_done.html"


class PasswordResetConfirmView(FormView):
    template_name = "users/pages/password_reset_confirm.html"
    form_class = PasswordResetConfirmForm
    success_url = reverse_lazy("users:password-reset-complete")

    def dispatch(self, request, *args, **kwargs):
        self.user = self._get_user(kwargs.get("uidb64"))
        valid_link = self.user is not None and default_token_generator.check_token(
            self.user,
            kwargs.get("token"),
        )
        if not valid_link:
            messages.error(
                request,
                _("Le lien de réinitialisation est invalide ou a expiré."),
            )
            return redirect("users:password-reset-request")
        return super().dispatch(request, *args, **kwargs)

    @staticmethod
    def _get_user(uidb64):
        try:
            uid = force_str(urlsafe_base64_decode(uidb64))
            return User.objects.get(pk=uid)
        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            return None

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.user
        return kwargs

    def form_valid(self, form):
        form.save()
        log_security_event(
            self.request,
            SecurityEventType.PASSWORD_RESET_COMPLETED,
            user=self.user,
        )
        send_password_changed_notice_task.delay(self.user.pk)
        return super().form_valid(form)


class PasswordResetCompleteView(TemplateView):
    template_name = "users/pages/password_reset_complete.html"


# ==============================================================================
# 6) APPROBATION PRODUCTEUR (ADMIN)
# ==============================================================================
class ProducerReviewListView(AdminRequiredMixin, TemplateView):
    template_name = "dashboard/pages/producer_review_list.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["pending_producers"] = ProducerProfile.objects.filter(
            user__is_producer=True,
            user__is_email_verified=True,
            user__is_approved=False,
        ).select_related("user", "user__location")
        return ctx


class ProducerReviewDetailView(AdminRequiredMixin, FormView):
    template_name = "dashboard/pages/producer_review_detail.html"
    form_class = ProducerReviewForm

    def dispatch(self, request, *args, **kwargs):
        self.profile = get_object_or_404(ProducerProfile, pk=kwargs["pk"])
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["profile"] = self.profile
        return ctx

    def form_valid(self, form):
        decision = form.cleaned_data["decision"]
        reason = form.cleaned_data.get("reason", "")
        user = self.profile.user

        self.profile.reviewed_by = self.request.user
        self.profile.reviewed_at = timezone.now()

        if decision == "APPROVE":
            user.is_approved = True
            self.profile.rejection_reason = ""
            event = SecurityEventType.PRODUCER_APPROVED
            messages.success(self.request, _("Le producteur a été approuvé."))
        else:
            user.is_approved = False
            self.profile.rejection_reason = reason
            event = SecurityEventType.PRODUCER_REJECTED
            messages.success(self.request, _("Le producteur a été rejeté."))

        with transaction.atomic():
            user.save(update_fields=["is_approved"])
            self.profile.save(
                update_fields=["reviewed_by", "reviewed_at", "rejection_reason"],
            )
        log_security_event(self.request, event, user=user)

        send_producer_decision_email_task.delay(
            user_id=user.pk,
            approved=(decision == "APPROVE"),
            reason=reason,
        )
        return redirect("users:producer-review-list")


class ProducerSuspendView(AdminRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        profile = get_object_or_404(ProducerProfile, pk=kwargs["pk"])
        user = profile.user
        if not user.is_active:
            user.is_active = True
            event = SecurityEventType.ACCOUNT_REACTIVATED
            messages.success(request, _("Le compte producteur a été réactivé."))
        else:
            user.is_active = False
            event = SecurityEventType.ACCOUNT_SUSPENDED
            messages.success(request, _("Le compte producteur a été suspendu."))
        user.save(update_fields=["is_active"])
        log_security_event(request, event, user=user)
        return redirect("users:producer-review-list")
