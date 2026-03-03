from django.urls import path, include
from rest_framework.routers import DefaultRouter
# core.views에서 필요한 뷰를 가져옵니다.
from core.views import (
    UserProfileViewSet,
    DashboardLogViewSet,
    CommonViewSet,
    PracticeViewSet,
    PracticeDetailViewSet,
    LoginView,
    LogoutView,
    SessionCheckView,
    AIProxyView,
    BugHuntEvaluationView,
    BugHuntInterviewView,
    CodeExecutionView,
    BehaviorVerificationView,
    OverallProgressView,
    UserAnswersView,
    activity_view,
    PseudocodeAgentView,
    JobPlannerParseView,
    JobPlannerAnalyzeView,
    JobPlannerCompanyAnalyzeView,
    JobPlannerAgentReportView,
    JobPlannerRecommendView,
    JobPlannerParseResumeView,
    JobPlannerGenerateCoverLetterView,
    JobPlannerReviewPortfolioView,
    JobPlannerCoverLetterByQuestionsView,
    CoduckWarsAnalyzeCodeView,
    CoduckWarsStartView,
    CoduckWarsPressureView,
    CoduckWarsEvaluationView,
    AdminLoginView,
    AdminLogView,
    AdminLogSaveView,
    AdminLogArchiveListView,
    AdminLogArchiveDetailView,
    AdminServerStatusView
)
from core.views.pseudocode.pseudocode_execution import execute_python_code
from core.views.pseudocode import pseudocode_evaluation
from core.views import youtube_recommendation
from core.views.architecture.architecture_view import ArchitectureEvaluationView, ArchitectureQuestionGeneratorView
from core.views.ai_coach.coach_view import AICoachView, CoachConversationView, CoachConversationDetailView
from core.views.interview import (
    InterviewVisionView,
    InterviewJobPostingView, InterviewJobPostingDetailView,
    InterviewSessionView, InterviewSessionDetailView, InterviewAnswerView,
    STTTranscribeView,
    TTSSynthesizeView,
    InterviewQuestionSearchView,    # 2026-03-01 면접 질문 뱅크 검색 API 추가
)

router = DefaultRouter()
router.register(r'users', UserProfileViewSet, basename='users')
router.register(r'dashboard-logs', DashboardLogViewSet)
router.register(r'commons', CommonViewSet)
router.register(r'practices', PracticeViewSet)
router.register(r'practice-details', PracticeDetailViewSet, basename='practice-details')

