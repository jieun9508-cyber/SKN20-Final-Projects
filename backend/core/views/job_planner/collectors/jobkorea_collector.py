"""
Jobkorea-optimized Collector

잡코리아 채용공고 전용 최적화 Collector입니다.
Playwright를 사용하되, 잡코리아의 HTML 구조에 맞춰 정확한 본문만 추출합니다.
"""

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
from .base import BaseCollector


class JobkoreaCollector(BaseCollector):
    """
    잡코리아 전용 최적화 Collector

    잡코리아 채용공고 페이지의 구조를 정확히 파악하여
    광고, 헤더, 푸터를 제외하고 본문만 추출합니다.

    장점:
    - 노이즈 제거 (광고, 헤더, 푸터 등 제외)
    - 정확한 채용공고 본문만 추출
    - BrowserCollector보다 정확도 높음

    단점:
    - 잡코리아에만 사용 가능
    - Playwright 필요 (느림, 3-5초)
    """

    def __init__(self, timeout: int = 20000):
        """
        Args:
            timeout (int): 페이지 로딩 타임아웃 (밀리초). 기본값 20초.
        """
        self.timeout = timeout

    def collect(self, url: str) -> str:
        """
        잡코리아 채용공고 페이지에서 본문만 정확하게 추출합니다.

        추출 대상:
        - 채용 제목
        - 회사 정보
        - 주요 업무
        - 자격 요건 (필수/우대)
        - 근무 조건
        - 복리후생

        제외 대상:
        - 광고
        - 헤더/푸터
        - 사이드바
        - 추천 공고

        Args:
            url (str): 잡코리아 채용공고 URL

        Returns:
            str: 추출된 텍스트 (실패 시 빈 문자열)
        """
        try:
            with sync_playwright() as p:
                # 1. 브라우저 실행
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()

                # 2. 잡코리아 페이지 로드
                print(f"[JOBKOREA] JobkoreaCollector: 잡코리아 페이지 로딩 중... ({url})")
                page.goto(url, timeout=self.timeout, wait_until='domcontentloaded')

                # 3. 잡코리아 특정 요소 대기
                # 잡코리아는 Next.js 기반 SSR, 주로 article, section, div 등 사용
                try:
                    # 메인 콘텐츠 영역이 로드될 때까지 대기
                    page.wait_for_selector('article, .recruiting-summary, .recruiting-view', timeout=3000)
                except PlaywrightTimeout:
                    print(f"[WARN] 잡코리아 콘텐츠 영역 대기 실패, 전체 본문 추출 시도...")

                # 4. 잡코리아 본문 추출 (최적화된 셀렉터)
                selectors_to_try = [
                    'article',                # Next.js 메인 콘텐츠
                    '.recruiting-view',       # 채용공고 뷰
                    '.recruiting-summary',    # 채용 요약
                    '.job-detail',            # 채용 상세
                    '.view-body',             # 본문
                    'main'                    # HTML5 main 태그
                ]

                extracted_text = ""

                for selector in selectors_to_try:
                    try:
                        elements = page.query_selector_all(selector)
                        if elements:
                            for elem in elements:
                                text = elem.inner_text()
                                if text and len(text) > 100:
                                    extracted_text += text + "\n\n"
                    except Exception:
                        continue

                # 5. 셀렉터로 찾지 못했다면 전체 본문 추출
                if len(extracted_text) < 200:
                    print(f"[WARN] 잡코리아 최적화 셀렉터 실패, 전체 body 추출...")
                    extracted_text = page.inner_text('body')

                # 6. 브라우저 종료
                browser.close()

                print(f"[OK] JobkoreaCollector: {len(extracted_text)} 문자 추출")
                return extracted_text.strip()

        except PlaywrightTimeout as e:
            print(f"[FAIL] JobkoreaCollector 타임아웃: {e}")
            return ""
        except Exception as e:
            print(f"[FAIL] JobkoreaCollector 실패: {e}")
            return ""

    def can_handle(self, url: str) -> bool:
        """
        잡코리아 URL만 처리 가능합니다.

        Args:
            url (str): 채용공고 URL

        Returns:
            bool: 잡코리아 URL이면 True, 아니면 False
        """
        return 'jobkorea.co.kr' in url.lower()
