"""상품 탭 검증.

한 줄이 왼쪽 표(거래 상위 종목)와 오른쪽 트리맵(시가총액 상위 종목)으로
이루어진다. 윗줄이 국내주식(상품_국내주식1·2), 다음 줄이 해외주식
(상품_해외주식1·2)이며, 셋째 줄은 트리맵 없이 ETF(상품_ETF2)와
펀드(상품_펀드1) 표가 나란히 선다. 줄마다 구분 선택이 하나씩이다.

트리맵의 두 변환도 여기서 본다. 시가총액은 면적, 순매수금액은 색이 되는데
둘 다 편차가 커서 로그로 바꾼다. 순매수금액은 음수가 될 수 있어 절댓값에
로그를 씌우고 부호를 되붙인다.
"""

from __future__ import annotations

import re

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import pytest

from dashboard import callbacks, grid, layout
from dashboard.data import (
    PENSION_RANK_PRODUCT_TYPES,
    PENSION_TYPES,
    TOTAL_LABEL,
    load_dashboard_data,
)
from dashboard.tabs import product
from dashboard.tabs.product import figures as product_figures
from dashboard.tabs.product import metrics
from dashboard.tabs.registry import GRID_CHART, GRID_TABLE, grid_order
from fixture_data import (
    OVERSEAS_STOCK_CAP_COUNT,
    STOCK_CAP_COUNT,
    STOCK_RANK_COUNT,
)

TAB = product.TAB
TABLE = TAB.tables[0]
CHART = TAB.charts[0]
OVERSEAS_TABLE = TAB.tables[1]
OVERSEAS_CHART = TAB.charts[1]
ETF_TABLE = TAB.tables[2]
FUND_TABLE = TAB.tables[3]
PENSION_TABLE = TAB.tables[4]


@pytest.fixture(scope="module")
def dataset():
    return load_dashboard_data()


def _selection(branch_name: str, product_type: str = "") -> dict:
    """모든 줄이 같은 구분을 고른 상태.

    줄마다 선택 키가 다르므로 모두 담는다(→ product.SELECT_ETF_BRANCH).
    연금 줄만 상품도 함께 고른다.
    """
    return {
        product.SELECT_BRANCH: branch_name,
        product.SELECT_OVERSEAS_BRANCH: branch_name,
        product.SELECT_ETF_BRANCH: branch_name,
        product.SELECT_FUND_BRANCH: branch_name,
        product.SELECT_PENSION_BRANCH: branch_name,
        product.SELECT_PENSION_PRODUCT: (
            product_type or PENSION_RANK_PRODUCT_TYPES[0]
        ),
    }


# --- 선언 --------------------------------------------------------------------
def test_each_row_has_one_select_of_its_own():
    """구분 컨트롤은 줄마다 하나씩이고 그 줄의 두 카드가 따른다.

    카드마다 컨트롤을 두면 값이 어긋나 한 줄에서 표와 트리맵이 서로 다른
    지점을 보여주게 된다. 반대로 탭에 하나만 두면 국내와 해외를 따로 볼 수
    없다(→ registry.Tab.select_groups).
    """
    groups = TAB.select_groups
    assert [group.name for group in groups] == [
        "",
        product.OVERSEAS_GROUP,
        product.ETF_GROUP,
        product.FUND_GROUP,
        product.PENSION_GROUP,
    ]
    assert [
        [select.key for select in group.selects] for group in groups
    ] == [
        [product.SELECT_BRANCH],
        [product.SELECT_OVERSEAS_BRANCH],
        [product.SELECT_ETF_BRANCH],
        [product.SELECT_FUND_BRANCH],
        # 연금 줄만 지점과 상품 둘을 고른다.
        [product.SELECT_PENSION_BRANCH, product.SELECT_PENSION_PRODUCT],
    ]
    for group in groups:
        assert group.tables
        assert group.followers == group.charts
    for chart in TAB.charts:
        assert chart.follows_tab
        assert chart.selects == ()


def test_each_row_keeps_its_own_selection():
    """두 줄이 서로 따로 움직인다. 한쪽을 바꿔도 다른 줄은 그대로다."""
    groups = {group.name: group for group in TAB.select_groups}
    assert groups[""].key == TAB.value
    for name in (
        product.OVERSEAS_GROUP,
        product.ETF_GROUP,
        product.FUND_GROUP,
        product.PENSION_GROUP,
    ):
        assert groups[name].key == f"{TAB.value}-{name}"
    # 선택 키가 모두 달라 한 줄의 값이 다른 줄을 덮지 않는다.
    keys = {
        product.SELECT_BRANCH,
        product.SELECT_OVERSEAS_BRANCH,
        product.SELECT_ETF_BRANCH,
        product.SELECT_FUND_BRANCH,
        product.SELECT_PENSION_BRANCH,
        product.SELECT_PENSION_PRODUCT,
    }
    assert len(keys) == 6


def test_select_is_labelled_by_what_it_holds():
    """고르는 값에 '전체'가 함께 들어 있어 '지점'이 아니라 '구분'이다.

    상품 라디오만 이름을 붙이지 않는다. 고른 값이 늘 보이기 때문이다.
    """
    branch_selects = [
        select
        for select in TAB.selects
        if select.key != product.SELECT_PENSION_PRODUCT
    ]
    assert {select.label for select in branch_selects} == {
        product.SELECT_LABEL
    }
    assert product.SELECT_LABEL == "구분"


def test_tables_sit_in_the_grid():
    """표는 화면 폭 전체가 아니라 그리드 칸에 놓인다.

    ETF·펀드 표는 짝이 되는 차트가 없어 둘이 나란히 한 줄을 이룬다.
    연금 표만 컬럼이 열여섯이라 화면 폭을 다 쓴다.
    """
    assert TAB.grid_tables == (
        TABLE,
        OVERSEAS_TABLE,
        ETF_TABLE,
        FUND_TABLE,
    )
    assert TAB.full_tables == (PENSION_TABLE,)


def test_etf_and_fund_selects_sit_inside_the_table_cards():
    """ETF·펀드 줄은 컨트롤을 카드 위 줄이 아니라 표 헤더 안에 둔다.

    카드가 표 하나뿐이라 줄을 따로 만들면 그 줄이 카드 하나만 이고 선다
    (→ registry.PLACE_TABLE).
    """
    groups = {g.name: g for g in TAB.select_groups}
    for name, keys in (
        (product.ETF_GROUP, [product.SELECT_ETF_BRANCH]),
        (product.FUND_GROUP, [product.SELECT_FUND_BRANCH]),
        (
            product.PENSION_GROUP,
            [
                product.SELECT_PENSION_BRANCH,
                product.SELECT_PENSION_PRODUCT,
            ],
        ),
    ):
        group = groups[name]
        assert group.row_selects == ()
        assert [select.key for select in group.table_selects] == keys
    # 다른 줄은 카드 위 한 줄에 그대로 둔다.
    for name in ("", product.OVERSEAS_GROUP):
        other = groups[name]
        assert other.table_selects == ()
        assert other.row_selects


