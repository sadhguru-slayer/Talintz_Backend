from django.db import models
from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType

User = settings.AUTH_USER_MODEL

class Conversation(models.Model):
    # For simple chat, context_object is null
    # For workspace/project chat, context_object points to Project, OBSP, etc.
    context_type = models.ForeignKey(ContentType, null=True, blank=True, on_delete=models.SET_NULL)
    context_id = models.PositiveIntegerField(null=True, blank=True)
    context_object = GenericForeignKey('context_type', 'context_id')
    is_group = models.BooleanField(default=False)
    is_temporary = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_archived = models.BooleanField(default=False, db_index=True)
    # Optionally: archive_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        if self.context_object:
            return f"Context Chat: {self.context_object}"
        return f"Simple Chat {self.id}"

class ConversationParticipant(models.Model):
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name='participants')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    joined_at = models.DateTimeField(auto_now_add=True)
    last_read_at = models.DateTimeField(null=True, blank=True)
    is_deleted = models.BooleanField(default=False, db_index=True)  # Soft delete for user
    role = models.CharField(max_length=16, default="member")  # For group/workspace roles

    class Meta:
        unique_together = ('conversation', 'user')

class Message(models.Model):
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name='messages', db_index=True)
    sender = models.ForeignKey(User, on_delete=models.CASCADE, db_index=True)
    content = models.TextField(blank=True)
    file = models.FileField(upload_to='chat_files/', null=True, blank=True)
    reply_to = models.ForeignKey('self', null=True, blank=True, on_delete=models.SET_NULL, related_name='replies')
    type = models.CharField(max_length=16, default="text")  # "text", "file", "system", etc.
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_deleted_for_me = models.ManyToManyField(
        User,
        related_name='deleted_messages',
        blank=True
    )
    is_deleted_for_everyone = models.BooleanField(default=False, db_index=True)
    is_archived = models.BooleanField(default=False, db_index=True)
    archived_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Message {self.id} in {self.conversation_id}"

    class Meta:
        indexes = [
            models.Index(fields=['conversation', 'created_at']),
            models.Index(fields=['conversation', 'is_archived']),
        ]

class MessagePin(models.Model):
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name='pinned_messages')
    message = models.ForeignKey(Message, on_delete=models.CASCADE)
    pinned_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    pinned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('conversation', 'message')

class MessageReaction(models.Model):
    message = models.ForeignKey(Message, on_delete=models.CASCADE, related_name='reactions')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    emoji = models.CharField(max_length=32)
    reacted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('message', 'user', 'emoji')

class MessageDelete(models.Model):
    message = models.ForeignKey(Message, on_delete=models.CASCADE, related_name='deletions')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    deleted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('message', 'user')

class MessageStatus(models.Model):
    STATUS_CHOICES = [
        ('sent', 'Sent'),
        ('delivered', 'Delivered'),
        ('seen', 'Seen'),
        ('failed', 'Failed'),
    ]
    message = models.ForeignKey(Message, on_delete=models.CASCADE, related_name='statuses')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('message', 'user')
