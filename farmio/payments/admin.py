from django.contrib import admin

from farmio.payments.models import PaymentTransaction


@admin.register(PaymentTransaction)
class PaymentTransactionAdmin(admin.ModelAdmin):
	list_display = ("id", "order", "provider", "method", "amount", "status", "initiated_at")
	list_filter = ("provider", "method", "status", "transaction_type")
	search_fields = ("order__reference", "provider_reference", "provider_transaction_id")
	readonly_fields = ("created_at", "updated_at", "initiated_at", "processed_at")
