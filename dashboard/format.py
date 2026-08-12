"""화면 표시용 포맷 함수.

숫자·금액·비율 표기를 여기서만 관리한다. Dash 화면과 정적 HTML,
그리드와 차트 hover가 같은 함수를 쓴다.
값이 없거나 계산할 수 없으면 `EMPTY_TEXT`를 반환한다.
"""

from __future__ import annotations

import math

EMPTY_TEXT = "-"

# --- 금액 표기 ---------------------------------------------------------------
# 입력값 1이 몇 원인지. 프레임마다 담는 단위가 달라 여기서 원으로 모은다.
WON_PER_100M = 100_000_000  # 억원 입력
WON_PER_1M = 1_000_000  # 백만원 입력
_WON_PER_10K = 10_000  # 만원

# 금액을 쪼갤 단위. 만원을 기준 자리로 삼는다(1조 = 1억 만원, 1억 = 1만 만원).
_MONEY_UNITS: tuple[tuple[int, str], ...] = (
    (100_000_000, "조"),
    (10_000, "억"),
    (1, "만"),
)

# 함께 적을 단위 수. 위 자리부터 이만큼만 적는다. 셋을 다 적으면
# '2조 8,266억 5,432만원'이 되어 표 한 칸에 들어가지 않고, 자리가 늘수록
# 오히려 크기가 눈에 안 들어온다.
MONEY_UNIT_COUNT = 2


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


def format_number(value: object) -> str:
    """단위 없는 정수: 1, 12 (순번·건수처럼 단위를 붙이지 않는 값)"""
    if _is_missing(value):
        return EMPTY_TEXT
    return f"{round(float(value)):,}"


def format_count_delta(value: object) -> str:
    """고객 수 증감: +1,730명 / -320명"""
    if _is_missing(value):
        return EMPTY_TEXT
    number = round(float(value))
    return f"{number:+,}명"


def format_won(value: object, unit: int) -> str:
    """금액을 조·억·만으로 적는다. `unit`은 입력값 1이 몇 원인지다.

    28,266억원 → 2조 8,266억원, 31.9백만원 → 3,190만원.
    한 가지 단위로만 적으면 자릿수를 사람이 세어 크기를 가늠해야 한다.

    만원 아래는 버린다. 이 화면이 다루는 금액대에서 원 단위는 읽는 데
    방해만 된다.
    """
    if _is_missing(value):
        return EMPTY_TEXT
    amount = round(float(value) * unit / _WON_PER_10K)
    sign = "-" if amount < 0 else ""
    return sign + _money_text(abs(amount))


def _money_text(amount: int) -> str:
    """만원 단위 정수를 '2조 8,266억원'처럼 적는다.

    값이 있는 가장 큰 자리부터 `MONEY_UNIT_COUNT`개만 적는다. 그 안에서
    비어 있는 자리는 건너뛴다 — 2조 0억 5,000만원은 '2조원'이 된다.
    """
    parts = []
    rest = amount
    for size, name in _MONEY_UNITS:
        digit, rest = divmod(rest, size)
        parts.append((digit, name))
    top = next(
        (index for index, (digit, _) in enumerate(parts) if digit), None
    )
    if top is None:
        return "0원"
    shown = [
        f"{digit:,}{name}"
        for digit, name in parts[top:top + MONEY_UNIT_COUNT]
        if digit
    ]
    return " ".join(shown) + "원"


def _signed_won(value: object, unit: int) -> str:
    if _is_missing(value):
        return EMPTY_TEXT
    number = float(value)
    sign = "+" if number >= 0 else "-"
    return f"{sign}{format_won(abs(number), unit)}"


def format_assets(value: object) -> str:
    """자산(억원 입력): 2조 8,266억원 / 3,226억 9,924만원"""
    return format_won(value, WON_PER_100M)


def format_assets_delta(value: object) -> str:
    """자산 증감(억원 입력): +170억원 / -1조 200억원"""
    return _signed_won(value, WON_PER_100M)


def format_million_won(value: object) -> str:
    """1인 평균 자산(백만원 입력): 3,190만원 / 24억 2,500만원"""
    return format_won(value, WON_PER_1M)


def format_million_won_delta(value: object) -> str:
    """1인 평균 자산 증감(백만원 입력): +120만원 / -40만원"""
    return _signed_won(value, WON_PER_1M)


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
