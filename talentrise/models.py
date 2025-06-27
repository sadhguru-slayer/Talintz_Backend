from django.db import models
from django.conf import settings
from core.models import Skill, User

class Institution(models.Model):
    """Educational institutions like universities and colleges"""
    name = models.CharField(max_length=255, unique=True)
    short_name = models.CharField(max_length=50, blank=True)
    location = models.CharField(max_length=255)
    country = models.CharField(max_length=100)
    website = models.URLField(blank=True, null=True)
    
    # Accreditation and ranking information
    accreditation = models.CharField(max_length=255, blank=True)
    ranking = models.PositiveIntegerField(null=True, blank=True, 
                                          help_text="National ranking if available")
    
    # Additional metadata
    established_year = models.PositiveIntegerField(null=True, blank=True)
    is_verified = models.BooleanField(default=False, 
                                     help_text="Whether this institution has been verified by our team")
    
    class Meta:
        ordering = ['name']
        
    def __str__(self):
        return self.name

class AcademicDiscipline(models.Model):
    """Broad academic disciplines (like Engineering, Arts, Science, etc.)"""
    name = models.CharField(max_length=100, unique=True)
    
    def __str__(self):
        return self.name

class FieldOfStudy(models.Model):
    """Specific fields of study (like Computer Science, Mechanical Engineering, etc.)"""
    name = models.CharField(max_length=255)
    discipline = models.ForeignKey(AcademicDiscipline, on_delete=models.CASCADE, 
                                   related_name='fields_of_study')
    description = models.TextField(blank=True)
    
    class Meta:
        unique_together = ['name', 'discipline']
        verbose_name_plural = "Fields of Study"
        
    def __str__(self):
        return f"{self.name} ({self.discipline})"

class Course(models.Model):
    """Degree programs and courses (like B.Tech, M.Sc, etc.)"""
    DEGREE_LEVELS = [
        ('diploma', 'Diploma'),
        ('associate', 'Associate Degree'),
        ('bachelor', 'Bachelor\'s Degree'),
        ('master', 'Master\'s Degree'),
        ('doctoral', 'Doctoral Degree'),
        ('certificate', 'Certificate Program'),
    ]
    
    name = models.CharField(max_length=255)
    abbreviation = models.CharField(max_length=20, blank=True)
    level = models.CharField(max_length=20, choices=DEGREE_LEVELS)
    duration_years = models.DecimalField(max_digits=3, decimal_places=1, 
                                        help_text="Duration in years")
    description = models.TextField(blank=True)
    fields_of_study = models.ManyToManyField(FieldOfStudy, related_name='courses')
    
    class Meta:
        unique_together = ['name', 'level']
        
    def __str__(self):
        return f"{self.abbreviation or self.name} ({self.get_level_display()})"

class AcademicYear(models.Model):
    """Academic years with standardized naming and tracking"""
    YEAR_CHOICES = [
        (1, '1st Year'),
        (2, '2nd Year'),
        (3, '3rd Year'),
        (4, '4th Year'),
        (5, '5th Year'),
        (6, '6th Year'),
    ]
    
    year_number = models.PositiveSmallIntegerField(choices=YEAR_CHOICES)
    description = models.CharField(max_length=100, blank=True)
    
    def __str__(self):
        return self.get_year_number_display()

