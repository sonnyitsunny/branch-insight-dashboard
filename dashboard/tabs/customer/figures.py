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
    PROFILE_STATES,
    TOTAL_LABEL,
)
from dashboard.figures import (
    COLOR_AXIS,
    COLOR_PRIMARY,
    COLOR_SECONDARY,
    COLOR_SECONDARY_LIGHT,
    COLOR_SURFACE,
    COLOR_TEXT,
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
        xaxis=axis(showgrid=False),
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


# --- 2. 지점별 고객 규모 비교분석
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
    # 가로축 이름에 기준 월을 적는다. 문자열로 박으면 데이터 기간이 바뀌어도
    # 옛 월이 그대로 남는다.
    count_label = (
        f"공통고객({fmt.format_month_tag(current_month)})"
        if current_month
        else "공통고객 수(명)"
    )

    figure = go.Figure(
        go.Scatter(
            x=scatter["current_count"],
            y=scatter["yoy"],
            mode="markers+text",
            name="영업점",
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
            count_label, tickformat=",.0f", range=x_range
        ),
        yaxis=axis(
            "공통고객 증가율(전년 동월 대비, YoY%)",
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


# --- 3. 연령별 고객분포
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


# --- 4. 투자성향 분석
# --------------------------------------------------------------
# 진단여부 파이와 성향별 막대를 한 카드에 나란히 둔다. 아래 값은 그림
# 영역(여백 안쪽)의 가로 폭을 1로 본 자리다. 둘 사이를 띄워 둔 칸에 막대의
# 성향 이름이 놓인다.
PROFILE_PIE_DOMAIN = (0.0, 0.27)
INVESTMENT_BAR_DOMAIN = (0.37, 1.0)
# 파이가 차지하는 세로 자리. 위는 제목, 아래는 범례 자리로 비워 둔다.
# 위쪽을 넉넉히 비우는 이유 — 조각 바깥 글자는 원 위로 조금 더 올라오는데,
# 얇은 조각이 12시 근처에 몰려 있어 그 글자가 제목 줄까지 닿는다.
PROFILE_PIE_HEIGHT = (0.14, 0.78)
# 도넛 범례를 놓을 높이. 파이 바로 아래다.
PROFILE_LEGEND_Y = PROFILE_PIE_HEIGHT[0] - 0.02
PROFILE_PIE_TITLE = "투자성향 진단여부"
# 가운데를 비워 도넛으로 그리고 그 자리에 전체 인원을 적는다. 조각마다
# 적는 비중의 분모가 무엇인지 그림 안에서 바로 읽힌다.
PROFILE_PIE_HOLE = 0.55
PROFILE_PIE_CENTER_LABEL = "공통고객"

# 진단 상태 색. 이름은 데이터 계층이 정한 것을 그대로 쓰고
# (→ data.PROFILE_STATES) 여기서는 색만 짝지어, 이름이 두 곳으로 갈라지지
# 않게 한다. 색만으로 구분하지 않도록 조각마다 이름을 함께 적는다
# (→ AGENTS.md §5.2).
#
# '유효'가 핵심 값이라 강조색인 주황을 쓴다. 나머지 둘은 원의 몇 %밖에
# 안 되는 얇은 조각이라, 주황 위에서 바로 눈에 띄도록 색을 멀리 둔다 —
# '만료'는 보조색인 짙은 남색, '미제공'은 값이 아니라 모른다는 뜻이므로
# 무채색이다.
PROFILE_STATE_COLORS = {
    PROFILE_STATES[column]: color
    for column, color in (
        ("profile_valid_count", COLOR_PRIMARY),
        ("profile_expired_count", COLOR_SECONDARY),
        ("profile_missing_count", COLOR_TEXT_MUTED),
    )
}
# 조각에 붙이는 글자. 비중은 표·hover와 같이 소수점 한 자리로 맞춘다
# (→ format.py).
#
# 두꺼운 조각은 글자가 원 안에 들어가므로 이름까지 적고, 바깥으로 밀려나는
# 얇은 조각에는 비중만 적는다. 얇은 조각은 12시 근처에 나란히 몰려 있어,
# 이름까지 붙이면 글자가 길어져 서로 겹치고 제목 줄까지 밀고 올라온다.
# 그 조각의 이름은 밑의 범례가 말해 준다(→ legend2).
PROFILE_PIE_TEXT = "%{label}<br>%{percent:.1%}"
PROFILE_PIE_SHORT_TEXT = "%{percent:.1%}"
PROFILE_PIE_NAME_MIN_SHARE = 15.0


def _profile_pie(states: pd.DataFrame, scope: str) -> go.Pie:
    """투자성향 진단 상태 구성 도넛."""
    labels = [str(state) for state in states["state"]]
    total = int(states["customer_count"].sum())
    return go.Pie(
        labels=labels,
        values=[int(value) for value in states["customer_count"]],
        domain={
            "x": list(PROFILE_PIE_DOMAIN),
            "y": list(PROFILE_PIE_HEIGHT),
        },
        hole=PROFILE_PIE_HOLE,
        # 가운데 글자는 주석이 아니라 이 그림의 제목으로 넣는다. 주석은
        # 자리를 직접 적어야 하는데, automargin이 원을 줄이면 중심이
        # 옮겨져 글자만 남아 어긋난다. 제목은 Plotly가 실제 중심에 놓는다.
        title={
            "text": (
                f"<b>{fmt.format_count(total)}</b>"
                f"<br>{PROFILE_PIE_CENTER_LABEL}"
            ),
            "position": "middle center",
            "font": {"size": 12, "color": COLOR_TEXT},
        },
        # 원본이 정한 차례를 그대로 둔다. 크기순으로 다시 세우면 유효 →
        # 만료 → 미제공 순서가 흐트러진다.
        sort=False,
        direction="clockwise",
        marker={
            "colors": [PROFILE_STATE_COLORS[label] for label in labels],
            "line": {"color": COLOR_SURFACE, "width": 1},
        },
        # 두꺼운 조각은 안에, 글자가 들어가지 않는 얇은 조각은 바깥에
        # 적는다. 얇은 조각끼리는 Plotly가 자리를 벌리고, automargin이
        # 바깥 글자가 domain을 넘지 않도록 원을 줄인다.
        texttemplate=[
            (
                PROFILE_PIE_TEXT
                if float(share) >= PROFILE_PIE_NAME_MIN_SHARE
                else PROFILE_PIE_SHORT_TEXT
            )
            for share in states["share"]
        ],
        textposition="auto",
        insidetextorientation="horizontal",
        automargin=True,
        # 안쪽 글자색은 정하지 않는다. Plotly가 조각 색에 맞춰 대비가 큰
        # 쪽을 고른다. 색을 박아 두면 조각 색을 바꿀 때 글자가 묻힌다.
        insidetextfont={"size": 11},
        outsidetextfont={"size": 11, "color": COLOR_TEXT_MUTED},
        # 도넛 밑에 따로 범례를 둔다. 막대의 범례에 섞으면 어느 그림의
        # 지표인지 알 수 없어 Plotly의 두 번째 범례를 쓴다.
        showlegend=True,
        legend="legend2",
        # 파이 hover에는 customdata를 쓰지 않는다. 조각 하나가 값 하나라
        # `%{customdata[0]}`이 칸을 골라내지 못하고 줄 전체를 그대로
        # 찍는다. Plotly가 들고 있는 값과 비중을 바로 쓴다.
        hovertemplate=(
            f"<b>%{{label}}</b><br>구분: {scope}"
            "<br>공통고객 수: %{value:,}명"
            "<br>비중: %{percent:.1%}<extra></extra>"
        ),
    )


def create_investment_figure(
    breakdown: pd.DataFrame,
    scope: str,
    states: pd.DataFrame | None = None,
) -> go.Figure:
    """진단여부 파이(왼쪽)와 성향별 동의·불원 누적 막대(오른쪽).

    `states`가 비어 있으면 파이를 그리지 않고 막대가 폭을 다 쓴다. 원본에
    진단 상태 컬럼이 없을 때다(→ metrics.profile_states).
    """
    if breakdown.empty:
        return empty_figure()

    with_pie = states is not None and not states.empty
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

    if with_pie:
        figure.add_trace(_profile_pie(states, scope))

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
    if with_pie:
        # 카드 제목은 두 그림을 함께 부르는 이름이므로, 왼쪽 그림이 무엇을
        # 센 것인지는 그림 위에 따로 적는다. 오른쪽 막대는 같은 높이에
        # 놓인 범례가 그 자리를 대신한다.
        #
        # 파이가 놓인 칸의 가운데에 맞춘다. 파이를 아래로 내려 둔 덕에
        # (→ PROFILE_PIE_HEIGHT) 조각 바깥 글자가 이 줄까지 올라오지
        # 않는다.
        annotations.append(
            {
                "text": PROFILE_PIE_TITLE,
                "xref": "paper",
                "yref": "paper",
                "x": sum(PROFILE_PIE_DOMAIN) / 2,
                "y": 1.0,
                "xanchor": "center",
                "yanchor": "bottom",
                "showarrow": False,
                "font": {"size": 12, "color": COLOR_TEXT},
            }
        )

    # 도넛 범례. 막대 범례(`legend`)와 자리도 항목도 달라 두 번째 범례로
    # 둔다. 조작 안내는 막대 범례에 한 번만 붙으므로(→ figures.legend_hint)
    # 여기서는 되풀이하지 않는다.
    second_legend = (
        {
            "legend2": {
                "orientation": "h",
                "xanchor": "center",
                "x": sum(PROFILE_PIE_DOMAIN) / 2,
                "yanchor": "top",
                "y": PROFILE_LEGEND_Y,
                "traceorder": "normal",
                "bgcolor": "rgba(0,0,0,0)",
                "font": {"size": 11},
            }
        }
        if with_pie
        else {}
    )

    figure.update_layout(
        **second_legend,
        # 누적 막대에서도 범례 순서를 막대 순서(동의 → 불원)와 맞춘다.
        # 파이가 있으면 왼쪽 여백을 두지 않는다. 성향 이름은 축 왼쪽이
        # 아니라 파이와 막대 사이의 빈 칸에 놓이므로 여백이 필요 없고,
        # 그만큼 파이가 카드 왼쪽 끝까지 붙는다. 위쪽은 파이 제목이
        # 들어갈 만큼 넓히고, 오른쪽은 막대 끝에 적는 인원수가 들어갈
        # 만큼만 남겨 막대를 최대한 길게 쓴다.
        **base_layout(
            margin=(
                {"l": 0, "r": 64, "t": 48, "b": 48}
                if with_pie
                else {"l": 88, "r": 64, "t": 24, "b": 48}
            ),
            legend={
                "orientation": "h",
                "yanchor": "bottom",
                "y": 1.02,
                "xanchor": "left",
                "x": INVESTMENT_BAR_DOMAIN[0] if with_pie else 0,
                "traceorder": "normal",
                "bgcolor": "rgba(0,0,0,0)",
            },
        ),
        barmode="stack",
        bargap=0.32,
        xaxis=axis(
            "구성 비율(%)",
            range=[0, 100],
            ticksuffix="%",
            domain=list(INVESTMENT_BAR_DOMAIN) if with_pie else [0.0, 1.0],
        ),
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