def test_etf_and_fund_share_one_grid_row():
    """컨트롤을 카드 안에 넣은 줄들이 한 그리드에 놓인다.

    줄마다 그리드를 열면 표 하나짜리 그리드가 여럿이 되어 위아래로 쌓인다
    (→ registry.Tab.grid_rows). 연금 표는 그 그리드에 들지 않고 화면 폭을
    다 쓰므로 아래에 따로 놓인다.
    """
    rows = TAB.grid_rows
    assert [[group.name for group in row] for row in rows] == [
        [""],
        [product.OVERSEAS_GROUP],
        [product.ETF_GROUP, product.FUND_GROUP, product.PENSION_GROUP],
    ]


def test_each_row_pairs_a_table_with_a_chart():
    """그리드가 표와 차트를 번갈아 놓아 짝마다 한 줄이 된다.

    표를 모두 앞에 몰면 표끼리 한 줄, 트리맵끼리 다음 줄이 되어 국내주식
    표 옆에 해외주식 표가 선다(→ registry.grid_order).
    """
    drawn = []
    for group in TAB.select_groups:
        drawn.extend(grid_order(list(group.grid_tables), group.charts))
    assert [kind for kind, _item in drawn] == [
        GRID_TABLE,
        GRID_CHART,
        GRID_TABLE,
        GRID_CHART,
        # ETF·펀드 줄은 표뿐이라 둘이 짝을 이룬다.
        GRID_TABLE,
        GRID_TABLE,
    ]
    assert [item for _kind, item in drawn] == [
        TABLE,
        CHART,
        OVERSEAS_TABLE,
        OVERSEAS_CHART,
        ETF_TABLE,
        FUND_TABLE,
    ]


def test_overseas_table_columns_match_the_source():
    """해외주식 표 컬럼은 일곱 개다.

    원본에 업종이 있어 ETF·펀드 표보다 컬럼이 하나 많다
    (→ dashboard/sources/overseas_stock1.py).
    """
    fields = [column.field for column in product.OVERSEAS_TABLE_COLUMNS]
    assert fields == [
        "stock_rank",
        "stock_name",
        "sector",
        "trade_customer_count",
        "trade_value",
        "net_buy_amount",
        "rank_change",
    ]
    assert "market_cap" not in fields


def test_table_columns_match_the_source():
    """표 컬럼은 일곱 개다. 시가총액은 표에 두지 않는다."""
    fields = [column.field for column in product.TABLE_COLUMNS]
    assert fields == [
        "stock_rank",
        "stock_name",
        "sector",
        "trade_customer_count",
        "trade_value",
        "net_buy_amount",
        "rank_change",
    ]


def test_no_rank_table_shows_the_market_cap():
    """시가총액은 어느 순위표에도 없다.

    지점이 무엇을 얼마나 사고팔았는지 보는 표라 시장이 정하는 값은 자리만
    차지한다. 트리맵은 그 값을 칸 크기로 계속 쓴다(→ metrics.area_values).
    """
    tables = (
        product.TABLE_COLUMNS,
        product.OVERSEAS_TABLE_COLUMNS,
        product.ETF_TABLE_COLUMNS,
        product.FUND_TABLE_COLUMNS,
    )
    for columns in tables:
        fields = [column.field for column in columns]
        assert "market_cap" not in fields
        assert "market_cap_usd" not in fields


def test_branch_options_start_with_total(dataset):
    options = TAB.option_map(dataset)[product.SELECT_BRANCH]
    assert options[0] == TOTAL_LABEL
    assert len(options) == len(dataset.branch_names) + 1
    assert TAB.defaults(dataset)[product.SELECT_BRANCH] == TOTAL_LABEL


# --- 표 ----------------------------------------------------------------------
def test_table_shows_the_chosen_branch(dataset):
    """고른 지점의 순위표만 나온다."""
    branch_name = dataset.branch_names[0]
    _total, rows = TABLE.build(dataset, _selection(branch_name))
    assert set(rows["branch_name"]) == {branch_name}
    assert len(rows) == STOCK_RANK_COUNT
    assert rows["stock_rank"].tolist() == sorted(rows["stock_rank"])


def test_table_total_uses_the_source_row(dataset):
    """'전체'는 지점 행을 더해 만들지 않고 원본의 '전체' 행을 그대로 쓴다."""
    _total, rows = TABLE.build(dataset, _selection(TOTAL_LABEL))
    assert set(rows["branch_name"]) == {TOTAL_LABEL}
    assert len(rows) == STOCK_RANK_COUNT


def test_table_has_no_summary_row(dataset):
    """순위표에는 합계 행을 두지 않는다. 종목마다 다른 값이라 더할 수 없다."""
    total, _rows = TABLE.build(dataset, _selection(TOTAL_LABEL))
    assert total is None


def test_money_columns_are_written_in_100m(dataset):
    """금액은 억원 숫자로 적고 단위는 컬럼 이름이 말한다.

    원본은 원 단위다. 억원으로 접는 함수를 쓰지 않으면 1억 배 어긋난다.
    """
    fields = {column.field: column for column in product.TABLE_COLUMNS}
    assert fields["trade_value"].header == "거래대금(억원)"
    assert fields["net_buy_amount"].header == "순매수금액(억원)"
    assert fields["trade_value"].to_text(165_591_510_000) == "1,655.9"
    assert fields["net_buy_amount"].to_text(13_700_708_000) == "+137.0"
    assert fields["net_buy_amount"].to_text(-7_769_180_000) == "-77.7"


def test_negative_net_buy_reaches_the_row_data(dataset):
    """순매도 종목의 음수가 표까지 그대로 간다."""
    view = callbacks.build_table_view(
        TABLE, dataset, _selection(TOTAL_LABEL), "", 0, TAB.value
    )
    amounts = [row["net_buy_amount"] for row in view["row_data"]]
    assert any(value < 0 for value in amounts)
    texts = [row["net_buy_amount__text"] for row in view["row_data"]]
    assert any(text.startswith("-") for text in texts)
    assert any(text.startswith("+") for text in texts)


def test_rank_change_keeps_zero_without_a_sign():
    """순위변동 0에는 부호를 붙이지 않는다.

    `+0`은 '조금 올랐다'로 읽히지만 실제 뜻은 '그대로'다. 화면과 정적
    HTML이 같은 규칙을 쓰는지도 함께 본다.
    """
    fields = {column.field: column for column in product.TABLE_COLUMNS}
    to_text = fields["rank_change"].to_text
    assert to_text(0) == "0"
    assert to_text(3) == "+3"
    assert to_text(-2) == "-2"
    assert 'params.value == 0 ? "0"' in grid.SIGNED_NUMBER_FORMAT


