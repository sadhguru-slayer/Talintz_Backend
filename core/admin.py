from django.contrib import admin
from .models import *
from django_celery_beat.models import PeriodicTask, IntervalSchedule

admin.site.register(User)
admin.site.register(Connection)
admin.site.register(Category)
admin.site.register(Skill)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ['title','id', 'client', 'domain', 'status']
    filter_horizontal = ('skills_required',)

admin.site.register(Project, ProjectAdmin)

admin.site.register(Task)
admin.site.register(Payment)
admin.site.register(UserFeedback)
admin.site.register(Notification)


class BidAdmin(admin.ModelAdmin):
    list_display = ['id', 'freelancer', 'project', 'bid_type', 'state', 'total_value', 'created_at']
    list_filter = ['state', 'bid_type']
    search_fields = ['freelancer__username', 'project__title']

admin.site.register(Bid, BidAdmin)

admin.site.register(BidItem)
admin.site.register(BidNegotiationLog)
admin.site.register(BidAttachment)
admin.site.register(Milestone)
admin.site.register(Invitation)
admin.site.register(Referral)