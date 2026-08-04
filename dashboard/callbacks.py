"""콜백 등록.

콜백은 파일이나 데이터베이스를 직접 읽지 않고, 데이터 소스 종류도 판별하지 않는다.
데이터는 앱 생성 시 주입받고, 계산은 `metrics`, 그림은 `figures`에 맡긴다.
"""

from __future__ import annotations

from dash import Dash, Input, Output

from dashboard import figures, layout, metrics
from dashboard.data import (
    YOY_MONTHS,
    DashboardData,
    TOTAL_LABEL,
    reference_month,
    shift_month,
)


def register_callbacks(app: Dash, data: DashboardData) -> None:
    """고객 탭의 선택 컨트롤 3개를 각각 처리한다."""

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
    trend = metrics.customer_trend(data.monthly, branch_name)
    return figures.create_customer_trend_figure(trend, branch_name)


def build_scatter_figure(data: DashboardData):
    current_month = reference_month(data)
    base_month = shift_month(current_month, -YOY_MONTHS)
    scatter = metrics.growth_scatter(data.monthly, current_month, base_month)
    return figures.create_growth_scatter_figure(
        scatter,
        metrics.median_customer_count(scatter),
        base_month=base_month,
        current_month=current_month,
    )


def build_age_figure(data: DashboardData, branch_name: str):
    distribution = metrics.age_distribution(data.age, branch_name, reference_month(data))
    return figures.create_age_distribution_figure(distribution, branch_name)


def build_investment_figure(data: DashboardData, scope: str = TOTAL_LABEL):
    breakdown = metrics.investment_breakdown(data.investment, scope, reference_month(data))
    return figures.create_investment_figure(breakdown, scope)
