# ProfileScoring and Level validation page

from datetime import timedelta

def score_project_completion(project):
    # Complexity: entry/intermediate/advanced
    complexity_points = {
        'entry': 15,
        'intermediate': 25,
        'advanced': 40,
    }
    return complexity_points.get(project.complexity_level, 15)

def score_obsp_completion(obssp_assignment):
    # Level: easy/medium/hard
    level_points = {
        'easy': 20,
        'medium': 35,
        'hard': 60,
    }
    return level_points.get(obssp_assignment.obsp_response.selected_level, 20)

def score_rating(rating, max_stars=5):
    # 2 points per star, +2 bonus for perfect 5-star
    base = float(rating) * 2
    bonus = 2 if float(rating) == max_stars else 0
    return base + bonus

def score_on_time_delivery(project):
    if project.updated_at and project.deadline:
        if project.updated_at.date() <= project.deadline:
            return 10
    return 0

def score_early_delivery_with_good_rating(project, rating):
    if project.updated_at and project.deadline:
        days_early = (project.deadline - project.updated_at.date()).days
        if days_early >= 5 and rating >= 4.5:
            return 12  # super fast & high quality
        elif days_early >= 2 and rating >= 4:
            return 8
    return 0

def score_bank_details_updated():
    return 5  # one-time

def score_bank_details_verified():
    return 10  # one-time

def score_document_uploaded():
    return 3  # per doc, one-time

def score_document_verified():
    return 7  # per doc, one-time

def score_profile_complete():
    return 20  # one-time

def score_repeat_client(project, user):
    # Only award for first 3 repeat projects per client
    from core.models import Project
    repeat_count = Project.objects.filter(client=project.client, assigned_to=user).count()
    if repeat_count == 2:
        return 10  # first repeat
    elif repeat_count == 3:
        return 5   # second repeat
    elif repeat_count > 3:
        return 0   # no more bonus
    return 0

def score_activity_streak(user):
    # Award 5 points for each week with at least 1 completed project in the last 4 weeks
    from core.models import Project
    from django.utils import timezone
    now = timezone.now().date()
    streak_points = 0
    for week in range(4):
        week_start = now - timedelta(days=7 * (week + 1))
        week_end = now - timedelta(days=7 * week)
        if Project.objects.filter(
            assigned_to=user,
            status='completed',
            updated_at__date__gte=week_start,
            updated_at__date__lt=week_end
        ).exists():
            streak_points += 5
    return streak_points

def score_recent_activity(user):
    # 5 points if user completed any project in last 30 days
    from core.models import Project
    from django.utils import timezone
    now = timezone.now().date()
    if Project.objects.filter(
        assigned_to=user,
        status='completed',
        updated_at__date__gte=now - timedelta(days=30)
    ).exists():
        return 5
    return 0

def score_client_diversity(user):
    # 5 points for every 3 unique clients (up to 15 points)
    from core.models import Project
    unique_clients = Project.objects.filter(
        assigned_to=user,
        status='completed'
    ).values_list('client', flat=True).distinct().count()
    return min((unique_clients // 3) * 5, 15)