from celery import shared_task
from django.utils.timezone import now
from datetime import timedelta,datetime
from .models import Event
from core.models import Project,Notification,Task
from django.utils import timezone


@shared_task
def check_deadlines():
    """
    Celery task to check for approaching deadlines (within 2 days) for projects and tasks
    and send notifications to clients and assigned users.
    """
    today = now().date()

    # Get projects with deadlines within the next 2 days
    projects = Project.objects.filter(
        deadline__gte=today,  # Deadline is today or in the future
        deadline__lte=today + timedelta(days=2),  # Deadline within 2 days
        status="pending"
    )

    # Notify project clients about the upcoming project deadlines
    for project in projects:
        days_left = (project.deadline - today).days
        notification_text = f"Your project '{project.title}' deadline is near! Due in {days_left} day(s)."
        
        # Avoid duplicate notifications for the same project client
        if not Notification.objects.filter(
            user=project.client,
            type="Projects",
            related_model_id=project.id
        ).exists():
            Notification.objects.create(
                user=project.client,
                type="Projects",
                related_model_id=project.id,
                notification_text=notification_text
            )

    # Get tasks with deadlines within the next 2 days
    tasks = Task.objects.filter(
        deadline__gte=today,  # Task deadline is today or in the future
        deadline__lte=today + timedelta(days=2),  # Deadline within 2 days
        status="pending"
    )

    # Notify assigned users about the upcoming task deadlines
    for task in tasks:
        days_left = (task.deadline - today).days
        notification_text = f"Your task '{task.title}' deadline is near! Due in {days_left} day(s)."
        
        # Create notifications for each assigned user (avoid duplicates)
        for user in task.assigned_to.all():
            if not Notification.objects.filter(
                user=user,
                type="Projects & Tasks",
                related_model_id=task.id
            ).exists():
                Notification.objects.create(
                    user=user,
                    type="Projects & Tasks",
                    related_model_id=task.id,
                    notification_text=notification_text
                )

        # Also notify the project client about the task deadline
        if not Notification.objects.filter(
            user=task.project.client,
            type="Projects & Tasks",
            related_model_id=task.id
        ).exists():
            Notification.objects.create(
                user=task.project.client,
                type="Projects & Tasks",
                related_model_id=task.id,
                notification_text=notification_text
            )

    # Return a log of how many projects and tasks were processed
    return f"Checked deadlines for {projects.count()} projects and {tasks.count()} tasks."

import logging
logger = logging.getLogger(__name__)

import datetime

from datetime import timedelta

def format_notification_time(notification_time):
    if notification_time == 60:
        return "1 hour"
    elif notification_time == 180:
        return "3 hours"
    elif notification_time == 360:
        return "6 hours"
    elif notification_time == 1440:
        return "1 day"
    elif notification_time == 4320:
        return "3 days"
    elif notification_time == 86400:
        return "6 days"
    else:
        return f"{notification_time} minutes"

@shared_task
def send_event_approaching_notification():
    try:
        events = Event.objects.filter(notification_sent=False)
        logger.info(f"Found {events.count()} events to check.")
        for event in events:
            logger.info(f"Processing event {event.id}...")

            # Handle DateField and convert to timezone-aware datetime if needed
            if isinstance(event.start, datetime.date) and not isinstance(event.start, datetime.datetime):
                # Combine the date with a default time (e.g., midnight) and make it timezone-aware
                event.start = timezone.make_aware(datetime.datetime.combine(event.start, datetime.time.min))

            notification_time = event.notification_time
            event_time = event.start
            notification_time_delta = timedelta(minutes=notification_time)

            notification_send_time = event_time - notification_time_delta

            logger.info(f"Notification should be sent at: {notification_send_time}")
            logger.info(f"Current time is: {timezone.now()}")
            
            if timezone.now() >= notification_send_time and not event.notification_sent:
                # Format the notification time
                formatted_notification_time = format_notification_time(notification_time)

                # Format the event start date as yyyy-mm-dd
                formatted_event_start = event.start.strftime('%Y-%m-%d')

                # Create notification with HTML and CSS
                notification_text = f"""
                <span class="event-title" style="font-weight: bold; text-decoration: none;" onmouseover="this.style.textDecoration='underline'" onmouseout="this.style.textDecoration='none'">
                    {event.title}
                </span> is scheduled for <span>{formatted_event_start}</span>. This is a reminder {formatted_notification_time} before the event.
                """

                Notification.objects.create(
                    user=event.user,  # Use the correct user field if necessary
                    type="Events",
                    related_model_id=event.id,
                    notification_text=notification_text
                )

                event.notification_sent = True
                event.save()

                logger.info(f"Notification sent for event {event.id}.")
            else:
                logger.info(f"Event {event.id} notification is not ready yet.")
        return 'Checked and scheduled notifications for future events.'
    except Exception as e:
        logger.error(f"Error occurred: {e}")
        raise e
