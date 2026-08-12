"""화면 표시용 포맷 함수.

숫자·금액·비율 표기를 여기서만 관리한다. Dash 화면과 정적 HTML,
그리드와 차트 hover가 같은 함수를 쓴다.
값이 없거나 계산할 수 없으면 `EMPTY_TEXT`를 반환한다.
"""

from __future__ import annotations

import math

EMPTY_TEXT = "-"

_UNIT_JO = 10_000  # 억원 → 조 단위 환산


def _is_missing(value: object) -> bool:
    if value is None:
        return True
    try:
        number = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return True
    return math.isnan(number) or math.isinf(number)


def format_count(value: object) -> str:
    """고객 수: 12,350명"""
    if _is_missing(value):
        return EMPTY_TEXT
    return f"{round(float(value)):,}명"


def format_count_delta(value: object) -> str:
    """고객 수 증감: +1,730명 / -320명"""
    if _is_missing(value):
        return EMPTY_TEXT
    number = round(float(value))
    return f"{number:+,}명"


def format_assets(value: object) -> str:
    """총자산(억원 입력): 21조 4,900억원"""
    if _is_missing(value):
        return EMPTY_TEXT
    total = round(float(value))
    sign = "-" if total < 0 else ""
    total = abs(total)
    jo, remainder = divmod(total, _UNIT_JO)
    if jo and remainder:
        return f"{sign}{jo:,}조 {remainder:,}억원"
    if jo:
        return f"{sign}{jo:,}조원"
    return f"{sign}{remainder:,}억원"


def format_assets_delta(value: object) -> str:
    """총자산 증감(억원 입력): +170억원 / -1조 200억원"""
    if _is_missing(value):
        return EMPTY_TEXT
    number = round(float(value))
    sign = "+" if number >= 0 else "-"
    return f"{sign}{format_assets(abs(number))}"


def format_assets_plain(value: object) -> str:
    """표에 쓰는 자산 표기(억원 입력): 3,181억원

    조 단위로 접지 않는다. 표는 같은 컬럼의 값을 위아래로 견주며 읽으므로
    어떤 행은 '조', 어떤 행은 '억'이면 자릿수를 눈으로 맞출 수 없다.
    AgGrid의 표현식도 같은 규칙을 쓴다(→ grid.ASSETS_FORMAT).
    """
    if _is_missing(value):
        return EMPTY_TEXT
    return f"{round(float(value)):,}억원"


def format_million_won(value: object, digits: int = 1) -> str:
    """1인 평균 자산(백만원 입력): 22.6백만원

    억원으로 바꾸지 않는다. 1인 평균은 억 단위에 못 미쳐 0.2억처럼 읽기
    어려워진다.
    """
    if _is_missing(value):
        return EMPTY_TEXT
    return f"{float(value):,.{digits}f}백만원"


def format_million_won_delta(value: object, digits: int = 1) -> str:
    """1인 평균 자산 증감(백만원 입력): +1.2백만원 / -0.4백만원"""
    if _is_missing(value):
        return EMPTY_TEXT
    return f"{float(value):+,.{digits}f}백만원"


def format_percent(value: object, digits: int = 1) -> str:
    """비율: 43.3%"""
    if _is_missing(value):
        return EMPTY_TEXT
    return f"{float(value):.{digits}f}%"


def format_signed_percent(value: object, digits: int = 1) -> str:
    """증가율: +11.0% / -2.4%"""
    if _is_missing(value):
        return EMPTY_TEXT
    return f"{float(value):+.{digits}f}%"


def format_pp_delta(value: object, digits: int = 1) -> str:
    """비율의 전월 대비 차이: +1.0%p / -0.8%p"""
    if _is_missing(value):
        return EMPTY_TEXT
    return f"{float(value):+.{digits}f}%p"


def format_age(value: object, digits: int = 1) -> str:
    """평균 연령: 29.4세"""
    if _is_missing(value):
        return EMPTY_TEXT
    return f"{float(value):.{digits}f}세"


def format_month(base_month: str) -> str:
    """기준 월: 2026년 7월"""
    if not base_month or len(str(base_month)) < 7:
        return EMPTY_TEXT
    year, month = str(base_month)[:7].split("-")
    return f"{int(year)}년 {int(month)}월"


def format_month_short(base_month: str) -> str:
    """차트 축 라벨: 25.07"""
    if not base_month or len(str(base_month)) < 7:
        return EMPTY_TEXT
    year, month = str(base_month)[:7].split("-")
    return f"{year[2:]}.{month}"
