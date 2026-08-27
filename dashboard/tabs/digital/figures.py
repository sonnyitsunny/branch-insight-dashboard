"""디지털 채널 탭의 Figure 생성.

데이터를 직접 조회하지 않는다. 계산이 끝난 프레임을 받아 Figure만
만든다(→ AGENTS.md §12). 색과 글꼴은 공통 토큰에서 가져온다.
"""

from __future__ import annotations

import math

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

# 메뉴 산점도의 점 색. 한 그림에 한 분류만 그려 계열이 하나뿐이라 가를
# 색이 없다. 지점 산점도와 같은 보조색을 쓴다.
COLOR_MENU_POINT = figures.COLOR_SECONDARY

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

# 메뉴 산점도의 가로 여백 비율. 지점 이름보다 메뉴 이름이 길어 좌우로 더
# 넓게 잡아야 양 끝의 글자가 잘리지 않는다.
MENU_PADDING = 0.22

# 로그 눈금일 때의 가로 여백 비율. 로그 축의 여백은 값의 차이가 아니라
# 자릿수의 차이로 잰다. 위와 같은 비율을 쓰면 여백이 몇 배로 벌어져
# 점들이 가운데로 몰린다(→ _log_padded).
MENU_LOG_PADDING = 0.10

# 메뉴 산점도의 세로축 이름. 축과 hover가 같은 이름을 쓰도록 한 곳에 적는다.
# 이용일수 그림과 같은 지표 이름이다(→ USAGE_DAYS_MEASURE).
MENU_ACTIVATION_MEASURE = "거래활성화"

# 조회수 축 이름. 로그 눈금일 때는 그 사실을 이름에 적는다. 적지 않으면
# 같은 거리를 같은 차이로 읽어 아래 순위 메뉴들의 차이를 크게 본다.
MENU_VIEW_TITLE = "조회수(건)"
MENU_VIEW_LOG_TITLE = "조회수(건, 로그변환)"

# 로그 축에 세울 눈금 자리. 한 자릿수 안에서 1·2·5배 자리에만 선을 둔다.
#
# **Plotly에 맡기지 않는다.** 맡겨 두면 한 자릿수를 1·2·3…9로 잘게 나눠
# 세로선이 스무 개 넘게 서고 축 아래 숫자가 서로 붙는다. 그렇다고 자릿수
# 마다 하나만 두면 선이 두어 개뿐이라 점이 어디쯤인지 가늠할 수 없다.
# 1·2·5는 그 사이를 고른 값이며, 조회 건수가 100배쯤 벌어진 이 그림에서
# 선이 예닐곱 개 선다.
MENU_LOG_STEPS = (1, 2, 5)

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
        xaxis=figures.axis(showgrid=False),
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


# 이용일수 그림의 세로축 이름. 축과 hover가 같은 이름을 쓰도록 한 곳에
# 적는다. 카드 제목도 이 이름을 따른다
# (→ tabs/digital/__init__.py 의 usage-days 카드).
USAGE_DAYS_MEASURE = "거래활성화"


