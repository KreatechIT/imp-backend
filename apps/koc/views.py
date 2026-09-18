from rest_framework.generics import GenericAPIView

from apps.frames.models import FrameAssignment
from apps.koc import models, serializers_get
from apps.third_party.models import ThirdPartyConnection
from base import responses
from core import permissions


class MemberKpiView(GenericAPIView):
    """KOC's own dashboard KPI tiles."""

    permission_classes = [permissions.IsAuthenticated]
    serializer_class = serializers_get.MemberKpiSerializer

    def get_member(self):
        return getattr(self.request.user, "member", None)

    def get(self, request, member_uuid=None, *args, **kwargs):
        member = self.get_member()
        if member is None or str(member.uuid) != str(member_uuid):
            return responses.MissingItemError(
                item_key="Member Id", item_id=member_uuid,
            ).get_response()

        data = {
            "assigned_frames": FrameAssignment.objects.filter(
                member=member, archived=None, frame__archived=None,
            ).count(),
            "total_submissions": models.Submission.objects.filter(member=member).count(),
            "connected_accounts": ThirdPartyConnection.objects.filter(
                member=member, archived=None,
            ).count(),
        }

        data = self.get_serializer(data).data
        return responses.SuccessResponse(data=data).get_response()
