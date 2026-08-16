from datetime import datetime, time, timedelta

from django.db import IntegrityError, transaction
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework.decorators import action
from rest_framework.serializers import ValidationError
from rest_framework.viewsets import ReadOnlyModelViewSet

from apps.jobs import models, serializers_create, serializers_get
from apps.members.models import Member
from base import responses
from core import permissions
from core.pagination import StandardPagination


class CompanyViewSet(ReadOnlyModelViewSet):
    serializer_class = serializers_get.CompanySerializer
    permission_classes = [permissions.IsAdmin]
    pagination_class = StandardPagination
    lookup_field = "uuid"
    item_key = "Company Id"

    def get_queryset(self):
        queryset = models.Company.objects.filter(archived=None).order_by("name")
        name = self.request.query_params.get("name")
        status = self.request.query_params.get("status")
        if name:
            queryset = queryset.filter(name__icontains=name)
        if status:
            queryset = queryset.filter(status=status)
        return queryset

    @extend_schema(request=serializers_create.CompanySerializer)
    def create(self, request, *args, **kwargs):
        serializer = serializers_create.CompanySerializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
        except ValidationError as e:
            return responses.InvalidDataError(details=e.detail).get_response()

        try:
            with transaction.atomic():
                company = models.Company.objects.create(**serializer.validated_data)
        except IntegrityError:
            return responses.ExistingDataError(
                item_key="Company", item_id=serializer.validated_data["name"],
            ).get_response()

        data = self.serializer_class(company).data
        return responses.CreatedSuccessResponse(data=data).get_response()

    @extend_schema(request=serializers_create.EditCompanySerializer)
    def update(self, request, uuid=None, *args, **kwargs):
        serializer = serializers_create.EditCompanySerializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
        except ValidationError as e:
            return responses.InvalidDataError(details=e.detail).get_response()

        try:
            company = models.Company.objects.get(uuid=uuid)
        except models.Company.DoesNotExist:
            return responses.MissingItemError(
                item_key=self.item_key, item_id=uuid,
            ).get_response()

        if company.is_archived:
            return responses.ItemAlreadyArchivedError(
                item_key=self.item_key, item_id=uuid,
            ).get_response()

        company.update(**serializer.validated_data)

        data = self.serializer_class(company).data
        return responses.SuccessResponse(data=data).get_response()

    @extend_schema(request=serializers_create.EditCompanySerializer)
    def partial_update(self, request, uuid=None, *args, **kwargs):
        return self.update(request, uuid=uuid, *args, **kwargs)

    @action(detail=True, methods=["patch"])
    def archive(self, request, uuid=None, *args, **kwargs):
        try:
            company = models.Company.objects.get(uuid=uuid)
        except models.Company.DoesNotExist:
            return responses.MissingItemError(
                item_key=self.item_key, item_id=uuid,
            ).get_response()

        if company.is_archived:
            return responses.ItemAlreadyArchivedError(
                item_key=self.item_key, item_id=uuid,
            ).get_response()

        company.archive()

        data = self.serializer_class(company).data
        return responses.SuccessResponse(data=data).get_response()


