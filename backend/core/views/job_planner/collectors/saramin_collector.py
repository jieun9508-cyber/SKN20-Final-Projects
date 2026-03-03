"""
Saramin-optimized Collector

사람인 채용공고 전용 최적화 Collector입니다.
Playwright를 사용하되, 사람인의 HTML 구조에 맞춰 정확한 본문만 추출합니다.
"""

from urllib.parse import urlparse, parse_qs
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
from .base import BaseCollector


class SaraminCollector(BaseCollector):
    """
    사람인 전용 최적화 Collector

    사람인 채용공고 페이지의 구조를 정확히 파악하여
    광고, 헤더, 푸터를 제외하고 본문만 추출합니다.

    장점:
    - 노이즈 제거 (광고, 헤더, 푸터 등 제외)
    - 정확한 채용공고 본문만 추출
    - BrowserCollector보다 정확도 높음

    단점:
    - 사람인에만 사용 가능
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
        사람인 채용공고 페이지에서 본문만 정확하게 추출합니다.

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
            url (str): 사람인 채용공고 URL

        Returns:
            str: 추출된 텍스트 (실패 시 빈 문자열)
        """
        try:
            # relay/view URL → 실제 채용공고 URL로 변환
            actual_url = self._resolve_relay_url(url)
            if actual_url != url:
                print(f"[SARAMIN] relay URL 변환: {url[:60]}... → {actual_url}")

            with sync_playwright() as p:
                # 1. 브라우저 실행
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()

                # 2. 사람인 페이지 로드
                # domcontentloaded: 본문 HTML이 파싱되면 즉시 반환 (광고·분석 스크립트 대기 없음)
                print(f"[SARAMIN] SaraminCollector: 사람인 페이지 로딩 중... ({actual_url})")
                page.goto(actual_url, timeout=self.timeout, wait_until='domcontentloaded')

                # 3. 사람인 특정 요소 대기
                # 사람인은 주로 `.user_content`, `.jv_cont`, `.cont` 등의 클래스 사용
                try:
                    # 메인 콘텐츠 영역이 로드될 때까지 대기
                    page.wait_for_selector('.wrap_jv_cont, .user_content, .cont', timeout=3000)
                except PlaywrightTimeout:
                    print(f"[WARN] 사람인 콘텐츠 영역 대기 실패, 전체 본문 추출 시도...")

                # 4. 사람인 본문 추출 (최적화된 셀렉터)
                # 여러 셀렉터를 시도하여 가장 정확한 본문 추출
                selectors_to_try = [
                    '.wrap_jv_cont',          # 채용공고 메인 래퍼
                    '.user_content',          # 사용자 작성 콘텐츠
                    '.cont',                  # 콘텐츠 영역
                    '.jv_summary',            # 채용 요약
                    '.jv_cont'                # 채용 콘텐츠
                ]

                extracted_text = ""

                for selector in selectors_to_try:
                    try:
                        # 각 셀렉터로 요소 찾기
                        elements = page.query_selector_all(selector)
                        if elements:
                            print(f"[DEBUG] 사람인 셀렉터 '{selector}': {len(elements)}개 요소 발견")
                            for i, elem in enumerate(elements):
                                text = elem.inner_text()
                                if text and len(text) > 100:  # 의미 있는 텍스트만
                                    print(f"[DEBUG] 사람인 '{selector}' 요소 #{i}: {len(text)}자 추출")
                                    print(f"[DEBUG] 앞 200자: {text[:200]}")
                                    extracted_text += text + "\n\n"
                    except Exception as e:
                        continue

                # 5. 셀렉터로 찾지 못했다면 전체 본문 추출
                if len(extracted_text) < 200:
                    print(f"[WARN] 사람인 최적화 셀렉터 실패, 전체 body 추출...")
                    extracted_text = page.inner_text('body')

                # 6. 브라우저 종료
                browser.close()

                print(f"[OK] SaraminCollector: {len(extracted_text)} 문자 추출")
                return extracted_text.strip()

        except PlaywrightTimeout as e:
            print(f"[FAIL] SaraminCollector 타임아웃: {e}")
            return ""
        except Exception as e:
            print(f"[FAIL] SaraminCollector 실패: {e}")
            return ""

    def _resolve_relay_url(self, url: str) -> str:
        """
        사람인 relay/view URL을 실제 채용공고 URL로 변환합니다.

        relay URL 예시:
          https://www.saramin.co.kr/zf_user/jobs/relay/view?rec_idx=52948032&...
        실제 URL 예시:
          https://www.saramin.co.kr/zf_user/jobs/view?rec_idx=52948032
        """
        if '/relay/view' in url:
            params = parse_qs(urlparse(url).query)
            rec_idx = params.get('rec_idx', [None])[0]
            if rec_idx:
                return f"https://www.saramin.co.kr/zf_user/jobs/view?rec_idx={rec_idx}"
        return url

    def can_handle(self, url: str) -> bool:
        """
        사람인 URL만 처리 가능합니다.

        Args:
            url (str): 채용공고 URL

        Returns:
            bool: 사람인 URL이면 True, 아니면 False
        """
        return 'saramin.co.kr' in url.lower()
