from django.core.management.base import BaseCommand
from core.models import Project, Milestone
from financeapp.models import Wallet
from financeapp.models.hold import Hold
from django.db import transaction

class Command(BaseCommand):
    help = "Force update Hold model for all auto-pay milestones"

    def handle(self, *args, **options):
        created_count = 0
        updated_count = 0
        skipped_count = 0

        for project in Project.objects.all():
            client = project.client
            try:
                wallet = Wallet.objects.get(user=client)
            except Wallet.DoesNotExist:
                self.stdout.write(self.style.WARNING(f"No wallet for client {client.username} (Project: {project.title})"))
                continue

            milestones = Milestone.objects.filter(project=project,is_automated=True)
            for milestone in milestones:
                # Check if a Hold already exists for this milestone
                hold_qs = Hold.objects.filter(
                    wallet=wallet,
                    project=project,
                    milestone=milestone,
                    hold_type='project_milestone'
                )
                if hold_qs.exists():
                    skipped_count += 1
                    continue

                # Calculate escrow amount
                if project.pricing_strategy == 'fixed':
                    amount = milestone.amount
                elif project.pricing_strategy == 'hourly':
                    amount = (milestone.max_hours or 0) * (project.hourly_rate or 0)
                else:
                    amount = 0

                if not amount or amount <= 0:
                    self.stdout.write(self.style.WARNING(
                        f"Skipping milestone '{milestone.title}' (Project: {project.title}) due to zero amount."
                    ))
                    continue

                # Create the Hold
                with transaction.atomic():
                    Hold.objects.create(
                        wallet=wallet,
                        user=client,
                        project=project,
                        milestone=milestone,
                        amount=amount,
                        hold_type='project_milestone',
                        title=f"Auto-pay hold for {milestone.title}",
                        description=f"Auto-pay hold for milestone '{milestone.title}' in project '{project.title}'"
                    )
                    created_count += 1
                    self.stdout.write(self.style.SUCCESS(
                        f"Created Hold for milestone '{milestone.title}' (Project: {project.title})"
                    ))

        self.stdout.write(self.style.SUCCESS(
            f"Done! Created: {created_count}, Skipped (already exists): {skipped_count}"
        ))
