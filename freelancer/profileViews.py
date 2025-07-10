# Add views related to Freelancer Profile

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework import status
from Profile.models import FreelancerProfile, Feedback, Certification, VerificationDocument, BankDetails
from core.models import Connection, Project, Skill
from django.contrib.auth import get_user_model
from django.db.models import Q
from django.db import transaction
from core.serializers import ProjectResponseSerializer
from datetime import datetime
import json
from rest_framework.parsers import MultiPartParser, FormParser

User = get_user_model()

class FreelancerProfileDataView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user_id = request.query_params.get('userId')
        tab = request.query_params.get('tab', 'all')
        
        if user_id:
            try:
                user = User.objects.get(id=user_id)
            except User.DoesNotExist:
                return Response({"error": "User not found"}, status=404)
        else:
            user = request.user

        try:
            profile = FreelancerProfile.objects.get(user=user)
        except FreelancerProfile.DoesNotExist:
            return Response({"error": "Profile not found"}, status=404)

        is_self = (user == request.user)

        # Base data for all tabs
        base_data = {
            "user": {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "role": user.role,
                "joined": user.date_joined,
            },
            "profile": {
                "tier": profile.current_level or "Bronze",
                "sub_level": profile.current_sub_level,
                "points": profile.points,
                "avg_rating": profile.average_rating,
                "profile_picture": request.build_absolute_uri(profile.profile_picture.url) if profile.profile_picture else None,
            }
        }

        # Return specific data based on tab
        if tab == 'personal':
            data = {
                **base_data,
                "profile": {
                    **base_data["profile"],
                    "gender": profile.gender,
                    "dob": profile.dob,
                    "bio": profile.bio,
                    "about": profile.description,
                    "profile_picture": request.build_absolute_uri(profile.profile_picture.url) if profile.profile_picture else None,
                }
            }
        elif tab == 'professional':
            data = {
                **base_data,
                "profile": {
                    **base_data["profile"],
                    "professional_title": profile.profiessional_title,
                    "hourly_rate": profile.hourly_rate,
                    "availability": profile.availability_status,
                    "skills": list(profile.skills.values("id", "name")),
                    "profile_picture": request.build_absolute_uri(profile.profile_picture.url) if profile.profile_picture else None,
                }
            }
        elif tab == 'portfolio':
            portfolio = [
                {
                    "id": item.id,
                    "title": item.title,
                    "description": item.description,
                    "project_url": item.project_url,
                    "image": request.build_absolute_uri(item.image.url) if item.image else None,
                    "technologies_used": item.technologies_used,
                    "start_date": item.start_date,
                    "end_date": item.end_date,
                    "verified": item.verified,
                }
                for item in profile.portfolio_items.all()
            ]
            data = {
                **base_data,
                "profile": {
                    **base_data["profile"],
                    "portfolio": portfolio,
                    "profile_picture": request.build_absolute_uri(profile.profile_picture.url) if profile.profile_picture else None,
                }
            }
        elif tab == 'certifications':
            certifications = [
                {
                    "id": cert.id,
                    "name": cert.name,
                    "issuer": cert.issuing_organization,
                    "date": cert.issue_date,
                    "expiry_date": cert.expiry_date,
                    "credential_id": cert.credential_id,
                    "verified": cert.verified
                }
                for cert in profile.certifications.all()
            ]
            data = {
                **base_data,
                "profile": {
                    **base_data["profile"],
                    "certifications": certifications,
                    "profile_picture": request.build_absolute_uri(profile.profile_picture.url) if profile.profile_picture else None,
                }
            }
        elif tab == 'banking':
            # Bank details (only for self)
            bank = profile.bank_details if is_self else None
            bank_details = {
                "id": bank.id,
                "bank_name": bank.bank_name,
                "account_number": bank.account_number,
                "ifsc_code": bank.ifsc_code,
                "account_holder_name": bank.account_holder_name,
                "branch_name": bank.branch_name,
                "swift_code": bank.swift_code,
                "primary": bank.primary,
                "verified": bank.verified,
            } if bank else None

            # Verification Documents
            documents = [
                {
                    "id": doc.id,
                    "document_type": doc.document_type,
                    "document_number": doc.document_number,
                    "expiry_date": doc.expiry_date,
                    "verification_notes": doc.verification_notes,
                    "verified": doc.verified
                }
                for doc in profile.verification_documents.all()
            ]
            
            data = {
                **base_data,
                "profile": {
                    **base_data["profile"],
                    "bank_details": bank_details,
                    "documents": documents,
                    "profile_picture": request.build_absolute_uri(profile.profile_picture.url) if profile.profile_picture else None,
                }
            }
        else:
            # Return all data
            # Connections count
            connections = Connection.objects.filter(
                (Q(from_user=user) | Q(to_user=user)) & Q(status='accepted')
            ).count()

            # Reviews
            reviews = Feedback.objects.filter(to_user=user).values(
                "from_user__username", "rating", "feedback", "created_at"
            )

            # Certifications
            certifications = [
                {
                    "name": cert.name,
                    "issuer": cert.issuing_organization,
                    "date": cert.issue_date,
                    "expiry_date": cert.expiry_date,
                    "credential_id": cert.credential_id,
                    "verified": cert.verified
                }
                for cert in profile.certifications.all()
            ]

            # Verification Documents
            documents = [
                {
                    "document_type": doc.document_type,
                    "document_number": doc.document_number,
                    "expiry_date": doc.expiry_date,
                    "verified": doc.verified
                }
                for doc in profile.verification_documents.all()
            ]

            # Completed Projects (Experience)
            completed_projects = Project.objects.filter(
                assigned_to=user,
                status='completed'
            )
            completed_projects_data = ProjectResponseSerializer(completed_projects, many=True).data

            # Portfolio (already selected by user)
            portfolio = [
                {
                    "title": item.title,
                    "description": item.description,
                    "project_url": item.project_url,
                    "image": request.build_absolute_uri(item.image.url) if item.image else None,
                    "technologies_used": item.technologies_used,
                    "start_date": item.start_date,
                    "end_date": item.end_date,
                    "verified": item.verified,
                }
                for item in profile.portfolio_items.all()
            ]

            # Skills
            skills = list(profile.skills.values("id", "name"))

            # Addresses
            addresses = list(profile.addresses.values())

            # Company details
            company = profile.company
            company_details = {
                "name": company.name,
                "registration_number": company.registration_number,
                "registration_date": company.registration_date,
                "company_type": company.company_type,
                "industry": company.industry,
                "website": company.website,
                "gst_number": company.gst_number,
                "pan_number": company.pan_number,
                "annual_turnover": company.annual_turnover,
                "employee_count": company.employee_count,
                "verified": company.verified,
            } if company else None

            # Bank details (only for self)
            bank = profile.bank_details if is_self else None
            bank_details = {
                "bank_name": bank.bank_name,
                "account_number": bank.account_number,
                "ifsc_code": bank.ifsc_code,
                "account_holder_name": bank.account_holder_name,
                "branch_name": bank.branch_name,
                "swift_code": bank.swift_code,
                "verified": bank.verified,
            } if bank else None

            # Profile header details
            data = {
                "user": {
                    "id": user.id,
                    "username": user.username,
                    "email": user.email,
                    "role": user.role,
                    "joined": user.date_joined,
                },
                "profile": {
                    "tier": profile.current_level or "Bronze",
                    "sub_level": profile.current_sub_level,
                    "points": profile.points,
                    "connections": connections,
                    "avg_rating": profile.average_rating,
                    "about": profile.description,
                    "bio": profile.bio,
                    'professional_title': profile.profiessional_title,
                    'hourly_rate': profile.hourly_rate,
                    'availability': profile.availability_status,
                    'dob': profile.dob,
                    'certifications': certifications,
                    'documents': documents,
                    "company_details": {
                        "name": company_details["name"] if company_details else None,
                        "website": company_details["website"] if company_details else None,
                    } if not is_self else company_details,
                    "bank_details": bank_details if is_self else None,
                    "addresses": addresses,
                    "skills": skills,
                    "experience": completed_projects_data,
                    "portfolio": portfolio,
                    "profile_picture": request.build_absolute_uri(profile.profile_picture.url) if profile.profile_picture else None,
                },
                "reviews": list(reviews),
            }
        return Response(data)

