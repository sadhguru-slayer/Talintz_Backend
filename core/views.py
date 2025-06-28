from django.shortcuts import render
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate
from rest_framework import status, views, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from .models import *
from django.middleware.csrf import get_token
from datetime import timedelta
from client.models import Activity,Event
from Profile.models import *
from .serializers import *
from django.db.models import Q
from rest_framework.pagination import PageNumberPagination
from django.core.cache import cache
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework import status
from .models import User, Project, Category
from .serializers import UserSerializer, ProjectSerializer, CategorySerializer
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.views import View
from .models import Task, Notification
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.db import transaction
from .models import User  # This will point to your custom User model if defined
from dateutil import parser
from rest_framework import serializers
from .serializers import ProjectResponseSerializer, TaskResponseSerializer
import traceback
from django.utils.dateparse import parse_date
from django.db import IntegrityError
from django.core.validators import validate_email
from decimal import Decimal
from django.core.validators import MinValueValidator, MaxValueValidator
from financeapp.models.hold import Hold
from financeapp.models import Wallet

# Create your views here.
class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer

class IsprofiledDetails(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, userId=None):
        # If userId is provided, fetch that user; else use the authenticated user
        if userId is not None:
            try:
                got_user = User.objects.get(id=userId)
            except User.DoesNotExist:
                return Response({"detail": "User not found."}, status=404)
        else:
            got_user = request.user

        # Get profile picture based on role
        if got_user.role == 'client':
            try:
                profile_picture = ClientProfile.objects.get(user=got_user).profile_picture or None
            except ClientProfile.DoesNotExist:
                profile_picture = None
        else:
            try:
                profile_picture = FreelancerProfile.objects.get(user=got_user).profile_picture or None
            except FreelancerProfile.DoesNotExist:
                profile_picture = None

        is_profiled = got_user.is_profiled
        role = got_user.role
        usename = got_user.username
        email = got_user.email
        is_email_verified = getattr(got_user, "is_email_verified", False)

        if is_profiled and profile_picture:
            profile_picture = profile_picture.url
        else:
            profile_picture = None

        result = {
            "user": {
                "id": got_user.id,
                "is_profiled": is_profiled,
                "role": role,
                "username": usename,
                "email": email,
                "is_email_verified": is_email_verified,
                "profile_picture": profile_picture
            }
        }
        return Response(result, status=200)