urlpatterns = [

    # 2. 인증 및 사용자 관리 API
    path('user/profile/', UserProfileViewSet.as_view({'get': 'list', 'post': 'create'})),

    # 3. 활동 및 리더보드 통합 API (AI-Arcade)
    path('activity/leaderboard/', activity_view.LeaderboardView.as_view(), name='leaderboard'),
    path('activity/progress/', activity_view.UserProgressView.as_view(), name='user_progress'),
    path('activity/solved-problems/', activity_view.UserSolvedProblemView.as_view(), name='solved_problems'),
    path('activity/submit/', activity_view.SubmitProblemView.as_view(), name='submit_problem'),
    path('activity/preview/', activity_view.AvatarPreviewView.as_view(), name='avatar_preview'),

    # 4. 일반 인증 관련
    path('auth/login/', LoginView.as_view(), name='login'),
    path('auth/logout/', LogoutView.as_view(), name='logout'),
    path('auth/me/', SessionCheckView.as_view(), name='session_check'),

    # 5. AI 평가 관련
    path('ai-proxy/', AIProxyView.as_view(), name='ai_proxy'),
    path('ai-bughunt-evaluate/', BugHuntEvaluationView.as_view(), name='bughunt_evaluate'),
    path('ai-bughunt-interview/', BugHuntInterviewView.as_view(), name='bughunt_interview'),

    # 6. 코드 실행 샌드박스 API
    path('execute-code/', CodeExecutionView.as_view(), name='execute_code'),
    path('verify-behavior/', BehaviorVerificationView.as_view(), name='verify_behavior'),

    # 7. 관리 및 기록 조회 API
    path('management/overall-progress/', OverallProgressView.as_view(), name='overall_progress'),
    path('management/user-answers/', UserAnswersView.as_view(), name='user_answers_all'),
    path('management/user-answers/<str:practice_id>/', UserAnswersView.as_view(), name='user_answers_practice'),
    path('management/user-answers/<str:practice_id>/<int:user_id>/', UserAnswersView.as_view(), name='user_answers_detail'),

    # 8. Pseudocode & YouTube API
    path('pseudocode/execute/', execute_python_code, name='pseudocode_execute'),
    path('pseudo-agent/', PseudocodeAgentView.as_view(), name='pseudo_agent'),
    path('pseudocode/evaluate-5d/', pseudocode_evaluation.evaluate_pseudocode_5d),
    path('youtube/recommendations', youtube_recommendation.get_youtube_recommendations),

    # 9. Architecture API
    path('architecture/evaluate/', ArchitectureEvaluationView.as_view(), name='architecture_evaluate'),
    path('architecture/generate-questions/', ArchitectureQuestionGeneratorView.as_view(), name='architecture_generate_questions'),

    # 10. AI Coach Agent API
    path('ai-coach/chat/', AICoachView.as_view(), name='ai_coach_chat'),
    path('ai-coach/chart-details/', AICoachView.as_view(), name='ai_coach_chart_details'),
    path('ai-coach/conversations/', CoachConversationView.as_view(), name='ai_coach_conversations'),
    path('ai-coach/conversations/<int:pk>/', CoachConversationDetailView.as_view(), name='ai_coach_conversation_detail'),

    # 11. 모의면접 API (STT/TTS 포함)
    path('interview/job-postings/', InterviewJobPostingView.as_view(), name='interview_job_postings'),
    path('interview/job-postings/<int:pk>/', InterviewJobPostingDetailView.as_view(), name='interview_job_posting_detail'),
    path('interview/sessions/', InterviewSessionView.as_view(), name='interview_sessions'),
    path('interview/sessions/<int:pk>/', InterviewSessionDetailView.as_view(), name='interview_session_detail'),
    path('interview/sessions/<int:pk>/answer/', InterviewAnswerView.as_view(), name='interview_answer'),
    path('interview/sessions/<int:pk>/vision/', InterviewVisionView.as_view(), name='interview_vision'),
    # [2026-03-01] 면접 질문 뱅크 검색 API
    path('interview/questions/search/', InterviewQuestionSearchView.as_view(), name='interview_question_search'),
    path('stt/transcribe/', STTTranscribeView.as_view(), name='stt_transcribe'),
    path('tts/synthesize/', TTSSynthesizeView.as_view(), name='tts_synthesize'),

    # 12. Job Planner API
    path('job-planner/parse/', JobPlannerParseView.as_view(), name='job_planner_parse'),
    path('job-planner/analyze/', JobPlannerAnalyzeView.as_view(), name='job_planner_analyze'),
    path('job-planner/company-analyze/', JobPlannerCompanyAnalyzeView.as_view(), name='job_planner_company_analyze'),
    path('job-planner/agent-report/', JobPlannerAgentReportView.as_view(), name='job_planner_agent_report'),
    path('job-planner/recommend/', JobPlannerRecommendView.as_view(), name='job_planner_recommend'),
    path('job-planner/parse-resume/', JobPlannerParseResumeView.as_view(), name='job_planner_parse_resume'),
    path('job-planner/generate-cover-letter/', JobPlannerGenerateCoverLetterView.as_view(), name='job_planner_generate_cover_letter'),
    path('job-planner/review-portfolio/', JobPlannerReviewPortfolioView.as_view(), name='job_planner_review_portfolio'),
    path('job-planner/generate-cover-letter-by-questions/', JobPlannerCoverLetterByQuestionsView.as_view(), name='job_planner_cover_letter_by_questions'),

    # 13. Coduck Wars API
    path('wars/analyze-code/', CoduckWarsAnalyzeCodeView.as_view(), name='wars_analyze_code'),
    path('wars/start/', CoduckWarsStartView.as_view(), name='wars_start'),
    path('wars/pressure-question/', CoduckWarsPressureView.as_view(), name='wars_pressure_question'),
    path('wars/evaluate/', CoduckWarsEvaluationView.as_view(), name='wars_evaluate'),
    
    # [수정일: 2026-02-26] 관리자 로그 뷰어 API 추가
    path('admin/login/', AdminLoginView.as_view(), name='admin_login'),
    path('admin/logs/', AdminLogView.as_view(), name='admin_logs'),
    path('admin/logs/save/', AdminLogSaveView.as_view(), name='admin_logs_save'),
    path('admin/logs/archives/', AdminLogArchiveListView.as_view(), name='admin_logs_archives'),
    path('admin/logs/archives/<str:filename>/', AdminLogArchiveDetailView.as_view(), name='admin_logs_archive_detail'),
    path('admin/server-status/', AdminServerStatusView.as_view(), name='admin_server_status'),
]


# [추가: 2026-02-26] Router 등록 (practices, users 등 ViewSet 기반 엔드포인트)
urlpatterns += router.urls
