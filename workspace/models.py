from django.db import models
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.conf import settings
from core.models import Milestone
from django.utils import timezone
from OBSP.models import OBSPMilestone

class Workspace(models.Model):
    """
    Represents a workspace for a project or OBSP assignment.
    """
    # Generic relation to Project or OBSPAssignment
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey('content_type', 'object_id')

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"Workspace for {self.content_object} (ID: {self.id})"


class WorkspaceParticipant(models.Model):
    ROLE_CHOICES = [
        ('client', 'Client'),
        ('freelancer', 'Freelancer'),
        ('admin', 'Admin'),
        # Add more as needed
    ]
    workspace = models.ForeignKey(Workspace, related_name='participants', on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    permissions = models.JSONField(default=dict, blank=True)  # e.g. {"can_upload": True, "can_raise_dispute": True}
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('workspace', 'user')

    def __str__(self):
        return f"{self.user.username} as {self.role} in Workspace {self.workspace.id}"

class WorkspaceAttachment(models.Model):
    """
    Generic attachment for revisions, disputes, or workspace.
    """
    workspace = models.ForeignKey(Workspace, related_name='attachments', on_delete=models.CASCADE)
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey('content_type', 'object_id')
    file = models.FileField(upload_to='workspace/attachments/')
    link = models.URLField(blank=True, null=True)
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Attachment {self.id} for {self.content_object}"


class WorkspaceBox(models.Model):
    """
    Represents a container (box) for attachments related to a specific workspace item,
    to organize files and prevent confusion across contexts.
    """

    APPROVAL_CHOICES = [
        ('submitted', 'Submitted'),
        ('viewed', 'Viewed'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]

    workspace = models.ForeignKey(Workspace, related_name='boxes', on_delete=models.CASCADE)
    title = models.CharField(max_length=255, help_text="A descriptive title for this box, e.g., 'Milestone 1 Submission'")
    description = models.TextField(blank=True, null=True, help_text="Optional description or instructions for this box")
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, help_text="The type of object this box relates to (e.g., Milestone)")
    object_id = models.PositiveIntegerField(help_text="The ID of the related object (e.g., Milestone ID)")
    content_object = GenericForeignKey('content_type', 'object_id')
    attachments = models.ManyToManyField(WorkspaceAttachment, related_name='boxes', blank=True, help_text="Attachments included in this box")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    status = models.CharField(max_length=50,choices=APPROVAL_CHOICES,default="submitted" )

    def __str__(self):
        return f"Workspace Box '{self.title}' for {self.content_object} in Workspace {self.workspace.id}"


class WorkspaceRevision(models.Model):
    workspace = models.ForeignKey(Workspace, related_name='revisions', on_delete=models.CASCADE)
    # Generic relation to either Milestone (Project) or OBSPMilestone (OBSP)
    milestone_content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, null=True)
    milestone_object_id = models.PositiveIntegerField(null=True)
    milestone = GenericForeignKey('milestone_content_type', 'milestone_object_id')

    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    description = models.TextField()
    type = models.CharField(max_length=20, choices=[('predefined', 'Predefined'), ('adhoc', 'Ad-hoc')], default='adhoc')
    revision_number = models.PositiveIntegerField(default=1)  # 1st, 2nd, etc. for that milestone
    status = models.CharField(max_length=20, choices=[
        ('open', 'Open'),
        ('addressed', 'Addressed'),
        ('closed', 'Closed'),
    ], default='open')
    created_at = models.DateTimeField(auto_now_add=True)
    addressed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"Revision {self.revision_number} ({self.type}) for {self.milestone} in Workspace {self.workspace.id}"


class WorkspaceDispute(models.Model):
    """
    Tracks disputes raised within a workspace.
    """
    workspace = models.ForeignKey(Workspace, related_name='disputes', on_delete=models.CASCADE)
    milestone = models.ForeignKey(Milestone, null=True, blank=True, on_delete=models.SET_NULL)
    raised_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    issue_description = models.TextField()
    deadline_passed = models.BooleanField(default=False)
    status = models.CharField(max_length=20, choices=[
        ('open', 'Open'),
        ('in_review', 'In Review'),
        ('resolved', 'Resolved'),
        ('rejected', 'Rejected'),
        ('escalated', 'Escalated'),
    ], default='open')
    freelancer_response = models.TextField(blank=True, null=True)
    admin_note = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Dispute ({self.status}) in Workspace {self.workspace.id}"

