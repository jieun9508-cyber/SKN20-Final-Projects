"""
question_bank_view.py -- 면접 질문 뱅크 검색 REST API

생성일: 2026-03-01
설명: InterviewQuestion DB에서 조건에 맞는 면접 질문을 검색하는 API 엔드포인트.
      프론트엔드에서 기업/직무/슬롯별 질문 목록을 조회할 때 사용한다.

엔드포인트:
  GET /api/core/interview/questions/search/

쿼리 파라미터:
  - slot_type : 슬롯 유형 (technical, motivation, collaboration, problem_solving, growth, general)
  - company   : 기업명 (정확 매치 우선, 부족하면 범용 보충)
  - job       : 직무명 (부분 매치)
  - limit     : 최대 반환 개수 (기본 10, 최대 50)

응답 예시:
  {
      "count": 5,
      "questions": [
          {"id": 1, "question_text": "...", "slot_type": "technical", "company": "카카오", ...},
          ...
      ]
  }
"""
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny

from core.services.interview.question_bank_service import search_questions


class InterviewQuestionSearchView(APIView):
    """면접 질문 뱅크 검색 API

    GET /api/core/interview/questions/search/?slot_type=technical&company=카카오&limit=10
    """
    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request):
        """쿼리 파라미터로 면접 질문을 검색하여 반환한다."""
        slot_type = request.query_params.get('slot_type', None)
        company = request.query_params.get('company', '')
        job = request.query_params.get('job', '')

        # limit 파라미터 파싱 (기본 10, 최대 50)
        try:
            limit = int(request.query_params.get('limit', 10))
            limit = max(1, min(limit, 50))
        except (ValueError, TypeError):
            limit = 10

        # slot_type 유효성 검사
        valid_slot_types = ['technical', 'motivation', 'collaboration',
                            'problem_solving', 'growth', 'general']
        if slot_type and slot_type not in valid_slot_types:
            return Response(
                {'error': f'유효하지 않은 slot_type입니다. 가능한 값: {", ".join(valid_slot_types)}'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        questions = search_questions(
            slot_type=slot_type,
            company=company,
            job=job,
            limit=limit,
        )

        return Response({
            'count': len(questions),
            'questions': questions,
        }, status=status.HTTP_200_OK)
