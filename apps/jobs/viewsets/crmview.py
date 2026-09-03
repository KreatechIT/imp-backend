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


class OrgScopedMixin:
    """Everything under /jobs/org/{org_uuid}/ belongs to one org.

    The org and the job come from the path now, so the parent is resolved
    once here and every lookup below stays inside that scope.
    """

    def get_org(self):
        return models.Company.objects.filter(
            uuid=self.kwargs.get("org_uuid"), archived=None,
        ).first()

    def missing_org(self):
        return responses.MissingItemError(
            item_key="Org Id", item_id=self.kwargs.get("org_uuid"),
        ).get_response()

    def get_job(self):
        return models.Job.objects.filter(
            uuid=self.kwargs.get("job_uuid"),
            company__uuid=self.kwargs.get("org_uuid"),
            archived=None,
        ).first()

    def missing_job(self):
        return responses.MissingItemError(
            item_key="Job Id", item_id=self.kwargs.get("job_uuid"),
        ).get_response()


class OrgViewSet(ReadOnlyModelViewSet):
    serializer_class = serializers_get.OrgSerializer
    permission_classes = [permissions.IsAdmin]
    pagination_class = StandardPagination
    lookup_field = "uuid"
    item_key = "Org Id"

    def get_queryset(self):
        queryset = models.Company.objects.filter(archived=None).order_by("name")
        name = self.request.query_params.get("name")
        status = self.request.query_params.get("status")
        if name:
            queryset = queryset.filter(name__icontains=name)
        if status:
            queryset = queryset.filter(status=status)
        return queryset

    @extend_schema(request=serializers_create.OrgSerializer)
    def create(self, request, *args, **kwargs):
        serializer = serializers_create.OrgSerializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
        except ValidationError as e:
            return responses.InvalidDataError(details=e.detail).get_response()

        try:
            with transaction.atomic():
                org = models.Company.objects.create(**serializer.validated_data)
        except IntegrityError:
            return responses.ExistingDataError(
                item_key="Org", item_id=serializer.validated_data["name"],
            ).get_response()

        data = self.serializer_class(org, context={"request": self.request}).data
        return responses.CreatedSuccessResponse(data=data).get_response()

    @extend_schema(request=serializers_create.EditOrgSerializer)
    def update(self, request, uuid=None, *args, **kwargs):
        serializer = serializers_create.EditOrgSerializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
        except ValidationError as e:
            return responses.InvalidDataError(details=e.detail).get_response()

        try:
            org = models.Company.objects.get(uuid=uuid)
        except models.Company.DoesNotExist:
            return responses.MissingItemError(
                item_key=self.item_key, item_id=uuid,
            ).get_response()

        if org.is_archived:
            return responses.ItemAlreadyArchivedError(
                item_key=self.item_key, item_id=uuid,
            ).get_response()

        org.update(**serializer.validated_data)

        data = self.serializer_class(org, context={"request": self.request}).data
        return responses.SuccessResponse(data=data).get_response()

    @extend_schema(request=serializers_create.EditOrgSerializer)
    def partial_update(self, request, uuid=None, *args, **kwargs):
        return self.update(request, uuid=uuid, *args, **kwargs)

    @action(detail=True, methods=["patch"])
    def archive(self, request, uuid=None, *args, **kwargs):
        try:
            org = models.Company.objects.get(uuid=uuid)
        except models.Company.DoesNotExist:
            return responses.MissingItemError(
                item_key=self.item_key, item_id=uuid,
            ).get_response()

        if org.is_archived:
            return responses.ItemAlreadyArchivedError(
                item_key=self.item_key, item_id=uuid,
            ).get_response()

        org.archive()

        data = self.serializer_class(org, context={"request": self.request}).data
        return responses.SuccessResponse(data=data).get_response()


