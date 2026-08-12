"""레이아웃과 재사용 UI 컴포넌트.

데이터를 직접 읽지 않는다. 계산이 끝난 값(`view`)을 받아 화면만 구성한다.
어떤 탭에 어떤 카드가 있는지도 여기 적지 않는다. 탭 등록표를 돌면서
선언대로 그린다(→ dashboard.tabs).
"""

from __future__ import annotations

import dash_ag_grid as dag
from dash import dcc, html

from dashboard import figures, grid
from dashboard import format as fmt
from dashboard import tabs as tab_registry
from dashboard.tabs.registry import (
    KIND_RADIO,
    Chart,
    Select,
    Tab,
    Table,
)

PAGE_TITLE = "지점 공통고객 현황"

# 4개 차트 카드의 그래프 높이를 동일하게 유지한다.
CHART_HEIGHT = "360px"

# 지점 표의 높이. 이 안에서 세로로 스크롤한다. 정적 HTML 표도 같은 값을 써서
# 두 산출물의 높이가 같게 한다(→ export_html).
TABLE_HEIGHT = "480px"

# 드롭다운 목록 패널의 최대 높이(px). dcc.Dropdown의 maxHeight로만 지정한다.
DROPDOWN_MAX_HEIGHT = 280

# 컴포넌트 ID. 차트·표 ID는 탭 선언에서 만든다(→ tabs.registry).
ID_MAIN_TABS = "dashboard-tabs"

KPI_CARDS = (
    ("customer_count", "고객 수", fmt.format_count, fmt.format_count_delta),
    ("net_assets", "순자산", fmt.format_assets, fmt.format_assets_delta),
    (
        "transaction_share",
        "거래고객 비중",
        fmt.format_percent,
        fmt.format_pp_delta,
    ),
    ("app_share", "앱 이용 비중", fmt.format_percent, fmt.format_pp_delta),
)


def create_layout(view: dict) -> html.Div:
    """페이지 전체 레이아웃."""
    return html.Div(
        className="page",
        children=[
            _page_header(view),
            _kpi_row(view["kpis"]),
            dcc.Tabs(
                id=ID_MAIN_TABS,
                value=tab_registry.default_value(),
                className="tab-bar",
                parent_className="tab-parent",
                children=[
                    _tab(value, label, view)
                    for value, label in tab_registry.TAB_ORDER
                ],
            ),
        ],
    )


def _tab(value: str, label: str, view: dict) -> dcc.Tab:
    """탭 하나. 구현하지 않은 탭은 이름만 비활성으로 보여준다."""
    tab = tab_registry.find(value)
    if tab is None:
        return dcc.Tab(
            label=label,
            value=value,
            className="tab",
            selected_className="tab--selected",
            disabled=True,
            disabled_className="tab--disabled",
        )
    return dcc.Tab(
        label=label,
        value=value,
        className="tab",
        selected_className="tab--selected",
        children=_tab_panel(tab, view["tabs"][value]),
    )


def _page_header(view: dict) -> html.Header:
    """제목 영역. 기준 월은 상수가 아니라 데이터에서 온 값을 쓴다."""
    return html.Header(
        className="page-header",
        children=[
            html.H1(PAGE_TITLE, className="page-title"),
            html.P(
                f"기준 월 {fmt.format_month(view['current_month'])} · "
                f"전월 비교 {fmt.format_month(view['previous_month'])}",
                className="page-subtitle",
            ),
        ],
    )


def _kpi_row(kpis: dict) -> html.Section:
    """상단 KPI 카드. 전체 지점 합산 기준이며 지점 선택과 연결하지 않는다."""
    return html.Section(
        className="kpi-row",
        children=[
            _kpi_card(
                label, kpis.get(key, {}), value_formatter, delta_formatter
            )
            for key, label, value_formatter, delta_formatter in KPI_CARDS
        ],
    )


def _kpi_card(
    label: str, metric: dict, value_formatter, delta_formatter
) -> html.Div:
    value = metric.get("value")
    delta = metric.get("delta")
    return html.Div(
        className="kpi-card",
        children=[
            html.P(label, className="kpi-label"),
            html.P(value_formatter(value), className="kpi-value"),
            html.P(
                delta_text(metric, delta_formatter),
                className=f"kpi-delta {delta_class(delta)}",
            ),
        ],
    )


def delta_text(metric: dict, delta_formatter) -> str:
    """카드 보조 문구: 전월 대비 +317명 (+0.4%)

    증감률은 전월 값이 없거나 0이면 계산할 수 없다. 그때는 괄호를 붙이지
    않는다. 없는 값을 0%로 적으면 "변화 없음"으로 읽힌다.

    화면과 정적 HTML이 같은 문구를 쓰도록 여기서 한 번만 만든다.
    """
    text = f"전월 대비 {delta_formatter(metric.get('delta'))}"
    rate = fmt.format_signed_percent(metric.get("rate"))
    if rate == fmt.EMPTY_TEXT:
        return text
    return f"{text} ({rate})"


def delta_class(delta: object) -> str:
    """증감 방향 클래스.

    문구에 +/- 기호가 함께 나오므로 색상만으로 구분하지 않는다.
    """
    try:
        number = float(delta)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return "kpi-delta--flat"
    if number > 0:
        return "kpi-delta--up"
    if number < 0:
        return "kpi-delta--down"
    return "kpi-delta--flat"


