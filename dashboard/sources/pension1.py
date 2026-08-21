"""원본 파일 — 지점 연금 상품 상위 종목.

기준월·지점·순위마다 한 행이고, 그 한 행에 **상품 여섯 개가 가로로 펼쳐져**
있다. 연금 구분 셋(개인연금·IRP·DC) × 상품 둘(펀드·ETF)이며 상품마다
종목명·거래고객수·거래대금·순매수금액·순위변동 다섯 컬럼을 갖는다.

데이터 계층이 이것을 한 줄에 한 상품인 형태로 편다(→ build). 거래2가 상품을
펴는 것과 같은 방식이고, 여기서는 축이 둘이라 한 행이 여섯 줄이 된다
(→ dashboard/sources/transaction2.py).

**종목명이 빈 칸이면 그 줄을 만들지 않는다.** 가로로 펼친 파일에서 빈 칸은
'그 상품은 이 순위까지 없다'는 뜻이다. 이름이 없으면 화면에 적을 것이
없으므로 줄이 아예 없는 것으로 읽는다. 값을 지어내 채우지 않는다
(→ AGENTS.md §9). 지점마다 상품마다 순위 수가 달라진다.

컬럼 이름의 공백 — 원본에 `IRP_ETF_ 거래고객수`처럼 공백이 섞여 들어올 수
있다. 컬럼 이름의 공백은 떼고 맞춘다(→ _tidy_columns). 값은 건드리지 않는다.

컬럼 이름 — 여섯 상품이 같은 규칙(`<연금구분>_<상품>_<항목>`)을 따르므로
표를 손으로 적지 않고 규칙에서 만든다. 규칙이 깨지면 `BLOCK_COLUMNS`만
고친다.

단위 — 거래대금과 순매수금액은 **원**이다. 거래1의 `trade_amount`(억원)와
뜻이 겹치지 않도록 거래대금은 `trade_value`(원)에 담는다
(→ dashboard/sources/fund1.py).

부호 — 순매수금액은 순매도인 달에 음수가 되며 원본이 앞에 `-`를 붙여 담는다.

순위변동 — `+3`·`-2`·`0`처럼 부호를 붙인 글이다. 앞 달에 없던 종목이라
비교할 값이 없으면 **비운 채로 두고** 0으로 채우지 않는다. 그 빈 칸을
화면에서 `NEW`로 적는다(→ dashboard/format.py 의 format_rank_change).

원본 컬럼 이름이 바뀌면 이 파일의 표만 고친다. 다른 파일은 고치지
않는다(→ AGENTS.md §9).
"""

from __future__ import annotations

import pandas as pd

