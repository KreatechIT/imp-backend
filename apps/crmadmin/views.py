from datetime import datetime, time, timedelta

from django.utils import timezone
from rest_framework.generics import GenericAPIView
from rest_framework.serializers import ValidationError

from apps.crmadmin import serializers_create, serializers_get
from apps.jobs.models import Job, MemberTask
from apps.members.models import Member
from base import responses
from core import permissions


class DashboardKpiView(GenericAPIView):
    """CMS dashboard KPI tiles. Totals are a live snapshot; approved_submissions
    is the only tile scoped to [from_date, to_date]."""

    permission_classes = [permissions.IsAdmin]
    serializer_class = serializers_get.DashboardKpiSerializer

    def get(self, request, *args, **kwargs):
        query = serializers_create.DashboardKpiQuerySerializer(data=request.query_params)
        try:
            query.is_valid(raise_exception=True)
        except ValidationError as e:
            return responses.InvalidDataError(details=e.detail).get_response()
        from_date = query.validated_data["from_date"]
        to_date = query.validated_data["to_date"]

        start_datetime = timezone.make_aware(datetime.combine(from_date, time.min))
        end_datetime = timezone.make_aware(datetime.combine(to_date, time.min)) + timedelta(days=1)

        data = {
            "total_influencers": Member.objects.filter(archived=None).count(),
            "active_campaigns": Job.objects.filter(archived=None, status=2).count(),
            "pending_submissions": MemberTask.objects.filter(
                submitted_at__isnull=False, reviewed_at__isnull=True,
            ).count(),
            "approved_submissions": MemberTask.objects.filter(
                reviewed_at__gte=start_datetime,
                reviewed_at__lt=end_datetime,
                is_approved=True,
            ).count(),
        }

        data = self.get_serializer(data).data
        return responses.SuccessResponse(data=data).get_response()
