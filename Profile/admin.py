from django.contrib import admin
from .models import (
    FreelancerProfile, ClientProfile, PaymentHistory, Feedback, FreelancerReview,
    Address, BankDetails, VerificationDocument, CompanyDetails,
    Institution, Department, Course, Education,
    Certification, PortfolioItem  # Now these are top-level classes
)
from django.contrib.admin import ModelAdmin

class FreelancerProfileAdmin(ModelAdmin):
    fieldsets = (
        ('Basic Information', {
            'fields': ('user', 'profile_picture', 'cover_photo', 'bio', 'description', 
                      'dob', 'gender')
        }),
        ('Professional Information', {
            'fields': ('title', 'skills', 'experience_years', 'education', 
                      'certifications', 'portfolio_items')
        }),
        ('Availability & Preferences', {
            'fields': ('availability_status', 'hourly_rate', 'preferred_project_duration',
                      'preferred_project_type', 'work_hours_per_week')
        }),
        ('Relationships', {
            'fields': ('addresses', 'bank_details', 'verification_documents', 'company')
        }),
        ('Security & Verification', {
            'fields': ('email_verified', 'phone_verified', 'identity_verified',
                      'skills_verified', 'two_factor_enabled')
        }),
        ('Statistics & Metrics', {
            'fields': ('total_projects_completed', 'current_active_projects',
                      'total_earnings', 'average_rating', 'success_rate',
                      'on_time_completion_rate', 'response_time_avg')
        }),
        ('TalentRise Specific', {
            'fields': ('is_talentrise', 'student_id', 'institution', 'course_details',
                      'graduation_year', 'current_semester', 'enrollment_year',
                      'academic_status', 'cgpa', 'academic_achievements',
                      'research_publications', 'specialization')
        }),
        ('Profile Levels', {
            'fields': ('points',
'current_level',
'current_sub_level')
        }),
        ('Profile Status', {
            'fields': ('profile_status', 'profile_completion_percentage',
                      'account_tier', 'created_at', 'last_active')
        })
    )
    list_display = ('user', 'title', 'is_talentrise', 'profile_status')
    search_fields = ('user__username', 'user__email', 'title')
    filter_horizontal = ('skills', 'education', 'certifications', 'portfolio_items')

class ClientProfileAdmin(ModelAdmin):
    fieldsets = (
        ('Basic Information', {
            'fields': ('user', 'profile_picture', 'cover_photo', 'bio', 'description',
                      'dob', 'gender')
        }),
        ('Contact Information', {
            'fields': ('primary_email', 'secondary_email', 'phone_number',
                      'alternate_phone')
        }),
        ('Relationships', {
            'fields': ('addresses', 'bank_details', 'verification_documents', 'company')
        }),
        ('Business Preferences', {
            'fields': ('preferred_payment_method', 'project_preferences', 'budget_range')
        }),
        ('Security & Verification', {
            'fields': ('email_verified', 'phone_verified', 'identity_verified',
                      'two_factor_enabled', 'last_verification_date')
        }),
        ('Legal & Compliance', {
            'fields': ('terms_accepted', 'privacy_policy_accepted',
                      'terms_acceptance_date', 'legal_agreements')
        }),
        ('Statistics & Metrics', {
            'fields': ('total_projects_posted', 'successful_projects', 'total_spent',
                      'average_rating', 'response_rate', 'payment_reliability_score')
        }),
        ('Profile Status', {
            'fields': ('profile_status', 'profile_completion_percentage',
                      'account_tier', 'created_at', 'last_active')
        })
    )
    list_display = ('user', 'company', 'profile_status')
    search_fields = ('user__username', 'user__email', 'company__name')
    readonly_fields = ('created_at', 'last_active')

class PaymentHistoryAdmin(ModelAdmin):
    list_display = ('user', 'transaction_id', 'amount', 'status', 'payment_date')
    list_filter = ('status', 'payment_date')
    search_fields = ('user__username', 'transaction_id')
    date_hierarchy = 'payment_date'
    ordering = ('-payment_date',)

class FeedbackAdmin(ModelAdmin):
    list_display = ('from_user', 'to_user', 'project', 'rating', 'created_at')
    search_fields = ('from_user__username', 'to_user__username', 'project__title')
    date_hierarchy = 'created_at'

class FreelancerReviewAdmin(ModelAdmin):
    list_display = ('from_client', 'to_freelancer', 'project', 'rating', 'created_at')
    search_fields = ('from_client__username', 'to_freelancer__username', 'project__title')
    date_hierarchy = 'created_at'

class AddressAdmin(ModelAdmin):
    list_display = ('street_address', 'city', 'state', 'country', 'is_primary')
    search_fields = ('street_address', 'city', 'state', 'country')

class BankDetailsAdmin(ModelAdmin):
    list_display = ('bank_name', 'account_holder_name', 'verified', 'primary')
    search_fields = ('bank_name', 'account_holder_name')

class VerificationDocumentAdmin(ModelAdmin):
    list_display = ('document_type', 'document_number', 'verified', 'expiry_date')
    search_fields = ('document_type', 'document_number')

class CompanyDetailsAdmin(ModelAdmin):
    list_display = ('name', 'registration_number', 'company_type', 'verified')
    search_fields = ('name', 'registration_number')

class InstitutionAdmin(ModelAdmin):
    list_display = ('name', 'type', 'country', 'verified')
    search_fields = ('name', 'type', 'country')

class DepartmentAdmin(ModelAdmin):
    list_display = ('name', 'code', 'institution')
    search_fields = ('name', 'code')

class CourseAdmin(ModelAdmin):
    list_display = ('name', 'code', 'department', 'degree_level')
    search_fields = ('name', 'code')

class EducationAdmin(ModelAdmin):
    list_display = ('institution', 'department', 'course', 'start_date', 'end_date')
    search_fields = ('institution__name', 'department__name', 'course__name')

class CertificationAdmin(ModelAdmin):
    list_display = ('name', 'issuing_organization', 'issue_date', 'verified')
    search_fields = ('name', 'issuing_organization')

class PortfolioItemAdmin(ModelAdmin):
    list_display = ('title', 'start_date', 'end_date', 'verified')
    search_fields = ('title',)

# Register all models
admin.site.register(FreelancerProfile, FreelancerProfileAdmin)
admin.site.register(ClientProfile, ClientProfileAdmin)
admin.site.register(PaymentHistory, PaymentHistoryAdmin)
admin.site.register(Feedback, FeedbackAdmin)
admin.site.register(FreelancerReview, FreelancerReviewAdmin)
admin.site.register(Address, AddressAdmin)
admin.site.register(BankDetails, BankDetailsAdmin)
admin.site.register(VerificationDocument, VerificationDocumentAdmin)
admin.site.register(CompanyDetails, CompanyDetailsAdmin)
admin.site.register(Institution, InstitutionAdmin)
admin.site.register(Department, DepartmentAdmin)
admin.site.register(Course, CourseAdmin)
admin.site.register(Education, EducationAdmin)
admin.site.register(Certification, CertificationAdmin)
admin.site.register(PortfolioItem, PortfolioItemAdmin)