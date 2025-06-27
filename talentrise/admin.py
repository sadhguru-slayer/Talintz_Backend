from django.contrib import admin
from .models import TalentRiseProfile, TalentRisePortfolio, Institution, AcademicDiscipline, FieldOfStudy, Course, AcademicYear
@admin.register(TalentRiseProfile)
class TalentRiseProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'institution', 'course', 'year_of_study', 'graduation_year', 'is_verified')
    list_filter = ('is_verified', 'year_of_study', 'graduation_year')
    search_fields = ('user__username', 'institution', 'course')
    fieldsets = (
        ('User Information', {
            'fields': ('user', 'is_verified')
        }),
        ('Academic Details', {
            'fields': ('institution', 'course', 'field_of_study', 'year_of_study', 'graduation_year')
        }),
        ('TalentRise Program', {
            'fields': ('skills', 'weekly_availability', 'preferred_work_categories')
        }),
        ('Projects & Certifications', {
            'fields': ('academic_projects', 'certifications')
        }),
        ('Verification', {
            'fields': ('verification_document',)
        }),
        ('Program Stats', {
            'fields': ('completed_gigs',)
        }),
    )

@admin.register(TalentRisePortfolio)
class TalentRisePortfolioAdmin(admin.ModelAdmin):
    list_display = ('profile', 'title', 'date_created', 'is_academic')
    list_filter = ('is_academic', 'date_created')
    search_fields = ('title', 'description', 'profile__user__username')


admin.site.register(Institution)
admin.site.register(AcademicDiscipline)
admin.site.register(FieldOfStudy)
admin.site.register(Course)
admin.site.register(AcademicYear)