class JobViewSet(ReadOnlyModelViewSet):
    serializer_class = serializers_get.JobSerializer
    permission_classes = [permissions.IsAdmin]
    pagination_class = StandardPagination
    lookup_field = "uuid"
    item_key = "Job Id"

    def get_queryset(self):
        queryset = (
            models.Job.objects
            .filter(archived=None)
            .select_related("company")
            .prefetch_related("requirements")
            .order_by("-created")
        )
        company_uuid = self.request.query_params.get("company_uuid")
        status = self.request.query_params.get("status")
        title = self.request.query_params.get("title")
        if company_uuid:
            queryset = queryset.filter(company__uuid=company_uuid)
        if status:
            queryset = queryset.filter(status=status)
        if title:
            queryset = queryset.filter(title__icontains=title)
        return queryset

    @extend_schema(request=serializers_create.JobSerializer)
    def create(self, request, *args, **kwargs):
        serializer = serializers_create.JobSerializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
        except ValidationError as e:
            return responses.InvalidDataError(details=e.detail).get_response()
        validated_data = serializer.validated_data

        company_uuid = validated_data.pop("company_uuid")
        requirements = validated_data.pop("requirements", [])

        try:
            company = models.Company.objects.get(uuid=company_uuid, archived=None)
        except models.Company.DoesNotExist:
            return responses.MissingItemError(
                item_key="Company Id", item_id=company_uuid,
            ).get_response()

        job = models.Job.objects.create(company=company, **validated_data)

        for requirement in requirements:
            models.JobRequirement.objects.create(job=job, **requirement)

        data = self.serializer_class(job).data
        return responses.CreatedSuccessResponse(data=data).get_response()

    @extend_schema(request=serializers_create.EditJobSerializer)
    def update(self, request, uuid=None, *args, **kwargs):
        serializer = serializers_create.EditJobSerializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
        except ValidationError as e:
            return responses.InvalidDataError(details=e.detail).get_response()
        validated_data = serializer.validated_data

        try:
            job = models.Job.objects.get(uuid=uuid)
        except models.Job.DoesNotExist:
            return responses.MissingItemError(
                item_key=self.item_key, item_id=uuid,
            ).get_response()

        if job.is_archived:
            return responses.ItemAlreadyArchivedError(
                item_key=self.item_key, item_id=uuid,
            ).get_response()

        company_uuid = validated_data.pop("company_uuid", None)
        if company_uuid:
            try:
                validated_data["company"] = models.Company.objects.get(
                    uuid=company_uuid, archived=None,
                )
            except models.Company.DoesNotExist:
                return responses.MissingItemError(
                    item_key="Company Id", item_id=company_uuid,
                ).get_response()

        job.update(**validated_data)

        data = self.serializer_class(job).data
        return responses.SuccessResponse(data=data).get_response()

    @extend_schema(request=serializers_create.EditJobSerializer)
    def partial_update(self, request, uuid=None, *args, **kwargs):
        return self.update(request, uuid=uuid, *args, **kwargs)

    @action(detail=True, methods=["patch"])
    def archive(self, request, uuid=None, *args, **kwargs):
        try:
            job = models.Job.objects.get(uuid=uuid)
        except models.Job.DoesNotExist:
            return responses.MissingItemError(
                item_key=self.item_key, item_id=uuid,
            ).get_response()

        if job.is_archived:
            return responses.ItemAlreadyArchivedError(
                item_key=self.item_key, item_id=uuid,
            ).get_response()

        job.archive()

        data = self.serializer_class(job).data
        return responses.SuccessResponse(data=data).get_response()


class JobRequirementViewSet(ReadOnlyModelViewSet):
    serializer_class = serializers_get.JobRequirementSerializer
    permission_classes = [permissions.IsAdmin]
    lookup_field = "uuid"
    item_key = "Requirement Id"

    def get_queryset(self):
        return models.JobRequirement.objects.filter(
            job__uuid=self.kwargs.get("job_uuid"), archived=None,
        ).order_by("content_type")

    def get_job(self):
        return models.Job.objects.filter(
            uuid=self.kwargs.get("job_uuid"), archived=None,
        ).first()

    @extend_schema(request=serializers_create.JobRequirementSerializer)
    def create(self, request, *args, **kwargs):
        serializer = serializers_create.JobRequirementSerializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
        except ValidationError as e:
            return responses.InvalidDataError(details=e.detail).get_response()

        job = self.get_job()
        if job is None:
            return responses.MissingItemError(
                item_key="Job Id", item_id=self.kwargs.get("job_uuid"),
            ).get_response()

        try:
            with transaction.atomic():
                requirement = models.JobRequirement.objects.create(
                    job=job, **serializer.validated_data
                )
        except IntegrityError:
            return responses.ExistingDataError(item_key="Requirement").get_response()

        data = self.serializer_class(requirement).data
        return responses.CreatedSuccessResponse(data=data).get_response()

    @extend_schema(request=serializers_create.JobRequirementSerializer)
    def update(self, request, uuid=None, *args, **kwargs):
        serializer = serializers_create.JobRequirementSerializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
        except ValidationError as e:
            return responses.InvalidDataError(details=e.detail).get_response()

        try:
            requirement = models.JobRequirement.objects.get(
                uuid=uuid, job__uuid=self.kwargs.get("job_uuid"),
            )
        except models.JobRequirement.DoesNotExist:
            return responses.MissingItemError(
                item_key=self.item_key, item_id=uuid,
            ).get_response()

        requirement.update(**serializer.validated_data)

        data = self.serializer_class(requirement).data
        return responses.SuccessResponse(data=data).get_response()

    @action(detail=True, methods=["patch"])
    def archive(self, request, uuid=None, *args, **kwargs):
        try:
            requirement = models.JobRequirement.objects.get(
                uuid=uuid, job__uuid=self.kwargs.get("job_uuid"),
            )
        except models.JobRequirement.DoesNotExist:
            return responses.MissingItemError(
                item_key=self.item_key, item_id=uuid,
            ).get_response()

        if requirement.is_archived:
            return responses.ItemAlreadyArchivedError(
                item_key=self.item_key, item_id=uuid,
            ).get_response()

        requirement.archive()

        data = self.serializer_class(requirement).data
        return responses.SuccessResponse(data=data).get_response()


