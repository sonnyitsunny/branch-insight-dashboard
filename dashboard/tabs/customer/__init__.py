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
    AI_TOPIC_CUSTOMER,
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
from dashboard.tabs.registry import Chart, Insight, Select, Table, Tab

# 투자성향 카드의 제목 아래 줄. 오른쪽 막대는 투자성향이 유효한 고객만
# 분류로 나눈 값이라 그 합이 고객 수보다 적다. 무엇을 센 값인지 적어 두지
# 않으면 다른 카드의 숫자와 안 맞는 것처럼 보인다.
INVESTMENT_SUBTITLE = (
    "우측 그래프는 '투자성향 유효' 고객을 대상으로 집계"
)

# 영업점별 공통고객 현황 표의 제목 아래 줄. "최근 가입 비중(%)" 컬럼이
# 무엇을 센 값인지 헤더 이름만으로는 밝히기 어렵다.
TABLE_SUBTITLE = (
    "최근 가입 비중(%): 최근 1년 동안 신규로 가입한 고객 비중(%)"
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
        header="영업점명",
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
    label="영업점",
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


def _ai_summary(data: DashboardData, scope: str) -> list[str]:
    """그 이름의 AI 요약 줄들. 원본이 없으면 빈 목록이다.

    프레임 하나에 탭별 글이 모여 있어 이 탭의 이름으로 가른다
    (→ data.AI_TOPICS).
    """
    return shared.ai_summary_lines(
        data.ai_summary,
        AI_TOPIC_CUSTOMER,
        scope,
        reference_month(data),
        data.ai_summary_total,
    )


def _investment(data: DashboardData, selection: dict):
    scope = selection.get("scope") or TOTAL_LABEL
    month = reference_month(data)
    breakdown = metrics.investment_breakdown(
        data.investment, scope, month, data.investment_total
    )
    # 진단 상태는 성향 분류가 아니라 지점 요약이 담고 있다
    # (→ data.PROFILE_STATES). 원본에 없으면 빈 프레임이 와서 파이가
    # 빠지고 막대만 그려진다.
    states = metrics.profile_states(
        data.summary, scope, month, data.summary_total
    )
    return figures.create_investment_figure(breakdown, scope, states)


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
    # 왼쪽 칸은 늘 '전체', 오른쪽 칸은 고른 영업점이다. 제목은 여기 적은
    # 이름에 그 이름을 이어 붙여 만든다(→ registry.Insight).
    insight=Insight(
        key="ai",
        build=_ai_summary,
        fixed=_total_scope,
        select=BRANCH_SELECT,
    ),
    charts=(
        Chart(
            key="trend",
            title="고객 월별 추이",
            build=_trend,
            selects=(BRANCH_SELECT,),
        ),
        Chart(
            key="scatter",
            title="영업점별 고객 규모 비교분석",
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
            title="투자성향 분포",
            # 무엇을 센 값인지 밝히는 말이라 고르는 칸 밑이 아니라 제목
            # 밑에 둔다. `note`에 두면 오른쪽 컨트롤에 딸린 조작 안내처럼
            # 읽힌다(→ registry.Chart.subtitle, layout.card_heading).
            subtitle=INVESTMENT_SUBTITLE,
            build=_investment,
            selects=(SCOPE_SELECT,),
        ),
    ),
    tables=(
        Table(
            title="영업점별 공통고객 현황",
            columns=TABLE_COLUMNS,
            build=_table_rows,
            description=_table_text,
            guide=TABLE_GUIDE,
            subtitle=TABLE_SUBTITLE,
        ),
    ),
)

__all__ = ["TAB", "TABLE_COLUMNS", "figures", "metrics", "shared"]