# --- 트리맵 변환 -------------------------------------------------------------
def test_area_keeps_the_order_of_market_cap():
    """면적은 시가총액 순서를 지킨다. 크기 비교가 뒤집히면 안 된다."""
    caps = pd.Series([3_000.0, 50_000.0, 5_000_000.0])
    areas = metrics.area_values(caps, floor=3_000.0)
    assert areas.is_monotonic_increasing
    # 가장 작은 종목은 기준과 같으므로 1을 받는다.
    assert areas.min() == pytest.approx(1.0)


def test_sector_area_keeps_the_order_of_market_cap():
    """시총이 큰 업종의 칸이 더 크다.

    묶음 칸의 크기는 그 안 칸들의 합이다. 종목마다 로그를 씌워 더하면
    그 합이 시가총액 합과 다른 순서를 갖는다 — 반도체 3종목(605조)이
    상사·자본재 10종목(30조)보다 작아졌다(→ metrics.area_values).
    """
    caps = pd.Series([450e12, 150e12, 5e12] + [3e12] * 10)
    areas = metrics.area_values(caps, floor=3e12)
    assert areas[:3].sum() > areas[3:].sum()


def test_area_presses_the_gap_between_big_and_small():
    """큰 종목이 화면을 덮지 않도록 자릿수 차이를 줄인다.

    시총 그대로 넣으면 1위 종목 하나가 그림을 거의 다 덮고 나머지는
    실선처럼 눌린다(→ metrics.AREA_EXPONENT).
    """
    caps = pd.Series([3_000.0, 5_000_000.0])
    areas = metrics.area_values(caps, floor=3_000.0)
    plain = caps / caps.min()
    assert areas.max() / areas.min() < plain.max() / plain.min()
    # 그래도 큰 종목이 크다는 것은 남아야 한다.
    assert areas.max() / areas.min() > 5


def test_signed_log_keeps_the_sign_and_zero():
    """부호를 지키고 0은 0으로 남는다.

    0이 0이어야 발산형 색 눈금의 가운데(중립색)에 정확히 놓인다.
    """
    values = pd.Series([-1_000_000.0, 0.0, 1_000_000.0])
    colors = metrics.signed_log(values)
    assert colors.iloc[0] < 0
    assert colors.iloc[1] == 0
    assert colors.iloc[2] > 0
    # 부호만 다른 값은 크기가 같다. 한쪽이 커지면 눈금이 치우친다.
    assert colors.iloc[0] == pytest.approx(-colors.iloc[2])


def test_signed_log_compresses_the_long_tail():
    """큰 값 하나가 색 눈금을 독차지하지 않는다."""
    values = pd.Series([1_000_000.0, 100_000_000_000.0])
    colors = metrics.signed_log(values)
    assert values.max() / values.min() > 10_000
    assert colors.max() / colors.min() < 3


def test_empty_sector_gets_a_name():
    """업종이 비면 트리맵이 묶을 이름이 없다. 화면에서만 이름을 붙인다."""
    assert metrics.sector_label("") == metrics.SECTOR_UNKNOWN
    assert metrics.sector_label(None) == metrics.SECTOR_UNKNOWN
    assert metrics.sector_label("업종 A") == "업종 A"


def test_treemap_rows_drop_values_that_cannot_be_drawn(dataset):
    """시가총액이나 순매수금액이 없는 행은 뺀다. 0으로 채우지 않는다."""
    rows = metrics.branch_rows(
        dataset.domestic_stock_cap,
        dataset.domestic_stock_cap_total,
        TOTAL_LABEL,
        TOTAL_LABEL,
    ).copy()
    rows.loc[0, "market_cap"] = np.nan
    ready = metrics.treemap_rows(rows, floor=1_000.0)
    assert len(ready) == len(rows) - 1
    assert ready["area"].notna().all()
    assert ready["color"].notna().all()


# --- 트리맵 Figure -----------------------------------------------------------
def _root_tiles(trace) -> list[int]:
    """뿌리 칸의 자리. 위 칸이 없어 `parents`가 빈 문자열이다."""
    return [i for i, parent in enumerate(trace.parents) if not parent]


def _split_tiles(trace) -> tuple[list[int], list[int]]:
    """업종 칸과 종목 칸의 자리.

    세 단계 중 가운데가 업종이다. 업종 칸의 `parents`는 뿌리 칸의 `id`,
    종목 칸의 `parents`는 그 업종 칸의 `id`다.
    """
    roots = {trace.ids[i] for i in _root_tiles(trace)}
    sectors = [i for i, parent in enumerate(trace.parents) if parent in roots]
    stock_parents = {trace.ids[i] for i in sectors}
    stocks = [
        i
        for i, parent in enumerate(trace.parents)
        if parent in stock_parents
    ]
    return sectors, stocks


def test_treemap_groups_stocks_under_sectors(dataset):
    """종목이 업종 아래에 묶인다."""
    figure = CHART.build(dataset, _selection(TOTAL_LABEL))
    assert isinstance(figure, go.Figure)
    trace = figure.data[0]
    sectors, stocks = _split_tiles(trace)
    assert len(stocks) == STOCK_CAP_COUNT
    assert sectors
    # 종목의 부모는 모두 업종 칸이다. px는 `parents`에 이름이 아니라
    # 경로로 만든 `id`를 넣는다.
    assert {trace.parents[i] for i in stocks} <= {
        trace.ids[i] for i in sectors
    }


def test_treemap_color_scale_is_centred_on_zero(dataset):
    """색 눈금의 가운데가 0이고 양끝이 같은 거리다.

    px는 색 설정을 trace가 아니라 `layout.coloraxis`에 둔다.
    """
    coloraxis = CHART.build(dataset, _selection(TOTAL_LABEL)).layout.coloraxis
    assert coloraxis.cmid == 0
    assert coloraxis.cmin == pytest.approx(-coloraxis.cmax)


def test_treemap_colors_buy_and_sell_apart(dataset):
    """순매수는 붉은 계열 끝, 순매도는 푸른 계열 끝으로 간다."""
    from dashboard import figures as shared

    figure = CHART.build(dataset, _selection(TOTAL_LABEL))
    scale = figure.layout.coloraxis.colorscale
    assert scale[0][1].upper() == shared.COLOR_NET_SELL
    assert scale[-1][1].upper() == shared.COLOR_NET_BUY
    colors = [
        value for value in figure.data[0].marker.colors if value is not None
    ]
    assert min(colors) < 0 < max(colors)


