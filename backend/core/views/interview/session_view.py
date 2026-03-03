"""
session_view.py -- 모의면접 세션 CRUD API

수정일: 2026-03-01
설명:
  POST /api/core/interview/sessions/           -> 새 세션 생성 (첫 질문 포함)
  GET  /api/core/interview/sessions/           -> 세션 목록
  GET  /api/core/interview/sessions/<pk>/      -> 세션 상세

[2026-03-01 변경사항]
  - 세션 생성 시 question_bank_service에서 슬롯별 기출 질문을 가져와
    interview_plan["bank_questions"]에 저장. humanizer -> interviewer로 전달됨.
"""
import json
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny

from core.models import (
    UserProfile, SavedJobPosting,
    InterviewSession, InterviewTurn, InterviewFeedback
)
from core.services.interview.weakness_analyzer import analyze_user_weakness
from core.services.interview.plan_generator import generate_plan
from core.services.interview.state_engine import StateEngine
from core.services.interview.planner import decide_intent
from core.services.interview.humanizer import build_context
from core.services.interview.interviewer import generate_question_sync
# [2026-03-01] 면접 질문 뱅크 서비스 추가
from core.services.interview.question_bank_service import get_questions_for_session

engine = StateEngine()


def _get_user(request):
    """세션에서 UserProfile을 가져온다. 없으면 None."""
    from django.contrib.auth.models import User
    auth_user_id = request.session.get('_auth_user_id')
    if not auth_user_id:
        return None
    try:
        django_user = User.objects.get(pk=auth_user_id)
        return UserProfile.objects.get(email=django_user.email)
    except (User.DoesNotExist, UserProfile.DoesNotExist):
        return None


def _serialize_session(session) -> dict:
    plan = session.interview_plan or {}
    slots = plan.get('slots', [])
    total_slots = plan.get('total_slots', len(slots))

    # 슬롯 진행 상황 요약
    slot_progress = []
    for s in slots:
        slot_name = s.get('slot', '')
        state = session.slot_states.get(slot_name, {})
        slot_progress.append({
            'slot': slot_name,
            'topic': s.get('topic', slot_name),
            'status': state.get('status', 'UNKNOWN'),
        })

    return {
        'id': session.id,
        'status': session.status,
        'current_slot': session.current_slot,
        'current_turn': session.current_turn,
        'max_turns': session.max_turns,
        'total_slots': total_slots,
        'slot_progress': slot_progress,
        'job_posting': {
            'id': session.job_posting.id,
            'company_name': session.job_posting.company_name,
            'position': session.job_posting.position,
        } if session.job_posting else None,
        'started_at': session.started_at.isoformat() if session.started_at else None,
        'finished_at': session.finished_at.isoformat() if session.finished_at else None,
    }


