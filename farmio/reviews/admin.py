from django.contrib import admin

from farmio.reviews.models import Review
from farmio.reviews.models import ReviewModeration


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = [
        "created_at",
        "buyer",
        "producer",
        "order",
        "rating",
        "is_deleted",
    ]
    list_filter = ["rating", "is_deleted", "created_at"]
    search_fields = [
        "buyer__email",
        "producer__email",
        "order__reference",
        "comment",
    ]
    raw_id_fields = ["buyer", "producer", "order"]
    readonly_fields = [
        "id",
        "created_at",
        "created_by",
        "updated_at",
        "updated_by",
        "is_deleted",
        "buyer",
        "producer",
        "order",
        "rating",
        "comment",
    ]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(ReviewModeration)
class ReviewModerationAdmin(admin.ModelAdmin):
    list_display = ["review", "status", "moderated_by", "moderated_at"]
    list_filter = ["status", "moderated_at"]
    search_fields = [
        "review__buyer__email",
        "review__producer__email",
        "review__order__reference",
    ]
    raw_id_fields = ["review", "moderated_by"]
    readonly_fields = [
        "id",
        "review",
        "status",
        "moderated_by",
        "moderated_at",
        "moderation_note",
        "created_at",
        "created_by",
        "updated_at",
        "updated_by",
        "is_deleted",
    ]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
