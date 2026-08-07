"""레이아웃과 재사용 UI 컴포넌트.

데이터를 직접 읽지 않는다. 계산이 끝난 값(`view`)을 받아 화면만 구성한다.
"""

from __future__ import annotations

import dash_ag_grid as dag
from dash import dcc, html

from dashboard import format as fmt
from dashboard import grid
from dashboard.data import (
    EXCLUDED_AGE_GROUPS,
    EXCLUDED_INVESTMENT_TYPES,
    TOTAL_LABEL,
)
from dashboard.figures import PLOTLY_CONFIG, ZOOMABLE_CONFIG

PAGE_TITLE = "지점 공통고객 현황"

# 투자성향 차트에서 빼는 분류를 알리는 문구. 데이터 계층이 정한 목록에서 만들어
# 두 곳이 어긋나지 않게 한다.
EXCLUDED_INVESTMENT_NOTE = (
    f"{', '.join(EXCLUDED_INVESTMENT_TYPES)} 제외"
    if EXCLUDED_INVESTMENT_TYPES
    else ""
)
# 연령 분포에서 빼는 구간(연령 미선택)을 알리는 문구.
EXCLUDED_AGE_NOTE = (
    f"{', '.join(EXCLUDED_AGE_GROUPS)} 제외" if EXCLUDED_AGE_GROUPS else ""
)
# 확대·축소가 있는 차트의 조작 안내. 오른쪽 위 아이콘만으로는 무엇을 할 수
# 있는지 알기 어렵다. 아이콘 모양(⌂ 같은 기호)은 글꼴에 없으면 네모로
# 깨지므로 문구에 넣지 않고 동작으로만 적는다.
ZOOM_GUIDE = "휠 확대·축소 · 드래그 이동 · 더블클릭 전체 보기"
# 표의 조작 안내. 켜 둔 기능만 적는다(→ grid.DEFAULT_COL_DEF).
# 컬럼 이동은 막아 두었으므로 넣지 않는다.
TABLE_GUIDE = "헤더 클릭 정렬 · 경계 드래그로 너비 조절"

# 4개 차트 카드의 그래프 높이를 동일하게 유지한다.
CHART_HEIGHT = "360px"

# 드롭다운 목록 패널의 최대 높이(px). dcc.Dropdown의 maxHeight로만 지정한다.
DROPDOWN_MAX_HEIGHT = 280

# 컴포넌트 ID
ID_MAIN_TABS = "dashboard-tabs"
ID_TREND_BRANCH_SELECT = "customer-trend-branch-select"
ID_TREND_CHART = "customer-trend-chart"
ID_SCATTER_CHART = "growth-scatter-chart"
ID_AGE_BRANCH_SELECT = "age-distribution-branch-select"
ID_AGE_CHART = "age-distribution-chart"
ID_INVESTMENT_SCOPE_SELECT = "investment-scope-select"
ID_INVESTMENT_CHART = "investment-chart"
ID_BRANCH_TABLE = "branch-customer-grid"

TAB_CUSTOMER = "customer"
# 이번 단계에서는 고객 탭만 구현하고 나머지는 이름만 표시한다.
_OTHER_TABS = (
    ("asset", "자산"),
    ("product", "상품"),
    ("transaction", "거래"),
    ("return", "수익률"),
    ("app", "앱 이용"),
    ("consulting", "상담"),
)

_KPI_CARDS = (
    ("customer_count", "고객 수", fmt.format_count, fmt.format_count_delta),
    ("total_assets", "총자산", fmt.format_assets, fmt.format_assets_delta),
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
                value=TAB_CUSTOMER,
                className="tab-bar",
                parent_className="tab-parent",
                children=[
                    dcc.Tab(
                        label="고객",
                        value=TAB_CUSTOMER,
                        className="tab",
                        selected_className="tab--selected",
                        children=_customer_tab(view),
                    ),
                    *[
                        dcc.Tab(
                            label=label,
                            value=value,
                            className="tab",
                            selected_className="tab--selected",
                            disabled=True,
                            disabled_className="tab--disabled",
                        )
                        for value, label in _OTHER_TABS
                    ],
                ],
            ),
        ],
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
            for key, label, value_formatter, delta_formatter in _KPI_CARDS
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
                f"전월 대비 {delta_formatter(delta)}",
                className=f"kpi-delta {_delta_class(delta)}",
            ),
        ],
    )


def _delta_class(delta: object) -> str:
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


