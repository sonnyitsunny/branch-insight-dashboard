"""상품 탭 선언.

무엇을 보여줄지 여기에 한 번만 적는다. Dash 화면과 정적 HTML이 이 선언을
함께 읽는다(→ dashboard/tabs/registry.py).

**줄마다 구분 선택이 하나씩 있다.** 그 줄의 왼쪽 표와 오른쪽 트리맵이 같은
값을 받아 같은 구분을 보여준다. 컨트롤을 카드마다 따로 두면 두 값이 어긋나
한 줄에서 서로 다른 지점을 보게 된다.

두 줄은 서로 따로 움직인다 — 국내는 '전체', 해외는 어느 지점을 놓고 볼 수
있다(→ registry.Tab.select_groups).

**한 줄이 원본 두 개로 만들어진다.** 왼쪽 표는 지점별 거래 상위 종목,
오른쪽 트리맵은 시가총액 상위 종목의 지점별 거래를 쓴다. 행을 고르는 기준이
달라 두 카드의 종목 목록은 같지 않다.

첫 줄이 국내주식(상품_국내주식1·2), 둘째 줄이 해외주식(상품_해외주식1·2)이다.
표와 트리맵을 번갈아 선언하면 그리드가 짝마다 한 줄로 놓는다
(→ registry.grid_order).

셋째 줄은 ETF(상품_ETF2)와 펀드(상품_펀드1) 표 둘이다. 짝이 되는 트리맵이
없어 표끼리 나란히 서고, 줄을 따로 만들지 않고 각 표의 헤더 안에 구분
컨트롤을 넣는다(→ registry.PLACE_TABLE). 두 표는 서로 다른 줄이라 구분을
따로 고른다. 컨트롤이 카드 안에 있는 줄은 한 그리드에 함께 놓인다
(→ registry.Tab.grid_rows).

맨 아래는 연금 상품(상품_연금통합1) 표 하나가 화면 폭을 다 쓴다. 연금 구분
셋(개인연금·IRP·DC)을 가로로 늘어놓아 컬럼이 열여섯이며, 라디오로 고른 상품
하나(ETF 또는 펀드)를 보여준다. **컬럼 이름이 그 라디오를 따라 바뀐다**
(→ registry.Table.columns).

해외주식은 두 가지가 다르다. 순위표에 시가총액이 없어 표 컬럼이 하나 적고,
트리맵의 시가총액은 달러라 표기 함수가 다르다(→ figures.OVERSEAS_HOVER).
"""

from __future__ import annotations

import unicodedata

import pandas as pd

from dashboard import format as fmt
from dashboard.data import (
    PENSION_RANK_PRODUCT_TYPES,
    TOTAL_LABEL,
    DashboardData,
)
from dashboard.grid import (
    COUNT_FORMAT,
    MONEY_FORMAT,
    NUMBER_FORMAT,
    RANK_CHANGE_FORMAT,
    SIGNED_NUMBER_FORMAT,
    TEXT_SUFFIX,
    Column,
)
from dashboard.tabs.product import figures as product_figures
from dashboard.tabs.product import metrics
from dashboard.tabs.registry import (
    KIND_RADIO,
    PLACE_TABLE,
    TABLE_PLACE_GRID,
    Chart,
    Select,
    Tab,
    Table,
)

# 표의 조작 안내. 켜 둔 기능만 적는다(→ grid.DEFAULT_COL_DEF).
TABLE_GUIDE = "헤더 클릭 정렬 · 경계 드래그로 너비 조절 · 행 클릭 강조"

# 트리맵 읽는 법. 색이 무엇을 뜻하는지 먼저 알린다 — 순매수와 순매도를
# 색으로만 가르지 않도록 글로도 적는다(→ AGENTS.md §5.2). 칸 크기와 색의
# 크기는 원래 값에 비례하지 않으므로(→ metrics.area_values) 정확한 값은
# hover로 읽는다(→ figures.DOMESTIC_HOVER).
CHART_NOTE = "빨간색: 순매수, 파란색: 순매도"