from dashboard.data import (
    PENSION_RANK_PRODUCT_TYPES,
    PENSION_TYPES,
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
#   FILE = "상품_연금통합1.pkl"   → data/상품_연금통합1.pkl
# 환경 변수를 지정하면 아래 값보다 환경 변수가 우선한다.
FILE = "상품_연금통합1.pkl"
FILE_ENV = "DASHBOARD_PENSION1_FILE"

LABEL = "상품 연금통합1"

# 원본 컬럼명 → 내부 표준 컬럼명. 한 행에 함께 있는 열쇠 컬럼만 적는다.
# 상품별 컬럼은 규칙에서 만든다(→ BLOCK_COLUMNS).
COLUMNS: dict[str, str] = {
    "기준월": "base_month",
    "CSMT_ORZ_CD": "branch_id",
    "CSMT_ORZ_NM": "branch_name",
    "순위": "stock_rank",
}

_KEY_COLUMNS = (
    "base_month",
    "branch_id",
    "branch_name",
    "stock_rank",
)

# 상품마다 붙어 있는 다섯 컬럼. 표준 이름 → 원본 이름의 끝부분.
BLOCK_COLUMNS: dict[str, str] = {
    "stock_name": "종목명",
    "trade_customer_count": "거래고객수",
    "trade_value": "거래대금",
    "net_buy_amount": "순매수금액",
    "rank_change": "순위변동",
}

# 음수를 허용하는 컬럼. 순매수금액만 순매도인 달에 음수가 된다.
SIGNED_COLUMNS = ("net_buy_amount",)

# 비어 있는 값으로 읽는 순위변동 표기. 앞 달에 없던 종목이라 비교할 값이
# 없다는 뜻이다. 부호만 있고 숫자가 없는 `-`는 변동값이 될 수 없으므로
# 여기 넣는다.
BLANK_RANK_CHANGE = ("", "-", "+", "신규", "NEW", "nan", "None", "NaT")


def block_column(
    pension_type: str, product_type: str, field: str
) -> str:
    """상품 하나의 원본 컬럼 이름. 규칙은 `<연금구분>_<상품>_<항목>`이다."""
    return f"{pension_type}_{product_type}_{BLOCK_COLUMNS[field]}"


def blocks() -> list[tuple[str, str]]:
    """원본에 가로로 펼쳐져 있는 (연금 구분, 상품) 짝."""
    return [
        (pension_type, product_type)
        for pension_type in PENSION_TYPES
        for product_type in PENSION_RANK_PRODUCT_TYPES
    ]


def build(frame: pd.DataFrame) -> pd.DataFrame:
    """표준 이름으로 바뀐 원본을 한 줄에 한 상품인 형태로 편다.

    되돌려주는 컬럼은 열쇠 넷(기준월·지점 코드·지점명·순위)에 연금 구분과
    상품, 그리고 상품별 다섯을 더한 열한 개다.

    기준 월은 `202607`이든 `2026-07`이든 날짜든 읽어서 `YYYY-MM`으로 맞춘다.
    """
    frame = _tidy_columns(frame)
    _check_columns(frame)
    parts = []
    for pension_type, product_type in blocks():
        columns = {
            block_column(pension_type, product_type, field): field
            for field in BLOCK_COLUMNS
        }
        part = frame.loc[
            :, [*_KEY_COLUMNS, *columns]
        ].rename(columns=columns)
        part.insert(len(_KEY_COLUMNS), "pension_type", pension_type)
        part.insert(len(_KEY_COLUMNS) + 1, "product_type", product_type)
        parts.append(part)
    long = pd.concat(parts, ignore_index=True)

    long["base_month"] = to_month_column(long["base_month"], "pension1")
    # 종목명이 빈 칸인 자리는 그 상품에 그 순위가 없다는 뜻이라 줄을
    # 만들지 않는다. 빈 칸을 가리는 규칙은 `to_label_column`에 있는 것을
    # 그대로 쓴다. 여기서 따로 적으면 원본이 빈 칸을 NaN으로 담았을 때
    # 한쪽만 걸러 내고 다른 쪽이 멈춘다.
    long["stock_name"] = to_label_column(
        long["stock_name"], LABEL, "stock_name", required=False
    )
    long = long[long["stock_name"] != ""].reset_index(drop=True)
    # 오류 문구에는 원본 컬럼 이름을 적는다. 표준 이름을 적으면 원본
    # 어디를 봐야 하는지 알 수 없다.
    for field in ("stock_rank", *_number_fields()):
        long[field] = _number(
            long[field],
            BLOCK_COLUMNS.get(field, "순위"),
            field in SIGNED_COLUMNS,
        )
    long["stock_rank"] = long["stock_rank"].round().astype(int)
    long["rank_change"] = _rank_change(long["rank_change"])
    check_ranks(long)
    return long


def _number_fields() -> list[str]:
    """숫자로 다루는 상품 컬럼. 종목명과 순위변동은 따로 다룬다."""
    return [
        field
        for field in BLOCK_COLUMNS
        if field not in ("stock_name", "rank_change")
    ]


def _tidy_columns(frame: pd.DataFrame) -> pd.DataFrame:
    """컬럼 이름의 공백을 뗀다. 값은 건드리지 않는다.

    원본에 `IRP_ETF_ 거래고객수`처럼 공백이 섞여 들어오는 자리가 있다.
    공백만 다른 이름을 못 찾는다고 멈추면 파일 전체가 열리지 않는다.

    공백을 뗐더니 두 컬럼의 이름이 같아지면, 어느 쪽 값이 맞는지 알 수
    없으므로 멈춘다.
    """
    tidied = {
        column: "".join(str(column).split()) for column in frame.columns
    }
    names = list(tidied.values())
    duplicated = sorted(
        {name for name in names if names.count(name) > 1}
    )
    if duplicated:
        raise ValueError(
            f"{LABEL} 파일에 공백만 다른 같은 이름의 컬럼이 있습니다: "
            f"{', '.join(duplicated[:5])}. "
            "어느 쪽 값을 써야 할지 알 수 없습니다."
        )
    return frame.rename(columns=tidied)


def _check_columns(frame: pd.DataFrame) -> None:
    """상품 컬럼이 모두 있는지 본다. 없으면 이름을 알리며 멈춘다."""
    missing = [
        block_column(pension_type, product_type, field)
        for pension_type, product_type in blocks()
        for field in BLOCK_COLUMNS
        if block_column(pension_type, product_type, field)
        not in frame.columns
    ]
    if missing:
        raise ValueError(
            f"{LABEL} 파일에 다음 컬럼이 없습니다:"
            f" {', '.join(missing[:8])}"
            f" (모두 {len(missing)}개). "
            "원본의 상품 컬럼 이름이 바뀌었으면 "
            "dashboard/sources/pension1.py 의 BLOCK_COLUMNS 를 고쳐 "
            f"주세요. 파일에 있는 컬럼: {', '.join(map(str, frame.columns))}"
        )


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
            "dashboard/sources/pension1.py 의 BLANK_RANK_CHANGE 에 "
            "그 표기를 더해 주세요."
        )
    return numbers.astype(float)


def check_ranks(long: pd.DataFrame) -> None:
    """한 지점·한 상품 안에서 순위와 종목이 겹치지 않는지 본다.

    가로로 펼쳐진 파일이라 상품마다 따로 본다. 순위가 겹치면 표에 같은
    등수가 두 번 나오고, 종목이 겹치면 같은 종목이 두 줄이 된다
    (→ data.check_unique_rows).

    순위가 몇 위까지 있는지는 보지 않는다. 종목명이 빈 칸이던 자리는 줄이
    없으므로 상품마다 끝나는 자리가 다르다.
    """
    keys = ["base_month", "branch_id", "pension_type", "product_type"]
    for column, label in (("stock_rank", "순위"), ("stock_name", "종목")):
        check_unique_rows(long, LABEL, keys, column, label)


__all__ = [
    "BLANK_RANK_CHANGE",
    "BLOCK_COLUMNS",
    "COLUMNS",
    "FILE",
    "FILE_ENV",
    "LABEL",
    "SIGNED_COLUMNS",
    "block_column",
    "blocks",
    "build",
    "check_ranks",
]