def _customer_tab(view: dict) -> html.Div:
    branch_options = view["branch_names"]
    default_branch = view["default_branch"]
    # Dash가 탭 콘텐츠 래퍼에 "tab-content"를 붙이므로 다른 이름을 쓴다.
    # 같은 이름이면 여백이 두 번 적용된다.
    return html.Div(
        className="tab-panel",
        children=[
            html.Section(
                className="chart-grid",
                children=[
                    _chart_card(
                        title="고객 추이",
                        chart_id=ID_TREND_CHART,
                        figure=view["trend_figure"],
                        control=_branch_dropdown(
                            ID_TREND_BRANCH_SELECT,
                            branch_options,
                            default_branch,
                        ),
                    ),
                    _chart_card(
                        title="고객 수 및 성장률",
                        chart_id=ID_SCATTER_CHART,
                        figure=view["scatter_figure"],
                        # 점이 몰린 구간을 들여다볼 수 있게 확대·축소를
                        # 켠다. Dash 콜백이 아니라 Plotly가 처리하므로
                        # 정적 HTML에서도 똑같이 동작한다.
                        config=ZOOMABLE_CONFIG,
                        description=(
                            f"{fmt.format_month(view['current_month'])} 기준 "
                            f"{view['branch_count']}개 지점"
                        ),
                        note=ZOOM_GUIDE,
                    ),
                    _chart_card(
                        title="연령별 고객 분포",
                        chart_id=ID_AGE_CHART,
                        figure=view["age_figure"],
                        control=_branch_dropdown(
                            ID_AGE_BRANCH_SELECT,
                            branch_options,
                            default_branch,
                        ),
                        # 연령 미선택 고객은 원본 '합계'에 없어 비중 분모에도
                        # 없다. 빼고 그린다는 걸 화면에 적어 둔다.
                        note=EXCLUDED_AGE_NOTE,
                    ),
                    _chart_card(
                        title="투자성향",
                        chart_id=ID_INVESTMENT_CHART,
                        figure=view["investment_figure"],
                        control=_branch_dropdown(
                            ID_INVESTMENT_SCOPE_SELECT,
                            [TOTAL_LABEL, *branch_options],
                            TOTAL_LABEL,
                        ),
                        # 제외한 분류가 있으면 합계가 고객 수보다 적다.
                        # 이유를 적어 두지 않으면 다른 카드의 숫자와
                        # 안 맞는 것처럼 보인다.
                        note=EXCLUDED_INVESTMENT_NOTE,
                    ),
                ],
            ),
            _table_card(view),
        ],
    )


def _chart_card(
    title: str,
    chart_id: str,
    figure,
    control: html.Div | None = None,
    description: str | None = None,
    note: str | None = None,
    config: dict | None = None,
) -> html.Section:
    """차트 카드. 제목은 왼쪽, 선택 컨트롤은 오른쪽에 두고 그래프와 분리한다.

    `note`는 컨트롤 아래에 작게 붙는 보조 문구다. 선택 컨트롤이 있는 카드에도
    데이터 범위를 알려야 할 때 쓴다.
    `config`를 주면 그 차트만 다른 Plotly 설정을 쓴다(예: 확대·축소 허용).
    """
    header_right = (
        control
        if control is not None
        else html.Span(description or "", className="card-description")
    )
    if note:
        header_right = html.Div(
            className="card-header-right",
            children=[header_right, html.Span(note, className="card-note")],
        )
    return html.Section(
        className="card",
        children=[
            html.Header(
                className="card-header",
                children=[
                    html.H2(title, className="card-title"),
                    header_right,
                ],
            ),
            html.Div(
                className="card-body",
                children=dcc.Graph(
                    id=chart_id,
                    figure=figure,
                    config=config or PLOTLY_CONFIG,
                    className="chart",
                    style={"height": CHART_HEIGHT, "width": "100%"},
                ),
            ),
        ],
    )


def _branch_dropdown(
    component_id: str, options: list[str], value: str
) -> html.Div:
    """지점 선택 드롭다운.

    목록 높이는 CSS가 아니라 `maxHeight`로 지정한다. 이 값이 목록 패널의
    스크롤 영역을 결정하므로, CSS에서 다시 제한하면 스크롤바가 두 개가 된다.
    """
    return html.Div(
        className="card-control",
        children=dcc.Dropdown(
            id=component_id,
            options=[{"label": option, "value": option} for option in options],
            value=value,
            clearable=False,
            searchable=False,
            maxHeight=DROPDOWN_MAX_HEIGHT,
            className="dropdown",
        ),
    )


def _table_card(view: dict) -> html.Section:
    return html.Section(
        className="card card--table",
        children=[
            html.Header(
                className="card-header",
                children=[
                    html.H2("지점별 고객 현황", className="card-title"),
                    html.Div(
                        className="card-header-right",
                        children=[
                            html.Span(
                                f"{fmt.format_month(view['current_month'])}"
                                " 기준 · 전체 1행과 지점 "
                                f"{view['branch_count']}행",
                                className="card-description",
                            ),
                            html.Span(
                                TABLE_GUIDE, className="card-note"
                            ),
                        ],
                    ),
                ],
            ),
            html.Div(
                className="card-body",
                children=dag.AgGrid(
                    id=ID_BRANCH_TABLE,
                    columnDefs=view["column_defs"],
                    rowData=view["row_data"],
                    defaultColDef=grid.DEFAULT_COL_DEF,
                    dashGridOptions=view["grid_options"],
                    # ag-grid 35는 Theming API를 쓰며 ag-theme-* 클래스를
                    # 실행 중 지우므로 넣지 않는다.
                    # 색은 assets/style.css의 --ag-* 변수로 맞춘다.
                    className="dashboard-grid",
                    style={"height": "480px", "width": "100%"},
                ),
            ),
        ],
    )
