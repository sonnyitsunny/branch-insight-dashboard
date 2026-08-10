"""첫 화면 값 계산과 콜백 등록.

콜백은 파일이나 데이터베이스를 직접 읽지 않고, 데이터 소스 종류도
판별하지 않는다. 데이터는 앱 생성 시 주입받는다.

어떤 차트에 어떤 콜백이 필요한지 여기 적지 않는다. 탭 등록표를 돌면서
선택 컨트롤이 있는 차트마다 하나씩 등록한다(→ dashboard.tabs).
"""

from __future__ import annotations

from dash import Dash, Input, Output

from dashboard import grid, metrics
from dashboard import tabs as tab_registry
from dashboard.data import DashboardData, reference_month, shift_month
from dashboard.tabs.registry import Chart, Tab


def build_initial_view(data: DashboardData) -> dict:
    """첫 화면에 필요한 값을 모아 준다.

    Dash 화면과 정적 HTML이 같은 값을 보여주도록 두 진입점이 이 함수를
    함께 쓴다. `app.py`에 두면 HTML을 만들 때 Dash 앱까지 만들어야 한다.

    기준 월은 상수가 아니라 데이터에서 구해 `view`로 내려보낸다.
    레이아웃이 상수를 직접 읽으면 실제 데이터로 바꿨을 때 화면 문구만
    옛 값으로 남는다.
    """
    current_month = reference_month(data)
    previous_month = shift_month(current_month, -1)
    return {
        "kpis": metrics.kpi_metrics(
            data.monthly, current_month, previous_month, data.monthly_total
        ),
        "current_month": current_month,
        "previous_month": previous_month,
        "tabs": {
            tab.value: build_tab_view(tab, data)
            for tab in tab_registry.TABS
        },
    }


def build_tab_view(tab: Tab, data: DashboardData) -> dict:
    """탭 하나가 첫 화면에 보여줄 값."""
    view: dict = {
        "context": tab.build_context(data),
        "charts": {
            chart.key: build_chart_view(chart, data) for chart in tab.charts
        },
    }
    if tab.table is not None:
        view["table"] = build_table_view(tab.table, data)
    return view


def build_chart_view(chart: Chart, data: DashboardData) -> dict:
    """차트 하나의 첫 Figure와 선택 목록."""
    options = list(chart.options(data)) if chart.options else []
    selected = chart.default(data) if chart.default else None
    if chart.options and selected is None and options:
        selected = options[0]
    return {
        "figure": chart.build(data, selected),
        "options": options,
        "value": selected,
        "description": (
            chart.description(data) if chart.description else ""
        ),
    }


def build_table_view(table, data: DashboardData) -> dict:
    """표의 첫 행 데이터와 컬럼 설정."""
    total_row, rows = table.build(data)
    return {
        "column_defs": grid.build_column_defs(table.columns),
        "row_data": grid.build_row_data(rows, table.columns),
        "grid_options": grid.build_grid_options(total_row, table.columns),
        "description": (
            table.description(data) if table.description else ""
        ),
    }


def register_callbacks(app: Dash, data: DashboardData) -> None:
    """선택 컨트롤이 있는 차트마다 콜백을 하나씩 등록한다.

    차트의 확대·축소는 콜백으로 두지 않는다. Plotly.js가 브라우저에서
    처리해야 서버 없는 정적 HTML에서도 똑같이 동작한다(→ figures 설정).
    """
    for tab in tab_registry.TABS:
        for chart in tab.charts:
            if chart.options is None:
                continue
            _register_chart(app, data, tab, chart)


def _register_chart(
    app: Dash, data: DashboardData, tab: Tab, chart: Chart
) -> None:
    """차트 하나의 선택 콜백.

    함수를 따로 둬서 반복문 변수가 콜백 안에 늦게 묶이는 일을 막는다.
    반복문 안에서 바로 정의하면 모든 콜백이 마지막 차트를 그린다.
    """

    @app.callback(
        Output(chart.chart_id(tab.value), "figure"),
        Input(chart.select_id(tab.value), "value"),
    )
    def update(selected: str):
        return chart.build(data, selected)
