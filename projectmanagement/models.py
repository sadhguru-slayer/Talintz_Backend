from django.db import models
from django.core.validators import MinValueValidator
from core.models import Project, Task, User, Skill, Milestone
from django.utils import timezone

class Sprint(models.Model):
    """Agile sprint model for iterative project management"""
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='sprints')
    name = models.CharField(max_length=100)
    goal = models.TextField()
    start_date = models.DateField()
    end_date = models.DateField()
    status = models.CharField(max_length=20, choices=[
        ('planning', 'Planning'),
        ('active', 'Active'),
        ('review', 'Review'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled')
    ], default='planning')
    
    # For tracking sprint metrics
    velocity = models.PositiveIntegerField(default=0)
    capacity = models.PositiveIntegerField(default=0)
    
    class Meta:
        ordering = ['-start_date']
        
    def __str__(self):
        return f"{self.name} ({self.project.title})"
    
    def duration_days(self):
        return (self.end_date - self.start_date).days
    
    def is_active(self):
        today = timezone.now().date()
        return self.start_date <= today <= self.end_date and self.status == 'active'
    
    def burndown_data(self):
        """Return a list of remaining points/hours per day of sprint"""
        # Implementation would return data for burndown chart
        return []

class TaskDependency(models.Model):
    """Tracks dependencies between tasks for advanced task scheduling"""
    DEPENDENCY_TYPES = [
        ('finish_to_start', 'Finish to Start'),  # Most common: Task B can't start until Task A completes
        ('start_to_start', 'Start to Start'),    # Task B can't start until Task A starts
        ('finish_to_finish', 'Finish to Finish'),# Task B can't finish until Task A finishes
        ('start_to_finish', 'Start to Finish')   # Task B can't finish until Task A starts
    ]
    
    from_task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='dependents')
    to_task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='dependencies')
    dependency_type = models.CharField(max_length=20, choices=DEPENDENCY_TYPES, default='finish_to_start')
    lag_days = models.IntegerField(default=0, help_text="Lag time in days (can be negative for lead time)")
    
    class Meta:
        unique_together = ('from_task', 'to_task')
        verbose_name_plural = 'Task Dependencies'
    
    def __str__(self):
        return f"{self.from_task.title} -> {self.to_task.title} ({self.get_dependency_type_display()})"
    
    def clean(self):
        from django.core.exceptions import ValidationError
        
        # Prevent circular dependencies
        if self.from_task == self.to_task:
            raise ValidationError("A task cannot depend on itself")
            
        # Check if this creates a circular dependency chain
        if self._creates_circular_dependency():
            raise ValidationError("This creates a circular dependency chain")
    
    def _creates_circular_dependency(self):
        """Check if adding this dependency creates a circular reference"""
        # Implementation would use a graph algorithm to detect cycles
        return False
    
    def calculate_lag_impact(self):
        """Calculate the impact of this dependency's lag on project timeline"""
        # Implementation would calculate timeline effects
        return self.lag_days
    
    def notify_affected_freelancers(self):
        """Notify freelancers affected by this dependency"""
        # Implementation would send notifications
        from_task_freelancers = self.from_task.assigned_to.all()
        to_task_freelancers = self.to_task.assigned_to.all()
        
        # Create notifications for affected users
        for user in to_task_freelancers:
            Notification.objects.create(
                user=user,
                type='Projects & Tasks',
                related_model_id=self.to_task.id,
                title=f"Task {self.to_task.title} dependency updated",
                notification_text=f"Your task depends on '{self.from_task.title}' which affects your timeline"
            )
        
        return True
    
    def can_start_dependent_task(self):
        """Check if the dependent task can be started based on this dependency"""
        if self.dependency_type == 'finish_to_start':
            return self.from_task.status == 'completed'
        elif self.dependency_type == 'start_to_start':
            return self.from_task.status in ['ongoing', 'completed']
        return True

class RACIMatrix(models.Model):
    """RACI responsibility assignment matrix"""
    ROLE_CHOICES = [
        ('responsible', 'Responsible'),
        ('accountable', 'Accountable'),
        ('consulted', 'Consulted'),
        ('informed', 'Informed')
    ]
    
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='raci_assignments')
    task = models.ForeignKey(Task, on_delete=models.CASCADE, null=True, blank=True, related_name='raci_assignments')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='raci_roles')
    role = models.CharField(max_length=15, choices=ROLE_CHOICES)
    notes = models.TextField(blank=True)
    
    class Meta:
        unique_together = ('task', 'user', 'role')
        verbose_name_plural = 'RACI Matrices'
        
    def __str__(self):
        target = self.task.title if self.task else self.project.title
        return f"{self.user.username} is {self.role} for {target}"