def _tab_panel(tab: Tab, tab_view: dict) -> html.Div:
    """탭 하나의 내용. 차트 그리드와 표를 선언 순서대로 쌓는다."""
    # Dash가 탭 콘텐츠 래퍼에 "tab-content"를 붙이므로 다른 이름을 쓴다.
    # 같은 이름이면 여백이 두 번 적용된다.
    children: list = []
    if tab.charts:
        children.append(
            html.Section(
                className="chart-grid",
                children=[
                    _chart_card(tab, chart, tab_view["charts"][chart.key])
                    for chart in tab.charts
                ],
            )
        )
    if tab.table is not None:
        children.append(_table_card(tab, tab.table, tab_view["table"]))
    return html.Div(className="tab-panel", children=children)


def _chart_card(tab: Tab, chart: Chart, card: dict) -> html.Section:
    """차트 카드. 제목은 왼쪽, 선택 컨트롤은 오른쪽에 두고 그래프와 분리한다.

    선언에 `selects`가 있으면 컨트롤을 순서대로, 없으면 보조 문구를
    오른쪽에 둔다. `note`는 그 아래에 작게 붙는 안내 문구다.
    """
    if chart.selects:
        header_right = html.Div(
            className="card-controls",
            children=[
                _control(tab, chart, select, card)
                for select in chart.selects
            ],
        )
    else:
        header_right = html.Span(
            card.get("description", ""), className="card-description"
        )
    if chart.note:
        header_right = html.Div(
            className="card-header-right",
            children=[
                header_right,
                html.Span(chart.note, className="card-note"),
            ],
        )
    return html.Section(
        className="card",
        children=[
            html.Header(
                className="card-header",
                children=[
                    html.H2(chart.title, className="card-title"),
                    header_right,
                ],
            ),
            html.Div(
                className="card-body",
                children=dcc.Graph(
                    id=chart.chart_id(tab.value),
                    figure=card["figure"],
                    config=figures.chart_config(chart.zoomable),
                    className="chart",
                    style={"height": CHART_HEIGHT, "width": "100%"},
                ),
            ),
        ],
    )


def _control(tab: Tab, chart: Chart, select: Select, card: dict):
    """선택 컨트롤 하나. 값이 적으면 라디오, 많으면 드롭다운으로 선언한다."""
    component_id = chart.select_id(tab.value, select.key)
    options = card["options"].get(select.key, [])
    value = card["values"].get(select.key, "")
    if select.kind == KIND_RADIO:
        return _radio(component_id, options, value)
    return _dropdown(component_id, options, value, select.label)


def _dropdown(
    component_id: str,
    options: list[str],
    value: str,
    label: str = "",
) -> html.Div:
    """선택 드롭다운.

    목록 높이는 CSS가 아니라 `maxHeight`로 지정한다. 이 값이 목록 패널의
    스크롤 영역을 결정하므로, CSS에서 다시 제한하면 스크롤바가 두 개가 된다.

    컨트롤이 둘 이상이면 무엇을 고르는 칸인지 라벨을 붙인다. 하나뿐이면
    붙이지 않는다 — 카드 제목이 이미 그 역할을 한다.
    """
    children: list = []
    if label:
        children.append(html.Span(label, className="control-label"))
    children.append(
        dcc.Dropdown(
            id=component_id,
            options=[{"label": option, "value": option} for option in options],
            value=value,
            clearable=False,
            searchable=False,
            maxHeight=DROPDOWN_MAX_HEIGHT,
            className="dropdown",
        )
    )
    return html.Div(className="card-control", children=children)


def _radio(component_id: str, options: list[str], value: str) -> html.Div:
    """값이 두세 개뿐인 선택. 펼치지 않고 바로 보이게 라디오로 그린다."""
    return html.Div(
        className="card-control card-control--radio",
        children=dcc.RadioItems(
            id=component_id,
            options=[{"label": option, "value": option} for option in options],
            value=value,
            className="radio-group",
            inputClassName="radio-input",
            labelClassName="radio-label",
        ),
    )


def _table_card(tab: Tab, table: Table, card: dict) -> html.Section:
    return html.Section(
        className="card card--table",
        children=[
            html.Header(
                className="card-header",
                children=[
                    html.H2(table.title, className="card-title"),
                    html.Div(
                        className="card-header-right",
                        children=[
                            html.Span(
                                card.get("description", ""),
                                className="card-description",
                            ),
                            html.Span(
                                table.guide, className="card-note"
                            ),
                        ],
                    ),
                ],
            ),
            html.Div(
                className="card-body",
                children=dag.AgGrid(
                    id=table.table_id(tab.value),
                    columnDefs=card["column_defs"],
                    rowData=card["row_data"],
                    defaultColDef=grid.DEFAULT_COL_DEF,
                    dashGridOptions=card["grid_options"],
                    # ag-grid 35는 Theming API를 쓰며 ag-theme-* 클래스를
                    # 실행 중 지우므로 넣지 않는다.
                    # 색은 assets/style.css의 --ag-* 변수로 맞춘다.
                    className="dashboard-grid",
                    style={"height": TABLE_HEIGHT, "width": "100%"},
                ),
            ),
        ],
    )
