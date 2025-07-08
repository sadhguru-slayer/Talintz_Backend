from django.core.management.base import BaseCommand
from workspace.models import Workspace, WorkspaceRevision
from OBSP.models import OBSPResponse, OBSPMilestone, OBSPLevel
from django.contrib.contenttypes.models import ContentType

class Command(BaseCommand):
    help = 'Create workspace revisions for OBSP milestones based on responses'

    def handle(self, *args, **kwargs):
        # Get all active OBSP responses (processing or in-progress)
        responses = OBSPResponse.objects.filter(
            status__in=['processing', 'completed']
        ).prefetch_related('template__levels__level_milestones')

        for response in responses:
            # Get the workspace for this response (using GenericForeignKey)
            try:
                workspace = Workspace.objects.get(
                    content_type=ContentType.objects.get_for_model(response),
                    object_id=response.id
                )
            except Workspace.DoesNotExist:
                self.stdout.write(self.style.ERROR(
                    f"No workspace found for response {response.id}. Skipping."
                ))
                continue

            # Get the level object for the selected level
            try:
                level = OBSPLevel.objects.get(
                    template=response.template,
                    level=response.selected_level
                )
            except OBSPLevel.DoesNotExist:
                self.stdout.write(self.style.ERROR(
                    f"Level '{response.selected_level}' not found for template {response.template.id}. Skipping response {response.id}."
                ))
                continue

            # Get all milestones for this level
            milestones = OBSPMilestone.objects.filter(
                level=level
            ).order_by('order')

            # Create a revision for each milestone
            for milestone in milestones:
                # Check if a revision already exists for this milestone
                if WorkspaceRevision.objects.filter(
                    workspace=workspace,
                    milestone_content_type=ContentType.objects.get_for_model(milestone),
                    milestone_object_id=milestone.id
                ).exists():
                    continue

                # Create the revision
                WorkspaceRevision.objects.create(
                    workspace=workspace,
                    milestone_content_type=ContentType.objects.get_for_model(milestone),
                    milestone_object_id=milestone.id,
                    requested_by=response.client,
                    description=f"Initial revision for {milestone.title}",
                    type='predefined',
                    status='open',
                    revision_number=1  # First revision for this milestone
                )

        self.stdout.write(self.style.SUCCESS(
            f"Completed processing {responses.count()} responses with {milestones.count()} total milestones."
        ))
