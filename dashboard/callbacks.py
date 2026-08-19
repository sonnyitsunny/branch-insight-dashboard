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
from dashboard.tabs.registry import Chart, Tab, variant_key


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
    """탭 하나가 첫 화면에 보여줄 값.

    표는 선언 순서대로 목록으로 담는다. 표를 나누는 선언이면 데이터에 있는
    값마다 하나씩 늘어난다(→ registry.Table.groups).
    """
    selection = tab.defaults(data)
    return {
        "context": tab.build_context(data),
        "charts": {
            chart.key: build_chart_view(
                chart, data, selection if chart.follows_tab else None
            )
            for chart in tab.charts
        },
        "selects": {
            "options": tab.option_map(data),
            "values": selection,
        },
        "tables": build_table_views(tab, data, selection),
    }


def build_table_views(
    tab: Tab, data: DashboardData, selection: dict
) -> list[dict]:
    """탭의 표 목록. 표 하나가 여러 개로 나뉘면 그만큼 늘어난다."""
    views: list[dict] = []
    for table in tab.tables:
        # 원본이 없거나 비어 있으면 나눌 값이 없다. 그래도 표 하나는 그려서
        # 왜 비었는지 화면에 남긴다. 아무것도 없으면 고장인지 데이터가
        # 없는 것인지 구분할 수 없다(→ Table.empty_note).
        for index, group in enumerate(table.groups(data) or [""]):
            views.append(
                build_table_view(
                    table, data, selection, group, index, tab.value
                )
            )
    return views


def build_chart_view(
    chart: Chart, data: DashboardData, tab_selection: dict | None = None
) -> dict:
    """차트 하나의 첫 Figure와 선택 컨트롤별 목록·값.

    `tab_selection`은 탭 전체 선택을 따르는 차트(→ Chart.follows_tab)에만
    넘어온다. 카드에 붙은 컨트롤이 있으면 그 값이 이긴다.
    """
    selection = {**(tab_selection or {}), **chart.defaults(data)}
    return {
        "figure": chart.build(data, selection),
        "options": chart.option_map(data),
        "values": selection,
        "description": (
            chart.description(data) if chart.description else ""
        ),
    }


def build_table_view(
    table,
    data: DashboardData,
    selection: dict | None = None,
    group: str = "",
    index: int = 0,
    tab_value: str = "",
) -> dict:
    """표의 첫 행 데이터와 컬럼 설정.

    `group`이 있으면 그 값의 행만 담고 제목도 그 값으로 바꾼다. 분류 이름을
    선언에 적지 않아도 되도록 데이터에서 온 값을 그대로 쓴다.
    """
    total_row, rows = table.build(data, selection or {})
    rows = table_group_rows(table, rows, group)
    row_data = grid.build_row_data(rows, table.columns)
    return {
        "table_id": table.table_id(tab_value, index),
        "title": group or table.title,
        "guide": table.guide,
        "auto_height": table.auto_height,
        "sortable": table.sortable,
        # 차트와 나란히 그리드에 놓는 표인지(→ registry.Table.place).
        "in_grid": table.in_grid,
        # 컬럼 선언과 지금 고른 조합. 정적 HTML이 표를 다시 그릴 때 쓴다.
        "columns": table.columns,
        "scope_key": variant_key(selection or {}),
        "column_defs": grid.build_column_defs(
            table.columns, table.sortable
        ),
        "row_data": row_data,
        "grid_options": grid.build_grid_options(
            total_row, table.columns, table.auto_height
        ),
        # 원본이 없어 표가 비면 왜 비었는지도 이 문구가 알린다. 무엇을
        # 적을지는 탭 모듈이 정한다(→ AGENTS.md §11).
        "description": (
            table.description(data) if table.description else ""
        ),
    }


def table_group_rows(table, rows, group: str):
    """표를 나누는 선언이면 그 값의 행만 남긴다."""
    if not table.group_field or rows is None or len(rows) == 0:
        return rows
    return rows[rows[table.group_field] == group].reset_index(drop=True)


def register_callbacks(app: Dash, data: DashboardData) -> None:
    """선택 컨트롤이 있는 차트마다 콜백을 하나씩 등록한다.

    차트의 확대·축소는 콜백으로 두지 않는다. Plotly.js가 브라우저에서
    처리해야 서버 없는 정적 HTML에서도 똑같이 동작한다(→ figures 설정).
    """
    for tab in tab_registry.TABS:
        for chart in tab.charts:
            if not chart.selects:
                continue
            _register_chart(app, data, tab, chart)
        if tab.selects and (tab.tables or tab.followers):
            _register_tab_selection(app, data, tab)


def _register_tab_selection(
    app: Dash, data: DashboardData, tab: Tab
) -> None:
    """탭 전체 선택으로 그 탭의 표와 차트를 함께 다시 그리는 콜백.

    표가 몇 개인지는 데이터가 정한다(표를 나누는 선언). 여기서는 첫 화면과
    같은 순서로 ID를 만들어 그 수만큼 Output을 건다.

    차트는 `follows_tab`을 켠 것만 따라온다. 표와 차트를 한 콜백에 묶는
    이유는 둘이 같은 선택을 보고 있어야 하기 때문이다. 콜백을 나누면 한쪽만
    갱신된 순간이 생겨 표와 그림이 다른 지점을 가리킨다.

    콜백 안에서 파일을 읽지 않는다. 데이터는 앱 생성 시 주입받은 것을 쓴다.
    """
    keys = [select.key for select in tab.selects]
    table_ids = [
        view["table_id"]
        for view in build_table_views(tab, data, tab.defaults(data))
    ]
    followers = tab.followers
    if not table_ids and not followers:
        return

    outputs = [Output(table_id, "rowData") for table_id in table_ids]
    outputs += [
        Output(chart.chart_id(tab.value), "figure") for chart in followers
    ]

    @app.callback(
        outputs, [Input(tab.select_id(key), "value") for key in keys]
    )
    def update(*values: str):
        selection = dict(zip(keys, values))
        rows = [
            view["row_data"]
            for view in build_table_views(tab, data, selection)
        ]
        figures = [
            chart.build(data, {**selection, **chart.defaults(data)})
            for chart in followers
        ]
        return rows + figures


def _register_chart(
    app: Dash, data: DashboardData, tab: Tab, chart: Chart
) -> None:
    """차트 하나의 선택 콜백.

    컨트롤이 여럿이면 Input을 그만큼 받아 선택값 묶음으로 넘긴다.
    함수를 따로 둬서 반복문 변수가 콜백 안에 늦게 묶이는 일을 막는다.
    반복문 안에서 바로 정의하면 모든 콜백이 마지막 차트를 그린다.
    """
    keys = [select.key for select in chart.selects]

    @app.callback(
        Output(chart.chart_id(tab.value), "figure"),
        [
            Input(chart.select_id(tab.value, key), "value")
            for key in keys
        ],
    )
    def update(*values: str):
        return chart.build(data, dict(zip(keys, values)))
