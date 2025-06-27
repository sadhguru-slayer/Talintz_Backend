# Connection view sets
from django.shortcuts import render, get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from django.db.models import Q
from rest_framework.exceptions import NotFound
from .serializers import (
    ProjectSerializer, 
    TaskSerializer, 
    SpendingDistributionByProjectSerializer,
    UserSerializer,
    ConnectionSerializer
)
from Profile.models import (
    ClientProfile,Project,User,BankDetails
)
from rest_framework.decorators import permission_classes
from .models import Connection
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.views import APIView
from rest_framework import viewsets, status, generics

import calendar
from datetime import timedelta

from Profile.serializers import (
    ConnectionSendinSerializer
)
from django.http import JsonResponse

from talentrise.models import TalentRiseProfile, Institution, Course, FieldOfStudy

import json
from django.core.files.base import ContentFile


class ConnectionManageViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]
    # Accept connection
    @action(detail=True, methods=['post'])
    def accept_connection(self, request, pk=None):
        connection = get_object_or_404(Connection, id=pk)
        print(connection)
        if connection.to_user == request.user:
            connection.accept()
        connection_serialized = ConnectionSerializer(connection)
        return Response(connection_serialized.data, status=status.HTTP_200_OK)
    @action(detail=True, methods=['post'])
    def establish_connection(self, request, pk=None):
        from_user = request.user
        to_user = get_object_or_404(User, id=pk)
        if from_user == to_user:
            return Response({"error": "You cannot connect to yourself"}, status=status.HTTP_400_BAD_REQUEST)
        if Connection.objects.filter(from_user=from_user, to_user=to_user).exists():
            return Response({"error": "You are already connected"}, status=status.HTTP_400_BAD_REQUEST)
        connection = Connection(from_user=from_user, to_user=to_user)
        connection.save()
        connection_serialized = ConnectionSerializer(connection)
        return Response(connection_serialized.data, status=status.HTTP_200_OK)

    # Reject connection
    @action(detail=True, methods=['post'])
    def reject_connection(self, request, pk=None):
        connection = get_object_or_404(Connection, id=pk)
        if connection.to_user == request.user:
            connection.reject()
        connection_serialized = ConnectionSerializer(connection)
        return Response(connection_serialized.data, status=status.HTTP_200_OK)
    

class ConnectionView(generics.ListAPIView):
    serializer_class = ConnectionSendinSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
    
        # Fetch connections where the user is either 'from_user' or 'to_user' with status 'accepted'
        connections1 = Connection.objects.filter(to_user=user, status='accepted')
        
        connections2 = Connection.objects.filter(from_user=user, status='accepted')

        # Combine both querysets using union (| operator)
        connections = connections1 | connections2
        print(connections)
        return connections

    def list(self, request, *args, **kwargs):
        # Get the queryset for connections
        queryset = self.get_queryset()

        # Serialize the connections
        connection_serializer = self.get_serializer(queryset, many=True)

        # Return the response with the connection data and profiles of both users in each connection
        return Response(connection_serializer.data, status=200)


class ConnectionRequestView(generics.ListAPIView):
    serializer_class = ConnectionSendinSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
    
        # Fetch connections where the user is either 'from_user' or 'to_user' with status 'accepted'
        connections1 = Connection.objects.filter(to_user=user, status='pending')
        print(connections1)
        # Combine both querysets using union (| operator)
        connections = connections1
        return connections

    def list(self, request, *args, **kwargs):
        # Get the queryset for connections
        queryset = self.get_queryset()

        # Serialize the connections
        connection_serializer = self.get_serializer(queryset, many=True)

        # Return the response with the connection data and profiles of both users in each connection
        return Response(connection_serializer.data, status=200)


class GetConnectionStatusView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, userId):
        try:
            other_user = User.objects.get(id=userId)
        except User.DoesNotExist:
            return Response({"error": "User not found"}, status=404)

        user = request.user

        # Check for connection in both directions
        connection = Connection.objects.filter(
            (Q(from_user=user) & Q(to_user=other_user)) | (Q(from_user=other_user) & Q(to_user=user))
        ).first()

        status = "notset"
        is_connected = False
        connection_id = None

        if connection:
            # If the connection is pending and the current user is the recipient, show 'not_accepted'
            if (
                connection.status == "pending"
                and connection.to_user == user
                and connection.from_user == other_user
            ):
                status = "not_accepted"
            else:
                status = connection.status
            is_connected = status == "accepted"
            connection_id = connection.id

        return Response({
            "status": status,
            "is_connected": is_connected,
            "connection_id": connection_id
        })