def test_treemap_sector_colour_comes_from_the_summed_amount(dataset):
    """업종 칸 색은 그 업종 순매수의 합에서 나온다.

    px에 맡기면 로그로 바꾼 자식 색을 면적으로 가중 평균한다. 로그가
    자릿수 차이를 줄여 놓아 매수와 매도가 평균에서 서로 지워지고,
    순매도 업종이 매수색으로 그려진다(→ product.figures._sector_colors).
    """
    trace = CHART.build(dataset, _selection(TOTAL_LABEL)).data[0]
    rows = metrics.treemap_rows(
        metrics.branch_rows(
            dataset.domestic_stock_cap,
            dataset.domestic_stock_cap_total,
            TOTAL_LABEL,
            TOTAL_LABEL,
        ),
        metrics.area_floor(dataset.domestic_stock_cap),
    )
    totals = rows.groupby("sector_label")["net_buy_amount"].sum()
    sectors, _ = _split_tiles(trace)
    colors = {trace.labels[i]: trace.marker.colors[i] for i in sectors}
    assert set(colors) == set(totals.index)
    for label, total in totals.items():
        assert np.sign(colors[label]) == np.sign(total)


def test_treemap_sector_hover_keeps_no_placeholder(dataset):
    """업종 칸에는 px가 자식에서 만들어 넣은 값이 남지 않는다.

    자식이 여럿이면 `(?)`, 하나면 그 자식 값이 그대로 들어간다. 둘 다
    업종 칸의 값이 아니므로 `-`로 비운다.
    """
    from dashboard import format as fmt

    trace = CHART.build(dataset, _selection(TOTAL_LABEL)).data[0]
    sectors, _ = _split_tiles(trace)
    assert sectors
    for index in sectors:
        cells = list(trace.customdata[index])
        assert cells == [fmt.EMPTY_TEXT] * 5


def test_treemap_root_hover_shows_dashes(dataset):
    """뿌리 칸 hover에 서식 원문이 아니라 `-`가 뜬다.

    `path`에 업종·종목만 주면 px가 이름 없는 뿌리를 만든다. 데이터에 없는
    칸이라 `customdata`를 받지 못해, 그 위에서 hover가 `%{label}`이나
    `%{customdata[0]}` 같은 서식 원문을 그대로 띄운다. 뿌리를 데이터에
    있는 칸으로 두고 네 값을 비워야 `-`로 나온다
    (→ product.figures.ROOT_LABEL).
    """
    from dashboard import format as fmt

    trace = CHART.build(dataset, _selection(TOTAL_LABEL)).data[0]
    roots = _root_tiles(trace)
    assert len(roots) == 1
    index = roots[0]
    assert trace.labels[index] == product_figures.ROOT_LABEL
    assert list(trace.customdata[index]) == [fmt.EMPTY_TEXT] * 5


def test_treemap_writes_only_the_name_in_the_tile(dataset):
    """칸 안에는 이름만 왼쪽 위에 적는다. 네 값은 hover로 읽는다.

    이름과 금액을 함께 넣으면 두 줄이 되고, Plotly가 칸에 맞추느라 글씨를
    더 세게 줄여 이름까지 읽을 수 없게 된다. 글씨를 가운데 두면 업종 이름이
    종목 칸에 덮여 보이지 않는다(→ product.figures.TILE_TEXT_POSITION).
    """
    trace = CHART.build(dataset, _selection(TOTAL_LABEL)).data[0]
    assert trace.texttemplate == "%{label}"
    assert trace.textposition == "top left"
    for line in ("시가총액", "거래고객수", "거래대금", "순매수금액"):
        assert line in trace.hovertemplate


def test_treemap_fits_the_name_to_each_tile(dataset):
    """칸마다 글씨 크기를 따로 맞춘다.

    `uniformtext`를 켜면 모든 칸이 가장 작은 칸의 크기로 통일되고, 그
    크기로도 안 맞는 칸은 이름이 통째로 사라진다. 빼 두어야 큰 칸은
    `TILE_FONT_SIZE`로, 작은 칸은 그 칸에 맞게 줄어든 크기로 그려진다
    (→ product.figures.treemap_figure).
    """
    figure = CHART.build(dataset, _selection(TOTAL_LABEL))
    assert not figure.layout.uniformtext.mode
    assert figure.data[0].textfont.size == product_figures.TILE_FONT_SIZE


def test_treemap_tile_size_is_stable_across_branches(dataset):
    """같은 종목의 칸 크기는 지점을 바꿔도 그대로다.

    지점마다 기준을 다시 잡으면 같은 종목이 지점에 따라 다른 크기로
    보인다(→ metrics.area_floor).
    """
    sizes = {}
    for branch_name in (TOTAL_LABEL, dataset.branch_names[0]):
        trace = CHART.build(dataset, _selection(branch_name)).data[0]
        _, stocks = _split_tiles(trace)
        for index in stocks:
            sizes.setdefault(trace.ids[index], set()).add(
                round(float(trace.values[index]), 6)
            )
    assert sizes
    assert all(len(values) == 1 for values in sizes.values())


def test_treemap_follows_the_branch(dataset):
    """지점을 바꾸면 그림이 바뀐다."""
    branch_name = dataset.branch_names[0]
    total = CHART.build(dataset, _selection(TOTAL_LABEL)).data[0]
    branch = CHART.build(dataset, _selection(branch_name)).data[0]
    assert len(branch.ids) <= len(total.ids)
    assert list(branch.values) != list(total.values)


def test_treemap_handles_an_empty_frame(dataset):
    """원본이 없어도 화면이 깨지지 않고 안내만 나온다."""
    from dashboard.data import DashboardData

    empty = DashboardData(
        monthly=dataset.monthly,
        age=dataset.age,
        investment=dataset.investment,
        summary=dataset.summary,
    )
    figure = CHART.build(empty, _selection(TOTAL_LABEL))
    assert isinstance(figure, go.Figure)
    assert not figure.data


# --- 화면과 정적 HTML --------------------------------------------------------
def test_dash_table_uses_the_chart_height():
    """차트와 나란히 놓는 표는 그래프와 같은 높이를 쓴다."""
    assert layout.table_style(False, True)["height"] == layout.CHART_HEIGHT
    assert layout.table_style(False, False)["height"] == layout.TABLE_HEIGHT
    assert "card--table-grid" in layout.table_card_class(True)
    assert "card--table-grid" not in layout.table_card_class(False)


def test_both_cards_declare_the_same_height():
    """표와 트리맵이 같은 높이를 쓴다.

    한 줄에 나란히 서므로 한쪽만 높이면 아랫선이 어긋난다. 선언이 적은
    높이는 자리에 따른 기본값보다 앞선다(→ layout.table_style).
    """
    assert TABLE.height == product.CARD_HEIGHT
    assert CHART.height == product.CARD_HEIGHT
    assert layout.table_style(False, True, TABLE.height)["height"] == (
        product.CARD_HEIGHT
    )
    # `auto_height`를 켠 표에는 뜻이 없다.
    assert "height" not in layout.table_style(True, True, TABLE.height)


