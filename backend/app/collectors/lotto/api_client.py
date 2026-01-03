"""동행복권 API 클라이언트 (개선판)"""
import json
import html
import re
import requests
from bs4 import BeautifulSoup
import time
import logging
from typing import Optional, Dict, Tuple
from datetime import datetime, timedelta
from backend.app.config import settings

BASE_URL = "https://www.dhlottery.co.kr/common.do?method=getLottoNumber&drwNo={}"
LATEST_URL = "https://dhlottery.co.kr/gameResult.do?method=byWin"
RESULT_URL = "https://www.dhlottery.co.kr/gameResult.do?method=byWin&drwNo={}"

logger = logging.getLogger(__name__)

class LottoAPIClient:
    def __init__(self, delay: float = 0.3):
        """
        Args:
            delay: API 호출 간 딜레이 (초) - 사이트 부하 방지
        """
        self.delay = delay
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7',
            'Referer': 'https://www.dhlottery.co.kr/'
        })
    
    def get_latest_draw_no(self) -> int:
        """
        최신 회차 번호 가져오기

        방법:
        1. 회차 추정 (2002년 12월 시작, 주 1회)
        2. 추정 회차부터 순차 확인 (HTML 파싱)
        3. 실패 시 역순 탐색
        """
        # 로또는 2002년 12월 7일 1회 시작, 매주 토요일
        start_date = datetime(2002, 12, 7)
        now = datetime.now()
        weeks_passed = (now - start_date).days // 7
        estimated = weeks_passed + 1  # 추정 회차

        logger.info(f"로또 회차 추정: {estimated}회 (시작일로부터 {weeks_passed}주 경과)")

        # JSON API 시도 (역순 탐색)
        for draw_no in range(estimated, max(estimated - 20, 1), -1):
            data, blocked = self._get_json(BASE_URL.format(draw_no))
            if blocked:
                logger.error("로또 API 접근 차단 감지 (redirect). 최신 회차 확인 불가")
                return self._get_latest_draw_no_from_naver()
            if not data:
                continue
            if data.get("returnValue") == "success":
                logger.info(f"✅ 최신 회차: {draw_no}회 (JSON API)")
                return draw_no
            time.sleep(0.2)

        logger.error("최신 회차 확인 실패 (JSON API)")
        return self._get_latest_draw_no_from_naver()

    def _fetch_draw_html(self, draw_no: int) -> Optional[Dict]:
        """
        HTML 페이지에서 회차 정보 파싱

        Args:
            draw_no: 회차 번호

        Returns:
            회차 정보 dict 또는 None
        """
        try:
            url = RESULT_URL.format(draw_no)
            res = self.session.get(url, timeout=10)
            res.raise_for_status()

            soup = BeautifulSoup(res.text, "html.parser")

            # 회차 확인
            draw_no_elem = soup.select_one(".win_result h4 strong")
            if not draw_no_elem:
                return None

            # 추첨일 찾기
            date_text = soup.select_one(".win_result .desc")
            if not date_text:
                return None

            date_match = re.search(r"(\d{4})\. (\d{2})\. (\d{2})", date_text.text)
            if not date_match:
                return None

            draw_date = f"{date_match.group(1)}-{date_match.group(2)}-{date_match.group(3)}"

            # 당첨번호 찾기
            number_elems = soup.select(".win_result .num.win .ball_645")
            bonus_elem = soup.select_one(".win_result .num.bonus .ball_645")

            if len(number_elems) != 6 or not bonus_elem:
                return None

            # 번호 추출
            numbers = []
            for elem in number_elems:
                num_text = elem.text.strip()
                try:
                    numbers.append(int(num_text))
                except ValueError:
                    return None

            bonus_text = bonus_elem.text.strip()
            try:
                bonus = int(bonus_text)
            except ValueError:
                return None

            return {
                "draw_no": draw_no,
                "date": draw_date,
                "n1": numbers[0],
                "n2": numbers[1],
                "n3": numbers[2],
                "n4": numbers[3],
                "n5": numbers[4],
                "n6": numbers[5],
                "bonus": bonus
            }

        except Exception as e:
            logger.debug(f"HTML 파싱 실패 (회차 {draw_no}): {e}")
            return None

    def _extract_json_from_text(self, text: str) -> Optional[Dict]:
        """텍스트에서 JSON 부분을 추출해 파싱."""
        try:
            start = text.find("{")
            end = text.rfind("}")
            if start == -1 or end == -1 or end <= start:
                return None
            return json.loads(text[start:end + 1])
        except Exception:
            return None

    def _get_json(self, url: str) -> tuple[Optional[Dict], bool]:
        """JSON API 요청. redirect면 차단으로 간주. 차단 시 프록시로 재시도."""
        try:
            res = self.session.get(url, timeout=10, allow_redirects=False)
            if res.status_code in (301, 302, 303, 307, 308):
                return self._get_json_via_proxy(url), True
            try:
                data = res.json()
                return data, False
            except Exception:
                # HTML/텍스트 응답일 수 있어 프록시 시도
                return self._get_json_via_proxy(url), False
        except Exception as e:
            logger.warning(f"로또 JSON API 요청 실패: {e}")
            return self._get_json_via_proxy(url), False

    def _get_json_via_proxy(self, url: str) -> Optional[Dict]:
        """프록시를 통해 JSON 응답 시도 (WAF 우회용)."""
        try:
            url_no_scheme = url.replace("https://", "").replace("http://", "")
            proxy_urls = [
                f"https://r.jina.ai/http://{url_no_scheme}",
                f"https://r.jina.ai/https://{url_no_scheme}",
            ]
            for proxy_url in proxy_urls:
                res = self.session.get(proxy_url, timeout=15)
                if res.status_code != 200:
                    continue
                data = self._extract_json_from_text(res.text)
                if data:
                    logger.info("프록시 JSON 응답 성공")
                    return data
        except Exception as e:
            logger.warning(f"프록시 JSON 요청 실패: {e}")
        return None

    def _get_naver_news(self, query: str, display: int = 10) -> list:
        if not settings.NAVER_CLIENT_ID or not settings.NAVER_CLIENT_SECRET:
            return []
        headers = {
            "X-Naver-Client-Id": settings.NAVER_CLIENT_ID,
            "X-Naver-Client-Secret": settings.NAVER_CLIENT_SECRET,
        }
        params = {
            "query": query,
            "display": display,
            "sort": "date",
        }
        try:
            res = self.session.get(
                "https://openapi.naver.com/v1/search/news.json",
                headers=headers,
                params=params,
                timeout=10,
            )
            res.raise_for_status()
            data = res.json()
            return data.get("items", [])
        except Exception as e:
            logger.warning(f"네이버 뉴스 API 실패: {e}")
            return []

    def _extract_numbers_from_text(self, text: str) -> Tuple[Optional[list], Optional[int]]:
        """뉴스 제목/본문에서 6개 번호 + 보너스를 추출."""
        if not text:
            return None, None
        clean = html.unescape(re.sub(r"<[^>]+>", "", text))

        # 보너스 번호
        bonus = None
        bonus_match = re.search(r"보너스\s*번호?\s*['\"]?\s*([1-3]\d|4[0-5]|[1-9])", clean)
        if bonus_match:
            bonus = int(bonus_match.group(1))

        # 6개 번호 패턴 (쉼표로 구분된 리스트 우선)
        seq_match = re.search(
            r"([1-3]\d|4[0-5]|[1-9])\s*,\s*([1-3]\d|4[0-5]|[1-9])\s*,\s*([1-3]\d|4[0-5]|[1-9])\s*,\s*([1-3]\d|4[0-5]|[1-9])\s*,\s*([1-3]\d|4[0-5]|[1-9])\s*,\s*([1-3]\d|4[0-5]|[1-9])",
            clean,
        )
        nums = None
        if seq_match:
            nums = [int(n) for n in seq_match.groups()]
        else:
            # 키워드 주변에서 숫자 6개 추출
            keyword_idx = clean.find("당첨번호")
            window = clean
            if keyword_idx != -1:
                start = max(keyword_idx - 50, 0)
                end = min(keyword_idx + 100, len(clean))
                window = clean[start:end]
            found = re.findall(r"([1-3]\d|4[0-5]|[1-9])", window)
            if len(found) >= 6:
                nums = [int(n) for n in found[:6]]

        if not nums or len(nums) != 6:
            return None, None
        return nums, bonus

    def _get_latest_draw_no_from_naver(self) -> int:
        """네이버 뉴스 기반 최신 회차 추정."""
        items = self._get_naver_news("로또 당첨번호", display=10)
        for item in items:
            text = f"{item.get('title', '')} {item.get('description', '')}"
            clean = html.unescape(re.sub(r"<[^>]+>", "", text))
            m = re.search(r"(\d{3,4})회", clean)
            if m:
                return int(m.group(1))
        return 0

    def _get_draw_from_naver(self, draw_no: int) -> Optional[Dict]:
        """네이버 뉴스에서 회차 번호 추출 (차단 시 대체)."""
        items = self._get_naver_news(f"로또 {draw_no}회 당첨번호", display=10)
        for item in items:
            text = f"{item.get('title', '')} {item.get('description', '')}"
            clean = html.unescape(re.sub(r"<[^>]+>", "", text))
            if f"{draw_no}회" not in clean:
                continue
            nums, bonus = self._extract_numbers_from_text(text)
            if nums and bonus is not None and len(set(nums)) == 6:
                draw_date = None
                pub_date = item.get("pubDate")
                try:
                    if pub_date:
                        from email.utils import parsedate_to_datetime
                        dt = parsedate_to_datetime(pub_date)
                        # 뉴스는 보통 일요일 게재 -> 추첨일(토)로 보정
                        if dt.weekday() == 6:
                            draw_date = (dt.date() - timedelta(days=1)).isoformat()
                        else:
                            draw_date = dt.date().isoformat()
                except Exception:
                    draw_date = None
                return {
                    "draw_no": draw_no,
                    "date": draw_date or datetime.now().date().isoformat(),
                    "n1": nums[0],
                    "n2": nums[1],
                    "n3": nums[2],
                    "n4": nums[3],
                    "n5": nums[4],
                    "n6": nums[5],
                    "bonus": bonus or 0,
                }
        return None
    
    def get_lotto_draw(self, draw_no: int, retries: int = 3) -> Optional[Dict]:
        """
        특정 회차 데이터 가져오기 (재시도 로직 포함)

        Args:
            draw_no: 회차 번호
            retries: 실패 시 재시도 횟수

        Returns:
            회차 정보 dict 또는 None (데이터 없음)
        """
        for attempt in range(retries):
            # 방법 1: JSON API 시도
            try:
                url = BASE_URL.format(draw_no)
                data, blocked = self._get_json(url)
                if blocked:
                    logger.error("로또 API 접근 차단 감지 (redirect).")
                    return self._get_draw_from_naver(draw_no)
                if data and data.get("returnValue") == "success":
                    logger.info(f"✅ 회차 {draw_no} 조회 성공 (JSON API)")
                    return {
                        "draw_no": data["drwNo"],
                        "date": data["drwNoDate"],
                        "n1": data["drwtNo1"],
                        "n2": data["drwtNo2"],
                        "n3": data["drwtNo3"],
                        "n4": data["drwtNo4"],
                        "n5": data["drwtNo5"],
                        "n6": data["drwtNo6"],
                        "bonus": data["bnusNo"],
                    }
                if data and data.get("returnValue") == "fail":
                    logger.info(f"회차 {draw_no} 데이터 없음 (API 응답: fail)")
                    return None

            except requests.RequestException as e:
                logger.warning(f"회차 {draw_no} JSON API 요청 실패: {e}")

            # 방법 2: HTML 파싱 시도
            draw_info = self._fetch_draw_html(draw_no)
            if draw_info:
                logger.info(f"✅ 회차 {draw_no} 조회 성공 (HTML 파싱)")
                return draw_info

            # 방법 3: 네이버 뉴스 검색 대체
            naver_info = self._get_draw_from_naver(draw_no)
            if naver_info:
                logger.info(f"✅ 회차 {draw_no} 조회 성공 (Naver 대체)")
                return naver_info

            # 재시도
            if attempt < retries - 1:
                logger.warning(f"회차 {draw_no} 조회 실패, 재시도 {attempt + 1}/{retries - 1}")
                time.sleep(1 + attempt)  # 점진적 대기 시간 증가
            else:
                logger.error(f"회차 {draw_no} 조회 최종 실패 ({retries}회 시도)")
                return None

            time.sleep(self.delay)

        return None
