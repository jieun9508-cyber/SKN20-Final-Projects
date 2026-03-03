from django.db import models
from .base_model import BaseModel
from .user_model import UserProfile


class CoachConversation(BaseModel):
    """AI Coach 대화 세션. 사용자별로 하나의 active 대화를 유지."""
    user = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name='coach_conversations')
    title = models.CharField(max_length=100, default='', help_text="첫 메시지 앞 100자")
    status = models.CharField(max_length=10, default='active', help_text="active / closed")

    class Meta:
        db_table = 'gym_coach_conversation'
        ordering = ['-create_date']

    def __str__(self):
        return f"CoachConv {self.pk} - {self.user.username} ({self.status})"


class CoachMessage(BaseModel):
    """AI Coach 대화 내 개별 메시지."""
    conversation = models.ForeignKey(CoachConversation, on_delete=models.CASCADE, related_name='messages')
    turn_number = models.IntegerField(help_text="대화 내 순번")
    role = models.CharField(max_length=10, help_text="user / assistant")
    content = models.TextField(help_text="메시지 본문")

    class Meta:
        db_table = 'gym_coach_message'
        ordering = ['turn_number']

    def __str__(self):
        return f"Msg {self.turn_number} ({self.role}) - Conv {self.conversation_id}"
