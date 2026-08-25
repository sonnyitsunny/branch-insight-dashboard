"""Figure·그리드·포맷·앱 조립 검증."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import pytest

from dashboard import callbacks, format as fmt, grid, layout
from dashboard import figures as shared_figures
from dashboard import tabs as tab_registry
from dashboard.data import (
    INVESTMENT_TYPES,
    TOTAL_LABEL,
    load_dashboard_data,
    shift_month,
)
from dashboard.tabs import customer
from dashboard.tabs.customer import figures, metrics
from fixture_data import (
    BRANCH_COUNT,
)

TAB = customer.TAB
COLUMNS = customer.TABLE_COLUMNS
CHARTS = {chart.key: chart for chart in TAB.charts}


def draw(key: str, data, selected: str | None = None):
    """탭 선언이 그리는 Figure. 화면·HTML과 같은 경로를 지난다.

    선택값 하나만 넘기면 그 차트의 첫 컨트롤에 넣는다. 컨트롤이 여럿인
    차트는 선택값 묶음을 그대로 넘긴다.
    """
    chart = CHARTS[key]
    if isinstance(selected, dict):
        return chart.build(data, selected)
    selection = chart.defaults(data)
    if selected is not None and chart.selects:
        selection[chart.selects[0].key] = selected
    return chart.build(data, selection)


@pytest.fixture(scope="module")
def dataset():
    return load_dashboard_data()


# --- 포맷 -------------------------------------------------------------------
def test_count_and_delta_format():
    assert fmt.format_count(12350) == "12,350명"
    assert fmt.format_count_delta(1730) == "+1,730명"
    assert fmt.format_count_delta(-320) == "-320명"


def test_assets_format():
    """금액은 조·억·만으로 접어 적는다.

    한 가지 단위로만 적으면(28,266억원) 자릿수를 사람이 세어야 크기를
    가늠할 수 있다.
    """
    assert fmt.format_assets(214900) == "21조 4,900억원"
    assert fmt.format_assets(28266) == "2조 8,266억원"
    assert fmt.format_assets(4900) == "4,900억원"
    assert fmt.format_assets(3226.992394) == "3,226억 9,924만원"
    assert fmt.format_assets(0.5) == "5,000만원"
    assert fmt.format_assets_delta(170) == "+170억원"
    assert fmt.format_assets_delta(-10200) == "-1조 200억원"


def test_million_won_format():
    """1인 평균은 억에 못 미치므로 만원으로 적힌다."""
    assert fmt.format_million_won(31.9) == "3,190만원"
    assert fmt.format_million_won(2425.0) == "24억 2,500만원"
    assert fmt.format_million_won(22.62) == "2,262만원"
    assert fmt.format_million_won_delta(1.2) == "+120만원"


def test_money_format_shows_at_most_two_units():
    """자리를 다 적으면 길어져 표 한 칸에 들어가지 않는다.

    값이 있는 가장 큰 자리부터 두 자리만 적고, 그 안의 빈 자리는 건너뛴다.
    """
    assert fmt.MONEY_UNIT_COUNT == 2
    # 2조 8,266억 5,432만원이 아니다.
    assert fmt.format_assets(28266.5432) == "2조 8,266억원"
    # 억 자리가 비면 건너뛰고 다음 자리를 적지 않는다.
    assert fmt.format_assets(20000.5) == "2조원"
    # 만원 아래는 버린다. 0으로 접히는 것이 값이 없는 것과 구분된다.
    assert fmt.format_assets(0.00005) == "0원"
    assert fmt.format_assets(None) == fmt.EMPTY_TEXT


def test_usd_format():
    """달러는 조·억으로 접지 않고 원본 숫자에 통화만 붙인다.

    조·억은 만 단위로 끊는 한국식 표기라 달러 금액에 붙이면 원본과 대조할
    수 없다(→ dashboard/sources/overseas_stock2.py).
    """
    assert fmt.format_usd(769_935_024) == "USD769,935,024"
    assert fmt.format_usd(3_000_000_000_000) == "USD3,000,000,000,000"
    assert fmt.format_usd(0) == "USD0"
    assert fmt.format_usd(None) == fmt.EMPTY_TEXT


def test_percent_and_pp_format():
    assert fmt.format_percent(43.34) == "43.3%"
    assert fmt.format_percent(43.0) == "43.0%"
    assert fmt.format_signed_percent(11.0) == "+11.0%"
    assert fmt.format_signed_percent(-2.4) == "-2.4%"
    # 증가율(%)과 한 줄에 놓이므로 단위를 %p로 구분해 적는다
    # (→ format.format_pp_delta).
    assert fmt.format_pp_delta(-0.8) == "-0.8%p"
    assert fmt.format_pp_delta(1.0) == "+1.0%p"
    assert fmt.format_age(29.42) == "29.4세"


def test_missing_values_render_dash():
    assert fmt.format_count(None) == fmt.EMPTY_TEXT
    assert fmt.format_percent(float("nan")) == fmt.EMPTY_TEXT
    assert fmt.format_signed_percent(float("inf")) == fmt.EMPTY_TEXT


def test_month_labels():
    assert fmt.format_month("2026-07") == "2026년 7월"
    assert fmt.format_month_short("2025-07") == "25.07"


# --- Figure -----------------------------------------------------------------
def test_trend_figure_has_bar_and_line_with_two_axes(dataset):
    trend = metrics.customer_trend(dataset.monthly, "지점 01")
    figure = figures.create_customer_trend_figure(trend, "지점 01")
    assert isinstance(figure, go.Figure)
    kinds = [trace.type for trace in figure.data]
    assert "bar" in kinds and "scatter" in kinds
    line = next(trace for trace in figure.data if trace.type == "scatter")
    assert line.yaxis == "y2"
    assert figure.layout.yaxis2.side == "right"


def test_trend_axes_zoom_to_the_data_not_to_zero(dataset):
    """0부터 그리면 몇 만 대에서 몇 백 명 움직이는 변화가 안 보인다."""
    trend = metrics.customer_trend(dataset.monthly, "지점 01")
    figure = figures.create_customer_trend_figure(trend, "지점 01")

    for axis, column in (("yaxis", "total_count"), ("yaxis2", "branch_count")):
        low, high = figure.layout[axis].range
        values = trend[column].dropna()
        assert low < values.min() and high > values.max()
        # 값이 움직인 폭이 축 높이의 절반은 넘어야 추이가 보인다.
        assert (values.max() - values.min()) > (high - low) * 0.5
        assert figure.layout[axis].rangemode != "tozero"


def _scatter_figure(dataset):
    scatter = metrics.growth_scatter(dataset.monthly)
    return scatter, figures.create_growth_scatter_figure(
        scatter, metrics.median_customer_count(scatter)
    )


def test_scatter_figure_uses_linear_axis_and_reference_lines(dataset):
    """축은 선형이다.

    로그 축은 규모가 100배 넘게 벌어질 때 쓴다. 지점 규모 차이는 그보다
    훨씬 작은데 로그로 그리면 눈금이 불규칙하게 촘촘해져 세로선이 화면을
    덮고 점 사이 간격도 왜곡된다(회귀 방지).
    """
    scatter, figure = _scatter_figure(dataset)
    assert figure.layout.xaxis.type != "log"
    assert len(figure.data[0].x) == BRANCH_COUNT

    horizontal = [shape for shape in figure.layout.shapes if shape.y0 == shape.y1 == 0]
    vertical = [shape for shape in figure.layout.shapes if shape.x0 == shape.x1]
    assert horizontal, "YoY 0% 가로 기준선이 있어야 한다"
    assert vertical, "고객 수 중앙값 세로 기준선이 있어야 한다"
    # 선형 축이면 세로선이 규칙적이라 격자선을 켜도 복잡해지지 않는다.
    assert figure.layout.xaxis.showgrid is not False
    # 기준선 좌표는 log10 변환 없이 실제 고객 수 그대로 쓴다.
    assert vertical[0].x0 == pytest.approx(scatter["current_count"].median())


def test_scatter_labels_every_branch(dataset):
    """지점 이름을 일부만 보여주면 나머지는 점만 찍혀 어느 지점인지 알 수 없다."""
    scatter, figure = _scatter_figure(dataset)
    labels = list(figure.data[0].text)
    assert len(labels) == BRANCH_COUNT
    assert all(labels), "빈 라벨이 없어야 한다"
    assert set(labels) == set(scatter["branch_name"])


def test_scatter_has_no_corner_captions(dataset):
    """네 귀퉁이 사분면 문구는 기준선 두 개로 이미 자명하다.

    지점 27개 라벨이 들어오면 자리만 차지한다.
    """
    _, figure = _scatter_figure(dataset)
    texts = [annotation.text for annotation in figure.layout.annotations]
    assert not [text for text in texts if "고객 수 적음" in text or "고객 수 많음" in text]
    assert any("중앙값" in text for text in texts)


def test_age_figure_is_grouped_with_two_series(dataset):
    distribution = metrics.age_distribution(dataset.age, "지점 02")
    figure = figures.create_age_distribution_figure(distribution, "지점 02")
    assert figure.layout.barmode == "group"
    assert [trace.name for trace in figure.data] == [TOTAL_LABEL, "지점 02"]


def test_investment_figure_is_stacked_with_fixed_order(dataset):
    breakdown = metrics.investment_breakdown(dataset.investment)
    figure = figures.create_investment_figure(breakdown, TOTAL_LABEL)
    assert figure.layout.barmode == "stack"
    assert all(trace.orientation == "h" for trace in figure.data)
    assert list(figure.layout.yaxis.categoryarray) == list(reversed(INVESTMENT_TYPES))
    assert len(figure.layout.annotations) == len(INVESTMENT_TYPES)


def test_figures_handle_empty_input():
    empty = pd.DataFrame()
    assert isinstance(figures.create_customer_trend_figure(empty, "지점 01"), go.Figure)
    assert figures.create_growth_scatter_figure(empty, None).layout.annotations[0].text
    assert isinstance(figures.create_age_distribution_figure(empty, "지점 01"), go.Figure)
    assert isinstance(figures.create_investment_figure(empty, TOTAL_LABEL), go.Figure)


def test_hover_labels_are_readable_on_every_chart(dataset):
    """hover 글자색을 직접 정한다.

    비워 두면 Plotly가 계열 색으로 글자를 그려 흰 배경 위에서 흐려진다.
    """
    first = dataset.branch_names[0]
    charts = (
        draw("trend", dataset, first),
        draw("scatter", dataset),
        draw("age", dataset, first),
        draw("investment", dataset, TOTAL_LABEL),
    )
    for figure in charts:
        hover = figure.layout.hoverlabel
        assert hover.bgcolor == shared_figures.COLOR_SURFACE
        assert hover.font.color == shared_figures.COLOR_TEXT


def test_legend_hint_is_added_to_charts_that_have_a_legend(dataset):
    """범례를 눌러 계열을 끌 수 있다는 사실을 화면에 적는다.

    안내를 base_layout이 붙이므로 차트를 더해도 빠뜨리지 않는다.
    범례를 통째로 바꾼 차트(투자성향)에도 남아야 한다.
    """
    first = dataset.branch_names[0]
    for key, args in (
        ("trend", (first,)),
        ("age", (first,)),
        ("investment", (TOTAL_LABEL,)),
    ):
        figure = draw(key, dataset, *args)
        assert figure.layout.showlegend is not False
        title = figure.layout.legend.title
        assert title.text == shared_figures.LEGEND_HINT_TEXT
        # 범례 위에 따로 한 줄을 차지해야 지표 이름과 겹치지 않는다.
        # 'left'를 넣으면 Plotly가 항목 격자를 제목 폭만큼 오른쪽으로 밀어
        # 오른쪽 칸이 차트 밖으로 나간다(→ figures.legend_hint).
        assert title.side == "top"
        assert "left" not in (title.side or "")


def test_legend_hint_is_left_out_where_there_is_no_legend(dataset):
    """범례가 없으면 안내할 것도 없다. 빈 차트의 안내 문구도 가리지 않는다."""
    for figure in (
        draw("scatter", dataset),
        shared_figures.empty_figure(),
    ):
        assert figure.layout.showlegend is False
        assert figure.layout.legend.title.text is None


def test_zoom_is_handled_by_plotly_not_by_a_callback(dataset):
    """확대·축소는 Plotly가 브라우저에서 처리해야 정적 HTML에서도 동작한다.

    Dash 콜백으로 만들면 서버가 없는 정적 HTML에서 눌러도 아무 일이 없다.
    """
    config = shared_figures.ZOOMABLE_CONFIG
    assert config["displayModeBar"] is True
    buttons = config["modeBarButtons"][0]
    for name in ("zoomIn2d", "zoomOut2d", "resetScale2d"):
        assert name in buttons
    assert "toImage" not in buttons
    # 확대한 뒤 드래그로 옮겨 볼 수 있어야 한다.
    assert draw("scatter", dataset).layout.dragmode == "pan"


def test_only_the_scatter_chart_allows_zooming():
    """확대를 켠 차트는 선언에 표시하고, 나머지는 기존 설정 그대로 둔다."""
    zoomable = [chart.key for chart in TAB.charts if chart.zoomable]
    assert zoomable == ["scatter"]
    assert shared_figures.PLOTLY_CONFIG["displayModeBar"] is False
    assert "modeBarButtons" not in shared_figures.PLOTLY_CONFIG
    assert shared_figures.base_layout()["dragmode"] is False


def test_plotly_config_hides_logo():
    assert shared_figures.PLOTLY_CONFIG["displaylogo"] is False
    assert shared_figures.PLOTLY_CONFIG["responsive"] is True


# --- 그리드 -----------------------------------------------------------------
def test_column_defs_order_and_formatters():
    column_defs = grid.build_column_defs(COLUMNS)
    assert [column["headerName"] for column in column_defs] == [
        "지점명",
        "공통고객 수",
        "공통고객 수 증가율(YoY)",
        "남성(%)",
        "평균 연령",
        "최근 가입 비중(%)",
        "투자권유 희망(%)",
        "고객등급 S 이상(%)",
    ]
    assert column_defs[0].get("valueFormatter") is None
    assert all("valueFormatter" in column for column in column_defs[1:])


def test_branch_name_column_is_pinned_left():
    """지점명은 왼쪽에 고정한다. 가로 스크롤에도 어느 지점인지 보여야 한다."""
    column_defs = grid.build_column_defs(COLUMNS)
    pinned = column_defs[0]
    assert pinned["field"] == grid.pinned_field(COLUMNS)
    assert pinned["pinned"] == "left"
    # 고정 컬럼은 flex 계산에서 빠진다. flex가 남으면 너비가 0으로 접힌다.
    assert pinned["flex"] == 0
    assert pinned["width"] == customer.BRANCH_COLUMN_WIDTH
    assert all("pinned" not in column for column in column_defs[1:])


def test_column_defs_alignment_classes():
    """정렬은 CSS 클래스로만 정한다.

    ag-grid의 `type`을 쓰면 그 타입이 넣는 headerClass·cellClass가
    아래 클래스와 서로 덮어써서 헤더와 셀의 정렬이 어긋난다.
    """
    column_defs = grid.build_column_defs(COLUMNS)
    assert all("type" not in column for column in column_defs)
    assert column_defs[0]["cellClass"] == "grid-cell-text"
    assert all(column["cellClass"] == "grid-cell-number" for column in column_defs[1:])
    assert grid.DEFAULT_COL_DEF["headerClass"] == "grid-header"


def test_row_data_keeps_numbers_for_sorting(dataset):
    total_row, branch_rows = metrics.branch_table(dataset.monthly, dataset.summary)
    rows = grid.build_row_data(branch_rows, COLUMNS)
    assert len(rows) == BRANCH_COUNT
    assert isinstance(rows[0]["customer_count"], int)
    assert isinstance(rows[0]["male_share"], float)
    pinned = grid.build_pinned_top_row(total_row, COLUMNS)
    assert len(pinned) == 1
    assert pinned[0]["branch_name"] == TOTAL_LABEL


def test_grid_options_pin_total_row(dataset):
    total_row, _ = metrics.branch_table(dataset.monthly, dataset.summary)
    options = grid.build_grid_options(total_row, COLUMNS)
    assert options["pinnedTopRowData"][0]["branch_name"] == TOTAL_LABEL


def test_grid_handles_empty_input():
    assert grid.build_row_data(pd.DataFrame(), COLUMNS) == []
    assert grid.build_pinned_top_row(None, COLUMNS) == []
    assert grid.build_grid_options(None, COLUMNS)["pinnedTopRowData"] == []


# --- 탭 등록표 --------------------------------------------------------------
def test_every_declared_tab_is_either_built_or_disabled():
    """구현한 탭은 등록표에, 나머지는 순서 목록에만 있다.

    구현했는데 순서 목록에서 빠지면 화면에 나타나지 않는다.
    """
    ordered = [value for value, _label in tab_registry.TAB_ORDER]
    assert len(ordered) == len(set(ordered)), "탭 값이 겹친다"
    for tab in tab_registry.TABS:
        assert tab.value in ordered, tab.value
        assert tab.implemented
    assert tab_registry.default_value() in ordered


def test_chart_and_table_ids_are_unique_across_tabs():
    """ID가 겹치면 콜백이 엉뚱한 차트를 그린다(→ AGENTS.md §11)."""
    ids = []
    for tab in tab_registry.TABS:
        for chart in tab.charts:
            ids.append(chart.chart_id(tab.value))
            for select in chart.selects:
                ids.append(chart.select_id(tab.value, select.key))
        for select in tab.selects:
            ids.append(tab.select_id(select.key))
        for table in tab.tables:
            ids.append(table.table_id(tab.value))
    assert len(ids) == len(set(ids)), "겹치는 ID가 있다"


def test_a_new_tab_needs_no_change_outside_its_module():
    """등록표에 넣기만 하면 화면과 콜백이 따라온다.

    탭을 추가할 때 layout·callbacks·export_html을 고쳐야 한다면 선언이
    한 곳에 모여 있지 않다는 뜻이다.
    """
    from dashboard import layout as layout_module

    for tab in tab_registry.TABS:
        for chart in tab.charts:
            assert callable(chart.build)
            for select in chart.selects:
                assert callable(select.options)
                assert callable(select.default)
    # 레이아웃은 탭 이름을 상수로 갖고 있지 않다.
    assert not hasattr(layout_module, "OTHER_TABS")
    assert not hasattr(layout_module, "TAB_CUSTOMER")


# --- 앱 조립 ----------------------------------------------------------------
def test_initial_view_and_layout_build(dataset):
    import app as app_module

    view = callbacks.build_initial_view(dataset)
    assert set(view) >= {"kpis", "current_month", "previous_month", "tabs"}
    tab_view = view["tabs"]["customer"]
    assert set(tab_view["charts"]) == {chart.key for chart in TAB.charts}
    assert set(tab_view["tables"][0]) >= {
        "column_defs",
        "row_data",
        "grid_options",
    }
    assert len(tab_view["context"]["branch_names"]) == BRANCH_COUNT
    assert app_module.app.layout is not None


def test_view_carries_reference_months_and_branch_count(dataset):
    """레이아웃이 상수를 직접 읽지 않도록 기준 월·지점 수를 view로 내려보낸다."""
    view = callbacks.build_initial_view(dataset)
    assert view["current_month"] == dataset.months[-1]
    assert view["previous_month"] == shift_month(view["current_month"], -1)
    context = view["tabs"]["customer"]["context"]
    assert context["branch_count"] == BRANCH_COUNT


def test_screen_text_follows_the_data():
    """데이터 기간·지점 수가 달라지면 화면 문구도 따라간다.

    예전에는 기준 월과 '27개 지점'이 문자열로 박혀 있어 데이터가 바뀌어도
    옛 값을 그대로 보여줬다(회귀 방지).
    """
    from dashboard import layout as layout_module

    full = load_dashboard_data()
    trimmed = load_dashboard_data(
        filters={
            "base_months": [month for month in full.months if month <= "2026-03"],
            "branch_names": full.branch_names[:5],
        }
    )
    view = callbacks.build_initial_view(trimmed)
    tab_view = view["tabs"]["customer"]

    subtitle = layout_module._page_header(view).children[1].children
    assert "2026년 3월" in subtitle
    assert "2026년 2월" in subtitle
    assert "2026년 7월" not in subtitle

    card = layout_module._table_card(tab_view["tables"][0])
    header_right = card.children[0].children[1]
    table_description = header_right.children[0].children
    assert "5행" in table_description
    assert "27행" not in table_description

    hover = tab_view["charts"]["scatter"]["figure"].data[0].hovertemplate
    assert "2026년 3월" in hover and "2025년 3월" in hover
    assert "2026년 7월" not in hover


def test_callback_ids_are_registered(dataset):
    """선택 컨트롤이 있는 차트·선택 줄마다 콜백이 하나씩 있어야 한다.

    선언에서 만든 ID를 그대로 쓰므로, 탭을 추가하면 콜백도 따라 붙는다.
    없는 ID를 참조하지 않는지도 함께 본다(→ AGENTS.md §11).

    선택 줄은 그 줄의 표를 한 콜백으로 함께 그린다. 표가 몇 개인지는
    데이터가 정하므로 첫 화면 값에서 ID를 가져온다. 줄이 둘 이상인 탭은
    콜백도 줄마다 하나씩이며, 각자 자기 줄의 카드만 다시 그린다
    (→ registry.Tab.select_groups).
    """
    import app as app_module

    registered = set(app_module.app.callback_map.keys())
    # 선택 줄을 따르는 차트는 자기 콜백을 갖지 않는다. 그 줄의 콜백이
    # 표와 함께 그린다. 여기서도 등록하면 같은 Figure에 Output이 둘이
    # 되어 Dash가 멈춘다(→ callbacks.register_callbacks).
    expected = {
        f"{chart.chart_id(tab.value)}.figure"
        for tab in tab_registry.TABS
        for chart in tab.charts
        if chart.selects and not chart.follows_tab
    }
    for tab in tab_registry.TABS:
        for group in tab.select_groups:
            if not (group.selects and (group.tables or group.followers)):
                continue
            # 표와 '그 줄을 따르는 차트'가 한 콜백에 함께 묶인다. 둘이
            # 갈라지면 한 화면에서 서로 다른 지점을 가리키게 된다
            # (→ callbacks._register_group_selection).
            views = callbacks.build_table_views(
                tab, dataset, group.defaults(dataset), group.tables
            )
            ids = [f"{view['table_id']}.rowData" for view in views]
            # 컬럼 이름이 선택에 따라 바뀌는 표는 columnDefs도 함께 내보낸다
            # (→ registry.Table.columns).
            ids += [
                f"{view['table_id']}.columnDefs"
                for view in views
                if view["dynamic_columns"]
            ]
            ids += [
                f"{chart.chart_id(tab.value)}.figure"
                for chart in group.followers
            ]
            assert ids
            expected.add(f"..{'...'.join(ids)}..")
    assert expected
    assert expected <= registered
    # 선택 컨트롤이 없는 차트에는 콜백을 만들지 않는다.
    assert len(registered) == len(expected)


# --- 상단 KPI 카드 보조 문구 -------------------------------------------------
def test_delta_text_can_omit_the_rate_in_parentheses():
    """증감이 이미 비율의 차이면 괄호 안 증감률을 뺀다.

    괄호 안에 또 %가 붙으면 '+1.3% (+3.9%)'처럼 두 숫자가 같은 뜻으로
    읽힌다(→ layout.KpiCard).
    """
    metric = {"value": 34.5, "delta": 1.28, "rate": 3.85}
    assert layout.delta_text(metric, fmt.format_pp_delta, False) == (
        "전월 대비 +1.3%p"
    )


def test_count_and_money_cards_keep_the_rate():
    """인원·금액은 증감이 절대 수라 몇 % 움직였는지가 함께 있어야 한다."""
    metric = {"value": 75659, "delta": 317, "rate": 0.42}
    by_key = {row.key: row for row in layout.KPI_CARDS}
    for key in ("customer_count", "net_assets", "common_revenue"):
        card = by_key[key]
        assert card.show_rate is True, key
        assert "(+0.4%)" in layout.delta_text(
            metric, card.to_delta_text, card.show_rate
        ), key


def test_share_card_pairs_the_ratio_with_the_customer_count():
    """비중 카드는 짝이 되는 인원수를 값과 증감 양쪽에 함께 적는다.

    34.5%만으로는 몇 명인지, 몇 명이 늘어 그렇게 됐는지 알 수 없다
    (→ layout.KpiCard).
    """
    card = {row.key: row for row in layout.KPI_CARDS}["transaction_share"]
    kpis = {
        "transaction_share": {"value": 34.5, "delta": 1.28, "rate": 3.85},
        "transaction_customer_count": {
            "value": 57282,
            "delta": 1730,
            "rate": 3.11,
        },
    }
    value, sub_text, line, delta = layout.kpi_parts(card, kpis)
    assert value == "34.5%"
    assert sub_text == "57,282명"
    # 비중 차이는 %p로 적어 증가율과 갈라 놓는다. 괄호는 증감률이 아니라
    # 짝 지표인 인원 증감이 가져간다.
    assert line == "전월 대비 +1.3%p (+1,730명)"
    # 증감 방향은 큰 숫자인 비중 기준이다.
    assert delta == 1.28


def test_share_card_without_a_count_leaves_the_ratio_alone():
    """거래 원본이 없으면 인원수도 괄호도 적지 않는다.

    0명으로 채우면 "없음"이 "0으로 측정됨"으로 바뀐다.
    """
    card = {row.key: row for row in layout.KPI_CARDS}["transaction_share"]
    kpis = {
        "transaction_share": {"value": 34.5, "delta": 1.28, "rate": 3.85},
        "transaction_customer_count": {},
    }
    _value, sub_text, line, _delta = layout.kpi_parts(card, kpis)
    assert sub_text == ""
    assert line == "전월 대비 +1.3%p"


def test_missing_rate_leaves_no_empty_parentheses():
    """전월 값이 없으면 괄호 자체를 붙이지 않는다."""
    metric = {"value": 75659, "delta": 317, "rate": None}
    assert layout.delta_text(metric, fmt.format_count_delta) == (
        "전월 대비 +317명"
    )