class KanbanBoard(models.Model):
    """Kanban board for visualizing workflow"""
    project = models.OneToOneField(Project, on_delete=models.CASCADE, related_name='kanban_board')
    name = models.CharField(max_length=100, default="Project Kanban")
    is_active = models.BooleanField(default=True)
    
    def __str__(self):
        return f"Kanban for {self.project.title}"
    
    def task_distribution(self):
        """Returns count of tasks in each column"""
        columns = self.columns.all()
        return {column.name: column.tasks.count() for column in columns}

class KanbanColumn(models.Model):
    """Column in a Kanban board representing a workflow stage"""
    board = models.ForeignKey(KanbanBoard, on_delete=models.CASCADE, related_name='columns')
    name = models.CharField(max_length=50)
    position = models.PositiveSmallIntegerField(default=0)
    wip_limit = models.PositiveIntegerField(null=True, blank=True, 
                                          help_text="Work in progress limit")
    tasks = models.ManyToManyField(Task, through='KanbanTask', related_name='kanban_columns')
    
    class Meta:
        ordering = ['position']
        
    def __str__(self):
        return f"{self.name} ({self.board.name})"
    
    def is_at_capacity(self):
        """Check if column has reached WIP limit"""
        if not self.wip_limit:
            return False
        return self.tasks.count() >= self.wip_limit

class KanbanTask(models.Model):
    """Task position in a Kanban column with additional metadata"""
    task = models.ForeignKey(Task, on_delete=models.CASCADE)
    column = models.ForeignKey(KanbanColumn, on_delete=models.CASCADE)
    position = models.PositiveIntegerField(default=0, help_text="Position within column")
    last_moved = models.DateTimeField(auto_now=True)
    blocked = models.BooleanField(default=False)
    blocked_reason = models.TextField(blank=True)
    
    class Meta:
        ordering = ['position']
        unique_together = ('task', 'column')

class Risk(models.Model):
    """Risk management for project planning"""
    PROBABILITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High')
    ]
    
    IMPACT_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High')
    ]
    
    STATUS_CHOICES = [
        ('identified', 'Identified'),
        ('assessed', 'Assessed'),
        ('mitigated', 'Mitigated'),
        ('closed', 'Closed')
    ]
    
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='risks')
    title = models.CharField(max_length=200)
    description = models.TextField()
    probability = models.CharField(max_length=10, choices=PROBABILITY_CHOICES, default='medium')
    impact = models.CharField(max_length=10, choices=IMPACT_CHOICES, default='medium')
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='identified')
    identified_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='identified_risks')
    owner = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='owned_risks')
    mitigation_plan = models.TextField(blank=True)
    contingency_plan = models.TextField(blank=True)
    identified_date = models.DateField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.title} ({self.get_status_display()})"
    
    @property
    def risk_score(self):
        """Calculate risk score based on probability and impact"""
        impact_scores = {'low': 1, 'medium': 2, 'high': 3}
        probability_scores = {'low': 1, 'medium': 2, 'high': 3}
        
        return impact_scores[self.impact] * probability_scores[self.probability]

class ProjectTemplate(models.Model):
    """Reusable project templates for quick setup"""
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField()
    estimated_duration_days = models.PositiveIntegerField()
    default_budget = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    skills_required = models.ManyToManyField(Skill, related_name='templates')
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    is_public = models.BooleanField(default=False)
    
    def __str__(self):
        return self.name
    
    def clone_to_project(self, client, title, budget=None):
        """Create a new project from this template"""
        project = Project.objects.create(
            title=title,
            description=self.description,
            budget=budget or self.default_budget,
            client=client,
            deadline=timezone.now().date() + timezone.timedelta(days=self.estimated_duration_days)
        )
        
        # Clone template task structures and milestones
        for task_template in self.task_templates.all():
            task = Task.objects.create(
                project=project,
                title=task_template.title,
                description=task_template.description,
                budget=task_template.default_budget,
                deadline=timezone.now().date() + timezone.timedelta(days=task_template.estimated_duration_days)
            )
            
            # Add task-specific skills
            for skill in task_template.skills_required.all():
                task.skills_required_for_task.add(skill)
                
        # Set up dependencies between tasks
        for dependency in self.task_dependencies.all():
            from_task = project.tasks.get(title=dependency.from_task.title)
            to_task = project.tasks.get(title=dependency.to_task.title)
            
            TaskDependency.objects.create(
                from_task=from_task,
                to_task=to_task,
                dependency_type=dependency.dependency_type,
                lag_days=dependency.lag_days
            )
            
        return project

