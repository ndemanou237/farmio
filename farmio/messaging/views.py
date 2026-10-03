from __future__ import annotations

import logging

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.db.models import Exists
from django.db.models import OuterRef
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.utils.translation import gettext_lazy as _
from django.views import View
from django.views.generic import DetailView
from django.views.generic import ListView

from farmio.messaging.models import Conversation
from farmio.messaging.services import ensure_conversation_access
from farmio.messaging.services import get_messages_after
from farmio.messaging.services import get_or_create_conversation_for_order
from farmio.messaging.services import send_message
from farmio.orders.models import Order

logger = logging.getLogger(__name__)


class ConversationListView(LoginRequiredMixin, ListView):
	template_name = "messaging/conversation_list.html"
	context_object_name = "conversations"
	paginate_by = 30

	def get_queryset(self):
		confirmed_orders = Order.objects.filter(
			buyer_id=OuterRef("buyer_id"),
			producer_id=OuterRef("producer_id"),
			status__in=["CONFIRMED", "IN_PROGRESS", "COMPLETED"],
			is_deleted=False,
		)
		return (
			Conversation.objects.filter(
				Q(buyer=self.request.user) | Q(producer=self.request.user),
			)
			.annotate(has_eligible_order=Exists(confirmed_orders))
			.filter(has_eligible_order=True)
			.select_related("buyer", "producer")
		)


class StartConversationView(LoginRequiredMixin, View):
	def get(self, request, order_id, *args, **kwargs):
		order = get_object_or_404(
			Order.objects.select_related("buyer", "producer"),
			pk=order_id,
			is_deleted=False,
		)
		conversation = get_or_create_conversation_for_order(order, request.user)
		return redirect("messaging:detail", pk=conversation.pk)


class ConversationDetailView(LoginRequiredMixin, DetailView):
	model = Conversation
	template_name = "messaging/conversation_detail.html"
	context_object_name = "conversation"

	def get_queryset(self):
		return Conversation.objects.select_related("buyer", "producer")

	def get_object(self, queryset=None):
		conversation = super().get_object(queryset)
		ensure_conversation_access(conversation, self.request.user)
		return conversation

	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)
		context["messages"] = get_messages_after(
			self.object,
			self.request.user,
		)
		context["other_party"] = (
			self.object.producer
			if self.request.user.pk == self.object.buyer_id
			else self.object.buyer
		)
		return context


class ConversationPollView(LoginRequiredMixin, View):
	def get(self, request, pk, *args, **kwargs):
		conversation = get_object_or_404(
			Conversation.objects.select_related("buyer", "producer"),
			pk=pk,
		)
		try:
			serialized = get_messages_after(
				conversation,
				request.user,
				request.GET.get("after_id") or None,
			)
		except PermissionDenied:
			raise
		except ValueError as exc:
			return JsonResponse({"error": str(exc)}, status=400)

		return JsonResponse(
			{
				"messages": [
					{
						"id": str(message.pk),
						"author_id": str(message.author_id),
						"author": message.author.get_full_name(),
						"content": message.content,
						"created_at": message.created_at.isoformat(),
						"is_mine": message.author_id == request.user.pk,
					}
					for message in serialized
				],
			},
		)


class SendMessageView(LoginRequiredMixin, View):
	def post(self, request, pk, *args, **kwargs):
		conversation = get_object_or_404(
			Conversation.objects.select_related("buyer", "producer"),
			pk=pk,
		)
		try:
			send_message(conversation, request.user, request.POST.get("content", ""))
		except PermissionDenied:
			raise
		except ValueError as exc:
			messages.error(request, str(exc))
		else:
			messages.success(request, _("Votre message a été envoyé."))
		return redirect("messaging:detail", pk=conversation.pk)
# Create your views here.
