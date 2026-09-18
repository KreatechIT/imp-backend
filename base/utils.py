from django.contrib.contenttypes.models import ContentType

from base.models import AuditLog


def log_action(actor, action, target=None, status="success", detail=""):
    AuditLog.objects.create(
        actor=actor if actor and actor.is_authenticated else None,
        action=action,
        status=status,
        target_content_type=(
            ContentType.objects.get_for_model(target) if target is not None else None
        ),
        target_object_id=str(target.pk) if target is not None else None,
        detail=detail,
    )
