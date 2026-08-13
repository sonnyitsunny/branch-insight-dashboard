"""원본 파일 — 월별 지점 거래.

기준월·지점마다 한 행이고 '전체' 합계 행이 월마다 하나 더 있다. 상품이
가로로 펼쳐져 있어 한 상품이 거래금액·거래고객수 두 컬럼을 차지한다.
데이터 계층은 한 줄에 한 상품인 형태로 편다. 상품이 늘어도 표준 프레임의
컬럼은 늘지 않는다.

단위 — 거래금액은 **억원**이다. 자산4와 같은 약속이다. 거래고객수는 명이며
원본 값을 그대로 쓴다.

'전체' 상품은 5개 상품의 합이 아닐 수 있어 더해서 만들지 않고 원본 값을
그대로 쓴다. 한 고객이 두 상품을 거래하면 거래고객수는 상품별 합보다
작다(→ dashboard/data.py의 TRADE_PRODUCT_TOTAL).

원본 컬럼 이름이 바뀌면 이 파일의 표만 고친다. 다른 파일은 고치지
않는다(→ AGENTS.md §9).
"""

from __future__ import annotations

import pandas as pd

from dashboard.data import (
    TRADE_PRODUCT_TOTAL,
    TRADE_PRODUCT_TYPES,
    plain_text,
    to_month_column,
)

# 실제 데이터를 붙일 때 여기만 고치면 된다.
#
# 파일 이름만 적으면 app.py 옆의 `data/` 폴더에서 찾는다.
#   FILE = "거래1.pkl"              → data/거래1.pkl
# 환경 변수를 지정하면 아래 값보다 환경 변수가 우선한다.
FILE = "거래1.pkl"
FILE_ENV = "DASHBOARD_TRANSACTION1_FILE"

LABEL = "지점 거래1"

# 원본 컬럼명 → 내부 표준 컬럼명.
# 상품 컬럼은 이름 하나가 분류와 지표를 함께 가리키므로 아래 표에 따로
# 적는다.
COLUMNS: dict[str, str] = {
    "기준월": "base_month",
    "CSMT_ORZ_CD": "branch_id",
    "CSMT_ORZ_NM": "branch_name",
}

_KEY_COLUMNS = ("base_month", "branch_id", "branch_name")

# 상품 분류 → (거래금액 컬럼, 거래고객수 컬럼).
# 원본에서 상품 이름이 바뀌면 오른쪽 컬럼 이름만 고친다. 왼쪽 이름은
# 화면까지 그대로 가며 `dashboard.data.ALL_TRADE_PRODUCT_TYPES`와 같아야
# 한다.
PRODUCT_COLUMNS: dict[str, tuple[str, str]] = {
    TRADE_PRODUCT_TOTAL: ("전체_거래금액", "전체_거래고객수"),
    "국내주식": ("국내주식_거래금액", "국내주식_거래고객수"),
    "해외주식": ("해외주식_거래금액", "해외주식_거래고객수"),
    "국내ETF": ("국내ETF_거래금액", "국내ETF_거래고객수"),
    "채권": ("채권_거래금액", "채권_거래고객수"),
    "펀드": ("펀드_거래금액", "펀드_거래고객수"),
}

AMOUNT_COLUMN = "trade_amount"
COUNT_COLUMN = "trade_customer_count"


def build(frame: pd.DataFrame) -> pd.DataFrame:
    """표준 이름으로 바뀐 원본을 한 줄에 한 상품인 형태로 편다.

    되돌려주는 컬럼은 base_month·branch_id·branch_name·product_type·
    trade_amount·trade_customer_count 여섯 개다.

    기준 월은 `202601`이든 `2026-01`이든 날짜든 읽어서 `YYYY-MM`으로 맞춘다.
    값은 고치지 않는다.
    """
    _check_columns(frame)
    parts = []
    for product, (amount, count) in PRODUCT_COLUMNS.items():
        part = frame.loc[
            :, [*_KEY_COLUMNS, amount, count]
        ].rename(columns={amount: AMOUNT_COLUMN, count: COUNT_COLUMN})
        part.insert(len(_KEY_COLUMNS), "product_type", product)
        parts.append(part)
    long = pd.concat(parts, ignore_index=True)
    long["base_month"] = to_month_column(long["base_month"], "transaction1")
    _check_keys(long)
    return long


def _check_columns(frame: pd.DataFrame) -> None:
    """상품 컬럼이 모두 있는지 본다. 없으면 이름을 알리며 멈춘다.

    키 컬럼은 `sources.rename`이 이미 확인했다. 여기서는 상품 컬럼만 본다.
    """
    missing = [
        column
        for columns in PRODUCT_COLUMNS.values()
        for column in columns
        if column not in frame.columns
    ]
    if missing:
        raise ValueError(
            f"{LABEL} 파일에 다음 컬럼이 없습니다: {', '.join(missing)}. "
            "원본의 상품 컬럼 이름이 바뀌었으면 "
            "dashboard/sources/transaction1.py 의 PRODUCT_COLUMNS 를 고쳐 "
            f"주세요. 파일에 있는 컬럼: {', '.join(map(str, frame.columns))}"
        )
    unknown = sorted(
        set(PRODUCT_COLUMNS) - {TRADE_PRODUCT_TOTAL, *TRADE_PRODUCT_TYPES}
    )
    if unknown:
        raise ValueError(
            f"{LABEL} 의 PRODUCT_COLUMNS 에 화면이 모르는 상품이 있습니다: "
            f"{', '.join(unknown)}. "
            "dashboard/data.py 의 TRADE_PRODUCT_TYPES 에도 더해 주세요."
        )


def _check_keys(long: pd.DataFrame) -> None:
    """한 지점의 한 달이 한 번씩만 있는지 본다.

    두 번 있으면 어느 값이 맞는지 알 수 없고, 화면의 합계는 조용히 두 배가
    된다.
    """
    keys = pd.MultiIndex.from_arrays(
        [
            long["base_month"],
            plain_text(long["branch_id"]),
            long["product_type"],
        ]
    )
    duplicated = keys.duplicated()
    if duplicated.any():
        month, branch_id, product = keys[duplicated][0]
        raise ValueError(
            f"{LABEL} 파일에 같은 기준월·지점이 두 번 이상 있습니다: "
            f"{month} 지점 {branch_id} ({product}). "
            "한 지점은 한 달에 한 행이어야 합니다."
        )