def test_dash_table_view_carries_the_declared_height(dataset):
    """콜백이 만든 표 값에 선언한 높이가 실려 화면까지 간다.

    그리드에 나란히 서는 네 표만 높이를 적는다. 화면 폭을 다 쓰는 연금
    표는 옆에 맞출 카드가 없어 자리에 따른 기본값을 쓴다.
    """
    views = callbacks.build_table_views(
        TAB, dataset, _selection(TOTAL_LABEL)
    )
    assert [view["height"] for view in views] == [
        *[product.CARD_HEIGHT] * len(TAB.grid_tables),
        "",
    ]


@pytest.fixture(scope="module")
def panel(dataset) -> str:
    """정적 HTML의 상품 탭 부분."""
    import export_html

    document = export_html.build_html(dataset)
    rest = document[document.find('data-panel="product"'):]
    end = rest.find('data-panel="', 1)
    return rest if end == -1 else rest[:end]


def test_static_html_puts_the_table_beside_the_chart(panel):
    """표가 차트 그리드 안에, 차트보다 앞에 놓인다."""
    grid_start = panel.find('<section class="chart-grid">')
    table_start = panel.find("card--table-grid")
    chart_start = panel.find(CHART.chart_id(TAB.value))
    assert -1 < grid_start < table_start < chart_start


def test_static_html_uses_the_declared_height(panel):
    """정적 HTML도 화면과 같은 높이를 쓴다.

    숫자를 내보내기 쪽에 다시 적지 않고 선언에서 받는다. 그러지 않으면
    화면 높이를 고쳤을 때 두 산출물이 갈라진다(→ AGENTS.md §14).
    """
    assert f'style="max-height:{product.CARD_HEIGHT}"' in panel
    assert f"height:{product.CARD_HEIGHT}" in panel


def test_static_html_carries_a_figure_for_every_branch(dataset):
    """서버가 없으므로 지점마다 그림을 미리 담아 둔다.

    표만 갈아 끼우고 그림을 두면 한 화면에서 둘이 다른 지점을 가리킨다.
    """
    import export_html

    variants = export_html._figure_variants(dataset)
    tables = export_html._tab_tables(dataset)
    options = TAB.option_map(dataset)[product.SELECT_BRANCH]
    for group in TAB.select_groups:
        chart_ids = [
            chart.chart_id(TAB.value) for chart in group.charts
        ]
        for chart_id in chart_ids:
            # 줄마다 자기 선택 목록만큼 담는다. 두 줄을 곱하지 않는다.
            assert set(variants[chart_id]) == set(options)
            assert chart_id in export_html._chart_configs()
        # 브라우저가 그 줄의 표와 함께 이 차트를 갈아 끼운다.
        assert tables[group.key]["charts"] == chart_ids


def test_static_html_shows_only_the_chosen_branch(panel, dataset):
    """지금 고른 지점의 행만 보이고 나머지는 숨어 있다."""
    rows = re.findall(r"<tr [^>]*data-scope=\"([^\"]+)\"([^>]*)>", panel)
    assert rows
    shown = [scope for scope, rest in rows if "hidden" not in rest]
    # 연금 줄은 지점과 상품 둘을 고르므로 조합 키가 둘로 이어져 있다.
    first = f"{TOTAL_LABEL}|{PENSION_RANK_PRODUCT_TYPES[0]}"
    assert set(shown) == {TOTAL_LABEL, first}
    # 표마다 '전체'의 순위 20개가 한 번씩 나온다.
    assert len(shown) == STOCK_RANK_COUNT * len(TAB.tables)


# --- 해외주식 표 -------------------------------------------------------------
def test_overseas_table_shows_the_chosen_branch(dataset):
    """고른 구분의 해외주식 순위표만 나온다."""
    branch_name = dataset.branch_names[0]
    _total, rows = OVERSEAS_TABLE.build(dataset, _selection(branch_name))
    assert set(rows["branch_name"]) == {branch_name}
    assert len(rows) == STOCK_RANK_COUNT
    assert rows["stock_rank"].tolist() == sorted(rows["stock_rank"])


def test_overseas_table_total_uses_the_source_row(dataset):
    """'전체'는 지점 행을 더해 만들지 않고 원본의 '전체' 행을 그대로 쓴다."""
    _total, rows = OVERSEAS_TABLE.build(dataset, _selection(TOTAL_LABEL))
    assert set(rows["branch_name"]) == {TOTAL_LABEL}
    assert len(rows) == STOCK_RANK_COUNT


def test_overseas_table_marks_new_entries(dataset):
    """앞 달에 없던 종목의 순위변동 자리에 NEW가 적힌다.

    빈 칸을 `-`로 두면 '값이 없다'로만 읽힌다. 이 컬럼에서 값이 없다는 것은
    새로 들어온 종목이라는 뜻이다(→ format.format_rank_change).
    """
    from dashboard import format as fmt

    view = callbacks.build_table_view(
        OVERSEAS_TABLE, dataset, _selection(TOTAL_LABEL)
    )
    blank = [
        row for row in view["row_data"] if row["rank_change"] is None
    ]
    assert blank
    # 정적 HTML 표
    assert grid.format_cell(
        OVERSEAS_TABLE.columns, "rank_change", None
    ) == fmt.NEW_ENTRY_TEXT
    # 화면(AgGrid)
    defs = {item["field"]: item for item in view["column_defs"]}
    formatter = defs["rank_change"]["valueFormatter"]["function"]
    assert fmt.NEW_ENTRY_TEXT in formatter


def test_domestic_table_keeps_the_dash_for_blanks(dataset):
    """국내주식 원본에는 빈 순위변동이 없어 표기를 바꾸지 않았다."""
    from dashboard import format as fmt

    assert grid.format_cell(
        TABLE.columns, "rank_change", None
    ) == fmt.EMPTY_TEXT


# --- 해외주식 트리맵 ---------------------------------------------------------
def test_overseas_treemap_groups_stocks_under_sectors(dataset):
    """종목이 업종 아래에 묶인다. 원리는 국내주식 트리맵과 같다."""
    figure = OVERSEAS_CHART.build(dataset, _selection(TOTAL_LABEL))
    assert isinstance(figure, go.Figure)
    sectors, stocks = _split_tiles(figure.data[0])
    assert len(stocks) == OVERSEAS_STOCK_CAP_COUNT
    assert sectors


def test_overseas_treemap_reads_the_dollar_market_cap(dataset):
    """시가총액은 달러라 USD를 붙여 적고, 원본에 없는 거래대금은 빠진다.

    원화 표기 함수를 그대로 쓰면 달러 값이 억원으로 적힌다
    (→ format.format_usd).
    """
    trace = OVERSEAS_CHART.build(dataset, _selection(TOTAL_LABEL)).data[0]
    assert "거래대금" not in trace.hovertemplate
    for line in ("시가총액", "거래고객수", "순매수금액"):
        assert line in trace.hovertemplate
    _sectors, stocks = _split_tiles(trace)
    caps = [trace.customdata[index][1] for index in stocks]
    assert all(text.startswith("USD") for text in caps)


