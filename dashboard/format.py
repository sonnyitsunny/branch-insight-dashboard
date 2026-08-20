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
WON_PER_WON = 1  # 원 입력 (수익 프레임 → sources/revenue1.py)
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


def format_signed_number(value: object) -> str:
    """단위 없는 부호 정수: +3 / -2 / 0 (순위변동처럼 오르내림을 적는 값)

    0에는 부호를 붙이지 않는다. `+0`은 '조금 올랐다'로 읽히지만 실제로는
    '그대로'라는 뜻이다.
    """
    if _is_missing(value):
        return EMPTY_TEXT
    number = round(float(value))
    return "0" if number == 0 else f"{number:+,}"


# 앞 달에 없던 종목의 순위변동 자리에 적는 글
# (→ dashboard/sources/overseas_stock1.py).
NEW_ENTRY_TEXT = "NEW"


def format_rank_change(value: object) -> str:
    """순위변동: +3 / -2 / 0, 앞 달에 없던 종목은 NEW

    빈 칸을 `-`로 두면 '값이 없다'로만 읽힌다. 이 컬럼에서 값이 없다는 것은
    앞 달 순위가 없었다는 뜻, 곧 새로 들어온 종목이라는 뜻이다.
    0으로 채우지 않는 이유도 같다 — 0은 '순위가 그대로'다.
    """
    if _is_missing(value):
        return NEW_ENTRY_TEXT
    return format_signed_number(value)


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


def format_revenue(value: object) -> str:
    """수익(원 입력): 10억 5,728만원

    수익 프레임만 원 단위다. 다른 프레임의 금액은 억원이라 `format_assets`를
    쓴다(→ dashboard/data.py 의 REVENUE_COLUMNS).
    """
    return format_won(value, WON_PER_WON)


def format_revenue_delta(value: object) -> str:
    """수익 증감(원 입력): +1억 2,000만원 / -3,400만원"""
    return _signed_won(value, WON_PER_WON)


# --- 달러 표기 ---------------------------------------------------------------
# 해외주식 시가총액만 달러로 담긴다(→ dashboard/sources/overseas_stock2.py).
# 원화 금액과 한 화면에 놓이므로 접두사로 통화를 밝힌다.
USD_PREFIX = "USD"


def format_usd(value: object) -> str:
    """달러 금액: USD769,935,024

    원본이 담은 숫자를 그대로 적고 천 단위 쉼표만 넣는다. 조·억으로 접지
    않는다. 그 자리 이름은 만 단위로 끊는 한국식 표기라 달러 금액에 붙이면
    원본과 대조할 수 없고, 환율을 곱해 원화로 바꾸면 그날 환율에 따라 화면
    숫자가 달라진다(→ AGENTS.md §9).
    """
    if _is_missing(value):
        return EMPTY_TEXT
    return f"{USD_PREFIX}{round(float(value)):,}"


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
    """비율의 전월 대비 차이: +1.0%p / -0.8%p

    한동안 %로만 적었다. 단위를 밝히면 '34.5%' 아래 '+1.3%'가 붙어 두
    숫자가 같은 뜻으로 보인다고 봤다. 그런데 %로 적으면 오히려 "34.5%가
    1.3% 늘었다"는 증가율로 읽힌다. 실제로는 33.2%에서 34.5%가 된
    차이이므로 %p로 적어 증가율과 갈라 놓는다(→ layout.KPI_CARDS).
    """
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
