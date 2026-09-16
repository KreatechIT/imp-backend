from django.core.management.base import BaseCommand

from apps.frames.models import Frame, FrameAssignment


class Command(BaseCommand):
    help = "Create a job FrameAssignment for every frame that does not have one"

    def handle(self, *args, **kwargs):
        frames = Frame.objects.filter(job__isnull=False).exclude(
            assignments__job__isnull=False,
        )

        assignments = [
            FrameAssignment(
                frame=frame,
                job_id=frame.job_id,
                status=1,
                archived=frame.archived,
            )
            for frame in frames
        ]
        FrameAssignment.objects.bulk_create(assignments)

        self.stdout.write(
            self.style.SUCCESS(f"Created {len(assignments)} frame assignments")
        )
