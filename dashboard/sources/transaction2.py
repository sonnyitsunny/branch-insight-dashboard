"""원본 파일 — 월별 지점 연금 거래.

거래1과 같은 골격에 축이 하나 더 있다. '구분' 컬럼이 개인연금·IRP·DC를
갖고 있어, 기준월·지점마다 세 행이 들어온다. 상품은 거래1처럼 가로로
펼쳐져 있으며 데이터 계층이 한 줄에 한 상품인 형태로 편다.

'기타'에는 거래금액만 있고 거래고객수가 없다. 없는 값을 0으로 채우지 않고
비워 둔 채 넘겨 화면에 `-`로 나타나게 한다(→ AGENTS.md §9).

단위 — 거래금액은 **억원**이다. 거래1과 같은 약속이다.

원본 컬럼 이름이 바뀌면 이 파일의 표만 고친다. 다른 파일은 고치지
않는다(→ AGENTS.md §9).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from dashboard.data import (
    PENSION_TRADE_PRODUCT_TYPES,
    PENSION_TYPES,
    TRADE_PRODUCT_TOTAL,
    plain_text,
    to_month_column,
)

# 실제 데이터를 붙일 때 여기만 고치면 된다.
#
# 파일 이름만 적으면 app.py 옆의 `data/` 폴더에서 찾는다.
#   FILE = "거래2.pkl"              → data/거래2.pkl
# 환경 변수를 지정하면 아래 값보다 환경 변수가 우선한다.
FILE = "거래2.pkl"
FILE_ENV = "DASHBOARD_TRANSACTION2_FILE"

LABEL = "지점 거래2"

# 원본 컬럼명 → 내부 표준 컬럼명.
COLUMNS: dict[str, str] = {
    "기준월": "base_month",
    "CSMT_ORZ_CD": "branch_id",
    "CSMT_ORZ_NM": "branch_name",
    "구분": "pension_type",
}

_KEY_COLUMNS = ("base_month", "branch_id", "branch_name", "pension_type")

# 상품 분류 → (거래금액 컬럼, 거래고객수 컬럼).
# 거래고객수가 None이면 원본에 그 컬럼이 없다는 뜻이다. 비운 채로 넘긴다.
PRODUCT_COLUMNS: dict[str, tuple[str, str | None]] = {
    TRADE_PRODUCT_TOTAL: ("전체_거래금액", "전체_거래고객수"),
    "국내ETF": ("국내ETF_거래금액", "국내ETF_거래고객수"),
    "펀드": ("펀드_거래금액", "펀드_거래고객수"),
    "기타": ("기타_거래금액", None),
}

AMOUNT_COLUMN = "trade_amount"
COUNT_COLUMN = "trade_customer_count"


def build(frame: pd.DataFrame) -> pd.DataFrame:
    """표준 이름으로 바뀐 원본을 한 줄에 한 상품인 형태로 편다.

    되돌려주는 컬럼은 base_month·branch_id·branch_name·pension_type·
    product_type·trade_amount·trade_customer_count 일곱 개다.
    """
    _check_columns(frame)
    parts = []
    for product, (amount, count) in PRODUCT_COLUMNS.items():
        columns = [*_KEY_COLUMNS, amount]
        if count is not None:
            columns.append(count)
        part = frame.loc[:, columns].rename(
            columns={amount: AMOUNT_COLUMN, count: COUNT_COLUMN}
        )
        if count is None:
            part[COUNT_COLUMN] = np.nan
        part.insert(len(_KEY_COLUMNS), "product_type", product)
        parts.append(part)
    long = pd.concat(parts, ignore_index=True)
    long["base_month"] = to_month_column(long["base_month"], "transaction2")
    long["pension_type"] = plain_text(long["pension_type"])
    _check_pension_types(long)
    _check_keys(long)
    return long


def _check_columns(frame: pd.DataFrame) -> None:
    """상품 컬럼이 모두 있는지 본다. 없으면 이름을 알리며 멈춘다."""
    missing = [
        column
        for columns in PRODUCT_COLUMNS.values()
        for column in columns
        if column is not None and column not in frame.columns
    ]
    if missing:
        raise ValueError(
            f"{LABEL} 파일에 다음 컬럼이 없습니다: {', '.join(missing)}. "
            "원본의 상품 컬럼 이름이 바뀌었으면 "
            "dashboard/sources/transaction2.py 의 PRODUCT_COLUMNS 를 고쳐 "
            f"주세요. 파일에 있는 컬럼: {', '.join(map(str, frame.columns))}"
        )
    allowed = {TRADE_PRODUCT_TOTAL, *PENSION_TRADE_PRODUCT_TYPES}
    unknown = sorted(set(PRODUCT_COLUMNS) - allowed)
    if unknown:
        raise ValueError(
            f"{LABEL} 의 PRODUCT_COLUMNS 에 화면이 모르는 상품이 있습니다: "
            f"{', '.join(unknown)}. dashboard/data.py 의 "
            "PENSION_TRADE_PRODUCT_TYPES 에도 더해 주세요."
        )


def _check_pension_types(long: pd.DataFrame) -> None:
    """'구분' 값이 쓸 수 있는 이름인지 본다.

    낯선 이름을 그냥 두면 데이터 계층의 분류 변환에서 결측이 되어 화면에서
    조용히 사라진다. 어떤 값이 문제인지 여기서 먼저 알린다.
    """
    unknown = sorted(set(long["pension_type"]) - set(PENSION_TYPES))
    if unknown:
        raise ValueError(
            f"{LABEL} 파일의 '구분'에 쓸 수 없는 값이 있습니다: "
            f"{', '.join(unknown[:5])}. "
            f"사용할 수 있는 값: {', '.join(PENSION_TYPES)}. "
            "원본의 구분 이름이 바뀌었으면 dashboard/data.py 의 "
            "PENSION_TYPES 를 고쳐 주세요."
        )


def _check_keys(long: pd.DataFrame) -> None:
    """한 지점의 한 달·한 구분이 한 번씩만 있는지 본다."""
    keys = pd.MultiIndex.from_arrays(
        [
            long["base_month"],
            plain_text(long["branch_id"]),
            long["pension_type"],
            long["product_type"],
        ]
    )
    duplicated = keys.duplicated()
    if duplicated.any():
        month, branch_id, pension_type, product = keys[duplicated][0]
        raise ValueError(
            f"{LABEL} 파일에 같은 기준월·지점·구분이 두 번 이상 있습니다: "
            f"{month} 지점 {branch_id} {pension_type} ({product}). "
            "한 지점의 한 구분은 한 달에 한 행이어야 합니다."
        )
