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

윗줄이 국내주식(상품_국내주식1·2), 아랫줄이 해외주식(상품_해외주식1·2)이다.
표와 트리맵을 번갈아 선언하면 그리드가 짝마다 한 줄로 놓는다
(→ registry.grid_order).

해외주식은 두 가지가 다르다. 순위표에 시가총액이 없어 표 컬럼이 하나 적고,
트리맵의 시가총액은 달러라 표기 함수가 다르다(→ figures.OVERSEAS_HOVER).
"""

from __future__ import annotations

from dashboard import format as fmt
from dashboard.data import TOTAL_LABEL, DashboardData
from dashboard.grid import (
    COUNT_FORMAT,
    MONEY_FORMAT,
    NUMBER_FORMAT,
    RANK_CHANGE_FORMAT,
    SIGNED_NUMBER_FORMAT,
    Column,
)
from dashboard.tabs.product import figures as product_figures
from dashboard.tabs.product import metrics
from dashboard.tabs.registry import (
    TABLE_PLACE_GRID,
    Chart,
    Select,
    Tab,
    Table,
)

# 표의 조작 안내. 켜 둔 기능만 적는다(→ grid.DEFAULT_COL_DEF).
TABLE_GUIDE = "헤더 클릭 정렬 · 경계 드래그로 너비 조절 · 행 클릭 강조"

# 트리맵 읽는 법. 칸 크기와 색이 원래 값에 비례하지 않으므로 그림만 보고
# 크기를 가늠하지 않도록 함께 적는다(→ metrics.area_values).
CHART_NOTE = "칸 크기 시가총액(제곱근) · 색 순매수금액(로그)"

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

# 선택 컨트롤 키. 콜백과 정적 HTML이 같은 이름을 쓴다. 줄마다 키가 달라야
# 두 줄이 서로의 값을 덮지 않는다.
SELECT_BRANCH = "branch"
SELECT_OVERSEAS_BRANCH = "overseas-branch"

# 해외주식 줄의 이름. 이 이름을 가진 표·차트 위에 선택 줄이 하나 더 생기고
# 그 두 카드만 움직인다(→ registry.Tab.select_groups).
OVERSEAS_GROUP = "overseas"

# 선택 컨트롤에 붙는 이름. 고르는 값에 지점과 '전체'가 함께 들어 있어
# '지점'이라고 적으면 '전체'가 그 이름에 들어맞지 않는다.
SELECT_LABEL = "구분"

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

# 두 순위표가 함께 쓰는 컬럼. 해외주식 원본에는 시가총액이 없어 그 컬럼만
# 빠지고 나머지는 같다(→ dashboard/sources/overseas_stock1.py).
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
# 금액은 파이썬이 문구까지 만들어 담는다(→ grid.MONEY_FORMAT).
# 시가총액만 억원 단위라 다른 두 컬럼과 표기 함수가 다르다.
_MARKET_CAP_COLUMN = Column(
    field="market_cap",
    header="시가총액",
    min_width=130,
    to_text=fmt.format_assets,
    js_format=MONEY_FORMAT,
    flex=2,
)
_CUSTOMER_COLUMN = Column(
    field="trade_customer_count",
    header="거래고객수",
    min_width=120,
    to_text=fmt.format_count,
    js_format=COUNT_FORMAT,
)
_TRADE_VALUE_COLUMN = Column(
    field="trade_value",
    header="거래대금",
    min_width=130,
    to_text=fmt.format_revenue,
    js_format=MONEY_FORMAT,
    flex=2,
)
# 순매수는 순매도인 종목에서 음수가 된다. 부호를 함께 적고 증감 색을
# 입힌다. 색만으로 구분하지 않도록 부호가 늘 함께 나온다.
_NET_BUY_COLUMN = Column(
    field="net_buy_amount",
    header="순매수금액",
    min_width=140,
    to_text=fmt.format_revenue_delta,
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
    _MARKET_CAP_COLUMN,
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


# --- 선택 목록 ---------------------------------------------------------------
def _branch_names(data: DashboardData) -> list[str]:
    """구분 선택 목록. 지점들과 '전체'가 함께 들어간다.

    네 원본이 같은 지점을 담고 있어야 표와 트리맵이 같은 값을 보여줄 수
    있다. 국내주식 순위 원본을 기준으로 삼고, 그것이 없으면 다음 원본에서
    차례로 읽는다. 어느 원본이 빠져도 나머지로 목록을 만들 수 있어야 그
    카드만 안내 상태로 남고 나머지 화면이 열린다.
    """
    for stock, total in (
        (data.domestic_stock_rank, data.domestic_stock_rank_total),
        (data.domestic_stock_cap, data.domestic_stock_cap_total),
        (data.overseas_stock_rank, data.overseas_stock_rank_total),
        (data.overseas_stock_cap, data.overseas_stock_cap_total),
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
    ),
    charts=(
        Chart(
            key="stock-map",
            title="국내주식 거래 상위 100 종목",
            build=_treemap,
            description=_chart_text,
            note=CHART_NOTE,
            # 국내주식 줄의 구분 선택을 그대로 따른다.
            follows_tab=True,
            height=CARD_HEIGHT,
        ),
        Chart(
            key="overseas-stock-map",
            title="미국주식 거래 상위 100 종목",
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
    "OVERSEAS_TABLE_COLUMNS",
    "TAB",
    "TABLE_COLUMNS",
    "metrics",
]
