from rest_framework.generics import GenericAPIView
from rest_framework.serializers import ValidationError

from apps.earnings import helper_functions, serializers_create, serializers_get
from base import responses
from core import permissions
from core.pagination import StandardPagination


class EarningsView(GenericAPIView):
    """This month's earnings for one member."""

    permission_classes = [permissions.IsAuthenticated]
    serializer_class = serializers_get.EarningsSerializer

    def get(self, request, member_uuid=None, *args, **kwargs):
        breakdown = helper_functions.earnings_breakdown(member_uuid)

        data = self.serializer_class(breakdown, context={"request": self.request}).data
        return responses.SuccessResponse(data=data).get_response()


class MissedView(GenericAPIView):
    """This month's missed days for one member."""

    permission_classes = [permissions.IsAuthenticated]
    serializer_class = serializers_get.MissedSerializer

    def get(self, request, member_uuid=None, *args, **kwargs):
        breakdown = helper_functions.missed_breakdown(member_uuid)

        data = self.serializer_class(breakdown, context={"request": self.request}).data
        return responses.SuccessResponse(data=data).get_response()


class EarningsStatisticsView(GenericAPIView):
    """Every member's earnings for a month, with the KPI totals alongside."""

    permission_classes = [permissions.IsAdmin]
    serializer_class = serializers_get.StatisticsRowSerializer
    pagination_class = StandardPagination

    def get(self, request, *args, **kwargs):
        query = serializers_create.StatisticsQuerySerializer(
            data=request.query_params
        )
        try:
            query.is_valid(raise_exception=True)
        except ValidationError as e:
            return responses.InvalidDataError(details=e.detail).get_response()
        filters = query.validated_data

        summary, rows = helper_functions.statistics(
            month_key=filters.get("month"),
            search=filters.get("search"),
            status=filters.get("status"),
            sort=filters.get("sort"),
            min_total=filters.get("min_total"),
            max_total=filters.get("max_total"),
        )

        paginator = self.pagination_class()
        page = paginator.paginate_queryset(rows, request, view=self)

        data = {
            "summary": serializers_get.StatisticsSummarySerializer(
                summary, context={"request": self.request},
            ).data,
            "count": paginator.page.paginator.count,
            "next": paginator.get_next_link(),
            "previous": paginator.get_previous_link(),
            "results": self.serializer_class(
                page, many=True, context={"request": self.request},
            ).data,
        }
        return responses.SuccessResponse(data=data).get_response()


class EarningsKpiView(GenericAPIView):
    permission_classes = [permissions.IsAdmin]
    serializer_class = serializers_get.EarningsKpiSerializer

    def get(self, request, *args, **kwargs):
        data = self.get_serializer(helper_functions.earnings_kpi()).data
        return responses.SuccessResponse(data=data).get_response()
