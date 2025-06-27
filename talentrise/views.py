from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import TalentRiseProfile
from core.models import User, Project, Skill
from Profile.models import FreelancerProfile

# Create your views here.
class TalentRiseViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    
    @action(detail=False, methods=['GET'])
    def talentrise_students(self, request):
        """Get all TalentRise students"""
        students = User.objects.filter(is_talentrise=True)
        data = [{
            'id': student.id,
            'username': student.username,
            'profile': {
                'institution': getattr(student.talentrise_profile, 'institution', ''),
                'course': getattr(student.talentrise_profile, 'course', ''),
                'year_of_study': getattr(student.talentrise_profile, 'get_year_of_study_display', lambda: '')(),
            } if hasattr(student, 'talentrise_profile') else {}
        } for student in students]
        return Response(data)
    
    @action(detail=False, methods=['GET'])
    def suitable_projects(self, request):
        """Get projects suitable for TalentRise students"""
        projects = Project.objects.filter(
            is_talentrise_friendly=True, 
            status='pending'
        ).order_by('-created_at')
        
        data = [{
            'id': project.id,
            'title': project.title,
            'budget': str(project.budget),
            'deadline': project.deadline,
            'complexity_level': project.complexity_level,
            'skills_required': [skill.name for skill in project.skills_required.all()]
        } for project in projects]
        
        return Response(data)
