# 생성일: 2026-02-28
# 설명: interview_questions_v3.json → DB 일괄 임포트 커맨드
#
# 사용법:
#   python manage.py import_questions data/interview_questions_v3.json
#   python manage.py import_questions data/interview_questions_v3.json --clear  # 기존 데이터 삭제 후 임포트
#   python manage.py import_questions data/interview_questions_v3.json --dry-run # 미리보기만

import json
import time
from django.core.management.base import BaseCommand
from core.models import InterviewQuestion


class Command(BaseCommand):
    help = 'interview_questions_v3.json 파일을 DB에 임포트합니다'

    def add_arguments(self, parser):
        parser.add_argument('json_file', type=str, help='v3.json 파일 경로')
        parser.add_argument('--clear', action='store_true', help='기존 데이터 전체 삭제 후 임포트')
        parser.add_argument('--dry-run', action='store_true', help='실제 저장하지 않고 미리보기만')
        parser.add_argument('--batch-size', type=int, default=1000, help='배치 크기 (기본: 1000)')

    def handle(self, *args, **options):
        json_file = options['json_file']
        clear = options['clear']
        dry_run = options['dry_run']
        batch_size = options['batch_size']

        # 1. JSON 로드
        self.stdout.write(f'📂 파일 로드: {json_file}')
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        questions = data.get('questions', [])
        metadata = data.get('metadata', {})
        self.stdout.write(f'  총 질문: {len(questions)}건')
        self.stdout.write(f'  버전: {metadata.get("version", "?")}')
        self.stdout.write(f'  소스: {metadata.get("source", "?")}')

        if dry_run:
            self.stdout.write(self.style.WARNING('\n🔍 DRY RUN 모드 - 실제 저장하지 않습니다'))
            self._print_stats(questions)
            return

        # 2. 기존 데이터 삭제
        if clear:
            count = InterviewQuestion.objects.count()
            InterviewQuestion.objects.all().delete()
            self.stdout.write(self.style.WARNING(f'\n🗑️  기존 데이터 {count}건 삭제'))

        # 3. 배치 임포트
        self.stdout.write(f'\n📥 임포트 시작 (배치 크기: {batch_size})')
        start = time.time()

        objects = []
        skipped = 0

        for q in questions:
            text = q.get('question_text', '').strip()
            if not text or len(text) < 5:
                skipped += 1
                continue

            # source 필드 정규화: github_xxx → github
            source_raw = q.get('source', '')
            if source_raw.startswith('github'):
                source_normalized = 'github'
            elif source_raw.startswith('youtube'):
                source_normalized = 'youtube'
            else:
                source_normalized = source_raw

            objects.append(InterviewQuestion(
                question_text=text,
                slot_type=q.get('slot_type', 'general'),
                company=q.get('company', ''),
                job=q.get('job', ''),
                category=q.get('category', ''),
                source=source_normalized,
                language=q.get('language', 'ko'),
                region=q.get('region', 'korea'),
                answer_text=q.get('answer_text', ''),
                answer_summary=q.get('answer_summary', ''),
                period=q.get('period', ''),
                employment_type=q.get('employment_type', ''),
                interview_type=q.get('interview_type', ''),
                is_it_job=q.get('is_it_job'),
                c_idx=q.get('c_idx'),
                difficulty=q.get('difficulty', ''),
                keywords=q.get('keywords', []),
                create_id='system',
                update_id='system',
            ))

        # bulk_create로 배치 삽입
        created = 0
        for i in range(0, len(objects), batch_size):
            batch = objects[i:i + batch_size]
            InterviewQuestion.objects.bulk_create(batch, batch_size=batch_size)
            created += len(batch)
            self.stdout.write(f'  ✅ {created}/{len(objects)}건 완료')

        elapsed = time.time() - start

        self.stdout.write(self.style.SUCCESS(
            f'\n🎉 임포트 완료!'
            f'\n  저장: {created}건'
            f'\n  건너뜀: {skipped}건'
            f'\n  소요시간: {elapsed:.1f}초'
            f'\n  DB 총 건수: {InterviewQuestion.objects.count()}건'
        ))

    def _print_stats(self, questions):
        """미리보기 통계"""
        from collections import Counter

        slots = Counter(q.get('slot_type', '') for q in questions)
        sources = Counter()
        for q in questions:
            s = q.get('source', '')
            sources['github' if s.startswith('github') else s] += 1
        companies = Counter(q.get('company', '') for q in questions if q.get('company'))

        self.stdout.write(f'\n📊 통계:')
        self.stdout.write(f'\n  슬롯별:')
        for s, n in slots.most_common():
            self.stdout.write(f'    {s:<18} {n:>6}건')
        self.stdout.write(f'\n  소스별:')
        for s, n in sources.most_common():
            self.stdout.write(f'    {s:<18} {n:>6}건')
        self.stdout.write(f'\n  기업 수: {len(companies)}개')
        self.stdout.write(f'\n  기업 TOP 10:')
        for c, n in companies.most_common(10):
            self.stdout.write(f'    {c:<25} {n:>4}건')