def test_overseas_treemap_sizes_tiles_from_the_dollar_column(dataset):
    """칸 크기는 달러 시가총액에서 나온다."""
    rows = metrics.branch_rows(
        dataset.overseas_stock_cap,
        dataset.overseas_stock_cap_total,
        TOTAL_LABEL,
        TOTAL_LABEL,
    )
    floor = metrics.area_floor(
        dataset.overseas_stock_cap, product.OVERSEAS_CAP_COLUMN
    )
    ready = metrics.treemap_rows(
        rows, floor, product.OVERSEAS_CAP_COLUMN
    )
    assert len(ready) == len(rows)
    biggest = ready.loc[ready["market_cap_usd"].idxmax(), "stock_name"]
    trace = OVERSEAS_CHART.build(dataset, _selection(TOTAL_LABEL)).data[0]
    _sectors, stocks = _split_tiles(trace)
    sizes = {
        trace.labels[index]: float(trace.values[index]) for index in stocks
    }
    assert biggest == max(sizes, key=sizes.get)


def test_overseas_treemap_sector_hover_keeps_no_placeholder(dataset):
    """업종 칸에는 px가 자식에서 만들어 넣은 값이 남지 않는다."""
    from dashboard import format as fmt

    trace = OVERSEAS_CHART.build(dataset, _selection(TOTAL_LABEL)).data[0]
    sectors, _stocks = _split_tiles(trace)
    assert sectors
    lines = len(product_figures.OVERSEAS_HOVER)
    for index in sectors:
        assert list(trace.customdata[index]) == [fmt.EMPTY_TEXT] * lines


def test_overseas_treemap_follows_the_branch(dataset):
    """구분을 바꾸면 그림이 바뀐다."""
    branch_name = dataset.branch_names[0]
    total = OVERSEAS_CHART.build(dataset, _selection(TOTAL_LABEL)).data[0]
    branch = OVERSEAS_CHART.build(
        dataset, _selection(branch_name)
    ).data[0]
    assert list(total.values) != list(branch.values)


# --- ETF 표 -----------------------------------------------------------------
def test_etf_table_columns_match_the_source():
    """ETF 표 컬럼은 여섯 개다. 원본에 업종이 없어 그 컬럼이 빠진다."""
    fields = [column.field for column in product.ETF_TABLE_COLUMNS]
    assert fields == [
        "stock_rank",
        "stock_name",
        "trade_customer_count",
        "trade_value",
        "net_buy_amount",
        "rank_change",
    ]
    assert "sector" not in fields


def test_etf_table_sits_below_the_overseas_table(dataset):
    """ETF 표가 해외주식 표 다음에, 펀드 표가 그 옆에 온다."""
    views = callbacks.build_table_views(
        TAB, dataset, _selection(TOTAL_LABEL)
    )
    assert [view["title"] for view in views] == [
        TABLE.title,
        OVERSEAS_TABLE.title,
        ETF_TABLE.title,
        FUND_TABLE.title,
        PENSION_TABLE.title,
    ]
    assert [view["group"] for view in views[-3:]] == [
        product.ETF_GROUP,
        product.FUND_GROUP,
        product.PENSION_GROUP,
    ]


def test_etf_table_shows_the_chosen_branch(dataset):
    """고른 구분의 ETF 순위표만 나온다."""
    branch_name = dataset.branch_names[0]
    _total, rows = ETF_TABLE.build(dataset, _selection(branch_name))
    assert set(rows["branch_name"]) == {branch_name}
    assert len(rows) == STOCK_RANK_COUNT
    assert rows["stock_rank"].tolist() == sorted(rows["stock_rank"])


def test_etf_table_total_uses_the_source_row(dataset):
    """'전체'는 지점 행을 더해 만들지 않고 원본의 '전체' 행을 그대로 쓴다."""
    _total, rows = ETF_TABLE.build(dataset, _selection(TOTAL_LABEL))
    assert set(rows["branch_name"]) == {TOTAL_LABEL}
    assert len(rows) == STOCK_RANK_COUNT


def test_etf_table_keeps_its_own_selection(dataset):
    """ETF 줄은 다른 두 줄과 따로 움직인다."""
    branch_name = dataset.branch_names[0]
    selection = {
        product.SELECT_BRANCH: TOTAL_LABEL,
        product.SELECT_OVERSEAS_BRANCH: TOTAL_LABEL,
        product.SELECT_ETF_BRANCH: branch_name,
    }
    _total, etf_rows = ETF_TABLE.build(dataset, selection)
    _total, domestic_rows = TABLE.build(dataset, selection)
    assert set(etf_rows["branch_name"]) == {branch_name}
    assert set(domestic_rows["branch_name"]) == {TOTAL_LABEL}


def test_etf_table_marks_new_entries(dataset):
    """앞 달에 없던 종목의 순위변동 자리에 NEW가 적힌다."""
    from dashboard import format as fmt

    view = callbacks.build_table_view(
        ETF_TABLE, dataset, _selection(TOTAL_LABEL)
    )
    assert [row for row in view["row_data"] if row["rank_change"] is None]
    assert grid.format_cell(
        ETF_TABLE.columns, "rank_change", None
    ) == fmt.NEW_ENTRY_TEXT


def test_etf_money_columns_are_written_in_100m(dataset):
    """ETF 금액도 억원 숫자로 적는다. 시가총액 컬럼은 아예 없다."""
    fields = {column.field: column for column in ETF_TABLE.columns}
    assert fields["trade_value"].to_text(75_392_180_000) == "753.9"
    assert fields["net_buy_amount"].to_text(-3_375_230_000) == "-33.8"
    assert "market_cap" not in fields


def test_dash_etf_card_carries_the_control(dataset):
    """화면의 ETF·펀드 카드 헤더 안에 구분 컨트롤이 각각 들어간다.

    컨트롤이 있으면 조작 안내는 빠진다. 헤더 높이가 고정이라 세 줄은
    들어가지 않는다(→ layout._table_header_right).
    """
    view = callbacks.build_initial_view(dataset)
    panel = layout._tab_panel(TAB, view["tabs"][TAB.value])
    found = _find_ids(panel)
    groups = {g.name: g for g in TAB.select_groups}
    for name, key in (
        (product.ETF_GROUP, product.SELECT_ETF_BRANCH),
        (product.FUND_GROUP, product.SELECT_FUND_BRANCH),
    ):
        assert groups[name].select_id(key) in found
    # 다른 두 줄의 컨트롤은 카드 위 줄에 그대로 있다.
    assert TAB.select_id(product.SELECT_BRANCH) in found


def _find_ids(node) -> set:
    """레이아웃 트리에 들어 있는 컴포넌트 ID를 모두 모은다."""
    found = set()
    component_id = getattr(node, "id", None)
    if isinstance(component_id, str):
        found.add(component_id)
    children = getattr(node, "children", None)
    if children is None:
        return found
    if not isinstance(children, (list, tuple)):
        children = [children]
    for child in children:
        found |= _find_ids(child)
    return found


