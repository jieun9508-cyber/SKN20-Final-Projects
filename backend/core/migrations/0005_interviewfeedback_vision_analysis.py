from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0004_add_interview_models'),
    ]

    operations = [
        migrations.AddField(
            model_name='interviewfeedback',
            name='vision_analysis',
            field=models.JSONField(blank=True, default=None, null=True),
        ),
    ]
