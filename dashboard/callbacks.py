"""콜백 등록.

콜백은 파일이나 데이터베이스를 직접 읽지 않고, 데이터 소스 종류도
판별하지 않는다.
데이터는 앱 생성 시 주입받고, 계산은 `metrics`, 그림은 `figures`에 맡긴다.
"""

from __future__ import annotations

from dash import Dash, Input, Output

from dashboard import figures, grid, layout, metrics
from dashboard.data import (
    YOY_MONTHS,
    DashboardData,
    TOTAL_LABEL,
    reference_month,
    shift_month,
)


def build_initial_view(data: DashboardData) -> dict:
    """첫 화면에 필요한 값을 모아 준다.

    Dash 화면과 정적 HTML이 같은 값을 보여주도록 두 진입점이 이 함수를
    함께 쓴다. `app.py`에 두면 HTML을 만들 때 Dash 앱까지 만들어야 한다.

    기준 월과 지점 수는 상수가 아니라 데이터에서 구해 `view`로 내려보낸다.
    레이아웃이 상수를 직접 읽으면 실제 데이터로 바꿨을 때 화면 문구만
    옛 값으로 남는다.
    """
    branch_names = data.branch_names
    default_branch = branch_names[0] if branch_names else ""
    current_month = reference_month(data)
    previous_month = shift_month(current_month, -1)
    base_month = shift_month(current_month, -YOY_MONTHS)
    total_row, branch_rows = metrics.branch_table(
        data.monthly,
        data.summary,
        current_month,
        base_month,
        data.summary_total,
    )
    return {
        "kpis": metrics.kpi_metrics(
            data.monthly, current_month, previous_month, data.monthly_total
        ),
        "current_month": current_month,
        "previous_month": previous_month,
        "branch_count": len(branch_names),
        "branch_names": branch_names,
        "default_branch": default_branch,
        "trend_figure": build_trend_figure(data, default_branch),
        "scatter_figure": build_scatter_figure(data),
        "age_figure": build_age_figure(data, default_branch),
        "investment_figure": build_investment_figure(data),
        "column_defs": grid.build_column_defs(),
        "row_data": grid.build_row_data(branch_rows),
        "grid_options": grid.build_grid_options(total_row),
    }


def register_callbacks(app: Dash, data: DashboardData) -> None:
    """고객 탭의 선택 컨트롤 3개를 각각 처리한다.

    산점도의 확대·축소는 콜백으로 두지 않는다. Plotly.js가 브라우저에서
    처리해야 서버 없는 정적 HTML에서도 똑같이 동작한다(→ figures 설정).
    """

    @app.callback(
        Output(layout.ID_TREND_CHART, "figure"),
        Input(layout.ID_TREND_BRANCH_SELECT, "value"),
    )
    def update_customer_trend(branch_name: str):
        return build_trend_figure(data, branch_name)

    @app.callback(
        Output(layout.ID_AGE_CHART, "figure"),
        Input(layout.ID_AGE_BRANCH_SELECT, "value"),
    )
    def update_age_distribution(branch_name: str):
        return build_age_figure(data, branch_name)

    @app.callback(
        Output(layout.ID_INVESTMENT_CHART, "figure"),
        Input(layout.ID_INVESTMENT_SCOPE_SELECT, "value"),
    )
    def update_investment(scope: str):
        return build_investment_figure(data, scope)


# 초기 렌더링과 콜백이 같은 함수를 쓰도록 여기서 한 번만 정의한다.
# 기준 월은 상수로 박지 않고 항상 데이터에서 끌어온다(→ data.reference_month).
def build_trend_figure(data: DashboardData, branch_name: str):
    trend = metrics.customer_trend(
        data.monthly, branch_name, data.monthly_total
    )
    return figures.create_customer_trend_figure(trend, branch_name)


def build_scatter_figure(data: DashboardData):
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


def build_age_figure(data: DashboardData, branch_name: str):
    distribution = metrics.age_distribution(
        data.age, branch_name, reference_month(data), data.age_total
    )
    return figures.create_age_distribution_figure(distribution, branch_name)


def build_investment_figure(data: DashboardData, scope: str = TOTAL_LABEL):
    breakdown = metrics.investment_breakdown(
        data.investment, scope, reference_month(data), data.investment_total
    )
    return figures.create_investment_figure(breakdown, scope)
