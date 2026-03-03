"""
Collector Router

URL을 분석하여 적절한 Collector를 선택합니다.
"""

from .base import BaseCollector
from .static_collector import StaticCollector
from .browser_collector import BrowserCollector
from .saramin_collector import SaraminCollector
from .jobkorea_collector import JobkoreaCollector
from .wanted_collector import WantedCollector


class CollectorRouter:
    """
    수집 전략 선택기

    URL의 특성을 분석하여 가장 적합한 Collector를 반환합니다.

    Phase 3 구현:
    - 사이트별 최적화 Collector (사람인, 잡코리아, 원티드)
    - URL 도메인 분석하여 자동으로 적절한 Collector 선택
    - Fallback 체인: 사이트 최적화 → Static → Browser

    Phase 4+ (예정):
    - OCRCollector 추가 (이미지 대응)
    """

    def __init__(self):
        """
        사용 가능한 Collector들을 초기화합니다.
        """
        # Phase 2: 기본 Collectors
        self.static_collector = StaticCollector()
        self.browser_collector = BrowserCollector()

        # Phase 3: 사이트별 최적화 Collectors
        self.saramin_collector = SaraminCollector()
        self.jobkorea_collector = JobkoreaCollector()
        self.wanted_collector = WantedCollector()

        # Phase 4+: 추가 Collector
        # self.ocr_collector = OCRCollector()

    def route(self, url: str) -> BaseCollector:
        """
        URL에 가장 적합한 Collector를 선택합니다.

        Phase 1 로직:
        - 모든 URL에 대해 StaticCollector 반환

        Phase 2+ 로직 (예정):
        - 사람인/잡코리아 → ApiCollector (빠르고 정확)
        - 원티드/LinkedIn → BrowserCollector (SPA 대응)
        - 기타 → StaticCollector (기본)

        Args:
            url (str): 채용공고 URL

        Returns:
            BaseCollector: 선택된 Collector 인스턴스
        """
        # Phase 1: 항상 StaticCollector 반환
        print(f"[INFO] CollectorRouter: StaticCollector 선택")
        return self.static_collector

        # Phase 2+ 구현 예시 (주석):
        # if 'saramin.co.kr' in url or 'jobkorea.co.kr' in url:
        #     print(f"[INFO] CollectorRouter: ApiCollector 선택 (채용사이트 API)")
        #     return self.api_collector
        # elif 'wanted.co.kr' in url or 'linkedin.com' in url:
        #     print(f"[INFO] CollectorRouter: BrowserCollector 선택 (SPA 사이트)")
        #     return self.browser_collector
        # else:
        #     print(f"[INFO] CollectorRouter: StaticCollector 선택 (기본)")
        #     return self.static_collector

    def collect_with_fallback(self, url: str) -> str:
        """
        여러 Collector를 순차적으로 시도하는 Fallback 체인입니다.

        Phase 3 구현:
        - URL 도메인 분석하여 사이트별 최적화 Collector 우선 시도
        - Fallback 체인: 사이트 최적화 → Static → Browser
        - 의미 있는 콘텐츠 검증 (길이 + 키워드)

        Fallback 체인 예시:
        - 사람인 URL: SaraminCollector → StaticCollector → BrowserCollector
        - 잡코리아 URL: JobkoreaCollector → StaticCollector → BrowserCollector
        - 원티드 URL: WantedCollector → StaticCollector → BrowserCollector
        - 기타 URL: StaticCollector → BrowserCollector

        Args:
            url (str): 채용공고 URL

        Returns:
            str: 추출된 텍스트 (모두 실패 시 빈 문자열)
        """
        # URL 도메인에 따라 Fallback 체인 동적 구성
        collectors = []

        # Phase 3: 사이트별 최적화 Collector 우선 추가
        url_lower = url.lower()
        is_spa = False  # SPA 사이트 여부 (StaticCollector 건너뜀)

        if 'saramin.co.kr' in url_lower:
            print(f"[INFO] 사람인 URL 감지 -> SaraminCollector 우선 시도")
            collectors.append(("Saramin", self.saramin_collector))
        elif 'jobkorea.co.kr' in url_lower:
            # 잡코리아는 SSR이므로 빠른 StaticCollector 먼저 시도, 실패 시 Playwright fallback
            print(f"[INFO] 잡코리아 URL 감지 -> StaticCollector 먼저 시도 (SSR), 실패 시 JobkoreaCollector")
            collectors.append(("Static", self.static_collector))
            collectors.append(("Jobkorea", self.jobkorea_collector))
        elif 'wanted.co.kr' in url_lower:
            is_spa = True
            print(f"[INFO] 원티드 URL 감지 (SPA) -> WantedCollector 우선 시도, StaticCollector 제외")
            collectors.append(("Wanted", self.wanted_collector))

        # SPA 사이트 및 잡코리아(이미 앞에 추가됨)는 StaticCollector 중복 추가 제외
        already_has_static = any(name == "Static" for name, _ in collectors)
        if not is_spa and not already_has_static:
            collectors.append(("Static", self.static_collector))
        collectors.append(("Browser", self.browser_collector))

        # Fallback 체인 순차 실행
        for name, collector in collectors:
            if not collector.can_handle(url):
                print(f"[SKIP] {name}Collector: 이 URL 처리 불가, 스킵")
                continue

            print(f"[TRY] {name}Collector 시도 중...")
            text = collector.collect(url)

            # 의미 있는 콘텐츠인지 검증
            if self._is_valid_content(text):
                print(f"[OK] {name}Collector 성공! ({len(text)}자, 유효한 채용공고 콘텐츠)")
                return text
            else:
                print(f"[WARN] {name}Collector: 유효하지 않은 콘텐츠 ({len(text)}자), 다음 시도...")

        # 모든 Collector 실패
        print(f"[FAIL] 모든 Collector 실패")
        return ""

    def _is_valid_content(self, text: str) -> bool:
        """
        추출된 텍스트가 유효한 채용공고 콘텐츠인지 검증합니다.

        검증 기준:
        1. 최소 길이: 50자 이상
        2. 채용 관련 키워드 포함 (채용, 모집, 경력, 개발 등)
        3. 기술 스택 키워드 포함 (선택)

        Args:
            text (str): 검증할 텍스트

        Returns:
            bool: 유효한 콘텐츠 여부
        """
        if len(text) < 50:
            return False

        text_lower = text.lower()

        # 채용 관련 필수 키워드 (하나 이상 포함되어야 함)
        job_keywords = [
            '채용', '모집', '경력', '신입', '개발', '엔지니어', 'engineer',
            '필수', '우대', '자격', '요건', '업무', '담당', 'developer',
            'recruit', 'hiring', 'position', 'requirements', 'qualifications'
        ]

        has_job_keyword = any(keyword in text_lower for keyword in job_keywords)

        if not has_job_keyword:
            return False

        # 기술 스택 키워드 (선택적, 있으면 더 확실)
        tech_keywords = [
            'python', 'java', 'javascript', 'react', 'vue', 'django',
            'spring', 'aws', 'docker', 'kubernetes', 'sql', 'git',
            '파이썬', '자바', '개발자'
        ]

        has_tech_keyword = any(keyword in text_lower for keyword in tech_keywords)

        # 채용 키워드 O + 기술 키워드 O = 확실한 채용공고
        # 채용 키워드 O + 기술 키워드 X + 충분한 길이 = 채용공고 가능성 높음
        if has_tech_keyword:
            return True
        elif len(text) >= 200:  # 채용 키워드는 있고 텍스트가 충분히 길면 OK
            return True

        return False
