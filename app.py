"""Dash 애플리케이션 생성과 실행 진입점.

레이아웃·데이터 로직은 `dashboard` 패키지에 있고, 여기서는 조립만 한다.
프론트엔드 리소스는 로컬에서 제공한다(내부망 실행 전제).
"""

from __future__ import annotations

import os

from dash import Dash

from dashboard import callbacks, grid, layout, metrics
from dashboard.data import (
    YOY_MONTHS,
    DashboardData,
    load_dashboard_data,
    reference_month,
    shift_month,
)


def build_initial_view(data: DashboardData) -> dict:
    """첫 렌더링에 필요한 값을 모아 레이아웃에 전달한다.

    기준 월과 지점 수는 상수가 아니라 데이터에서 구해 `view`로 내려보낸다.
    레이아웃이 상수를 직접 읽으면 실제 데이터로 바꿨을 때 화면 문구만 옛 값으로 남는다.
    """
    branch_names = data.branch_names
    default_branch = branch_names[0] if branch_names else ""
    current_month = reference_month(data)
    previous_month = shift_month(current_month, -1)
    base_month = shift_month(current_month, -YOY_MONTHS)
    total_row, branch_rows = metrics.branch_table(
        data.monthly, data.summary, current_month, base_month
    )
    return {
        "kpis": metrics.kpi_metrics(data.monthly, current_month, previous_month),
        "current_month": current_month,
        "previous_month": previous_month,
        "branch_count": len(branch_names),
        "branch_names": branch_names,
        "default_branch": default_branch,
        "trend_figure": callbacks.build_trend_figure(data, default_branch),
        "scatter_figure": callbacks.build_scatter_figure(data),
        "age_figure": callbacks.build_age_figure(data, default_branch),
        "investment_figure": callbacks.build_investment_figure(data),
        "column_defs": grid.build_column_defs(),
        "row_data": grid.build_row_data(branch_rows),
        "grid_options": grid.build_grid_options(total_row),
    }


def create_app() -> Dash:
    data = load_dashboard_data()
    app = Dash(
        __name__,
        title=layout.PAGE_TITLE,
        serve_locally=True,
        update_title=None,
    )
    app.layout = layout.create_layout(build_initial_view(data))
    callbacks.register_callbacks(app, data)
    return app


app = create_app()

if __name__ == "__main__":
    # 운영 코드에 debug=True를 고정하지 않는다. 필요하면 환경 변수로 켠다.
    debug = os.environ.get("DASHBOARD_DEBUG", "").lower() in {"1", "true", "yes"}
    app.run(host="127.0.0.1", port=int(os.environ.get("DASHBOARD_PORT", "8050")), debug=debug)
