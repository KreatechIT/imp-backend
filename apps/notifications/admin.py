from django.contrib import admin

from apps.notifications import models


@admin.register(models.Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("uuid", "recipient", "notification_type", "title", "read_at", "created")
    list_filter = ("notification_type", "role")
    search_fields = ("title", "message", "recipient__username")
