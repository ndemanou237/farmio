from django.contrib import admin

from farmio.messaging.models import Conversation
from farmio.messaging.models import Message


class MessageInline(admin.TabularInline):
	model = Message
	extra = 0
	readonly_fields = ("created_at",)


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
	list_display = ("buyer", "producer", "last_activity_at")
	search_fields = ("buyer__email", "producer__email")
	inlines = (MessageInline,)
