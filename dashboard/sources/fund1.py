"""원본 파일 — 지점 펀드 상위 종목.

기준월·지점마다 순위 1..N의 종목이 한 행씩 들어 있다. 지점 행 외에 '전체'
행도 같은 모양으로 들어 있으며, 데이터 계층이 그 행을 따로 떼어 둔다
(→ dashboard/data.py).

ETF 순위표와 같은 모양이되 **시가총액이 없다.** 업종과 거래소도 없으므로
이 원본만으로는 종목을 묶을 축이 없고, 칸 크기를 정할 값도 없다
(→ dashboard/sources/etf2.py).

**지점마다 행 수가 다르다.** 파는 종목이 적은 지점은 순위가 20까지 차지
않는다. 그러므로 지점마다 같은 수의 행을 요구하지 않는다.

**동순위가 있다.** 값이 같은 종목이 여럿이면 같은 등수가 나란히 온다. 그래서
순위가 겹치는지는 보지 않고, 같은 종목이 두 번 있는지만 확인한다
(→ check_ranks). 주식·ETF 순위표는 순위도 겹치지 않아야 하므로 이 파일만
다르다.

단위 — 거래대금과 순매수금액은 **원**이다. 거래1의 `trade_amount`(억원)와
뜻이 겹치지 않도록 거래대금은 `trade_value`(원)에 담는다. 원본이 담은 단위를
그대로 두고 여기서 환산하지 않는다(→ AGENTS.md §9).

컬럼 이름 — 펀드도 순위표의 표준 이름(`stock_rank`·`stock_name`)을 쓴다.
이름은 상품 종류가 아니라 프레임의 모양을 따른다. 이름을 새로 만들면 같은
모양의 표를 그리는 공통 함수가 상품마다 갈린다.

'전체'의 상위 종목은 지점 목록을 더해 만든 값이 아니라 따로 뽑은 순위표다.
같은 순위에 다른 종목이 오므로 지점 합계와 대조하지 않는다
(→ data.py의 _TOTAL_CHECK_COLUMNS).

부호 — 순매수금액은 순매도인 달에 음수가 되며 원본이 앞에 `-`를 붙여 담는다.
인원수와 달리 음수를 막지 않는다.

순위변동 — 원본이 `+3`·`-2`·`0`처럼 부호를 붙인 글로 담는다. 부호를 읽어
숫자로 넘긴다. 앞 달에 없던 종목이라 비교할 값이 없으면 **비운 채로 두고**
0으로 채우지 않는다. 0은 '순위가 그대로'라는 뜻이라 '앞 달에 없었다'와
다르다. 그 빈 칸을 화면에서 `NEW`로 적는데, 그 글자는 화면이 붙인다. 여기서
글로 채우면 숫자 컬럼에 글이 섞여 정렬이 깨진다
(→ dashboard/format.py 의 format_rank_change).

원본 컬럼 이름이 바뀌면 이 파일의 표만 고친다. 다른 파일은 고치지
않는다(→ AGENTS.md §9).
"""

from __future__ import annotations

import pandas as pd

from dashboard.data import (
    check_not_negative,
    check_unique_rows,
    plain_text,
    strip_number_marks,
    to_label_column,
    to_month_column,
    to_numeric_column,
)

# 실제 데이터를 붙일 때 여기만 고치면 된다.
#
# 파일 이름만 적으면 app.py 옆의 `data/` 폴더에서 찾는다.
#   FILE = "상품_펀드1.pkl"     → data/상품_펀드1.pkl
# 환경 변수를 지정하면 아래 값보다 환경 변수가 우선한다.
FILE = "상품_펀드1.pkl"
FILE_ENV = "DASHBOARD_FUND1_FILE"

LABEL = "상품 펀드1"

# 원본 컬럼명 → 내부 표준 컬럼명.
COLUMNS: dict[str, str] = {
    "기준월": "base_month",
    "CSMT_ORZ_CD": "branch_id",
    "CSMT_ORZ_NM": "branch_name",
    "순위": "stock_rank",
    "종목명": "stock_name",
    "거래고객수": "trade_customer_count",
    "거래대금": "trade_value",
    "순매수금액": "net_buy_amount",
    "순위변동": "rank_change",
}

# 글로 다루는 컬럼 → 비어 있으면 안 되는지 여부.
TEXT_COLUMNS: dict[str, bool] = {"stock_name": True}