class TalentRiseProfile(models.Model):
    """Enhanced student profile with structured academic information"""
    AVAILABILITY_CHOICES = [
        ('5-10', '5-10 hours/week'),
        ('10-15', '10-15 hours/week'),
        ('15-20', '15-20 hours/week'),
        ('20+', 'More than 20 hours/week'),
    ]
    
    ACADEMIC_STATUS_CHOICES = [
        ('active', 'Active'),
        ('graduated', 'Graduated'),
        ('on_break', 'On Break'),
        ('dropped', 'Dropped')
    ]
    
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, 
                              related_name='talentrise_profile')
    
    # Academic Details (now using foreign keys)
    institution = models.ForeignKey(Institution, on_delete=models.PROTECT, 
                                   related_name='students')
    course = models.ForeignKey(Course, on_delete=models.PROTECT,
                             related_name='students')
    field_of_study = models.ForeignKey(FieldOfStudy, on_delete=models.PROTECT,
                                     related_name='students')
    year_of_study = models.ForeignKey(AcademicYear, on_delete=models.PROTECT,
                                    related_name='students')
    graduation_year = models.PositiveIntegerField(help_text="Expected graduation year")
    
    # Student ID and enrollment information
    student_id = models.CharField(max_length=50, blank=True,
                                help_text="Official student ID at the institution")
    enrollment_date = models.DateField(null=True, blank=True,
                                     help_text="When the student enrolled in their program")
    
    # TalentRise specific details
    skills = models.ManyToManyField(Skill, related_name="talentrise_students")
    weekly_availability = models.CharField(max_length=10, choices=AVAILABILITY_CHOICES, default='10-15')
    preferred_work_categories = models.TextField(blank=True, 
                                              help_text="Areas of work the student is interested in")
    
    # Academic performance
    gpa = models.DecimalField(max_digits=3, decimal_places=2, null=True, blank=True,
                           help_text="Current GPA on a 4.0 scale")
    academic_achievements = models.TextField(blank=True,
                                          help_text="Honors, awards, scholarships, etc.")
    
    # Academic projects and achievements
    academic_projects = models.JSONField(default=list, blank=True, 
                                      help_text="List of academic projects completed or in progress")
    certifications = models.JSONField(default=list, blank=True, 
                                   help_text="List of relevant certifications")
    
    # Profile verification
    is_verified = models.BooleanField(default=False, 
                                   help_text="Indicates if academic credentials have been verified")
    verification_document = models.FileField(upload_to='talentrise_verification/', null=True, blank=True,
                                          help_text="Student ID or enrollment verification document")
    verification_date = models.DateField(null=True, blank=True,
                                      help_text="When the profile was verified")
    
    # Program activity
    date_joined = models.DateTimeField(auto_now_add=True)
    completed_gigs = models.PositiveIntegerField(default=0)
    ongoing_gigs = models.PositiveIntegerField(default=0)
    
    # Profile completion and status
    profile_completion = models.PositiveSmallIntegerField(default=0,
                                                      help_text="Profile completion percentage")
    is_active = models.BooleanField(default=True,
                                 help_text="Whether the student is currently active in the program")
    
    # Additional fields
    current_semester = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        help_text="Current semester of study"
    )
    
    academic_status = models.CharField(
        max_length=20,
        choices=ACADEMIC_STATUS_CHOICES,
        default='active',
        help_text="Current academic status of the student"
    )
    
    class Meta:
        ordering = ['-date_joined']
    
    def __str__(self):
        return f"{self.user.username} - TalentRise Student at {self.institution}"
    
    def save(self, *args, **kwargs):
        # When saving a TalentRise profile, ensure the user is marked as talentrise
        if not self.user.is_talentrise:
            self.user.is_talentrise = True
            self.user.save()
        super().save(*args, **kwargs)
    
    def calculate_profile_completion(self):
        """Calculate and update the profile completion percentage"""
        # Implementation depends on which fields are considered essential
        # This is a placeholder for the actual implementation
        completed_fields = 0
        total_fields = 10  # Number of essential fields
        
        # Count completed fields
        if self.institution_id:
            completed_fields += 1
        if self.course_id:
            completed_fields += 1
        if self.field_of_study_id:
            completed_fields += 1
        if self.year_of_study_id:
            completed_fields += 1
        if self.graduation_year:
            completed_fields += 1
        if self.skills.exists():
            completed_fields += 1
        if self.weekly_availability:
            completed_fields += 1
        if self.preferred_work_categories:
            completed_fields += 1
        if self.academic_projects:
            completed_fields += 1
        if self.verification_document:
            completed_fields += 1
            
        self.profile_completion = (completed_fields / total_fields) * 100
        return self.profile_completion

class TalentRisePortfolio(models.Model):
    """Portfolio items showcasing student work"""
    portfolio_categories = [
        ('academic', 'Academic Project'),
        ('personal', 'Personal Project'),
        ('freelance', 'Freelance Work'),
        ('internship', 'Internship Project'),
        ('competition', 'Competition Entry'),
    ]
    
    profile = models.ForeignKey(TalentRiseProfile, on_delete=models.CASCADE, 
                               related_name='portfolio_items')
    title = models.CharField(max_length=255)
    description = models.TextField()
    category = models.CharField(max_length=20, choices=portfolio_categories, default='academic')
    image = models.ImageField(upload_to='talentrise_portfolio/', blank=True, null=True)
    project_url = models.URLField(blank=True, null=True)
    repository_url = models.URLField(blank=True, null=True, 
                                   help_text="GitHub or other repository link")
    skills_used = models.ManyToManyField(Skill, related_name='portfolio_uses')
    date_created = models.DateField()
    date_completed = models.DateField(null=True, blank=True)
    
    # For academic projects
    is_academic = models.BooleanField(default=True, 
                                    help_text="Indicates if this is an academic project")
    course_related = models.CharField(max_length=255, blank=True,
                                    help_text="Course or subject this project was part of")
    
    # For recognition and grades
    grade_received = models.CharField(max_length=10, blank=True,
                                   help_text="Grade received for this project if applicable")
    recognition = models.TextField(blank=True,
                                help_text="Any awards or recognition received")
    
    featured = models.BooleanField(default=False,
                               help_text="Featured projects appear prominently on the profile")
    
    class Meta:
        ordering = ['-date_created']
    
    def __str__(self):
        return f"{self.profile.user.username} - {self.title}"