# 보여줄 행이 없을 때의 안내. 원본을 못 읽으면 지점 목록까지 비어 아무
# 반응이 없는 화면이 된다. 그때 왜 비었는지 여기서 알린다(→ AGENTS.md §11).
TABLE_EMPTY_NOTE = (
    "국내주식 순위 원본을 읽지 못했습니다."
    " 상품_국내주식1.pkl 을 data 폴더에 두고 다시 실행해 주세요."
)
CHART_EMPTY_NOTE = (
    "국내주식 종목 원본을 읽지 못했습니다."
    " 상품_국내주식2.pkl 을 data 폴더에 두고 다시 실행해 주세요."
)
OVERSEAS_TABLE_EMPTY_NOTE = (
    "해외주식 순위 원본을 읽지 못했습니다."
    " 상품_해외주식1.pkl 을 data 폴더에 두고 다시 실행해 주세요."
)
OVERSEAS_CHART_EMPTY_NOTE = (
    "해외주식 종목 원본을 읽지 못했습니다."
    " 상품_해외주식2.pkl 을 data 폴더에 두고 다시 실행해 주세요."
)
ETF_TABLE_EMPTY_NOTE = (
    "ETF 순위 원본을 읽지 못했습니다."
    " 상품_ETF2.pkl 을 data 폴더에 두고 다시 실행해 주세요."
)
FUND_TABLE_EMPTY_NOTE = (
    "펀드 순위 원본을 읽지 못했습니다."
    " 상품_펀드1.pkl 을 data 폴더에 두고 다시 실행해 주세요."
)
PENSION_TABLE_EMPTY_NOTE = (
    "연금 상품 순위 원본을 읽지 못했습니다."
    " 상품_연금통합1.pkl 을 data 폴더에 두고 다시 실행해 주세요."
)

# 선택 컨트롤 키. 콜백과 정적 HTML이 같은 이름을 쓴다. 줄마다 키가 달라야
# 두 줄이 서로의 값을 덮지 않는다.
SELECT_BRANCH = "branch"
SELECT_OVERSEAS_BRANCH = "overseas-branch"
SELECT_ETF_BRANCH = "etf-branch"
SELECT_FUND_BRANCH = "fund-branch"
SELECT_PENSION_BRANCH = "pension-branch"
# 연금 표만 고르는 것이 둘이다. 지점과 상품(ETF·펀드)을 함께 고른다.
SELECT_PENSION_PRODUCT = "pension-product"

# 줄의 이름. 같은 이름을 가진 표·차트가 한 선택을 따른다
# (→ registry.Tab.select_groups).
OVERSEAS_GROUP = "overseas"
ETF_GROUP = "etf"
FUND_GROUP = "fund"
PENSION_GROUP = "pension"

# 선택 컨트롤에 붙는 이름. 고르는 값에 지점과 '전체'가 함께 들어 있어
# '지점'이라고 적으면 '전체'가 그 이름에 들어맞지 않는다.
SELECT_LABEL = "구분"

# 연금 표의 상품 선택에 붙는 이름. 라디오는 고른 값이 늘 보이므로 이름을
# 붙이지 않는다(→ layout._radio).
PRODUCT_LABEL = ""

# 해외주식 트리맵이 면적으로 쓰는 컬럼. 값이 달러라 국내주식과 이름이
# 다르다(→ dashboard/data.py 의 OVERSEAS_STOCK_CAP_COLUMNS).
OVERSEAS_CAP_COLUMN = "market_cap_usd"

# 나란히 선 두 카드의 높이. 다른 탭 차트가 함께 쓰는 기본 높이(360px)로는
# 트리맵 칸 하나에 돌아가는 자리가 좁아 종목명이 들어가지 않는다. 이 탭에서만
# 높인다(→ registry.Chart.height).
#
# **두 곳에 같은 값을 쓴다.** 표와 트리맵이 한 줄에 나란히 서므로 한쪽만
# 높이면 아랫선이 어긋난다.
CARD_HEIGHT = "560px"

# 순위 컬럼 폭(px). 두 자리 숫자만 들어가므로 남는 폭을 나눠 갖지 않는다.
RANK_COLUMN_WIDTH = 76
# 순위변동 컬럼 폭(px). 부호와 한 자리 숫자만 들어간다.
CHANGE_COLUMN_WIDTH = 96

