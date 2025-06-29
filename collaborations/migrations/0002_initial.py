# Generated by Django 5.2.3 on 2025-06-27 19:37

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('collaborations', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='collaboration',
            name='admin',
            field=models.ManyToManyField(related_name='admin_collaborations', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='collaborationinvitation',
            name='collaboration',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='invitations', to='collaborations.collaboration'),
        ),
        migrations.AddField(
            model_name='collaborationinvitation',
            name='receiver',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='received_invitations', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='collaborationinvitation',
            name='sender',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='sent_invitations', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='collaborationmembership',
            name='collaboration',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='memberships', to='collaborations.collaboration'),
        ),
        migrations.AddField(
            model_name='collaborationmembership',
            name='user',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='collaboration_memberships', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AlterUniqueTogether(
            name='collaborationmembership',
            unique_together={('collaboration', 'user')},
        ),
    ]