# Update Viewsets for each tab
class PersonalInfoUpdateView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def put(self, request):
        try:
            profile = FreelancerProfile.objects.get(user=request.user)
            
            # Update user fields
            user = request.user
            if 'name' in request.data:
                user.username = request.data['name']
            if 'email' in request.data:
                user.email = request.data['email']
            user.save()

            # Update profile fields
            if 'gender' in request.data:
                profile.gender = request.data['gender']
            if 'dob' in request.data:
                profile.dob = request.data['dob']
            if 'bio' in request.data:
                profile.bio = request.data['bio']
            if 'description' in request.data:
                profile.description = request.data['description']
            
            profile.save()
            
            return Response({
                "message": "Personal information updated successfully",
                "status": "success"
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response({
                "error": f"Failed to update personal information: {str(e)}",
                "status": "error"
            }, status=status.HTTP_400_BAD_REQUEST)

class ProfessionalInfoUpdateView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def put(self, request):
        try:
            profile = FreelancerProfile.objects.get(user=request.user)
            
            # Only update fields that are provided in the request
            if 'title' in request.data:
                profile.profiessional_title = request.data['title']
            if 'hourly_rate' in request.data:
                profile.hourly_rate = request.data['hourly_rate']
            if 'availability' in request.data:
                profile.availability_status = request.data['availability']
            
            # Update skills only if provided
            if 'skills' in request.data:
                profile.skills.clear()
                for skill_name in request.data['skills']:
                    skill, created = Skill.objects.get_or_create(name=skill_name)
                    profile.skills.add(skill)
            
            profile.save()
        
            return Response({
                "message": "Professional information updated successfully",
                "status": "success"
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response({
                "error": f"Failed to update professional information: {str(e)}",
                "status": "error"
            }, status=status.HTTP_400_BAD_REQUEST)

class PortfolioUpdateView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def put(self, request):
        try:
            profile = FreelancerProfile.objects.get(user=request.user)
            
            # Clear existing portfolio items
            profile.portfolio_items.all().delete()
            
            # Add new portfolio items
            if 'portfolio' in request.data:
                for item_data in request.data['portfolio']:
                    from Profile.models import PortfolioItem
                    
                    portfolio_item = PortfolioItem.objects.create(
                        title=item_data.get('title', ''),
                        description=item_data.get('description', ''),
                        project_url=item_data.get('link', ''),
                        technologies_used=item_data.get('technologies', []),
                        start_date=item_data.get('start_date'),
                        end_date=item_data.get('end_date'),
                    )
                    profile.portfolio_items.add(portfolio_item)
            
            profile.save()
            
            return Response({
                "message": "Portfolio updated successfully",
                "status": "success"
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response({
                "error": f"Failed to update portfolio: {str(e)}",
                "status": "error"
            }, status=status.HTTP_400_BAD_REQUEST)

class CertificationsUpdateView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def put(self, request):
        try:
            profile = FreelancerProfile.objects.get(user=request.user)
            
            # Clear existing certifications
            profile.certifications.all().delete()
            
            # Add new certifications
            if 'certifications' in request.data:
                for cert_data in request.data['certifications']:
                    certification = Certification.objects.create(
                        name=cert_data.get('name', ''),
                        issuing_organization=cert_data.get('issuer', ''),
                        issue_date=cert_data.get('date'),
                        expiry_date=cert_data.get('expiry_date'),
                        credential_id=cert_data.get('credential_id', ''),
                        credential_url=cert_data.get('verification_url', ''),
                    )
                    profile.certifications.add(certification)
            
            profile.save()
            
            return Response({
                "message": "Certifications updated successfully",
                "status": "success"
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response({
                "error": f"Failed to update certifications: {str(e)}",
                "status": "error"
            }, status=status.HTTP_400_BAD_REQUEST)

class BankingUpdateView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def put(self, request):
        try:
            profile = FreelancerProfile.objects.get(user=request.user)
            
            # Update bank details
            if 'bank_details' in request.data:
                bank_data = request.data['bank_details']
                
                if profile.bank_details:
                    bank = profile.bank_details
                else:
                    bank = BankDetails.objects.create()
                    profile.bank_details = bank
                
                if 'bank_name' in bank_data:
                    bank.bank_name = bank_data['bank_name']
                if 'account_number' in bank_data:
                    bank.account_number = bank_data['account_number']
                if 'ifsc_code' in bank_data:
                    bank.ifsc_code = bank_data['ifsc_code']
                if 'account_holder_name' in bank_data:
                    bank.account_holder_name = bank_data['account_holder_name']
                if 'branch_name' in bank_data:
                    bank.branch_name = bank_data['branch_name']
                if 'swift_code' in bank_data:
                    bank.swift_code = bank_data['swift_code']
                if 'primary' in bank_data:
                    bank.primary = bank_data['primary']
                
                bank.save()
                profile.save()
            
            # Update verification documents
            if 'verification_documents' in request.data:
                # Clear existing documents
                profile.verification_documents.all().delete()
                
                # Add new documents
                for doc_data in request.data['verification_documents']:
                    document = VerificationDocument.objects.create(
                        document_type=doc_data.get('document_type', ''),
                        document_number=doc_data.get('document_number', ''),
                        expiry_date=doc_data.get('expiry_date'),
                        verification_notes=doc_data.get('verification_notes', ''),
                        user=request.user,
                    )
                    profile.verification_documents.add(document)
            
            profile.save()
            
            return Response({
                "message": "Banking information updated successfully",
                "status": "success"
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response({
                "error": f"Failed to update banking information: {str(e)}",
                "status": "error"
            }, status=status.HTTP_400_BAD_REQUEST)

class ProfilePictureUpdateView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    @transaction.atomic
    def put(self, request):
        try:
            profile = FreelancerProfile.objects.get(user=request.user)
            if 'profile_picture' not in request.FILES:
                return Response({"error": "No file uploaded"}, status=status.HTTP_400_BAD_REQUEST)
            profile.profile_picture = request.FILES['profile_picture']
            profile.save()
            return Response({
                "message": "Profile picture updated successfully",
                "profile_picture": profile.profile_picture.url
            }, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({
                "error": f"Failed to update profile picture: {str(e)}"
            }, status=status.HTTP_400_BAD_REQUEST)