class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        identifier = request.data.get('identifier')
        password = request.data.get('password')

        if not identifier or not password:
            return Response(
                {"error": "Email/Username and Password are required."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check if identifier is an email
        is_email = '@' in identifier

        try:
            if is_email:
                # Try to find user by email
                try:
                    user_obj = User.objects.get(email=identifier)
                    user = authenticate(request, username=user_obj.username, password=password)
                    if not user:
                        return Response({
                            "error": "Invalid password. Please try again or use your username instead.",
                            "suggestion": "username",
                            "exists": True
                        }, status=status.HTTP_401_UNAUTHORIZED)
                except User.DoesNotExist:
                    return Response({
                        "error": "No account found with this email.",
                        "suggestion": "register",
                        "exists": False
                    }, status=status.HTTP_401_UNAUTHORIZED)
            else:
                # Try to find user by username
                try:
                    user_obj = User.objects.get(username=identifier)
                    user = authenticate(request, username=identifier, password=password)
                    if not user:
                        return Response({
                            "error": "Invalid password. Please try again or use your email instead.",
                            "suggestion": "email",
                            "exists": True
                        }, status=status.HTTP_401_UNAUTHORIZED)
                except User.DoesNotExist:
                    return Response({
                        "error": "No account found with this username.",
                        "suggestion": "register",
                        "exists": False
                    }, status=status.HTTP_401_UNAUTHORIZED)

            if user:
                frontend_role = 'client' if user.role == 'client' else 'freelancer'
                refresh = RefreshToken.for_user(user)
                access_token = str(refresh.access_token)

                response_data = {
                    "message": "Login successful.",
                    "access": access_token,
                    "refresh": str(refresh),
                    "role": frontend_role,
                    "user_id": user.id
                }

                if user.role == 'student':
                    response_data["is_talentrise"] = True

                response = Response(response_data, status=status.HTTP_200_OK)
                response.set_cookie(
                    'accessToken', access_token,
                    max_age=timedelta(days=30),
                    secure=True,
                    httponly=True,
                    samesite='Strict'
                )
                return response

        except Exception as e:
            return Response({
                "error": "Login failed. Please try again.",
                "suggestion": "retry"
            }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([AllowAny])
def check_email_exists(request):
    """
    Check if an email already exists in the system
    """
    email = request.query_params.get('email', '')
    
    try:
        # Validate email format
        validate_email(email)
        
        # Check if email exists
        exists = User.objects.filter(email=email).exists()
        return Response({'exists': exists})
    except ValidationError:
        return Response({'error': 'Invalid email format'}, status=status.HTTP_400_BAD_REQUEST)


class RegisterView(APIView):
    permission_classes = [AllowAny]

    def generate_unique_username(self, email, attempt=0):
        """Generate a unique username based on email."""
        base_username = email.split('@')[0]
        if attempt == 0:
            username = base_username
        else:
            username = f"{base_username}{attempt}"
            
        try:
            User.objects.get(username=username)
            return self.generate_unique_username(email, attempt + 1)
        except User.DoesNotExist:
            return username

    def generate_nickname(self, email):
        """Generate a friendly nickname from the email"""
        name_part = email.split('@')[0]
        clean_name = ''.join(c for c in name_part if c.isalpha())
        return clean_name.capitalize() if clean_name else name_part.capitalize()

    def validate_referral_code(self, referral_code):
        """Validate referral code and return referrer user"""
        if not referral_code:
            return None
            
        try:
            # Find user with this referral code
            referrer = User.objects.get(referral_code=referral_code)
            return referrer
        except User.DoesNotExist:
            return None

    def create_referral_relationship(self, referrer, referred_user, user_type, referral_code):
        """Create referral relationship and prevent duplicates"""
        try:
            # Check if referral already exists (prevent duplicates)
            existing_referral = Referral.objects.filter(
                referrer=referrer,
                referred_email=referred_user.email
            ).first()
            
            if existing_referral:
                # Update existing referral with the new user
                existing_referral.referred_user = referred_user
                existing_referral.accepted = True
                existing_referral.accepted_at = timezone.now()
                existing_referral.save()
                return existing_referral
            
            # Create new referral
            referral = Referral.objects.create(
                referrer=referrer,
                referred_email=referred_user.email,
                referred_user=referred_user,
                user_type=user_type,
                code=referral_code,  # Now referral_code is available
                accepted=True,
                accepted_at=timezone.now()
            )
            return referral
            
        except Exception as e:
            print(f"Error creating referral: {e}")
            return None

    def post(self, request):
        # Debug: Log incoming request data
        print("\n=== DEBUG: REGISTER REQUEST DATA ===")
        print("Raw request data:", request.data)
        print("Headers:", request.headers)
        
        data = request.data.copy()  # Create mutable copy
        
        # Debug: Log processed data
        print("\n=== DEBUG: PROCESSED DATA ===")
        print("Email:", data.get('email'))
        print("Role:", data.get('role'))
        print("Password:", bool(data.get('password')))
        print("Confirm Password:", bool(data.get('confirm_password')))
        print("Referral Code:", data.get('referral_code', 'None'))
        
        # Validate required fields
        required_fields = ['email', 'password', 'confirm_password', 'role']
        missing_fields = [field for field in required_fields if field not in data]
        if missing_fields:
            print("\n=== DEBUG: MISSING FIELDS ===")
            print("Missing:", missing_fields)
            return Response(
                {"error": f"Missing required fields: {', '.join(missing_fields)}"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Validate email format
        try:
            validate_email(data['email'])
            print("\n=== DEBUG: EMAIL VALIDATION ===")
            print("Email is valid.")
        except ValidationError:
            print("\n=== DEBUG: EMAIL VALIDATION ===")
            print("Email is invalid.")
            return Response(
                {"error": "Invalid email format"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Check if email exists
        if User.objects.filter(email=data['email']).exists():
            print("\n=== DEBUG: EMAIL EXISTS ===")
            print("Email already registered.")
            return Response({
                "error": "This email is already registered. Please use a different email or login.",
                "action": "login"
            }, status=status.HTTP_400_BAD_REQUEST)

        # Validate role
        valid_roles = ['client', 'freelancer', 'student']
        if data['role'].lower() not in valid_roles:
            print("\n=== DEBUG: INVALID ROLE ===")
            print("Invalid role:", data['role'])
            return Response(
                {"error": f"Invalid role selected. Valid roles: {', '.join(valid_roles)}"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Validate passwords match
        if data['password'] != data['confirm_password']:
            print("\n=== DEBUG: PASSWORD MISMATCH ===")
            print("Password and confirm_password do not match.")
            return Response(
                {"error": "Password and Confirm Password must match."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Debug: Log referral code handling
        referral_code = data.get('referral_code', '').strip()
        if referral_code:
            print("\n=== DEBUG: REFERRAL CODE ===")
            print("Referral code provided:", referral_code)
        
        try:
            # Debug: Log password validation
            print("\n=== DEBUG: PASSWORD VALIDATION ===")
            validate_password(data['password'])
            print("Password is valid.")

            # Handle referral code
        referrer = None
        referral_created = False
        
        if referral_code:
            referrer = self.validate_referral_code(referral_code)
            if not referrer:
                return Response({
                    "error": "Invalid referral code. Please check and try again."
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Prevent self-referral
            if referrer.email == data['email']:
                return Response({
                    "error": "You cannot refer yourself."
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Generate unique username and nickname
            username = self.generate_unique_username(data['email'])
            nickname = self.generate_nickname(data['email'])
            
            # Set role and TalentRise status
            role = data.get('role', 'student').lower()
            is_talentrise = data.get('is_talentrise', False)

            with transaction.atomic():
                # Create user
                user = User.objects.create_user(
                    email=data['email'],
                    username=username,
                    nickname=nickname,
                    password=data['password'],
                    role=role,
                    is_talentrise=is_talentrise
                )
                
                # Create appropriate profile
                if role == 'client':
                    ClientProfile.objects.create(
                        user=user,
                        primary_email=data['email']
                    )
                else:
                    FreelancerProfile.objects.create(
                        user=user,
                        primary_email=data['email']
                    )

                # Handle referral relationship
                if referrer:
                    user_type = 'client' if role == 'client' else 'freelancer'
                    referral = self.create_referral_relationship(
                        referrer=referrer,
                        referred_user=user,
                        user_type=user_type,
                        referral_code=referral_code
                    )
                    if referral:
                        referral_created = True
                        print(f"Referral created: {referrer.username} -> {user.username}")

                # Generate tokens
                refresh = RefreshToken.for_user(user)
                access_token = str(refresh.access_token)

                response_data = {
                    "message": "Account created successfully!",
                    "access": access_token,
                    "refresh": str(refresh),
                    "role": role,
                    "is_talentrise": is_talentrise,
                    "username": username,
                    "nickname": nickname
                }

                # Add referral info to response
                if referral_created:
                    response_data["referral_info"] = {
                        "referred_by": referrer.username,
                        "referral_code_used": referral_code
                    }

                return Response(response_data, status=status.HTTP_201_CREATED)

        except ValidationError as e:
            print("\n=== DEBUG: PASSWORD VALIDATION ERROR ===")
            print("Password error:", str(e))
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            print("\n=== DEBUG: UNEXPECTED ERROR ===")
            print("Error:", str(e))
            return Response(
                {"error": "Registration failed. Please try again."},
                status=status.HTTP_400_BAD_REQUEST
            )

class LogoutView(APIView):
    permission_classes = [IsAuthenticated]  # Ensure the user is authenticated

    def post(self, request):
        """
        Handle user logout by blacklisting the refresh token and clearing the session.
        """
        refresh_token = request.data.get('refreshToken')

        if not refresh_token:
            return Response({"error": "Refresh token is required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            # Blacklist the refresh token
            token = RefreshToken(refresh_token)
            token.blacklist()
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        # Clear the session (optional)
        request.session.flush()

        return Response({"message": "Logout successful!"}, status=status.HTTP_200_OK)


from financeapp.models import Wallet

class CreateProjectView(APIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        print("CreateProjectView.post() called")
        client = request.user
        
        # Remove all task-related data extraction
        project_milestones_data = request.data.get('milestones', [])
        total_auto_payment = request.data.get('total_auto_payment', 0)
        client_skill_level = request.data.get('client_skill_level', 'beginner')
        
        # Extract pricing strategy data (matching frontend field names)
        pricing_strategy = request.data.get('pricing_strategy', 'fixed')
        hourly_rate = request.data.get('hourly_rate', 0)
        estimated_hours = request.data.get('estimated_hours', 0)
        max_hours = request.data.get('max_hours', 0)
        
        # Extract hourly project management fields
        allow_hour_flexibility = request.data.get('allow_hour_flexibility', True)
        require_milestone_approval = request.data.get('require_milestone_approval', True)
        emergency_hours = request.data.get('emergency_hours', 0)
        
        # Validate pricing strategy data
        if pricing_strategy == 'hourly':
            if not hourly_rate or hourly_rate <= 0:
                return Response({"message": "Hourly rate must be greater than 0 for hourly projects"}, 
                              status=status.HTTP_400_BAD_REQUEST)
            if not estimated_hours or estimated_hours <= 0:
                return Response({"message": "Estimated hours must be greater than 0 for hourly projects"}, 
                              status=status.HTTP_400_BAD_REQUEST)
            if not max_hours or max_hours <= 0:
                return Response({"message": "Maximum hours must be greater than 0 for hourly projects"}, 
                              status=status.HTTP_400_BAD_REQUEST)
            if max_hours < estimated_hours:
                return Response({"message": "Maximum hours cannot be less than estimated hours"}, 
                              status=status.HTTP_400_BAD_REQUEST)
        
        # Check wallet balance for automated payments
        if total_auto_payment > 0:
            wallet_balance = Wallet.objects.get(user=client).balance
            if wallet_balance < total_auto_payment:
                return Response({"message": "Insufficient wallet balance."}, 
                              status=status.HTTP_400_BAD_REQUEST)
            else:
                wallet = Wallet.objects.get(user=client)
                wallet.hold_balance += total_auto_payment
                wallet.save()

        # Create Project with error handling
        try:
            # Parse the deadline string to a proper date object
            deadline_str = request.data.get('deadline')
            deadline = parse_date(deadline_str)
            if not deadline:
                return Response({"message": "Invalid deadline format"}, status=status.HTTP_400_BAD_REQUEST)
            
            # Calculate budget based on pricing strategy
            budget = request.data.get('budget', 0)
            if pricing_strategy == 'hourly':
                # For hourly projects, budget is calculated as max_hours * hourly_rate
                budget = max_hours * hourly_rate
            
            # Create the project with all pricing strategy fields
            project = Project.objects.create(
                title=request.data['title'],
                description=request.data['description'],
                budget=budget,
                deadline=deadline,
                domain=Category.objects.get(id=request.data['domain']),
                client=client,
                status='pending',
                # Pricing strategy fields
                pricing_strategy=pricing_strategy,
                hourly_rate=hourly_rate if pricing_strategy == 'hourly' else None,
                estimated_hours=estimated_hours if pricing_strategy == 'hourly' else None,
                max_hours=max_hours if pricing_strategy == 'hourly' else None,
                # Hourly project management fields
                allow_hour_flexibility=allow_hour_flexibility,
                require_milestone_approval=require_milestone_approval,
                emergency_hours=emergency_hours,
                # Existing fields
                client_skill_level=client_skill_level,
                show_simplified_ui=(client_skill_level == 'beginner'),
                auto_schedule_tasks=request.data.get('auto_schedule_tasks', True)
            )
            
            # Handle Project Milestones only
            if project_milestones_data:
                self.create_project_milestones(project, project_milestones_data)
                project.update_payment_strategy()

            # Handle skills and create events
            self.handle_skills_and_events(project, client)
            
            # Use the dedicated response serializers
            try:
                print("Serializing project response...")
                project_data = ProjectResponseSerializer(project).data
                print("Project serialization successful!")
                
                return Response({
                    "message": "Project created successfully",
                    "project": project_data
                }, status=status.HTTP_201_CREATED)
                
            except Exception as serialize_error:
                print(f"Serialization error: {str(serialize_error)}")
                print(traceback.format_exc())
                # Fall back to basic response if serialization fails
                return Response({
                    "message": "Project created successfully, but error in response formatting",
                    "project_id": project.id,
                    "project_title": project.title
                }, status=status.HTTP_201_CREATED)

        except Exception as e:
            print(f"Project creation error: {str(e)}")
            print(traceback.format_exc())
            return Response({"message": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    def create_project_milestones(self, project, milestones_data):
        """Create only project-level milestones with smart escrow logic"""
        for milestone_data in milestones_data:
            # Handle milestone type based on project pricing strategy
            milestone_type = milestone_data.get('milestone_type', 'hybrid')
            
            # For hourly projects, set milestone type to 'hourly'
            if project.pricing_strategy == 'hourly':
                milestone_type = 'hourly'
            
            # Calculate escrow amount based on pricing strategy
            escrow_amount = 0
            if project.pricing_strategy == 'fixed':
                # For fixed price projects, use the milestone amount
                escrow_amount = float(milestone_data.get('amount', 0))
            elif project.pricing_strategy == 'hourly':
                # For hourly projects, calculate based on max hours
                max_hours = milestone_data.get('max_hours', 0)
                if max_hours and project.hourly_rate:
                    escrow_amount = float(max_hours) * float(project.hourly_rate)
            
            # Create milestone with all required fields
            milestone = Milestone.objects.create(
                title=milestone_data.get('title', ''),
                project=project,
                amount=float(milestone_data.get('amount', 0)),
                due_date=milestone_data.get('due_date') if project.pricing_strategy == 'fixed' else None,
                milestone_type=milestone_type,
                is_automated=milestone_data.get('is_automated', True),
                status='pending',
                estimated_hours=milestone_data.get('estimated_hours') if project.pricing_strategy == 'hourly' else None,
                max_hours=milestone_data.get('max_hours') if project.pricing_strategy == 'hourly' else None,
                priority_level=milestone_data.get('priority_level', 'medium'),
                quality_requirements=milestone_data.get('quality_requirements', ''),
                deliverables=milestone_data.get('deliverables', ''),
                # Add all missing fields from migrations with proper defaults
                actual_hours=None,  # Will be set when work is completed
                client_approved_hours=False,  # Default to False, will be set when client approves
                escrow_amount=escrow_amount,
                client_approval_required=project.require_milestone_approval if project.pricing_strategy == 'hourly' else False,
                hours_submitted_at=None,  # Will be set when hours are submitted
                overage_amount=0  # Will be calculated if hours exceed max_hours
            )
            
            print(f"Created milestone: {milestone.title} with escrow: {escrow_amount}")

            # If this milestone is auto-pay, create a Hold
            if milestone_data.get('is_automated'):
                if escrow_amount > 0:
                    wallet = Wallet.objects.get(user=project.client)
                    Hold.objects.create(
                        wallet=wallet,
                        user=project.client,
                        project=project,
                        milestone=milestone,
                        amount=escrow_amount,
                        hold_type='project_milestone',
                        reason=f"Auto-pay hold for milestone '{milestone.title}' in project '{project.title}'"
                    )

    def handle_skills_and_events(self, project, client):
        """Handle project skills and create events"""
        # Handle project skills
        if skills_data := self.request.data.get('skills_required'):
            # Ensure we have a list of skill IDs
            skill_ids = [skill['value'] if isinstance(skill, dict) else skill 
                        for skill in skills_data]
            project.skills_required.set(Skill.objects.filter(id__in=skill_ids))

        # Create project deadline event
        Event.objects.create(
            user=client,
            title=f"{project.title} - Deadline",
            type='Deadline',
            start=project.deadline
            )
            
            # Activity logging
        Activity.objects.create(
                user=client,
            activity_type='project_created',
            description=f'Created Project: {project.title}',
            related_model='project',
            related_object_id=project.id
            )



class CategoryListView(APIView):
    permission_classes = [IsAuthenticated]  # Ensure the user is authenticated

    def get(self, request):
        """
        Returns a list of all categories (domains).
        """
        categories = Category.objects.all()
        serializer = CategorySerializer(categories, many=True)
        return Response(serializer.data)


class SkillsByCategoryView(APIView):
    permission_classes = [IsAuthenticated]  # Ensure the user is authenticated

    def get(self, request, category_id):
        """
        Returns a list of skills that belong to the selected category (domain).
        """
        skills = Skill.objects.filter(category_id=category_id)
        serializer = SkillSerializer(skills, many=True)
        return Response(serializer.data)



# Custom pagination class
from .models import User
class CustomPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100

@api_view(['GET'])
@permission_classes([])  # Open API, modify as needed
def search_partial(request):
    query = request.GET.get('query', '').strip()
    if not query:
        return Response({"error": "Search query is required"}, status=status.HTTP_400_BAD_REQUEST)

    # Check cache first
    cached_results = cache.get(query)
    if cached_results:
        return Response(cached_results)

    paginator = CustomPagination()
    # Search Users (by username & role)
    users = User.objects.filter(
        Q(username__icontains=query) | Q(role__icontains=query)
    ).order_by('id')

    # Paginate Users
    paginated_users = paginator.paginate_queryset(users, request)

    # Manually serialize the users with a Python dict
    serialized_users = []
    projects = []
    seen_project_ids = set()  # To track unique project IDs

    for user in paginated_users:
        user_data = {
            'id': user.id,
            'username': user.username,
            'role': user.role,
            'profile_picture': None,  # Default value for profile_picture
        }

        # Add the profile_picture based on the role
        if user.role == 'client':
            try:
                client_profile = ClientProfile.objects.get(user=user)
                user_data['profile_picture'] = client_profile.profile_picture.url if client_profile.profile_picture else None
                # Query for projects assigned to this client
                client_projects = Project.objects.filter(
                    Q(client=user) |  # Projects assigned to this client
                    Q(title__icontains=query) | 
                    Q(description__icontains=query) | 
                    Q(domain__name__icontains=query)
                ).distinct().order_by('id')

                # Add only unique projects by ID
                for project in client_projects:
                    if project.id not in seen_project_ids:
                        seen_project_ids.add(project.id)
                        projects.append(project)

            except ClientProfile.DoesNotExist:
                user_data['profile_picture'] = None
        elif user.role == 'freelancer':
            try:
                freelancer_profile = FreelancerProfile.objects.get(user=user)
                # Query for projects assigned to this freelancer
                freelancer_projects = Project.objects.filter(
                    Q(assigned_to=user) |  # Correct for ManyToManyField lookup
                    Q(title__icontains=query) | 
                    Q(description__icontains=query) | 
                    Q(domain__name__icontains=query)
                ).distinct().order_by('id')

                # Add only unique projects by ID
                for project in freelancer_projects:
                    if project.id not in seen_project_ids:
                        seen_project_ids.add(project.id)
                        projects.append(project)

                user_data['profile_picture'] = freelancer_profile.profile_picture.url if freelancer_profile.profile_picture else None
            except FreelancerProfile.DoesNotExist:
                user_data['profile_picture'] = None

        serialized_users.append(user_data)

    # Paginate Projects
    if projects:
        paginated_projects = paginator.paginate_queryset(projects, request)
        serialized_projects = ProjectSerializer(paginated_projects, many=True)
        project_count = len(projects)  # Count the total number of projects
    else:
        project_count = 0

    # Search Categories (by name)
    categories = Category.objects.filter(
        Q(name__icontains=query)
    ).order_by('id')

    # Paginate Categories
    paginated_categories = paginator.paginate_queryset(categories, request)
    serialized_categories = CategorySerializer(paginated_categories, many=True)

    # Prepare the final response data, including pagination info
    response_data = {
        "users": {
            "count": users.count(),
            "next": paginator.get_next_link(),
            "previous": paginator.get_previous_link(),
            "results": serialized_users
        },
        "projects": {
            "count": project_count,
            "next": paginator.get_next_link(),
            "previous": paginator.get_previous_link(),
            "results": serialized_projects.data if projects else []
        },
        "categories": {
            "count": categories.count(),
            "next": paginator.get_next_link(),
            "previous": paginator.get_previous_link(),
            "results": serialized_categories.data
        }
    }
    print(response_data)

    # Cache the results for 15 minutes
    cache.set(query, response_data, timeout=60*15)

    # Return the paginated response
    return Response(response_data)



class NotificationListView(APIView):
    permission_classes=[IsAuthenticated]
    def get(self, request):
        notifications = Notification.objects.filter(user=request.user).order_by('-created_at')
        serializer = NotificationSerializer(notifications, many=True)
        return Response(serializer.data)


# Mark a specific notification as read
class MarkNotificationAsRead(APIView):
    permission_classes=[IsAuthenticated]

    def patch(self, request, notification_id):
        try:
            notification = Notification.objects.get(id=notification_id, user=request.user)
            notification.is_read = True
            notification.save()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except Notification.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)


# Delete a specific notification
class DeleteNotification(APIView):
    permission_classes=[IsAuthenticated]

    def delete(self, request, notification_id):
        try:
            notification = Notification.objects.get(id=notification_id, user=request.user)
            notification.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except Notification.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)


from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

def send_notification(user, message):
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        f"notifications_{user.id}",
        {
            "type": "send_notification",
            "message": {"message": message}
        }
    )


class UnmarkedNotificationListView(APIView):
    permission_classes=[IsAuthenticated]

    def get(self, request):
        # Filter notifications by the current logged-in user and those that are unread
        notifications = Notification.objects.filter(user=request.user, is_read=False)
        
        # Serialize the notifications
        serializer = NotificationSerializer(notifications, many=True)
        
        # Return the serialized data as the response
        return Response(serializer.data)


from django.core.exceptions import ObjectDoesNotExist

@method_decorator(csrf_exempt, name='dispatch')
class NotifyFreelancerView(View):
    permission_classes = [IsAuthenticated]

    def post(self, request, object_id, type):
        try:
            task = None
            project = None
            notification_text = ''
            users_to_notify = []

            try:
                # Try to fetch task
                print(type)
                if type == 'task':
                    task = Task.objects.get(id=object_id)
                    project = task.project  # If task found, get associated project
                    notification_text = _(
                        f"{task.title} - The task you have been assigned by {project.client.username} is pending. "
                        f"Deadline: {task.deadline}. Project: {project.title}."
                    )
                    users_to_notify = task.assigned_to.all()

                elif type == 'project':
                    project = Project.objects.get(id=object_id)
                    notification_text = _(
                        f"{project.title} - The project you have been assigned by {project.client.username} is pending. "
                        f"Deadline: {project.deadline}."
                    )
                    users_to_notify = project.assigned_to.all()
                    print(users_to_notify)

                # Include the client in the notification list
                

            except ObjectDoesNotExist:
                return JsonResponse({
                    "status": "error",
                    "message": "Invalid task or project ID."
                }, status=400)

            # Check if user has already been notified within the last 24 hours
            
            for user in users_to_notify:
                recent_notification = Notification.objects.filter(
                    user=user,
                    related_model_id=task.id if task else project.id,
                    created_at__gte=timezone.now() - timezone.timedelta(hours=24)
                ).first()

                print("recent_notification",recent_notification)

                if recent_notification:
                    return JsonResponse({
                        "status": "error",
                        "message": "User already notified. Please try again in 24 hours."
                    }, status=400)

                # Send new notification
                Notification.objects.create(
                    user=user,
                    type='Projects & Tasks' if task else 'Projects',
                    related_model_id=task.id if task else project.id,
                    notification_text=notification_text
                )

            return JsonResponse({"status": "success", "message": "Notifications sent successfully."})

        except Exception as e:
            # Log exception here
            return JsonResponse({"status": "error", "message": str(e)}, status=500)


def get_upcoming_notifications(request):
    if request.method == 'GET':
        # Get notifications due within the next week
        upcoming_notifications = Notification.objects.filter(
            created_at__gte=timezone.now(),
            created_at__lt=timezone.now() + timezone.timedelta(weeks=1)
        ).values('id', 'notification_text', 'created_at')

        return JsonResponse(list(upcoming_notifications), safe=False)
