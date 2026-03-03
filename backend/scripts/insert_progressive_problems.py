"""
Progressive Problems 데이터를 gym_practice_detail 테이블에 삽입하는 스크립트
docker compose exec backend python insert_progressive_problems.py
"""
import os
import sys
import json
import django
from datetime import datetime

# Django 설정
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from core.models import Practice, PracticeDetail

def load_progressive_problems():
    """progressive-problems.json 파일 로드"""
    json_path = os.path.join(
        os.path.dirname(__file__),
        'progressive-problems.json'
    )

    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    return data['progressiveProblems']

def insert_progressive_problems():
    """Progressive Problems를 데이터베이스에 삽입"""

    # 1. Practice 확인 또는 생성 (fixture의 unit02 활용)
    practice_id = 'unit02'
    practice, created = Practice.objects.get_or_create(
        id=practice_id,
    )

    if created:
        print(f'✅ Practice 생성됨: {practice.id} - {practice.title}')
    else:
        print(f'ℹ️  기존 Practice 사용: {practice.id} - {practice.title}')

    # 2. Progressive Problems 로드
    problems = load_progressive_problems()
    print(f'\n📂 로드된 문제 수: {len(problems)}개')

    # 3. 각 문제를 PracticeDetail로 삽입
    inserted_count = 0
    updated_count = 0

    for idx, problem in enumerate(problems, 1):
        detail_id = f"{practice_id}_{idx:02d}"

        # 문제 데이터 준비
        detail_data = {
            'practice': practice,
            'detail_title': f"{problem.get('scenario', problem['id'])}",
            'detail_type': 'PROBLEM',
            'content_data': problem,  # 전체 문제 데이터를 JSON으로 저장
            'display_order': idx,
            'is_active': True,
            'use_yn': 'Y',
            'create_id': 'system',
            'update_id': 'system',
            'create_date': datetime.now(),
            'update_date': datetime.now()
        }

        # 생성 또는 업데이트
        detail, created = PracticeDetail.objects.update_or_create(
            id=detail_id,
            defaults=detail_data
        )

        if created:
            inserted_count += 1
            print(f'  ✅ [{idx}] 생성: {detail.id} - {problem["id"]}')
        else:
            updated_count += 1
            print(f'  🔄 [{idx}] 업데이트: {detail.id} - {problem["id"]}')

    # 4. 결과 요약
    print(f'\n{"="*60}')
    print(f'✨ 완료!')
    print(f'   - 신규 생성: {inserted_count}개')
    print(f'   - 업데이트: {updated_count}개')
    print(f'   - 총 처리: {inserted_count + updated_count}개')
    print(f'{"="*60}\n')

if __name__ == '__main__':
    try:
        print('🚀 Progressive Problems 데이터 삽입 시작...\n')
        insert_progressive_problems()
        print('✅ 모든 작업이 성공적으로 완료되었습니다!')
    except Exception as e:
        print(f'\n❌ 오류 발생: {str(e)}')
        import traceback
        traceback.print_exc()
        sys.exit(1)
