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
        # 표는 선택 줄마다 그 줄의 선택으로 만든다. 그래야 카드가 들고 가는
        # 조합 키(`scope_key`)가 그 줄의 조합과 맞물린다. 탭 전체 선택으로
        # 만들면 줄이 둘일 때 키에 다른 줄의 값까지 섞여, 정적 HTML이 보여줄
        # 행을 찾지 못한다(→ export_html._table_scopes).
        "tables": [
            view
            for group in tab.select_groups
            for view in build_table_views(
                tab, data, group.defaults(data), group.tables
            )
        ],
    }


def build_table_views(
    tab: Tab,
    data: DashboardData,
    selection: dict,
    tables: tuple | None = None,
) -> list[dict]:
    """탭의 표 목록. 표 하나가 여러 개로 나뉘면 그만큼 늘어난다.

    `tables`를 주면 그 표들만 만든다. 선택 줄이 둘 이상인 탭에서 한 줄이
    움직이는 표만 다시 그릴 때 쓴다(→ registry.Tab.select_groups).
    """
    views: list[dict] = []
    for table in tab.tables if tables is None else tables:
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
        # 카드보다 넓게 그리는 그림의 폭. 칸 수를 데이터가 정하므로 선언이
        # 아니라 여기서 값으로 만든다(→ registry.Chart.scroll_width).
        "scroll_width": (
            chart.scroll_width(data) if chart.scroll_width else ""
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
    # 컬럼 이름이 선택에 따라 달라지는 표가 있다. 어느 쪽이든 여기서 한 번
    # 정하고, 아래는 그 목록만 쓴다(→ registry.Table.columns_of).
    columns = table.columns_of(selection)
    row_data = grid.build_row_data(rows, columns)
    return {
        "table_id": table.table_id(tab_value, index),
        "title": group or table.title,
        "guide": table.guide,
        # 제목 아래 줄. 나뉜 표는 그 분류의 문구를 쓴다
        # (→ registry.Table.group_notes).
        "subtitle": table.subtitle_for(group),
        "auto_height": table.auto_height,
        "sortable": table.sortable,
        # 선언이 적은 높이. 비면 자리에 따른 기본값을 쓴다
        # (→ layout.table_style).
        "height": table.height,
        # 차트와 나란히 그리드에 놓는 표인지(→ registry.Table.place).
        "in_grid": table.in_grid,
        # 어느 선택 줄에 속한 표인지(→ registry.Tab.select_groups).
        "group": table.group,
        # 그리드에서 몇 번째 칸인지(→ registry.grid_order).
        "order": table.order,
        # 컬럼 선언과 지금 고른 조합. 정적 HTML이 표를 다시 그릴 때 쓴다.
        "columns": columns,
        # 선택이 바뀌면 컬럼 이름도 다시 내보내야 하는 표인지.
        "dynamic_columns": table.dynamic_columns,
        "scope_key": variant_key(selection or {}),
        "column_defs": grid.build_column_defs(columns, table.sortable),
        "row_data": row_data,
        "grid_options": grid.build_grid_options(
            total_row, columns, table.auto_height
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
            # 선택 줄을 따르는 차트는 그 줄의 콜백이 함께 그린다. 여기서도
            # 등록하면 같은 Figure에 Output이 둘이 되어 Dash가 멈춘다
            # (→ _register_group_selection).
            if not chart.selects or chart.follows_tab:
                continue
            _register_chart(app, data, tab, chart)
        for group in tab.select_groups:
            if group.selects and (group.tables or group.followers):
                _register_group_selection(app, data, tab, group)


def _register_group_selection(
    app: Dash, data: DashboardData, tab: Tab, group
) -> None:
    """선택 줄 하나로 그 줄의 표와 차트를 함께 다시 그리는 콜백.

    표가 몇 개인지는 데이터가 정한다(표를 나누는 선언). 여기서는 첫 화면과
    같은 순서로 ID를 만들어 그 수만큼 Output을 건다.

    차트는 `follows_tab`을 켠 것만 따라온다. 표와 차트를 한 콜백에 묶는
    이유는 둘이 같은 선택을 보고 있어야 하기 때문이다. 콜백을 나누면 한쪽만
    갱신된 순간이 생겨 표와 그림이 다른 지점을 가리킨다.

    따라오는 차트가 자기 컨트롤도 갖고 있으면 그 값까지 Input으로 받는다.
    그 차트의 Figure는 이 콜백 하나만 그리므로, 줄의 선택을 바꿔도 카드에서
    고른 값이 기본값으로 되돌아가지 않는다(→ register_callbacks).

    줄이 둘 이상인 탭은 줄마다 콜백이 하나씩 생기고, 각자 자기 줄의 표와
    차트만 다시 그린다(→ registry.Tab.select_groups).

    콜백 안에서 파일을 읽지 않는다. 데이터는 앱 생성 시 주입받은 것을 쓴다.
    """
    keys = [select.key for select in group.selects]
    views = build_table_views(
        tab, data, group.defaults(data), group.tables
    )
    table_ids = [view["table_id"] for view in views]
    # 컬럼 이름이 선택에 따라 달라지는 표만 columnDefs도 함께 내보낸다.
    # 모든 표에 걸면 지점을 고를 때마다 컬럼이 새로 만들어져, 손으로
    # 조절해 둔 너비와 정렬이 풀린다(→ registry.Table.columns).
    dynamic_ids = [
        view["table_id"] for view in views if view["dynamic_columns"]
    ]
    followers = group.followers
    if not table_ids and not followers:
        return

    outputs = [Output(table_id, "rowData") for table_id in table_ids]
    outputs += [
        Output(table_id, "columnDefs") for table_id in dynamic_ids
    ]
    outputs += [
        Output(chart.chart_id(tab.value), "figure") for chart in followers
    ]

    # 줄의 컨트롤 뒤에 따라오는 차트의 컨트롤을 차례로 붙인다. 값이 한
    # 묶음으로 들어오므로 차트마다 몇 개씩인지 여기서 세어 둔다.
    chart_keys = [
        [select.key for select in chart.selects] for chart in followers
    ]
    inputs = [Input(group.select_id(key), "value") for key in keys]
    for chart, own in zip(followers, chart_keys):
        inputs += [
            Input(chart.select_id(tab.value, key), "value") for key in own
        ]

    @app.callback(outputs, inputs)
    def update(*values: str):
        selection = dict(zip(keys, values[: len(keys)]))
        drawn = build_table_views(tab, data, selection, group.tables)
        rows = [view["row_data"] for view in drawn]
        column_defs = [
            view["column_defs"]
            for view in drawn
            if view["dynamic_columns"]
        ]
        figures = []
        at = len(keys)
        for chart, own in zip(followers, chart_keys):
            chosen = dict(zip(own, values[at : at + len(own)]))
            at += len(own)
            figures.append(chart.build(data, {**selection, **chosen}))
        return rows + column_defs + figures


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
