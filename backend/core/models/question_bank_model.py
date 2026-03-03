# 생성일: 2026-02-28
# 설명: 면접 질문 뱅크 모델 - interview_questions_v3.json 데이터 저장 및 검색

from django.db import models
from .base_model import BaseModel


class InterviewQuestion(BaseModel):
    """
    면접 질문 뱅크
    - AI Hub ICT, GitHub 레포, 잡코리아 면접질문 데이터 통합
    - 기업/슬롯/직무/소스별 검색 지원
    """

    class SlotType(models.TextChoices):
        TECHNICAL = 'technical', '기술'
        MOTIVATION = 'motivation', '지원동기'
        COLLABORATION = 'collaboration', '협업'
        PROBLEM_SOLVING = 'problem_solving', '문제해결'
        GROWTH = 'growth', '성장'
        GENERAL = 'general', '공통'

    class Source(models.TextChoices):
        AIHUB = 'aihub_ict', 'AI Hub ICT'
        JOBKOREA = 'jobkorea', '잡코리아'
        GITHUB = 'github', 'GitHub'
        YOUTUBE = 'youtube', 'YouTube'
        USER = 'user', '사용자 제보'

    class Language(models.TextChoices):
        KO = 'ko', '한국어'
        EN = 'en', '영어'

    # ── 핵심 필드 ──
    question_text = models.TextField(help_text="질문 텍스트")
    slot_type = models.CharField(
        max_length=20,
        choices=SlotType.choices,
        default=SlotType.GENERAL,
        db_index=True,
        help_text="슬롯 유형",
    )

    # ── 기업/직무 정보 ──
    company = models.CharField(max_length=100, blank=True, default='', db_index=True, help_text="기업명")
    job = models.CharField(max_length=100, blank=True, default='', db_index=True, help_text="직무")
    category = models.CharField(max_length=100, blank=True, default='', help_text="카테고리 (OS, Network, ML 등)")

    # ── 출처 정보 ──
    source = models.CharField(max_length=30, blank=True, default='', db_index=True, help_text="데이터 소스")
    language = models.CharField(
        max_length=5,
        choices=Language.choices,
        default=Language.KO,
        help_text="언어",
    )
    region = models.CharField(max_length=20, blank=True, default='korea', help_text="지역")

    # ── 답변 (AI Hub 데이터) ──
    answer_text = models.TextField(blank=True, default='', help_text="답변 텍스트")
    answer_summary = models.TextField(blank=True, default='', help_text="답변 요약")

    # ── 잡코리아 메타데이터 ──
    period = models.CharField(max_length=20, blank=True, default='', help_text="채용시기 (2024년 상반기)")
    employment_type = models.CharField(max_length=10, blank=True, default='', help_text="채용유형 (신입/인턴/경력)")
    interview_type = models.CharField(max_length=20, blank=True, default='', help_text="면접유형 (일반/인성/압박/임원/PT)")
    is_it_job = models.BooleanField(null=True, blank=True, help_text="IT 직무 여부")
    c_idx = models.IntegerField(null=True, blank=True, help_text="잡코리아 기업 ID")

    # ── 부가 정보 ──
    difficulty = models.CharField(max_length=20, blank=True, default='', help_text="난이도")
    keywords = models.JSONField(default=list, blank=True, help_text="키워드 태그")

    class Meta:
        db_table = 'question_bank'
        verbose_name = '면접 질문'
        verbose_name_plural = '면접 질문 뱅크'
        ordering = ['-create_date']

        indexes = [
            # 핵심 검색 조합: 기업 + 슬롯 + 직무
            models.Index(fields=['company', 'slot_type', 'job'], name='idx_company_slot_job'),
            # 슬롯 + 소스
            models.Index(fields=['slot_type', 'source'], name='idx_slot_source'),
            # 기업 + 면접유형
            models.Index(fields=['company', 'interview_type'], name='idx_company_interview'),
        ]

    def __str__(self):
        company_str = f"[{self.company}] " if self.company else ""
        return f"{company_str}{self.question_text[:50]}"
