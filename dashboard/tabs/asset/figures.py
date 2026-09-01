"""자산 탭의 Plotly Figure 생성.

데이터를 입력받아 Figure만 반환한다. 데이터를 직접 조회하지 않는다.
색상·글꼴 토큰과 공통 레이아웃은 `dashboard.figures`에서 가져온다.
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
    COLOR_GRID,
    COLOR_PRIMARY,
    COLOR_PRIMARY_DARK,
    COLOR_SECONDARY,
    COLOR_SURFACE,
    COLOR_TEXT_MUTED,
    axis,
    base_layout,
    empty_figure,
    hover_columns,
    mix_figure,
    padded_range,
    share_label,
    trend_figure,
)

# `share_label`은 막대 안에 적을 문구 규칙이다. 수익 비중 막대와 같은
# 규칙이라 `dashboard.figures`에 있고, 이 탭은 그것을 그대로 쓴다
# (→ tabs/asset/__init__.py 의 _mix_slot_values).

# 자산 구성 막대의 상품별 색. 6개를 한눈에 구분하되 주색상을 과하게 쓰지
# 않는다. 순서는 상품 순서와 같다(→ data.ASSET_SHARE_COLUMNS).
MIX_COLORS = (
    COLOR_PRIMARY,
    COLOR_PRIMARY_DARK,
    "#F0B26B",
    COLOR_SECONDARY,
    "#7E9FC3",
    "#A0A6A8",
)

# 증감 히트맵의 색. 늘면 붉게, 줄면 푸르게, 0은 흰색이다.
# 색만으로 읽지 않도록 칸마다 숫자를 함께 적는다.
HEATMAP_SCALE = (
    (0.0, COLOR_ACCENT_DARK),
    (0.5, COLOR_SURFACE),
    (1.0, COLOR_PRIMARY_DARK),
)


# --- 1. 자산 추이 ------------------------------------------------------------
def create_asset_trend_figure(
    trend: pd.DataFrame,
    branch_name: str,
    measure_label: str,
    unit_label: str,
    to_text,
    to_delta_text,
) -> go.Figure:
    """전체와 선택 지점의 월별 자산 추이."""
    if trend.empty:
        return empty_figure()

    formatters = (("value", to_text), ("delta", to_delta_text))
    return trend_figure(
        trend,
        branch_name,
        f"{TOTAL_LABEL} {measure_label}({unit_label})",
        f"{branch_name} {measure_label}({unit_label})",
        {
            scope: hover_columns(trend, scope, formatters)
            for scope in ("total", "branch")
        },
        f"<br>{measure_label}: %{{customdata[0]}}"
        "<br>전월 대비: %{customdata[1]}",
    )


# --- 2. 자산 규모와 증가율 ---------------------------------------------------
def create_asset_growth_figure(
    scatter: pd.DataFrame,
    median_assets: float | None,
    start_month: str | None = None,
    end_month: str | None = None,
) -> go.Figure:
    """지점별 순자산과 증가율 산점도.

    기준선 두 개가 사분면을 만든다. 가로는 증가·감소, 세로는 규모
    많음·적음이다.
    """
    if scatter.empty:
        return empty_figure()

    start_label = (
        fmt.format_month(start_month) if start_month else "시작 시점"
    )
    end_label = fmt.format_month(end_month) if end_month else "기준 월"

    figure = go.Figure(
        go.Scatter(
            x=scatter["net_assets_end"],
            y=scatter["net_assets_growth"],
            mode="markers+text",
            name="영업점",
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
                        fmt.format_assets(value)
                        for value in scatter["net_assets_start"]
                    ],
                    [
                        fmt.format_assets(value)
                        for value in scatter["net_assets_end"]
                    ],
                    [
                        fmt.format_signed_percent(value)
                        for value in scatter["net_assets_growth"]
                    ],
                ],
                axis=-1,
            ),
            hovertemplate=(
                "<b>%{customdata[0]}</b>"
                f"<br>{start_label}: %{{customdata[1]}}"
                f"<br>{end_label}: %{{customdata[2]}}"
                "<br>증가율: %{customdata[3]}<extra></extra>"
            ),
        )
    )

    values = pd.to_numeric(
        scatter["net_assets_end"], errors="coerce"
    ).dropna()
    x_range = None
    if not values.empty:
        margin = max(
            (values.max() - values.min()) * 0.08, values.max() * 0.02
        )
        x_range = [
            float(max(0.0, values.min() - margin)),
            float(values.max() + margin),
        ]

    figure.update_layout(
        **base_layout(
            showlegend=False,
            margin={"l": 92, "r": 32, "t": 40, "b": 56},
            dragmode="pan",
        ),
        xaxis=axis("순자산(억원)", tickformat=",.0f", range=x_range),
        yaxis=axis(
            "순자산 증가율(전년 동월대비, YoY%)",
            ticksuffix="%",
            zeroline=False,
        ),
    )
    figure.add_hline(
        y=0,
        line={"color": COLOR_AXIS, "width": 1, "dash": "dash"},
        annotation={
            "text": "증가율 0%",
            "font": {"size": 10, "color": COLOR_TEXT_MUTED},
        },
        annotation_position="right",
    )
    if median_assets and median_assets > 0:
        figure.add_shape(
            type="line",
            xref="x",
            yref="paper",
            x0=median_assets,
            x1=median_assets,
            y0=0,
            y1=1,
            line={"color": COLOR_AXIS, "width": 1, "dash": "dash"},
        )
        figure.add_annotation(
            xref="x",
            yref="paper",
            x=median_assets,
            y=1.06,
            text=f"순자산 중앙값 {fmt.format_assets(median_assets)}",
            showarrow=False,
            font={"size": 10, "color": COLOR_TEXT_MUTED},
        )
    return figure


# --- 3. 자산 구성 ------------------------------------------------------------
def create_asset_mix_figure(
    mix: pd.DataFrame, labels: tuple[str, ...]
) -> go.Figure:
    """구분별 자산 구성 100% 누적 세로 막대.

    첫 막대가 전체, 나머지가 고른 지점이다. 그림 골격은 수익 비중과 같아
    `dashboard.figures.mix_figure`에 있다. 여기서는 이 탭의 색과 이름만
    정한다.
    """
    return mix_figure(mix, labels, MIX_COLORS, "구성 비중(%)", "상품")


# --- 4. 상품 비중 비교 -------------------------------------------------------
# 산점도 축 여백. 값이 놓인 구간의 이 비율만큼 양쪽으로 넓힌다. 점 위에
# 얹은 지점 이름이 축 끝에서 잘리지 않을 만큼만 준다.
SCATTER_PADDING = 0.12


def create_mix_scatter_figure(
    scatter: pd.DataFrame, x_label: str, y_label: str
) -> go.Figure:
    """두 상품 비중을 지점마다 짝지은 산점도.

    같은 상품을 고르면 모든 점이 대각선 위에 놓인다. 그 선을 함께 그려
    어느 쪽으로 치우쳤는지 바로 읽히게 한다.
    """
    if scatter.empty:
        return empty_figure()

    figure = go.Figure(
        go.Scatter(
            x=scatter["x"],
            y=scatter["y"],
            mode="markers+text",
            name="영업점",
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
                    [fmt.format_percent(value) for value in scatter["x"]],
                    [fmt.format_percent(value) for value in scatter["y"]],
                ],
                axis=-1,
            ),
            hovertemplate=(
                "<b>%{customdata[0]}</b>"
                f"<br>{x_label}: %{{customdata[1]}}"
                f"<br>{y_label}: %{{customdata[2]}}<extra></extra>"
            ),
        )
    )

    # 축 범위는 축마다 그 축의 값에 맞춘다. 두 축에 같은 범위를 쓰면
    # 값이 좁게 모인 축이 화면의 절반만 쓰게 되고, 점 위에 얹은 지점
    # 이름이 그 좁은 띠 안에 겹쳐 쌓인다. 패널이 가로로 넓고 세로로
    # 짧아서 세로축이 특히 그렇다.
    x_range = padded_range(scatter["x"], SCATTER_PADDING)
    y_range = padded_range(scatter["y"], SCATTER_PADDING)

    # 동일 비중선. 두 축 범위를 모두 덮게 그으면 Plotly가 보이는 구간만
    # 남기고 자른다. 축 범위가 서로 달라 45도로 보이지는 않으므로
    # 무슨 선인지 끝에 적는다.
    if x_range and y_range:
        low = min(x_range[0], y_range[0])
        high = max(x_range[1], y_range[1])
        figure.add_shape(
            type="line",
            x0=low,
            y0=low,
            x1=high,
            y1=high,
            line={"color": COLOR_GRID, "width": 1, "dash": "dash"},
            layer="below",
        )
        # 선이 화면 안에 남는 구간의 위쪽 끝에 붙인다.
        edge = min(x_range[1], y_range[1])
        if edge > max(x_range[0], y_range[0]):
            figure.add_annotation(
                x=edge,
                y=edge,
                text="동일 비중",
                showarrow=False,
                xanchor="right",
                yanchor="bottom",
                font={"size": 10, "color": COLOR_TEXT_MUTED},
            )

    figure.update_layout(
        **base_layout(
            showlegend=False,
            margin={"l": 92, "r": 32, "t": 32, "b": 56},
            dragmode="pan",
        ),
        xaxis=axis(f"{x_label} 비중(%)", ticksuffix="%", range=x_range),
        yaxis=axis(f"{y_label} 비중(%)", ticksuffix="%", range=y_range),
    )
    return figure


# --- 5. 상품 구성별 증감 -----------------------------------------------------
def create_change_heatmap_figure(
    matrix: pd.DataFrame, scope: str
) -> go.Figure:
    """상품 × 월 전월 대비 증감율 히트맵.

    색은 늘면 붉게 줄면 푸르게 하되, 색만으로 읽지 않도록 칸마다 숫자를
    적는다. 색 범위는 데이터의 최대 절댓값으로 잡아 0이 항상 흰색에 오게
    한다. 고정 범위를 쓰면 변동이 작은 달이 전부 흰색이 된다.
    """
    if matrix.empty:
        return empty_figure()

    values = matrix.to_numpy(dtype=float)
    # 원본에 없는 분류는 빈 줄로 남으므로 결측을 빼고 최대 절댓값을 찾는다.
    known = np.abs(values[~np.isnan(values)])
    limit = float(known.max()) if known.size else 0.0
    limit = limit if limit > 0 else 1.0
    labels = [fmt.format_month_short(month) for month in matrix.columns]

    figure = go.Figure(
        go.Heatmap(
            z=values,
            x=labels,
            y=[str(name) for name in matrix.index],
            colorscale=[list(stop) for stop in HEATMAP_SCALE],
            zmid=0,
            zmin=-limit,
            zmax=limit,
            xgap=1,
            ygap=1,
            colorbar={
                "title": {
                    "text": "증감율(%)",
                    "font": {"size": 11, "color": COLOR_TEXT_MUTED},
                },
                "tickfont": {"size": 10, "color": COLOR_TEXT_MUTED},
                "ticksuffix": "%",
                "outlinewidth": 0,
                "thickness": 12,
            },
            text=[
                [
                    "" if np.isnan(value) else f"{value:+.1f}"
                    for value in row
                ]
                for row in values
            ],
            texttemplate="%{text}",
            textfont={"size": 9},
            hovertemplate=(
                f"<b>%{{y}}</b><br>구분: {scope}"
                "<br>기준 월: %{x}"
                "<br>전월 대비: %{z:+.1f}%<extra></extra>"
            ),
        )
    )
    figure.update_layout(
        **base_layout(
            showlegend=False, margin={"l": 108, "r": 32, "t": 24, "b": 48}
        ),
        xaxis=axis(showgrid=False),
        # 원본 행 순서대로 위에서 아래로 읽히게 뒤집는다.
        yaxis=axis(None, showgrid=False, autorange="reversed"),
    )
    return figure


# --- 6. 연금 추이 ------------------------------------------------------------
def create_pension_trend_figure(
    trend: pd.DataFrame,
    branch_name: str,
    product_label: str,
    measure_label: str,
    unit_label: str,
    to_text,
    to_delta_text,
) -> go.Figure:
    """전체와 선택 지점의 월별 연금 추이.

    자산 추이 패널과 같은 골격을 쓴다. 고른 지표가 자산이든 1인 평균이든
    가입 고객 수를 함께 실어, 값이 움직인 것이 가입자가 늘어서인지 1인당
    금액이 커져서인지 hover 한 번으로 견줄 수 있게 한다.

    지표 이름과 단위는 인자로 받는다. 여기 적어 두면 지표가 늘 때마다
    탭 선언과 이 함수 두 곳을 고쳐야 한다(→ tabs.asset.PENSION_MEASURES).
    """
    if trend.empty:
        return empty_figure()

    unit = f"{product_label} {measure_label}({unit_label})"
    formatters = (
        ("value", to_text),
        ("delta", to_delta_text),
        ("count", fmt.format_count),
    )
    return trend_figure(
        trend,
        branch_name,
        f"{TOTAL_LABEL} {unit}",
        f"{branch_name} {unit}",
        {
            scope: hover_columns(trend, scope, formatters)
            for scope in ("total", "branch")
        },
        f"<br>{product_label} {measure_label}: %{{customdata[0]}}"
        "<br>전월 대비: %{customdata[1]}"
        "<br>가입 고객 수: %{customdata[2]}",
    )
