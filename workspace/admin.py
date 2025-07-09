from django.contrib import admin
from .models import Workspace, WorkspaceParticipant, WorkspaceAttachment, WorkspaceRevision, WorkspaceDispute
# Register your models here.
from .models import WorkspaceActivity,WorkspaceBox
admin.site.register(Workspace)
admin.site.register(WorkspaceParticipant)
admin.site.register(WorkspaceAttachment)
admin.site.register(WorkspaceRevision)
admin.site.register(WorkspaceDispute)
admin.site.register(WorkspaceActivity)
admin.site.register(WorkspaceBox)