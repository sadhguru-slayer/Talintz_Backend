from django.db import migrations, models
import django.core.validators

class Migration(migrations.Migration):

    dependencies = [
        ('core', 'previous_migration'),
    ]

    operations = [
        migrations.AddField(
            model_name='project',
            name='pricing_strategy',
            field=models.CharField(
                choices=[
                    ('fixed', 'Fixed Price'),
                    ('hourly', 'Hourly Rate'),
                    ('milestone', 'Milestone-Based'),
                    ('hybrid', 'Hybrid Model')
                ],
                default='fixed',
                max_length=20,
                help_text='How the project will be priced and paid'
            ),
        ),
        migrations.AddField(
            model_name='project',
            name='hourly_rate_min',
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                help_text='Minimum hourly rate for hourly projects',
                max_digits=8,
                null=True
            ),
        ),
        migrations.AddField(
            model_name='project',
            name='hourly_rate_max',
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                help_text='Maximum hourly rate for hourly projects',
                max_digits=8,
                null=True
            ),
        ),
        migrations.AddField(
            model_name='project',
            name='estimated_hours',
            field=models.PositiveIntegerField(
                blank=True,
                help_text='Estimated hours for hourly projects',
                null=True
            ),
        ),
        migrations.AddField(
            model_name='project',
            name='milestone_budget',
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                help_text='Total budget for milestone-based projects',
                max_digits=10,
                null=True
            ),
        ),
        migrations.AlterField(
            model_name='project',
            name='budget',
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                help_text='Total budget for fixed price projects',
                max_digits=10,
                null=True
            ),
        ),
        migrations.AddIndex(
            model_name='project',
            index=models.Index(fields=['pricing_strategy'], name='project_pricing_strategy_idx'),
        ),
    ] 