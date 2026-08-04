"""Figure·그리드·포맷·앱 조립 검증."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import pytest

from dashboard import figures, format as fmt, grid, metrics
from dashboard.data import BRANCH_COUNT, INVESTMENT_TYPES, TOTAL_LABEL, load_dashboard_data


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


def test_scatter_figure_uses_log_axis_and_reference_lines(dataset):
    scatter = metrics.growth_scatter(dataset.monthly)
    figure = figures.create_growth_scatter_figure(
        scatter, metrics.median_customer_count(scatter)
    )
    assert figure.layout.xaxis.type == "log"
    assert len(figure.data[0].x) == BRANCH_COUNT
    horizontal = [shape for shape in figure.layout.shapes if shape.y0 == shape.y1 == 0]
    vertical = [shape for shape in figure.layout.shapes if shape.x0 == shape.x1]
    assert horizontal, "YoY 0% 가로 기준선이 있어야 한다"
    assert vertical, "고객 수 중앙값 세로 기준선이 있어야 한다"


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
