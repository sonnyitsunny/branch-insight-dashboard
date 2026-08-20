"""상품 탭 검증.

왼쪽은 지점별 거래 상위 종목 표(상품_국내주식1), 오른쪽은 시가총액 상위
종목 트리맵(상품_국내주식2)이다. 탭 맨 위의 지점 선택 하나가 둘에 함께
걸린다.

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
from dashboard.data import TOTAL_LABEL, load_dashboard_data
from dashboard.tabs import product
from dashboard.tabs.product import figures as product_figures
from dashboard.tabs.product import metrics
from fixture_data import STOCK_CAP_COUNT, STOCK_RANK_COUNT

TAB = product.TAB
TABLE = TAB.tables[0]
CHART = TAB.charts[0]


@pytest.fixture(scope="module")
def dataset():
    return load_dashboard_data()


def _selection(branch_name: str) -> dict:
    return {product.SELECT_BRANCH: branch_name}


# --- 선언 --------------------------------------------------------------------
def test_one_branch_select_drives_both_cards():
    """지점 컨트롤은 탭에 하나뿐이고 차트가 그것을 따른다.

    카드마다 컨트롤을 두면 두 값이 어긋나 한 화면에서 서로 다른 지점을
    보여주게 된다.
    """
    assert [select.key for select in TAB.selects] == [product.SELECT_BRANCH]
    assert CHART.follows_tab
    assert CHART.selects == ()
    assert TAB.followers == (CHART,)


def test_table_sits_next_to_the_chart():
    """표는 화면 폭 전체가 아니라 차트 옆 그리드 칸에 놓인다."""
    assert TABLE.in_grid
    assert TAB.grid_tables == (TABLE,)
    assert TAB.full_tables == ()


def test_table_columns_match_the_source():
    """표 컬럼은 원본이 주는 여덟 개다."""
    fields = [column.field for column in product.TABLE_COLUMNS]
    assert fields == [
        "stock_rank",
        "stock_name",
        "sector",
        "market_cap",
        "trade_customer_count",
        "trade_value",
        "net_buy_amount",
        "rank_change",
    ]


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


def test_money_columns_keep_their_units(dataset):
    """시가총액은 억원, 거래대금·순매수금액은 원으로 적는다.

    같은 표기 함수를 쓰면 억원 값이 원으로 읽혀 1억 배 어긋난다.
    """
    fields = {column.field: column for column in product.TABLE_COLUMNS}
    assert fields["market_cap"].to_text(10_000) == "1조원"
    assert fields["trade_value"].to_text(10_000) == "1만원"
    assert fields["net_buy_amount"].to_text(-10_000) == "-1만원"


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
def _split_tiles(trace) -> tuple[list[int], list[int]]:
    """업종 칸과 종목 칸의 자리.

    px가 만든 트리맵에서 업종 칸은 위 칸이 없어 `parents`가 빈 문자열이다.
    """
    sectors = [i for i, parent in enumerate(trace.parents) if not parent]
    stocks = [i for i, parent in enumerate(trace.parents) if parent]
    return sectors, stocks


def test_treemap_groups_stocks_under_sectors(dataset):
    """종목이 업종 아래에 묶인다."""
    figure = CHART.build(dataset, _selection(TOTAL_LABEL))
    assert isinstance(figure, go.Figure)
    trace = figure.data[0]
    sectors, stocks = _split_tiles(trace)
    assert len(stocks) == STOCK_CAP_COUNT
    assert sectors
    # 종목의 부모는 모두 업종 칸이다.
    labels = {trace.labels[i] for i in sectors}
    assert {trace.parents[i] for i in stocks} <= labels


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
    """콜백이 만든 표 값에 선언한 높이가 실려 화면까지 간다."""
    views = callbacks.build_table_views(
        TAB, dataset, _selection(TOTAL_LABEL)
    )
    assert [view["height"] for view in views] == [product.CARD_HEIGHT]


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

    chart_id = CHART.chart_id(TAB.value)
    variants = export_html._figure_variants(dataset)
    options = TAB.option_map(dataset)[product.SELECT_BRANCH]
    assert set(variants[chart_id]) == set(options)
    # 브라우저가 표와 함께 이 차트를 갈아 끼운다.
    assert export_html._tab_tables()[TAB.value]["charts"] == [chart_id]
    assert chart_id in export_html._chart_configs()


def test_static_html_shows_only_the_chosen_branch(panel, dataset):
    """지금 고른 지점의 행만 보이고 나머지는 숨어 있다."""
    rows = re.findall(r"<tr [^>]*data-scope=\"([^\"]+)\"([^>]*)>", panel)
    assert rows
    shown = [scope for scope, rest in rows if "hidden" not in rest]
    assert set(shown) == {TOTAL_LABEL}
    assert len(shown) == STOCK_RANK_COUNT