class WorkspaceActivity(models.Model):
    """
    Tracks all workspace activities with high performance and simplicity.
    """
    # Core Activity Types - Only what you actually need
    ACTIVITY_TYPES = [
        # Milestone Activities
        ('milestone_created', 'Milestone Created'),
        ('milestone_started', 'Milestone Started'),
        ('milestone_completed', 'Milestone Completed'),
        ('milestone_approved', 'Milestone Approved'),
        ('milestone_rejected', 'Milestone Rejected'),
        ('milestone_updated', 'Milestone Updated'),
        
        # Payment Activities
        ('payment_initiated', 'Payment Initiated'),
        ('payment_completed', 'Payment Completed'),
        ('payment_failed', 'Payment Failed'),
        ('payment_refunded', 'Payment Refunded'),
        
        # File/Attachment Activities
        ('file_uploaded', 'File Uploaded'),
        ('file_downloaded', 'File Downloaded'),
        ('file_deleted', 'File Deleted'),
        # Box Activities
        ('box_uploaded', 'Box Uploaded'),
        ('box_downloaded', 'Box Downloaded'),
        ('box_deleted', 'Box Deleted'),
        
        # Revision Activities
        ('revision_requested', 'Revision Requested'),
        ('revision_submitted', 'Revision Submitted'),
        ('revision_approved', 'Revision Approved'),
        ('revision_rejected', 'Revision Rejected'),
        
        # Dispute Activities
        ('dispute_raised', 'Dispute Raised'),
        ('dispute_resolved', 'Dispute Resolved'),
        ('dispute_escalated', 'Dispute Escalated'),
        
        # Meeting Activities
        ('meeting_scheduled', 'Meeting Scheduled'),
        ('meeting_started', 'Meeting Started'),
        ('meeting_completed', 'Meeting Completed'),
        ('meeting_cancelled', 'Meeting Cancelled'),
        
        # Communication Activities
        ('message_sent', 'Message Sent'),
        ('note_added', 'Note Added'),
        ('feedback_given', 'Feedback Given'),
        
        # Status Changes
        ('status_changed', 'Status Changed'),
        ('deadline_updated', 'Deadline Updated'),
        ('budget_updated', 'Budget Updated'),
        
        # Participant Activities
        ('participant_joined', 'Participant Joined'),
        ('participant_left', 'Participant Left'),
        ('role_changed', 'Role Changed'),
    ]

    # Core fields - Keep it simple and fast
    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name='activities')
    activity_type = models.CharField(max_length=30, choices=ACTIVITY_TYPES, db_index=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, db_index=True)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    payment = models.ForeignKey(
        'financeapp.Transaction',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='workspace_activities'
    )
    # Optional reference fields - Only when needed
    milestone = models.ForeignKey(Milestone, null=True, blank=True, on_delete=models.SET_NULL)
    obsp_milestone = models.ForeignKey(OBSPMilestone, null=True, blank=True, on_delete=models.SET_NULL)
    attachment = models.ForeignKey(WorkspaceAttachment, null=True, blank=True, on_delete=models.SET_NULL)
    revision = models.ForeignKey(WorkspaceRevision, null=True, blank=True, on_delete=models.SET_NULL)
    dispute = models.ForeignKey(WorkspaceDispute, null=True, blank=True, on_delete=models.SET_NULL)
    
    # Add these new fields for linking to related objects like notes
    content_type = models.ForeignKey(ContentType, on_delete=models.SET_NULL, null=True, blank=True)
    object_id = models.PositiveIntegerField(null=True, blank=True)
    related_object = GenericForeignKey('content_type', 'object_id')

    # Simple metadata - No complex JSON, just what you need
    title = models.CharField(max_length=255, blank=True)  # Human-readable title
    description = models.TextField(blank=True)  # Brief description
    amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)  # For payments
    old_value = models.CharField(max_length=100, blank=True)  # For status changes
    new_value = models.CharField(max_length=100, blank=True)  # For status changes

    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['workspace', 'timestamp']),
            models.Index(fields=['workspace', 'activity_type']),
            models.Index(fields=['workspace', 'user']),
            models.Index(fields=['activity_type', 'timestamp']),
            models.Index(fields=['user', 'timestamp']),
        ]

    def __str__(self):
        return f"{self.get_activity_type_display()} by {self.user.username} at {self.timestamp}"
