from django.contrib import admin
from .models import *
# Register your models here.
admin.site.register(Collaboration)
admin.site.register(CollaborationInvitation)
admin.site.register(CollaborationMembership)