# 숫자로 다루는 컬럼 → (원본 컬럼 이름, 음수 허용 여부).
NUMBER_COLUMNS: dict[str, tuple[str, bool]] = {
    "stock_rank": ("순위", False),
    "trade_customer_count": ("거래고객수", False),
    "trade_value": ("거래대금", False),
    "net_buy_amount": ("순매수금액", True),
}

# 비어 있는 값으로 읽는 순위변동 표기. 앞 달에 없던 종목이라 비교할 값이
# 없다는 뜻이다. 부호만 있고 숫자가 없는 `-`는 변동값이 될 수 없으므로
# 여기 넣는다.
BLANK_RANK_CHANGE = ("", "-", "+", "신규", "NEW", "nan", "None", "NaT")


def build(frame: pd.DataFrame) -> pd.DataFrame:
    """표준 이름으로 바뀐 원본에서 펀드 상위 종목 프레임을 만든다.

    되돌려주는 컬럼은 `COLUMNS`의 표준 이름 9개다.

    기준 월은 `202607`이든 `2026-07`이든 날짜든 읽어서 `YYYY-MM`으로 맞춘다.
    순위 순서는 데이터 계층이 정렬로 다시 맞추므로 여기서는 값만 본다.
    """
    fund = frame.loc[:, list(COLUMNS.values())].copy()
    fund["base_month"] = to_month_column(fund["base_month"], "fund1")
    for column, required in TEXT_COLUMNS.items():
        fund[column] = to_label_column(
            fund[column], LABEL, column, required=required
        )
    for column, (label, signed) in NUMBER_COLUMNS.items():
        fund[column] = _number(fund[column], label, signed)
    fund["stock_rank"] = fund["stock_rank"].round().astype(int)
    fund["rank_change"] = _rank_change(fund["rank_change"])
    check_ranks(fund)
    return fund


def _number(series: pd.Series, column: str, signed: bool) -> pd.Series:
    """숫자로 맞춘다. 천 단위 쉼표와 앞에 붙은 `+`를 떼고 읽는다."""
    numbers = to_numeric_column(
        strip_number_marks(series), LABEL, column
    )
    if not signed:
        check_not_negative(numbers, LABEL, column)
    return numbers.astype(float)


def _rank_change(series: pd.Series) -> pd.Series:
    """순위변동을 부호가 있는 숫자로 맞춘다.

    `+3`은 3, `-2`는 -2, `0`은 0이다. 앞 달에 없던 종목처럼 비교할 값이
    없는 표기는 비운 채로 둔다(→ BLANK_RANK_CHANGE). 0으로 채우지 않는다.
    """
    text = plain_text(series).str.removeprefix("+").str.strip()
    blank = text.isin(BLANK_RANK_CHANGE)
    numbers = pd.to_numeric(text.where(~blank), errors="coerce")
    unreadable = numbers.isna() & ~blank
    if unreadable.any():
        raise ValueError(
            f"{LABEL} 파일의 순위변동을 숫자로 읽을 수 없는 값이"
            f" {int(unreadable.sum())}건 있습니다. "
            f"예: {text[unreadable].head(3).tolist()}. "
            "앞 달에 없던 종목을 다른 말로 적는다면 "
            "dashboard/sources/fund1.py 의 BLANK_RANK_CHANGE 에 "
            "그 표기를 더해 주세요."
        )
    return numbers.astype(float)


def check_ranks(fund: pd.DataFrame) -> None:
    """한 지점의 한 달 안에서 같은 종목이 두 번 있는지 본다.

    종목이 겹치면 같은 종목이 두 줄이 되어 금액이 두 번 세어진다. 어느 쪽이
    맞는지 화면에서는 알 수 없으므로 멈춘다(→ data.check_unique_rows).

    **순위는 대조하지 않는다.** 이 원본은 동순위를 담는다 — 값이 같은 종목이
    여럿이면 같은 등수가 나란히 온다. 표는 그대로 보여주면 되므로 잘못이
    아니다. 다른 순위표(주식·ETF)와 다른 점이다.

    순위가 몇 위까지 있는지도 보지 않는다. 파는 종목이 적은 지점은 20까지
    차지 않으며, 동순위가 있으면 행 수와 마지막 등수도 어긋난다.
    """
    keys = ["base_month", "branch_id"]
    check_unique_rows(fund, LABEL, keys, "stock_name", "종목")


__all__ = [
    "BLANK_RANK_CHANGE",
    "COLUMNS",
    "FILE",
    "FILE_ENV",
    "LABEL",
    "NUMBER_COLUMNS",
    "TEXT_COLUMNS",
    "build",
    "check_ranks",
]