# 네 순위표(국내주식·해외주식·ETF·펀드)가 함께 쓰는 컬럼. 원본마다 없는
# 항목이 있어 컬럼 수만 다르고 나머지는 같다 — 해외주식과 펀드에는 업종·
# 시가총액이 없다(→ dashboard/sources/overseas_stock1.py, fund1.py).
#
# 시가총액은 어느 표에도 두지 않는다. 지점이 무엇을 얼마나 사고팔았는지
# 보는 표라 시장이 정하는 값은 자리를 차지할 뿐이다. 트리맵은 그 값을 칸
# 크기로 계속 쓴다(→ metrics.area_values, figures.DOMESTIC_HOVER).
_RANK_COLUMN = Column(
    field="stock_rank",
    header="순위",
    min_width=RANK_COLUMN_WIDTH,
    to_text=fmt.format_number,
    js_format=NUMBER_FORMAT,
    width=RANK_COLUMN_WIDTH,
    flex=0,
)
_NAME_COLUMN = Column(
    field="stock_name",
    header="종목명",
    min_width=130,
    to_text=str,
    flex=2,
)
_SECTOR_COLUMN = Column(
    field="sector",
    header="업종",
    min_width=110,
    to_text=str,
    flex=2,
)
_CUSTOMER_COLUMN = Column(
    field="trade_customer_count",
    header="거래고객수",
    min_width=120,
    to_text=fmt.format_count,
    js_format=COUNT_FORMAT,
)
# 금액은 파이썬이 문구까지 만들어 담는다(→ grid.MONEY_FORMAT).
#
# 억원 숫자 하나로 적고 단위는 컬럼 이름이 말한다. 조·억·만으로 풀어 쓰면
# ('1,655억 9,151만원') 자리 이름이 행마다 달라져 위아래 값의 크기를 견주기
# 어렵다(→ format.format_won_as_100m). 원본은 원 단위다(→ data.py).
_TRADE_VALUE_COLUMN = Column(
    field="trade_value",
    header="거래대금(억원)",
    min_width=130,
    to_text=fmt.format_won_as_100m,
    js_format=MONEY_FORMAT,
    flex=2,
)
# 순매수는 순매도인 종목에서 음수가 된다. 부호를 함께 적고 증감 색을
# 입힌다. 색만으로 구분하지 않도록 부호가 늘 함께 나온다.
_NET_BUY_COLUMN = Column(
    field="net_buy_amount",
    header="순매수금액(억원)",
    min_width=140,
    to_text=fmt.format_signed_won_as_100m,
    js_format=MONEY_FORMAT,
    growth=True,
    flex=2,
)
_RANK_CHANGE_COLUMN = Column(
    field="rank_change",
    header="순위변동",
    min_width=CHANGE_COLUMN_WIDTH,
    to_text=fmt.format_signed_number,
    js_format=SIGNED_NUMBER_FORMAT,
    width=CHANGE_COLUMN_WIDTH,
    growth=True,
    flex=0,
)
# 해외주식 원본에는 앞 달에 없던 종목이 있어 순위변동이 비어 있는 행이
# 온다. 그 자리를 `-`가 아니라 NEW로 적는다
# (→ format.format_rank_change). 국내주식 원본에는 빈 칸이 없어 그대로
# 둔다. 빈 칸이 생기면 그때 이 컬럼으로 바꾼다.
_NEW_RANK_CHANGE_COLUMN = Column(
    field="rank_change",
    header="순위변동",
    min_width=CHANGE_COLUMN_WIDTH,
    to_text=fmt.format_rank_change,
    js_format=RANK_CHANGE_FORMAT,
    width=CHANGE_COLUMN_WIDTH,
    growth=True,
    flex=0,
)

TABLE_COLUMNS = (
    _RANK_COLUMN,
    _NAME_COLUMN,
    _SECTOR_COLUMN,
    _CUSTOMER_COLUMN,
    _TRADE_VALUE_COLUMN,
    _NET_BUY_COLUMN,
    _RANK_CHANGE_COLUMN,
)

OVERSEAS_TABLE_COLUMNS = (
    _RANK_COLUMN,
    _NAME_COLUMN,
    _SECTOR_COLUMN,
    _CUSTOMER_COLUMN,
    _TRADE_VALUE_COLUMN,
    _NET_BUY_COLUMN,
    _NEW_RANK_CHANGE_COLUMN,
)

