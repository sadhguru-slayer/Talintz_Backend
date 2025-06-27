from django.db import models
from core.models import User
from django.core.exceptions import ValidationError

# Create your models here.
class Collaboration(models.Model):
    admin = models.ManyToManyField(User, related_name='admin_collaborations')
    collaboration_name = models.CharField(max_length=255,verbose_name="Collaboration Title")
    collaboration_description = models.TextField(help_text="Write a Description for your Collaborations",null=True)
    STATUS_CHOICES = [
        ('inactive', 'Inactive'),
        ('active', 'Active'),
        ('completed', 'Completed'),
        ('removed', 'Removed'), 
    ]
    STATUS = models.CharField(max_length=10, choices=STATUS_CHOICES, default='inactive',verbose_name="Collaboration Status")
    
    # New collaboration_type field to define the nature of the collaboration
    COLLABORATION_TYPE_CHOICES = [
        ('freelancer', 'Freelancer Collaboration'),
        ('client', 'Client Collaboration'),
        ('project', 'Project Collaboration'),  # For general collaborations on a single project
        ('request_job', 'Request Job Collaboration'),
    ]
    collaboration_type = models.CharField(max_length=50, choices=COLLABORATION_TYPE_CHOICES, default='mixed')

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        first_admin = self.admin.first()  # Get the first admin user, if available
        if first_admin:
            return f"Collaboration '{self.collaboration_name}' led by {first_admin.username} ({self.get_collaboration_type_display()})"
        return f"Collaboration '{self.collaboration_name}' with no admins ({self.get_collaboration_type_display()})"

    def start_collaboration(self):
        """Start the collaboration by changing its status to 'active'."""
        self.status = 'active'
        self.save()

    def finish_collaboration(self):
        """Finish the collaboration by changing its status to 'completed'."""
        self.status = 'completed'
        self.save()

    def can_collaborate(self, sender, receiver):
        """Check if two users can collaborate based on roles and collaboration type."""
        if self.collaboration_type == 'client':
            return sender.role == 'client' and receiver.role == 'client'
        elif self.collaboration_type == 'freelancer':
            return sender.role == 'freelancer' and receiver.role == 'freelancer'
        elif self.collaboration_type == 'mixed':
            return (sender.role == 'client' and receiver.role == 'freelancer') or (sender.role == 'freelancer' and receiver.role == 'client')
        elif self.collaboration_type == 'project':
            return True  # In a project collaboration, it can be a mix of both, or any roles
        return False


class CollaborationMembership(models.Model):
    collaboration = models.ForeignKey(Collaboration, related_name='memberships', on_delete=models.CASCADE)
    user = models.ForeignKey(User, related_name='collaboration_memberships', on_delete=models.CASCADE)
    role = models.CharField(max_length=50, choices=[('admin', 'Admin'), ('collaborator', 'Collaborator')])
    join_date = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('collaboration', 'user')

    def __str__(self):
        return f"{self.user.username} ({self.role}) in {self.collaboration.collaboration_name}"

    def make_admin(self):
        """Change the role to 'admin'."""
        if self.role != 'admin':
            self.role = 'admin'
            self.save()

    def remove_user(self):
        """Remove a user from the collaboration."""
        self.delete()


class CollaborationInvitation(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('accepted', 'Accepted'),
        ('declined', 'Declined'),
    ]
    
    collaboration = models.ForeignKey(Collaboration, related_name='invitations', on_delete=models.CASCADE)
    sender = models.ForeignKey(User, related_name='sent_invitations', on_delete=models.CASCADE)
    receiver = models.ForeignKey(User, related_name='received_invitations', on_delete=models.CASCADE)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Invitation from {self.sender.username} to {self.receiver.username} for {self.collaboration.collaboration_name}"

    def accept(self):
        """Accept the invitation, add the user to the collaboration."""
        # Ensure the receiver's role is compatible with the collaboration's rules
        if not self.collaboration.can_collaborate(self.sender, self.receiver):
            raise ValidationError(f"Invalid roles for collaboration between {self.sender.username} and {self.receiver.username}.")

        # Add the receiver as a collaborator
        CollaborationMembership.objects.create(collaboration=self.collaboration, user=self.receiver, role='collaborator')
        self.status = 'accepted'
        self.save()

    def decline(self):
        """Decline the invitation."""
        self.status = 'declined'
        self.save()
