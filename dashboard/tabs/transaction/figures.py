"""거래 탭의 Plotly Figure 생성.

데이터를 입력받아 Figure만 반환한다. 데이터를 직접 조회하지 않는다.
색상·글꼴 토큰과 공통 레이아웃은 `dashboard.figures`에서 가져온다.

추이 그림 두 개는 자산 탭과 같은 골격(`figures.trend_figure`)을 쓴다.
전체가 막대, 고른 지점이 선이다.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from dashboard import format as fmt
from dashboard.data import TOTAL_LABEL
from dashboard.figures import (
    COLOR_ACCENT_DARK,
    COLOR_AXIS,
    COLOR_PRIMARY,
    COLOR_SECONDARY,
    COLOR_SECONDARY_LIGHT,
    COLOR_SURFACE,
    COLOR_TEXT_MUTED,
    axis,
    base_layout,
    empty_figure,
    growth_scatter_figure,
    hover_columns,
    trend_figure,
)

# 연금 거래 현황 막대의 상품별 색. 순서는 상품 순서와 같다
# (→ data.PENSION_TRADE_PRODUCT_TYPES).
PENSION_COLORS = (COLOR_PRIMARY, COLOR_SECONDARY, "#A0A6A8")

# 입출금 선 두 개의 색. 채널 순서와 같다(→ data.CASH_FLOW_CHANNELS).
CHANNEL_COLORS = (COLOR_PRIMARY, COLOR_ACCENT_DARK)

# 산점도 축 여백. 점 위에 얹은 지점 이름이 축 끝에서 잘리지 않을 만큼만
# 준다.
SCATTER_PADDING = 0.12


# --- 1·3. 거래 추이 ----------------------------------------------------------
def create_trade_trend_figure(
    trend: pd.DataFrame,
    branch_name: str,
    measure_label: str,
    unit_label: str,
    to_text,
    to_delta_text,
) -> go.Figure:
    """전체와 선택 지점의 월별 거래 추이.

    `measure_label`은 상품 이름을 앞에 붙인 지표 이름이다(예: '국내주식
    거래금액'). 무엇을 그린 것인지 축 이름과 hover가 함께 알린다.
    """
    if trend.empty:
        return empty_figure()

    formatters = (("value", to_text), ("delta", to_delta_text))
    unit = f"{measure_label}({unit_label})"
    return trend_figure(
        trend,
        branch_name,
        f"{TOTAL_LABEL} {unit}",
        f"{branch_name} {unit}",
        {
            scope: hover_columns(trend, scope, formatters)
            for scope in ("total", "branch")
        },
        f"<br>{measure_label}: %{{customdata[0]}}"
        "<br>전월 대비: %{customdata[1]}",
    )


# --- 2·4. 거래 증가율 --------------------------------------------------------
def create_growth_scatter_figure(
    scatter: pd.DataFrame,
    measure_label: str,
    unit_label: str,
    to_text,
    median: float | None,
    base_month: str | None = None,
    current_month: str | None = None,
) -> go.Figure:
    """지점별 거래 규모와 전년 동월 대비 증가율 산점도.

    기준선 두 개가 사분면을 만든다. 가로는 증가·감소, 세로는 규모
    많음·적음이다. 자산 탭의 증가율 산점도와 같은 읽는 법을 쓴다.

    그림 골격은 수익 탭의 두 산점도와 같아 `dashboard.figures`에 있다.
    """
    return growth_scatter_figure(
        scatter,
        measure_label,
        unit_label,
        to_text,
        median,
        base_month=base_month,
        current_month=current_month,
    )


# --- 5. 입출금 분석 ----------------------------------------------------------
def create_cash_flow_figure(
    trend: pd.DataFrame, scope: str, channel_labels: tuple[str, str]
) -> go.Figure:
    """고른 구분의 월별 순입금.

    막대가 전체 순입금이고, 선 두 개가 그것을 이루는 채널이다. 두 선을
    더하면 막대가 된다. 세 값이 모두 억원이라 축 하나에 함께 그린다.

    순입금은 빠져나간 달에 음수가 되므로 0선을 그어 위아래를 나눈다.
    """
    if trend.empty:
        return empty_figure()

    labels = [fmt.format_month_short(month) for month in trend["base_month"]]
    figure = go.Figure()
    figure.add_trace(
        go.Bar(
            x=labels,
            y=trend["net_total"],
            name=f"순입금 {TOTAL_LABEL}",
            marker={"color": COLOR_SECONDARY_LIGHT, "line": {"width": 0}},
            customdata=[
                fmt.format_assets(value) for value in trend["net_total"]
            ],
            hovertemplate=(
                f"<b>%{{x}}</b><br>구분: {scope}"
                "<br>순입금 전체: %{customdata}<extra></extra>"
            ),
        )
    )
    for index, (column, label) in enumerate(
        zip(("net_securities", "net_bank"), channel_labels)
    ):
        figure.add_trace(
            go.Scatter(
                x=labels,
                y=trend[column],
                name=f"순입금 {label}",
                mode="lines+markers",
                line={
                    "color": CHANNEL_COLORS[index % len(CHANNEL_COLORS)],
                    "width": 2.5,
                },
                marker={
                    "color": CHANNEL_COLORS[index % len(CHANNEL_COLORS)],
                    "size": 8,
                    "symbol": "diamond" if index == 0 else "circle",
                    "line": {"color": COLOR_SURFACE, "width": 1.5},
                },
                customdata=[
                    fmt.format_assets(value) for value in trend[column]
                ],
                hovertemplate=(
                    f"<b>%{{x}}</b><br>구분: {scope}"
                    f"<br>순입금 {label}: %{{customdata}}<extra></extra>"
                ),
            )
        )

    values = pd.concat(
        [trend["net_total"], trend["net_securities"], trend["net_bank"]]
    )
    figure.update_layout(
        **base_layout(
            margin={"l": 92, "r": 32, "t": 24, "b": 48},
            hovermode="x unified",
        ),
        xaxis=axis(showgrid=False),
        yaxis=axis(
            "순입금(억원)",
            tickformat=",.0f",
            range=_symmetric_range(values),
            zeroline=True,
            zerolinecolor=COLOR_AXIS,
            zerolinewidth=1,
        ),
        bargap=0.35,
    )
    return figure


def _symmetric_range(values: pd.Series) -> list[float] | None:
    """0을 포함하는 축 범위.

    순입금은 부호가 뜻을 가지므로 0이 축 안에 있어야 한다. `padded_range`는
    값이 놓인 구간만 잡아 0이 밖으로 밀려날 수 있다.
    """
    numbers = pd.to_numeric(values, errors="coerce").dropna()
    if numbers.empty:
        return None
    low = min(0.0, float(numbers.min()))
    high = max(0.0, float(numbers.max()))
    span = high - low
    padding = span * 0.12 if span > 0 else 1.0
    return [low - padding, high + padding]


# --- 6. 연금 거래 현황 분석 --------------------------------------------------
def create_pension_mix_figure(
    mix: pd.DataFrame,
    products: tuple[str, ...],
    scope: str,
    pension_type: str,
    measure_label: str,
    unit_label: str,
    to_text,
) -> go.Figure:
    """고른 구분·연금의 월별 상품 구성 누적 막대.

    원본에 값이 없는 상품은 막대에서 뺀다. 빈 계열을 그대로 두면 범례에는
    이름이 뜨는데 막대에는 아무것도 없어 고장으로 보인다. 무엇이 빠졌는지는
    카드의 안내 문구가 알린다(→ tabs.transaction).
    """
    if mix.empty:
        return empty_figure()

    labels = [fmt.format_month_short(month) for month in mix["base_month"]]
    figure = go.Figure()
    drawn = 0
    for index, product in enumerate(products):
        if product not in mix.columns or mix[product].isna().all():
            continue
        values = [
            None if pd.isna(value) else float(value) for value in mix[product]
        ]
        figure.add_trace(
            go.Bar(
                x=labels,
                y=values,
                name=product,
                marker={
                    "color": PENSION_COLORS[index % len(PENSION_COLORS)],
                    "line": {"width": 0},
                },
                customdata=[to_text(value) for value in values],
                hovertemplate=(
                    f"<b>%{{x}}</b><br>구분: {scope}"
                    f"<br>{pension_type} {product}"
                    " %{customdata}<extra></extra>"
                ),
            )
        )
        drawn += 1
    if drawn == 0:
        return empty_figure()

    figure.update_layout(
        **base_layout(
            margin={"l": 92, "r": 32, "t": 24, "b": 48},
            hovermode="x unified",
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
        bargap=0.35,
        xaxis=axis(showgrid=False),
        yaxis=axis(
            f"{pension_type} {measure_label}({unit_label})",
            tickformat=",.0f",
        ),
    )
    return figure


__all__ = [
    "CHANNEL_COLORS",
    "PENSION_COLORS",
    "create_cash_flow_figure",
    "create_growth_scatter_figure",
    "create_pension_mix_figure",
    "create_trade_trend_figure",
]