# ETF 원본에는 업종이 없어 그 컬럼이 빠진다(→ dashboard/sources/etf2.py).
ETF_TABLE_COLUMNS = (
    _RANK_COLUMN,
    _NAME_COLUMN,
    _CUSTOMER_COLUMN,
    _TRADE_VALUE_COLUMN,
    _NET_BUY_COLUMN,
    _NEW_RANK_CHANGE_COLUMN,
)

# 펀드 원본에도 업종이 없어 ETF 표와 같은 컬럼이 된다. 원본이 다르므로
# 따로 적어 둔다(→ dashboard/sources/fund1.py).
FUND_TABLE_COLUMNS = (
    _RANK_COLUMN,
    _NAME_COLUMN,
    _CUSTOMER_COLUMN,
    _TRADE_VALUE_COLUMN,
    _NET_BUY_COLUMN,
    _NEW_RANK_CHANGE_COLUMN,
)


# 연금 표의 컬럼. 연금 구분 셋을 가로로 늘어놓아 다섯 항목이 세 번
# 되풀이된다. 구분마다 필드 이름 앞에 붙이는 말(→ metrics.pension_rows).
PENSION_FIELDS: dict[str, str] = {
    "개인연금": "personal",
    "IRP": "irp",
    "DC": "dc",
}

# 되풀이되는 다섯 항목. (표준 컬럼, 헤더 뒷부분, 최소 너비, 표기 함수,
# 표시 형식, 증감 색) 순이다. 순위변동은 값이 없는 까닭이 둘이라 문구를
# 표 쪽에서 만들어 담는다(→ _pension_rows, grid._cell_text).
_PENSION_ITEMS = (
    ("stock_name", "종목명", 150, str, None, False),
    ("trade_customer_count", "거래고객수", 120, fmt.format_count,
     COUNT_FORMAT, False),
    ("trade_value", "거래대금", 130, fmt.format_revenue,
     MONEY_FORMAT, False),
    ("net_buy_amount", "순매수금액", 140, fmt.format_revenue_delta,
     MONEY_FORMAT, True),
    ("rank_change", "순위변동", CHANGE_COLUMN_WIDTH,
     fmt.format_rank_change, MONEY_FORMAT, True),
)

# 헤더 글자 한 칸이 차지하는 너비(px)와 좌우 여백. 한글은 두 칸으로 센다.
# 컬럼이 열여섯이라 남는 폭을 나눠 가지면 한 칸이 좁아져 이름이 말줄임으로
# 잘린다. 이름이 들어갈 만큼을 최소 너비로 잡아 두고, 화면보다 넓어지면
# 가로로 밀어 본다(→ export_html의 fitColumns, grid.build_column_defs).
HEADER_CELL_WIDTH = 8
HEADER_PADDING = 34


def header_width(header: str) -> int:
    """헤더 글자가 잘리지 않는 최소 너비(px).

    글자 수로 잡는다. 실제 글꼴 너비를 잴 수 없으므로 넉넉한 쪽으로
    센다 — 좁아서 잘리는 것보다 조금 넓은 편이 낫다.
    """
    cells = sum(
        2 if unicodedata.east_asian_width(letter) in "WF" else 1
        for letter in header
    )
    return HEADER_PADDING + cells * HEADER_CELL_WIDTH


# 순위 컬럼은 왼쪽에 고정한다. 컬럼이 열여섯이라 가로로 훑는 동안 몇 위의
# 줄을 보고 있는지 놓치지 않게 한다(→ grid.Column.pinned).
_PENSION_RANK_COLUMN = Column(
    field="stock_rank",
    header="순위",
    min_width=RANK_COLUMN_WIDTH,
    to_text=fmt.format_number,
    js_format=NUMBER_FORMAT,
    width=RANK_COLUMN_WIDTH,
    pinned=True,
    flex=0,
)


def pension_field(pension_type: str, column: str) -> str:
    """연금 구분 하나의 표 필드 이름."""
    return f"{PENSION_FIELDS[pension_type]}_{column}"


