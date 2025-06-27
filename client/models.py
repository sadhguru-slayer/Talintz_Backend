from django.db import models
from core.models import User
# Create your models here.


class Event(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True)
    title = models.CharField(max_length=255)
    start = models.DateField(null=True)
    type_choices = [
        ('Meeting', 'Meeting'),
        ('Deadline', 'Deadline'),
        ('Others', 'Others'),
    ]
    type = models.CharField(max_length=100, choices=type_choices, blank=True, null=True)
    
    # New field to store the custom notification time
    # Store the time in minutes
    notification_time = models.PositiveIntegerField(
        default=1440,  # Default: 1 day before (24 hours = 1440 minutes)
        help_text="Notification time in minutes before the event."
    )
    notification_sent = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.title} - {self.user.username}"


class Activity(models.Model):
    ACTIVITY_TYPES = [
        ('project_created', 'Project Created'),
        ('project_updated', 'Project Updated'),
        ('project_deleted', 'Project Deleted'),
        ('payment_received', 'Payment Received'),
        ('payment_failed', 'Payment Failed'),
        ('payment_sent', 'Payment Sent'),
        ('event_created', 'Event Created'),
        ('event_updated', 'Event Updated'),
        ('event_deleted', 'Event Deleted'),
        ('profile_updated', 'Profile Updated'),
        ('login', 'User Logged In'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    activity_type = models.CharField(max_length=50, choices=ACTIVITY_TYPES)
    description = models.CharField(max_length=255, blank=True, null=True)  # A detailed description of the activity
    timestamp = models.DateTimeField(auto_now_add=True)  # Auto-sets the timestamp when activity is created
    related_model = models.CharField(max_length=100, null=True, blank=True)  # Name of the related model (e.g., project, payment, etc.)
    related_object_id = models.PositiveIntegerField(null=True, blank=True)  # ID of the related object (e.g., project ID, payment ID)
    
    # Add new fields to store more detailed change information
    changes_detail = models.JSONField(null=True, blank=True)  # Store detailed changes
    
    class Meta:
        ordering = ['-timestamp']  # Order by most recent activity

    def __str__(self):
        return f'{self.user.username} - {self.activity_type} - {self.timestamp}'
    
    @property
    def formatted_changes(self):
        """Returns a formatted string of changes for display"""
        if self.changes_detail:
            return " | ".join(self.changes_detail.get('changes', []))
        return self.description
    
    
