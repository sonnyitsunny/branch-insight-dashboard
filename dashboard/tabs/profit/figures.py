"""수익 탭의 Plotly Figure 생성.

데이터를 입력받아 Figure만 반환한다. 데이터를 직접 조회하지 않는다.
색상·글꼴 토큰과 공통 레이아웃은 `dashboard.figures`에서 가져온다.

비중 막대와 산점도 두 개는 자산·거래 탭과 같은 골격(`figures.mix_figure`,
`figures.growth_scatter_figure`)을 쓴다. 여기서는 이 탭의 색과 이름만
정한다. 수익 추이만 이 탭에서 그린다 — 막대와 선이 서로 다른 지표(금액과
비중)라 기존 추이 골격에 맞지 않는다.
"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

from dashboard import format as fmt
from dashboard.figures import (
    COLOR_PRIMARY,
    COLOR_PRIMARY_DARK,
    COLOR_PRIMARY_LIGHT,
    COLOR_SECONDARY,
    COLOR_SECONDARY_LIGHT,
    COLOR_SURFACE,
    axis,
    base_layout,
    empty_figure,
    growth_scatter_figure,
    mix_figure,
    padded_range,
)

# 수익 비중 막대에 쌓는 분류별 색. 열 칸을 한눈에 가르되 주색상을 화면
# 전체에 과하게 쓰지 않는다(→ AGENTS.md §5.2). 순서는 쌓는 순서와 같다
# (→ tabs/profit/__init__.py 의 MIX_TYPES).
#
# 칸이 열 개라 §5.1의 그래프 보조색 여덟 개로는 모자란다. 주색상·보조색을
# 양 끝에 한 번씩만 더해 열 개를 채운다.
MIX_COLORS = (
    COLOR_PRIMARY,
    COLOR_PRIMARY_DARK,
    COLOR_PRIMARY_LIGHT,
    "#AD624E",
    "#C2AC97",
    COLOR_SECONDARY,
    "#0086B8",
    "#00A9CE",
    "#8DC8E8",
    "#A0A6A8",
)


# --- 1. 수익 추이 ------------------------------------------------------------
def create_revenue_trend_figure(
    trend: pd.DataFrame,
    scope: str,
    amount_label: str,
    share_label_text: str,
) -> go.Figure:
    """고른 구분의 월별 수익 금액(막대)과 공통고객 수익 비중(선).

    두 지표의 단위가 달라(원과 %) 축을 좌우로 나눈다. 왼쪽이 금액,
    오른쪽이 비중이다.

    두 축 모두 0이 아니라 값이 움직인 구간에 맞춘다. 규모가 크고 변화가
    작아 0부터 그리면 움직임이 보이지 않는다. 실제 크기는 축 눈금과
    hover 값으로 읽는다(→ figures.trend_figure와 같은 규칙).
    """
    if trend.empty:
        return empty_figure()

    labels = [
        fmt.format_month_short(month) for month in trend["base_month"]
    ]
    figure = go.Figure()
    figure.add_trace(
        go.Bar(
            x=labels,
            y=trend["amount"],
            name=amount_label,
            marker={"color": COLOR_SECONDARY_LIGHT, "line": {"width": 0}},
            customdata=[
                fmt.format_revenue(value) for value in trend["amount"]
            ],
            hovertemplate=(
                f"<b>%{{x}}</b><br>구분: {scope}"
                f"<br>{amount_label}: %{{customdata}}<extra></extra>"
            ),
        )
    )
    figure.add_trace(
        go.Scatter(
            x=labels,
            y=trend["share"],
            name=share_label_text,
            yaxis="y2",
            mode="lines+markers",
            line={"color": COLOR_PRIMARY, "width": 2.5},
            marker={
                "color": COLOR_PRIMARY,
                "size": 8,
                "symbol": "diamond",
                "line": {"color": COLOR_SURFACE, "width": 1.5},
            },
            customdata=[
                fmt.format_percent(value) for value in trend["share"]
            ],
            hovertemplate=(
                f"<b>%{{x}}</b><br>구분: {scope}"
                f"<br>{share_label_text}: %{{customdata}}<extra></extra>"
            ),
        )
    )
    figure.update_layout(
        **base_layout(
            margin={"l": 92, "r": 92, "t": 24, "b": 48},
            hovermode="x unified",
        ),
        xaxis=axis("기준 월", showgrid=False),
        yaxis=axis(
            amount_label,
            tickformat=",.0f",
            range=padded_range(trend["amount"]),
        ),
        yaxis2=axis(
            f"{share_label_text}(%)",
            overlaying="y",
            side="right",
            showgrid=False,
            ticksuffix="%",
            range=padded_range(trend["share"]),
        ),
        bargap=0.35,
    )
    return figure


# --- 2. 수익 비중 ------------------------------------------------------------
# 범례를 몇 칸씩 끊을지. 쌓는 칸이 열 개고 그중 'CMA발행어음RP'가 길어,
# 칸 수를 Plotly에 맡기면 2열 화면에서 마지막 칸의 이름이 잘린다. 넷으로
# 끊으면 가장 좁은 2열 화면(카드 폭 약 628px)에서도 칸 안에 들어간다
# (→ figures._legend_grid, assets/style.css 의 1320px 분기).
MIX_LEGEND_COLUMNS = 4


def create_revenue_mix_figure(
    mix: pd.DataFrame, labels: tuple[str, ...]
) -> go.Figure:
    """구분별 수익 구성 100% 누적 세로 막대.

    첫 막대가 전체, 나머지가 고른 지점이다. 자산 구성과 같은 골격을 쓴다.
    """
    return mix_figure(
        mix,
        labels,
        MIX_COLORS,
        "수익 비중(%)",
        "분류",
        legend_columns=MIX_LEGEND_COLUMNS,
    )


# --- 3·4. 수익 비교 산점도 ---------------------------------------------------
def create_revenue_scatter_figure(
    scatter: pd.DataFrame,
    measure_label: str,
    unit_label: str,
    to_text,
    median: float | None,
    base_month: str | None = None,
    current_month: str | None = None,
    value_suffix: str = "",
) -> go.Figure:
    """지점별 수익 규모와 전년 동월 대비 증가율 산점도.

    금액 비교와 점유율 비교가 같은 함수를 쓴다. 단위와 표기만 다르다.
    거래 탭의 증가율 산점도와 같은 읽는 법이다.
    """
    return growth_scatter_figure(
        scatter,
        measure_label,
        unit_label,
        to_text,
        median,
        base_month=base_month,
        current_month=current_month,
        value_suffix=value_suffix,
    )


__all__ = [
    "MIX_COLORS",
    "create_revenue_mix_figure",
    "create_revenue_scatter_figure",
    "create_revenue_trend_figure",
]
