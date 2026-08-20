"""원본 파일 — 시가총액 상위 종목의 지점별 해외주식 거래.

시장 전체의 시가총액 상위 N종목을 먼저 고르고, 그 종목마다 지점별 거래를
담는다. 해외주식1과 컬럼 이름이 겹치지만 행을 고르는 기준이 다르다. 1은
지점마다 그 지점의 거래 상위 종목을 담고, 이쪽은 모든 지점이 같은 종목
목록을 놓고 본다(→ dashboard/sources/overseas_stock1.py).

지점 행 외에 '전체' 행도 같은 모양으로 들어 있으며, 데이터 계층이 그 행을
따로 떼어 둔다(→ dashboard/data.py).

**지점마다 행 수가 다르다.** 그 지점이 대상 종목을 하나도 거래하지 않았으면
그 행이 아예 없다. 없는 행을 0으로 채우지 않는다. 0은 '거래 없음'이 아니라
'0으로 측정됨'을 뜻한다(→ AGENTS.md §9). 대상 종목이 몇 개인지는 원본이
정하므로 여기에 적지 않는다(→ AGENTS.md §10.1).

**단위가 둘로 갈린다.** 시가총액은 **달러**, 순매수금액은 **원**이다. 그래서
시가총액만 이름에 단위를 박아 `market_cap_usd`로 담는다. 국내주식의
`market_cap`(억원)과 같은 이름을 쓰면 원화 표기 함수에 그대로 넘어가 화면에
억원으로 적힌다. 화면은 `format_usd`로 `USD769,935,024`처럼 적는다
(→ dashboard/format.py). 환율을 곱해 원화로 바꾸지 않는다. 그날 환율에 따라
화면 숫자가 달라진다.

거래대금은 이 원본에 없다. 국내주식 쪽 트리맵이 hover에 적는 값이라 해외주식
hover에서는 그 줄이 빠진다.

부호 — 순매수금액은 순매도인 종목에서 음수가 된다. 인원수와 달리 음수를 막지
않는다.

업종 — 원본에 비어 있는 행이 있다. 값을 지어내지 않고 빈 값 그대로 넘긴다.

순위 — 원본이 준 숫자를 그대로 읽어 넘긴다. **무엇을 기준으로 매긴 순위인지는
확인되지 않았다**(→ AGENTS.md §17). 시가총액 순위라면 지점이 달라도 종목마다
같은 값이고, 지점별 거래 순위라면 지점마다 다르다. 어느 쪽인지 모르는 채로
종목의 성질처럼 다루면 한쪽에서 틀리므로, 지점마다 같은지 확인하지 않고
종목표(`stock_facts`)에도 넣지 않는다. 확인되면 그때 다룬다.

같은 종목의 시가총액·업종·거래소는 지점이 달라도 같아야 한다. 시가총액은
시장이 정하는 값이고 업종과 거래소는 종목의 성질이기 때문이다. 지점마다
다르면 파일이 잘못 붙었다는 뜻이라 멈춘다(→ check_stock_facts).

원본 컬럼 이름이 바뀌면 이 파일의 표만 고친다. 다른 파일은 고치지
않는다(→ AGENTS.md §9).
"""

from __future__ import annotations

import pandas as pd

from dashboard.data import (
    check_not_negative,
    check_unique_rows,
    strip_number_marks,
    to_label_column,
    to_month_column,
    to_numeric_column,
)

# 실제 데이터를 붙일 때 여기만 고치면 된다.
#
# 파일 이름만 적으면 app.py 옆의 `data/` 폴더에서 찾는다.
#   FILE = "상품_해외주식2.pkl"     → data/상품_해외주식2.pkl
# 환경 변수를 지정하면 아래 값보다 환경 변수가 우선한다.
FILE = "상품_해외주식2.pkl"
FILE_ENV = "DASHBOARD_OVERSEAS_STOCK2_FILE"

LABEL = "상품 해외주식2"

# 원본 컬럼명 → 내부 표준 컬럼명.
COLUMNS: dict[str, str] = {
    "기준월": "base_month",
    "CSMT_ORZ_CD": "branch_id",
    "CSMT_ORZ_NM": "branch_name",
    "종목명": "stock_name",
    "거래소": "exchange",
    "업종": "sector",
    "시가총액": "market_cap_usd",
    "거래고객수": "trade_customer_count",
    "순매수금액": "net_buy_amount",
    "순위": "stock_rank",
}

# 글로 다루는 컬럼 → 비어 있으면 안 되는지 여부.
TEXT_COLUMNS: dict[str, bool] = {
    "stock_name": True,
    "sector": False,
    "exchange": False,
}

# 숫자로 다루는 컬럼 → (원본 컬럼 이름, 음수 허용 여부).
NUMBER_COLUMNS: dict[str, tuple[str, bool]] = {
    "stock_rank": ("순위", False),
    "market_cap_usd": ("시가총액", False),
    "trade_customer_count": ("거래고객수", False),
    "net_buy_amount": ("순매수금액", True),
}

# 종목의 성질이라 지점이 달라도 같아야 하는 컬럼.
STOCK_FACT_COLUMNS = ("market_cap_usd", "sector", "exchange")

