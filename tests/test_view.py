"""Figure·그리드·포맷·앱 조립 검증."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import pytest

from dashboard import callbacks, figures, format as fmt, grid, metrics
from dashboard.data import (
    INVESTMENT_TYPES,
    TOTAL_LABEL,
    load_dashboard_data,
    shift_month,
)
from fixture_data import (
    BRANCH_COUNT,
)


@pytest.fixture(scope="module")
def dataset():
    return load_dashboard_data()


# --- 포맷 -------------------------------------------------------------------
def test_count_and_delta_format():
    assert fmt.format_count(12350) == "12,350명"
    assert fmt.format_count_delta(1730) == "+1,730명"
    assert fmt.format_count_delta(-320) == "-320명"


def test_assets_format():
    assert fmt.format_assets(214900) == "21조 4,900억원"
    assert fmt.format_assets(4900) == "4,900억원"
    assert fmt.format_assets_delta(170) == "+170억원"
    assert fmt.format_assets_delta(-170) == "-170억원"


def test_percent_and_pp_format():
    assert fmt.format_percent(43.34) == "43.3%"
    assert fmt.format_percent(43.0) == "43.0%"
    assert fmt.format_signed_percent(11.0) == "+11.0%"
    assert fmt.format_signed_percent(-2.4) == "-2.4%"
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
    charts = (
        callbacks.build_trend_figure(dataset, dataset.branch_names[0]),
        callbacks.build_scatter_figure(dataset),
        callbacks.build_age_figure(dataset, dataset.branch_names[0]),
        callbacks.build_investment_figure(dataset),
    )
    for figure in charts:
        hover = figure.layout.hoverlabel
        assert hover.bgcolor == figures.COLOR_SURFACE
        assert hover.font.color == figures.COLOR_TEXT


def test_zoom_is_handled_by_plotly_not_by_a_callback(dataset):
    """확대·축소는 Plotly가 브라우저에서 처리해야 정적 HTML에서도 동작한다.

    Dash 콜백으로 만들면 서버가 없는 정적 HTML에서 눌러도 아무 일이 없다.
    """
    config = figures.ZOOMABLE_CONFIG
    assert config["displayModeBar"] is True
    buttons = config["modeBarButtons"][0]
    for name in ("zoomIn2d", "zoomOut2d", "resetScale2d"):
        assert name in buttons
    assert "toImage" not in buttons
    # 확대한 뒤 드래그로 옮겨 볼 수 있어야 한다.
    scatter = callbacks.build_scatter_figure(dataset)
    assert scatter.layout.dragmode == "pan"


def test_only_the_scatter_chart_allows_zooming():
    """나머지 차트는 기존 설정 그대로 둔다."""
    assert figures.PLOTLY_CONFIG["displayModeBar"] is False
    assert "modeBarButtons" not in figures.PLOTLY_CONFIG
    assert figures.base_layout()["dragmode"] is False


def test_plotly_config_hides_logo():
    assert figures.PLOTLY_CONFIG["displaylogo"] is False
    assert figures.PLOTLY_CONFIG["responsive"] is True


# --- 그리드 -----------------------------------------------------------------
def test_column_defs_order_and_formatters():
    column_defs = grid.build_column_defs()
    assert [column["headerName"] for column in column_defs] == [
        "지점명",
        "고객 수",
        "고객 수 증가율(YoY)",
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
    column_defs = grid.build_column_defs()
    pinned = column_defs[0]
    assert pinned["field"] == grid.PINNED_FIELD
    assert pinned["pinned"] == "left"
    # 고정 컬럼은 flex 계산에서 빠진다. flex가 남으면 너비가 0으로 접힌다.
    assert pinned["flex"] == 0
    assert pinned["width"] == grid.PINNED_WIDTH
    assert all("pinned" not in column for column in column_defs[1:])


def test_column_defs_alignment_classes():
    """정렬은 CSS 클래스로만 정한다.

    ag-grid의 `type`을 쓰면 그 타입이 넣는 headerClass·cellClass가
    아래 클래스와 서로 덮어써서 헤더와 셀의 정렬이 어긋난다.
    """
    column_defs = grid.build_column_defs()
    assert all("type" not in column for column in column_defs)
    assert column_defs[0]["cellClass"] == "grid-cell-text"
    assert all(column["cellClass"] == "grid-cell-number" for column in column_defs[1:])
    assert grid.DEFAULT_COL_DEF["headerClass"] == "grid-header"


def test_row_data_keeps_numbers_for_sorting(dataset):
    total_row, branch_rows = metrics.branch_table(dataset.monthly, dataset.summary)
    rows = grid.build_row_data(branch_rows)
    assert len(rows) == BRANCH_COUNT
    assert isinstance(rows[0]["customer_count"], int)
    assert isinstance(rows[0]["male_share"], float)
    pinned = grid.build_pinned_top_row(total_row)
    assert len(pinned) == 1
    assert pinned[0]["branch_name"] == TOTAL_LABEL


def test_grid_options_pin_total_row(dataset):
    total_row, _ = metrics.branch_table(dataset.monthly, dataset.summary)
    options = grid.build_grid_options(total_row)
    assert options["pinnedTopRowData"][0]["branch_name"] == TOTAL_LABEL


def test_grid_handles_empty_input():
    assert grid.build_row_data(pd.DataFrame()) == []
    assert grid.build_pinned_top_row(None) == []
    assert grid.build_grid_options(None)["pinnedTopRowData"] == []


# --- 앱 조립 ----------------------------------------------------------------
def test_initial_view_and_layout_build(dataset):
    import app as app_module

    view = app_module.build_initial_view(dataset)
    assert set(view) >= {
        "kpis",
        "branch_names",
        "default_branch",
        "trend_figure",
        "scatter_figure",
        "age_figure",
        "investment_figure",
        "column_defs",
        "row_data",
        "grid_options",
    }
    assert len(view["branch_names"]) == BRANCH_COUNT
    assert app_module.app.layout is not None


def test_view_carries_reference_months_and_branch_count(dataset):
    """레이아웃이 상수를 직접 읽지 않도록 기준 월·지점 수를 view로 내려보낸다."""
    import app as app_module

    view = app_module.build_initial_view(dataset)
    assert view["current_month"] == dataset.months[-1]
    assert view["previous_month"] == shift_month(view["current_month"], -1)
    assert view["branch_count"] == BRANCH_COUNT


def test_screen_text_follows_the_data():
    """데이터 기간·지점 수가 달라지면 화면 문구도 따라간다.

    예전에는 기준 월과 '27개 지점'이 문자열로 박혀 있어 데이터가 바뀌어도
    옛 값을 그대로 보여줬다(회귀 방지).
    """
    import app as app_module
    from dashboard import layout as layout_module

    full = load_dashboard_data()
    trimmed = load_dashboard_data(
        filters={
            "base_months": [month for month in full.months if month <= "2026-03"],
            "branch_names": full.branch_names[:5],
        }
    )
    view = app_module.build_initial_view(trimmed)

    subtitle = layout_module._page_header(view).children[1].children
    assert "2026년 3월" in subtitle
    assert "2026년 2월" in subtitle
    assert "2026년 7월" not in subtitle

    table_description = layout_module._table_card(view).children[0].children[1].children
    assert "5행" in table_description
    assert "27행" not in table_description

    hover = view["scatter_figure"].data[0].hovertemplate
    assert "2026년 3월" in hover and "2025년 3월" in hover
    assert "2026년 7월" not in hover


def test_callback_ids_are_registered():
    import app as app_module
    from dashboard import layout as layout_module

    registered = "\n".join(app_module.app.callback_map.keys())
    for output_id in (
        layout_module.ID_TREND_CHART,
        layout_module.ID_AGE_CHART,
        layout_module.ID_INVESTMENT_CHART,
    ):
        assert output_id in registered
