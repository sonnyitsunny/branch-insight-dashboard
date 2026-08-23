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

# 지점 막대·점 색. 27곳을 주색상으로 칠하면 화면이 주황으로 덮여
# 견주는 기준인 '전체'가 묻힌다(→ AGENTS.md §5.2).
COLOR_BRANCH = figures.COLOR_SECONDARY_LIGHT
# '전체' 색. 하나뿐인 기준 막대라 주색상을 여기에 쓴다.
COLOR_TOTAL = figures.COLOR_PRIMARY

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
        COLOR_TOTAL if is_total else COLOR_BRANCH
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
                f"<br>지점 순위: %{{customdata[1]}} / {count}곳"
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
        (False, "지점", COLOR_BRANCH, POINT_SIZE, "circle"),
        (True, TOTAL_LABEL, COLOR_TOTAL, TOTAL_POINT_SIZE, "diamond"),
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


__all__ = [
    "COLOR_BRANCH",
    "COLOR_TOTAL",
    "create_return_rank_figure",
    "create_return_scatter_figure",
]
