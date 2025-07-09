from django.shortcuts import render
# Freelancer Workspace

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from workspace.models import Workspace
from core.models import Notification
from django.contrib.contenttypes.models import ContentType
from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from rest_framework import status

# Create your views here.

class WorkspaceNotificationsAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, workspace_id):
        # Ensure user is a participant in the workspace
        workspace = get_object_or_404(
            Workspace,
            id=workspace_id,
            participants__user=request.user
        )

        # Get ContentType for Workspace
        workspace_ct = ContentType.objects.get_for_model(Workspace)

        # Fetch notifications where related_object is this workspace
        notifications = Notification.objects.filter(
            user = request.user,
            content_type=workspace_ct,
            related_model_id=workspace.id
        ).order_by('-created_at')

        def serialize_notification(n):
            return {
                "id": n.id,
                "type": n.type,
                "subtype": n.subtype,
                "title": n.title,
                "notification_text": n.notification_text,
                "is_read": n.is_read,
                "created_at": n.created_at.isoformat(),
                "priority": n.priority,
                "metadata": n.metadata,
            }

        return Response({
            "count": notifications.count(),
            "results": [serialize_notification(n) for n in notifications]
        }, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def mark_notification_read(request, workspace_id, notification_id):
    from core.models import Notification
    from workspace.models import Workspace
    from django.shortcuts import get_object_or_404

    # Ensure user is a participant in the workspace
    workspace = get_object_or_404(
        Workspace,
        id=workspace_id,
        participants__user=request.user
    )

    notification = get_object_or_404(Notification, id=notification_id)
    # Optionally, check that notification is for this workspace
    if notification.related_model_id != workspace.id:
        return Response({"error": "Notification does not belong to this workspace."}, status=403)

    notification.is_read = True
    notification.save(update_fields=["is_read"])
    return Response({"success": True, "id": notification.id, "is_read": True}, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def workspace_type(request, workspace_id):
    try:
        workspace = Workspace.objects.get(id=workspace_id, participants__user=request.user)
    except Workspace.DoesNotExist:
        return Response({"error": "Workspace not found or access denied"}, status=404)
    content_object = workspace.content_object
    workspace_type = "obsp" if hasattr(content_object, 'template') else "project"
    return Response({"type": workspace_type})