def pension_columns(selection: dict | None = None) -> tuple[Column, ...]:
    """고른 상품의 연금 표 컬럼 열여섯 개.

    헤더에 상품 이름을 함께 적는다. 같은 다섯 항목이 세 번 되풀이되므로,
    구분만 적고 상품을 빼면 표만 보고는 ETF인지 펀드인지 알 수 없다.
    컬럼 수와 순서는 상품이 바뀌어도 같다(→ registry.Table.columns).
    """
    product = _chosen_product(selection or {})
    columns = [_PENSION_RANK_COLUMN]
    for pension_type in PENSION_FIELDS:
        for (
            column,
            label,
            min_width,
            to_text,
            js_format,
            growth,
        ) in _PENSION_ITEMS:
            header = f"{pension_type} {product} {label}"
            # 이름이 잘리지 않을 만큼은 넓어야 한다. 값보다 헤더가 길다.
            # 너비는 상품 중 가장 긴 이름에 맞춘다. 상품마다 다르게 잡으면
            # 라디오를 누를 때마다 컬럼이 들썩이고, 정적 HTML은 첫 화면의
            # 너비를 그대로 쓰므로 다른 상품에서 이름이 잘린다.
            fits = max(
                min_width,
                *(
                    header_width(f"{pension_type} {name} {label}")
                    for name in PENSION_RANK_PRODUCT_TYPES
                ),
            )
            columns.append(
                Column(
                    field=pension_field(pension_type, column),
                    header=header,
                    min_width=fits,
                    to_text=to_text,
                    js_format=js_format,
                    width=fits,
                    growth=growth,
                    flex=2,
                )
            )
    return tuple(columns)


# --- 선택 목록 ---------------------------------------------------------------
def _branch_names(data: DashboardData) -> list[str]:
    """구분 선택 목록. 지점들과 '전체'가 함께 들어간다.

    원본들이 같은 지점을 담고 있어야 표와 트리맵이 같은 값을 보여줄 수
    있다. 국내주식 순위 원본을 기준으로 삼고, 그것이 없으면 다음 원본에서
    차례로 읽는다. 어느 원본이 빠져도 나머지로 목록을 만들 수 있어야 그
    카드만 안내 상태로 남고 나머지 화면이 열린다.
    """
    for stock, total in (
        (data.domestic_stock_rank, data.domestic_stock_rank_total),
        (data.domestic_stock_cap, data.domestic_stock_cap_total),
        (data.overseas_stock_rank, data.overseas_stock_rank_total),
        (data.overseas_stock_cap, data.overseas_stock_cap_total),
        (data.etf_rank, data.etf_rank_total),
        (data.fund_rank, data.fund_rank_total),
    ):
        names = metrics.scope_names(stock, total, TOTAL_LABEL)
        if names:
            return names
    return []


def _default_branch(data: DashboardData) -> str:
    names = _branch_names(data)
    if TOTAL_LABEL in names:
        return TOTAL_LABEL
    return names[0] if names else ""


def _product_types(_data: DashboardData) -> list[str]:
    """연금 표에서 고를 수 있는 상품. 원본이 담고 있는 둘이다."""
    return list(PENSION_RANK_PRODUCT_TYPES)


def _default_product(_data: DashboardData) -> str:
    return PENSION_RANK_PRODUCT_TYPES[0]


def _chosen_product(selection: dict) -> str:
    """고른 상품. 선택이 비어 있으면 첫 화면의 기본값을 쓴다."""
    return (
        selection.get(SELECT_PENSION_PRODUCT)
        or PENSION_RANK_PRODUCT_TYPES[0]
    )


def _chosen_branch(
    data: DashboardData, selection: dict, key: str = SELECT_BRANCH
) -> str:
    """고른 구분. 선택이 비어 있으면 첫 화면의 기본값을 쓴다.

    줄마다 키가 다르므로 어느 줄의 값을 볼지 함께 받는다.
    """
    return selection.get(key) or _default_branch(data)


# --- 표 만들기 ---------------------------------------------------------------
def _rank_rows(
    stock, stock_total, data: DashboardData, selection: dict, key: str
):
    """고른 구분의 상위 종목 행.

    합계 행은 두지 않는다. 순위표의 값은 종목마다 다른 것이라 세로로 더할
    수 있는 값이 아니다.
    """
    rows = metrics.branch_rows(
        stock,
        stock_total,
        _chosen_branch(data, selection, key),
        TOTAL_LABEL,
    )
    return None, rows


def _table_rows(data: DashboardData, selection: dict):
    return _rank_rows(
        data.domestic_stock_rank,
        data.domestic_stock_rank_total,
        data,
        selection,
        SELECT_BRANCH,
    )