class TemplateTask(models.Model):
    """Task template for project templates"""
    template = models.ForeignKey(ProjectTemplate, on_delete=models.CASCADE, related_name='task_templates')
    title = models.CharField(max_length=100)
    description = models.TextField()
    estimated_duration_days = models.PositiveIntegerField()
    default_budget = models.DecimalField(max_digits=10, decimal_places=2)
    skills_required = models.ManyToManyField(Skill, related_name='task_templates')
    position = models.PositiveIntegerField(default=0)
    
    class Meta:
        ordering = ['position']
        
    def __str__(self):
        return f"{self.title} in {self.template.name}"

class TemplateDependency(models.Model):
    """Dependencies between task templates"""
    template = models.ForeignKey(ProjectTemplate, on_delete=models.CASCADE, related_name='task_dependencies')
    from_task = models.ForeignKey(TemplateTask, on_delete=models.CASCADE, related_name='dependents')
    to_task = models.ForeignKey(TemplateTask, on_delete=models.CASCADE, related_name='dependencies')
    dependency_type = models.CharField(max_length=20, choices=TaskDependency.DEPENDENCY_TYPES, default='finish_to_start')
    lag_days = models.IntegerField(default=0)
    
    def __str__(self):
        return f"{self.from_task.title} -> {self.to_task.title}"

class AIProjectInsight(models.Model):
    """AI-generated insights about project status and risks"""
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='ai_insights')
    insight_type = models.CharField(max_length=50, choices=[
        ('risk_prediction', 'Risk Prediction'),
        ('delay_forecast', 'Delay Forecast'),
        ('resource_allocation', 'Resource Allocation'),
        ('budget_projection', 'Budget Projection'),
        ('quality_assessment', 'Quality Assessment')
    ])
    confidence_score = models.DecimalField(max_digits=5, decimal_places=2,
                                         validators=[MinValueValidator(0)])
    insight_text = models.TextField()
    suggested_actions = models.TextField(blank=True)
    generated_at = models.DateTimeField(auto_now_add=True)
    is_resolved = models.BooleanField(default=False)
    
    class Meta:
        ordering = ['-generated_at']
        
    def __str__(self):
        return f"{self.get_insight_type_display()} for {self.project.title}"

class TaskMention(models.Model):
    """@mentions in task discussions to improve collaboration"""
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='mentions')
    mentioned_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='mentions_made')
    mentioned_user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='mentions_received')
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)
    
    def __str__(self):
        return f"@{self.mentioned_user.username} mentioned by {self.mentioned_by.username}"
    
    def mark_as_read(self):
        self.is_read = True
        self.save()

class PerformanceBadge(models.Model):
    """Gamification badges for freelancer achievements"""
    name = models.CharField(max_length=50)
    description = models.TextField()
    badge_type = models.CharField(max_length=30, choices=[
        ('speed', 'Fast Delivery'),
        ('quality', 'High Quality'),
        ('communication', 'Great Communication'),
        ('efficiency', 'Efficient Work'),
        ('innovation', 'Innovative Solutions'),
        ('collaboration', 'Team Player')
    ])
    icon = models.URLField(max_length=255)
    points_value = models.PositiveIntegerField(default=10)
    
    def __str__(self):
        return self.name