class MemberScopedMixin:
    """Admins may act on any member; a member only on their own uuid."""

    def resolve_member(self):
        member_uuid = self.kwargs.get("member_uuid")
        user = self.request.user

        member = Member.objects.filter(uuid=member_uuid, archived=None).first()
        if member is None:
            return None, responses.MissingItemError(
                item_key="Member Id", item_id=member_uuid,
            ).get_response()

        if user.is_admin:
            return member, None

        if user.is_member and user.member.uuid == member.uuid:
            return member, None

        return None, responses.PermissionDeniedError().get_response()

    def require_admin(self):
        if not self.request.user.is_admin:
            return responses.PermissionDeniedError().get_response()
        return None


class MemberJobViewSet(MemberScopedMixin, ReadOnlyModelViewSet):
    serializer_class = serializers_get.MemberJobSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = StandardPagination
    lookup_field = "uuid"
    item_key = "Member Job Id"

    def get_queryset(self):
        queryset = (
            models.MemberJob.objects
            .filter(member__uuid=self.kwargs.get("member_uuid"), archived=None)
            .select_related("member__user", "job__company")
            .order_by("-created")
        )
        status = self.request.query_params.get("status")
        if status:
            queryset = queryset.filter(status=status)
        return queryset

    def list(self, request, *args, **kwargs):
        _, error = self.resolve_member()
        if error:
            return error
        return super().list(request, *args, **kwargs)

    def retrieve(self, request, *args, **kwargs):
        _, error = self.resolve_member()
        if error:
            return error
        return super().retrieve(request, *args, **kwargs)

    def get_member_job(self, uuid):
        return models.MemberJob.objects.filter(
            uuid=uuid,
            member__uuid=self.kwargs.get("member_uuid"),
            archived=None,
        ).first()

    def admin_action(self, uuid, **updates):
        error = self.require_admin()
        if error:
            return error

        member_job = self.get_member_job(uuid)
        if member_job is None:
            return responses.MissingItemError(
                item_key=self.item_key, item_id=uuid,
            ).get_response()

        member_job.update(**updates)

        data = self.serializer_class(member_job).data
        return responses.SuccessResponse(data=data).get_response()

    @extend_schema(request=serializers_create.EditMemberJobSerializer)
    def partial_update(self, request, uuid=None, *args, **kwargs):
        error = self.require_admin()
        if error:
            return error

        serializer = serializers_create.EditMemberJobSerializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
        except ValidationError as e:
            return responses.InvalidDataError(details=e.detail).get_response()

        return self.admin_action(uuid, **serializer.validated_data)

    @extend_schema(request=serializers_create.ApproveMemberJobSerializer)
    @action(detail=True, methods=["patch"])
    def approve(self, request, uuid=None, *args, **kwargs):
        serializer = serializers_create.ApproveMemberJobSerializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
        except ValidationError as e:
            return responses.InvalidDataError(details=e.detail).get_response()

        updates = {"status": 2, "joined": timezone.localdate()}
        affiliate_link = serializer.validated_data.get("affiliate_link")
        if affiliate_link:
            updates["affiliate_link"] = affiliate_link
            updates["affiliate_link_status"] = 3

        return self.admin_action(uuid, **updates)

    @action(detail=True, methods=["patch"])
    def reject(self, request, uuid=None, *args, **kwargs):
        return self.admin_action(uuid, status=4)

    @action(detail=True, methods=["patch"])
    def complete(self, request, uuid=None, *args, **kwargs):
        return self.admin_action(
            uuid, status=3, completed=timezone.localdate(),
        )