def test_static_html_etf_card_carries_the_control(panel):
    """정적 HTML도 ETF·펀드·연금 카드 헤더 안에 컨트롤을 그린다."""
    assert panel.count('class="card-controls"') == 3
    for key in ("product-etf", "product-fund", "product-pension"):
        assert f'data-chart="{key}"' in panel
        assert f'data-tab="{key}"' in panel


# --- 펀드 표 ----------------------------------------------------------------
def test_fund_table_columns_match_the_source():
    """펀드 표 컬럼은 여섯 개다.

    원본에 업종이 없어 해외주식 표보다 컬럼이 하나 적다
    (→ dashboard/sources/fund1.py).
    """
    fields = [column.field for column in product.FUND_TABLE_COLUMNS]
    assert fields == [
        "stock_rank",
        "stock_name",
        "trade_customer_count",
        "trade_value",
        "net_buy_amount",
        "rank_change",
    ]
    assert "market_cap" not in fields
    assert "sector" not in fields


def test_fund_table_shows_the_chosen_branch(dataset):
    """고른 구분의 펀드 순위표만 나온다."""
    branch_name = dataset.branch_names[0]
    _total, rows = FUND_TABLE.build(dataset, _selection(branch_name))
    assert set(rows["branch_name"]) == {branch_name}
    assert rows["stock_rank"].tolist() == sorted(rows["stock_rank"])


def test_fund_table_may_be_shorter_than_the_others(dataset):
    """20위까지 차지 않는 지점은 그만큼만 나온다.

    빈 순위를 채우면 화면에 없는 종목이 생긴다
    (→ dashboard/sources/fund1.py).
    """
    lengths = set()
    for branch_name in dataset.branch_names:
        _total, rows = FUND_TABLE.build(dataset, _selection(branch_name))
        assert len(rows) <= STOCK_RANK_COUNT
        lengths.add(len(rows))
    assert len(lengths) > 1


def test_fund_table_total_uses_the_source_row(dataset):
    """'전체'는 지점 행을 더해 만들지 않고 원본의 '전체' 행을 그대로 쓴다."""
    _total, rows = FUND_TABLE.build(dataset, _selection(TOTAL_LABEL))
    assert set(rows["branch_name"]) == {TOTAL_LABEL}
    assert len(rows) == STOCK_RANK_COUNT


def test_fund_table_keeps_its_own_selection(dataset):
    """펀드 줄은 ETF 줄과 따로 움직인다. 나란히 서 있어도 값이 다르다."""
    branch_name = dataset.branch_names[0]
    selection = {
        product.SELECT_BRANCH: TOTAL_LABEL,
        product.SELECT_OVERSEAS_BRANCH: TOTAL_LABEL,
        product.SELECT_ETF_BRANCH: TOTAL_LABEL,
        product.SELECT_FUND_BRANCH: branch_name,
    }
    _total, fund_rows = FUND_TABLE.build(dataset, selection)
    _total, etf_rows = ETF_TABLE.build(dataset, selection)
    assert set(fund_rows["branch_name"]) == {branch_name}
    assert set(etf_rows["branch_name"]) == {TOTAL_LABEL}


def test_fund_table_marks_new_entries(dataset):
    """앞 달에 없던 종목의 순위변동 자리에 NEW가 적힌다."""
    from dashboard import format as fmt

    view = callbacks.build_table_view(
        FUND_TABLE, dataset, _selection(TOTAL_LABEL)
    )
    assert [row for row in view["row_data"] if row["rank_change"] is None]
    assert grid.format_cell(
        FUND_TABLE.columns, "rank_change", None
    ) == fmt.NEW_ENTRY_TEXT


def test_fund_money_columns_are_written_in_100m(dataset):
    """펀드 금액도 억원 숫자로 적는다. 시가총액 컬럼은 아예 없다."""
    fields = {column.field: column for column in FUND_TABLE.columns}
    assert fields["trade_value"].to_text(20_956_960_000) == "209.6"
    assert fields["net_buy_amount"].to_text(-1_207_780_000) == "-12.1"
    assert "market_cap" not in fields


def test_fund_table_has_its_own_callback(dataset):
    """펀드 표만 다시 그리는 콜백이 따로 등록된다."""
    import app as app_module

    application = app_module.create_app()
    table_id = FUND_TABLE.table_id(TAB.value)
    assert any(table_id in key for key in application.callback_map)


# --- 연금 상품 표 ------------------------------------------------------------
def test_pension_table_uses_the_full_width(dataset):
    """연금 표는 그리드 칸이 아니라 화면 폭을 다 쓴다.

    연금 구분 셋이 가로로 늘어서 컬럼이 열여섯이라 한 칸에 들어가지 않는다.
    """
    assert not PENSION_TABLE.in_grid
    assert PENSION_TABLE in TAB.full_tables


def test_pension_table_columns_repeat_for_each_type():
    """다섯 항목이 연금 구분 셋마다 되풀이되어 컬럼이 열여섯이다."""
    columns = product.pension_columns()
    assert len(columns) == 1 + len(PENSION_TYPES) * 5
    assert columns[0].field == "stock_rank"
    # 순위는 왼쪽에 고정한다. 가로로 훑어도 몇 위의 줄인지 보여야 한다.
    assert columns[0].pinned
    assert list(product.PENSION_FIELDS) == list(PENSION_TYPES)
    fields = [column.field for column in columns[1:6]]
    assert fields == [
        product.pension_field(PENSION_TYPES[0], name)
        for name in (
            "stock_name",
            "trade_customer_count",
            "trade_value",
            "net_buy_amount",
            "rank_change",
        )
    ]
    # 구분마다 필드 이름이 달라야 한 행에 셋이 함께 들어간다.
    assert len({column.field for column in columns}) == len(columns)


def test_pension_headers_name_the_chosen_product():
    """헤더에 고른 상품 이름이 들어간다.

    같은 다섯 항목이 세 번 되풀이되므로, 구분만 적고 상품을 빼면 표만 보고는
    ETF인지 펀드인지 알 수 없다(→ registry.Table.columns).
    """
    for product_type in PENSION_RANK_PRODUCT_TYPES:
        columns = PENSION_TABLE.columns_of(
            {product.SELECT_PENSION_PRODUCT: product_type}
        )
        assert columns[1].header == f"{PENSION_TYPES[0]} {product_type} 종목명"
        headers = [column.header for column in columns[1:]]
        assert all(product_type in header for header in headers)
    # 컬럼 수와 자리는 상품이 바뀌어도 같다. 자리가 달라지면 정렬해 둔
    # 순서와 조절해 둔 너비가 어긋난다.
    assert PENSION_TABLE.dynamic_columns
    shapes = {
        tuple(
            column.field
            for column in PENSION_TABLE.columns_of(
                {product.SELECT_PENSION_PRODUCT: name}
            )
        )
        for name in PENSION_RANK_PRODUCT_TYPES
    }
    assert len(shapes) == 1


