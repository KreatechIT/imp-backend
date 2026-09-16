from rest_framework import serializers

from apps.frames import models


class RenderedContentSerializer(serializers.ModelSerializer):
    member_uuid = serializers.UUIDField(source="member.uuid")
    member = serializers.CharField(source="member.full_name")
    org = serializers.SerializerMethodField()
    job_uuid = serializers.SerializerMethodField()
    job_title = serializers.SerializerMethodField()
    frame_uuid = serializers.UUIDField(source="frame.uuid")
    frame_name = serializers.CharField(source="frame.name")

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
            "member",
            "member_uuid",
            "org",
            "job_uuid",
            "job_title",
            "frame_uuid",
            "frame_name",
            "original_file",
            "rendered_file",
            "media_type",
            "original_name",
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
