# 수정내용: 코드 실행 샌드박스 및 활동/아바타 뷰 병합 (Antigravity)

from .user_view import UserProfileViewSet
from .dashboard_view import DashboardLogViewSet
from .common_view import CommonViewSet
from .practice_view import PracticeViewSet, PracticeDetailViewSet
from .auth_view import LoginView, LogoutView, SessionCheckView
from .bughunt.bughunt_evaluation_view import BugHuntEvaluationView
from .bughunt.bughunt_interview_view import BugHuntInterviewView
from .code_execution_view import CodeExecutionView, BehaviorVerificationView
from .management_view import OverallProgressView, UserAnswersView
from . import activity_view
from .ai_proxy_view import AIProxyView
from .pseudocode.pseudocode_execution import execute_python_code
from .pseudocode.pseudocode_agent_view import PseudocodeAgentView
from .architecture.architecture_view import ArchitectureEvaluationView, ArchitectureQuestionGeneratorView
from .ai_coach.coach_view import AICoachView
from .job_planner.job_planner_view import (
    JobPlannerParseView,
    JobPlannerAnalyzeView,
    JobPlannerCompanyAnalyzeView,
    JobPlannerAgentReportView,
    JobPlannerRecommendView,
    JobPlannerParseResumeView,
    JobPlannerGenerateCoverLetterView,
    JobPlannerReviewPortfolioView,
    JobPlannerCoverLetterByQuestionsView,
)
from .coduck_wars_view import (
    CoduckWarsAnalyzeCodeView,
    CoduckWarsStartView,
    CoduckWarsPressureView,
    CoduckWarsEvaluationView
)

# [수정일: 2026-02-26] 로그 뷰어 관리자 기능 추가
from .admin_views import (
    AdminLoginView,
    AdminLogView,
    AdminLogSaveView,
    AdminLogArchiveListView,
    AdminLogArchiveDetailView,
    AdminServerStatusView
)