@method_decorator(csrf_exempt, name='dispatch')
class InterviewSessionView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request):
        """사용자의 세션 목록 반환"""
        user = _get_user(request)
        if not user:
            return Response({'error': '로그인이 필요합니다.'}, status=status.HTTP_401_UNAUTHORIZED)

        sessions = InterviewSession.objects.filter(user=user).select_related('job_posting')
        data = [_serialize_session(s) for s in sessions]
        return Response(data, status=status.HTTP_200_OK)

    def post(self, request):
        """새 모의면접 세션 생성 + 첫 질문 반환"""
        user = _get_user(request)
        if not user:
            return Response({'error': '로그인이 필요합니다.'}, status=status.HTTP_401_UNAUTHORIZED)

        data = request.data
        job_posting_id = data.get('job_posting_id')

        # 채용공고 조회 (없으면 None으로 진행)
        job_posting = None
        if job_posting_id:
            try:
                job_posting = SavedJobPosting.objects.get(pk=job_posting_id, user=user)
            except SavedJobPosting.DoesNotExist:
                # [수정일: 2026-03-01]
                # 수정내용: 채용공고 조회가 실패(없는 ID 이거나 권한 없음)할 경우, 
                # 라우팅 오류(404 Not Found)와 혼동되지 않도록 400 Bad Request를 반환하고 
                # 명시적인 에러 메시지를 제공하도록 수정함.
                return Response(
                    {'error': f'채용공고(ID: {job_posting_id})를 찾을 수 없습니다. (삭제되었거나 내 공고가 아님)'},
                    status=status.HTTP_400_BAD_REQUEST
                )

        try:
            # 1. 사용자 취약점 분석
            user_weakness = analyze_user_weakness(user)

            # 1-1. 유저 프로필의 직무 역할 조회
            user_job_roles = []
            try:
                detail = user.user_detail
                user_job_roles = detail.job_role if isinstance(detail.job_role, list) else []
            except Exception:
                pass

            # 2. 면접 계획 생성
            interview_plan = generate_plan(job_posting, user_weakness, user_job_roles)

            # 2-1. [2026-03-01] DB에서 슬롯별 기출 질문을 가져와 interview_plan에 저장
            #      humanizer -> interviewer로 전달되어 기출 기반 면접 진행
            try:
                slot_types = [s["slot"] for s in interview_plan.get("slots", [])]
                company = job_posting.company_name if job_posting else ""
                job = job_posting.position if job_posting else ""
                print(f"\n{'='*60}")
                print(f"[기출 질문 조회] 기업: '{company}' | 직무: '{job}'")
                print(f"[기출 질문 조회] 슬롯: {slot_types}")
                bank_questions = get_questions_for_session(
                    company=company, job=job, slot_types=slot_types
                )
                interview_plan["bank_questions"] = bank_questions
                total = sum(len(qs) for qs in bank_questions.values())
                if total > 0:
                    print(f"[기출 질문 조회] ✅ 총 {total}개 기출 질문 로드 완료")
                    for slot_key, qs in bank_questions.items():
                        if qs:
                            print(f"  - {slot_key}: {len(qs)}개")
                            for q in qs[:3]:
                                print(f"    · {q.get('question_text', '')[:60]}")
                else:
                    print(f"[기출 질문 조회] ⚠️ 기출 질문 없음 (DB에 해당 기업/직무 데이터 없음)")
                print(f"{'='*60}\n")
            except Exception as e:
                print(f"[SessionView] 기출 질문 로드 실패 (무시): {e}")
                interview_plan["bank_questions"] = {}

            # 2-2. 유저 직무 정보를 interview_plan에 저장 (humanizer에서 참조)
            interview_plan["user_job_roles"] = user_job_roles

            # 3. 세션 생성
            session = InterviewSession.objects.create(
                user=user,
                job_posting=job_posting,
                interview_plan=interview_plan,
                slot_states={},
                current_slot='',
                current_turn=0,
                max_turns=data.get('max_turns', 20),
                status='in_progress',
                just_moved_slot=False,
                question_history=[],
            )

            # 4. slot_states 초기화
            slot_states = engine.initialize_slot_states(interview_plan)
            session.slot_states = slot_states

            # 5. 첫 슬롯 설정
            slots = interview_plan.get('slots', [])
            if not slots:
                session.delete()
                return Response({'error': '면접 계획 생성에 실패했습니다.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            first_slot_plan = slots[0]
            first_slot = first_slot_plan['slot']
            session.current_slot = first_slot
            session.just_moved_slot = False
            # current_turn=0 → humanizer가 is_first_question=True로 처리

            session.save()

            # 6. 첫 질문 생성 (L3 → L5 → L4 sync)
            required = session.get_slot_required(first_slot)
            intent_data = decide_intent(required, [])
            intent = intent_data['intent']

            ctx = build_context(session, first_slot_plan)
            ctx['is_first_question'] = True

            first_question = generate_question_sync(intent, ctx)

            # 7. current_turn 업데이트
            session.current_turn = 1
            session.question_history = [
                {'slot': first_slot, 'intent': intent, 'turn': 1}
            ]
            session.save()

            # 8. 첫 InterviewTurn 생성 (answer는 빈 문자열 — 사용자가 아직 답변 안 함)
            InterviewTurn.objects.create(
                session=session,
                turn_number=1,
                slot=first_slot,
                question=first_question,
                answer='',
                evidence_map={},
                slot_status_before='UNKNOWN',
                slot_status_after='UNKNOWN',
                engine_action='',
                intent=intent,
            )

            return Response({
                'session_id': session.id,
                'first_question': first_question,
                'current_slot': first_slot,
                'current_turn': 1,
                'total_slots': interview_plan.get('total_slots', len(slots)),
                'slot_info': {
                    'slot': first_slot,
                    'topic': first_slot_plan.get('topic', first_slot),
                },
            }, status=status.HTTP_201_CREATED)

        except Exception as e:
            import traceback
            import os
            try:
                base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
                with open(os.path.join(base_dir, 'error_traceback.txt'), 'w', encoding='utf-8') as f:
                    traceback.print_exc(file=f)
                    f.write(f"\n세션 생성 오류: {e}")
            except:
                pass
            print(f'[SessionView] 세션 생성 오류: {e}')
            return Response({'error': '세션 생성 중 오류가 발생했습니다.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@method_decorator(csrf_exempt, name='dispatch')
class InterviewSessionDetailView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request, pk):
        """세션 상세 조회 (슬롯 진행 상황 + 최신 질문)"""
        user = _get_user(request)
        if not user:
            return Response({'error': '로그인이 필요합니다.'}, status=status.HTTP_401_UNAUTHORIZED)

        try:
            session = InterviewSession.objects.select_related('job_posting').get(pk=pk, user=user)
        except InterviewSession.DoesNotExist:
            return Response({'error': '세션을 찾을 수 없습니다.'}, status=status.HTTP_404_NOT_FOUND)

        serialized = _serialize_session(session)

        # 현재 턴의 질문 (아직 답변 안 한 마지막 질문)
        pending_turn = session.turns.filter(answer='').order_by('-turn_number').first()
        serialized['current_question'] = pending_turn.question if pending_turn else ''

        # 전체 Q&A 턴 목록 (완료된 턴만 — answer 있는 것)
        completed_turns = session.turns.filter(answer__gt='').order_by('turn_number')
        serialized['turns'] = [
            {
                'turn_number': t.turn_number,
                'slot': t.slot,
                'question': t.question,
                'answer': t.answer,
                'slot_status_after': t.slot_status_after,
            }
            for t in completed_turns
        ]

        # 최종 피드백 (세션 완료 시)
        if session.status == 'completed':
            try:
                fb = session.feedback
                serialized['feedback'] = {
                    'overall_summary': fb.overall_summary,
                    'top_strengths': fb.top_strengths,
                    'top_improvements': fb.top_improvements,
                    'recommendation': fb.recommendation,
                    'slot_summary': fb.slot_summary,
                    'vision_analysis': fb.vision_analysis,
                    'vision_analysis': fb.vision_analysis,
                }
            except InterviewFeedback.DoesNotExist:
                serialized['feedback'] = None

        return Response(serialized, status=status.HTTP_200_OK)

    def delete(self, request, pk):
        """세션 삭제"""
        user = _get_user(request)
        if not user:
            return Response({'error': '로그인이 필요합니다.'}, status=status.HTTP_401_UNAUTHORIZED)

        try:
            session = InterviewSession.objects.get(pk=pk, user=user)
        except InterviewSession.DoesNotExist:
            return Response({'error': '세션을 찾을 수 없습니다.'}, status=status.HTTP_404_NOT_FOUND)

        session.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


@method_decorator(csrf_exempt, name='dispatch')
class InterviewVisionView(APIView):
    """PATCH /api/core/interview/sessions/<pk>/vision/ — 비전 분석 결과 저장"""
    authentication_classes = []
    permission_classes = [AllowAny]

    def patch(self, request, pk):
        user = _get_user(request)
        if not user:
            return Response({'error': '로그인이 필요합니다.'}, status=status.HTTP_401_UNAUTHORIZED)

        try:
            session = InterviewSession.objects.get(pk=pk, user=user, status='completed')
        except InterviewSession.DoesNotExist:
            return Response({'error': '완료된 세션을 찾을 수 없습니다.'}, status=status.HTTP_404_NOT_FOUND)

        try:
            fb = session.feedback
        except InterviewFeedback.DoesNotExist:
            return Response({'error': '피드백을 찾을 수 없습니다.'}, status=status.HTTP_404_NOT_FOUND)

        vision_data = request.data.get('vision_analysis')
        if vision_data is None:
            return Response({'error': 'vision_analysis 데이터가 없습니다.'}, status=status.HTTP_400_BAD_REQUEST)

        fb.vision_analysis = vision_data
        fb.save(update_fields=['vision_analysis'])
        return Response({'ok': True}, status=status.HTTP_200_OK)


@method_decorator(csrf_exempt, name='dispatch')
class InterviewVisionView(APIView):
    """PATCH /api/core/interview/sessions/<pk>/vision/ — 비전 분석 결과 저장"""
    authentication_classes = []
    permission_classes = [AllowAny]

    def patch(self, request, pk):
        user = _get_user(request)
        if not user:
            return Response({'error': '로그인이 필요합니다.'}, status=status.HTTP_401_UNAUTHORIZED)

        try:
            session = InterviewSession.objects.get(pk=pk, user=user, status='completed')
        except InterviewSession.DoesNotExist:
            return Response({'error': '완료된 세션을 찾을 수 없습니다.'}, status=status.HTTP_404_NOT_FOUND)

        try:
            fb = session.feedback
        except InterviewFeedback.DoesNotExist:
            return Response({'error': '피드백을 찾을 수 없습니다.'}, status=status.HTTP_404_NOT_FOUND)

        vision_data = request.data.get('vision_analysis')
        if vision_data is None:
            return Response({'error': 'vision_analysis 데이터가 없습니다.'}, status=status.HTTP_400_BAD_REQUEST)

        fb.vision_analysis = vision_data
        fb.save(update_fields=['vision_analysis'])
        return Response({'ok': True}, status=status.HTTP_200_OK)
