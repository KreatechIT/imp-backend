from rest_framework.generics import GenericAPIView

from apps.leaderboard import helper_functions, serializers_get
from base import responses
from core import permissions
from core.pagination import StandardPagination

TOP_RANKING_LIMIT = 20


class RankingView(GenericAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = serializers_get.RankingRowSerializer

    def get(self, request, *args, **kwargs):
        rows = helper_functions.ranking_rows()[:TOP_RANKING_LIMIT]

        data = self.serializer_class(rows, many=True, context={"request": self.request}).data
        return responses.SuccessResponse(data=data).get_response()


class AllRankingView(GenericAPIView):
    permission_classes = [permissions.IsAdmin]
    serializer_class = serializers_get.RankingRowSerializer
    pagination_class = StandardPagination

    def get(self, request, *args, **kwargs):
        rows = helper_functions.ranking_rows()

        paginator = self.pagination_class()
        page = paginator.paginate_queryset(rows, request, view=self)

        data = {
            "count": paginator.page.paginator.count,
            "next": paginator.get_next_link(),
            "previous": paginator.get_previous_link(),
            "results": self.serializer_class(
                page, many=True, context={"request": self.request},
            ).data,
        }
        return responses.SuccessResponse(data=data).get_response()


class MemberRankingView(GenericAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = serializers_get.MemberRankingSerializer
    item_key = "Member Id"

    def get(self, request, member_uuid=None, *args, **kwargs):
        ranking = helper_functions.member_ranking(member_uuid)
        if ranking is None:
            return responses.MissingItemError(
                item_key=self.item_key, item_id=member_uuid,
            ).get_response()

        data = self.serializer_class(ranking, context={"request": self.request}).data
        return responses.SuccessResponse(data=data).get_response()


class RankingKpiView(GenericAPIView):
    permission_classes = [permissions.IsAdmin]
    serializer_class = serializers_get.RankingKpiSerializer

    def get(self, request, *args, **kwargs):
        data = self.get_serializer(helper_functions.ranking_kpi()).data
        return responses.SuccessResponse(data=data).get_response()
