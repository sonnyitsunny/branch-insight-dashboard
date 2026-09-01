"""수익률 탭의 Figure 생성.

데이터를 직접 조회하지 않는다. 계산이 끝난 프레임을 받아 Figure만
만든다(→ AGENTS.md §12). 색과 글꼴은 공통 토큰에서 가져온다.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from dashboard import figures
from dashboard import format as fmt
from dashboard.data import TOTAL_LABEL
from dashboard.tabs.returns import metrics

# '전체' 색. 어느 탭에서나 '전체'는 같은 연한 파랑이다
# (→ customer.figures, transaction.figures). 탭을 옮겨도 같은 것이 같은
# 색으로 보여야 한다.
COLOR_TOTAL = figures.COLOR_SECONDARY_LIGHT
# 고른 지점 색. '전체'와 나란히 놓고 견주는 그림에서 쓴다. 눈이 가야
# 할 것이 고른 지점이므로 주색상을 여기에 쓴다. 어느 탭에서나 같다.
COLOR_BRANCH = figures.COLOR_PRIMARY
# 지점을 모두 한 무리로 늘어놓는 산점도의 점 색. 여기에 주색상을
# 쓰면 화면이 주황으로 덮인다(→ AGENTS.md §5.2). 이런 그림에는 견주는
# 짝이 되는 '고른 지점' 계열이 없으므로 위 색과 섞이지 않는다. 다른
# 탭의 지점 산점도와 같은 색을 쓴다(→ customer.figures, asset.figures).
COLOR_BRANCH_GROUP = figures.COLOR_SECONDARY
# 같은 무리를 막대로 늘어놓는 그림의 막대 색. 점과 달리 막대는 넓은
# 면을 채워서, 남색으로 스물여덟 개를 세우면 카드가 어둡게 덮인다.
# 한 단계 연한 파랑으로 두어 면적이 커져도 화면이 무거워지지 않게
# 한다. 그 무리 속의 '전체' 하나는 아래 색으로 따로 찍는다.
COLOR_BRANCH_BAR = figures.COLOR_SECONDARY_LIGHT
# 그 무리 속에 섞인 '전체' 하나를 찍는 색. 위와 같은 파랑 계열로 두면
# 파란 막대·점 스물일곱 개에 묻혀 기준점이 보이지 않는다. 여기서는
# 주색상이 '전체'라는 뜻이 아니라 '이 그림에서 눈이 가야 할 하나'라는
# 뜻이며, 견줄 짝인 '고른 지점' 계열이 없어 COLOR_BRANCH와 마주치지
# 않는다. 색만으로 구분하지 않는다 — 축 눈금과 범례에 이름이 적히고
# 산점도는 점 모양도 다르다(→ AGENTS.md §5.2).
COLOR_TOTAL_MARK = figures.COLOR_PRIMARY

# 막대 위에 적는 값의 글자 크기. 막대가 좁아 기본 크기로는 옆 막대의
# 글씨와 붙는다.
BAR_TEXT_SIZE = 10

# 지점 이름 눈금을 눕히는 각도. 이름이 길면 가로로는 옆 눈금과 겹친다.
TICK_ANGLE = -45

# 산점도 점 크기. '전체'는 하나뿐인 기준점이라 조금 크게 그리고 모양도
# 달리해 색만으로 구분하지 않는다(→ AGENTS.md §5.2).
POINT_SIZE = 11
TOTAL_POINT_SIZE = 15

# 축 여백 비율. 막대 위에 적은 값과 점 위에 얹은 지점 이름이 축 끝에서
# 잘리지 않을 만큼만 준다.
BAR_PADDING = 0.18
POINT_PADDING = 0.14


def _padded(
    values, ratio: float, include: tuple[float, ...] = ()
) -> list[float] | None:
    """값이 움직인 구간에 여백을 더한 축 범위.

    `figures.padded_range`를 쓰지 않는다. 그쪽은 아래를 0에서 자르는데,
    수익률은 음수가 될 수 있어 그대로 쓰면 손실 막대가 통째로 잘린다.

    `include`에 넣은 값은 범위 안에 반드시 들어간다. 막대그래프는 0을
    넣어 기준선이 화면에 남게 한다.
    """
    numbers = pd.to_numeric(
        pd.Series(list(values)), errors="coerce"
    ).dropna()
    if numbers.empty:
        return None
    low = min(float(numbers.min()), *include) if include else float(
        numbers.min()
    )
    high = max(float(numbers.max()), *include) if include else float(
        numbers.max()
    )
    span = high - low
    padding = span * ratio if span > 0 else max(abs(high) * 0.1, 1.0)
    return [low - padding, high + padding]


def _rank_text(row) -> str:
    """hover에 적을 지점 순위. '전체'는 지점이 아니라 비운다."""
    if row[metrics.TOTAL_FLAG] or pd.isna(row["rank"]):
        return fmt.EMPTY_TEXT
    return f"{int(row['rank'])}위"


def create_return_rank_figure(
    rank: pd.DataFrame, measure_label: str
) -> go.Figure:
    """수익률이 높은 순으로 늘어놓은 세로 막대.

    왼쪽이 가장 높고 오른쪽으로 갈수록 낮아진다. 손실이 난 지점은 0선
    아래로 막대가 내려간다.

    막대가 하나뿐인 계열이라 범례를 두지 않는다. '전체'는 색이 다르지만
    축 눈금에 이름이 그대로 적히므로 색만으로 구분되지 않는다
    (→ AGENTS.md §5.2).

    지점이 많아 카드 폭에 들어가지 않으면 카드 안에서 가로로 스크롤한다.
    폭은 화면 쪽에서 정한다(→ registry.Chart.scroll_width).
    """
    if rank.empty:
        return figures.empty_figure()

    names = [str(name) for name in rank["branch_name"]]
    values = [
        None if pd.isna(value) else float(value)
        for value in rank["value"]
    ]
    colors = [
        COLOR_TOTAL_MARK if is_total else COLOR_BRANCH_BAR
        for is_total in rank[metrics.TOTAL_FLAG]
    ]
    count = metrics.branch_count(rank)
    figure = go.Figure(
        go.Bar(
            x=names,
            y=values,
            marker={"color": colors, "line": {"width": 0}},
            text=[fmt.format_signed_percent(value) for value in values],
            texttemplate="%{text}",
            textposition="outside",
            # 막대 위에 적은 값이 그래프 밖으로 나가도 지우지 않는다.
            cliponaxis=False,
            textfont={"size": BAR_TEXT_SIZE},
            customdata=np.stack(
                [
                    [
                        fmt.format_signed_percent(value)
                        for value in rank["value"]
                    ],
                    [
                        _rank_text(row)
                        for _index, row in rank.iterrows()
                    ],
                ],
                axis=-1,
            ),
            hovertemplate=(
                "<b>%{x}</b>"
                f"<br>{measure_label}: %{{customdata[0]}}"
                f"<br>영업점 순위: %{{customdata[1]}} / {count}곳"
                "<extra></extra>"
            ),
        )
    )
    figure.update_layout(
        **figures.base_layout(
            showlegend=False,
            margin={"l": 64, "r": 24, "t": 32, "b": 24},
        ),
        bargap=0.3,
        xaxis=figures.axis(
            None,
            showgrid=False,
            tickangle=TICK_ANGLE,
            categoryorder="array",
            categoryarray=names,
        ),
        yaxis=figures.axis(
            f"{measure_label}(%)",
            ticksuffix="%",
            range=_padded(rank["value"], BAR_PADDING, include=(0.0,)),
            # 손실이 난 지점이 어디부터인지 0선으로 가른다.
            zeroline=True,
            zerolinecolor=figures.COLOR_AXIS,
            zerolinewidth=1,
        ),
    )
    return figure


def create_return_scatter_figure(
    scatter: pd.DataFrame, x_label: str, y_label: str
) -> go.Figure:
    """두 기간의 수익률을 가로·세로에 놓은 산점도.

    기준선 두 개가 사분면을 만든다. 오른쪽 위는 두 기간 모두 이익,
    왼쪽 아래는 두 기간 모두 손실이다.

    '전체'는 계열을 나눠 그린다. 하나뿐인 기준점이라 범례에 이름이
    남아야 하고, 모양도 달라 색만으로 구분되지 않는다.
    """
    if scatter.empty:
        return figures.empty_figure()

    figure = go.Figure()
    for is_total, name, color, size, symbol in (
        (False, "영업점", COLOR_BRANCH_GROUP, POINT_SIZE, "circle"),
        (True, TOTAL_LABEL, COLOR_TOTAL_MARK, TOTAL_POINT_SIZE, "diamond"),
    ):
        rows = scatter[scatter[metrics.TOTAL_FLAG] == is_total]
        if rows.empty:
            continue
        figure.add_trace(
            go.Scatter(
                x=rows["x"],
                y=rows["y"],
                name=name,
                mode="markers+text",
                text=rows["branch_name"].astype(str),
                textposition="top center",
                textfont={
                    "size": 9,
                    "color": figures.COLOR_TEXT_MUTED,
                },
                marker={
                    "color": color,
                    "size": size,
                    "symbol": symbol,
                    "opacity": 0.9,
                    "line": {
                        "color": figures.COLOR_SURFACE,
                        "width": 1,
                    },
                },
                customdata=np.stack(
                    [
                        rows["branch_name"].astype(str),
                        [
                            fmt.format_signed_percent(value)
                            for value in rows["x"]
                        ],
                        [
                            fmt.format_signed_percent(value)
                            for value in rows["y"]
                        ],
                    ],
                    axis=-1,
                ),
                hovertemplate=(
                    "<b>%{customdata[0]}</b>"
                    f"<br>{x_label}: %{{customdata[1]}}"
                    f"<br>{y_label}: %{{customdata[2]}}"
                    "<extra></extra>"
                ),
            )
        )

    figure.update_layout(
        **figures.base_layout(
            margin={"l": 76, "r": 32, "t": 24, "b": 56},
            dragmode="pan",
        ),
        xaxis=figures.axis(
            f"{x_label}(%)",
            ticksuffix="%",
            range=_padded(scatter["x"], POINT_PADDING),
        ),
        yaxis=figures.axis(
            f"{y_label}(%)",
            ticksuffix="%",
            range=_padded(scatter["y"], POINT_PADDING),
        ),
    )
    # 이익과 손실을 가르는 기준선. 값이 모두 한쪽에 몰려 있으면 범위 밖에
    # 놓여 화면에 나타나지 않는다.
    line = {"color": figures.COLOR_AXIS, "width": 1, "dash": "dash"}
    figure.add_hline(y=0, line=line)
    figure.add_vline(x=0, line=line)
    return figure


def create_return_group_figure(
    distribution: pd.DataFrame, branch_name: str
) -> go.Figure:
    """'전체'와 고른 지점의 수익률 구간별 고객 비중(그룹형 막대).

    가로축은 손실이 큰 구간부터 이익이 큰 구간 순으로 늘어선다. 차례는
    데이터 계층이 정한다(→ data.RETURN_GROUPS).

    계열이 둘이라 범례를 둔다. '전체'는 어느 탭에서나 같은 색을 써서,
    탭이 바뀌어도 같은 것이 같은 색으로 보이게 한다(→ COLOR_TOTAL).
    """
    if distribution.empty:
        return figures.empty_figure()

    figure = go.Figure()
    colors = {TOTAL_LABEL: COLOR_TOTAL, branch_name: COLOR_BRANCH}
    groups = list(dict.fromkeys(distribution["return_group"]))
    for scope in (TOTAL_LABEL, branch_name):
        rows = distribution[distribution["scope"] == scope]
        if rows.empty:
            continue
        figure.add_trace(
            go.Bar(
                x=rows["return_group"],
                y=rows["share"],
                name=scope,
                marker={
                    "color": colors.get(scope, COLOR_BRANCH),
                    "line": {"width": 0},
                },
                customdata=np.stack(
                    [
                        [
                            fmt.format_count(value)
                            for value in rows["customer_count"]
                        ],
                        [
                            fmt.format_percent(value)
                            for value in rows["share"]
                        ],
                    ],
                    axis=-1,
                ),
                hovertemplate=(
                    f"<b>%{{x}}</b><br>구분: {scope}"
                    "<br>고객 수: %{customdata[0]}"
                    "<br>고객 비중: %{customdata[1]}<extra></extra>"
                ),
            )
        )

    figure.update_layout(
        **figures.base_layout(margin={"l": 76, "r": 24, "t": 24, "b": 72}),
        barmode="group",
        bargap=0.28,
        bargroupgap=0.08,
        xaxis=figures.axis(
            "수익률 구간",
            showgrid=False,
            tickangle=TICK_ANGLE,
            categoryorder="array",
            categoryarray=groups,
        ),
        yaxis=figures.axis(
            "고객 비중(%)", ticksuffix="%", rangemode="tozero"
        ),
    )
    return figure


def create_segment_return_figure(
    distribution: pd.DataFrame,
    branch_name: str,
    axis_title: str,
    measure_label: str,
    vertical: bool = False,
) -> go.Figure:
    """'전체'와 고른 지점의 구간별 수익률(그룹형 막대).

    기본은 가로 막대다. 구간 축이 세로이고 수익률이 가로이며, 구간은 목록
    차례대로 위에서 아래로 늘어선다. 구간 이름이 길어도 눈금이 눕지 않아
    세로 막대보다 읽기 쉽다.

    `vertical`을 켜면 두 축을 맞바꾼다. 구간이 가로축에 왼쪽부터 늘어서고
    수익률이 세로축이 된다. 구간 이름이 짧아 눕히지 않아도 되는 카드에
    쓴다(→ returns.SegmentCard.vertical).

    어느 쪽이든 손실이 난 구간은 0선 반대쪽으로 막대가 뻗는다.
    """
    if distribution.empty:
        return figures.empty_figure()

    figure = go.Figure()
    colors = {TOTAL_LABEL: COLOR_TOTAL, branch_name: COLOR_BRANCH}
    segments = list(dict.fromkeys(distribution["segment"]))
    for scope in (TOTAL_LABEL, branch_name):
        rows = distribution[distribution["scope"] == scope]
        if rows.empty:
            continue
        texts = [
            fmt.format_signed_percent(value) for value in rows["value"]
        ]
        # 축을 맞바꿔도 담는 값은 같다. 무엇을 어느 축에 놓는지만 다르다.
        axes = (
            {"x": rows["segment"], "y": rows["value"]}
            if vertical
            else {"x": rows["value"], "y": rows["segment"]}
        )
        name_slot = "%{x}" if vertical else "%{y}"
        figure.add_trace(
            go.Bar(
                **axes,
                name=scope,
                orientation="v" if vertical else "h",
                marker={
                    "color": colors.get(scope, COLOR_BRANCH),
                    "line": {"width": 0},
                },
                text=texts,
                texttemplate="%{text}",
                textposition="outside",
                # 막대 끝에 적은 값이 그래프 밖으로 나가도 지우지 않는다.
                cliponaxis=False,
                textfont={"size": BAR_TEXT_SIZE},
                customdata=texts,
                hovertemplate=(
                    f"<b>{name_slot}</b><br>구분: {scope}"
                    f"<br>{measure_label}: %{{customdata}}"
                    "<extra></extra>"
                ),
            )
        )

    value_axis = figures.axis(
        f"{measure_label}(%)",
        ticksuffix="%",
        range=_padded(distribution["value"], BAR_PADDING, include=(0.0,)),
        # 손실이 난 구간이 어디부터인지 0선으로 가른다.
        zeroline=True,
        zerolinecolor=figures.COLOR_AXIS,
        zerolinewidth=1,
    )
    segment_axis = figures.axis(
        axis_title,
        showgrid=False,
        categoryorder="array",
        categoryarray=segments,
    )
    if vertical:
        # 가로축은 왼쪽부터 목록 차례대로 늘어선다. 뒤집지 않는다.
        axis_pair = {"xaxis": segment_axis, "yaxis": value_axis}
        margin = {"l": 76, "r": 24, "t": 24, "b": 56}
    else:
        # 목록의 첫 구간이 맨 위에 오게 뒤집는다. 그대로 두면 Plotly가
        # 아래에서 위로 쌓아 차례가 거꾸로 보인다.
        segment_axis["autorange"] = "reversed"
        axis_pair = {"xaxis": value_axis, "yaxis": segment_axis}
        margin = {"l": 96, "r": 48, "t": 24, "b": 48}

    figure.update_layout(
        **figures.base_layout(margin=margin),
        barmode="group",
        bargap=0.3,
        bargroupgap=0.08,
        **axis_pair,
    )
    return figure


__all__ = [
    "COLOR_BRANCH",
    "COLOR_BRANCH_BAR",
    "COLOR_BRANCH_GROUP",
    "COLOR_TOTAL",
    "COLOR_TOTAL_MARK",
    "create_return_group_figure",
    "create_segment_return_figure",
    "create_return_rank_figure",
    "create_return_scatter_figure",
]
