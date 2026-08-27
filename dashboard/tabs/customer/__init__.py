"""고객 탭 선언.

이 탭이 무엇을 보여주는지 여기 한 번만 적는다. Dash 화면과 정적 HTML이
이 선언을 함께 읽으므로 제목·선택 목록·안내 문구가 두 곳으로 갈라지지
않는다(→ dashboard.tabs.registry).

계산은 `metrics`, 그림은 `figures`에 있다. 여기서는 둘을 엮어 카드로
선언하기만 한다.
"""

from __future__ import annotations

from dashboard import format as fmt
from dashboard import metrics as shared
from dashboard.data import (
    EXCLUDED_INVESTMENT_TYPES,
    TOTAL_LABEL,
    YOY_MONTHS,
    DashboardData,
    reference_month,
    shift_month,
)
from dashboard.grid import (
    AGE_FORMAT,
    COUNT_FORMAT,
    PERCENT_FORMAT,
    SIGNED_PERCENT_FORMAT,
    Column,
)
from dashboard.tabs.customer import figures, metrics
from dashboard.tabs.registry import Chart, Select, Table, Tab

# 투자성향 차트에서 빼는 분류를 알리는 문구. 데이터 계층이 정한 목록에서
# 만들어 두 곳이 어긋나지 않게 한다.
EXCLUDED_INVESTMENT_NOTE = (
    f"{', '.join(EXCLUDED_INVESTMENT_TYPES)} 제외"
    if EXCLUDED_INVESTMENT_TYPES
    else ""
)
# 확대·축소가 있는 차트의 조작 안내. 오른쪽 위 아이콘만으로는 무엇을 할 수
# 있는지 알기 어렵다. 아이콘 모양(⌂ 같은 기호)은 글꼴에 없으면 네모로
# 깨지므로 문구에 넣지 않고 동작으로만 적는다.
ZOOM_GUIDE = "휠 확대·축소 · 드래그 이동 · 더블클릭 전체 보기"
# 표의 조작 안내. 켜 둔 기능만 적는다(→ grid.DEFAULT_COL_DEF).
# 컬럼 이동은 막아 두었으므로 넣지 않는다.
TABLE_GUIDE = "헤더 클릭 정렬 · 경계 드래그로 너비 조절 · 행 클릭 강조"

# 고정 컬럼은 남는 폭을 나눠 갖지 않으므로 폭을 직접 정한다. 좁으면 지점명이
# 말줄임(…)으로 잘린다. 고정하기 전 flex로 늘어나던 폭이 약 183px이었고,
# 경계선(style.css의 --ag-pinned-column-border)이 셀에서 1px를 가져가므로
# 여유를 더해 잡았다. 지점명이 길어 잘리면 이 값만 키우면 된다.
BRANCH_COLUMN_WIDTH = 192

TABLE_COLUMNS = (
    Column(
        field="branch_name",
        header="지점명",
        min_width=120,
        to_text=str,
        width=BRANCH_COLUMN_WIDTH,
        pinned=True,
    ),
    Column(
        field="customer_count",
        header="공통고객 수",
        min_width=130,
        to_text=fmt.format_count,
        js_format=COUNT_FORMAT,
    ),
    Column(
        field="customer_growth_yoy",
        header="공통고객 수 증가율(YoY)",
        min_width=190,
        to_text=fmt.format_signed_percent,
        js_format=SIGNED_PERCENT_FORMAT,
        growth=True,
    ),
    Column(
        field="male_share",
        header="남성(%)",
        min_width=110,
        to_text=fmt.format_percent,
        js_format=PERCENT_FORMAT,
    ),
    Column(
        field="average_age",
        header="평균 연령",
        min_width=120,
        to_text=fmt.format_age,
        js_format=AGE_FORMAT,
    ),
    Column(
        field="recent_signup_share",
        header="최근 가입 비중(%)",
        min_width=150,
        to_text=fmt.format_percent,
        js_format=PERCENT_FORMAT,
    ),
    Column(
        field="recommendation_share",
        header="투자권유 희망(%)",
        min_width=150,
        to_text=fmt.format_percent,
        js_format=PERCENT_FORMAT,
    ),
    Column(
        field="grade_s_share",
        header="고객등급 S 이상(%)",
        min_width=160,
        to_text=fmt.format_percent,
        js_format=PERCENT_FORMAT,
    ),
)


# --- 선택 목록 ---------------------------------------------------------------
def _branch_names(data: DashboardData) -> list[str]:
    return list(data.branch_names)