def _overseas_table_rows(data: DashboardData, selection: dict):
    return _rank_rows(
        data.overseas_stock_rank,
        data.overseas_stock_rank_total,
        data,
        selection,
        SELECT_OVERSEAS_BRANCH,
    )


def _etf_table_rows(data: DashboardData, selection: dict):
    return _rank_rows(
        data.etf_rank,
        data.etf_rank_total,
        data,
        selection,
        SELECT_ETF_BRANCH,
    )


def _fund_table_rows(data: DashboardData, selection: dict):
    return _rank_rows(
        data.fund_rank,
        data.fund_rank_total,
        data,
        selection,
        SELECT_FUND_BRANCH,
    )


def _pension_table_rows(data: DashboardData, selection: dict):
    """고른 구분·상품의 연금 상위 종목 행.

    원본은 한 줄에 한 상품이다. 화면은 연금 구분 셋을 가로로 늘어놓으므로
    여기서 다시 편다. 합계 행은 두지 않는다 — 종목마다 다른 값이라 세로로
    더할 수 있는 값이 아니다.
    """
    rows = metrics.branch_rows(
        data.pension_rank,
        data.pension_rank_total,
        _chosen_branch(data, selection, SELECT_PENSION_BRANCH),
        TOTAL_LABEL,
    )
    product = _chosen_product(selection)
    if rows is not None and len(rows):
        rows = rows[rows["product_type"] == product]
    return None, _pension_wide(rows)


def _pension_wide(rows) -> pd.DataFrame:
    """연금 구분을 가로로 늘어놓는다. 줄을 맞추는 것은 순위다.

    구분마다 순위가 몇 위까지 있는지 다르다. 어느 구분에 그 순위가 없으면
    그 다섯 칸은 비운다. 순위를 맞춰 놓지 않고 각자 채우면 한 줄에 서로
    다른 등수가 나란히 서게 된다.
    """
    if rows is None or len(rows) == 0:
        return pd.DataFrame()
    parts = []
    for pension_type in PENSION_FIELDS:
        part = rows[rows["pension_type"] == pension_type].set_index(
            "stock_rank"
        )
        part = part[[column for column, *_rest in _PENSION_ITEMS]]
        part = part.rename(
            columns={
                column: pension_field(pension_type, column)
                for column, *_rest in _PENSION_ITEMS
            }
        )
        parts.append(part)
    wide = pd.concat(parts, axis=1).sort_index()
    wide.insert(0, "stock_rank", wide.index)
    for pension_type in PENSION_FIELDS:
        _pension_rank_text(wide, pension_type)
    return wide.reset_index(drop=True)


def _pension_rank_text(wide: pd.DataFrame, pension_type: str) -> None:
    """순위변동 칸에 적을 문구를 함께 담는다.

    이 컬럼은 값이 없는 까닭이 둘이다. 앞 달에 없던 종목이면 `NEW`,
    그 구분에 그 순위가 아예 없으면 `-`다. 값만 보고는 가릴 수 없으므로
    여기서 문구를 만들어 보낸다(→ grid._cell_text).

    줄이 있는지는 종목명으로 가린다. 이름이 없는 자리는 그 구분에 그
    순위가 없다는 뜻이다(→ _pension_wide).
    """
    field = pension_field(pension_type, "rank_change")
    name = pension_field(pension_type, "stock_name")
    wide[f"{field}{TEXT_SUFFIX}"] = [
        fmt.format_rank_change(change)
        if isinstance(stock_name, str) and stock_name
        else fmt.EMPTY_TEXT
        for stock_name, change in zip(wide[name], wide[field])
    ]


def _empty_note(stock, stock_total, note: str) -> str:
    """원본을 못 읽었으면 그 안내, 읽었으면 빈 문구."""
    return note if stock.empty and stock_total.empty else ""


def _table_text(data: DashboardData) -> str:
    return _empty_note(
        data.domestic_stock_rank,
        data.domestic_stock_rank_total,
        TABLE_EMPTY_NOTE,
    )


def _overseas_table_text(data: DashboardData) -> str:
    return _empty_note(
        data.overseas_stock_rank,
        data.overseas_stock_rank_total,
        OVERSEAS_TABLE_EMPTY_NOTE,
    )


def _etf_table_text(data: DashboardData) -> str:
    return _empty_note(
        data.etf_rank, data.etf_rank_total, ETF_TABLE_EMPTY_NOTE
    )


