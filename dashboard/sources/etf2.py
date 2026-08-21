"""원본 파일 — 지점 ETF 상위 종목.

기준월·지점마다 순위 1..N의 종목이 한 행씩 들어 있다. 지점 행 외에 '전체'
행도 같은 모양으로 들어 있으며, 데이터 계층이 그 행을 따로 떼어 둔다
(→ dashboard/data.py).

주식 순위표와 같은 모양이되 **업종과 거래소가 없다.** 그래서 이 원본만으로는
종목을 묶을 축이 없다(→ dashboard/sources/overseas_stock1.py).

파일 이름의 숫자와 프레임 이름이 맞지 않는다. `상품_ETF2`가 순위표이며
표준 프레임 이름은 `etf_rank`다. 이름은 파일 번호가 아니라 그 원본이 담은
모양을 따른다.

'전체'의 상위 종목은 지점 목록을 더해 만든 값이 아니라 따로 뽑은 순위표다.
같은 순위에 다른 종목이 오므로 지점 합계와 대조하지 않는다
(→ data.py의 _TOTAL_CHECK_COLUMNS).

단위 — 시가총액은 **억원**, 거래대금과 순매수금액은 **원**이다. 한 파일 안에서
단위가 갈리므로 표준 이름을 서로 다르게 둔다. 거래1의 `trade_amount`(억원)와
뜻이 겹치지 않도록 거래대금은 `trade_value`(원)에 담는다. 원본이 담은 단위를
그대로 두고 여기서 환산하지 않는다(→ AGENTS.md §9).

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
#   FILE = "상품_ETF2.pkl"     → data/상품_ETF2.pkl
# 환경 변수를 지정하면 아래 값보다 환경 변수가 우선한다.
FILE = "상품_ETF2.pkl"
FILE_ENV = "DASHBOARD_ETF2_FILE"

LABEL = "상품 ETF2"

# 원본 컬럼명 → 내부 표준 컬럼명.
COLUMNS: dict[str, str] = {
    "기준월": "base_month",
    "CSMT_ORZ_CD": "branch_id",
    "CSMT_ORZ_NM": "branch_name",
    "순위": "stock_rank",
    "종목명": "stock_name",
    "시가총액": "market_cap",
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
    "market_cap": ("시가총액", False),
    "trade_customer_count": ("거래고객수", False),
    "trade_value": ("거래대금", False),
    "net_buy_amount": ("순매수금액", True),
}

# 비어 있는 값으로 읽는 순위변동 표기. 앞 달에 없던 종목이라 비교할 값이
# 없다는 뜻이다. 부호만 있고 숫자가 없는 `-`는 변동값이 될 수 없으므로
# 여기 넣는다.
BLANK_RANK_CHANGE = ("", "-", "+", "신규", "NEW", "nan", "None", "NaT")


def build(frame: pd.DataFrame) -> pd.DataFrame:
    """표준 이름으로 바뀐 원본에서 ETF 상위 종목 프레임을 만든다.

    되돌려주는 컬럼은 `COLUMNS`의 표준 이름 10개다.

    기준 월은 `202607`이든 `2026-07`이든 날짜든 읽어서 `YYYY-MM`으로 맞춘다.
    순위 순서는 데이터 계층이 정렬로 다시 맞추므로 여기서는 값만 본다.
    """
    etf = frame.loc[:, list(COLUMNS.values())].copy()
    etf["base_month"] = to_month_column(etf["base_month"], "etf2")
    for column, required in TEXT_COLUMNS.items():
        etf[column] = to_label_column(
            etf[column], LABEL, column, required=required
        )
    for column, (label, signed) in NUMBER_COLUMNS.items():
        etf[column] = _number(etf[column], label, signed)
    etf["stock_rank"] = etf["stock_rank"].round().astype(int)
    etf["rank_change"] = _rank_change(etf["rank_change"])
    check_ranks(etf)
    return etf


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
            "dashboard/sources/etf2.py 의 BLANK_RANK_CHANGE 에 "
            "그 표기를 더해 주세요."
        )
    return numbers.astype(float)


def check_ranks(etf: pd.DataFrame) -> None:
    """한 지점의 한 달 안에서 순위와 종목이 겹치지 않는지 본다.

    순위가 겹치면 표에 같은 등수가 두 번 나오고, 종목이 겹치면 같은 종목의
    금액이 두 번 더해진다. 어느 쪽이 맞는지 화면에서는 알 수 없으므로
    멈춘다(→ data.check_unique_rows).
    """
    keys = ["base_month", "branch_id"]
    for column, label in (("stock_rank", "순위"), ("stock_name", "종목")):
        check_unique_rows(etf, LABEL, keys, column, label)


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
