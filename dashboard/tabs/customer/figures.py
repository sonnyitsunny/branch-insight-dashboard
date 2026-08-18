"""고객 탭의 Plotly Figure 생성.

데이터를 입력받아 Figure만 반환한다. 데이터를 직접 조회하지 않는다.
색상·글꼴 토큰과 공통 레이아웃은 `dashboard.figures`에서 가져온다.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from dashboard import format as fmt
from dashboard.data import (
    AGE_GROUPS,
    CONSENT_LABEL,
    INVESTMENT_TYPES,
    NON_CONSENT_LABEL,
    TOTAL_LABEL,
)
from dashboard.figures import (
    COLOR_AXIS,
    COLOR_PRIMARY,
    COLOR_SECONDARY,
    COLOR_SECONDARY_LIGHT,
    COLOR_SURFACE,
    COLOR_TEXT_MUTED,
    axis,
    base_layout,
    empty_figure,
    padded_range,
)


# --- 1. 고객 추이
# -------------------------------------------------------------
def create_customer_trend_figure(
    trend: pd.DataFrame, branch_name: str
) -> go.Figure:
    """전체 공통고객 수(막대, 왼쪽 축)와 선택 지점 값(선, 오른쪽 축).

    두 축 모두 0이 아니라 값이 움직인 구간에 맞춘다. 공통고객 수는 몇 만 대에서
    몇 백 명씩 움직여서 0부터 그리면 변화가 눈에 보이지 않는다.

    이렇게 하면 막대 길이의 비율이 값의 비율과 달라진다. 실제 크기는 축
    눈금 숫자와 hover 값으로 읽는다.
    """
    if trend.empty:
        return empty_figure()

    labels = [fmt.format_month_short(month) for month in trend["base_month"]]
    figure = go.Figure()

    figure.add_trace(
        go.Bar(
            x=labels,
            y=trend["total_count"],
            name=TOTAL_LABEL,
            marker={"color": COLOR_SECONDARY_LIGHT, "line": {"width": 0}},
            customdata=np.stack(
                [
                    [
                        fmt.format_count(value)
                        for value in trend["total_count"]
                    ],
                    [
                        fmt.format_count_delta(value)
                        for value in trend["total_delta"]
                    ],
                ],
                axis=-1,
            ),
            hovertemplate=(
                "<b>%{x}</b><br>구분: 전체<br>공통고객 수: %{customdata[0]}"
                "<br>전월 대비: %{customdata[1]}<extra></extra>"
            ),
        )
    )

    figure.add_trace(
        go.Scatter(
            x=labels,
            y=trend["branch_count"],
            name=branch_name,
            yaxis="y2",
            mode="lines+markers",
            line={"color": COLOR_PRIMARY, "width": 2.5},
            marker={
                "color": COLOR_PRIMARY,
                "size": 8,
                "symbol": "diamond",
                "line": {"color": COLOR_SURFACE, "width": 1.5},
            },
            customdata=np.stack(
                [
                    [
                        fmt.format_count(value)
                        for value in trend["branch_count"]
                    ],
                    [
                        fmt.format_count_delta(value)
                        for value in trend["branch_delta"]
                    ],
                    [
                        fmt.format_signed_percent(value)
                        for value in trend["branch_yoy"]
                    ],
                ],
                axis=-1,
            ),
            hovertemplate=(
                f"<b>%{{x}}</b><br>구분: {branch_name}"
                "<br>공통고객 수: %{customdata[0]}"
                "<br>전월 대비: %{customdata[1]}"
                "<br>전년 동월 대비: %{customdata[2]}<extra></extra>"
            ),
        )
    )

    figure.update_layout(
        **base_layout(
            margin={"l": 86, "r": 86, "t": 24, "b": 48}, hovermode="x unified"
        ),
        xaxis=axis("기준 월", showgrid=False),
        # 값이 움직인 구간에 여백만 더해 축 범위를 잡는다. 두 계열의 규모가
        # 달라 축을 따로 두므로, 각자 자기 범위에 맞춘다. 축 눈금 숫자를
        # 보고 실제 크기를 알 수 있게 눈금은 그대로 표시한다.
        yaxis=axis(
            "전체 공통고객 수(명)",
            tickformat=",.0f",
            range=padded_range(trend["total_count"]),
        ),
        yaxis2=axis(
            f"{branch_name} 공통고객 수(명)",
            overlaying="y",
            side="right",
            showgrid=False,
            tickformat=",.0f",
            range=padded_range(trend["branch_count"]),
        ),
        bargap=0.35,
    )
    return figure


# --- 2. 공통고객 수 및 성장률
# ------------------------------------------------------
def create_growth_scatter_figure(
    scatter: pd.DataFrame,
    median_count: float | None,
    base_month: str | None = None,
    current_month: str | None = None,
) -> go.Figure:
    """지점별 공통고객 수와 YoY 증가율 산점도.

    hover에 쓰는 두 월 이름은 인자로 받는다. 문자열로 적어두면 데이터 기간이
    바뀌었을 때 실제 비교 기준과 어긋나도 알아채지 못한다.
    """
    if scatter.empty:
        return empty_figure()

    base_label = fmt.format_month(base_month) if base_month else "비교 기준 월"
    current_label = (
        fmt.format_month(current_month) if current_month else "기준 월"
    )

    figure = go.Figure(
        go.Scatter(
            x=scatter["current_count"],
            y=scatter["yoy"],
            mode="markers+text",
            name="지점",
            # 모든 지점 이름을 표시한다. 일부만 보이면 나머지는 점만 찍혀
            # 어느 지점인지 알 수 없다. 위치를 위·아래로 번갈아 놓아 봤지만
            # x 순서만 보고 정하는 방식이라 오히려 더 겹쳤다(4쌍 → 6쌍).
            text=scatter["branch_name"].astype(str),
            textposition="top center",
            textfont={"size": 9, "color": COLOR_TEXT_MUTED},
            marker={
                "color": COLOR_SECONDARY,
                "size": 11,
                "opacity": 0.85,
                "line": {"color": COLOR_SURFACE, "width": 1},
            },
            customdata=np.stack(
                [
                    scatter["branch_name"].astype(str),
                    [
                        fmt.format_count(value)
                        for value in scatter["base_count"]
                    ],
                    [
                        fmt.format_count(value)
                        for value in scatter["current_count"]
                    ],
                    [
                        fmt.format_count_delta(value)
                        for value in scatter["count_delta"]
                    ],
                    [
                        fmt.format_signed_percent(value)
                        for value in scatter["yoy"]
                    ],
                ],
                axis=-1,
            ),
            hovertemplate=(
                "<b>%{customdata[0]}</b>"
                f"<br>{base_label}: %{{customdata[1]}}"
                f"<br>{current_label}: %{{customdata[2]}}"
                "<br>공통고객 수 증감: %{customdata[3]}"
                "<br>증가율(YoY): %{customdata[4]}<extra></extra>"
            ),
        )
    )

    # 축 범위를 데이터에 맞춰 점과 라벨이 가장자리에 붙지 않게 한다.
    counts = pd.to_numeric(scatter["current_count"], errors="coerce").dropna()
    counts = counts[counts > 0]
    x_range = None
    if not counts.empty:
        margin = max((counts.max() - counts.min()) * 0.08, counts.max() * 0.02)
        x_range = [
            float(max(0.0, counts.min() - margin)),
            float(counts.max() + margin),
        ]

    figure.update_layout(
        **base_layout(
            showlegend=False,
            margin={"l": 86, "r": 32, "t": 40, "b": 56},
            # 드래그는 이동으로 쓴다. 영역 확대로 두면 확대한 뒤 다른 곳을
            # 보려면 모드바에서 팬으로 바꿔야 해서 한 단계가 더 는다.
            # 확대·축소는 휠과 모드바 버튼이 맡는다.
            dragmode="pan",
        ),
        # 선형 축을 쓴다. 로그 축은 규모가 100배 넘게 벌어질 때 쓰는 것이고,
        # 지점 규모 차이는 그보다 훨씬 작다. 로그로 그리면 눈금이
        # 600·700·800…처럼
        # 불규칙하게 촘촘해져 세로선이 화면을 덮고, 점 사이 간격도 왜곡된다.
        xaxis=axis(
            "공통고객 수(명)", tickformat=",.0f", range=x_range
        ),
        yaxis=axis(
            "공통고객 수 증가율(YoY, %)",
            ticksuffix="%",
            zeroline=False,
        ),
    )

    # 기준선 두 개가 사분면을 만든다. 가로는 증가·감소, 세로는 규모 많음·적음.
    figure.add_hline(
        y=0,
        line={"color": COLOR_AXIS, "width": 1, "dash": "dash"},
        annotation={
            "text": "증가율 0%",
            "font": {"size": 10, "color": COLOR_TEXT_MUTED},
        },
        annotation_position="right",
    )
    if median_count and median_count > 0:
        figure.add_shape(
            type="line",
            xref="x",
            yref="paper",
            x0=median_count,
            x1=median_count,
            y0=0,
            y1=1,
            line={"color": COLOR_AXIS, "width": 1, "dash": "dash"},
        )
        figure.add_annotation(
            xref="x",
            yref="paper",
            x=median_count,
            y=1.06,
            text=f"공통고객 수 중앙값 {fmt.format_count(median_count)}",
            showarrow=False,
            font={"size": 10, "color": COLOR_TEXT_MUTED},
        )
    return figure


# --- 3. 연령별 공통고객 분포
# ------------------------------------------------------
def create_age_distribution_figure(
    distribution: pd.DataFrame, branch_name: str
) -> go.Figure:
    """전체와 선택 지점의 연령 구간별 공통고객 비중(그룹형 막대)."""
    if distribution.empty:
        return empty_figure()

    figure = go.Figure()
    colors = {TOTAL_LABEL: COLOR_SECONDARY_LIGHT, branch_name: COLOR_PRIMARY}
    for scope in (TOTAL_LABEL, branch_name):
        scope_data = distribution[distribution["scope"] == scope]
        if scope_data.empty:
            continue
        scope_data = (
            scope_data.set_index("age_group")
            .reindex(list(AGE_GROUPS))
            .reset_index()
        )
        figure.add_trace(
            go.Bar(
                x=scope_data["age_group"],
                y=scope_data["share"],
                name=scope,
                marker={
                    "color": colors.get(scope, COLOR_SECONDARY),
                    "line": {"width": 0},
                },
                customdata=np.stack(
                    [
                        [
                            fmt.format_count(value)
                            for value in scope_data["customer_count"]
                        ],
                        [
                            fmt.format_percent(value)
                            for value in scope_data["share"]
                        ],
                    ],
                    axis=-1,
                ),
                hovertemplate=(
                    f"<b>%{{x}}</b><br>구분: {scope}"
                    "<br>공통고객 수: %{customdata[0]}"
                    "<br>공통고객 비중: %{customdata[1]}<extra></extra>"
                ),
            )
        )

    figure.update_layout(
        **base_layout(margin={"l": 86, "r": 32, "t": 24, "b": 56}),
        barmode="group",
        bargap=0.28,
        bargroupgap=0.08,
        xaxis=axis("연령 구간", showgrid=False),
        yaxis=axis("공통고객 비중(%)", ticksuffix="%", rangemode="tozero"),
    )
    return figure


# --- 4. 공통고객 투자성향
# --------------------------------------------------------------
def create_investment_figure(breakdown: pd.DataFrame, scope: str) -> go.Figure:
    """투자성향별 마케팅 동의·불원 100% 누적 가로 막대."""
    if breakdown.empty:
        return empty_figure()

    figure = go.Figure()
    colors = {
        CONSENT_LABEL: COLOR_PRIMARY,
        NON_CONSENT_LABEL: COLOR_SECONDARY_LIGHT,
    }
    for label in (CONSENT_LABEL, NON_CONSENT_LABEL):
        segment = (
            breakdown[breakdown["consent_label"] == label]
            .set_index("investment_type")
            .reindex(list(INVESTMENT_TYPES))
            .reset_index()
        )
        figure.add_trace(
            go.Bar(
                x=segment["share"],
                y=segment["investment_type"],
                name=label,
                orientation="h",
                marker={"color": colors[label], "line": {"width": 0}},
                customdata=np.stack(
                    [
                        [
                            fmt.format_count(value)
                            for value in segment["customer_count"]
                        ],
                        [
                            fmt.format_percent(value)
                            for value in segment["share"]
                        ],
                        [
                            fmt.format_count(value)
                            for value in segment["type_total"]
                        ],
                    ],
                    axis=-1,
                ),
                hovertemplate=(
                    f"<b>%{{y}}</b><br>구분: {scope}"
                    f"<br>마케팅 동의 여부: {label}"
                    "<br>공통고객 수: %{customdata[0]}"
                    "<br>성향 내 비율: %{customdata[1]}"
                    "<br>성향 전체 공통고객 수: %{customdata[2]}"
                    "<extra></extra>"
                ),
            )
        )

    totals = (
        breakdown.groupby("investment_type", observed=True)["type_total"]
        .max()
        .reindex(list(INVESTMENT_TYPES))
    )
    annotations = [
        {
            "x": 100,
            "y": investment_type,
            "xref": "x",
            "yref": "y",
            "text": f"  {fmt.format_count(total)}",
            "showarrow": False,
            "xanchor": "left",
            "font": {"size": 11, "color": COLOR_TEXT_MUTED},
        }
        for investment_type, total in totals.items()
    ]

    figure.update_layout(
        # 누적 막대에서도 범례 순서를 막대 순서(동의 → 불원)와 맞춘다.
        **base_layout(
            margin={"l": 88, "r": 104, "t": 24, "b": 48},
            legend={
                "orientation": "h",
                "yanchor": "bottom",
                "y": 1.02,
                "xanchor": "left",
                "x": 0,
                "traceorder": "normal",
                "bgcolor": "rgba(0,0,0,0)",
            },
        ),
        barmode="stack",
        bargap=0.32,
        xaxis=axis("구성 비율(%)", range=[0, 100], ticksuffix="%"),
        # 가로 막대는 아래에서 위로 쌓이므로 순서를 뒤집어 성향 순서를
        # 고정한다.
        yaxis=axis(
            None,
            showgrid=False,
            categoryorder="array",
            categoryarray=list(reversed(INVESTMENT_TYPES)),
        ),
        annotations=annotations,
    )
    return figure