def _fund_table_text(data: DashboardData) -> str:
    return _empty_note(
        data.fund_rank, data.fund_rank_total, FUND_TABLE_EMPTY_NOTE
    )


def _pension_table_text(data: DashboardData) -> str:
    return _empty_note(
        data.pension_rank,
        data.pension_rank_total,
        PENSION_TABLE_EMPTY_NOTE,
    )


# --- 트리맵 만들기 -----------------------------------------------------------
def _cap_treemap(
    stock,
    stock_total,
    data: DashboardData,
    selection: dict,
    key: str,
    cap_column: str,
    hover,
):
    """고른 구분의 시가총액 상위 종목 트리맵.

    면적 기준이 되는 가장 작은 시가총액은 지점이 아니라 전체 종목에서
    구한다. 지점마다 다시 구하면 같은 종목의 칸 크기가 구분을 바꿀 때마다
    달라진다(→ metrics.area_floor).

    국내주식과 해외주식은 시가총액 컬럼과 단위가 다르므로 그 이름과 hover
    선언만 갈아 끼운다. 두 그림의 칸 크기는 각자 안에서만 견준 값이라
    서로 견주지 않는다.
    """
    rows = metrics.branch_rows(
        stock,
        stock_total,
        _chosen_branch(data, selection, key),
        TOTAL_LABEL,
    )
    floor = metrics.area_floor(
        stock if not stock.empty else stock_total, cap_column
    )
    return product_figures.treemap_figure(
        metrics.treemap_rows(rows, floor, cap_column), hover
    )


def _treemap(data: DashboardData, selection: dict):
    return _cap_treemap(
        data.domestic_stock_cap,
        data.domestic_stock_cap_total,
        data,
        selection,
        SELECT_BRANCH,
        metrics.CAP_COLUMN,
        product_figures.DOMESTIC_HOVER,
    )


def _overseas_treemap(data: DashboardData, selection: dict):
    return _cap_treemap(
        data.overseas_stock_cap,
        data.overseas_stock_cap_total,
        data,
        selection,
        SELECT_OVERSEAS_BRANCH,
        OVERSEAS_CAP_COLUMN,
        product_figures.OVERSEAS_HOVER,
    )


def _chart_text(data: DashboardData) -> str:
    return _empty_note(
        data.domestic_stock_cap,
        data.domestic_stock_cap_total,
        CHART_EMPTY_NOTE,
    )


def _overseas_chart_text(data: DashboardData) -> str:
    return _empty_note(
        data.overseas_stock_cap,
        data.overseas_stock_cap_total,
        OVERSEAS_CHART_EMPTY_NOTE,
    )


def _context(data: DashboardData) -> dict:
    return {"branch_names": _branch_names(data)}