class FreelancerBadge(models.Model):
    """Awarded badges to freelancers"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='badges')
    badge = models.ForeignKey(PerformanceBadge, on_delete=models.CASCADE)
    project = models.ForeignKey(Project, on_delete=models.CASCADE, null=True, blank=True)
    task = models.ForeignKey(Task, on_delete=models.CASCADE, null=True, blank=True)
    awarded_date = models.DateTimeField(auto_now_add=True)
    awarded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='badges_awarded')
    notes = models.TextField(blank=True)
    
    class Meta:
        unique_together = ('user', 'badge', 'project')
        
    def __str__(self):
        return f"{self.user.username} earned {self.badge.name}"

class ParallelWorkflow(models.Model):
    """Manages parallel work streams within a project"""
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='workflows')
    name = models.CharField(max_length=100)
    description = models.TextField()
    start_date = models.DateField()
    target_end_date = models.DateField()
    actual_end_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=[
        ('planning', 'Planning'),
        ('active', 'Active'),
        ('completed', 'Completed'),
        ('blocked', 'Blocked')
    ], default='planning')
    
    def __str__(self):
        return f"{self.name} - {self.project.title}"
    
    def add_tasks(self, tasks):
        """Add tasks to this workflow"""
        for task in tasks:
            self.workflow_tasks.create(task=task)
    
    @property
    def completion_percentage(self):
        """Calculate percentage of completed tasks"""
        total = self.workflow_tasks.count()
        if not total:
            return 0
        completed = self.workflow_tasks.filter(task__status='completed').count()
        return (completed / total) * 100

class WorkflowTask(models.Model):
    """Tasks assigned to specific workflows"""
    workflow = models.ForeignKey(ParallelWorkflow, on_delete=models.CASCADE, related_name='workflow_tasks')
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='workflows')
    position = models.PositiveIntegerField(default=0)
    
    class Meta:
        ordering = ['position']
        unique_together = ('workflow', 'task')
        
    def __str__(self):
        return f"{self.task.title} in {self.workflow.name}"

class ProjectAnalytics(models.Model):
    """Analytics for client-friendly project insights"""
    project = models.OneToOneField('core.Project', on_delete=models.CASCADE, related_name='analytics')
    time_saved_days = models.IntegerField(default=0, help_text="Days saved using multi-freelancer approach")
    cost_efficiency_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0, 
                                               help_text="Cost efficiency from specialist freelancers")
    parallel_work_streams = models.IntegerField(default=0, help_text="Number of parallel work streams")
    risk_reduction_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0,
                                               help_text="Risk reduction from multiple freelancers")
    quality_improvement_score = models.DecimalField(max_digits=5, decimal_places=2, default=0,
                                                  help_text="Quality improvement from specialist freelancers")
    last_updated = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Analytics for {self.project.title}"
    
    def calculate_metrics(self):
        """Calculate all metrics for project analytics"""
        self.calculate_time_savings()
        self.calculate_cost_efficiency()
        self.calculate_risk_reduction()
        self.calculate_quality_score()
        self.save()
    
    def calculate_time_savings(self):
        """Calculate time saved through parallel work"""
        # Implementation would compare sequential vs parallel paths
        tasks = self.project.tasks.all()
        sequential_days = sum(task.estimated_days for task in tasks)
        
        # Calculate critical path length
        critical_path_days = sequential_days  # Simplified - actual implementation would use critical path algorithm
        
        # Calculate days saved
        if sequential_days > 0:
            self.time_saved_days = sequential_days - critical_path_days
            
        return self.time_saved_days
    
    def calculate_cost_efficiency(self):
        """Calculate cost efficiency of specialists vs generalists"""
        # Implementation would compare specialist vs generalist costs
        self.cost_efficiency_percent = 15.0  # Placeholder
        return self.cost_efficiency_percent
    
    def calculate_risk_reduction(self):
        """Calculate risk reduction from diversified freelancer pool"""
        # Implementation would calculate risk metrics
        self.risk_reduction_percent = 25.0  # Placeholder
        return self.risk_reduction_percent
    
    def calculate_quality_score(self):
        """Calculate quality improvement from specialist work"""
        # Implementation would analyze specialist skills vs requirements
        self.quality_improvement_score = 20.0  # Placeholder
        return self.quality_improvement_score

class AITaskRecommendation(models.Model):
    """AI-generated recommendations for task management"""
    project = models.ForeignKey('core.Project', on_delete=models.CASCADE, related_name='task_recommendations')
    recommendation_type = models.CharField(max_length=30, choices=[
        ('task_splitting', 'Task Splitting'),
        ('freelancer_matching', 'Freelancer Matching'),
        ('schedule_optimization', 'Schedule Optimization'),
        ('dependency_suggestion', 'Dependency Suggestion'),
        ('risk_mitigation', 'Risk Mitigation')
    ])
    task = models.ForeignKey('core.Task', on_delete=models.CASCADE, null=True, blank=True, 
                           related_name='ai_recommendations')
    recommendation_text = models.TextField()
    confidence_score = models.DecimalField(max_digits=5, decimal_places=2)
    is_implemented = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.get_recommendation_type_display()} for {self.project.title}"
