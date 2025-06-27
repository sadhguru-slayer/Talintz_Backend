from django.contrib import admin
from .models import *
# Register your models here.
admin.site.register(Message)
admin.site.register(MessageStatus)
admin.site.register(ConversationParticipant)
admin.site.register(Conversation)