def test_pension_columns_are_wide_enough_for_their_headers():
    """컬럼 이름이 말줄임으로 잘리지 않을 만큼 넓다.

    컬럼이 열여섯이라 남는 폭을 나눠 가지면 한 칸이 좁아진다. 이름이 들어갈
    만큼을 최소 너비로 잡아 두고 화면보다 넓어지면 가로로 밀어 본다.
    """
    columns = product.pension_columns()
    for column in columns:
        assert column.min_width >= product.header_width(column.header)
    # 너비는 상품이 바뀌어도 같다. 라디오를 누를 때마다 들썩이면 안 되고,
    # 정적 HTML은 첫 화면의 너비를 그대로 쓴다.
    widths = {
        tuple(
            column.min_width
            for column in PENSION_TABLE.columns_of(
                {product.SELECT_PENSION_PRODUCT: name}
            )
        )
        for name in PENSION_RANK_PRODUCT_TYPES
    }
    assert len(widths) == 1
    # 다 합치면 화면보다 넓다. 그래서 가로 스크롤이 생긴다.
    assert sum(column.min_width for column in columns) > 1920


def test_pension_table_shows_the_chosen_branch_and_product(dataset):
    """고른 구분과 상품의 행만 나온다."""
    branch_name = dataset.branch_names[0]
    for product_type in PENSION_RANK_PRODUCT_TYPES:
        _total, rows = PENSION_TABLE.build(
            dataset, _selection(branch_name, product_type)
        )
        names = rows[
            product.pension_field(PENSION_TYPES[0], "stock_name")
        ].dropna()
        assert len(names)
        assert all(product_type in name for name in names)


def test_pension_table_lines_up_the_three_types_by_rank(dataset):
    """한 줄에 선 셋은 모두 같은 등수다.

    구분마다 따로 채우면 한 줄에 서로 다른 등수가 나란히 서게 된다.
    """
    _total, rows = PENSION_TABLE.build(dataset, _selection(TOTAL_LABEL))
    assert rows["stock_rank"].tolist() == sorted(rows["stock_rank"])
    assert rows["stock_rank"].iloc[0] == 1
    long = dataset.pension_rank_total
    for pension_type in PENSION_TYPES:
        part = long[
            (long["pension_type"] == pension_type)
            & (long["product_type"] == PENSION_RANK_PRODUCT_TYPES[0])
        ].set_index("stock_rank")
        field = product.pension_field(pension_type, "stock_name")
        for rank, name in zip(rows["stock_rank"], rows[field]):
            assert name == part.loc[rank, "stock_name"]


def test_pension_table_leaves_missing_ranks_empty(dataset):
    """어느 구분에 그 순위가 없으면 그 다섯 칸을 비운다.

    파는 종목이 적은 구분이 있어 순위가 끝까지 차지 않는다. 그 자리를
    다음 종목으로 채우면 한 줄에 서로 다른 등수가 선다.
    """
    branch_name = _short_pension_branch(dataset)
    view = callbacks.build_table_view(
        PENSION_TABLE, dataset, _selection(branch_name, "펀드")
    )
    holes = [
        row
        for row in view["row_data"]
        if row[product.pension_field("개인연금", "stock_name")] is None
    ]
    assert holes
    for row in holes:
        for name in ("trade_customer_count", "trade_value"):
            assert row[product.pension_field("개인연금", name)] is None


def test_pension_empty_rank_change_tells_new_from_missing(dataset):
    """순위변동 빈 칸의 뜻이 둘이라 문구를 갈라 적는다.

    앞 달에 없던 종목이면 NEW, 그 구분에 그 순위가 아예 없으면 `-`다.
    값만 보면 둘 다 비어 있어 가릴 수 없다(→ grid._cell_text).
    """
    from dashboard import format as fmt

    branch_name = _short_pension_branch(dataset)
    view = callbacks.build_table_view(
        PENSION_TABLE, dataset, _selection(branch_name, "펀드")
    )
    field = product.pension_field("개인연금", "rank_change")
    name = product.pension_field("개인연금", "stock_name")
    texts = {
        (row[name] is None): row[f"{field}{grid.TEXT_SUFFIX}"]
        for row in view["row_data"]
        if row[field] is None
    }
    # 줄이 없는 자리는 `-`, 줄은 있는데 값이 없는 자리는 NEW다.
    assert texts[True] == fmt.EMPTY_TEXT
    assert texts[False] == fmt.NEW_ENTRY_TEXT


def _short_pension_branch(dataset) -> str:
    """개인연금 펀드가 20위까지 차지 않는 지점 하나."""
    long = dataset.pension_rank
    counts = long[
        (long["pension_type"] == "개인연금")
        & (long["product_type"] == "펀드")
    ].groupby("branch_name", observed=True)["stock_rank"].max()
    short = counts[counts < counts.max()]
    assert len(short)
    return str(short.index[0])


def test_pension_money_columns_keep_their_units(dataset):
    """거래대금·순매수금액은 원으로 적는다."""
    fields = {
        column.field: column for column in product.pension_columns()
    }
    assert fields[
        product.pension_field("IRP", "trade_value")
    ].to_text(10_000) == "1만원"
    assert fields[
        product.pension_field("IRP", "net_buy_amount")
    ].to_text(-10_000) == "-1만원"


def test_pension_product_is_a_radio():
    """값이 둘뿐이라 펼치지 않고 라디오로 둔다."""
    from dashboard.tabs.registry import KIND_RADIO

    select = {
        item.key: item
        for item in TAB.selects
    }[product.SELECT_PENSION_PRODUCT]
    assert select.kind == KIND_RADIO
    assert select.options(None) == list(PENSION_RANK_PRODUCT_TYPES)


def test_static_html_swaps_the_pension_headers(dataset):
    """정적 HTML은 조합마다 컬럼 이름을 담아 두고 갈아 끼운다.

    서버가 없으므로 행과 마찬가지로 미리 만들어 둔다
    (→ export_html._table_headers).
    """
    import export_html

    spec = export_html._tab_tables(dataset)[
        f"{TAB.value}-{product.PENSION_GROUP}"
    ]
    headers = spec["headers"][PENSION_TABLE.table_id(TAB.value)]
    branch = dataset.branch_names[0]
    for product_type in PENSION_RANK_PRODUCT_TYPES:
        names = headers[f"{branch}|{product_type}"]
        assert len(names) == len(product.pension_columns())
        assert names[1] == f"{PENSION_TYPES[0]} {product_type} 종목명"
    # 다른 표에는 이름을 담지 않는다. 바뀌지 않기 때문이다.
    assert len(spec["headers"]) == 1
