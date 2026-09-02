from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework.decorators import action
from rest_framework.serializers import ValidationError
from rest_framework.viewsets import ReadOnlyModelViewSet

from apps.jobs import models, serializers_create, serializers_get
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

        data = self.serializer_class(company, context={"request": self.request}).data
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

        data = self.serializer_class(company, context={"request": self.request}).data
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

        data = self.serializer_class(company, context={"request": self.request}).data
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

        data = self.serializer_class(job, context={"request": self.request}).data
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

        start_date = validated_data.get("start_date", job.start_date)
        end_date = validated_data.get("end_date", job.end_date)
        if end_date and end_date < start_date:
            return responses.InvalidDataError(details={
                "end_date": "End date cannot be before start date."
            }).get_response()

        job.update(**validated_data)

        data = self.serializer_class(job, context={"request": self.request}).data
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

        data = self.serializer_class(job, context={"request": self.request}).data
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

        data = self.serializer_class(requirement, context={"request": self.request}).data
        return responses.CreatedSuccessResponse(data=data).get_response()

    @extend_schema(request=serializers_create.EditJobRequirementSerializer)
    def update(self, request, uuid=None, *args, **kwargs):
        serializer = serializers_create.EditJobRequirementSerializer(
            data=request.data
        )
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

        data = self.serializer_class(requirement, context={"request": self.request}).data
        return responses.SuccessResponse(data=data).get_response()

    @extend_schema(request=serializers_create.EditJobRequirementSerializer)
    def partial_update(self, request, uuid=None, *args, **kwargs):
        return self.update(request, uuid=uuid, *args, **kwargs)

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

        data = self.serializer_class(requirement, context={"request": self.request}).data
        return responses.SuccessResponse(data=data).get_response()


class SubmissionViewSet(ReadOnlyModelViewSet):
    serializer_class = serializers_get.MemberTaskSerializer
    permission_classes = [permissions.IsAdmin]
    pagination_class = StandardPagination
    lookup_field = "uuid"
    item_key = "Submission Id"

    # status codes that give /pending/, /approved/, /rejected/ a fixed filter
    # while /submissions/ itself still takes ?status= like before.
    ACTION_STATUS = {
        "pending": "2",
        "approved": "3",
        "rejected": "4",
    }

    def base_queryset(self):
        return (
            models.MemberTask.objects
            .select_related(
                "member_job__member__user",
                "member_job__job__company",
                "requirement",
            )
            .order_by("-submitted_at", "-created")
        )

    def apply_filters(self, queryset, status=None):
        params = self.request.query_params

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

        job_uuid = params.get("job_uuid")
        member_uuid = params.get("member_uuid")
        period_key = params.get("period_key")
        from_date = params.get("from_date")
        to_date = params.get("to_date")
        search = params.get("search")

        if job_uuid:
            queryset = queryset.filter(member_job__job__uuid=job_uuid)
        if member_uuid:
            queryset = queryset.filter(member_job__member__uuid=member_uuid)
        if period_key:
            queryset = queryset.filter(period_key=period_key)
        if from_date:
            queryset = queryset.filter(submitted_at__date__gte=from_date)
        if to_date:
            queryset = queryset.filter(submitted_at__date__lte=to_date)
        if search:
            queryset = queryset.filter(
                Q(member_job__member__full_name__icontains=search)
                | Q(member_job__member__user__username__icontains=search)
                | Q(member_job__member__phone_number__icontains=search)
            )

        return queryset

    def get_queryset(self):
        forced_status = self.ACTION_STATUS.get(self.action)
        status = forced_status or self.request.query_params.get("status")
        return self.apply_filters(self.base_queryset(), status=status)

    @action(detail=False, methods=["get"])
    def pending(self, request, *args, **kwargs):
        """Submissions awaiting review. Same filters as /submissions/."""
        return self.list(request, *args, **kwargs)

    @action(detail=False, methods=["get"])
    def approved(self, request, *args, **kwargs):
        """Approved submissions. Same filters as /submissions/."""
        return self.list(request, *args, **kwargs)

    @action(detail=False, methods=["get"])
    def rejected(self, request, *args, **kwargs):
        """Rejected submissions. Same filters as /submissions/."""
        return self.list(request, *args, **kwargs)

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

        if task.reviewed_at:
            return responses.BadRequestError(
                details="Task has already been reviewed"
            ).get_response()

        task.review(admin=request.user.admin, is_approved=True)

        data = self.serializer_class(task, context={"request": self.request}).data
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

        if task.reviewed_at:
            return responses.BadRequestError(
                details="Task has already been reviewed"
            ).get_response()

        task.review(
            admin=request.user.admin,
            is_approved=False,
            reject_reason=serializer.validated_data["reject_reason"],
        )

        data = self.serializer_class(task, context={"request": self.request}).data
        return responses.SuccessResponse(data=data).get_response()
