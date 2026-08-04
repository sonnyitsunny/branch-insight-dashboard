"""Plotly Figure 생성.

데이터를 입력받아 Figure만 반환한다. 데이터를 직접 조회하지 않는다.
색상·글꼴 토큰은 이 모듈에서 한 번만 정의하고 `assets/style.css`의
CSS 변수와 이름·의미를 맞춘다.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from dashboard import format as fmt
from dashboard.data import AGE_GROUPS, CONSENT_LABEL, INVESTMENT_TYPES, NON_CONSENT_LABEL, TOTAL_LABEL

# --- 디자인 토큰 (CSS 변수와 동일한 의미) --------------------------------------
FONT_FAMILY = '"Spoqa Han Sans Neo", "Spoqa Han Sans", "Malgun Gothic", sans-serif'

COLOR_PRIMARY = "#F58220"  # --color-primary
COLOR_SECONDARY = "#043B72"  # --color-secondary
COLOR_PRIMARY_LIGHT = "#F0B26B"  # --color-primary-light
COLOR_PRIMARY_DARK = "#CB6015"  # --color-primary-dark
COLOR_ACCENT = "#00A9CE"  # --color-accent
COLOR_ACCENT_DARK = "#0086B8"  # --color-accent-dark
COLOR_SECONDARY_LIGHT = "#7E9FC3"  # --color-secondary-light
COLOR_SECONDARY_PALE = "#8DC8E8"  # --color-secondary-pale

COLOR_TEXT = "#48535B"  # --color-text
COLOR_TEXT_MUTED = "#84888B"  # --color-text-muted
COLOR_AXIS = "#A0A6A8"  # --color-axis
COLOR_GRID = "#E5E4E1"  # --color-grid
COLOR_BORDER = "#CDCECB"  # --color-border
COLOR_SURFACE = "#FFFFFF"  # --color-surface

# 증감 표기색. 색상만으로 구분하지 않고 항상 +/- 기호와 함께 쓴다.
COLOR_UP = COLOR_PRIMARY_DARK
COLOR_DOWN = COLOR_ACCENT_DARK

EMPTY_MESSAGE = "표시할 데이터가 없습니다"

# 정적 HTML과 Dash 화면에서 같은 설정을 쓴다.
PLOTLY_CONFIG = {
    "displaylogo": False,
    "displayModeBar": False,
    "responsive": True,
    "locale": "ko",
    "modeBarButtonsToRemove": [
        "select2d",
        "lasso2d",
        "autoScale2d",
        "zoomIn2d",
        "zoomOut2d",
        "toggleSpikelines",
        "hoverClosestCartesian",
        "hoverCompareCartesian",
    ],
    "toImageButtonOptions": {"format": "png", "scale": 2},
}


def base_layout(**overrides) -> dict:
    """모든 차트가 공유하는 레이아웃 설정."""
    layout = {
        "font": {"family": FONT_FAMILY, "size": 12, "color": COLOR_TEXT},
        "paper_bgcolor": COLOR_SURFACE,
        "plot_bgcolor": COLOR_SURFACE,
        "margin": {"l": 64, "r": 32, "t": 24, "b": 56},
        "hoverlabel": {
            "font": {"family": FONT_FAMILY, "size": 12},
            "bgcolor": COLOR_SURFACE,
            "bordercolor": COLOR_BORDER,
            "align": "left",
        },
        "legend": {
            "orientation": "h",
            "yanchor": "bottom",
            "y": 1.02,
            "xanchor": "left",
            "x": 0,
            "bgcolor": "rgba(0,0,0,0)",
        },
        "showlegend": True,
        "dragmode": False,
    }
    layout.update(overrides)
    return layout


def _axis(title: str | None = None, **overrides) -> dict:
    axis = {
        "title": {"text": title, "font": {"size": 12, "color": COLOR_TEXT_MUTED}},
        "showgrid": True,
        "gridcolor": COLOR_GRID,
        "zeroline": False,
        "showline": True,
        "linecolor": COLOR_AXIS,
        "ticks": "outside",
        "tickcolor": COLOR_GRID,
        "tickfont": {"size": 11, "color": COLOR_TEXT_MUTED},
        "automargin": True,
    }
    axis.update(overrides)
    return axis


def empty_figure(message: str = EMPTY_MESSAGE) -> go.Figure:
    """데이터가 없을 때 안내 문구만 표시한다."""
    figure = go.Figure()
    figure.update_layout(
        **base_layout(showlegend=False, margin={"l": 24, "r": 24, "t": 24, "b": 24}),
        xaxis={"visible": False},
        yaxis={"visible": False},
        annotations=[
            {
                "text": message,
                "xref": "paper",
                "yref": "paper",
                "x": 0.5,
                "y": 0.5,
                "showarrow": False,
                "font": {"size": 13, "color": COLOR_TEXT_MUTED},
            }
        ],
    )
    return figure


# --- 1. 고객 추이 -------------------------------------------------------------
def create_customer_trend_figure(trend: pd.DataFrame, branch_name: str) -> go.Figure:
    """전체 고객 수(막대, 왼쪽 축)와 선택 지점 고객 수(선, 오른쪽 축)."""
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
                    [fmt.format_count(value) for value in trend["total_count"]],
                    [fmt.format_count_delta(value) for value in trend["total_delta"]],
                ],
                axis=-1,
            ),
            hovertemplate=(
                "<b>%{x}</b><br>구분: 전체<br>고객 수: %{customdata[0]}"
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
            marker={"color": COLOR_PRIMARY, "size": 7, "line": {"color": COLOR_SURFACE, "width": 1.5}},
            customdata=np.stack(
                [
                    [fmt.format_count(value) for value in trend["branch_count"]],
                    [fmt.format_count_delta(value) for value in trend["branch_delta"]],
                    [fmt.format_signed_percent(value) for value in trend["branch_yoy"]],
                ],
                axis=-1,
            ),
            hovertemplate=(
                f"<b>%{{x}}</b><br>구분: {branch_name}<br>고객 수: %{{customdata[0]}}"
                "<br>전월 대비: %{customdata[1]}<br>전년 동월 대비: %{customdata[2]}<extra></extra>"
            ),
        )
    )

    figure.update_layout(
        **base_layout(margin={"l": 86, "r": 86, "t": 24, "b": 48}, hovermode="x unified"),
        xaxis=_axis("기준 월", showgrid=False),
        # 두 축 모두 0부터 시작해 한쪽의 변동이 과장되어 보이지 않게 한다.
        yaxis=_axis("전체 고객 수(명)", tickformat=",.0f", rangemode="tozero"),
        yaxis2=_axis(
            f"{branch_name} 고객 수(명)",
            overlaying="y",
            side="right",
            showgrid=False,
            tickformat=",.0f",
            rangemode="tozero",
        ),
        bargap=0.35,
    )
    return figure


# --- 2. 고객 수 및 성장률 ------------------------------------------------------
def create_growth_scatter_figure(scatter: pd.DataFrame, median_count: float | None) -> go.Figure:
    """지점별 고객 수(로그)와 YoY 증가율 산점도."""
    if scatter.empty:
        return empty_figure()

    # 성장률 상·하위 3개 지점만 라벨을 표시해 화면을 복잡하게 만들지 않는다.
    ranked = scatter.dropna(subset=["yoy"]).sort_values("yoy")
    labeled = set(ranked["branch_name"].head(3)) | set(ranked["branch_name"].tail(3))
    texts = [name if name in labeled else "" for name in scatter["branch_name"]]

    figure = go.Figure(
        go.Scatter(
            x=scatter["current_count"],
            y=scatter["yoy"],
            mode="markers+text",
            name="지점",
            text=texts,
            textposition="top center",
            textfont={"size": 10, "color": COLOR_TEXT_MUTED},
            marker={
                "color": COLOR_SECONDARY,
                "size": 11,
                "opacity": 0.85,
                "line": {"color": COLOR_SURFACE, "width": 1},
            },
            customdata=np.stack(
                [
                    scatter["branch_name"].astype(str),
                    [fmt.format_count(value) for value in scatter["base_count"]],
                    [fmt.format_count(value) for value in scatter["current_count"]],
                    [fmt.format_count_delta(value) for value in scatter["count_delta"]],
                    [fmt.format_signed_percent(value) for value in scatter["yoy"]],
                ],
                axis=-1,
            ),
            hovertemplate=(
                "<b>%{customdata[0]}</b><br>2025년 7월: %{customdata[1]}"
                "<br>2026년 7월: %{customdata[2]}<br>고객 수 증감: %{customdata[3]}"
                "<br>증가율(YoY): %{customdata[4]}<extra></extra>"
            ),
        )
    )

    # 로그 축 범위를 데이터에 맞춰 점이 한쪽에 몰리지 않게 한다.
    counts = pd.to_numeric(scatter["current_count"], errors="coerce").dropna()
    counts = counts[counts > 0]
    x_range = (
        [float(np.log10(counts.min() * 0.75)), float(np.log10(counts.max() * 1.35))]
        if not counts.empty
        else None
    )

    figure.update_layout(
        **base_layout(showlegend=False, margin={"l": 86, "r": 32, "t": 40, "b": 56}),
        xaxis=_axis("고객 수(log)", type="log", tickformat=",.0f", range=x_range),
        yaxis=_axis("고객 수 증가율(YoY, %)", ticksuffix="%", zeroline=False),
    )

    # 기준선: YoY 0%와 고객 수 중앙값. 영역은 옅은 보조 문구로만 구분한다.
    figure.add_hline(
        y=0,
        line={"color": COLOR_AXIS, "width": 1, "dash": "dash"},
        annotation={"text": "증가율 0%", "font": {"size": 10, "color": COLOR_TEXT_MUTED}},
        annotation_position="right",
    )
    if median_count and median_count > 0:
        # 로그 축의 도형 좌표는 log10 값을 쓴다.
        log_median = float(np.log10(median_count))
        figure.add_shape(
            type="line",
            xref="x",
            yref="paper",
            x0=log_median,
            x1=log_median,
            y0=0,
            y1=1,
            line={"color": COLOR_AXIS, "width": 1, "dash": "dash"},
        )
        figure.add_annotation(
            xref="x",
            yref="paper",
            x=log_median,
            y=1.06,
            text=f"고객 수 중앙값 {fmt.format_count(median_count)}",
            showarrow=False,
            font={"size": 10, "color": COLOR_TEXT_MUTED},
        )

    for x_position, y_position, x_anchor, text in (
        (0.02, 0.96, "left", "고객 수 적음 · 성장"),
        (0.98, 0.96, "right", "고객 수 많음 · 성장"),
        (0.02, 0.04, "left", "고객 수 적음 · 감소"),
        (0.98, 0.04, "right", "고객 수 많음 · 감소"),
    ):
        figure.add_annotation(
            xref="paper",
            yref="paper",
            x=x_position,
            y=y_position,
            xanchor=x_anchor,
            text=text,
            showarrow=False,
            font={"size": 10, "color": COLOR_AXIS},
        )
    return figure


# --- 3. 연령별 고객 분포 ------------------------------------------------------
def create_age_distribution_figure(distribution: pd.DataFrame, branch_name: str) -> go.Figure:
    """전체와 선택 지점의 연령 구간별 고객 비중(그룹형 막대)."""
    if distribution.empty:
        return empty_figure()

    figure = go.Figure()
    colors = {TOTAL_LABEL: COLOR_SECONDARY_LIGHT, branch_name: COLOR_PRIMARY}
    for scope in (TOTAL_LABEL, branch_name):
        scope_data = distribution[distribution["scope"] == scope]
        if scope_data.empty:
            continue
        scope_data = scope_data.set_index("age_group").reindex(list(AGE_GROUPS)).reset_index()
        figure.add_trace(
            go.Bar(
                x=scope_data["age_group"],
                y=scope_data["share"],
                name=scope,
                marker={"color": colors.get(scope, COLOR_SECONDARY), "line": {"width": 0}},
                customdata=np.stack(
                    [
                        [fmt.format_count(value) for value in scope_data["customer_count"]],
                        [fmt.format_percent(value) for value in scope_data["share"]],
                    ],
                    axis=-1,
                ),
                hovertemplate=(
                    f"<b>%{{x}}</b><br>구분: {scope}<br>고객 수: %{{customdata[0]}}"
                    "<br>고객 비중: %{customdata[1]}<extra></extra>"
                ),
            )
        )

    figure.update_layout(
        **base_layout(margin={"l": 86, "r": 32, "t": 24, "b": 56}),
        barmode="group",
        bargap=0.28,
        bargroupgap=0.08,
        xaxis=_axis("연령 구간", showgrid=False),
        yaxis=_axis("고객 비중(%)", ticksuffix="%", rangemode="tozero"),
    )
    return figure


# --- 4. 투자성향 --------------------------------------------------------------
def create_investment_figure(breakdown: pd.DataFrame, scope: str) -> go.Figure:
    """투자성향별 마케팅 동의·비동의 100% 누적 가로 막대."""
    if breakdown.empty:
        return empty_figure()

    figure = go.Figure()
    colors = {CONSENT_LABEL: COLOR_PRIMARY, NON_CONSENT_LABEL: COLOR_SECONDARY_LIGHT}
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
                        [fmt.format_count(value) for value in segment["customer_count"]],
                        [fmt.format_percent(value) for value in segment["share"]],
                        [fmt.format_count(value) for value in segment["type_total"]],
                    ],
                    axis=-1,
                ),
                hovertemplate=(
                    f"<b>%{{y}}</b><br>구분: {scope}<br>마케팅 동의 여부: {label}"
                    "<br>고객 수: %{customdata[0]}<br>성향 내 비율: %{customdata[1]}"
                    "<br>성향 전체 고객 수: %{customdata[2]}<extra></extra>"
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
        # 누적 막대에서도 범례 순서를 막대 순서(동의 → 비동의)와 맞춘다.
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
        xaxis=_axis("구성 비율(%)", range=[0, 100], ticksuffix="%"),
        # 가로 막대는 아래에서 위로 쌓이므로 순서를 뒤집어 성향 순서를 고정한다.
        yaxis=_axis(None, showgrid=False, categoryorder="array", categoryarray=list(reversed(INVESTMENT_TYPES))),
        annotations=annotations,
    )
    return figure
