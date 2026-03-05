# job_planner_view.py
"""
Job Planner Agent - Django REST API
원본 v3.1 기반 - URL 크롤링 및 이미지 OCR 지원
"""
import os
import json
import base64
import traceback
from django.conf import settings

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator

# 외부 라이브러리
try:
    import requests
    from bs4 import BeautifulSoup
    import openai
    CRAWLER_AVAILABLE = True
except ImportError:
    CRAWLER_AVAILABLE = False

def _embed_texts(texts: list):
    """
    텍스트 리스트를 OpenAI 임베딩 벡터로 변환 후 L2 정규화하여 반환.

    Args:
        texts (list): 임베딩할 문자열 리스트

    Returns:
        np.ndarray: shape (n, dim) — L2 정규화된 float32 벡터 행렬.
                    코사인 유사도를 내적(dot product)으로 계산할 수 있게 단위 벡터로 변환됨.
    """
    import numpy as np
    import openai as _openai

    # 환경변수에서 OpenAI API 키를 읽어 클라이언트 생성
    client = _openai.OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

    # text-embedding-3-small 모델로 배치 임베딩 요청
    # 여러 텍스트를 한 번의 API 호출로 처리 (비용·속도 효율)
    response = client.embeddings.create(model="text-embedding-3-small", input=texts)

    # API 응답은 순서가 보장되지 않을 수 있으므로 index 기준으로 정렬 후 벡터 추출
    vectors = [item.embedding for item in sorted(response.data, key=lambda x: x.index)]

    # Python list -> float32 numpy 배열로 변환 (shape: n x dim)
    arr = np.array(vectors, dtype=np.float32)

    # 각 벡터의 L2 norm(크기) 계산, keepdims=True로 브로드캐스팅 가능하게 유지 (shape: n x 1)
    norms = np.linalg.norm(arr, axis=1, keepdims=True)

    # 각 벡터를 norm으로 나눠 단위 벡터로 정규화
    # np.maximum(norms, 1e-8): norm이 0인 제로 벡터일 때 division by zero 방지
    return arr / np.maximum(norms, 1e-8)