class JobViewSet(OrgScopedMixin, ReadOnlyModelViewSet):
    serializer_class = serializers_get.JobSerializer
    permission_classes = [permissions.IsAdmin]
    pagination_class = StandardPagination
    lookup_field = "uuid"
    item_key = "Job Id"

    def get_queryset(self):
        queryset = (
            models.Job.objects
            .filter(company__uuid=self.kwargs.get("org_uuid"), archived=None)
            .select_related("company")
            .prefetch_related("requirements")
            .order_by("-created")
        )
        status = self.request.query_params.get("status")
        title = self.request.query_params.get("title")
        if status:
            queryset = queryset.filter(status=status)
        if title:
            queryset = queryset.filter(title__icontains=title)
        return queryset

    def get_scoped_job(self, uuid):
        return models.Job.objects.filter(
            uuid=uuid, company__uuid=self.kwargs.get("org_uuid"),
        ).first()

    @extend_schema(request=serializers_create.JobSerializer)
    def create(self, request, *args, **kwargs):
        serializer = serializers_create.JobSerializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
        except ValidationError as e:
            return responses.InvalidDataError(details=e.detail).get_response()
        validated_data = serializer.validated_data

        org = self.get_org()
        if org is None:
            return self.missing_org()

        requirements = validated_data.pop("requirements", [])

        job = models.Job.objects.create(company=org, **validated_data)

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

        job = self.get_scoped_job(uuid)
        if job is None:
            return responses.MissingItemError(
                item_key=self.item_key, item_id=uuid,
            ).get_response()

        if job.is_archived:
            return responses.ItemAlreadyArchivedError(
                item_key=self.item_key, item_id=uuid,
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
        job = self.get_scoped_job(uuid)
        if job is None:
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


class JobListViewSet(ReadOnlyModelViewSet):
    """Flat, cross-org job list — /jobs/list/. Read-only.

    JobViewSet above stays org-scoped for the admin CRUD flow; this exists
    alongside it for callers that just need every job (with its uuid)
    without knowing the org uuid up front.
    """

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
        org_uuid = self.request.query_params.get("org_uuid")
        status = self.request.query_params.get("status")
        title = self.request.query_params.get("title")
        if org_uuid:
            queryset = queryset.filter(company__uuid=org_uuid)
        if status:
            queryset = queryset.filter(status=status)
        if title:
            queryset = queryset.filter(title__icontains=title)
        return queryset


class JobRequirementViewSet(OrgScopedMixin, ReadOnlyModelViewSet):
    serializer_class = serializers_get.JobRequirementSerializer
    permission_classes = [permissions.IsAdmin]
    lookup_field = "uuid"
    item_key = "Requirement Id"

    def get_queryset(self):
        return models.JobRequirement.objects.filter(
            job__uuid=self.kwargs.get("job_uuid"),
            job__company__uuid=self.kwargs.get("org_uuid"),
            archived=None,
        ).order_by("content_type")

    def get_requirement(self, uuid):
        return models.JobRequirement.objects.filter(
            uuid=uuid,
            job__uuid=self.kwargs.get("job_uuid"),
            job__company__uuid=self.kwargs.get("org_uuid"),
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
            return self.missing_job()

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

        requirement = self.get_requirement(uuid)
        if requirement is None:
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
        requirement = self.get_requirement(uuid)
        if requirement is None:
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


class JobMemberViewSet(OrgScopedMixin, ReadOnlyModelViewSet):
    """Who applied to this job, and the decision on each application.

    One list for every state. `?status=1` is the pending queue, `?status=2`
    the members currently working the job.
    """

    serializer_class = serializers_get.MemberJobSerializer
    permission_classes = [permissions.IsAdmin]
    pagination_class = StandardPagination
    lookup_field = "uuid"
    item_key = "Application Id"

    def base_queryset(self):
        return (
            models.MemberJob.objects
            .filter(
                job__uuid=self.kwargs.get("job_uuid"),
                job__company__uuid=self.kwargs.get("org_uuid"),
                archived=None,
            )
            .select_related("member__user", "job__company")
            .order_by("-created")
        )

    def get_queryset(self):
        queryset = self.base_queryset()

        status = self.request.query_params.get("status")
        search = self.request.query_params.get("search")
        if status:
            queryset = queryset.filter(status=status)
        if search:
            queryset = queryset.filter(
                Q(member__full_name__icontains=search)
                | Q(member__user__username__icontains=search)
                | Q(member__phone_number__icontains=search)
            )
        return queryset

    def get_application(self, uuid):
        return self.base_queryset().filter(uuid=uuid).first()

    @extend_schema(request=serializers_create.EditMemberJobSerializer)
    def partial_update(self, request, uuid=None, *args, **kwargs):
        """The escape hatch: set any field directly, no state guard."""
        serializer = serializers_create.EditMemberJobSerializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
        except ValidationError as e:
            return responses.InvalidDataError(details=e.detail).get_response()

        application = self.get_application(uuid)
        if application is None:
            return responses.MissingItemError(
                item_key=self.item_key, item_id=uuid,
            ).get_response()

        application.update(**serializer.validated_data)

        data = self.serializer_class(application, context={"request": self.request}).data
        return responses.SuccessResponse(data=data).get_response()

    @action(detail=True, methods=["patch"])
    def complete(self, request, uuid=None, *args, **kwargs):
        application = self.get_application(uuid)
        if application is None:
            return responses.MissingItemError(
                item_key=self.item_key, item_id=uuid,
            ).get_response()

        if application.status != 2:
            return responses.BadRequestError(
                details="Only an active application can be completed"
            ).get_response()

        application.update(status=3, completed=timezone.localdate())

        data = self.serializer_class(application, context={"request": self.request}).data
        return responses.SuccessResponse(data=data).get_response()

    @extend_schema(request=serializers_create.ApproveMemberJobSerializer)
    @action(detail=True, methods=["patch"])
    def approve(self, request, uuid=None, *args, **kwargs):
        serializer = serializers_create.ApproveMemberJobSerializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
        except ValidationError as e:
            return responses.InvalidDataError(details=e.detail).get_response()

        application = self.get_application(uuid)
        if application is None:
            return responses.MissingItemError(
                item_key=self.item_key, item_id=uuid,
            ).get_response()

        if application.status != 1:
            return responses.BadRequestError(
                details="Application has already been reviewed"
            ).get_response()

        updates = {"status": 2, "joined": timezone.localdate()}
        affiliate_link = serializer.validated_data.get("affiliate_link")
        if affiliate_link:
            updates["affiliate_link"] = affiliate_link
            updates["affiliate_link_status"] = 3

        application.update(**updates)

        data = self.serializer_class(application, context={"request": self.request}).data
        return responses.SuccessResponse(data=data).get_response()

    @action(detail=True, methods=["patch"])
    def reject(self, request, uuid=None, *args, **kwargs):
        application = self.get_application(uuid)
        if application is None:
            return responses.MissingItemError(
                item_key=self.item_key, item_id=uuid,
            ).get_response()

        if application.status != 1:
            return responses.BadRequestError(
                details="Application has already been reviewed"
            ).get_response()

        application.update(status=4)

        data = self.serializer_class(application, context={"request": self.request}).data
        return responses.SuccessResponse(data=data).get_response()


class PendingApplicationViewSet(ReadOnlyModelViewSet):
    """Flat, cross-job/cross-org pending applications — /jobs/applications/pending/.

    JobMemberViewSet above stays job-scoped (?status=1 there is the pending
    queue for one job); this exists alongside it for callers that need every
    still-applied member across every job/org in one paginated list, each
    row carrying its own job_uuid and org_uuid.
    """

    serializer_class = serializers_get.MemberJobSerializer
    permission_classes = [permissions.IsAdmin]
    pagination_class = StandardPagination
    lookup_field = "uuid"
    item_key = "Application Id"

    def get_queryset(self):
        queryset = (
            models.MemberJob.objects
            .filter(status=1, archived=None)
            .select_related("member__user", "job__company")
            .order_by("-created")
        )
        org_uuid = self.request.query_params.get("org_uuid")
        job_uuid = self.request.query_params.get("job_uuid")
        search = self.request.query_params.get("search")
        if org_uuid:
            queryset = queryset.filter(job__company__uuid=org_uuid)
        if job_uuid:
            queryset = queryset.filter(job__uuid=job_uuid)
        if search:
            queryset = queryset.filter(
                Q(member__full_name__icontains=search)
                | Q(member__user__username__icontains=search)
                | Q(member__phone_number__icontains=search)
            )
        return queryset


class SubmissionViewSet(ReadOnlyModelViewSet):
    serializer_class = serializers_get.MemberTaskSerializer
    permission_classes = [permissions.IsAdmin]
    pagination_class = StandardPagination
    lookup_field = "uuid"
    item_key = "Submission Id"

    # status codes that give /pending/, /approved/, /rejected/ a fixed filter
    # while /submission/ itself still takes ?status= like before.
    ACTION_STATUS = {
        "pending": "2",
        "approved": "3",
        "rejected": "4",
    }

    def base_queryset(self):
        return (
            models.MemberTask.objects
            .filter(member_job__job__uuid=self.kwargs.get("job_uuid"))
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

        member_uuid = params.get("member_uuid")
        period_key = params.get("period_key")
        from_date = params.get("from_date")
        to_date = params.get("to_date")
        search = params.get("search")

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
        """Submissions awaiting review. Same filters as /submission/."""
        return self.list(request, *args, **kwargs)

    @action(detail=False, methods=["get"])
    def approved(self, request, *args, **kwargs):
        """Approved submissions. Same filters as /submission/."""
        return self.list(request, *args, **kwargs)

    @action(detail=False, methods=["get"])
    def rejected(self, request, *args, **kwargs):
        """Rejected submissions. Same filters as /submission/."""
        return self.list(request, *args, **kwargs)

    def get_task(self, uuid):
        return models.MemberTask.objects.filter(
            uuid=uuid, member_job__job__uuid=self.kwargs.get("job_uuid"),
        ).first()

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