TAB = Tab(
    value="product",
    label="상품",
    build_context=_context,
    # 줄마다 선택 컨트롤이 하나씩이다. 같은 `group` 이름을 가진 표·차트
    # 위에 그 줄이 놓인다(→ registry.Tab.select_groups).
    selects=(
        Select(
            key=SELECT_BRANCH,
            label=SELECT_LABEL,
            options=_branch_names,
            default=_default_branch,
        ),
        Select(
            key=SELECT_OVERSEAS_BRANCH,
            label=SELECT_LABEL,
            options=_branch_names,
            default=_default_branch,
            group=OVERSEAS_GROUP,
        ),
        # ETF·펀드 줄은 카드가 표 하나뿐이라 줄을 따로 만들지 않고 그 표의
        # 헤더 안에 컨트롤을 넣는다(→ registry.PLACE_TABLE). 두 줄이 한
        # 그리드에 나란히 놓인다(→ registry.Tab.grid_rows).
        Select(
            key=SELECT_ETF_BRANCH,
            label=SELECT_LABEL,
            options=_branch_names,
            default=_default_branch,
            place=PLACE_TABLE,
            group=ETF_GROUP,
        ),
        Select(
            key=SELECT_FUND_BRANCH,
            label=SELECT_LABEL,
            options=_branch_names,
            default=_default_branch,
            place=PLACE_TABLE,
            group=FUND_GROUP,
        ),
        # 연금 줄만 고르는 것이 둘이다. 상품은 값이 둘뿐이라 펼치지 않고
        # 라디오로 둔다(→ registry.KIND_RADIO).
        Select(
            key=SELECT_PENSION_BRANCH,
            label=SELECT_LABEL,
            options=_branch_names,
            default=_default_branch,
            place=PLACE_TABLE,
            group=PENSION_GROUP,
        ),
        Select(
            key=SELECT_PENSION_PRODUCT,
            label=PRODUCT_LABEL,
            options=_product_types,
            default=_default_product,
            kind=KIND_RADIO,
            place=PLACE_TABLE,
            group=PENSION_GROUP,
        ),
    ),
    # 표와 차트를 같은 순서로 선언한다. 그리드가 둘을 번갈아 놓아
    # 윗줄이 국내주식, 아랫줄이 해외주식이 된다(→ registry.grid_order).
    tables=(
        Table(
            title="국내주식 거래 상위 종목",
            columns=TABLE_COLUMNS,
            build=_table_rows,
            description=_table_text,
            guide=TABLE_GUIDE,
            key="stock-rank",
            # 오른쪽 트리맵과 나란히 놓는다(→ registry.TABLE_PLACE_GRID).
            place=TABLE_PLACE_GRID,
            height=CARD_HEIGHT,
        ),
        Table(
            title="해외주식 거래 상위 종목",
            columns=OVERSEAS_TABLE_COLUMNS,
            build=_overseas_table_rows,
            description=_overseas_table_text,
            guide=TABLE_GUIDE,
            key="overseas-stock-rank",
            place=TABLE_PLACE_GRID,
            height=CARD_HEIGHT,
            group=OVERSEAS_GROUP,
        ),
        # 해외주식 표 아래에 둘이 나란히 놓인다. 짝이 되는 차트가 없어
        # 표끼리 한 줄을 이룬다(→ registry.grid_order). 조작 안내는 헤더 안
        # 컨트롤에 자리를 내준다(→ layout._table_header_right).
        Table(
            title="ETF 거래 상위 종목",
            columns=ETF_TABLE_COLUMNS,
            build=_etf_table_rows,
            description=_etf_table_text,
            guide=TABLE_GUIDE,
            key="etf-rank",
            place=TABLE_PLACE_GRID,
            height=CARD_HEIGHT,
            group=ETF_GROUP,
        ),
        Table(
            title="펀드 거래 상위 종목",
            columns=FUND_TABLE_COLUMNS,
            build=_fund_table_rows,
            description=_fund_table_text,
            guide=TABLE_GUIDE,
            key="fund-rank",
            place=TABLE_PLACE_GRID,
            height=CARD_HEIGHT,
            group=FUND_GROUP,
        ),
        # 맨 아래에서 화면 폭을 다 쓴다. 연금 구분 셋이 가로로 늘어서
        # 컬럼이 열여섯이라 그리드 한 칸에는 들어가지 않는다. 컬럼 이름은
        # 고른 상품에 따라 달라진다(→ pension_columns).
        Table(
            title="연금 상품 거래 상위 종목",
            columns=pension_columns,
            build=_pension_table_rows,
            description=_pension_table_text,
            guide=TABLE_GUIDE,
            key="pension-rank",
            group=PENSION_GROUP,
        ),
    ),
    charts=(
        Chart(
            key="stock-map",
            title="국내주식 순매수 현황(거래상위종목)",
            build=_treemap,
            description=_chart_text,
            note=CHART_NOTE,
            # 국내주식 줄의 구분 선택을 그대로 따른다.
            follows_tab=True,
            height=CARD_HEIGHT,
        ),
        Chart(
            key="overseas-stock-map",
            title="미국주식 순매수 현황(거래상위종목)",
            build=_overseas_treemap,
            description=_overseas_chart_text,
            note=CHART_NOTE,
            # 해외주식 줄의 구분 선택을 따른다.
            follows_tab=True,
            height=CARD_HEIGHT,
            group=OVERSEAS_GROUP,
        ),
    ),
)

__all__ = [
    "ETF_TABLE_COLUMNS",
    "FUND_TABLE_COLUMNS",
    "OVERSEAS_TABLE_COLUMNS",
    "PENSION_FIELDS",
    "TAB",
    "TABLE_COLUMNS",
    "metrics",
    "pension_columns",
    "pension_field",
]