@method_decorator(csrf_exempt, name='dispatch')
class JobPlannerParseView(APIView):
    """
    채용공고 파싱 API
    - URL 크롤링
    - 이미지 OCR (OpenAI Vision)
    - 텍스트 직접 입력
    """
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        input_type = request.data.get('type')  # 'url', 'image', 'text'

        try:
            if input_type == 'url':
                return self._parse_from_url(request)
            elif input_type == 'image':
                return self._parse_from_image(request)
            elif input_type == 'text':
                return self._parse_from_text(request)
            else:
                return Response({
                    "error": "Invalid input type. Use 'url', 'image', or 'text'."
                }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            print(f"❌ Parse 에러: {e}")
            print(traceback.format_exc())
            return Response({
                "error": f"파싱 중 오류 발생: {str(e)}"
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def _parse_from_url(self, request):
        """
        URL 크롤링으로 채용공고 파싱 (Collector 시스템 사용)

        Collector 레이어를 통해 채용공고 텍스트를 수집한 후,
        LLM으로 구조화된 정보를 파싱합니다.

        Collector 시스템 단계별 설명:
        - Phase 1: StaticCollector (requests + BeautifulSoup)
          -> 정적 HTML 페이지 크롤링 (서버에서 완성된 HTML을 반환하는 사이트)
        - Phase 2+: BrowserCollector, ApiCollector 추가 예정
          -> BrowserCollector: JavaScript로 렌더링되는 SPA 사이트 크롤링 (Selenium/Playwright)
          -> ApiCollector: 채용 사이트 공식 API를 통한 데이터 수집

        Args:
            request: URL이 포함된 HTTP 요청 객체

        Returns:
            Response: 파싱된 채용공고 정보 (JSON)
        """
        if not CRAWLER_AVAILABLE:
            return Response({
                "error": "크롤링 라이브러리가 설치되지 않았습니다."
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        url = request.data.get('url')
        if not url:
            return Response({
                "error": "URL이 필요합니다."
            }, status=status.HTTP_400_BAD_REQUEST)

        try:
            # === Collector 시스템으로 텍스트 수집 ===
            from .collectors import CollectorRouter

            router = CollectorRouter()
            text = router.collect_with_fallback(url)

            # 텍스트가 너무 짧으면 경고
            if len(text) < 100:
                print(f"⚠️  추출된 텍스트가 짧습니다 ({len(text)}자). SPA 사이트일 수 있습니다.")

            # LLM으로 구조화된 채용공고 정보 추출
            parsed_data = self._extract_job_info_with_llm(text, source='url')

            # 파싱 결과 SavedJobPosting에 저장
            saved_id = self._save_job_posting(request, parsed_data, source='url', source_url=url)
            if saved_id:
                parsed_data['saved_posting_id'] = saved_id

            return Response(parsed_data, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({
                "error": f"URL 파싱 실패: {str(e)}"
            }, status=status.HTTP_400_BAD_REQUEST)

    def _parse_from_image(self, request):
        """이미지 OCR로 채용공고 파싱 (OpenAI Vision)"""
        image_data = request.data.get('image')  # base64 encoded
        if not image_data:
            return Response({
                "error": "이미지 데이터가 필요합니다."
            }, status=status.HTTP_400_BAD_REQUEST)

        api_key = os.getenv('OPENAI_API_KEY')
        if not api_key:
            return Response({
                "error": "OPENAI_API_KEY가 설정되지 않았습니다."
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        try:
            client = openai.OpenAI(api_key=api_key)

            # Vision API 호출
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": """당신은 IT 채용공고 이미지 분석 전문가입니다.
이미지에서 채용공고 정보를 정확하게 추출하여 JSON 형식으로 반환하세요.

🎯 **핵심 미션**: required_skills와 preferred_skills 배열을 최대한 많이 추출하는 것이 가장 중요합니다!

## 추출 정보:
1. 회사명과 포지션
2. 주요 업무 (담당할 업무, 하게 될 일, 담당 업무)
3. 필수 요건 (자격 요건, 필수 조건) - **원문 그대로**
4. 우대 조건 (우대 사항, 플러스 요소) - **원문 그대로**
5. **기술 스택 (가장 중요!)** - 프로그래밍 언어, 프레임워크, 도구, DB, 클라우드 등 모두 추출

## 기술 스택 추출 가이드:
이미지 텍스트에서 다음 **모든** 기술을 찾아 배열로 추출하세요:

### 언어
- Python, Java, JavaScript, TypeScript, C++, C#, Go, Kotlin, Swift, Ruby, PHP, Rust, Scala 등
- 한글: 파이썬, 자바, 자바스크립트, 타입스크립트 -> 영문으로 변환

### 프레임워크/라이브러리
- Django, Flask, FastAPI, Spring, SpringBoot, React, Vue, Angular, Next.js, Node.js, Express 등
- 한글: 장고, 플라스크, 스프링, 리액트, 뷰 -> 영문으로 변환

### 데이터베이스
- MySQL, PostgreSQL, MongoDB, Redis, Oracle, MariaDB, Elasticsearch 등

### 클라우드/인프라
- AWS, Azure, GCP, Docker, Kubernetes, Jenkins, Linux, Nginx 등

### AI/ML/데이터
- TensorFlow, PyTorch, Pandas, NumPy, Spark, Kafka 등

### 도구
- Git, GitHub, GitLab, Jira, Figma, Postman 등

## 추출 규칙:
1. **문장에서도 기술 추출**: "Python과 Django를 활용한 백엔드 개발" -> ["Python", "Django"]
2. **리스트 형태도 추출**: "• Python\n• Django\n• PostgreSQL" -> ["Python", "Django", "PostgreSQL"]
3. **쉼표 구분도 추출**: "Python, Django, React 경험자" -> ["Python", "Django", "React"]
4. **한글을 영문으로**: "파이썬" -> "Python", "장고" -> "Django"
5. **버전 제거**: "Python 3.x" -> "Python", "Django 4.0" -> "Django"
6. **기술이 아닌 것 제외**: "팀워크", "성실성", "커뮤니케이션", "책임감" 등은 제외
7. **최소 3개 이상** 추출 (있다면 최대한 많이)

## position 추출 규칙:
- 이미지에 직무명/포지션이 명시되어 있으면 그대로 사용 (예: "백엔드 개발자", "AI 엔지니어")
- 명시되어 있지 않으면 업무내용과 요구 기술을 바탕으로 적절한 직무명을 추론 (예: Python/Django 백엔드 -> "백엔드 개발자", React/Vue 프론트 -> "프론트엔드 개발자", ML/DL 관련 -> "AI 엔지니어")

## JSON 형식:
{
  "company_name": "회사명",
  "position": "직무명 (예: 백엔드 개발자, AI 엔지니어, 데이터 분석가)",
  "job_responsibilities": "주요 업무 내용 (원문 그대로, 줄바꿈 포함)",
  "required_qualifications": "필수 자격 요건 (원문 그대로, 줄바꿈 포함)",
  "preferred_qualifications": "우대 사항 (원문 그대로, 줄바꿈 포함)",
  "required_skills": ["Python", "Django", "PostgreSQL", "..."],
  "preferred_skills": ["Docker", "AWS", "..."],
  "experience_range": "신입/경력 (예: 신입, 2-4년, 5년 이상)",
  "deadline": "YYYY-MM-DD 또는 null"
}

## 예시:
입력 텍스트: "Python, Django를 활용한 백엔드 개발 경험 3년 이상. PostgreSQL 또는 MySQL 사용 경험. Docker 및 AWS 경험자 우대"
출력:
{
  "required_skills": ["Python", "Django", "PostgreSQL", "MySQL"],
  "preferred_skills": ["Docker", "AWS"]
}

⚠️ **중요**: required_skills와 preferred_skills 배열을 절대 비워두지 마세요! 이미지에서 기술 스택을 최대한 찾아내세요!"""
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": image_data  # data:image/jpeg;base64,... 형식
                                }
                            }
                        ]
                    }
                ],
                max_tokens=3000,  # 2000 -> 3000 (더 많은 정보 추출)
                temperature=0.2   # 0.3 -> 0.2 (더 정확한 추출)
            )

            content = response.choices[0].message.content

            # JSON 추출
            try:
                # JSON 코드 블록 제거
                if '```json' in content:
                    content = content.split('```json')[1].split('```')[0].strip()
                elif '```' in content:
                    content = content.split('```')[1].split('```')[0].strip()

                parsed_data = json.loads(content)
                parsed_data['source'] = 'image'
                parsed_data['raw_text'] = ''

                # 파싱 결과 SavedJobPosting에 저장
                saved_id = self._save_job_posting(request, parsed_data, source='image', source_url='')
                if saved_id:
                    parsed_data['saved_posting_id'] = saved_id

                return Response(parsed_data, status=status.HTTP_200_OK)
            except json.JSONDecodeError:
                return Response({
                    "error": "이미지에서 채용공고 정보를 추출할 수 없습니다.",
                    "raw_response": content
                }, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            return Response({
                "error": f"Vision API 오류: {str(e)}"
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def _parse_from_text(self, request):
        """텍스트에서 채용공고 파싱"""
        text = request.data.get('text')
        if not text:
            return Response({
                "error": "텍스트가 필요합니다."
            }, status=status.HTTP_400_BAD_REQUEST)

        parsed_data = self._extract_job_info_with_llm(text, source='text')

        # 파싱 결과 SavedJobPosting에 저장
        saved_id = self._save_job_posting(request, parsed_data, source='text', source_url='')
        if saved_id:
            parsed_data['saved_posting_id'] = saved_id

        return Response(parsed_data, status=status.HTTP_200_OK)

    def _save_job_posting(self, request, parsed_data: dict, source: str, source_url: str) -> int | None:
        """
        파싱된 채용공고를 SavedJobPosting에 저장한다.
        세션에 user_id가 없으면 저장하지 않는다.
        동일 사용자 + 동일 URL -> update_or_create (중복 저장 방지)

        Returns:
            저장된 SavedJobPosting의 id (실패 시 None)
        """
        try:
            from core.models import SavedJobPosting, UserProfile

            # 세션에서 auth user 추출 -> email로 UserProfile 조회
            from django.contrib.auth.models import User
            auth_user_id = request.session.get('_auth_user_id')
            if not auth_user_id:
                return None

            django_user = User.objects.get(pk=auth_user_id)
            user = UserProfile.objects.get(email=django_user.email)

            defaults = {
                'company_name': parsed_data.get('company_name', ''),
                'position': parsed_data.get('position', ''),
                'job_responsibilities': parsed_data.get('job_responsibilities', ''),
                'required_qualifications': parsed_data.get('required_qualifications', ''),
                'preferred_qualifications': parsed_data.get('preferred_qualifications', ''),
                'required_skills': parsed_data.get('required_skills', []),
                'preferred_skills': parsed_data.get('preferred_skills', []),
                'experience_range': parsed_data.get('experience_range', ''),
                'deadline': parsed_data.get('deadline'),
                'source': source,
                'raw_text': parsed_data.get('raw_text', ''),
                'parsed_data': {k: v for k, v in parsed_data.items()
                                if k not in ('saved_posting_id',)},
            }

            if source == 'url' and source_url:
                saved, _ = SavedJobPosting.objects.update_or_create(
                    user=user, source_url=source_url, defaults=defaults
                )
            else:
                defaults['source_url'] = ''
                saved = SavedJobPosting.objects.create(user=user, **defaults)

            return saved.id

        except Exception as e:
            print(f"[JobPlanner] SavedJobPosting 저장 실패: {e}")
            return None

    def _extract_job_info_with_llm(self, text, source='text'):
        """
        LLM으로 채용공고 정보 추출

        비정형 텍스트에서 OpenAI GPT를 사용하여 구조화된 채용공고 정보를 추출합니다.
        회사명, 포지션, 업무 내용, 필수/우대 요건, 기술 스택 등을 JSON 형태로 변환합니다.

        Args:
            text (str): 채용공고 원문 텍스트
            source (str): 데이터 출처 ('url', 'text', 'image')

        Returns:
            dict: 구조화된 채용공고 정보
        """
        print(f"\n📄 [LLM 파싱] 입력 텍스트 ({len(text)}자)")
        print(f"   앞 500자: {text[:500]}")

        api_key = os.getenv('OPENAI_API_KEY')
        if not api_key:
            # Fallback: API 키가 없을 때 기본 응답 반환
            return {
                "source": source,
                "raw_text": text,
                "company_name": "알 수 없음",
                "position": "개발자",
                "job_responsibilities": text[:200] if len(text) > 200 else text,
                "required_qualifications": "정보 없음",
                "preferred_qualifications": "정보 없음",
                "required_skills": [],
                "preferred_skills": [],
                "experience_range": "",
                "deadline": None
            }

        try:
            client = openai.OpenAI(api_key=api_key)

            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": """당신은 채용공고 파싱 전문가입니다.
아래 규칙을 반드시 따르세요:
1. 텍스트에 실제로 존재하는 정보만 추출한다.
2. 텍스트에 없는 정보는 절대 만들어내지 마라. 없으면 빈 문자열("") 또는 빈 배열([])로 반환한다.
3. 반드시 JSON만 출력한다."""
                    },
                    {
                        "role": "user",
                        "content": f"""다음 채용공고 텍스트에서 정보를 추출하세요.

{text[:15000]}

위 텍스트를 바탕으로 아래 JSON 키를 채우세요. 텍스트에 없는 정보는 "" 또는 []로 두세요:
- company_name: string
- position: string (직무명이 명시되어 있으면 그대로, 없으면 업무내용/요구기술로 추론. 예: "백엔드 개발자", "AI 엔지니어")
- job_responsibilities: string
- required_qualifications: string (필수 요건 원문)
- preferred_qualifications: string (우대 조건 원문)
- required_skills: array of strings (필수 요건에서 언급된 기술/도구명만 추출. 예: "React", "Python", "Docker")
- preferred_skills: array of strings (우대 조건에서 언급된 기술/도구/분야명을 모두 추출. 문장 속에 포함된 기술명도 반드시 추출. 예: "Typescript 기반 프로젝트 경험" -> "Typescript")
- responsibilities_skills: array of strings (담당업무/주요업무에서 언급된 기술/도구/분야명을 추출. 예: "AI", "XR", "Vision", "Computer Vision")
- experience_range: string
- deadline: null"""
                    }
                ],
                response_format={"type": "json_object"},
                temperature=0.2,
                max_tokens=2000,
            )

            content = response.choices[0].message.content

            # JSON 추출
            if '```json' in content:
                content = content.split('```json')[1].split('```')[0].strip()
            elif '```' in content:
                content = content.split('```')[1].split('```')[0].strip()

            parsed_data = json.loads(content)
            parsed_data['source'] = source
            parsed_data['raw_text'] = text

            # 파싱 결과 로그 출력
            print(f"\n✅ [LLM 파싱 완료]")
            print(f"   회사명: {parsed_data.get('company_name', '없음')}")
            print(f"   포지션: {parsed_data.get('position', '없음')}")
            print(f"   필수 스킬: {len(parsed_data.get('required_skills', []))}개 - {parsed_data.get('required_skills', [])}")
            print(f"   우대 스킬: {len(parsed_data.get('preferred_skills', []))}개 - {parsed_data.get('preferred_skills', [])}")
            print(f"   주요 업무: {len(parsed_data.get('job_responsibilities', ''))}자 - {parsed_data.get('job_responsibilities', '')[:100]}...")
            print(f"   필수 요건: {len(parsed_data.get('required_qualifications', ''))}자 - {parsed_data.get('required_qualifications', '')[:100]}...")

            return parsed_data

        except Exception as e:
            print(f"⚠️  LLM 파싱 실패: {e}")
            # Fallback
            return {
                "source": source,
                "raw_text": text,
                "company_name": "알 수 없음",
                "position": "개발자",
                "job_responsibilities": text[:200] if len(text) > 200 else text,
                "required_qualifications": "정보 없음",
                "preferred_qualifications": "정보 없음",
                "required_skills": [],
                "preferred_skills": [],
                "experience_range": "",
                "deadline": None
            }


@method_decorator(csrf_exempt, name='dispatch')
class JobPlannerAnalyzeView(APIView):
    """
    스킬 매칭 분석 API

    사용자의 스킬셋과 채용공고의 요구 스킬을 비교 분석하여
    준비도 점수, 스킬 갭, 매칭 정보 등을 제공합니다.

    주요 기능:
    1. LLM 기반 스킬 매칭 (동일 기술·대체 가능 기술·생태계 연관 기술 판단)
    2. 한영 스킬 정규화 (예: "파이썬" -> "python")
    3. 준비도 점수 계산 (매칭률 + 경력 적합도 + 숙련도)
    4. 맞춤형 인사이트 생성
    """
    authentication_classes = []
    permission_classes = [AllowAny]

    # 한영 스킬 동의어 사전
    # 다양한 표기를 통일된 형태로 정규화하기 위한 매핑 테이블
    # 예: "파이썬", "Python", "python" -> 모두 "python"으로 통일
    # 참고: 'python': 'python' 같은 중복은 불필요 (_normalize_skill에서 자동 처리)
    SKILL_SYNONYMS = {
        # 프로그래밍 언어
        '파이썬': 'python',
        '자바': 'java',
        '자바스크립트': 'javascript', 'js': 'javascript',
        '타입스크립트': 'typescript', 'ts': 'typescript',
        'c++': 'cpp', '씨쁠쁠': 'cpp',
        'c#': 'csharp', '씨샵': 'csharp', '씨샤프': 'csharp',
        '고': 'go', 'golang': 'go',
        '코틀린': 'kotlin',
        '스위프트': 'swift',
        '루비': 'ruby',
        '러스트': 'rust',
        '스칼라': 'scala',
        'php': 'php', '피에이치피': 'php',
        '다트': 'dart',
        '펄': 'perl',

        # 웹 프레임워크
        '장고': 'django',
        '플라스크': 'flask',
        '패스트에이피아이': 'fastapi', 'fast api': 'fastapi',
        '스프링': 'spring',
        '스프링부트': 'springboot', 'spring boot': 'springboot', '스프링 부트': 'springboot',
        '리액트': 'react', 'reactjs': 'react', 'react.js': 'react',
        '뷰': 'vue', 'vuejs': 'vue', 'vue.js': 'vue',
        '앵귤러': 'angular', 'angularjs': 'angular',
        '노드': 'node', 'nodejs': 'node', 'node.js': 'node',
        '익스프레스': 'express', 'expressjs': 'express', 'express.js': 'express',
        '넥스트': 'next', 'nextjs': 'next', 'next.js': 'next',
        '넥스트제이에스': 'next', '넥스트js': 'next',
        '네스트': 'nestjs', 'nestjs': 'nestjs', 'nest.js': 'nestjs', '네스트제이에스': 'nestjs',
        '넉스트': 'nuxtjs', 'nuxtjs': 'nuxtjs', 'nuxt.js': 'nuxtjs',
        '스벨트': 'svelte',
        '플러터': 'flutter',
        '라라벨': 'laravel',
        '레일즈': 'rails', 'ruby on rails': 'rails',
        '하이버네이트': 'hibernate',
        '마이바티스': 'mybatis',

        # 데이터 분석/과학 라이브러리
        '판다스': 'pandas',
        '넘파이': 'numpy',
        '맷플롯립': 'matplotlib',
        '사이킷런': 'sklearn', 'scikit-learn': 'sklearn',
        '엑스지부스트': 'xgboost',
        '라이트지비엠': 'lightgbm',
        '오픈cv': 'opencv', 'open cv': 'opencv',
        '엔엘티케이': 'nltk',
        '스페이시': 'spacy',

        # 데이터베이스
        '마이에스큐엘': 'mysql',
        '포스트그레': 'postgresql', 'postgres': 'postgresql', 'postgre sql': 'postgresql',
        '몽고디비': 'mongodb', 'mongo': 'mongodb',
        '레디스': 'redis',
        '오라클': 'oracle',
        '마리아디비': 'mariadb',
        '에스큐엘서버': 'mssql', 'sql server': 'mssql', 'sqlserver': 'mssql',
        '에스큐엘라이트': 'sqlite',
        '엘라스틱서치': 'elasticsearch', '엘라스틱': 'elasticsearch',
        '크로마': 'chromadb', 'chroma': 'chromadb', 'chroma db': 'chromadb',
        '파인콘': 'pinecone',
        '카산드라': 'cassandra',
        '다이나모디비': 'dynamodb', 'dynamo db': 'dynamodb',
        '파이어베이스': 'firebase',
        '수파베이스': 'supabase',

        # 클라우드/인프라
        '아마존웹서비스': 'aws', 'amazon web services': 'aws',
        '애저': 'azure', 'microsoft azure': 'azure',
        '구글클라우드': 'gcp', 'google cloud': 'gcp', 'google cloud platform': 'gcp',
        '도커': 'docker',
        '쿠버네티스': 'kubernetes', 'k8s': 'kubernetes',
        '테라폼': 'terraform',
        '앤서블': 'ansible',
        '젠킨스': 'jenkins',
        '깃허브액션스': 'githubactions', 'github actions': 'githubactions',
        '엔진엑스': 'nginx',
        '아파치': 'apache',
        '리눅스': 'linux',
        '우분투': 'ubuntu',
        '카프카': 'kafka', 'apache kafka': 'kafka',
        '래빗엠큐': 'rabbitmq', 'rabbit mq': 'rabbitmq',

        # AI/ML
        '텐서플로': 'tensorflow', '텐서플로우': 'tensorflow',
        '파이토치': 'pytorch',
        '케라스': 'keras',
        '랭체인': 'langchain',
        '허깅페이스': 'huggingface', 'hugging face': 'huggingface',
        '트랜스포머': 'transformers',

        # 도구
        '깃': 'git',
        '깃허브': 'github',
        '깃랩': 'gitlab',
        '지라': 'jira',
        '컨플루언스': 'confluence',
        '노션': 'notion',
        '슬랙': 'slack',
        '포스트맨': 'postman',
        '피그마': 'figma',
        '태블로': 'tableau',
        '파워비아이': 'powerbi', 'power bi': 'powerbi',
        '그라파나': 'grafana',
        '키바나': 'kibana',
    }

    def _normalize_skill(self, skill):
        """
        스킬명을 정규화 (한글->영어, 소문자 변환)

        동의어 사전을 사용하여 다양한 표기를 통일된 형태로 변환합니다.
        예: "파이썬" -> "python", "장고" -> "django", "JS" -> "javascript"

        Args:
            skill (str): 원본 스킬명

        Returns:
            str: 정규화된 스킬명 (소문자)
        """
        skill_lower = skill.lower().strip()
        return self.SKILL_SYNONYMS.get(skill_lower, skill_lower)

    def _extract_skills_from_text(self, required_text, preferred_text, responsibilities_text):
        """
        필수/우대 요건 및 업무 텍스트에서 기술 스택과 역량을 추출
        - 정규식 패턴 매칭으로 빠르게 추출
        - LLM 없이도 작동하도록 구현
        """
        import re

        # 전체 텍스트 결합
        full_text = f"{required_text} {preferred_text} {responsibilities_text}"

        # 알려진 기술 스택 키워드 (대소문자 구분 없이)
        tech_keywords = [
            # 언어
            'Python', 'Java', 'JavaScript', 'TypeScript', 'C++', 'C#', 'Go', 'Kotlin',
            'Swift', 'Ruby', 'PHP', 'Rust', 'Scala', 'R',
            '파이썬', '자바', '자바스크립트', '타입스크립트', '코틀린',

            # 프레임워크
            'Django', 'Flask', 'FastAPI', 'Spring', 'SpringBoot', 'React', 'Vue',
            'Angular', 'Next.js', 'Nuxt', 'Express', 'Node.js', 'Nest.js',
            '장고', '플라스크', '스프링', '리액트', '뷰', '앵귤러', '노드',

            # 데이터베이스
            'MySQL', 'PostgreSQL', 'MongoDB', 'Redis', 'Oracle', 'MariaDB',
            'SQLite', 'Elasticsearch', 'DynamoDB', 'Cassandra',
            '마이에스큐엘', '몽고디비', '레디스', '오라클',

            # 클라우드/인프라
            'AWS', 'Azure', 'GCP', 'Docker', 'Kubernetes', 'Jenkins', 'GitLab CI',
            'Terraform', 'Ansible', 'Linux', 'Nginx', 'Apache',
            '도커', '쿠버네티스', '리눅스',

            # AI/ML/Data
            'TensorFlow', 'PyTorch', 'Keras', 'scikit-learn', 'Pandas', 'NumPy',
            'Spark', 'Hadoop', 'Airflow', 'Kafka',
            '텐서플로', '파이토치',

            # 도구
            'Git', 'GitHub', 'GitLab', 'Jira', 'Confluence', 'Slack', 'Notion',
            'Figma', 'Postman', 'Swagger',
            '깃', '깃허브', '지라',

            # 방법론/개념
            'Agile', 'Scrum', 'Kanban', 'CI/CD', 'DevOps', 'TDD', 'DDD',
            'Microservices', 'REST', 'GraphQL', 'gRPC', 'WebSocket',
            '애자일', '스크럼', '칸반', '마이크로서비스'
        ]

        found_skills = []

        # 각 키워드가 텍스트에 있는지 확인 (단어 경계 고려)
        for keyword in tech_keywords:
            # 대소문자 구분 없이, 단어 경계를 고려한 검색
            pattern = r'\b' + re.escape(keyword) + r'\b'
            if re.search(pattern, full_text, re.IGNORECASE):
                # 이미 추가되지 않았으면 추가
                normalized = self._normalize_skill(keyword)
                if normalized not in [self._normalize_skill(s) for s in found_skills]:
                    found_skills.append(keyword)

        # 필수와 우대 구분 (간단한 휴리스틱)
        required_found = []
        preferred_found = []

        for skill in found_skills:
            # 필수 요건 텍스트에 있으면 필수로 분류
            pattern = r'\b' + re.escape(skill) + r'\b'
            if re.search(pattern, required_text, re.IGNORECASE):
                required_found.append(skill)
            elif re.search(pattern, preferred_text, re.IGNORECASE):
                preferred_found.append(skill)
            else:
                # 업무 내용에만 있으면 필수로 간주
                required_found.append(skill)

        return {
            'required': required_found,
            'preferred': preferred_found
        }

    def post(self, request):
        try:
            # 기본 프로필
            user_skills = request.data.get('user_skills', [])
            skill_levels = request.data.get('skill_levels', {})  # {"Python": 4, "Django": 3}
            experience_years = int(request.data.get('experience_years', 0))

            # 상세 프로필 (선택사항)
            name = request.data.get('name', '지원자')
            current_role = request.data.get('current_role', '')
            education = request.data.get('education', '')
            certifications = request.data.get('certifications', [])
            training = request.data.get('training', [])
            career_goals = request.data.get('career_goals', '')
            available_prep_days = request.data.get('available_prep_days', None)

            # 이력서 경력 사항 (관련 경력 연수 추출용)
            work_experience = request.data.get('work_experience', [])

            # 채용공고 정보
            required_skills = request.data.get('required_skills', [])
            preferred_skills = request.data.get('preferred_skills', [])
            responsibilities_skills = request.data.get('responsibilities_skills', [])
            experience_range = request.data.get('experience_range', '')
            position = request.data.get('position', '')

            # 필수/우대 요건 전체 텍스트 (추가 역량 추출용)
            required_qualifications = request.data.get('required_qualifications', '')
            preferred_qualifications = request.data.get('preferred_qualifications', '')
            job_responsibilities = request.data.get('job_responsibilities', '')

            if not user_skills:
                return Response({
                    "error": "사용자 스킬 정보가 필요합니다."
                }, status=status.HTTP_400_BAD_REQUEST)

            # 필수 요건 텍스트에서 추가 스킬/역량 추출
            extracted_skills = self._extract_skills_from_text(
                required_qualifications,
                preferred_qualifications,
                job_responsibilities
            )

            # 기존 스킬 배열과 추출된 스킬 결합 (중복 제거)
            all_required_skills = list(set(required_skills + extracted_skills['required']))
            all_preferred_skills = list(set(preferred_skills + extracted_skills['preferred']))

            # 세 카테고리 모두 없을 때만 fallback
            if not all_required_skills and not responsibilities_skills and not all_preferred_skills:
                all_required_skills = extracted_skills['required'] if extracted_skills['required'] else ['개발 역량']

            print(f"📊 담당업무 스킬: {len(responsibilities_skills)}개")
            print(f"📊 필수 스킬: {len(required_skills)}개 -> {len(all_required_skills)}개 (텍스트 분석 추가)")
            print(f"📊 우대 스킬: {len(preferred_skills)}개 -> {len(all_preferred_skills)}개 (텍스트 분석 추가)")

            # === LLM 기반 스킬 매칭 (담당업무 + 필수 + 우대 통합, category 태그) ===
            combined_skills = []
            skill_category_map = {}
            for s in responsibilities_skills:
                norm = self._normalize_skill(s)
                if norm not in skill_category_map:
                    combined_skills.append(s)
                    skill_category_map[norm] = 'responsibilities'
            for s in all_required_skills:
                norm = self._normalize_skill(s)
                if norm not in skill_category_map:
                    combined_skills.append(s)
                    skill_category_map[norm] = 'required'
            for s in all_preferred_skills:
                norm = self._normalize_skill(s)
                if norm not in skill_category_map:
                    combined_skills.append(s)
                    skill_category_map[norm] = 'preferred'

            matched_skills, missing_skills = self._match_skills_with_llm(
                combined_skills, user_skills
            )

            # 매칭/미매칭 결과에 category 태그 추가
            for m in matched_skills:
                norm = self._normalize_skill(m['required'])
                m['category'] = skill_category_map.get(norm, 'required')
            for m in missing_skills:
                norm = self._normalize_skill(m['required'])
                m['category'] = skill_category_map.get(norm, 'required')

            # 담당업무/필수/우대 분리
            matched_resp = [m for m in matched_skills if m['category'] == 'responsibilities']
            matched_required = [m for m in matched_skills if m['category'] == 'required']
            matched_preferred = [m for m in matched_skills if m['category'] == 'preferred']

            print(f"✅ 매칭 결과: 담당업무 {len(matched_resp)}/{len(responsibilities_skills)}, 필수 {len(matched_required)}/{len(all_required_skills)}, 우대 {len(matched_preferred)}/{len(all_preferred_skills)}")

            # === 점수 계산 (존재하는 카테고리에 동적 가중치 배분) ===
            resp_rate = min(len(matched_resp) / len(responsibilities_skills), 1.0) if responsibilities_skills else 0
            required_rate = min(len(matched_required) / len(all_required_skills), 1.0) if all_required_skills else 0
            preferred_rate = min(len(matched_preferred) / len(all_preferred_skills), 1.0) if all_preferred_skills else 0

            weights = {}
            if responsibilities_skills: weights['resp'] = 0.40
            if all_required_skills: weights['req'] = 0.40
            if all_preferred_skills: weights['pref'] = 0.20
            total_weight = sum(weights.values()) or 1.0
            match_rate = (
                weights.get('resp', 0) / total_weight * resp_rate +
                weights.get('req', 0) / total_weight * required_rate +
                weights.get('pref', 0) / total_weight * preferred_rate
            )

            # 경력 적합도: work_experience에서 관련 경력만 추출하여 비교
            relevant_years = self._extract_relevant_years(
                work_experience, all_required_skills, position
            )
            print(f"📋 경력 정보: 총 {experience_years}년, 관련 경력 {relevant_years}년, work_experience {len(work_experience)}건, 요구 범위: {experience_range}")
            exp_fit = self._calculate_exp_fit(experience_years, experience_range, relevant_years)

            # 숙련도 가중치 (스킬 레벨이 있으면 반영)
            # 단순히 스킬을 보유하는 것뿐 아니라 숙련도까지 고려
            proficiency_score = 0.0
            if skill_levels and matched_skills:
                level_sum = 0
                for m in matched_skills:
                    user_skill = m["user_skill"]
                    level = skill_levels.get(user_skill, 3)  # 기본값 3 (중급)
                    level_sum += level
                # 평균 숙련도를 0.0-1.0 범위로 정규화 (1-5 레벨 -> 0.2-1.0)
                proficiency_score = round(level_sum / len(matched_skills) / 5.0, 3) if matched_skills else 0.0

            # 준비도 점수 개선 (더 직관적인 계산)
            # 1. 기본: 매칭률 (60%)
            # 2. 경력 적합도 (25%)
            # 3. 숙련도 (15%)
            base_score = match_rate * 0.60
            exp_score = exp_fit * 0.25
            skill_score = proficiency_score * 0.15 if proficiency_score > 0 else 0

            readiness = round(base_score + exp_score + skill_score, 3)

            # readiness가 1.0을 초과하지 않도록
            readiness = min(readiness, 1.0)

            # skill_gap: 매칭되지 않은 비율 (0.0 ~ 1.0)
            skill_gap = round(max(1.0 - match_rate, 0.0), 3)

            # 추가 인사이트
            insights = self._generate_insights(
                name, current_role, education, certifications,
                career_goals, available_prep_days,
                matched_skills, missing_skills, readiness, skill_gap
            )

            return Response({
                "readiness_score": readiness,
                "skill_gap_score": skill_gap,
                "experience_fit": exp_fit,
                "proficiency_score": proficiency_score,
                "matched_skills": matched_skills,
                "missing_skills": missing_skills,
                "insights": insights,
                "profile_summary": {
                    "name": name,
                    "current_role": current_role,
                    "education": education,
                    "certifications": certifications,
                    "training": training,
                    "career_goals": career_goals,
                    "available_prep_days": available_prep_days
                }
            }, status=status.HTTP_200_OK)

        except Exception as e:
            print(f"❌ 분석 에러: {e}")
            print(traceback.format_exc())
            return Response({
                "error": f"분석 중 오류 발생: {str(e)}"
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def _match_skills_with_llm(self, required_skills, user_skills):
        """
        LLM 기반 스킬 매칭.
        단순 문자열 비교가 아닌 의미 기반으로 유사 기술을 판단합니다.

        similarity 기준:
            1.0        : 완전히 동일 (대소문자·한국어 표기 포함)
            0.85~0.99  : 표기(구분자·축약)만 다른 동일 기술
            0.70~0.84  : 같은 목적으로 대체 가능한 경쟁 기술 (Django ↔ Flask)
            0.50~0.69  : 같은 생태계 내 연관 기술 (pandas ↔ Python)
            0.30~0.49  : 간접 연관 (같은 도메인, 역할 다름)
            0.30 미만  : 매칭 안 함 -> missing_skills

        LLM 호출 실패 시 _match_skills_fallback()으로 대체됩니다.

        Returns:
            matched_skills: [{required, user_skill, similarity, reason}]
            missing_skills: [{required}]
        """
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            return self._match_skills_fallback(required_skills, user_skills)

        try:
            client = openai.OpenAI(api_key=api_key)
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{
                    "role": "user",
                    "content": f"""IT 채용 전문가로서 채용공고 요구 스킬과 지원자 보유 스킬을 비교하세요.

채용공고 요구 스킬: {json.dumps(required_skills, ensure_ascii=False)}
지원자 보유 스킬: {json.dumps(user_skills, ensure_ascii=False)}

similarity 기준:

[1.0] 완전히 동일한 기술
- 대소문자만 다른 경우 반드시 1.0: langchain ↔ LangChain, tensorflow ↔ TensorFlow
- 한국어·영어 표기 차이: Python ↔ 파이썬, Docker ↔ 도커, API ↔ 에이피아이
- 전체 이름 ↔ 약어: JavaScript ↔ JS, Kubernetes ↔ K8s

[0.85~0.99] 표기만 다를 뿐 동일한 기술
- 구분자·축약 차이만 있음: Node.js ↔ NodeJS, scikit-learn ↔ sklearn, TypeScript ↔ TS
- 버전·세대 표기 차이: Python3 ↔ Python

[0.70~0.84] 동일한 목적·역할로 대체 가능한 기술 (같은 카테고리 내 경쟁 기술)
- 조건: 같은 문제를 해결하는 기술이어야 함. 단순히 같은 분야에서 쓰인다는 이유만으로는 해당 안 됨
- Python 웹 프레임워크끼리: Django ↔ Flask ↔ FastAPI
- JavaScript 프론트엔드 프레임워크끼리: React ↔ Vue ↔ Angular
- 관계형 DB끼리: MySQL ↔ PostgreSQL ↔ MariaDB
- NoSQL DB끼리: MongoDB ↔ CouchDB
- 클라우드 플랫폼끼리: AWS ↔ GCP ↔ Azure
- ❌ 목적이 다른 기술은 해당 안 됨: Elasticsearch(검색엔진) ↔ Django(웹프레임워크), Redis(캐시) ↔ PostgreSQL(RDBMS)

[0.50~0.69] 같은 언어·생태계 내에서 함께 사용되는 기술 (대체 불가, 연관성 높음)
- 조건: 직접 대체는 불가하지만 같은 생태계에서 함께 쓰이며 개념적 연관성이 높음
- Python 데이터사이언스 생태계: pandas ↔ Python, pandas ↔ Scikit-learn, numpy ↔ Python
- 언어 ↔ 해당 언어 기반 프레임워크: Java ↔ Spring, Python ↔ Django, JavaScript ↔ React
- 유사 역할 언어끼리: Java ↔ Kotlin (JVM 기반), TypeScript ↔ JavaScript

[0.30~0.49] 간접적으로 연관된 기술 (같은 도메인이지만 역할이 다름)
- 조건: 같은 도메인(백엔드·ML 등)에 있지만 역할·목적이 다름
- CI/CD 개념 ↔ 특정 도구: CI/CD ↔ GitHub Actions, 배포 ↔ Jenkins
- 다른 패러다임의 언어: Python ↔ R
- 다른 API 스타일: REST API ↔ GraphQL

[0.30 미만] 매칭하지 않음 -> missing_skills에 추가
- 역할·목적·생태계가 모두 다른 기술: Elasticsearch ↔ Django, Redis ↔ React

규칙:
- 각 보유 스킬은 하나의 요구 스킬에만 매칭 (1:1)
- 특정 라이브러리가 요구될 때, 지원자의 전체 보유 스킬 목록을 고려해 해당 라이브러리가 속한 언어·생태계를 보유하고 있으면 유사 기술로 판단 (예: pandas 요구 + Python·Scikit-learn 보유 -> 0.50 이상)
- 개별 스킬 쌍만 보지 말고 지원자의 전체 스킬 맥락을 함께 고려할 것
- 단순히 같은 분야(백엔드, 프론트엔드 등)에서 쓰인다는 이유만으로 0.70 이상을 부여하지 말 것

JSON으로만 반환:
{{
  "matched_skills": [{{"required": "요구스킬", "user_skill": "보유스킬", "similarity": 1.0, "reason": "매칭 이유"}}],
  "missing_skills": [{{"required": "요구스킬"}}]
}}"""
                }],
                response_format={"type": "json_object"},
                temperature=0
            )

            data = json.loads(response.choices[0].message.content)
            matched = data.get("matched_skills", [])
            missing = data.get("missing_skills", [])
            print(f"✅ LLM 매칭 완료: {len(matched)}개 매칭, {len(missing)}개 미매칭")
            return matched, missing

        except Exception as e:
            print(f"⚠️  LLM 매칭 실패, fallback 사용: {e}")
            return self._match_skills_fallback(required_skills, user_skills)

    def _match_skills_fallback(self, required_skills, user_skills):
        """LLM 실패 시 정규화 기반 단순 매칭 (fallback)"""
        user_normalized = {self._normalize_skill(s): s for s in user_skills}
        matched, missing = [], []
        used = set()

        for req in required_skills:
            req_norm = self._normalize_skill(req)
            if req_norm in user_normalized and req_norm not in used:
                matched.append({
                    "required": req,
                    "user_skill": user_normalized[req_norm],
                    "similarity": 1.0,
                    "reason": "정확히 일치"
                })
                used.add(req_norm)
            else:
                missing.append({"required": req})

        return matched, missing

    def _extract_relevant_years(self, work_experience, required_skills, position):
        """
        이력서 work_experience에서 공고 포지션/스킬과 관련된 경력 연수만 추출.

        각 경력 항목의 role, description, skills를 공고의 required_skills, position과 비교하여
        관련 있는 항목의 기간만 합산합니다.
        work_experience가 없으면 None을 반환하여 총 경력으로 fallback합니다.
        """
        if not work_experience:
            return None

        import re

        # 비교용 키워드 세트 (공고의 필수 스킬 + 포지션 키워드)
        job_keywords = set()
        for s in required_skills:
            job_keywords.add(self._normalize_skill(s))
        if position:
            for word in re.split(r'[\s/·,]+', position.lower()):
                if len(word) >= 2:
                    job_keywords.add(word)

        relevant_years = 0.0
        print(f"  🔎 경력 관련성 판정 — job_keywords: {job_keywords}")

        for entry in work_experience:
            if not isinstance(entry, dict):
                continue

            # 경력 항목의 텍스트를 모아서 키워드 비교
            entry_text = ' '.join([
                entry.get('role', ''),
                entry.get('description', ''),
                ' '.join(entry.get('skills', [])),
                ' '.join(entry.get('achievements', [])),
            ]).lower()

            # 경력 항목의 스킬을 정규화해서 비교
            entry_skills = {self._normalize_skill(s) for s in entry.get('skills', [])}

            # 관련성 판정: 스킬 겹침 또는 직무 키워드 포함
            is_relevant = bool(entry_skills & job_keywords)
            print(f"  📌 [{entry.get('role', '?')}] entry_skills={entry_skills}, is_relevant={is_relevant}, period={entry.get('period', '?')}, desc={entry.get('description', '')[:80]}")
            if not is_relevant:
                for kw in job_keywords:
                    if kw in entry_text:
                        is_relevant = True
                        break

            if is_relevant:
                relevant_years += self._parse_period_years(entry.get('period', ''))

        # work_experience가 있었으면 관련 경력이 0이라도 그대로 반환 (다른 도메인 경력)
        # None은 work_experience 자체가 없을 때만 (fallback용)
        return relevant_years

    def _parse_period_years(self, period_str):
        """
        경력 기간 문자열에서 연수를 추출.
        "2년 3개월" -> 2.25, "2022.01 - 2024.06" -> 2.42, "3년" -> 3.0
        """
        import re
        if not period_str:
            return 0.0

        # "N년 M개월" 패턴
        ym = re.search(r'(\d+)\s*년\s*(\d+)?\s*개?월?', period_str)
        if ym:
            y = int(ym.group(1))
            m = int(ym.group(2)) if ym.group(2) else 0
            return y + m / 12.0

        # "2022.01 - 2024.06" 또는 "2022-01 ~ 2024-06" 패턴
        dates = re.findall(r'(\d{4})[.\-/](\d{1,2})', period_str)
        if len(dates) >= 2:
            start_y, start_m = int(dates[0][0]), int(dates[0][1])
            end_y, end_m = int(dates[1][0]), int(dates[1][1])
            return max(0.0, (end_y - start_y) + (end_m - start_m) / 12.0)

        # "2022 - 2024" 패턴 (월 없이 연도만)
        years_only = re.findall(r'(\d{4})', period_str)
        if len(years_only) >= 2:
            return max(0.0, int(years_only[1]) - int(years_only[0]))

        # "N년" 패턴
        y_only = re.search(r'(\d+)\s*년', period_str)
        if y_only:
            return float(y_only.group(1))

        return 0.0

    def _calculate_exp_fit(self, total_years, req_range, relevant_years=None):
        """
        경력 적합도 계산

        work_experience에서 추출한 관련 경력 연수(relevant_years)가 있으면 그 값을 사용하고,
        없으면 총 경력(total_years)으로 fallback합니다.

        Args:
            total_years (int): 총 경력 연수
            req_range (str): 요구 경력 범위 (예: "3-5년", "5년 이상", "신입")
            relevant_years (float|None): 관련 도메인 경력 연수 (없으면 total_years 사용)

        Returns:
            float: 경력 적합도 점수 (0.0-1.0)
        """
        import re

        years = relevant_years if relevant_years is not None else total_years

        # 정규식으로 숫자 추출 (예: "3-5년" -> [3, 5], "신입" -> [])
        nums = re.findall(r'\d+', req_range)
        if not nums:
            # 숫자 정보가 없으면 중간 점수 반환
            return 0.7

        # 최소 경력과 최대 경력 파싱
        lo = int(nums[0])
        hi = int(nums[-1]) if len(nums) > 1 else lo + 2  # 단일 숫자면 +2년 범위

        if lo <= years <= hi:
            # 요구 범위 내: 완벽한 적합
            return 1.0
        elif years < lo:
            # 경력 부족: 비율로 계산 (예: 2년 경력 / 3년 요구 = 0.67)
            return max(0.0, years / lo)
        else:
            # 경력 초과: 약간의 감점 (경력이 너무 많으면 오버스펙)
            # 예: 8년 경력, 5년 요구 -> 1.0 - (8-5)*0.05 = 0.85
            return max(0.7, 1.0 - (years - hi) * 0.05)

    def _generate_insights(self, name, current_role, education, certifications,
                          career_goals, available_prep_days,
                          matched_skills, missing_skills, readiness, skill_gap):
        """
        프로필 기반 인사이트 생성

        사용자의 프로필 정보와 분석 결과를 바탕으로
        맞춤형 조언과 인사이트를 생성합니다.

        Args:
            name, current_role, education, certifications: 프로필 정보
            career_goals: 커리어 목표
            available_prep_days: 준비 가능한 기간 (일)
            matched_skills, missing_skills: 매칭 결과
            readiness, skill_gap: 준비도 점수

        Returns:
            list: 인사이트 목록 (각 인사이트는 type, title, message 포함)
        """
        insights = []

        # 준비도 기반 조언
        if readiness >= 0.7:
            insights.append({
                "type": "positive",
                "title": "높은 준비도",
                "message": "현재 스킬셋이 공고 요구사항과 잘 맞습니다. 자신감을 갖고 지원하세요!"
            })
        elif readiness >= 0.5:
            insights.append({
                "type": "neutral",
                "title": "중간 준비도",
                "message": f"부족한 스킬 {len(missing_skills)}개를 보완하면 경쟁력이 크게 향상됩니다."
            })
        else:
            insights.append({
                "type": "warning",
                "title": "준비 필요",
                "message": "핵심 스킬 보완이 필요합니다. 우선순위를 정해 집중적으로 학습하세요."
            })

        # 준비 기간 조언
        if available_prep_days:
            days = int(available_prep_days)
            if days < 7 and skill_gap > 0.4:
                insights.append({
                    "type": "warning",
                    "title": "시간 부족",
                    "message": f"준비 기간({days}일)이 부족 스킬 수({len(missing_skills)}개)에 비해 짧습니다. 가장 중요한 스킬 1-2개에 집중하세요."
                })
            elif days >= 30:
                insights.append({
                    "type": "positive",
                    "title": "충분한 준비 시간",
                    "message": f"{days}일 동안 체계적으로 학습하면 준비도를 크게 향상시킬 수 있습니다."
                })

        # 자격증 활용
        if certifications and len(certifications) > 0:
            insights.append({
                "type": "positive",
                "title": "자격증 보유",
                "message": f"보유 자격증({', '.join(certifications)})을 이력서와 면접에서 적극 어필하세요."
            })

        # 커리어 목표 일치성
        if career_goals:
            insights.append({
                "type": "neutral",
                "title": "커리어 목표 확인",
                "message": f"목표({career_goals})와 이 포지션이 일치하는지 다시 한번 확인하세요."
            })

        # 현재 직무와의 연관성
        if current_role:
            insights.append({
                "type": "neutral",
                "title": "경력 연속성",
                "message": f"현재 직무({current_role})와의 연관성을 면접에서 강조하면 좋습니다."
            })

        return insights


@method_decorator(csrf_exempt, name='dispatch')
class JobPlannerAgentReportView(APIView):
    """
    최종 종합 보고서 생성 API
    - SWOT 분석
    - 경험 포장 가이드
    - 실행 전략
    """
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        try:
            # 분석 결과 데이터
            job_data = request.data.get('job_data', {})
            analysis_result = request.data.get('analysis_result', {})
            company_analysis = request.data.get('company_analysis', {})
            user_profile = request.data.get('user_profile', {})
            # LLM으로 종합 보고서 생성
            available_prep_days = analysis_result.get('profile_summary', {}).get('available_prep_days')
            report = self._generate_report_with_llm(
                job_data, analysis_result, company_analysis, available_prep_days, user_profile
            )

            return Response(report, status=status.HTTP_200_OK)

        except Exception as e:
            print(f"❌ 보고서 생성 에러: {e}")
            print(traceback.format_exc())
            return Response({
                "error": f"보고서 생성 중 오류 발생: {str(e)}"
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def _generate_report_with_llm(self, job_data, analysis_result, company_analysis, available_prep_days=None, user_profile=None):
        """LLM으로 최종 종합 보고서 생성"""
        api_key = os.getenv('OPENAI_API_KEY')
        if not api_key:
            return {
                "error": "OPENAI_API_KEY가 설정되지 않았습니다.",
                "swot": {
                    "strengths": [{"point": "스킬 매칭률이 높습니다", "evidence": "분석 데이터 없음"}],
                    "weaknesses": [{"point": "일부 스킬이 부족합니다", "evidence": "분석 데이터 없음"}],
                    "opportunities": [{"point": "성장 가능성이 있습니다", "evidence": "분석 데이터 없음"}],
                    "threats": [{"point": "경쟁이 치열할 수 있습니다", "evidence": "분석 데이터 없음"}]
                },

                "experience_packaging": [],
                "execution_strategy": ""
            }

        try:
            client = openai.OpenAI(api_key=api_key)

            # 준비 기간에 따른 전략 기간 레이블 생성
            print(f"[DEBUG] available_prep_days = {available_prep_days}, type = {type(available_prep_days)}")

            # 타입 변환 (문자열이나 숫자 모두 처리)
            try:
                days = int(float(available_prep_days)) if available_prep_days else 0
            except (ValueError, TypeError):
                days = 0

            if days > 0:
                print(f"[INFO] 준비 기간 {days}일 기반으로 전략 기간 설정")
                if days <= 7:
                    short_term_label = f"단기 ({days}일)"
                    mid_term_label = "중기 (2주)"
                elif days <= 14:
                    short_term_label = "단기 (1주)"
                    mid_term_label = f"중기 ({days}일)"
                elif days <= 21:
                    short_term_label = "단기 (1주)"
                    mid_term_label = f"중기 (3주, {days}일)"
                elif days <= 30:
                    short_term_label = "단기 (1-2주)"
                    mid_term_label = f"중기 (1개월, {days}일)"
                else:
                    short_term_label = "단기 (1-2주)"
                    mid_term_label = f"중기 (1-2개월, {days}일)"
                prep_days_info = f"\n- 준비 가능 기간: {days}일"
            else:
                print(f"[WARN] 준비 기간 정보 없음, 기본값 사용")
                short_term_label = "단기 (1-2주)"
                mid_term_label = "중기 (1개월)"
                prep_days_info = ""

            # 사용자 프로필 상세 정보 구성
            profile = user_profile or {}
            profile_summary = analysis_result.get('profile_summary', {})

            work_exp = profile.get('work_experience', [])
            work_exp_text = '\n'.join(
                f"  - {e.get('company', '')} | {e.get('role', '')} ({e.get('period', '')}): {e.get('description', '')}"
                for e in work_exp
            ) if work_exp else '  없음'

            projects = profile.get('projects', [])
            projects_text = '\n'.join(
                f"  - {p}" if isinstance(p, str) else f"  - {p.get('name', '')}: {p.get('description', '')} [기술: {', '.join(p.get('skills', []))}] [성과: {', '.join(p.get('achievements', []))}]"
                for p in projects
            ) if projects else '  없음'

            achievements = profile.get('key_achievements', [])
            achievements_text = '\n'.join(f"  - {a}" for a in achievements) if achievements else '  없음'

            strengths = profile.get('strengths', [])
            strengths_text = ', '.join(strengths) if strengths else '없음'

            awards = profile.get('awards', [])
            awards_text = ', '.join(awards) if awards else '없음'

            languages = profile.get('languages', [])
            languages_text = ', '.join(
                f"{l.get('language', '')}({l.get('level', '')})" if isinstance(l, dict) else str(l)
                for l in languages
            ) if languages else '없음'

            # 컨텍스트 구성
            context = f"""
채용공고:
- 회사: {job_data.get('company_name', '미정')}
- 포지션: {job_data.get('position', '개발자')}
- 주요 업무: {job_data.get('job_responsibilities', '정보 없음')}
- 필수 요건: {job_data.get('required_qualifications', '정보 없음')}
- 필수 스킬: {', '.join(job_data.get('required_skills', []))}
- 우대 스킬: {', '.join(job_data.get('preferred_skills', []))}
- 우대 사항: {job_data.get('preferred_qualifications', '정보 없음')}

분석 결과:
- 준비도: {analysis_result.get('readiness_score', 0)}
- 스킬 갭: {analysis_result.get('skill_gap_score', 0)}
- 매칭된 스킬: {json.dumps(analysis_result.get('matched_skills', []), ensure_ascii=False)}
- 부족한 스킬: {json.dumps(analysis_result.get('missing_skills', []), ensure_ascii=False)}{prep_days_info}

사용자 프로필 (서류 기반):
- 이름: {profile_summary.get('name', '미정')}
- 현재 직무: {profile_summary.get('current_role', '없음')}
- 학력: {profile_summary.get('education', '없음')}
- 자격증: {', '.join(profile_summary.get('certifications', [])) or '없음'}
- 교육 이수: {json.dumps(profile_summary.get('training', []), ensure_ascii=False) or '없음'}
- 커리어 목표: {profile_summary.get('career_goals', '없음')}
- 보유 스킬: {', '.join(profile.get('user_skills', []))}
- 스킬 숙련도: {json.dumps(profile.get('skill_levels', {}), ensure_ascii=False)}
- 강점: {strengths_text}
- 수상 경력: {awards_text}
- 외국어: {languages_text}
- 팀워크 경험: {profile.get('teamwork_experience', '없음') or '없음'}
- 성장 스토리: {profile.get('growth_story', '없음') or '없음'}
- GitHub: {profile.get('github_url', '없음') or '없음'}
- 포트폴리오: {profile.get('portfolio_url', '없음') or '없음'}

경력 사항:
{work_exp_text}

프로젝트:
{projects_text}

핵심 성과:
{achievements_text}

기업 분석:
{json.dumps(company_analysis, ensure_ascii=False) if company_analysis else '정보 없음'}
"""

            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "system",
                        "content": """당신은 전문 커리어 컨설턴트입니다.
취업 준비생을 위한 종합 보고서를 작성하세요.
구체적이고 실행 가능한 조언을 제공해야 합니다."""
                    },
                    {
                        "role": "user",
                        "content": f"""{context}

위 정보를 바탕으로 다음 내용을 포함한 종합 보고서를 JSON 형식으로 작성하세요:

1. **SWOT 분석**
   - Strengths: 강점 3-5개 (구체적으로, 각 항목마다 공고 또는 사용자 서류의 어떤 내용을 근거로 판단했는지 반드시 명시)
   - Weaknesses: 약점 2-4개 (보완 방법 포함, 각 항목마다 공고 요구사항 또는 사용자 프로필의 어떤 부분에서 도출했는지 근거 명시)
   - Opportunities: 기회 2-3개 (각 항목마다 근거 명시)
   - Threats: 위협 요소 1-2개 (각 항목마다 근거 명시)

2. **경험 포장 가이드**
   - 이력서/포트폴리오에서 강조할 점
   - 프로젝트 경험 어필 방법
   - 부족한 스킬을 보완하는 방법

4. **실행 전략**
   - {short_term_label}: 즉시 할 일
   - {mid_term_label}: 스킬 보완
   - 지원 시점: 최적 타이밍

JSON 형식:
{{
  "swot": {{
    "strengths": [{{"point": "강점 내용", "evidence": "근거 (예: 공고에서 요구하는 Python을 사용자가 보유)"}}, ...],
    "weaknesses": [{{"point": "약점 내용 (보완: ...)", "evidence": "근거 (예: 공고에서 요구하는 Kubernetes 경험이 프로필에 없음)"}}, ...],
    "opportunities": [{{"point": "기회 내용", "evidence": "근거"}}, ...],
    "threats": [{{"point": "위협 내용", "evidence": "근거"}}, ...]
  }},
  "experience_packaging": {{
    "resume_highlights": ["이력서에 강조할 점1", "강조할 점2", ...],
    "portfolio_tips": ["포트폴리오 팁1", "팁2", ...],
    "skill_compensation": ["부족 스킬 보완법1", "보완법2", ...]
  }},
  "execution_strategy": {{
    "immediate": ["즉시 할 일1", "할 일2", ...],
    "short_term": ["{short_term_label} 내 할 일1", "할 일2", ...],
    "mid_term": ["{mid_term_label} 내 할 일1", "할 일2", ...],
    "application_timing": "최적 지원 시점 및 이유"
  }},
  "final_message": "최종 격려 메시지 (2-3문장)"
}}"""
                    }
                ],
                temperature=0.7
            )

            content = response.choices[0].message.content

            # JSON 추출
            if '```json' in content:
                content = content.split('```json')[1].split('```')[0].strip()
            elif '```' in content:
                content = content.split('```')[1].split('```')[0].strip()

            report = json.loads(content)
            return report

        except Exception as e:
            print(f"⚠️  LLM 보고서 생성 실패: {e}")
            return {
                "error": f"보고서 생성 실패: {str(e)}",
                "swot": {
                    "strengths": [{"point": "분석 정보가 부족합니다", "evidence": "분석 데이터 없음"}],
                    "weaknesses": [],
                    "opportunities": [],
                    "threats": []
                },

                "experience_packaging": {
                    "resume_highlights": [],
                    "portfolio_tips": [],
                    "skill_compensation": []
                },
                "execution_strategy": {
                    "immediate": [],
                    "short_term": [],
                    "mid_term": [],
                    "application_timing": ""
                },
                "final_message": "정보가 부족하여 상세 보고서를 생성할 수 없습니다."
            }


@method_decorator(csrf_exempt, name='dispatch')
class JobPlannerRecommendView(APIView):
    """
    채용공고 추천 API

    현재 분석 중인 공고보다 더 적합한 대안 공고를 추천합니다.
    사람인을 실시간 크롤링하여 최신 공고를 수집하고,
    3단계 매칭 시스템으로 사용자 스킬과 비교합니다.

    주요 기능:
    - 실시간 채용공고 크롤링 (사람인)
    - 3단계 스킬 매칭 시스템 적용
    - 중복 공고 필터링
    - 매칭률 기반 정렬 및 추천 이유 생성

    추천 조건:
    - 최소 30% 이상 매칭
    - 현재 준비도보다 높은 매칭률
    - 또는 비슷한 수준이면서 새로운 기술 학습 기회 제공
    """
    authentication_classes = []
    permission_classes = [AllowAny]

    # JobPlannerAnalyzeView와 동일한 스킬 동의어 사전 재사용
    SKILL_SYNONYMS = JobPlannerAnalyzeView.SKILL_SYNONYMS

    def _normalize_skill(self, skill):
        """
        스킬명을 정규화 (한글->영어, 소문자 변환)

        JobPlannerAnalyzeView와 동일한 정규화 로직을 사용하여
        일관된 스킬 매칭을 보장합니다.

        Args:
            skill (str): 원본 스킬명

        Returns:
            str: 정규화된 스킬명 (소문자)
        """
        skill_lower = skill.lower().strip()
        return self.SKILL_SYNONYMS.get(skill_lower, skill_lower)

    def post(self, request):
        try:
            if not CRAWLER_AVAILABLE:
                return Response({
                    "error": "필요한 라이브러리가 설치되지 않았습니다."
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            # 사용자 정보
            user_skills = request.data.get('user_skills', [])
            skill_levels = request.data.get('skill_levels', {})
            readiness_score = float(request.data.get('readiness_score', 0.0))
            job_position = request.data.get('job_position', '개발자')

            # 사용자 프로필 (LLM 2차 평가용)
            work_experience = request.data.get('work_experience', [])
            projects = request.data.get('projects', [])
            key_achievements = request.data.get('key_achievements', [])

            # 원래 공고 정보 (유사도 기준 + 검색 키워드 보강)
            current_required_skills = request.data.get('current_required_skills', [])
            current_required_qualifications = request.data.get('current_required_qualifications', '')
            current_job_responsibilities = request.data.get('current_job_responsibilities', '')

            # 현재 분석 중인 공고 정보 (중복 제거용)
            current_job_url = request.data.get('current_job_url', '')
            current_job_company = request.data.get('current_job_company', '')
            current_job_title = request.data.get('current_job_title', '')

            if not user_skills:
                return Response({
                    "error": "사용자 스킬 정보가 필요합니다."
                }, status=status.HTTP_400_BAD_REQUEST)

            print(f"🔍 추천 공고 검색 시작 (준비도: {readiness_score}, 스킬: {user_skills})")
            print(f"📍 원본 직무: '{job_position}'")

            # 직무명 + 필수 스킬 조합으로 검색 키워드 구성
            search_keyword = self._build_search_keyword(job_position, current_required_skills, user_skills)
            print(f"🔍 검색 키워드: '{search_keyword}'")

            if current_job_url:
                print(f"🚫 제외할 공고: {current_job_company} - {current_job_title}")

            # 1. 사람인에서 공고 수집 (복수 키워드 크롤링)
            job_listings = []
            seen_urls = set()

            # 메인 키워드 + 사용자 핵심 스킬로 추가 검색하여 후보 확대
            search_keywords = [search_keyword]
            position_only = self._simplify_job_position(job_position)
            if position_only != search_keyword and position_only not in {'포지션명', '포지션', '직무명', '직무', '개발자', '담당자', '직책명', ''}:
                search_keywords.append(position_only)

            # 사용자의 대표 스킬로 추가 검색 (첫번째 검색어와 다른 스킬)
            SEARCHABLE = {'python', 'java', 'javascript', 'typescript', 'react', 'vue', 'django',
                          'fastapi', 'spring', 'node.js', 'pytorch', 'tensorflow', 'langchain', 'aws', 'docker'}
            for skill in user_skills:
                if skill.lower() in SEARCHABLE and skill.lower() not in search_keyword.lower():
                    search_keywords.append(f"{skill} 개발자")
                    break

            for kw in search_keywords:
                print(f"🔍 사람인 크롤링: '{kw}' 검색")
                saramin_jobs = self._crawl_saramin(kw, limit=60)
                for job in saramin_jobs:
                    if job['url'] not in seen_urls:
                        seen_urls.add(job['url'])
                        job_listings.append(job)
                print(f"  -> {len(saramin_jobs)}개 수집 (누적 {len(job_listings)}개)")

            print(f"✅ 사람인 총: {len(job_listings)}개 공고")

            if not job_listings:
                return Response({
                    "recommendations": [],
                    "message": "현재 추천 가능한 공고가 없습니다."
                }, status=status.HTTP_200_OK)

            # 1.5. 사용자가 이미 분석한 공고 제외
            filtered_listings = self._filter_duplicate_jobs(
                job_listings, current_job_url, current_job_company, current_job_title
            )
            print(f"🔍 중복 제거 후: {len(filtered_listings)}개 공고")

            # 원래 공고 텍스트 구성
            current_job_text = ' '.join(current_required_skills) + ' ' + current_required_qualifications + ' ' + current_job_responsibilities

            # 1차: 스킬 매칭으로 후보 선별 (검색 결과 스킬 태그만으로 빠르게 필터)
            recommendations = self._match_jobs_with_skills(
                filtered_listings, user_skills, skill_levels, readiness_score, current_job_text
            )

            # 1차: 스킬 태그 30% 이상만 통과 -> 상위 15개 후보 선별
            recommendations = [r for r in recommendations if r['match_rate'] >= 0.30]
            recommendations.sort(key=lambda x: x['match_rate'], reverse=True)
            candidates = recommendations[:15]
            print(f"📋 1차 스킬 필터 (30%↑): {len(candidates)}개 후보")

            if not candidates:
                print(f"⚠️ 유사한 공고를 찾지 못했습니다.")
                return Response({
                    "recommendations": [],
                    "message": "매칭되는 유사한 공고를 찾지 못했습니다."
                }, status=status.HTTP_200_OK)

            # 2차: 후보만 상세 크롤링 (전체가 아닌 후보만 -> 빠름)
            print(f"🔍 후보 {len(candidates)}개 상세 파싱 시작...")
            candidate_jobs = [{'url': c['url'], 'skills': c['skills'], 'company_name': c['company_name'],
                               'title': c['title'], 'source': c['source'], 'location': c['location']}
                              for c in candidates]
            enriched = self._enrich_jobs_with_detail(candidate_jobs)
            # 상세 텍스트 + enriched 스킬을 candidates에 반영
            url_to_enriched = {j['url']: j for j in enriched}
            for c in candidates:
                ej = url_to_enriched.get(c['url'])
                if ej:
                    c['detail_text'] = ej.get('detail_text', '')
                    c['skills'] = ej.get('skills', c['skills'])
            print(f"✅ 상세 파싱 완료")

            # 3차: LLM으로 상세 적합도 평가
            if candidates:
                # 사용자 프로필 구성
                exp_summary = '; '.join(
                    f"{e.get('company', '')} {e.get('role', '')} ({e.get('period', '')}): {e.get('description', '')}"
                    for e in work_experience
                ) if work_experience else '정보 없음'
                proj_summary = '; '.join(
                    p if isinstance(p, str) else p.get('name', '') + ': ' + p.get('description', '')
                    for p in projects
                ) if projects else '정보 없음'
                achievements_summary = '; '.join(
                    a if isinstance(a, str) else str(a)
                    for a in key_achievements
                ) if key_achievements else '정보 없음'

                user_profile = {
                    'skills': user_skills,
                    'experience_summary': exp_summary,
                    'projects_summary': proj_summary,
                    'achievements_summary': achievements_summary,
                }
                print(f"🤖 LLM 2차 평가 시작 ({len(candidates)}개)...")
                candidates = self._evaluate_with_llm(candidates, user_profile)
                print(f"✅ LLM 평가 완료")

            # detail_text는 응답에서 제외 (프론트에 불필요)
            # LLM 점수가 있으면 그대로 match_rate로 사용 (스킬+경력+프로젝트 종합 평가)
            for c in candidates:
                c.pop('detail_text', None)
                if 'llm_score' in c:
                    c['match_rate'] = round(c['llm_score'] / 100.0, 3)

            # 최종: LLM 종합 매칭률 50% 이상만 반환
            final = [c for c in candidates if c['match_rate'] >= 0.50]
            final.sort(key=lambda x: x['match_rate'], reverse=True)
            print(f"📋 최종 결과: {len(final)}개 (50% 이상)")

            if not final:
                return Response({
                    "recommendations": [],
                    "message": "현재 스킬과 매칭되는 유사한 공고를 찾지 못했습니다."
                }, status=status.HTTP_200_OK)

            return Response({
                "recommendations": final,
                "total_found": len(job_listings),
                "total_recommendations": len(final)
            }, status=status.HTTP_200_OK)

        except Exception as e:
            print(f"❌ 추천 에러: {e}")
            print(traceback.format_exc())
            return Response({
                "error": f"추천 중 오류 발생: {str(e)}"
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def _filter_duplicate_jobs(self, job_listings, current_url, current_company, current_title):
        """사용자가 이미 분석한 공고를 제외"""
        import re

        def normalize(text):
            """비교를 위해 텍스트 정규화: 소문자, 특수문자/공백 제거"""
            if not text:
                return ''
            return re.sub(r'[^a-z0-9가-힣]', '', text.lower().strip())

        def extract_keywords(title):
            """제목에서 핵심 키워드 추출"""
            if not title:
                return set()
            # 괄호 내용 제거, 특수문자로 분리
            cleaned = re.sub(r'[(\[（【].*?[)\]）】]', ' ', title)
            words = re.split(r'[\s/·,|_\-]+', cleaned)
            # 1글자 이하 제거, 의미없는 단어 제거
            stopwords = {'채용', '모집', '신입', '경력', '정규직', '계약직', '급구', '상시', '및', '외', '등'}
            return {w.lower().strip() for w in words if len(w.strip()) > 1 and w.strip() not in stopwords}

        curr_company_norm = normalize(current_company)
        curr_title_norm = normalize(current_title)
        curr_keywords = extract_keywords(current_title)

        filtered = []

        for job in job_listings:
            # URL이 정확히 일치하면 제외
            if current_url and job.get('url') == current_url:
                print(f"  ❌ URL 중복 제외: {job['title']}")
                continue

            job_company_norm = normalize(job.get('company_name', ''))
            job_title_norm = normalize(job.get('title', ''))

            # 회사명이 유사한지 확인
            company_match = False
            if curr_company_norm and job_company_norm:
                company_match = (curr_company_norm in job_company_norm or job_company_norm in curr_company_norm)

            if company_match:
                # 1) 정규화된 제목이 서로 포함되면 제외
                if curr_title_norm and job_title_norm:
                    if curr_title_norm in job_title_norm or job_title_norm in curr_title_norm:
                        print(f"  ❌ 제목 중복 제외: {job['company_name']} - {job['title']}")
                        continue

                # 2) 제목 키워드 겹침이 60% 이상이면 제외 (같은 공고가 다른 표현으로 올라온 경우)
                if curr_keywords:
                    job_keywords = extract_keywords(job.get('title', ''))
                    if job_keywords:
                        overlap = curr_keywords & job_keywords
                        overlap_ratio = len(overlap) / min(len(curr_keywords), len(job_keywords))
                        if overlap_ratio >= 0.8:
                            print(f"  ❌ 키워드 중복 제외 ({overlap_ratio:.0%}): {job['company_name']} - {job['title']}")
                            continue

            filtered.append(job)

        return filtered

    def _build_search_keyword(self, job_position: str, required_skills: list, user_skills: list = None) -> str:
        """
        검색 키워드 구성.
        포지션명이 유효하면 포지션 + 기술 스킬 조합.
        포지션명이 의미없으면 사용자 스킬 기반으로 검색어 생성.
        """
        position = self._simplify_job_position(job_position)

        # 의미없는 직무명 감지
        INVALID_POSITIONS = {'포지션명', '포지션', '직무명', '직무', '개발자', '담당자', '직책명', ''}
        is_valid_position = position not in INVALID_POSITIONS

        # 사람인 검색에서 인식되는 대표 기술 스킬 목록
        SEARCHABLE_SKILLS = [
            'Python', 'Java', 'JavaScript', 'TypeScript', 'Kotlin', 'Go',
            'React', 'Vue', 'Angular', 'Django', 'FastAPI', 'Flask',
            'Spring', 'Node.js', 'Next.js', 'Docker', 'Kubernetes',
            'AWS', 'GCP', 'MySQL', 'PostgreSQL', 'MongoDB', 'TensorFlow', 'PyTorch',
            'LangChain', 'Spark', 'Airflow',
        ]

        # 필수 스킬에서 검색 가능한 기술 찾기
        matched_tech = None
        for skill in required_skills:
            for ts in SEARCHABLE_SKILLS:
                if ts.lower() == skill.lower() or ts.lower() in skill.lower():
                    matched_tech = ts
                    break
            if matched_tech:
                break

        if is_valid_position:
            return f"{matched_tech} {position}" if matched_tech else position

        # 직무명이 의미없으면 사용자 스킬에서 대표 기술을 찾아 검색어 생성
        all_skills = required_skills + (user_skills or [])
        tech_found = []
        for skill in all_skills:
            for ts in SEARCHABLE_SKILLS:
                if ts.lower() == skill.lower() or ts.lower() in skill.lower():
                    if ts not in tech_found:
                        tech_found.append(ts)
                    break
            if len(tech_found) >= 2:
                break

        if tech_found:
            return f"{tech_found[0]} 개발자"
        return '개발자'

    def _simplify_job_position(self, job_position: str) -> str:
        """
        직무명을 검색에 적합한 간단한 키워드로 정제합니다.

        예시:
        - "AI리서치엔지니어-LLM포스트트레이닝" -> "AI 엔지니어"
        - "(주)헥토 AI개발" -> "AI개발"
        - "백엔드 개발자 (Python/Django)" -> "백엔드 개발자"
        - "데이터 분석가 [신입/경력]" -> "데이터 분석가"

        Args:
            job_position (str): 원본 직무명

        Returns:
            str: 정제된 검색 키워드
        """
        import re

        # 괄호와 그 내용 제거 (영어 괄호)
        simplified = re.sub(r'\([^)]*\)', '', job_position)
        # 대괄호와 그 내용 제거
        simplified = re.sub(r'\[[^\]]*\]', '', simplified)
        # 중괄호와 그 내용 제거
        simplified = re.sub(r'\{[^}]*\}', '', simplified)

        # 하이픈 이후 제거 (보통 상세 설명)
        if '-' in simplified:
            simplified = simplified.split('-')[0]

        # 슬래시로 구분된 경우 첫 번째 항목만
        if '/' in simplified:
            parts = simplified.split('/')
            # 가장 긴 부분 선택 (보통 메인 직무명)
            simplified = max(parts, key=len)

        # 회사명 패턴 제거
        simplified = re.sub(r'(주\)|㈜|\(주\))', '', simplified)

        # 특수문자 제거하되 공백은 유지
        simplified = re.sub(r'[^\w\s가-힣]', ' ', simplified)

        # 다중 공백을 단일 공백으로
        simplified = ' '.join(simplified.split())

        # 핵심 키워드 추출 시도
        # AI/데이터/개발 관련 키워드가 있으면 우선 사용
        keywords_priority = {
            'AI': ['AI', '인공지능', 'LLM', 'GPT'],
            '머신러닝': ['머신러닝', 'ML', '기계학습'],
            '딥러닝': ['딥러닝', 'DL', '심층학습'],
            '데이터': ['데이터', 'Data'],
            '백엔드': ['백엔드', 'Backend', '서버'],
            '프론트엔드': ['프론트엔드', 'Frontend', '프론트'],
            '풀스택': ['풀스택', 'Full Stack', 'Fullstack'],
            'DevOps': ['DevOps', '데브옵스'],
            '클라우드': ['클라우드', 'Cloud'],
            'QA': ['QA', '테스트', 'Test']
        }

        for main_keyword, variants in keywords_priority.items():
            for variant in variants:
                if variant in simplified:
                    # 해당 키워드와 "엔지니어", "개발자", "분석가" 등이 함께 있는지 확인
                    if any(role in simplified for role in ['엔지니어', '개발자', '분석가', '매니저', 'Engineer', 'Developer', 'Analyst']):
                        # 키워드와 역할을 함께 반환
                        for role in ['엔지니어', '개발자', '분석가', '매니저', 'Engineer', 'Developer', 'Analyst']:
                            if role in simplified:
                                return f"{main_keyword} {role}"
                    # 역할이 없으면 키워드만 반환
                    return main_keyword

        # 우선순위 키워드가 없으면 정제된 텍스트 그대로 반환
        # 단, 너무 길면 앞부분만 (15자 제한)
        if len(simplified) > 15:
            simplified = simplified[:15].strip()

        return simplified.strip() if simplified.strip() else '개발자'

    def _crawl_saramin(self, job_position, limit=60):
        """
        사람인 검색 결과 다중 페이지 크롤링 (병렬).
        페이지당 약 20개 × 3페이지 = 최대 60개 수집 후 상세 크롤링.
        """
        import urllib.parse
        from concurrent.futures import ThreadPoolExecutor, as_completed

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        encoded = urllib.parse.quote(job_position)
        base_url = f"https://www.saramin.co.kr/zf_user/search?searchType=search&searchword={encoded}"

        def fetch_page(page):
            url = base_url if page == 1 else f"{base_url}&recruitPage={page}"
            try:
                resp = requests.get(url, headers=headers, timeout=15)
                resp.raise_for_status()
                soup = BeautifulSoup(resp.text, 'html.parser')
                items = soup.select('.item_recruit')
                page_jobs = []
                for item in items:
                    try:
                        company_elem = item.select_one('.corp_name a')
                        company_name = company_elem.get_text(strip=True) if company_elem else '알 수 없음'

                        title_elem = item.select_one('.job_tit a')
                        if not title_elem:
                            continue
                        title = title_elem.get_text(strip=True)
                        job_url = 'https://www.saramin.co.kr' + title_elem['href'] if title_elem.get('href') else ''

                        skills_elem = item.select('.job_sector a')
                        skills = [s.get_text(strip=True) for s in skills_elem]

                        conditions = item.select('.job_condition span')
                        conditions_text = [c.get_text(strip=True) for c in conditions]

                        location_elem = item.select_one('.job_condition span:first-child')
                        location = location_elem.get_text(strip=True) if location_elem else ''

                        print(f'  [사람인 p{page}] {company_name} - 스킬: {skills if skills else "없음"}')
                        page_jobs.append({
                            'source': '사람인',
                            'company_name': company_name,
                            'title': title,
                            'url': job_url,
                            'skills': skills,
                            'location': location,
                            'conditions': conditions_text,
                            'description': f'{title} - {company_name}',
                        })
                    except Exception:
                        continue
                return page_jobs
            except Exception as e:
                print(f'⚠️ 사람인 {page}페이지 크롤링 실패: {e}')
                return []

        # 3페이지 병렬 요청
        jobs = []
        with ThreadPoolExecutor(max_workers=3) as ex:
            futures = [ex.submit(fetch_page, p) for p in range(1, 4)]
            for f in as_completed(futures):
                jobs.extend(f.result())

        # URL 중복 제거
        seen_urls = set()
        unique_jobs = []
        for job in jobs:
            if job['url'] and job['url'] not in seen_urls:
                seen_urls.add(job['url'])
                unique_jobs.append(job)

        print(f'  사람인 크롤링 총 {len(unique_jobs)}개 수집')
        return unique_jobs[:limit]

    def _fetch_job_detail(self, url):
        """개별 공고 페이지에서 기술 키워드 + 상세 텍스트 추출"""
        import re
        if not url:
            return {'skills': [], 'detail_text': ''}
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            }
            response = requests.get(url, headers=headers, timeout=8)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')

            # 상세 텍스트 추출 (공고 본문 영역)
            detail_text = ''
            detail_area = soup.select_one('.user_content') or soup.select_one('.wrap_jv_cont') or soup.select_one('.jv_detail')
            if detail_area:
                detail_text = detail_area.get_text(separator='\n', strip=True)
            if not detail_text:
                detail_text = soup.get_text(separator='\n', strip=True)
            # 너무 길면 앞부분만 (LLM 토큰 절약)
            if len(detail_text) > 2000:
                detail_text = detail_text[:2000]

            # 기술 키워드 추출
            text = soup.get_text()
            tech_keywords = [
                # 언어
                'Python', 'Java', 'JavaScript', 'TypeScript', 'C\\+\\+', 'C#', 'Go', 'Kotlin',
                'Swift', 'Ruby', 'PHP', 'Rust', 'Scala', 'Dart', 'Perl', 'R',
                # 웹 프레임워크
                'Django', 'Flask', 'FastAPI', 'Spring', 'SpringBoot', 'Spring Boot',
                'React', 'Vue', 'Angular', 'Next\\.js', 'Nuxt', 'Express', 'Node\\.js',
                'Nest\\.js', 'Svelte', 'Flutter', 'Laravel', 'Rails',
                # 데이터/ML
                'pandas', 'NumPy', 'scikit-learn', 'TensorFlow', 'PyTorch', 'Keras',
                'OpenCV', 'Matplotlib', 'XGBoost', 'LightGBM', 'Spark', 'Hadoop',
                'Airflow', 'dbt', 'Tableau', 'Power BI',
                # AI/LLM
                'LangChain', 'HuggingFace', 'Hugging Face', 'OpenAI', 'GPT',
                'LLM', 'RAG', 'Transformers',
                # DB
                'MySQL', 'PostgreSQL', 'MongoDB', 'Redis', 'Oracle', 'MariaDB',
                'Elasticsearch', 'DynamoDB', 'Cassandra', 'SQLite', 'Firebase',
                'Supabase', 'Pinecone', 'ChromaDB',
                # 인프라/DevOps
                'AWS', 'Azure', 'GCP', 'Docker', 'Kubernetes', 'Jenkins',
                'Terraform', 'Ansible', 'Nginx', 'Apache',
                'GitHub Actions', 'GitLab', 'ArgoCD', 'Prometheus', 'Grafana',
                # 메시징/통신
                'Kafka', 'RabbitMQ', 'gRPC', 'GraphQL', 'REST',
                # 기타
                'Git', 'Linux', 'Selenium', 'Celery', 'Jira', 'Figma',
            ]
            found = []
            for kw in tech_keywords:
                display = kw.replace('\\+\\+', '++').replace('\\.', '.')
                if re.search(r'(?<![a-zA-Z])' + kw + r'(?![a-zA-Z])', text, re.IGNORECASE):
                    found.append(display)
            return {'skills': found, 'detail_text': detail_text}
        except Exception:
            return {'skills': [], 'detail_text': ''}

    def _enrich_jobs_with_detail(self, jobs):
        """개별 공고 페이지를 5개씩 병렬 파싱하여 스킬 + 상세 텍스트 보완"""
        from concurrent.futures import ThreadPoolExecutor, as_completed

        def enrich_one(job):
            detail = self._fetch_job_detail(job.get('url', ''))
            # 스킬 보완
            if detail['skills']:
                existing_lower = {s.lower() for s in job.get('skills', [])}
                new_skills = [s for s in detail['skills'] if s.lower() not in existing_lower]
                job['skills'] = job.get('skills', []) + new_skills
            # 상세 텍스트 저장
            job['detail_text'] = detail['detail_text']
            return job

        enriched = []
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = {executor.submit(enrich_one, job): job for job in jobs}
            for future in as_completed(futures):
                try:
                    enriched.append(future.result())
                except Exception:
                    enriched.append(futures[future])
        return enriched


    def _match_jobs_with_skills(self, job_listings, user_skills, skill_levels, readiness_score, current_job_text=''):
        """
        SKILL_SYNONYMS 기반 스킬 매칭.
        정규화(동의어 사전)를 통해 표기가 다른 동일 기술도 매칭.
        예: "React.js" ↔ "리액트", "Node.js" ↔ "nodejs"
        match_rate = 매칭된 스킬 수 / 공고 요구 스킬 수 (공고 커버리지)
        """
        # 사용자 스킬을 {정규화값: 원본명} 매핑으로 구성
        user_skills_map = {}
        for s in user_skills:
            norm = self._normalize_skill(s)
            if norm not in user_skills_map:
                user_skills_map[norm] = s

        recommendations = []

        for job in job_listings:
            job_skills = job.get('skills', [])
            if not job_skills:
                continue

            matched_skills = []
            matched_norms = set()
            for job_skill in job_skills:
                norm = self._normalize_skill(job_skill)
                if norm in user_skills_map and norm not in matched_norms:
                    matched_skills.append({
                        'job_skill': job_skill,
                        'user_skill': user_skills_map[norm],
                        'similarity': 1.0,
                        'match_type': 'synonym' if job_skill.lower() != user_skills_map[norm].lower() else 'exact'
                    })
                    matched_norms.add(norm)

            matched_count = len(matched_skills)
            total_job_skills = len(job_skills)
            match_rate = round(matched_count / total_job_skills, 3) if total_job_skills > 0 else 0.0

            company_name = job['company_name']
            print(f'  📊 {company_name} | 매칭: {matched_count}/{total_job_skills} ({match_rate*100:.0f}%)')

            recommendations.append({
                'source': job.get('source', ''),
                'company_name': job['company_name'],
                'title': job['title'],
                'url': job['url'],
                'skills': job_skills,
                'location': job.get('location', ''),
                'match_rate': match_rate,
                'matched_skills': matched_skills,
                'matched_count': matched_count,
                'total_skills': total_job_skills,
                'detail_text': job.get('detail_text', ''),
                'reason': self._generate_recommendation_reason(matched_count, total_job_skills)
            })

        recommendations.sort(key=lambda x: x['match_rate'], reverse=True)
        return recommendations

    def _generate_recommendation_reason(self, matched_count, total_skills):
        """추천 이유 생성 (실제 스킬 매칭 기반)"""
        match_pct = int(matched_count / total_skills * 100) if total_skills > 0 else 0
        if match_pct >= 70:
            return f"요구 스킬 {matched_count}/{total_skills}개를 보유하고 있어 합격 가능성이 높습니다."
        elif match_pct >= 40:
            return f"요구 스킬 {matched_count}/{total_skills}개 보유 중. 부족한 스킬을 보완하면 충분히 지원 가능합니다."
        else:
            return f"같은 분야 공고로, 스킬을 보완하면 도전 가능한 포지션입니다."

    def _evaluate_with_llm(self, candidates, user_profile):
        """
        LLM으로 후보 공고와 사용자 프로필의 종합 적합도 평가.
        스킬 1차 필터를 통과한 상위 15개 후보에 대해서만 호출.
        """
        from concurrent.futures import ThreadPoolExecutor, as_completed

        api_key = os.environ.get("OPENAI_API_KEY")
        llm_client = openai.OpenAI(api_key=api_key)

        def evaluate_one(candidate):
            # 기술 매칭 점수: 객관적 계산 (40점 만점)
            matched_count = candidate.get('matched_count', 0)
            total_skills = candidate.get('total_skills', 1)
            skill_score = round(min(matched_count / total_skills, 1.0) * 40) if total_skills > 0 else 0

            detail_text = candidate.get('detail_text', '')
            if not detail_text:
                # 상세 텍스트 없으면 스킬 점수만으로 산출
                candidate['skill_score'] = skill_score
                candidate['experience_score'] = 0
                candidate['project_score'] = 0
                candidate['llm_score'] = skill_score
                return candidate

            prompt = f"""당신은 채용 적합도 평가 전문가입니다.

아래 [채용공고]와 [지원자 프로필]을 비교하여 경력과 프로젝트 적합도만 평가하세요.
(기술 스택 일치도는 별도로 계산하므로 평가하지 마세요)

[채용공고]
회사: {candidate['company_name']}
제목: {candidate['title']}
상세내용:
{detail_text}

[지원자 프로필]
경력: {user_profile.get('experience_summary', '정보 없음')}
프로젝트: {user_profile.get('projects_summary', '정보 없음')}
핵심 성과: {user_profile.get('achievements_summary', '정보 없음')}

다음 기준별 배점으로 평가하세요:
1. 경력 적합도 (30점 만점): 경력 내용이 공고 업무와 관련 있는지
2. 프로젝트 관련성 (30점 만점): 수행한 프로젝트가 공고 업무에 도움이 되는지

반드시 아래 JSON 형식으로만 응답하세요:
{{"requirements_summary": "이 공고가 원하는 인재상/주요 요구사항을 2-3문장으로 요약 (공고 내용 기반)", "experience_score": 0~30 정수, "project_score": 0~30 정수, "reason": "이 지원자에게 적합한 이유를 구체적 근거 기반으로 2-3문장으로 작성"}}"""

            try:
                response = llm_client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[{"role": "user", "content": prompt}],
                    response_format={"type": "json_object"},
                    temperature=0,
                    max_tokens=600,
                )
                result = json.loads(response.choices[0].message.content)
                exp_score = min(result.get('experience_score', 0), 30)
                proj_score = min(result.get('project_score', 0), 30)
                total = skill_score + exp_score + proj_score

                candidate['skill_score'] = skill_score
                candidate['experience_score'] = exp_score
                candidate['project_score'] = proj_score
                candidate['llm_score'] = total
                candidate['reason'] = result.get('reason', candidate.get('reason', ''))
                candidate['requirements_summary'] = result.get('requirements_summary', '')
                print(f"  🤖 {candidate['company_name']} | 기술:{skill_score}/40(객관) 경력:{exp_score}/30 프로젝트:{proj_score}/30 = 총:{total}점")
            except Exception as e:
                print(f"  ⚠️ LLM 평가 실패 ({candidate['company_name']}): {e}")
                candidate['skill_score'] = skill_score
                candidate['experience_score'] = 0
                candidate['project_score'] = 0
                candidate['llm_score'] = skill_score
            return candidate

        # 최대 5개 병렬 평가
        evaluated = []
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = {executor.submit(evaluate_one, c): c for c in candidates}
            for future in as_completed(futures):
                try:
                    evaluated.append(future.result())
                except Exception:
                    evaluated.append(futures[future])

        # LLM 점수 기준으로 정렬
        evaluated.sort(key=lambda x: x.get('llm_score', 0), reverse=True)
        return evaluated


JOB_SITE_DOMAINS = [
    'saramin.co.kr', 'jobkorea.co.kr', 'wanted.co.kr',
    'linkedin.com', 'jumpit.co.kr', 'programmers.co.kr',
    'incruit.com', 'rocketpunch.com'
]


@method_decorator(csrf_exempt, name='dispatch')
class JobPlannerCompanyAnalyzeView(APIView):
    """
    기업 분석 API
    - URL 크롤링 또는 텍스트 입력으로 회사 정보 수집
    - LLM으로 종합 분석:
      1. 회사 개요 및 비전
      2. 기술 스택 및 개발 문화
      3. 성장성 및 안정성
      4. 복지 및 근무환경
    """
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        try:
            input_type = request.data.get('type')  # 'url' or 'text'
            company_name = request.data.get('company_name', '회사')

            # 회사 정보 수집
            if input_type == 'url':
                company_info = self._fetch_from_url(request.data.get('url'))
            elif input_type == 'text':
                company_info = request.data.get('text', '')
            else:
                return Response({
                    "error": "Invalid input type. Use 'url' or 'text'."
                }, status=status.HTTP_400_BAD_REQUEST)

            # 크롤링 결과 로그 출력
            print(f"📄 크롤링 결과 ({len(company_info) if company_info else 0}자):")
            print(company_info[:1000] if company_info else "(없음)")
            print("--- 크롤링 끝 ---")

            # LLM으로 종합 분석
            analysis = self._analyze_company_with_llm(company_name, company_info)

            return Response(analysis, status=status.HTTP_200_OK)

        except Exception as e:
            print(f"❌ 기업분석 에러: {e}")
            print(traceback.format_exc())
            return Response({
                "error": f"기업분석 중 오류 발생: {str(e)}"
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def _fetch_from_url(self, url):
        """URL에서 회사 정보 크롤링"""
        if not url:
            raise Exception("URL이 필요합니다.")

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }

        # 채용 사이트 -> BeautifulSoup 방식
        if any(domain in url for domain in JOB_SITE_DOMAINS):
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            for tag in soup(["script", "style"]):
                tag.decompose()
            text = soup.get_text(separator='\n', strip=True)

            # 결과가 너무 짧으면 trafilatura로 fallback
            if len(text) < 200:
                import trafilatura
                fallback = trafilatura.extract(response.text)
                if fallback:
                    return fallback

            return text

        # 일반 사이트(회사 홈페이지, 뉴스, 블로그 등) -> trafilatura
        import trafilatura
        downloaded = trafilatura.fetch_url(url)
        text = trafilatura.extract(downloaded)
        if not text:
            raise Exception("URL에서 텍스트를 추출할 수 없습니다.")
        return text

    def _analyze_company_with_llm(self, company_name, company_info):
        """LLM으로 기업 종합 분석 (크롤링 정보 부족 시 웹서치 보충)"""
        api_key = os.getenv('OPENAI_API_KEY')
        if not api_key:
            return {
                "error": "OPENAI_API_KEY가 설정되지 않았습니다.",
                "company_name": company_name,
                "overview": "",
                "tech_stack": {},
                "growth": {},
                "welfare": {}
            }

        json_format = f"""{{
  "company_name": "{company_name}",
  "overview": {{
    "description": "회사 소개 (2-3문장)",
    "vision": "비전 및 미션",
    "industry": "산업 분야",
    "founded_year": "설립연도 (알 수 없으면 null)",
    "size": "회사 규모 (예: 50-100명)"
  }},
  "tech_stack": {{
    "languages": ["주요 프로그래밍 언어"],
    "frameworks": ["주요 프레임워크"],
    "tools": ["개발 도구 및 협업 툴"],
    "culture": "개발 문화 설명 (2-3문장)",
    "tech_blog": "기술 블로그 활동 여부 및 평가"
  }},
  "growth": {{
    "funding": "투자 유치 현황",
    "market_position": "시장 위치 및 경쟁력"
  }},
  "welfare": {{
    "salary_level": "연봉 수준 (평균 또는 범위)",
    "benefits": ["복지 혜택 리스트"],
    "work_life_balance": "워라밸 평가 및 설명",
    "remote_work": "리모트 근무 가능 여부"
  }},
  "recommendation": "이 회사에 지원하면 좋은 이유 또는 주의사항 (3-4문장)"
}}"""

        try:
            client = openai.OpenAI(api_key=api_key)
            use_web_search = not company_info or len(company_info.strip()) < 200

            if use_web_search:
                # 크롤링 정보 부족 -> Responses API + web_search로 실시간 검색
                print(f"🔍 크롤링 정보 부족 ({len(company_info.strip()) if company_info else 0}자) -> 웹서치 사용")
                response = client.responses.create(
                    model="gpt-4o-mini",
                    tools=[{"type": "web_search_preview"}],
                    input=f"""당신은 IT 기업 분석 전문가입니다.
"{company_name}" 회사에 대해 웹 검색을 수행하여 다음 정보를 수집하고 JSON 형식으로 반환하세요.
검색 키워드 예시: "{company_name} 기술스택", "{company_name} 복지", "{company_name} 채용", "{company_name} 투자"

중요: 검색 결과에서 확인할 수 없는 정보는 절대 추측하거나 지어내지 마세요. 확인되지 않은 항목은 문자열이면 null, 리스트면 빈 배열 []로 남겨주세요.

반드시 아래 JSON 형식만 반환하세요:
{json_format}"""
                )
                content = response.output_text
            else:
                # 크롤링 정보 충분 -> 기존 Chat Completions 방식
                response = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {
                            "role": "system",
                            "content": """당신은 IT 기업 분석 전문가입니다.
회사 정보를 바탕으로 다음 4가지 항목을 분석하여 JSON 형식으로 반환하세요:
1. 회사 개요 및 비전
2. 기술 스택 및 개발 문화
3. 성장성 및 안정성
4. 복지 및 근무환경

중요: 제공된 정보에서 확인할 수 없는 항목은 절대 추측하거나 지어내지 마세요. 확인되지 않은 항목은 문자열이면 null, 리스트면 빈 배열 []로 남겨주세요."""
                        },
                        {
                            "role": "user",
                            "content": f"""다음 회사 정보를 분석해주세요:

회사명: {company_name}

정보:
{company_info[:3000]}

JSON 형식으로 반환:
{json_format}"""
                        }
                    ],
                    temperature=0.5
                )
                content = response.choices[0].message.content

            # JSON 추출
            if '```json' in content:
                content = content.split('```json')[1].split('```')[0].strip()
            elif '```' in content:
                content = content.split('```')[1].split('```')[0].strip()

            analysis = json.loads(content)
            return analysis

        except Exception as e:
            print(f"⚠️  LLM 기업분석 실패: {e}")
            return {
                "error": f"분석 실패: {str(e)}",
                "company_name": company_name,
                "overview": {"description": "정보 부족", "vision": "", "industry": "", "founded_year": None, "size": ""},
                "tech_stack": {"languages": [], "frameworks": [], "tools": [], "culture": "", "tech_blog": ""},
                "growth": {"funding": "", "market_position": ""},
                "welfare": {"salary_level": "", "benefits": [], "work_life_balance": "", "remote_work": ""},
                "recommendation": "정보가 부족하여 분석할 수 없습니다."
            }


@method_decorator(csrf_exempt, name='dispatch')
class JobPlannerParseResumeView(APIView):
    """
    이력서/자기소개서/포트폴리오 PDF 파싱 API

    세 종류의 서류를 병렬로 분석하여 사용자 프로필을 자동 추출합니다.
    - 자기소개서: pdfplumber 텍스트 추출 -> GPT 텍스트 분석
    - 이력서: PDF->이미지 변환 -> Vision API (표 형식 대응)
    - 포트폴리오: PDF->이미지 변환 -> Vision API
    세 작업을 ThreadPoolExecutor로 병렬 실행 후 LLM으로 결과 병합.
    """
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        from concurrent.futures import ThreadPoolExecutor

        resume_pdf = request.data.get('resume')
        cover_letter_pdf = request.data.get('cover_letter')
        portfolio_pdf = request.data.get('portfolio')
        career_desc_pdf = request.data.get('career_description')
        # 이전에 파싱된 다른 서류의 개별 결과 (부분 업데이트 시 사용)
        existing_doc_results = request.data.get('existing_doc_results', {})
        if isinstance(existing_doc_results, str):
            existing_doc_results = json.loads(existing_doc_results)

        if not any([resume_pdf, cover_letter_pdf, portfolio_pdf, career_desc_pdf]):
            return Response(
                {"error": "이력서, 자기소개서, 포트폴리오, 경력기술서 중 최소 하나를 업로드해주세요."},
                status=status.HTTP_400_BAD_REQUEST
            )

        api_key = os.getenv('OPENAI_API_KEY')
        if not api_key:
            return Response(
                {"error": "OPENAI_API_KEY가 설정되지 않았습니다."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        try:
            results = {}
            tasks = {}

            with ThreadPoolExecutor(max_workers=4) as executor:
                if cover_letter_pdf:
                    tasks['cover_letter'] = executor.submit(
                        self._parse_cover_letter, cover_letter_pdf, api_key
                    )
                if resume_pdf:
                    tasks['resume'] = executor.submit(
                        self._parse_resume, resume_pdf, api_key
                    )
                if portfolio_pdf:
                    tasks['portfolio'] = executor.submit(
                        self._parse_with_vision, portfolio_pdf, api_key, 'portfolio'
                    )
                if career_desc_pdf:
                    tasks['career_description'] = executor.submit(
                        self._parse_career_description, career_desc_pdf, api_key
                    )

                for key, future in tasks.items():
                    try:
                        results[key] = future.result(timeout=60)
                        print(f"✅ {key} 파싱 완료")
                    except Exception as e:
                        print(f"⚠️ {key} 파싱 실패: {e}")
                        results[key] = {}

            # 기존 서류 결과 + 새로 파싱한 결과 합치기 (새 결과가 우선)
            all_results = {**existing_doc_results, **results}

            merged = self._merge_results(all_results, api_key)
            # 개별 서류 파싱 결과를 반환 (프론트에서 부분 업데이트 시 재사용)
            merged['_doc_results'] = all_results
            # 포트폴리오 개별 파싱 결과를 별도로 포함 (리뷰 시 재파싱 방지)
            portfolio_result = all_results.get('portfolio')
            if portfolio_result:
                merged['_portfolio_parsed'] = portfolio_result
            return Response(merged, status=status.HTTP_200_OK)

        except Exception as e:
            print(f"❌ 서류 파싱 에러: {e}")
            print(traceback.format_exc())
            return Response(
                {"error": f"서류 분석 중 오류 발생: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def _pdf_to_images(self, pdf_base64, max_pages=10):
        """PDF를 JPEG 이미지 base64 리스트로 변환 (PyMuPDF)"""
        import fitz

        raw = pdf_base64.split(',')[-1]
        pdf_bytes = base64.b64decode(raw)
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")

        images = []
        for i, page in enumerate(doc):
            if i >= max_pages:
                break
            mat = fitz.Matrix(2, 2)  # 2배 해상도
            pix = page.get_pixmap(matrix=mat)
            img_b64 = base64.b64encode(pix.tobytes("jpeg")).decode()
            images.append(f"data:image/jpeg;base64,{img_b64}")

        doc.close()
        return images

    def _extract_pdf_text(self, pdf_base64):
        """PDF에서 텍스트 추출 (pdfplumber)"""
        import pdfplumber, io

        raw = pdf_base64.split(',')[-1]
        pdf_bytes = base64.b64decode(raw)
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            text = "\n".join(page.extract_text() or "" for page in pdf.pages)
        return text.strip()

    def _parse_resume(self, pdf_base64, api_key):
        """이력서: 텍스트 추출 우선 -> 부족하면 Vision API fallback"""
        RESUME_PROMPT = """이력서에서 추출 가능한 모든 정보를 JSON으로 추출하세요.
없는 정보는 null 또는 빈 배열로 반환하세요.
학력은 "학교명-학과(전공)" 형식으로 작성하세요.

JSON 형식:
{{
  "name": "이름 또는 null",
  "email": "이메일 또는 null",
  "phone": "연락처 또는 null",
  "current_role": "현재 직무 또는 null",
  "education": "학교명-학과(전공) 형식 또는 null (예: 서울대학교-컴퓨터공학과(컴퓨터공학))",
  "certifications": ["자격증 목록"],
  "skills": ["기술 스택 목록 (최대한 많이)"],
  "languages": [{{"language": "언어명", "level": "수준 (예: 비즈니스, 일상, 원어민)"}}],
  "awards": ["수상 경력 목록"],
  "experience_years": 총 경력 연수(숫자) 또는 null,
  "work_experience": [{{"company": "회사명", "role": "직책", "period": "재직기간", "description": "담당업무 요약", "skills": ["해당 업무에서 사용한 기술/도구"]}}],
  "projects": [{{"name": "프로젝트명", "description": "설명", "skills": ["사용기술"], "achievements": ["성과/결과"]}}],
  "training": [{{"name": "교육명", "institution": "기관명 또는 null", "period": "기간 또는 null"}}],
  "github_url": "GitHub URL 또는 null",
  "portfolio_url": "포트폴리오 사이트 URL 또는 null"
}}"""

        # 1차: pdfplumber 텍스트 추출
        text = self._extract_pdf_text(pdf_base64)

        if len(text) >= 100:
            # 텍스트 충분 -> gpt-4o-mini로 빠르게 처리
            print("📄 이력서: 텍스트 추출 성공 -> gpt-4o-mini 사용")
            client = openai.OpenAI(api_key=api_key)
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{
                    "role": "user",
                    "content": f"{RESUME_PROMPT}\n\n이력서 내용:\n{text}"
                }],
                response_format={"type": "json_object"},
                temperature=0.1
            )
            return json.loads(response.choices[0].message.content)
        else:
            # 텍스트 부족 (스캔본/이미지 PDF) -> Vision API fallback
            print("🖼️ 이력서: 텍스트 부족 -> Vision API fallback")
            images = self._pdf_to_images(pdf_base64)
            if not images:
                return {}
            client = openai.OpenAI(api_key=api_key)
            content = [{"type": "text", "text": RESUME_PROMPT}]
            for img in images:
                content.append({"type": "image_url", "image_url": {"url": img}})
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": content}],
                max_tokens=2000,
                temperature=0.1
            )
            raw = response.choices[0].message.content
            if '```json' in raw:
                raw = raw.split('```json')[1].split('```')[0].strip()
            elif '```' in raw:
                raw = raw.split('```')[1].split('```')[0].strip()
            return json.loads(raw)

    def _parse_cover_letter(self, pdf_base64, api_key):
        """자기소개서: 텍스트 추출 후 GPT로 구조화"""
        text = self._extract_pdf_text(pdf_base64)
        if not text:
            return {}

        client = openai.OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{
                "role": "user",
                "content": f"""아래는 자기소개서 내용입니다. 추출 가능한 모든 정보를 JSON으로 추출하세요.
없는 정보는 null 또는 빈 배열로 반환하세요.
학력은 "학교명-학과(전공)" 형식으로 작성하세요.

자기소개서:
{text}

JSON 형식:
{{
  "name": "이름 또는 null",
  "email": "이메일 또는 null",
  "phone": "연락처 또는 null",
  "current_role": "현재 직무 또는 null",
  "education": "학교명-학과(전공) 형식 또는 null (예: 서울대학교-컴퓨터공학과(컴퓨터공학))",
  "certifications": ["자격증 목록"],
  "skills": ["언급된 기술 스택 목록"],
  "languages": [{{"language": "언어명", "level": "수준"}}],
  "awards": ["수상 경력 목록"],
  "experience_years": 총 경력 연수(숫자) 또는 null,
  "work_experience": [{{"company": "회사명", "role": "직책", "period": "재직기간", "description": "담당업무 요약", "skills": ["해당 업무에서 사용한 기술/도구"]}}],
  "projects": [{{"name": "프로젝트명", "description": "설명", "skills": ["사용기술"], "achievements": ["성과 또는 결과"]}}],
  "training": [{{"name": "교육명", "institution": "기관명 또는 null", "period": "기간 또는 null"}}],
  "key_achievements": ["핵심 성과 목록"],
  "career_goals": "커리어 목표/지원동기 요약 또는 null",
  "strengths": ["강점 키워드 목록 (성실함, 문제해결능력 등)"],
  "teamwork_experience": "팀 협업 경험 요약 또는 null",
  "growth_story": "성장 과정/배경 요약 또는 null",
  "github_url": "GitHub URL 또는 null",
  "portfolio_url": "포트폴리오 사이트 URL 또는 null"
}}"""
            }],
            response_format={"type": "json_object"},
            temperature=0.1
        )
        return json.loads(response.choices[0].message.content)

    def _parse_career_description(self, pdf_base64, api_key):
        """경력기술서: 텍스트 추출 후 GPT로 구조화"""
        text = self._extract_pdf_text(pdf_base64)
        if not text:
            return {}

        client = openai.OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{
                "role": "user",
                "content": f"""아래는 경력기술서 내용입니다. 추출 가능한 모든 정보를 JSON으로 추출하세요.
없는 정보는 null 또는 빈 배열로 반환하세요.
학력은 "학교명-학과(전공)" 형식으로 작성하세요.

경력기술서:
{text}

JSON 형식:
{{
  "name": "이름 또는 null",
  "email": "이메일 또는 null",
  "phone": "연락처 또는 null",
  "current_role": "현재 직무 또는 null",
  "education": "학교명-학과(전공) 형식 또는 null (예: 서울대학교-컴퓨터공학과(컴퓨터공학))",
  "certifications": ["자격증 목록"],
  "skills": ["사용된 기술 스택 목록"],
  "languages": [{{"language": "언어명", "level": "수준"}}],
  "awards": ["수상 경력 목록"],
  "experience_years": 총 경력 연수(숫자) 또는 null,
  "work_experience": [{{"company": "회사명", "role": "직책/포지션", "period": "재직기간", "description": "담당업무 상세", "achievements": ["주요 성과 (수치 포함)"], "skills": ["사용 기술"]}}],
  "projects": [{{"name": "프로젝트명", "description": "설명", "skills": ["사용기술"], "achievements": ["성과/결과"]}}],
  "training": [{{"name": "교육명", "institution": "기관명 또는 null", "period": "기간 또는 null"}}],
  "key_achievements": ["핵심 성과 목록 (수치 있으면 포함, 예: 서비스 응답시간 40% 개선)"],
  "career_goals": "커리어 목표 또는 null",
  "strengths": ["강점 키워드 목록"],
  "teamwork_experience": "팀 협업 경험 요약 또는 null",
  "growth_story": "성장 과정/배경 요약 또는 null",
  "github_url": "GitHub URL 또는 null",
  "portfolio_url": "포트폴리오 사이트 URL 또는 null"
}}"""
            }],
            response_format={"type": "json_object"},
            temperature=0.1
        )
        return json.loads(response.choices[0].message.content)

    def _parse_with_vision(self, pdf_base64, api_key, doc_type):
        """이력서/포트폴리오: Vision API로 파싱"""
        images = self._pdf_to_images(pdf_base64)
        if not images:
            return {}

        prompts = {
            'resume': """이력서 이미지에서 추출 가능한 모든 정보를 JSON으로 추출하세요.
없는 정보는 null 또는 빈 배열로 반환하세요.

JSON 형식:
{
  "name": "이름 또는 null",
  "email": "이메일 또는 null",
  "phone": "연락처 또는 null",
  "current_role": "현재 직무 또는 null",
  "education": "학교명-학과(전공) 형식 또는 null (예: 서울대학교-컴퓨터공학과(컴퓨터공학))",
  "certifications": ["자격증 목록"],
  "skills": ["기술 스택 목록 (최대한 많이)"],
  "languages": [{"language": "언어명", "level": "수준 (예: 비즈니스, 일상, 원어민)"}],
  "awards": ["수상 경력 목록"],
  "experience_years": 총 경력 연수(숫자) 또는 null,
  "work_experience": [{"company": "회사명", "role": "직책", "period": "재직기간", "description": "담당업무 요약", "skills": ["해당 업무에서 사용한 기술/도구"]}],
  "projects": [{"name": "프로젝트명", "description": "설명", "skills": ["사용기술"], "achievements": ["성과/결과"]}],
  "training": [{"name": "교육명", "institution": "기관명 또는 null", "period": "기간 또는 null"}],
  "github_url": "GitHub URL 또는 null",
  "portfolio_url": "포트폴리오 사이트 URL 또는 null"
}""",
            'portfolio': """포트폴리오 이미지에서 추출 가능한 모든 정보를 JSON으로 추출하세요.
없는 정보는 null 또는 빈 배열로 반환하세요.
학력은 "학교명-학과(전공)" 형식으로 작성하세요.

JSON 형식:
{
  "name": "이름 또는 null",
  "email": "이메일 또는 null",
  "phone": "연락처 또는 null",
  "current_role": "현재 직무 또는 null",
  "education": "학교명-학과(전공) 형식 또는 null (예: 서울대학교-컴퓨터공학과(컴퓨터공학))",
  "certifications": ["자격증 목록"],
  "skills": ["사용된 기술 스택 (최대한 많이)"],
  "languages": [{"language": "언어명", "level": "수준"}],
  "awards": ["수상 경력 목록"],
  "experience_years": 총 경력 연수(숫자) 또는 null,
  "work_experience": [{"company": "회사명", "role": "직책", "period": "재직기간", "description": "담당업무 요약", "skills": ["해당 업무에서 사용한 기술/도구"]}],
  "projects": [{"name": "프로젝트명", "description": "설명", "skills": ["사용기술"], "achievements": ["성과 지표 (예: MAU 10만, 응답시간 50% 개선)"]}],
  "training": [{"name": "교육명", "institution": "기관명 또는 null", "period": "기간 또는 null"}],
  "key_achievements": ["핵심 성과 목록"],
  "career_goals": "커리어 목표 또는 null",
  "strengths": ["강점 키워드 목록"],
  "teamwork_experience": "팀 협업 경험 요약 또는 null",
  "growth_story": "성장 과정/배경 요약 또는 null",
  "github_url": "GitHub URL 또는 null",
  "portfolio_url": "포트폴리오 사이트 URL 또는 null"
}"""
        }

        content = [{"type": "text", "text": prompts[doc_type]}]
        for img in images:
            content.append({"type": "image_url", "image_url": {"url": img}})

        client = openai.OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": content}],
            max_tokens=2000,
            temperature=0.1
        )

        raw = response.choices[0].message.content
        if '```json' in raw:
            raw = raw.split('```json')[1].split('```')[0].strip()
        elif '```' in raw:
            raw = raw.split('```')[1].split('```')[0].strip()

        return json.loads(raw)

    def _merge_results(self, results, api_key):
        """여러 서류 결과를 LLM으로 병합하여 최종 프로필 생성"""
        client = openai.OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{
                "role": "user",
                "content": f"""다음은 여러 서류에서 추출한 정보입니다. 통합하여 가장 완전한 프로필을 만들어주세요.

서류별 추출 결과:
{json.dumps(results, ensure_ascii=False, indent=2)}

통합 규칙:
- user_skills: 모든 서류의 스킬 합집합 (중복 제거, 영문 표준명으로 통일)
- skill_levels: user_skills의 각 스킬을 문서 전체 맥락으로 1~5 추정 (1:입문, 2:초급, 3:실무가능, 4:능숙, 5:전문가). 경력연수/프로젝트 규모/성과 수치 등을 참고하여 추정, 근거 없으면 3
- projects: 포트폴리오 > 경력기술서 > 이력서 순서로 우선, 중복은 더 상세한 것 선택
- work_experience: 경력기술서 > 이력서 순서로 우선
- key_achievements: 경력기술서 우선, 나머지에서 추가
- career_goals: 자기소개서 우선
- strengths: 자기소개서 우선
- training: 모든 서류의 교육 이수 내역 합집합 (중복 제거)
- education: 값이 있는 것 우선, "학교명-학과(전공)" 형식으로 통일
- github_url / portfolio_url: 있는 것 사용
- 그 외 필드: 값이 있는 것 우선, 없으면 null

반환 JSON 형식:
{{
  "name": null,
  "email": null,
  "phone": null,
  "current_role": null,
  "education": null,
  "certifications": [],
  "career_goals": null,
  "experience_years": 0,
  "languages": [],
  "awards": [],
  "strengths": [],
  "work_experience": [],
  "key_achievements": [],
  "user_skills": [],
  "skill_levels": {{}},
  "training": [],
  "projects": [],
  "github_url": null,
  "portfolio_url": null,
  "teamwork_experience": null,
  "growth_story": null
}}"""
            }],
            response_format={"type": "json_object"},
            temperature=0.1
        )
        merged = json.loads(response.choices[0].message.content)

        # skill_levels 누락된 스킬은 3(실무가능)으로 보완
        skills = merged.get("user_skills", [])
        skill_levels = merged.get("skill_levels", {})
        for skill in skills:
            if skill not in skill_levels:
                skill_levels[skill] = 3
        merged["skill_levels"] = skill_levels

        return merged


@method_decorator(csrf_exempt, name='dispatch')
class JobPlannerReviewPortfolioView(APIView):
    """채용공고 기준 포트폴리오 개선점 분석 API (파싱된 데이터 기반)"""
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        job_data = request.data.get('job_data', {})
        portfolio_parsed = request.data.get('portfolio_parsed', {})

        if not portfolio_parsed:
            return Response(
                {"error": "포트폴리오 파싱 데이터가 없습니다. 서류 분석을 먼저 진행해주세요."},
                status=status.HTTP_400_BAD_REQUEST
            )

        api_key = os.getenv('OPENAI_API_KEY')
        if not api_key:
            return Response({"error": "OPENAI_API_KEY가 설정되지 않았습니다."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        try:
            client = openai.OpenAI(api_key=api_key)

            # 파싱된 포트폴리오 데이터를 텍스트로 구성
            portfolio_content = json.dumps(portfolio_parsed, ensure_ascii=False, indent=2)

            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": """당신은 IT 채용 포트폴리오 전문 리뷰어입니다.

[분석 방법론]
1. 공고의 각 요구사항(필수 스킬, 우대 스킬, 업무 내용)을 하나씩 꺼내서, 포트폴리오의 경험 중 대응되는 것을 1:1 매칭합니다.
2. 매칭된 경험의 서술 완성도를 아래 기준으로 평가합니다:
   - 실무 경력: STAR 기법(Situation→Task→Action→Result) 기준. 상황, 과제, 행동, 정량적 성과가 모두 있는지 확인.
   - 팀 프로젝트: 본인 담당 범위, 기술 선택 이유, 협업 방식이 명확한지 확인.
   - 개인/학습 프로젝트: 만든 동기, 겪은 문제와 해결 과정, 배운 점이 있는지 확인.
3. 매칭되지 않는 요구사항은 포트폴리오의 유사 경험에서 연결고리를 찾아 대체 어필 방법을 제안합니다.
4. 모든 조언에는 반드시 "현재 서술(as_is)"과 "개선 서술(to_be)"을 대비하여 제시합니다.
5. 포트폴리오에서 추출된 프로젝트, 기술스택, 성과 등을 꼼꼼히 분석합니다.

[필수 규칙]
- "프로젝트 설명을 보강하세요", "기술 스택을 강조하세요" 같은 추상적 조언 금지
- 반드시 포트폴리오의 특정 프로젝트명 또는 경력사항을 지목하여 조언할 것
- 반드시 공고의 어떤 요구사항에 대응하는 조언인지 명시할 것
- 정량적 성과가 없는 프로젝트는 해당 프로젝트에서 측정 가능한 수치가 무엇인지 구체적으로 제안할 것
- to_be는 포트폴리오에 바로 붙여넣을 수 있는 수준의 완성된 문장을 작성할 것
- to_be에 공고에서 사용된 키워드를 자연스럽게 포함할 것

[Few-shot 예시 — improvements 작성법]

❌ 나쁜 예시 (추상적):
{
  "target": "실시간 감성 분석 대시보드",
  "issue": "프론트엔드 성능 최적화 경험이 부족합니다.",
  "as_is": "React를 사용하여 대시보드를 개발했습니다.",
  "to_be": "성능 최적화 사례를 추가하세요."
}

✅ 좋은 예시 (구체적):
{
  "target": "실시간 감성 분석 대시보드",
  "issue": "공고에서 요구하는 '대규모 트래픽 처리 경험'에 대한 서술이 없습니다. 현재는 단순 기능 나열에 그치고 있어 성능 관점의 기술적 깊이가 드러나지 않습니다.",
  "as_is": "React와 Chart.js를 활용하여 실시간 감성 분석 결과를 시각화하는 대시보드를 개발했습니다.",
  "to_be": "React.memo와 useMemo를 적용하여 실시간 데이터 스트림(초당 50건) 환경에서 불필요한 리렌더링을 70% 줄이고, React-Query의 staleTime 설정으로 API 호출 빈도를 분당 60회에서 12회로 최적화했습니다. Chart.js canvas 렌더링 시 requestAnimationFrame 기반 배치 업데이트를 도입하여 프레임 드롭 없이 실시간 차트를 구현했습니다."
}

❌ 나쁜 예시 (추상적):
{
  "target": "AI Knowledge Bot",
  "issue": "팀 리드 경험이 부족합니다.",
  "as_is": "팀 프로젝트로 진행했습니다.",
  "to_be": "팀에서의 역할을 구체적으로 서술하세요."
}

✅ 좋은 예시 (구체적):
{
  "target": "AI Knowledge Bot",
  "issue": "공고에서 요구하는 '팀 리더십 및 협업 경험'에 대해, 현재 서술에는 본인의 역할과 기여도가 드러나지 않습니다.",
  "as_is": "4인 팀 프로젝트로 FastAPI 기반 AI 챗봇을 개발했습니다.",
  "to_be": "4인 팀에서 백엔드 리드를 맡아 API 설계와 코드 리뷰를 주도했습니다. 주 2회 기술 미팅을 통해 LangChain RAG 파이프라인의 아키텍처 결정을 이끌었고, GitHub PR 리뷰 프로세스를 도입하여 배포 후 버그를 팀 평균 대비 40% 감소시켰습니다. Notion으로 API 명세서를 문서화하여 프론트엔드 팀과의 통합 일정을 1주 단축했습니다."
}

위 예시처럼 as_is에는 포트폴리오의 실제 서술(또는 서술이 없으면 '해당 내용 없음')을, to_be에는 공고 키워드를 반영한 구체적 개선 문장을 작성하세요."""
                    },
                    {
                        "role": "user",
                        "content": f"""아래 채용공고와 포트폴리오 분석 내용을 1:1 대조 분석하여 포트폴리오 개선 가이드를 제공하세요.

=== 채용공고 ===
회사: {job_data.get('company_name', '')}
포지션: {job_data.get('position', '')}
주요 업무:
{job_data.get('job_responsibilities', '정보 없음')}
필수 요건:
{job_data.get('required_qualifications', '정보 없음')}
필수 스킬: {', '.join(job_data.get('required_skills', []))}
우대 스킬: {', '.join(job_data.get('preferred_skills', []))}
우대 사항:
{job_data.get('preferred_qualifications', '정보 없음')}

=== 포트폴리오 분석 내용 ===
{portfolio_content}

JSON으로 반환하세요:
{{
  "strengths": [
    "공고의 어떤 요구사항에 대해, 포트폴리오의 어떤 내용이 강점인지 구체적으로 (최소 3개)"
  ],
  "improvements": [
    {{
      "target": "개선 대상 (포트폴리오의 특정 프로젝트명 또는 섹션)",
      "issue": "이 공고 기준으로 부족한 점 (공고의 어떤 요구사항에 대응하는지 명시)",
      "as_is": "포트폴리오의 현재 서술 (실제 내용을 인용하거나 요약. 서술이 없으면 '해당 내용 없음')",
      "to_be": "개선된 서술 예시 (포트폴리오에 바로 붙여넣을 수 있는 완성된 문장. 공고 키워드 반영, 정량적 수치 포함)"
    }}
  ],
  "missing": [
    "공고에서 요구하지만 포트폴리오에 없는 경험/스킬과, 이를 포트폴리오에서 보완할 수 있는 방법"
  ],
  "portfolio_structure": [
    "이 공고에 맞는 포트폴리오 구성 순서와 각 섹션에 담을 핵심 내용 (예: '1. 프로젝트A를 메인으로 배치 - OO 업무 경험 강조')"
  ],
  "priority_actions": ["지금 당장 실행할 수 있는 우선순위 높은 액션 3가지"]
}}"""
                    }
                ],
                response_format={"type": "json_object"},
                temperature=0.3
            )

            return Response(
                json.loads(response.choices[0].message.content),
                status=status.HTTP_200_OK
            )

        except Exception as e:
            print(f"❌ 포트폴리오 리뷰 에러: {e}")
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


