# Generated manually for AI Coach conversation history

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0006_remove_coach_feedback'),
    ]

    operations = [
        migrations.CreateModel(
            name='CoachConversation',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('create_id', models.CharField(blank=True, help_text='생성자 ID', max_length=50, null=True)),
                ('update_id', models.CharField(blank=True, help_text='수정자 ID', max_length=50, null=True)),
                ('create_date', models.DateTimeField(auto_now_add=True, help_text='생성 일시')),
                ('update_date', models.DateTimeField(auto_now=True, help_text='수정 일시')),
                ('use_yn', models.CharField(default='Y', help_text='사용 여부 (Y/N)', max_length=1)),
                ('title', models.CharField(default='', help_text='첫 메시지 앞 100자', max_length=100)),
                ('status', models.CharField(default='active', help_text='active / closed', max_length=10)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='coach_conversations', to='core.userprofile')),
            ],
            options={
                'db_table': 'gym_coach_conversation',
                'ordering': ['-create_date'],
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='CoachMessage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('create_id', models.CharField(blank=True, help_text='생성자 ID', max_length=50, null=True)),
                ('update_id', models.CharField(blank=True, help_text='수정자 ID', max_length=50, null=True)),
                ('create_date', models.DateTimeField(auto_now_add=True, help_text='생성 일시')),
                ('update_date', models.DateTimeField(auto_now=True, help_text='수정 일시')),
                ('use_yn', models.CharField(default='Y', help_text='사용 여부 (Y/N)', max_length=1)),
                ('turn_number', models.IntegerField(help_text='대화 내 순번')),
                ('role', models.CharField(help_text='user / assistant', max_length=10)),
                ('content', models.TextField(help_text='메시지 본문')),
                ('conversation', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='messages', to='core.coachconversation')),
            ],
            options={
                'db_table': 'gym_coach_message',
                'ordering': ['turn_number'],
                'abstract': False,
            },
        ),
    ]
