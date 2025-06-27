from django.contrib import admin
from .models import (
    Event, 
    FreelancerActivity, 
    FreelancerOBSPEligibility, 
    FreelancerEligibilityCache
)

# Register your models here.
admin.site.register(Event)
admin.site.register(FreelancerActivity)

@admin.register(FreelancerOBSPEligibility)
class FreelancerOBSPEligibilityAdmin(admin.ModelAdmin):
    list_display = ['freelancer', 'obsp_template', 'last_updated', 'get_eligible_levels']
    list_filter = ['last_updated', 'obsp_template__category']
    search_fields = ['freelancer__username', 'obsp_template__title']
    readonly_fields = ['last_updated', 'calculation_version', 'eligibility_data']
    
    def get_eligible_levels(self, obj):
        eligible = obj.get_all_eligible_levels()
        return ', '.join(eligible) if eligible else 'None'
    get_eligible_levels.short_description = 'Eligible Levels'
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('freelancer', 'obsp_template', 'last_updated', 'calculation_version')
        }),
        ('Eligibility Data', {
            'fields': ('eligibility_data',),
            'classes': ('collapse',),
            'description': 'Detailed eligibility analysis for all levels'
        }),
    )

@admin.register(FreelancerEligibilityCache)
class FreelancerEligibilityCacheAdmin(admin.ModelAdmin):
    list_display = ['freelancer', 'total_eligible_obsp', 'total_obsp_checked', 'average_score', 'last_calculated']
    list_filter = ['last_calculated']
    search_fields = ['freelancer__username']
    readonly_fields = ['last_calculated', 'cache_version']
