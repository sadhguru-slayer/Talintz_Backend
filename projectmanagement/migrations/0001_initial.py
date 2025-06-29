# Generated by Django 5.2.3 on 2025-06-27 19:37

import django.core.validators
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('core', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='PerformanceBadge',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=50)),
                ('description', models.TextField()),
                ('badge_type', models.CharField(choices=[('speed', 'Fast Delivery'), ('quality', 'High Quality'), ('communication', 'Great Communication'), ('efficiency', 'Efficient Work'), ('innovation', 'Innovative Solutions'), ('collaboration', 'Team Player')], max_length=30)),
                ('icon', models.URLField(max_length=255)),
                ('points_value', models.PositiveIntegerField(default=10)),
            ],
        ),
        migrations.CreateModel(
            name='AIProjectInsight',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('insight_type', models.CharField(choices=[('risk_prediction', 'Risk Prediction'), ('delay_forecast', 'Delay Forecast'), ('resource_allocation', 'Resource Allocation'), ('budget_projection', 'Budget Projection'), ('quality_assessment', 'Quality Assessment')], max_length=50)),
                ('confidence_score', models.DecimalField(decimal_places=2, max_digits=5, validators=[django.core.validators.MinValueValidator(0)])),
                ('insight_text', models.TextField()),
                ('suggested_actions', models.TextField(blank=True)),
                ('generated_at', models.DateTimeField(auto_now_add=True)),
                ('is_resolved', models.BooleanField(default=False)),
                ('project', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='ai_insights', to='core.project')),
            ],
            options={
                'ordering': ['-generated_at'],
            },
        ),
        migrations.CreateModel(
            name='AITaskRecommendation',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('recommendation_type', models.CharField(choices=[('task_splitting', 'Task Splitting'), ('freelancer_matching', 'Freelancer Matching'), ('schedule_optimization', 'Schedule Optimization'), ('dependency_suggestion', 'Dependency Suggestion'), ('risk_mitigation', 'Risk Mitigation')], max_length=30)),
                ('recommendation_text', models.TextField()),
                ('confidence_score', models.DecimalField(decimal_places=2, max_digits=5)),
                ('is_implemented', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('project', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='task_recommendations', to='core.project')),
                ('task', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='ai_recommendations', to='core.task')),
            ],
        ),
        migrations.CreateModel(
            name='KanbanBoard',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(default='Project Kanban', max_length=100)),
                ('is_active', models.BooleanField(default=True)),
                ('project', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='kanban_board', to='core.project')),
            ],
        ),
        migrations.CreateModel(
            name='KanbanColumn',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=50)),
                ('position', models.PositiveSmallIntegerField(default=0)),
                ('wip_limit', models.PositiveIntegerField(blank=True, help_text='Work in progress limit', null=True)),
                ('board', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='columns', to='projectmanagement.kanbanboard')),
            ],
            options={
                'ordering': ['position'],
            },
        ),
        migrations.CreateModel(
            name='KanbanTask',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('position', models.PositiveIntegerField(default=0, help_text='Position within column')),
                ('last_moved', models.DateTimeField(auto_now=True)),
                ('blocked', models.BooleanField(default=False)),
                ('blocked_reason', models.TextField(blank=True)),
                ('column', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='projectmanagement.kanbancolumn')),
                ('task', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='core.task')),
            ],
            options={
                'ordering': ['position'],
                'unique_together': {('task', 'column')},
            },
        ),
        migrations.AddField(
            model_name='kanbancolumn',
            name='tasks',
            field=models.ManyToManyField(related_name='kanban_columns', through='projectmanagement.KanbanTask', to='core.task'),
        ),
        migrations.CreateModel(
            name='ParallelWorkflow',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100)),
                ('description', models.TextField()),
                ('start_date', models.DateField()),
                ('target_end_date', models.DateField()),
                ('actual_end_date', models.DateField(blank=True, null=True)),
                ('status', models.CharField(choices=[('planning', 'Planning'), ('active', 'Active'), ('completed', 'Completed'), ('blocked', 'Blocked')], default='planning', max_length=20)),
                ('project', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='workflows', to='core.project')),
            ],
        ),
        migrations.CreateModel(
            name='ProjectAnalytics',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('time_saved_days', models.IntegerField(default=0, help_text='Days saved using multi-freelancer approach')),
                ('cost_efficiency_percent', models.DecimalField(decimal_places=2, default=0, help_text='Cost efficiency from specialist freelancers', max_digits=5)),
                ('parallel_work_streams', models.IntegerField(default=0, help_text='Number of parallel work streams')),
                ('risk_reduction_percent', models.DecimalField(decimal_places=2, default=0, help_text='Risk reduction from multiple freelancers', max_digits=5)),
                ('quality_improvement_score', models.DecimalField(decimal_places=2, default=0, help_text='Quality improvement from specialist freelancers', max_digits=5)),
                ('last_updated', models.DateTimeField(auto_now=True)),
                ('project', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='analytics', to='core.project')),
            ],
        ),
        migrations.CreateModel(
            name='ProjectTemplate',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100, unique=True)),
                ('description', models.TextField()),
                ('estimated_duration_days', models.PositiveIntegerField()),
                ('default_budget', models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True)),
                ('is_public', models.BooleanField(default=False)),
                ('created_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
                ('skills_required', models.ManyToManyField(related_name='templates', to='core.skill')),
            ],
        ),
        migrations.CreateModel(
            name='Risk',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=200)),
                ('description', models.TextField()),
                ('probability', models.CharField(choices=[('low', 'Low'), ('medium', 'Medium'), ('high', 'High')], default='medium', max_length=10)),
                ('impact', models.CharField(choices=[('low', 'Low'), ('medium', 'Medium'), ('high', 'High')], default='medium', max_length=10)),
                ('status', models.CharField(choices=[('identified', 'Identified'), ('assessed', 'Assessed'), ('mitigated', 'Mitigated'), ('closed', 'Closed')], default='identified', max_length=15)),
                ('mitigation_plan', models.TextField(blank=True)),
                ('contingency_plan', models.TextField(blank=True)),
                ('identified_date', models.DateField(auto_now_add=True)),
                ('identified_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='identified_risks', to=settings.AUTH_USER_MODEL)),
                ('owner', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='owned_risks', to=settings.AUTH_USER_MODEL)),
                ('project', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='risks', to='core.project')),
            ],
        ),
        migrations.CreateModel(
            name='Sprint',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100)),
                ('goal', models.TextField()),
                ('start_date', models.DateField()),
                ('end_date', models.DateField()),
                ('status', models.CharField(choices=[('planning', 'Planning'), ('active', 'Active'), ('review', 'Review'), ('completed', 'Completed'), ('cancelled', 'Cancelled')], default='planning', max_length=20)),
                ('velocity', models.PositiveIntegerField(default=0)),
                ('capacity', models.PositiveIntegerField(default=0)),
                ('project', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='sprints', to='core.project')),
            ],
            options={
                'ordering': ['-start_date'],
            },
        ),
        migrations.CreateModel(
            name='TaskMention',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('message', models.TextField()),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('is_read', models.BooleanField(default=False)),
                ('mentioned_by', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='mentions_made', to=settings.AUTH_USER_MODEL)),
                ('mentioned_user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='mentions_received', to=settings.AUTH_USER_MODEL)),
                ('task', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='mentions', to='core.task')),
            ],
        ),
        migrations.CreateModel(
            name='TemplateTask',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=100)),
                ('description', models.TextField()),
                ('estimated_duration_days', models.PositiveIntegerField()),
                ('default_budget', models.DecimalField(decimal_places=2, max_digits=10)),
                ('position', models.PositiveIntegerField(default=0)),
                ('skills_required', models.ManyToManyField(related_name='task_templates', to='core.skill')),
                ('template', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='task_templates', to='projectmanagement.projecttemplate')),
            ],
            options={
                'ordering': ['position'],
            },
        ),
        migrations.CreateModel(
            name='TemplateDependency',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('dependency_type', models.CharField(choices=[('finish_to_start', 'Finish to Start'), ('start_to_start', 'Start to Start'), ('finish_to_finish', 'Finish to Finish'), ('start_to_finish', 'Start to Finish')], default='finish_to_start', max_length=20)),
                ('lag_days', models.IntegerField(default=0)),
                ('template', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='task_dependencies', to='projectmanagement.projecttemplate')),
                ('from_task', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='dependents', to='projectmanagement.templatetask')),
                ('to_task', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='dependencies', to='projectmanagement.templatetask')),
            ],
        ),
        migrations.CreateModel(
            name='FreelancerBadge',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('awarded_date', models.DateTimeField(auto_now_add=True)),
                ('notes', models.TextField(blank=True)),
                ('awarded_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='badges_awarded', to=settings.AUTH_USER_MODEL)),
                ('project', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='core.project')),
                ('task', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='core.task')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='badges', to=settings.AUTH_USER_MODEL)),
                ('badge', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='projectmanagement.performancebadge')),
            ],
            options={
                'unique_together': {('user', 'badge', 'project')},
            },
        ),
        migrations.CreateModel(
            name='RACIMatrix',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('role', models.CharField(choices=[('responsible', 'Responsible'), ('accountable', 'Accountable'), ('consulted', 'Consulted'), ('informed', 'Informed')], max_length=15)),
                ('notes', models.TextField(blank=True)),
                ('project', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='raci_assignments', to='core.project')),
                ('task', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='raci_assignments', to='core.task')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='raci_roles', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name_plural': 'RACI Matrices',
                'unique_together': {('task', 'user', 'role')},
            },
        ),
        migrations.CreateModel(
            name='TaskDependency',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('dependency_type', models.CharField(choices=[('finish_to_start', 'Finish to Start'), ('start_to_start', 'Start to Start'), ('finish_to_finish', 'Finish to Finish'), ('start_to_finish', 'Start to Finish')], default='finish_to_start', max_length=20)),
                ('lag_days', models.IntegerField(default=0, help_text='Lag time in days (can be negative for lead time)')),
                ('from_task', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='dependents', to='core.task')),
                ('to_task', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='dependencies', to='core.task')),
            ],
            options={
                'verbose_name_plural': 'Task Dependencies',
                'unique_together': {('from_task', 'to_task')},
            },
        ),
        migrations.CreateModel(
            name='WorkflowTask',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('position', models.PositiveIntegerField(default=0)),
                ('task', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='workflows', to='core.task')),
                ('workflow', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='workflow_tasks', to='projectmanagement.parallelworkflow')),
            ],
            options={
                'ordering': ['position'],
                'unique_together': {('workflow', 'task')},
            },
        ),
    ]