class SubmissionViewSet(ReadOnlyModelViewSet):
    serializer_class = serializers_get.MemberTaskSerializer
    permission_classes = [permissions.IsAdmin]
    pagination_class = StandardPagination
    lookup_field = "uuid"
    item_key = "Submission Id"

    def get_queryset(self):
        queryset = (
            models.MemberTask.objects
            .select_related(
                "member_job__member__user",
                "member_job__job__company",
                "requirement",
            )
            .order_by("-submitted_at", "-created")
        )

        status = self.request.query_params.get("status")
        job_uuid = self.request.query_params.get("job_uuid")
        member_uuid = self.request.query_params.get("member_uuid")
        period_key = self.request.query_params.get("period_key")

        if status == "2":
            queryset = queryset.filter(
                submitted_at__isnull=False, reviewed_at__isnull=True,
            )
        elif status == "3":
            queryset = queryset.filter(reviewed_at__isnull=False, is_approved=True)
        elif status == "4":
            queryset = queryset.filter(reviewed_at__isnull=False, is_approved=False)
        elif status == "5":
            queryset = queryset.filter(
                submitted_at__isnull=True, period_end__lt=timezone.localdate(),
            )
        elif status == "1":
            queryset = queryset.filter(
                submitted_at__isnull=True, period_end__gte=timezone.localdate(),
            )
        else:
            queryset = queryset.filter(submitted_at__isnull=False)

        if job_uuid:
            queryset = queryset.filter(member_job__job__uuid=job_uuid)
        if member_uuid:
            queryset = queryset.filter(member_job__member__uuid=member_uuid)
        if period_key:
            queryset = queryset.filter(period_key=period_key)

        return queryset

    def get_task(self, uuid):
        return models.MemberTask.objects.filter(uuid=uuid).first()

    @action(detail=True, methods=["patch"])
    def approve(self, request, uuid=None, *args, **kwargs):
        task = self.get_task(uuid)
        if task is None:
            return responses.MissingItemError(
                item_key=self.item_key, item_id=uuid,
            ).get_response()

        if task.submitted_at is None:
            return responses.BadRequestError(
                details="Task has not been submitted"
            ).get_response()

        task.review(admin=request.user.admin, is_approved=True)

        data = self.serializer_class(task).data
        return responses.SuccessResponse(data=data).get_response()

    @extend_schema(request=serializers_create.RejectTaskSerializer)
    @action(detail=True, methods=["patch"])
    def reject(self, request, uuid=None, *args, **kwargs):
        serializer = serializers_create.RejectTaskSerializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
        except ValidationError as e:
            return responses.InvalidDataError(details=e.detail).get_response()

        task = self.get_task(uuid)
        if task is None:
            return responses.MissingItemError(
                item_key=self.item_key, item_id=uuid,
            ).get_response()

        if task.submitted_at is None:
            return responses.BadRequestError(
                details="Task has not been submitted"
            ).get_response()

        task.review(
            admin=request.user.admin,
            is_approved=False,
            reject_reason=serializer.validated_data["reject_reason"],
        )

        data = self.serializer_class(task).data
        return responses.SuccessResponse(data=data).get_response()


