from django.contrib import admin
from .models import *
from django_celery_beat.models import PeriodicTask, IntervalSchedule
from django.contrib.auth.hashers import make_password

class UserAdmin(admin.ModelAdmin):
    list_display = ('username', 'email', 'role', 'is_email_verified', 'is_active')
    list_filter = ('role', 'is_active', 'is_email_verified')
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Personal info', {'fields': ('first_name', 'last_name', 'email', 'phone_number', 'nickname')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
        ('Custom fields', {'fields': ('role', 'membership', 'is_profiled', 'is_talentrise', 'is_email_verified', 'is_phone_verified', 'referral_code')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'email', 'password1', 'password2', 'role', 'membership'),
        }),
    )
    search_fields = ('username', 'email', 'first_name', 'last_name')
    ordering = ('username',)

    def save_model(self, request, obj, form, change):
        # Hash the password if it's being set or changed
        if 'password' in form.changed_data:
            obj.password = make_password(obj.password)
        super().save_model(request, obj, form, change)

admin.site.register(User, UserAdmin)
admin.site.register(Connection)
admin.site.register(Category)
admin.site.register(Skill)

class ProjectAdmin(admin.ModelAdmin):
    list_display = ['title', 'id', 'client', 'domain', 'status']
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