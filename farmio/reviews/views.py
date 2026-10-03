from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.shortcuts import render
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.views import View
from django.views.generic import ListView

from farmio.orders.models import Order
from farmio.reviews.forms import ReviewForm
from farmio.reviews.models import Review
from farmio.reviews.models import ReviewModeration
from farmio.reviews.models import ReviewModerationStatus
from farmio.reviews.services import ReviewSubmissionError
from farmio.reviews.services import submit_order_review
from farmio.users.permissions import AdminRequiredMixin
from farmio.users.permissions import BuyerRequiredMixin
from farmio.utils.enums import OrderStatus


class ReviewSubmitView(LoginRequiredMixin, BuyerRequiredMixin, View):
    http_method_names = ["post"]

    def post(self, request, order_id, *args, **kwargs):
        order = get_object_or_404(
            Order.objects.select_related(
                "buyer",
                "producer",
                "producer__producer_profile",
            ).prefetch_related("lines__product"),
            pk=order_id,
            buyer=request.user,
            is_deleted=False,
        )
        if order.status != OrderStatus.COMPLETED:
            messages.error(
                request,
                _("Un avis est possible uniquement après la réception de la commande."),
            )
            return redirect("orders:detail", pk=order.pk)
        if Review.objects.filter(order=order, buyer=request.user).exists():
            messages.error(
                request,
                _("Vous avez déjà donné votre avis pour cette commande."),
            )
            return redirect("orders:detail", pk=order.pk)

        form = ReviewForm(request.POST)
        if not form.is_valid():
            return render(
                request,
                "orders/order_detail.html",
                {"order": order, "review_form": form},
                status=400,
            )
        try:
            submit_order_review(
                order.pk,
                request.user,
                rating=int(form.cleaned_data["rating"]),
                comment=form.cleaned_data["comment"],
            )
        except (PermissionDenied, ReviewSubmissionError) as exc:
            messages.error(request, str(exc))
        else:
            messages.success(
                request,
                _("Votre avis a été envoyé et sera publié après modération."),
            )
        return redirect("orders:detail", pk=order.pk)


class ReviewModerationListView(LoginRequiredMixin, AdminRequiredMixin, ListView):
    template_name = "reviews/moderation_list.html"
    context_object_name = "reviews"
    paginate_by = 30

    def get_queryset(self):
        queryset = Review.all_objects.select_related(
            "buyer",
            "producer",
            "order",
            "moderation",
            "moderation__moderated_by",
        )
        selected_status = self.request.GET.get(
            "status",
            ReviewModerationStatus.PENDING,
        )
        valid_statuses = {value for value, _label in ReviewModerationStatus.choices}
        if selected_status not in valid_statuses:
            selected_status = ReviewModerationStatus.PENDING
        return queryset.filter(moderation__status=selected_status).order_by(
            "-created_at",
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["selected_status"] = self.request.GET.get(
            "status",
            ReviewModerationStatus.PENDING,
        )
        context["status_choices"] = ReviewModerationStatus.choices
        context["action_labels"] = [
            ("approve", _("Approuver")),
            ("reject", _("Rejeter")),
            ("hide", _("Masquer")),
        ]
        return context


class ReviewModerationActionView(LoginRequiredMixin, AdminRequiredMixin, View):
    http_method_names = ["post"]
    actions = {"approve", "reject", "hide"}

    def post(self, request, pk, *args, **kwargs):
        decision = request.POST.get("decision", "")
        if decision not in self.actions:
            raise PermissionDenied(_("Action de modération invalide."))

        with transaction.atomic():
            review = get_object_or_404(
                Review.all_objects.select_for_update(),
                pk=pk,
            )
            moderation, _created = (
                ReviewModeration.objects.select_for_update().get_or_create(
                    review=review,
                    defaults={"created_by": request.user},
                )
            )
            moderation.status = {
                "approve": ReviewModerationStatus.APPROVED,
                "reject": ReviewModerationStatus.REJECTED,
                "hide": ReviewModerationStatus.HIDDEN,
            }[decision]
            moderation.moderated_by = request.user
            moderation.moderated_at = timezone.now()
            moderation.updated_by = request.user
            moderation.save(
                update_fields=[
                    "status",
                    "moderated_by",
                    "moderated_at",
                    "updated_by",
                    "updated_at",
                ],
            )
            review.is_deleted = decision == "hide"
            review.updated_by = request.user
            review.save(update_fields=["is_deleted", "updated_by", "updated_at"])

        messages.success(request, _("La modération de l'avis a été enregistrée."))
        return redirect("reviews:moderation-list")
