from drf_spectacular.utils import extend_schema
from rest_framework.serializers import ValidationError
from rest_framework.mixins import CreateModelMixin, ListModelMixin, RetrieveModelMixin
from rest_framework.viewsets import GenericViewSet

from apps.jobs.helper_functions import media_type_for
from apps.koc import models, serializers_create, serializers_get
from apps.notifications import helper_functions as notifications
from base import responses
from base.utils import log_action
from core import permissions
from core.pagination import StandardPagination


class MemberSubmissionViewSet(CreateModelMixin, ListModelMixin, RetrieveModelMixin, GenericViewSet):
    """KOC's own Published Reel Link submissions.

    Create-only: there is no update/delete/partial_update here. Once a
    submission exists it is permanent.
    """

    serializer_class = serializers_get.SubmissionSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = StandardPagination
    lookup_field = "uuid"
    item_key = "Submission Id"

    def get_member(self):
        return getattr(self.request.user, "member", None)

    def get_queryset(self):
        member = self.get_member()
        if member is None:
            return models.Submission.objects.none()

        return (
            models.Submission.objects
            .filter(member=member, member__uuid=self.kwargs.get("member_uuid"))
            .order_by("-created")
        )

    @extend_schema(request=serializers_create.SubmissionCreateSerializer)
    def create(self, request, member_uuid=None, *args, **kwargs):
        serializer = serializers_create.SubmissionCreateSerializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
        except ValidationError as e:
            return responses.InvalidDataError(details=e.detail).get_response()
        validated = serializer.validated_data

        member = self.get_member()
        if member is None or str(member.uuid) != member_uuid:
            return responses.MissingItemError(
                item_key="Member Id", item_id=member_uuid,
            ).get_response()

        upload = validated["content_file"]

        submission = models.Submission.objects.create(
            member=member,
            content_file=upload,
            media_type=media_type_for(upload.name),
            platform=validated["platform"],
            published_url=validated["published_url"],
        )

        log_action(
            actor=request.user,
            action="submission.published_link_submitted",
            target=submission,
            detail=f"{member} submitted published Reel link {submission.published_url}",
        )

        notifications.notify_admins(
            notification_type=11,
            title="New KOC submission",
            message=f"{member} submitted a published Reel link",
        )

        data = self.serializer_class(submission, context={"request": self.request}).data
        return responses.CreatedSuccessResponse(data=data).get_response()