def create_usage_days_figure(
    days: pd.DataFrame, groups: tuple, scope: str
) -> go.Figure:
    """이용일수 구간(가로)별 거래활성화(세로). 채널마다 선 하나.

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
                    f"<br>{channel} {USAGE_DAYS_MEASURE}: %{{customdata}}"
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
            f"{USAGE_DAYS_MEASURE}(%)",
            ticksuffix="%",
            rangemode="tozero",
        ),
    )
    return figure


def create_menu_scatter_figure(
    scatter: pd.DataFrame, label: str, scope: str
) -> go.Figure:
    """메뉴 조회 건수(가로)와 그 메뉴 조회고객의 거래활성화(세로) 산점도.

    한 점이 메뉴 하나다. 오른쪽 위에 있을수록 많이 보고 거래까지 이어진
    메뉴이고, 오른쪽 아래는 많이 보지만 거래로 이어지지 않는 메뉴다.

    **점 위에 메뉴 이름을 적는다.** 순위 숫자만 적으면 어느 메뉴인지 알려고
    매번 hover해야 한다.

    **가로축은 로그 눈금이다.** 1위와 끝 순위의 조회 건수가 수십 배
    차이 나서, 선형 눈금에서는 아래 순위 메뉴 대부분이 왼쪽 끝 한자리에
    뭉쳐 서로 갈리지 않는다. 로그 눈금은 같은 거리를 같은 배수로 그리므로
    그 뭉친 자리가 펴진다(→ _view_axis).

    남는 자리에서 이름은 여전히 겹칠 수 있다. 확대하면 점이 벌어지면서
    글자도 갈라지고(→ Chart.zoomable), 위아래를 번갈아 적어 겹치는 정도를
    줄인다(→ _label_positions).
    """
    if scatter.empty:
        return figures.empty_figure()

    figure = go.Figure()
    figure.add_trace(
        go.Scatter(
            x=scatter["view_count"],
            y=scatter["trade_conversion_share"],
            name=label,
            mode="markers+text",
            text=scatter["menu_name"].astype(str),
            textposition=_label_positions(len(scatter)),
            textfont={"size": 9, "color": figures.COLOR_TEXT_MUTED},
            marker={
                "color": COLOR_MENU_POINT,
                "size": POINT_SIZE,
                "symbol": "circle",
                "opacity": 0.85,
                "line": {"color": figures.COLOR_SURFACE, "width": 1},
            },
            customdata=np.stack(
                [
                    scatter["menu_name"].astype(str),
                    [
                        fmt.format_number(value)
                        for value in scatter["menu_rank"]
                    ],
                    [
                        fmt.format_number(value)
                        for value in scatter["view_count"]
                    ],
                    [
                        fmt.format_percent(value)
                        for value in scatter["trade_conversion_share"]
                    ],
                ],
                axis=-1,
            ),
            hovertemplate=(
                "<b>%{customdata[0]}</b>"
                f"<br>구분: {scope} · {label}"
                "<br>순위: %{customdata[1]}위"
                "<br>조회수: %{customdata[2]}건"
                f"<br>{MENU_ACTIVATION_MEASURE}: %{{customdata[3]}}"
                "<extra></extra>"
            ),
        )
    )
    figure.update_layout(
        **figures.base_layout(
            margin={"l": 88, "r": 32, "t": 24, "b": 56},
            dragmode="pan",
            showlegend=False,
        ),
        xaxis=_view_axis(scatter["view_count"]),
        yaxis=figures.axis(
            f"{MENU_ACTIVATION_MEASURE}(%)",
            ticksuffix="%",
            range=_padded(scatter["trade_conversion_share"]),
        ),
    )
    return figure


def _label_positions(count: int) -> list[str]:
    """점 위에 적는 이름의 자리. 위아래를 번갈아 놓는다.

    메뉴 이름은 점보다 넓어 이웃한 점끼리 글자가 겹친다. 한 칸씩 위아래로
    갈라 놓으면 겹치는 자리가 절반으로 준다. 완전히 없애지는 못하므로
    몰린 자리는 확대해서 본다(→ create_menu_scatter_figure).
    """
    return [
        "top center" if index % 2 == 0 else "bottom center"
        for index in range(count)
    ]


def _channels_in(days: pd.DataFrame) -> list[str]:
    """그림에 그릴 채널. 데이터에 나온 차례를 그대로 쓴다."""
    return list(dict.fromkeys(days["channel"].astype(str)))


def _view_axis(values) -> dict:
    """조회수 가로축. 값이 모두 양수면 로그 눈금으로 그린다.

    **로그는 양수에서만 뜻이 있다.** 조회수가 0인 메뉴가 섞이면 Plotly가
    그 점을 아무 말 없이 빼고 그린다. 점 하나가 사라진 그림은 뭉친
    그림보다 위험하므로, 그때는 선형 눈금으로 되돌려 전부 그린다
    (→ AGENTS.md §9).
    """
    numbers = _numbers(values)
    if numbers.empty or float(numbers.min()) <= 0:
        return figures.axis(
            MENU_VIEW_TITLE,
            tickformat=",.0f",
            # 이름이 점보다 넓어 축 끝에서 잘린다. 좌우 여백을 더 준다.
            range=_padded(values, MENU_PADDING),
        )
    low, high = _log_padded(numbers, MENU_LOG_PADDING)
    ticks = _log_ticks(low, high)
    return figures.axis(
        MENU_VIEW_LOG_TITLE,
        type="log",
        # 눈금에 적히는 숫자는 로그를 씌우기 전의 조회 건수 그대로다.
        tickformat=",.0f",
        # 눈금 자리를 직접 적는다. 두 개도 못 세울 만큼 값이 몰린 그림에서만
        # Plotly에 맡긴다. 그 폭에서는 잘게 나눠도 숫자가 붙지 않는다.
        **(
            {"tickmode": "array", "tickvals": ticks}
            if len(ticks) >= 2
            else {}
        ),
        # 자릿수 사이의 잔금은 끈다. 선만 있고 숫자가 없어 무엇을 가리키는
        # 선인지 알 수 없다.
        minor={"showgrid": False, "ticks": ""},
        range=[low, high],
    )


def _log_ticks(low: float, high: float) -> list[float]:
    """로그 축에 세울 눈금 값. **로그를 씌우기 전의 값으로 적는다.**

    Plotly는 같은 축의 `range`를 자릿수로, `tickvals`를 데이터 값 그대로
    읽는다. 둘의 단위가 달라 한쪽 기준으로 적으면 눈금이 축 밖으로 나간다.

    `low`·`high`는 자릿수다(→ _log_padded).
    """
    ticks: list[float] = []
    for exponent in range(math.floor(low), math.ceil(high) + 1):
        for step in MENU_LOG_STEPS:
            value = float(step) * 10.0**exponent
            if low <= math.log10(value) <= high:
                ticks.append(value)
    return ticks


def _log_padded(numbers: pd.Series, ratio: float) -> list[float]:
    """로그 축의 범위. **자릿수(log10)로 적는다.**

    Plotly의 로그 축은 `range`를 값이 아니라 그 값의 log10으로 읽는다.
    조회 건수를 그대로 넣으면 축이 엉뚱하게 멀리 벌어진다.

    값이 모두 같아 폭이 0이면 그 값 앞뒤로 반 자릿수씩 준다. 여백이 없으면
    점이 축 끝에 붙는다.
    """
    low = float(np.log10(float(numbers.min())))
    high = float(np.log10(float(numbers.max())))
    span = high - low
    padding = span * ratio if span > 0 else 0.5
    return [low - padding, high + padding]


def _numbers(values) -> pd.Series:
    """숫자로 읽히는 값만 남긴 계열. 읽을 수 없는 값은 뺀다."""
    return pd.to_numeric(
        pd.Series(list(values)), errors="coerce"
    ).dropna()


def _padded(values, ratio: float = POINT_PADDING) -> list[float] | None:
    """값이 움직인 구간에 여백을 더한 축 범위.

    `figures.padded_range`를 쓰지 않는다. 그쪽은 아래를 0에서 자르는데,
    여기서는 값이 몰려 있어도 그 구간만 크게 보여야 한다.
    """
    numbers = _numbers(values)
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
    "COLOR_MENU_POINT",
    "COLOR_PICKED",
    "COLOR_SHARE",
    "MENU_ACTIVATION_MEASURE",
    "MENU_LOG_PADDING",
    "MENU_LOG_STEPS",
    "MENU_PADDING",
    "MENU_VIEW_LOG_TITLE",
    "MENU_VIEW_TITLE",
    "create_activation_figure",
    "create_channel_trend_figure",
    "create_menu_scatter_figure",
    "create_usage_days_figure",
]
