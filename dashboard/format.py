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
