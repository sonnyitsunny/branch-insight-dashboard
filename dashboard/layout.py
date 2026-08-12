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
    PLACE_AXIS_X,
    Chart,
    Select,
    Tab,
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
    (
        "customer_count",
        "공통고객 수",
        fmt.format_count,
        fmt.format_count_delta,
    ),
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
    if tab.selects:
        children.append(_tab_controls(tab, tab_view["selects"]))
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
    children.extend(
        _table_card(card) for card in tab_view.get("tables", [])
    )
    return html.Div(className="tab-panel", children=children)


def _tab_controls(tab: Tab, selects: dict) -> html.Div:
    """탭 전체에 걸리는 선택 줄. 그 탭의 표가 모두 같은 값을 받는다."""
    return html.Div(
        className="tab-controls",
        children=[
            _dropdown(
                tab.select_id(select.key),
                selects["options"].get(select.key, []),
                selects["values"].get(select.key, ""),
                select.label,
            )
            for select in tab.selects
        ],
    )


def axis_control_class(select: Select) -> str:
    """축 옆에 겹쳐 그리는 컨트롤의 CSS 클래스.

    화면과 정적 HTML이 같은 이름을 쓰도록 여기서 한 번만 만든다
    (→ export_html). 자리와 크기는 `assets/style.css`가 정한다.
    """
    side = "x" if select.place == PLACE_AXIS_X else "y"
    return f"chart-axis-control chart-axis-control--{side}"


def _chart_card(tab: Tab, chart: Chart, card: dict) -> html.Section:
    """차트 카드. 제목은 왼쪽, 선택 컨트롤은 오른쪽에 두고 그래프와 분리한다.

    헤더 컨트롤이 있으면 순서대로, 없으면 보조 문구를 오른쪽에 둔다.
    `note`는 그 아래에 작게 붙는 안내 문구다.

    축을 고르는 컨트롤(`place=axis-*`)은 헤더가 아니라 그래프 위 그 축
    옆에 겹쳐 그린다.
    """
    if chart.header_selects:
        header_right = html.Div(
            className="card-controls",
            children=[
                _control(tab, chart, select, card)
                for select in chart.header_selects
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
                className=_body_class(chart),
                children=[
                    dcc.Graph(
                        id=chart.chart_id(tab.value),
                        figure=card["figure"],
                        config=figures.chart_config(chart.zoomable),
                        className="chart",
                        style={"height": CHART_HEIGHT, "width": "100%"},
                    ),
                    *[
                        _control(
                            tab,
                            chart,
                            select,
                            card,
                            axis_control_class(select),
                        )
                        for select in chart.axis_selects
                    ],
                ],
            ),
        ],
    )


def _body_class(chart: Chart) -> str:
    """카드 본문의 클래스.

    축 옆 컨트롤은 그래프 위에 겹쳐 놓으므로 본문이 기준 자리가 되어야
    한다. 그 차트에서만 `chart-canvas`를 더한다.
    """
    if chart.axis_selects:
        return "card-body chart-canvas"
    return "card-body"


def _control(
    tab: Tab,
    chart: Chart,
    select: Select,
    card: dict,
    class_name: str = "",
):
    """선택 컨트롤 하나. 값이 적으면 라디오, 많으면 드롭다운으로 선언한다.

    `class_name`은 자리를 정하는 클래스다. 헤더에 두는 컨트롤은 비운다.
    """
    component_id = chart.select_id(tab.value, select.key)
    options = card["options"].get(select.key, [])
    value = card["values"].get(select.key, "")
    if select.kind == KIND_RADIO:
        return _radio(component_id, options, value, class_name)
    return _dropdown(component_id, options, value, select.label, class_name)


def _control_class(*names: str) -> str:
    """컨트롤 바깥 상자의 클래스. 빈 이름은 버린다."""
    return " ".join(name for name in ("card-control", *names) if name)


def _dropdown(
    component_id: str,
    options: list[str],
    value: str,
    label: str = "",
    class_name: str = "",
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
    return html.Div(
        className=_control_class(class_name), children=children
    )


def _radio(
    component_id: str,
    options: list[str],
    value: str,
    class_name: str = "",
) -> html.Div:
    """값이 두세 개뿐인 선택. 펼치지 않고 바로 보이게 라디오로 그린다."""
    return html.Div(
        className=_control_class("card-control--radio", class_name),
        children=dcc.RadioItems(
            id=component_id,
            options=[{"label": option, "value": option} for option in options],
            value=value,
            className="radio-group",
            inputClassName="radio-input",
            labelClassName="radio-label",
        ),
    )


def _table_card(card: dict) -> html.Section:
    """표 카드 하나.

    무엇을 그릴지 여기서 정하지 않는다. 제목·ID·행까지 모두 계산이 끝난
    값(`card`)으로 받는다. 표가 몇 개인지는 데이터가 정한다(→ callbacks).
    """
    return html.Section(
        className="card card--table",
        children=[
            html.Header(
                className="card-header",
                children=[
                    html.H2(card["title"], className="card-title"),
                    html.Div(
                        className="card-header-right",
                        children=[
                            html.Span(
                                card.get("description", ""),
                                className="card-description",
                            ),
                            html.Span(
                                card.get("guide", ""), className="card-note"
                            ),
                        ],
                    ),
                ],
            ),
            html.Div(
                className="card-body",
                children=dag.AgGrid(
                    id=card["table_id"],
                    columnDefs=card["column_defs"],
                    rowData=card["row_data"],
                    defaultColDef=grid.DEFAULT_COL_DEF,
                    dashGridOptions=card["grid_options"],
                    # ag-grid 35는 Theming API를 쓴다.
                    # 예전 테마 클래스는 실행 중 지워지므로
                    # 넣지 않는다. 색은 style.css에서 맞춘다.
                    className="dashboard-grid",
                    style=table_style(card.get("auto_height", False)),
                ),
            ),
        ],
    )


def table_style(auto_height: bool) -> dict:
    """표 바깥 상자의 크기.

    행이 늘 몇 개뿐인 표는 높이를 내용에 맞춘다. 고정 높이를 주면 아래가
    빈 채로 남는다. 그때 높이는 ag-grid가 정하므로 여기서 적지 않는다.
    """
    if auto_height:
        return {"width": "100%"}
    return {"height": TABLE_HEIGHT, "width": "100%"}