# 값이 들어 있는 행끼리만 견주는 컬럼. 비어 있는 행이 있어도 되는 값이다.
BLANK_FACT_COLUMNS = ("sector", "exchange")


def build(frame: pd.DataFrame) -> pd.DataFrame:
    """표준 이름으로 바뀐 원본에서 시가총액 상위 종목 프레임을 만든다.

    되돌려주는 컬럼은 `COLUMNS`의 표준 이름 10개다.

    기준 월은 `202607`이든 `2026-07`이든 날짜든 읽어서 `YYYY-MM`으로 맞춘다.
    """
    stock = frame.loc[:, list(COLUMNS.values())].copy()
    stock["base_month"] = to_month_column(
        stock["base_month"], "overseas_stock2"
    )
    for column, required in TEXT_COLUMNS.items():
        stock[column] = to_label_column(
            stock[column], LABEL, column, required=required
        )
    for column, (label, signed) in NUMBER_COLUMNS.items():
        stock[column] = _number(stock[column], label, signed)
    stock["stock_rank"] = stock["stock_rank"].round().astype(int)
    check_one_row_per_stock(stock)
    check_stock_facts(stock)
    return stock


def _number(series: pd.Series, column: str, signed: bool) -> pd.Series:
    """숫자로 맞춘다. 천 단위 쉼표와 앞에 붙은 `+`를 떼고 읽는다."""
    numbers = to_numeric_column(
        strip_number_marks(series), LABEL, column
    )
    if not signed:
        check_not_negative(numbers, LABEL, column)
    return numbers.astype(float)


def check_one_row_per_stock(stock: pd.DataFrame) -> None:
    """한 지점의 한 달에 같은 종목이 두 번 있는지 본다.

    두 번 있으면 트리맵에서 그 종목의 면적이 두 번 더해지고, 합계도 조용히
    커진다. 어느 행이 맞는지 화면에서는 알 수 없으므로 멈춘다
    (→ data.check_unique_rows).

    순위는 대조하지 않는다. 무엇을 기준으로 매긴 순위인지 확인되지 않아,
    겹치는 것이 잘못인지 아닌지 판단할 수 없다.
    """
    keys = ["base_month", "branch_id"]
    check_unique_rows(stock, LABEL, keys, "stock_name", "종목")


def check_stock_facts(stock: pd.DataFrame) -> None:
    """한 종목의 시가총액·업종·거래소가 지점마다 같은지 본다.

    시가총액은 시장이 정하는 값이고 업종과 거래소는 종목의 성질이라 지점에
    따라 달라질 수 없다. 다르다면 종목명이 겹쳤거나 파일이 잘못 붙은 것이다.
    트리맵은 시가총액을 면적으로, 업종을 묶음으로 쓰므로 이 값이 흔들리면
    그림 자체가 달라진다.

    업종과 거래소는 비어 있는 행이 있으므로 값이 들어 있는 행끼리만 견준다.
    빈 값을 채워 넣지는 않는다(→ AGENTS.md §9).
    """
    for column in STOCK_FACT_COLUMNS:
        rows = stock
        if column in BLANK_FACT_COLUMNS:
            rows = stock[stock[column] != ""]
        if rows.empty:
            continue
        counts = rows.groupby(
            ["base_month", "stock_name"], observed=True
        )[column].nunique()
        mixed = counts[counts > 1]
        if mixed.empty:
            continue
        month, name = mixed.index[0]
        values = sorted(
            rows.loc[
                (rows["base_month"] == month)
                & (rows["stock_name"] == name),
                column,
            ]
            .unique()
            .tolist()
        )
        raise ValueError(
            f"{LABEL} 파일에서 같은 종목의 {column} 이 지점마다 다릅니다: "
            f"{month} {name} — {values[:3]}. "
            f"어긋난 종목이 {len(mixed)}개입니다. "
            "종목명이 겹쳤는지, 파일이 제대로 붙었는지 확인해 주세요."
        )


def stock_facts(stock: pd.DataFrame) -> pd.DataFrame:
    """종목마다 한 행인 표. 기준월·종목명·시가총액·업종·거래소를 담는다.

    지점을 고르지 않고 종목 자체를 보는 화면이 쓴다. 지점마다 같은 값이라는
    것은 `check_stock_facts`가 이미 확인했으므로 첫 행을 그대로 쓴다.

    순위는 넣지 않는다. 지점마다 같은 값이라고 확인된 적이 없어, 첫 행의
    순위를 종목의 순위처럼 적으면 지점별 순위인 경우에 틀린 값이 된다.
    """
    if stock.empty:
        return stock
    columns = ["base_month", "stock_name", *STOCK_FACT_COLUMNS]
    return (
        stock.loc[:, columns]
        .drop_duplicates(subset=["base_month", "stock_name"])
        .sort_values(
            ["base_month", "market_cap_usd"], ascending=[True, False]
        )
        .reset_index(drop=True)
    )


__all__ = [
    "BLANK_FACT_COLUMNS",
    "COLUMNS",
    "FILE",
    "FILE_ENV",
    "LABEL",
    "NUMBER_COLUMNS",
    "STOCK_FACT_COLUMNS",
    "TEXT_COLUMNS",
    "build",
    "check_one_row_per_stock",
    "check_stock_facts",
    "stock_facts",
]
