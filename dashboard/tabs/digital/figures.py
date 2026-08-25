"""디지털 채널 탭의 Figure 생성.

데이터를 직접 조회하지 않는다. 계산이 끝난 프레임을 받아 Figure만
만든다(→ AGENTS.md §12). 색과 글꼴은 공통 토큰에서 가져온다.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from dashboard import figures
from dashboard import format as fmt

# 월별 추이의 두 계열. 막대가 인원수(왼쪽 축), 선이 비중(오른쪽 축)이다.
# 다른 탭의 추이 그림과 같은 짝이라 같은 색을 쓴다(→ figures.trend_figure).
COLOR_COUNT = figures.COLOR_SECONDARY_LIGHT
COLOR_SHARE = figures.COLOR_PRIMARY

# 지점을 모두 한 무리로 늘어놓는 산점도의 점 색. 여기에 주색상을 쓰면
# 화면이 주황으로 덮인다(→ AGENTS.md §5.2). 다른 탭의 지점 산점도와
# 같은 색이다(→ returns.figures).
COLOR_BRANCH_GROUP = figures.COLOR_SECONDARY
# 그 무리 속에서 눈이 가야 할 하나 — 지금 고른 대상 — 를 찍는 색.
# 색만으로 구분하지 않는다. 점 위에 이름이 적히고 모양도 다르다.
COLOR_PICKED = figures.COLOR_PRIMARY

# 채널마다 다른 색. 세 선을 한 그림에 겹치므로 서로 구분되어야 한다.
# 범례에 이름이 적히므로 색만으로 구분되지 않는다(→ AGENTS.md §5.2).
CHANNEL_COLORS: dict[str, str] = {
    "HTS": figures.COLOR_SECONDARY,
    "MTS": figures.COLOR_PRIMARY,
    "WEB": figures.COLOR_ACCENT,
}
# 채널마다 다른 점 모양. 흑백으로 인쇄해도 세 선이 갈린다.
CHANNEL_SYMBOLS: dict[str, str] = {
    "HTS": "circle",
    "MTS": "diamond",
    "WEB": "square",
}

# 산점도 점 크기. 고른 대상은 하나뿐인 기준점이라 조금 크게 그린다.
POINT_SIZE = 11
PICKED_POINT_SIZE = 15

# 축 여백 비율. 점 위에 얹은 이름이 축 끝에서 잘리지 않을 만큼만 준다.
POINT_PADDING = 0.14

# 이름을 점 위에 적을 최대 지점 수. 이보다 많으면 글자가 서로 겹쳐
# 읽을 수 없으므로 고른 대상만 적고 나머지는 hover로 읽는다.
NAME_LIMIT = 40


def create_channel_trend_figure(
    trend: pd.DataFrame, channel: str, scope: str
) -> go.Figure:
    """한 채널의 월별 이용 고객 수(막대)와 이용 비중(선).

    두 값의 단위가 달라 축을 둘로 나눈다. 인원수는 왼쪽, 비중은 오른쪽이다.
    비중 축은 0부터 그리지 않는다. 규모가 크고 변화가 작아 0부터 그리면
    움직임이 보이지 않는다(→ figures.trend_figure).
    """
    if trend.empty:
        return figures.empty_figure()

    labels = [
        fmt.format_month_short(month) for month in trend["base_month"]
    ]
    counts = [
        None if pd.isna(value) else float(value)
        for value in trend["user_count"]
    ]
    shares = [
        None if pd.isna(value) else float(value)
        for value in trend["user_share"]
    ]
    hover = (
        f"<br>{channel} 이용고객: %{{customdata[0]}}"
        f"<br>{channel} 이용비중: %{{customdata[1]}}"
    )
    customdata = np.stack(
        [
            [fmt.format_count(value) for value in counts],
            [fmt.format_percent(value) for value in shares],
        ],
        axis=-1,
    )

    figure = go.Figure()
    figure.add_trace(
        go.Bar(
            x=labels,
            y=counts,
            name=f"{channel} 이용고객 수",
            marker={"color": COLOR_COUNT, "line": {"width": 0}},
            customdata=customdata,
            hovertemplate=(
                f"<b>%{{x}}</b><br>구분: {scope}{hover}<extra></extra>"
            ),
        )
    )
    figure.add_trace(
        go.Scatter(
            x=labels,
            y=shares,
            name=f"{channel} 이용비중",
            yaxis="y2",
            mode="lines+markers",
            line={"color": COLOR_SHARE, "width": 2.5},
            marker={
                "color": COLOR_SHARE,
                "size": 8,
                "symbol": "diamond",
                "line": {"color": figures.COLOR_SURFACE, "width": 1.5},
            },
            customdata=customdata,
            hovertemplate=(
                f"<b>%{{x}}</b><br>구분: {scope}{hover}<extra></extra>"
            ),
        )
    )
    figure.update_layout(
        **figures.base_layout(
            margin={"l": 92, "r": 92, "t": 24, "b": 48},
            hovermode="x unified",
        ),
        bargap=0.35,
        xaxis=figures.axis("기준 월", showgrid=False),
        yaxis=figures.axis(
            "이용고객 수(명)",
            tickformat=",.0f",
            range=figures.padded_range(trend["user_count"]),
        ),
        yaxis2=figures.axis(
            "이용비중(%)",
            overlaying="y",
            side="right",
            showgrid=False,
            ticksuffix="%",
            range=figures.padded_range(trend["user_share"]),
        ),
    )
    return figure


def create_activation_figure(
    scatter: pd.DataFrame, channel: str, scope: str
) -> go.Figure:
    """채널 이용 비중(가로)과 거래활성화율(세로)의 지점 산점도.

    지금 고른 대상은 계열을 나눠 다른 색·모양으로 찍고 이름을 적는다.
    범례에 이름이 남으므로 색만으로 구분되지 않는다(→ AGENTS.md §5.2).
    """
    if scatter.empty:
        return figures.empty_figure()

    picked = scatter["branch_name"].astype(str) == scope
    figure = go.Figure()
    for is_picked, rows in (
        (False, scatter[~picked]),
        (True, scatter[picked]),
    ):
        if rows.empty:
            continue
        figure.add_trace(
            _scatter_trace(rows, is_picked, scope, channel, len(scatter))
        )

    figure.update_layout(
        **figures.base_layout(
            margin={"l": 88, "r": 32, "t": 24, "b": 56},
            dragmode="pan",
        ),
        xaxis=figures.axis(
            f"{channel} 이용비중(%)",
            ticksuffix="%",
            range=_padded(scatter["user_share"]),
        ),
        yaxis=figures.axis(
            "거래활성화(%)",
            ticksuffix="%",
            range=_padded(scatter["activation"]),
        ),
    )
    return figure


def _scatter_trace(
    rows: pd.DataFrame,
    is_picked: bool,
    scope: str,
    channel: str,
    total_points: int,
) -> go.Scatter:
    """산점도 계열 하나. 고른 대상만 이름을 늘 적는다.

    지점이 많으면 이름이 서로 겹쳐 읽을 수 없다. 그때는 고른 대상만 적고
    나머지는 hover로 읽게 한다(→ NAME_LIMIT).
    """
    names = rows["branch_name"].astype(str)
    shows_name = is_picked or total_points <= NAME_LIMIT
    return go.Scatter(
        x=rows["user_share"],
        y=rows["activation"],
        name=scope if is_picked else "지점",
        mode="markers+text" if shows_name else "markers",
        text=names if shows_name else None,
        textposition="top center",
        textfont={
            "size": 10 if is_picked else 9,
            "color": (
                COLOR_PICKED if is_picked else figures.COLOR_TEXT_MUTED
            ),
        },
        marker={
            "color": COLOR_PICKED if is_picked else COLOR_BRANCH_GROUP,
            "size": PICKED_POINT_SIZE if is_picked else POINT_SIZE,
            "symbol": "diamond" if is_picked else "circle",
            "opacity": 1.0 if is_picked else 0.85,
            "line": {"color": figures.COLOR_SURFACE, "width": 1},
        },
        customdata=np.stack(
            [
                names,
                [fmt.format_percent(value) for value in rows["user_share"]],
                [fmt.format_percent(value) for value in rows["activation"]],
            ],
            axis=-1,
        ),
        hovertemplate=(
            "<b>%{customdata[0]}</b>"
            f"<br>{channel} 이용비중: %{{customdata[1]}}"
            "<br>거래활성화: %{customdata[2]}<extra></extra>"
        ),
    )


def create_usage_days_figure(
    days: pd.DataFrame, groups: tuple, scope: str
) -> go.Figure:
    """이용일수 구간(가로)별 채널 이용 비중(세로). 채널마다 선 하나.

    구간 차례는 데이터 계층이 정한 순서를 그대로 쓴다. 가나다순으로 다시
    세우면 적게 쓴 쪽부터라는 뜻이 사라진다.
    """
    if days.empty:
        return figures.empty_figure()

    figure = go.Figure()
    for channel in _channels_in(days):
        rows = days[days["channel"] == channel]
        if rows.empty:
            continue
        figure.add_trace(
            go.Scatter(
                x=rows["usage_day_group"].astype(str),
                y=rows["day_group_share"],
                name=channel,
                mode="lines+markers",
                line={
                    "color": CHANNEL_COLORS.get(
                        channel, figures.COLOR_SECONDARY
                    ),
                    "width": 2.5,
                },
                marker={
                    "color": CHANNEL_COLORS.get(
                        channel, figures.COLOR_SECONDARY
                    ),
                    "size": 9,
                    "symbol": CHANNEL_SYMBOLS.get(channel, "circle"),
                    "line": {
                        "color": figures.COLOR_SURFACE,
                        "width": 1.5,
                    },
                },
                customdata=[
                    fmt.format_percent(value)
                    for value in rows["day_group_share"]
                ],
                hovertemplate=(
                    f"<b>%{{x}}</b><br>구분: {scope}"
                    f"<br>{channel} 이용비중: %{{customdata}}"
                    "<extra></extra>"
                ),
            )
        )

    figure.update_layout(
        **figures.base_layout(margin={"l": 76, "r": 32, "t": 24, "b": 64}),
        xaxis=figures.axis(
            "이용일수 구간",
            showgrid=False,
            categoryorder="array",
            categoryarray=[str(name) for name in groups],
        ),
        yaxis=figures.axis(
            "이용비중(%)", ticksuffix="%", rangemode="tozero"
        ),
    )
    return figure


def _channels_in(days: pd.DataFrame) -> list[str]:
    """그림에 그릴 채널. 데이터에 나온 차례를 그대로 쓴다."""
    return list(dict.fromkeys(days["channel"].astype(str)))


def _padded(values, ratio: float = POINT_PADDING) -> list[float] | None:
    """값이 움직인 구간에 여백을 더한 축 범위.

    `figures.padded_range`를 쓰지 않는다. 그쪽은 아래를 0에서 자르는데,
    여기서는 값이 몰려 있어도 그 구간만 크게 보여야 한다.
    """
    numbers = pd.to_numeric(
        pd.Series(list(values)), errors="coerce"
    ).dropna()
    if numbers.empty:
        return None
    low, high = float(numbers.min()), float(numbers.max())
    span = high - low
    padding = span * ratio if span > 0 else max(abs(high) * 0.1, 1.0)
    return [low - padding, high + padding]


__all__ = [
    "CHANNEL_COLORS",
    "CHANNEL_SYMBOLS",
    "COLOR_BRANCH_GROUP",
    "COLOR_COUNT",
    "COLOR_PICKED",
    "COLOR_SHARE",
    "create_activation_figure",
    "create_channel_trend_figure",
    "create_usage_days_figure",
]