class AvailableJobViewSet(MemberScopedMixin, ReadOnlyModelViewSet):
    serializer_class = serializers_get.AvailableJobSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = StandardPagination
    lookup_field = "uuid"
    item_key = "Job Id"

    def get_queryset(self):
        return (
            models.Job.objects
            .filter(archived=None, status=2)
            .select_related("company")
            .prefetch_related("requirements")
            .order_by("-created")
        )

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["subscribed_job_ids"] = set(
            models.MemberJob.objects
            .filter(member__uuid=self.kwargs.get("member_uuid"), archived=None)
            .values_list("job_id", flat=True)
        )
        return context

    def list(self, request, *args, **kwargs):
        _, error = self.resolve_member()
        if error:
            return error
        return super().list(request, *args, **kwargs)

    def retrieve(self, request, *args, **kwargs):
        _, error = self.resolve_member()
        if error:
            return error
        return super().retrieve(request, *args, **kwargs)

    @action(detail=True, methods=["post"])
    def subscribe(self, request, uuid=None, *args, **kwargs):
        member, error = self.resolve_member()
        if error:
            return error

        try:
            job = models.Job.objects.get(uuid=uuid, archived=None)
        except models.Job.DoesNotExist:
            return responses.MissingItemError(
                item_key=self.item_key, item_id=uuid,
            ).get_response()

        if not job.is_live:
            return responses.BadRequestError(
                details="Job is not open for subscription"
            ).get_response()

        try:
            with transaction.atomic():
                member_job = models.MemberJob.objects.create(
                    member=member, job=job, status=1,
                )
        except IntegrityError:
            return responses.ExistingDataError(
                error_message="Already subscribed to this job",
            ).get_response()

        data = serializers_get.MemberJobSerializer(member_job).data
        return responses.CreatedSuccessResponse(data=data).get_response()


class MemberTaskViewSet(MemberScopedMixin, ReadOnlyModelViewSet):
    serializer_class = serializers_get.MemberTaskSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = StandardPagination
    lookup_field = "uuid"
    item_key = "Task Id"

    def get_queryset(self):
        queryset = (
            models.MemberTask.objects
            .filter(member_job__member__uuid=self.kwargs.get("member_uuid"))
            .select_related(
                "member_job__member__user",
                "member_job__job__company",
                "requirement",
            )
            .order_by("-period_start", "requirement__content_type")
        )

        member_job_uuid = self.request.query_params.get("member_job_uuid")
        period_key = self.request.query_params.get("period_key")
        if member_job_uuid:
            queryset = queryset.filter(member_job__uuid=member_job_uuid)
        if period_key:
            queryset = queryset.filter(period_key=period_key)
        return queryset

    def list(self, request, *args, **kwargs):
        _, error = self.resolve_member()
        if error:
            return error
        return super().list(request, *args, **kwargs)

    def retrieve(self, request, *args, **kwargs):
        _, error = self.resolve_member()
        if error:
            return error
        return super().retrieve(request, *args, **kwargs)

    @extend_schema(request=serializers_create.SubmitTaskSerializer)
    @action(detail=True, methods=["post", "patch"])
    def submit(self, request, uuid=None, *args, **kwargs):
        member, error = self.resolve_member()
        if error:
            return error

        serializer = serializers_create.SubmitTaskSerializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
        except ValidationError as e:
            return responses.InvalidDataError(details=e.detail).get_response()
        validated_data = serializer.validated_data

        try:
            task = models.MemberTask.objects.get(
                uuid=uuid, member_job__member=member,
            )
        except models.MemberTask.DoesNotExist:
            return responses.MissingItemError(
                item_key=self.item_key, item_id=uuid,
            ).get_response()

        if task.is_submitted:
            return responses.BadRequestError(
                details="Task has already been submitted"
            ).get_response()

        settings_row = models.JobSettings.objects.first()
        grace_hours = settings_row.submission_grace_hours if settings_row else 0
        deadline = timezone.make_aware(
            datetime.combine(task.period_end, time.max)
        ) + timedelta(hours=grace_hours)
        if timezone.now() > deadline:
            return responses.BadRequestError(
                details="Submission window has closed"
            ).get_response()

        task.submit(
            proof_link=validated_data.get("proof_link"),
            proof_file=validated_data.get("proof_file"),
            note=validated_data.get("note"),
        )

        data = self.serializer_class(task).data
        return responses.SuccessResponse(data=data).get_response()
