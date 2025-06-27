# Recommmend projects  viewset

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from core.models import Project, Invitation, Milestone
from Profile.models import FreelancerProfile
from rest_framework import status

class ProjectRecommendationView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        try:
            profile = user.freelancer_profile
        except FreelancerProfile.DoesNotExist:
            return Response({"detail": "Freelancer profile not found."}, status=status.HTTP_404_NOT_FOUND)

        # Get freelancer's skills as a set of skill IDs
        freelancer_skills = set(profile.skills.values_list('id', flat=True))
        current_level = profile.current_level
        current_sub_level = profile.current_sub_level

        # Get projects the user has already bid on
        already_bid_project_ids = set(user.submitted_bids.values_list('project_id', flat=True))

        # Filter projects
        projects = Project.objects.filter(
            status__in=['pending', 'ongoing']
        ).exclude(
            id__in=already_bid_project_ids
        )

        # Level threshold: Only recommend projects for which the freelancer is eligible
        def is_eligible(project):
            # You can add more sophisticated logic here if you have level/sub-level requirements on projects
            # For now, let's assume all projects are eligible for all levels, or you can add a field to Project for min_level/min_sub_level
            return True  # Or implement your logic

        # Score projects by skill overlap
        recommendations = []
        for project in projects:
            project_skills = set(project.skills_required.values_list('id', flat=True))
            skill_overlap = len(freelancer_skills & project_skills)
            if skill_overlap == 0:
                continue  # Only recommend if at least one skill matches
            if not is_eligible(project):
                continue
            # Get all required skill names
            all_skill_names = list(project.skills_required.values_list('name', flat=True))
            # Get matched and unmatched skill names
            matched_skill_names = [name for name in all_skill_names if name in profile.skills.values_list('name', flat=True)]
            unmatched_skill_names = [name for name in all_skill_names if name not in matched_skill_names]
            # Concatenate: matched first, then unmatched
            ordered_skills = matched_skill_names + unmatched_skill_names
            recommendations.append({
                "id": project.id,
                "title": project.title,
                "description": project.description,
                "budget": project.budget,
                "deadline": project.deadline,
                "domain": project.domain.name,
                "client": project.client.username,
                "status": project.status,
                "skills_required": ordered_skills,
                "skill_match_count": len(matched_skill_names),
                "total_skills_required": project_skills.__len__(),
                "created_at": project.created_at.isoformat() if project.created_at else None,
                "hourly_rate": float(project.hourly_rate) if project.hourly_rate else None,
                "max_hours": project.max_hours,
            })

        # Sort by skill match (descending)
        recommendations.sort(key=lambda x: x['skill_match_count'], reverse=True)

        # Limit to top 10
        recommendations = recommendations[:10]

        return Response({"recommendations": recommendations})

class BrowseProjectsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        try:
            profile = user.freelancer_profile
        except FreelancerProfile.DoesNotExist:
            return Response({"detail": "Freelancer profile not found."}, status=status.HTTP_404_NOT_FOUND)

        freelancer_skills = set(profile.skills.values_list('id', flat=True))
        already_bid_project_ids = set(user.submitted_bids.values_list('project_id', flat=True))

        # Get all pending project assignment invitations for this user
        pending_invitations = Invitation.objects.filter(
            to_user=user,
            invitation_type='project_assignment',
            status='pending'
        )

        # Build a set of project_ids from the terms field
        invited_project_ids = set()
        for inv in pending_invitations:
            try:
                project_id = inv.terms.get('project_id')
                if project_id:
                    invited_project_ids.add(project_id)
            except Exception:
                continue

        # Only pending projects
        projects = Project.objects.filter(status='pending')

        browse_projects = []
        user_level = profile.current_level  # 'Bronze', 'Silver', 'Gold'
        # Budget thresholds (example, adjust as needed)
        medium_budget_limit = 15000
        advanced_budget_limit = 30000

        for project in projects:
            project_skills = set(project.skills_required.values_list('id', flat=True))
            if not project_skills:
                continue
            skill_overlap = len(freelancer_skills & project_skills)
            match_percent = (skill_overlap / len(project_skills)) * 100 if project_skills else 0
            already_bid = project.id in already_bid_project_ids

            # Get project complexity and budget
            complexity = getattr(project, 'complexity_level', 'entry')
            budget = float(getattr(project, 'budget', 0))

            # Filtering logic
            show_project = False
            priority = 0

            if user_level == 'Bronze':
                if complexity == 'entry':
                    show_project = match_percent >= 20
                    priority = 1
                elif complexity == 'intermediate' and match_percent >= 40 and budget <= medium_budget_limit:
                    show_project = True
                    priority = 2
            elif user_level == 'Silver':
                if complexity in ['entry', 'intermediate']:
                    show_project = match_percent >= 20
                    priority = 1 if complexity == 'entry' else 2
                elif complexity == 'advanced' and match_percent >= 40 and budget <= advanced_budget_limit:
                    show_project = True
                    priority = 3
            elif user_level == 'Gold':
                show_project = match_percent >= 20
                priority = {'entry': 1, 'intermediate': 2, 'advanced': 3}.get(complexity, 4)

            if show_project:
                # Get all required skill names
                all_skill_names = list(project.skills_required.values_list('name', flat=True))
                matched_skill_names = [name for name in all_skill_names if name in profile.skills.values_list('name', flat=True)]
                unmatched_skill_names = [name for name in all_skill_names if name not in matched_skill_names]
                ordered_skills = matched_skill_names + unmatched_skill_names

                # Get milestones (if any)
                milestones_qs = project.milestones.all()
                milestones = [
                    {
                        "id": m.id,
                        "title": m.title,
                        "amount": float(m.amount),
                        "due_date": m.due_date,
                        "status": m.status,
                        "milestone_type": m.milestone_type,
                    }
                    for m in milestones_qs
                ] if milestones_qs.exists() else []

                # Check for pending invitation for this user and project
                is_invitation_pending = project.id in invited_project_ids

                browse_projects.append({
                    "id": project.id,
                    "title": project.title,
                    "description": project.description,
                    "budget": project.budget,
                    "deadline": project.deadline,
                    "domain": project.domain.name,
                    "client": project.client.username,
                    "status": project.status,
                    "skills_required": ordered_skills,
                    "skill_match_count": len(matched_skill_names),
                    "match_percent": match_percent,
                    "complexity_level": complexity,
                    "already_bid": already_bid,
                    "priority": priority,
                    "payment_strategy": project.pricing_strategy,
                    "milestones": milestones,
                    "is_invitation_pending": is_invitation_pending,
                    "created_at": project.created_at.isoformat() if project.created_at else None,
                    "hourly_rate": float(project.hourly_rate) if project.hourly_rate else None,
                    "max_hours": project.max_hours,
                })

        # Sort: priority (asc), match_percent (desc), budget (desc)
        browse_projects.sort(key=lambda x: (x['priority'], -x['match_percent'], -float(x['budget'])))

        # Limit to top 20
        browse_projects = browse_projects[:20]

        return Response({"browse_projects": browse_projects})
    
    