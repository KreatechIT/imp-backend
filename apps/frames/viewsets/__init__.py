from apps.frames.viewsets.crmview import (
    FrameLibraryViewSet,
    FramePostDeskViewSet,
    FrameViewSet,
    MemberContentViewSet,
)
from apps.frames.viewsets.member import (
    FrameByJobViewSet,
    FrameRenderViewSet,
    MemberFrameViewSet,
    MemberPostDeskFrameViewSet,
    PostDeskRenderViewSet,
    SourceVideoViewSet,
)

__all__ = [
    "FrameViewSet",
    "FrameLibraryViewSet",
    "FramePostDeskViewSet",
    "MemberContentViewSet",
    "FrameByJobViewSet",
    "MemberFrameViewSet",
    "MemberPostDeskFrameViewSet",
    "SourceVideoViewSet",
    "FrameRenderViewSet",
    "PostDeskRenderViewSet",
]
