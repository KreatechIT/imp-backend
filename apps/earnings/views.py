from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.generics import GenericAPIView
from rest_framework.serializers import ValidationError

from apps.earnings import helper_functions, serializers_create, serializers_get
from base import responses
from core import permissions

MONTH_PARAM = OpenApiParameter(
    name="month",
    description="Month to report on, as YYYY-MM. Defaults to the current month.",
    required=False,
    type=str,
)


class MonthReportView(GenericAPIView):
    permission_classes = [permissions.IsAuthenticated]

    def get_month(self, request):
        serializer = serializers_create.MonthQuerySerializer(
            data=request.query_params
        )
        serializer.is_valid(raise_exception=True)
        return serializer.validated_data.get("month")


class EarningsView(MonthReportView):
    serializer_class = serializers_get.EarningsSerializer

    @extend_schema(parameters=[MONTH_PARAM])
    def get(self, request, member_uuid=None, *args, **kwargs):
        try:
            month = self.get_month(request)
        except ValidationError as e:
            return responses.InvalidDataError(details=e.detail).get_response()

        breakdown = helper_functions.earnings_breakdown(member_uuid, month)

        data = self.serializer_class(breakdown).data
        return responses.SuccessResponse(data=data).get_response()


class MissedView(MonthReportView):
    serializer_class = serializers_get.MissedSerializer

    @extend_schema(parameters=[MONTH_PARAM])
    def get(self, request, member_uuid=None, *args, **kwargs):
        try:
            month = self.get_month(request)
        except ValidationError as e:
            return responses.InvalidDataError(details=e.detail).get_response()

        breakdown = helper_functions.missed_breakdown(member_uuid, month)

        data = self.serializer_class(breakdown).data
        return responses.SuccessResponse(data=data).get_response()
