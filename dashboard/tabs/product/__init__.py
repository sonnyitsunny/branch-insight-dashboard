"""상품 탭 선언.

무엇을 보여줄지 여기에 한 번만 적는다. Dash 화면과 정적 HTML이 이 선언을
함께 읽는다(→ dashboard/tabs/registry.py).

탭 맨 위의 지점 선택은 이 탭 전체에 걸린다. 왼쪽 표와 오른쪽 트리맵이
같은 값을 받아 같은 지점을 보여준다. 컨트롤을 카드마다 따로 두면 두 값이
어긋나 한 화면에서 서로 다른 지점을 보게 된다.

**원본이 둘이다.** 왼쪽 표는 지점별 거래 상위 종목(상품_국내주식1),
오른쪽 트리맵은 시가총액 상위 종목의 지점별 거래(상품_국내주식2)를 쓴다.
행을 고르는 기준이 달라 두 카드의 종목 목록은 같지 않다.
"""

from __future__ import annotations

from dashboard import format as fmt
from dashboard.data import TOTAL_LABEL, DashboardData
from dashboard.grid import (
    COUNT_FORMAT,
    MONEY_FORMAT,
    NUMBER_FORMAT,
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

# 선택 컨트롤 키. 콜백과 정적 HTML이 같은 이름을 쓴다.
SELECT_BRANCH = "branch"

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

TABLE_COLUMNS = (
    Column(
        field="stock_rank",
        header="순위",
        min_width=RANK_COLUMN_WIDTH,
        to_text=fmt.format_number,
        js_format=NUMBER_FORMAT,
        width=RANK_COLUMN_WIDTH,
        flex=0,
    ),
    Column(
        field="stock_name",
        header="종목명",
        min_width=130,
        to_text=str,
        flex=2,
    ),
    Column(
        field="sector",
        header="업종",
        min_width=110,
        to_text=str,
        flex=2,
    ),
    # 금액은 파이썬이 문구까지 만들어 담는다(→ grid.MONEY_FORMAT).
    # 시가총액만 억원 단위라 다른 두 컬럼과 표기 함수가 다르다.
    Column(
        field="market_cap",
        header="시가총액",
        min_width=130,
        to_text=fmt.format_assets,
        js_format=MONEY_FORMAT,
        flex=2,
    ),
    Column(
        field="trade_customer_count",
        header="거래고객수",
        min_width=120,
        to_text=fmt.format_count,
        js_format=COUNT_FORMAT,
    ),
    Column(
        field="trade_value",
        header="거래대금",
        min_width=130,
        to_text=fmt.format_revenue,
        js_format=MONEY_FORMAT,
        flex=2,
    ),
    # 순매수는 순매도인 종목에서 음수가 된다. 부호를 함께 적고 증감 색을
    # 입힌다. 색만으로 구분하지 않도록 부호가 늘 함께 나온다.
    Column(
        field="net_buy_amount",
        header="순매수금액",
        min_width=140,
        to_text=fmt.format_revenue_delta,
        js_format=MONEY_FORMAT,
        growth=True,
        flex=2,
    ),
    Column(
        field="rank_change",
        header="순위변동",
        min_width=CHANGE_COLUMN_WIDTH,
        to_text=fmt.format_signed_number,
        js_format=SIGNED_NUMBER_FORMAT,
        width=CHANGE_COLUMN_WIDTH,
        growth=True,
        flex=0,
    ),
)


# --- 선택 목록 ---------------------------------------------------------------
def _branch_names(data: DashboardData) -> list[str]:
    """지점 선택 목록.

    두 원본이 같은 지점을 담고 있어야 표와 트리맵이 같은 지점을 보여줄 수
    있다. 순위 원본을 기준으로 삼고, 그것이 없으면 종목 원본에서 읽는다.
    """
    names = metrics.scope_names(
        data.domestic_stock_rank,
        data.domestic_stock_rank_total,
        TOTAL_LABEL,
    )
    if names:
        return names
    return metrics.scope_names(
        data.domestic_stock_cap,
        data.domestic_stock_cap_total,
        TOTAL_LABEL,
    )


def _default_branch(data: DashboardData) -> str:
    names = _branch_names(data)
    if TOTAL_LABEL in names:
        return TOTAL_LABEL
    return names[0] if names else ""


def _chosen_branch(data: DashboardData, selection: dict) -> str:
    """고른 지점. 선택이 비어 있으면 첫 화면의 기본값을 쓴다."""
    return selection.get(SELECT_BRANCH) or _default_branch(data)


# --- 표 만들기 ---------------------------------------------------------------
def _table_rows(data: DashboardData, selection: dict):
    """고른 지점의 상위 종목 행.

    합계 행은 두지 않는다. 순위표의 값은 종목마다 다른 것이라 세로로 더할
    수 있는 값이 아니다.
    """
    rows = metrics.branch_rows(
        data.domestic_stock_rank,
        data.domestic_stock_rank_total,
        _chosen_branch(data, selection),
        TOTAL_LABEL,
    )
    return None, rows


def _table_text(data: DashboardData) -> str:
    if (
        data.domestic_stock_rank.empty
        and data.domestic_stock_rank_total.empty
    ):
        return TABLE_EMPTY_NOTE
    return ""


# --- 트리맵 만들기 -----------------------------------------------------------
def _treemap(data: DashboardData, selection: dict):
    """고른 지점의 시가총액 상위 종목 트리맵.

    면적 기준이 되는 가장 작은 시가총액은 지점이 아니라 전체 종목에서
    구한다. 지점마다 다시 구하면 같은 종목의 칸 크기가 지점을 바꿀 때마다
    달라진다(→ metrics.area_floor).
    """
    rows = metrics.branch_rows(
        data.domestic_stock_cap,
        data.domestic_stock_cap_total,
        _chosen_branch(data, selection),
        TOTAL_LABEL,
    )
    floor = metrics.area_floor(
        data.domestic_stock_cap
        if not data.domestic_stock_cap.empty
        else data.domestic_stock_cap_total
    )
    return product_figures.treemap_figure(metrics.treemap_rows(rows, floor))


def _chart_text(data: DashboardData) -> str:
    if data.domestic_stock_cap.empty and data.domestic_stock_cap_total.empty:
        return CHART_EMPTY_NOTE
    return ""


def _context(data: DashboardData) -> dict:
    return {"branch_names": _branch_names(data)}


TAB = Tab(
    value="product",
    label="상품",
    build_context=_context,
    selects=(
        Select(
            key=SELECT_BRANCH,
            label="지점",
            options=_branch_names,
            default=_default_branch,
        ),
    ),
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
    ),
    charts=(
        Chart(
            key="stock-map",
            title="국내주식 시가총액 상위 종목",
            build=_treemap,
            description=_chart_text,
            note=CHART_NOTE,
            # 탭 맨 위의 지점 선택을 그대로 따른다.
            follows_tab=True,
            height=CARD_HEIGHT,
        ),
    ),
)

__all__ = ["TAB", "TABLE_COLUMNS", "metrics"]
