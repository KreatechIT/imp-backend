from rest_framework import serializers

from apps.frames import models


class SourceVideoSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.SourceVideo
        fields = [
            "uuid",
            "original_file",
            "media_type",
            "original_name",
            "pull_status",
            "pull_failure_reason",
            "source_url",
            "created",
        ]


class MemberContentSerializer(serializers.ModelSerializer):
    member_uuid = serializers.UUIDField(source="member.uuid")
    member_name = serializers.CharField(source="member.full_name")
    member_phone_number = serializers.CharField(source="member.phone_number")
    member_role = serializers.SerializerMethodField()
    frame_uuid = serializers.UUIDField(source="frame.uuid")
    frame_name = serializers.CharField(source="frame.name")
    frame_type = serializers.IntegerField(source="frame.frame_type")
    org = serializers.SerializerMethodField()
    job_uuid = serializers.SerializerMethodField()
    job_title = serializers.SerializerMethodField()
    source_video_uuid = serializers.UUIDField(source="source_video.uuid")
    original_file = serializers.FileField(source="source_video.original_file", read_only=True)
    media_type = serializers.IntegerField(source="source_video.media_type", read_only=True)
    original_name = serializers.CharField(source="source_video.original_name", read_only=True)
    source_url = serializers.URLField(source="source_video.source_url", read_only=True)

    def get_member_role(self, obj):
        return obj.member.role.name if obj.member.role else None

    def get_org(self, obj):
        job = obj.frame.job
        return job.company.name if job else None

    def get_job_uuid(self, obj):
        job = obj.frame.job
        return job.uuid if job else None

    def get_job_title(self, obj):
        job = obj.frame.job
        return job.title if job else None

    class Meta:
        model = models.RenderedContent
        fields = [
            "uuid",
            "member_uuid",
            "member_name",
            "member_phone_number",
            "member_role",
            "frame_uuid",
            "frame_name",
            "frame_type",
            "org",
            "job_uuid",
            "job_title",
            "source_video_uuid",
            "original_file",
            "media_type",
            "original_name",
            "source_url",
            "rendered_file",
            "render_status",
            "created",
        ]


class RenderDetailSerializer(serializers.ModelSerializer):
    frame_uuid = serializers.UUIDField(source="frame.uuid")
    frame_name = serializers.CharField(source="frame.name")
    source_video_uuid = serializers.UUIDField(source="source_video.uuid")

    class Meta:
        model = models.RenderedContent
        fields = [
            "uuid",
            "frame_uuid",
            "frame_name",
            "source_video_uuid",
            "rendered_file",
            "render_status",
            "crop_x",
            "crop_y",
            "crop_width",
            "crop_height",
            "trim_in",
            "trim_out",
            "created",
        ]


class AssignedMemberSerializer(serializers.Serializer):
    uuid = serializers.UUIDField()
    username = serializers.CharField(source="user.username")
    full_name = serializers.CharField()


class AssignedUserGroupSerializer(serializers.Serializer):
    uuid = serializers.UUIDField()
    name = serializers.CharField()


class FrameSerializer(serializers.ModelSerializer):
    job_uuid = serializers.SerializerMethodField()
    job_title = serializers.SerializerMethodField()
    org = serializers.SerializerMethodField()

    def get_job_uuid(self, obj):
        return obj.job.uuid if obj.job else None

    def get_job_title(self, obj):
        return obj.job.title if obj.job else None

    def get_org(self, obj):
        return obj.job.company.name if obj.job else None

    class Meta:
        model = models.Frame
        fields = [
            "uuid",
            "frame_type",
            "job_uuid",
            "job_title",
            "org",
            "name",
            "background",
            "image",
            "aspect_ratio",
            "media_type",
            "ordering",
            "status",
            "is_live",
            "created",
            "modified",
        ]


class FrameDetailSerializer(FrameSerializer):
    total_assigned = serializers.IntegerField(read_only=True)
    members = serializers.SerializerMethodField()
    user_groups = serializers.SerializerMethodField()

    def get_members(self, obj):
        members = [a.member for a in obj.assignments.all() if a.member_id]
        return AssignedMemberSerializer(members, many=True).data

    def get_user_groups(self, obj):
        groups = [a.user_group for a in obj.assignments.all() if a.user_group_id]
        return AssignedUserGroupSerializer(groups, many=True).data

    class Meta(FrameSerializer.Meta):
        fields = FrameSerializer.Meta.fields + [
            "total_assigned", "members", "user_groups",
        ]