def _first_branch(data: DashboardData) -> str:
    names = data.branch_names
    return names[0] if names else ""


def _scopes(data: DashboardData) -> list[str]:
    return [TOTAL_LABEL, *data.branch_names]


def _total_scope(data: DashboardData) -> str:
    return TOTAL_LABEL


# --- Figure 만들기 -----------------------------------------------------------
# 기준 월은 상수로 박지 않고 항상 데이터에서 끌어온다
# (→ data.reference_month).
BRANCH_SELECT = Select(
    key="branch",
    label="지점",
    options=_branch_names,
    default=_first_branch,
)
SCOPE_SELECT = Select(
    key="scope",
    label="구분",
    options=_scopes,
    default=_total_scope,
)


def _trend(data: DashboardData, selection: dict):
    branch_name = selection.get("branch") or ""
    trend = metrics.customer_trend(
        data.monthly, branch_name, data.monthly_total
    )
    return figures.create_customer_trend_figure(trend, branch_name)


def _scatter(data: DashboardData, selection: dict | None = None):
    current_month = reference_month(data)
    base_month = shift_month(current_month, -YOY_MONTHS)
    scatter = metrics.growth_scatter(
        data.monthly, current_month, base_month, data.summary
    )
    return figures.create_growth_scatter_figure(
        scatter,
        metrics.median_customer_count(scatter),
        base_month=base_month,
        current_month=current_month,
    )


def _age(data: DashboardData, selection: dict):
    branch_name = selection.get("branch") or ""
    distribution = metrics.age_distribution(
        data.age, branch_name, reference_month(data), data.age_total
    )
    return figures.create_age_distribution_figure(distribution, branch_name)


def _investment(data: DashboardData, selection: dict):
    scope = selection.get("scope") or TOTAL_LABEL
    breakdown = metrics.investment_breakdown(
        data.investment,
        scope,
        reference_month(data),
        data.investment_total,
    )
    return figures.create_investment_figure(breakdown, scope)


# --- 표 ----------------------------------------------------------------------
def _table_rows(data: DashboardData, _selection: dict | None = None):
    current_month = reference_month(data)
    base_month = shift_month(current_month, -YOY_MONTHS)
    return metrics.branch_table(
        data.monthly,
        data.summary,
        current_month,
        base_month,
        data.summary_total,
    )


# --- 보조 문구 ---------------------------------------------------------------
def _table_text(data: DashboardData) -> str:
    month = fmt.format_month(reference_month(data))
    return f"{month} 기준"


def _context(data: DashboardData) -> dict:
    """탭이 화면에 내려보내는 값. 상수가 아니라 데이터에서 구한다."""
    return {
        "branch_names": list(data.branch_names),
        "branch_count": len(data.branch_names),
    }


TAB = Tab(
    value="customer",
    label="고객",
    build_context=_context,
    charts=(
        Chart(
            key="trend",
            title="고객 월별 추이",
            build=_trend,
            selects=(BRANCH_SELECT,),
        ),
        Chart(
            key="scatter",
            title="지점별 고객 규모 비교분석",
            build=_scatter,
            note=ZOOM_GUIDE,
            # 점이 몰린 구간을 들여다볼 수 있게 확대·축소를 켠다. Dash
            # 콜백이 아니라 Plotly가 처리하므로 정적 HTML에서도 똑같이
            # 동작한다.
            zoomable=True,
        ),
        Chart(
            key="age",
            title="연령별 고객분포",
            build=_age,
            selects=(BRANCH_SELECT,),
        ),
        Chart(
            key="investment",
            title="투자성향 분석",
            build=_investment,
            selects=(SCOPE_SELECT,),
            # 제외한 분류가 있으면 합계가 고객 수보다 적다. 이유를 적어
            # 두지 않으면 다른 카드의 숫자와 안 맞는 것처럼 보인다.
            #
            # 무엇을 세었는지 밝히는 말이라 고르는 칸 밑이 아니라 제목
            # 밑에 둔다. `note`에 두면 오른쪽 컨트롤에 딸린 조작 안내처럼
            # 읽힌다(→ registry.Chart.subtitle, layout.card_heading).
            subtitle=EXCLUDED_INVESTMENT_NOTE,
        ),
    ),
    tables=(
        Table(
            title="지점별 공통고객 현황",
            columns=TABLE_COLUMNS,
            build=_table_rows,
            description=_table_text,
            guide=TABLE_GUIDE,
        ),
    ),
)

__all__ = ["TAB", "TABLE_COLUMNS", "figures", "metrics", "shared"]
