"""Plotly 공통 설정과 디자인 토큰.

색상·글꼴 토큰은 이 모듈에서 한 번만 정의하고 `assets/style.css`의
CSS 변수와 이름·의미를 맞춘다. 어느 차트에나 쓰는 레이아웃·축 설정도
여기 둔다.

차트 종류별 Figure 생성 함수는 그 탭 모듈에 있다(→ dashboard.tabs).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from dashboard.data import TOTAL_LABEL
from dashboard.format import (
    format_month,
    format_month_short,
    format_signed_percent,
)

# --- 디자인 토큰 (CSS 변수와 동일한 의미)
# --------------------------------------
FONT_FAMILY = (
    '"Spoqa Han Sans Neo", "Spoqa Han Sans", "Malgun Gothic", sans-serif'
)

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

COLOR_PAGE = "#ECEFF4"  # --color-page

# 증감 표기색. 색상만으로 구분하지 않고 항상 +/- 기호와 함께 쓴다.
COLOR_UP = COLOR_PRIMARY_DARK
COLOR_DOWN = COLOR_ACCENT_DARK

# 순매수·순매도 표기색. 국내 시장 관행대로 사는 쪽을 빨강, 파는 쪽을
# 파랑으로 둔다. CI 팔레트에는 순수한 빨강·파랑이 없어 여기서만 팔레트
# 밖의 값을 쓴다(→ AGENTS.md §5.1). 매수와 매도를 한눈에 갈라 보는 것이
# 이 눈금의 목적이라 CI 계열색으로는 두 방향이 구분되지 않았다.
# 색만으로 구분하지 않도록 값을 함께 적는다(→ §5.2).
COLOR_NET_BUY = "#FF0000"
COLOR_NET_SELL = "#0000FF"

# 순매수 발산형 색 눈금. 가운데(0)를 흰색에 두어 사는 쪽과 파는 쪽이 0을
# 기준으로 갈리게 한다. 눈금의 가운데를 0에 맞추는 일은 그리는 쪽에서
# 한다(→ product.figures).
#
# 중간 단계를 두지 않는다. 순매수금액은 로그로 눌러 놓아 대부분의 값이
# 눈금의 양끝 가까이 모이는데, 중간 색을 끼우면 어쩌다 가운데에 놓인
# 값만 매수·매도와 상관없는 색(청록·주황)으로 튀어 보인다.
NET_FLOW_COLORSCALE = (
    (0.0, COLOR_NET_SELL),
    (0.5, COLOR_SURFACE),
    (1.0, COLOR_NET_BUY),
)

EMPTY_MESSAGE = "표시할 데이터가 없습니다"

# 범례 조작 안내. 범례를 눌러 계열을 켜고 끌 수 있다는 사실이 화면에
# 드러나지 않아 함께 적는다. '범례'는 업무 용어가 아니므로 화면에 보이는
# 대로 '지표'라고 부른다.
LEGEND_HINT_TEXT = "지표 클릭 · 켜고 끄기"

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
        "toImage",
    ],
}

# 확대·축소가 필요한 차트용 설정. Plotly.js가 브라우저 안에서 처리하므로
# 서버가 없는 정적 HTML에서도 똑같이 동작한다. Dash 콜백으로 만든 버튼은
# 정적 HTML에서 눌러도 아무 일이 없으므로 쓰지 않는다(→ AGENTS.md §14).
# 모드바는 항상 띄운다. 마우스를 올려야 나타나면 있는 줄 모른다.
ZOOMABLE_CONFIG = {
    **PLOTLY_CONFIG,
    "displayModeBar": True,
    "scrollZoom": True,
    "modeBarButtons": [["zoomIn2d", "zoomOut2d", "resetScale2d"]],
}
# 위에서 버튼 목록을 직접 정하므로 제거 목록은 쓰이지 않는다. 남겨 두면
# 두 설정이 어긋났을 때 어느 쪽이 맞는지 헷갈린다.
ZOOMABLE_CONFIG.pop("modeBarButtonsToRemove", None)


def chart_config(zoomable: bool) -> dict:
    """차트 선언의 확대 허용 여부로 Plotly 설정을 고른다.

    Dash 화면과 정적 HTML이 같은 함수를 써서 설정이 갈라지지 않게 한다.
    """
    return ZOOMABLE_CONFIG if zoomable else PLOTLY_CONFIG


def legend_hint() -> dict:
    """범례 조작 안내. 범례의 제목으로 넣는다.

    주석(annotation)으로 두면 자리를 직접 정해야 하는데, 범례 폭을 미리
    알 수 없어 항목이 많은 차트에서 지표 이름과 겹친다. 제목으로 넣으면
    Plotly가 범례 위에 자리를 만들고 그만큼 여백을 넓혀 준다. 항목이
    늘거나 두 줄로 접혀도 겹치지 않는다.

    **`side`에 `left`를 넣지 않는다.** 가로 범례에서 제목을 왼쪽에 두면
    Plotly가 항목 격자 전체를 제목 폭만큼 오른쪽으로 민다. 그런데 줄을
    나누는 계산은 차트 영역 폭 그대로라, 밀린 만큼 오른쪽 칸이 차트 밖으로
    나가 이름이 잘린다. 항목이 많은 차트일수록 눈에 띈다. `top`으로 두면
    제목이 범례 위에 놓이고 항목은 차트 왼쪽 끝에서 시작한다.

    범례보다 한 단계 작고 흐린 글씨로 적어 지표 이름과 섞여 보이지
    않게 한다.
    """
    return {
        "text": LEGEND_HINT_TEXT,
        "side": "top",
        "font": {"size": 11, "color": COLOR_TEXT_MUTED},
    }


def base_layout(**overrides) -> dict:
    """모든 차트가 공유하는 레이아웃 설정.

    범례가 있는 차트에는 조작 안내를 함께 붙인다. 차트마다 적지 않으므로
    문구를 고치면 Dash 화면과 정적 HTML의 모든 차트가 같이 바뀐다.
    """
    layout = {
        "font": {"family": FONT_FAMILY, "size": 12, "color": COLOR_TEXT},
        "paper_bgcolor": COLOR_SURFACE,
        "plot_bgcolor": COLOR_SURFACE,
        "margin": {"l": 64, "r": 32, "t": 24, "b": 56},
        # 글자색을 직접 정한다. 비워 두면 Plotly가 계열 색으로 글자를 그려
        # 흰 배경 위에서 흐려진다. 배경은 흰색으로 고정해 어느 계열이든
        # 대비가 같게 한다.
        "hoverlabel": {
            "font": {
                "family": FONT_FAMILY,
                "size": 12.5,
                "color": COLOR_TEXT,
            },
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
    if layout.get("showlegend"):
        # 범례를 통째로 바꾼 차트에도 안내가 남도록 제목만 끼워 넣는다.
        # 여기서 한 번만 붙이므로 차트를 더해도 빠뜨리지 않는다.
        legend = dict(layout.get("legend") or {})
        legend.setdefault("title", legend_hint())
        layout["legend"] = legend
    return layout


def axis(title: str | None = None, **overrides) -> dict:
    """축 설정. 모든 차트가 같은 눈금·격자 모양을 갖게 한다."""
    settings = {
        "title": {
            "text": title,
            "font": {"size": 12, "color": COLOR_TEXT_MUTED},
        },
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
    settings.update(overrides)
    return settings


def padded_range(values, ratio: float = 0.18) -> list[float] | None:
    """값이 움직인 구간에 위아래 여백을 더한 축 범위.

    여백이 없으면 선이 그래프 위아래 끝에 붙는다. 값이 모두 같으면 범위가
    0이 되어 선이 사라지므로 그때만 값의 크기에 비례한 여백을 준다.
    """
    numbers = pd.to_numeric(pd.Series(list(values)), errors="coerce").dropna()
    if numbers.empty:
        return None
    low, high = float(numbers.min()), float(numbers.max())
    span = high - low
    padding = span * ratio if span > 0 else max(abs(high) * 0.05, 1.0)
    # 고객 수는 음수가 될 수 없다.
    return [max(0.0, low - padding), high + padding]


# --- 월별 추이 골격 ----------------------------------------------------------
# 전체를 막대로, 고른 지점을 선으로 겹쳐 그리는 그림. 자산·연금·거래 추이가
# 모두 이 골격을 쓴다. 여백·색·축 규칙을 탭마다 적으면 한쪽만 고쳤을 때
# 화면 안에서 그림이 갈라진다(→ AGENTS.md §12).
def hover_columns(
    trend: pd.DataFrame,
    scope: str,
    formatters: tuple[tuple[str, object], ...],
) -> np.ndarray:
    """hover에 실을 문구를 `customdata` 순서대로 쌓는다.

    `scope`는 `total` 또는 `branch`이며, 컬럼 이름을 `<scope>_<이름>`으로
    만든다.
    """
    return np.stack(
        [
            [to_text(value) for value in trend[f"{scope}_{name}"]]
            for name, to_text in formatters
        ],
        axis=-1,
    )


def trend_figure(
    trend: pd.DataFrame,
    branch_name: str,
    left_title: str,
    right_title: str,
    customdata: dict[str, np.ndarray],
    hover_lines: str,
) -> go.Figure:
    """전체 값(막대, 왼쪽 축)과 선택 지점 값(선, 오른쪽 축).

    두 축 모두 0이 아니라 값이 움직인 구간에 맞춘다. 규모가 크고 변화가
    작아 0부터 그리면 움직임이 보이지 않는다. 실제 크기는 축 눈금과
    hover 값으로 읽는다.

    `hover_lines`는 `customdata` 자리를 채운 hover 본문이다. 구분 이름은
    막대와 선이 서로 달라 여기서 앞에 붙인다.
    """
    labels = [format_month_short(month) for month in trend["base_month"]]
    figure = go.Figure()
    figure.add_trace(
        go.Bar(
            x=labels,
            y=trend["total_value"],
            name=TOTAL_LABEL,
            marker={"color": COLOR_SECONDARY_LIGHT, "line": {"width": 0}},
            customdata=customdata["total"],
            hovertemplate=(
                f"<b>%{{x}}</b><br>구분: {TOTAL_LABEL}"
                f"{hover_lines}<extra></extra>"
            ),
        )
    )
    figure.add_trace(
        go.Scatter(
            x=labels,
            y=trend["branch_value"],
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
            customdata=customdata["branch"],
            hovertemplate=(
                f"<b>%{{x}}</b><br>구분: {branch_name}"
                f"{hover_lines}<extra></extra>"
            ),
        )
    )
    figure.update_layout(
        **base_layout(
            margin={"l": 92, "r": 92, "t": 24, "b": 48},
            hovermode="x unified",
        ),
        xaxis=axis(showgrid=False),
        yaxis=axis(
            left_title,
            tickformat=",.0f",
            range=padded_range(trend["total_value"]),
        ),
        yaxis2=axis(
            right_title,
            overlaying="y",
            side="right",
            showgrid=False,
            tickformat=",.0f",
            range=padded_range(trend["branch_value"]),
        ),
        bargap=0.35,
    )
    return figure


# --- 구성 비중 막대 골격 -----------------------------------------------------
# 첫 칸이 전체, 나머지가 고른 지점인 100% 누적 세로 막대. 자산 구성과 수익
# 비중이 이 골격을 쓴다. 색과 이름은 탭이 정해서 넘긴다.

# 막대 안에 비중을 적을 최소 크기(%). 이보다 얇은 칸은 글자가 칸을 넘어
# 옆 칸까지 덮으므로 비워 둔다. 그 값은 hover로 읽는다.
MIX_LABEL_MIN_SHARE = 4.0


def share_label(value: float | None) -> str:
    """막대 안에 적을 비중. 칸이 얇으면 비운다."""
    if value is None or pd.isna(value):
        return ""
    if float(value) < MIX_LABEL_MIN_SHARE:
        return ""
    return f"{float(value):.1f}%"


# 범례 칸을 몇 개씩 끊을지 정할 때 쓰는 글자 크기. 기본 글자보다 한 단계
# 작게 적어 이름이 칸 안에 들어가게 한다.
MIX_LEGEND_FONT_SIZE = 11


def _legend_grid(columns: int) -> dict:
    """가로 범례를 정해진 칸 수로 끊는 설정.

    Plotly의 가로 범례는 **차트 영역 폭** 안에서만 줄을 나눈다. 칸 수를
    맡겨 두면 가장 긴 이름의 폭으로 칸을 나누는데, 그 폭이 차트 폭을 몇 등분한
    값과 비슷하면 마지막 칸이 오른쪽으로 밀려 이름이 잘린다.

    `entrywidth`를 차트 폭의 분수로 주면 칸 수가 화면 폭과 무관하게 고정되고,
    범례 전체 폭이 차트 폭을 넘지 않는다. 칸이 늘면 옆으로 넘치는 대신
    아래로 한 줄이 더 생긴다.
    """
    return {
        "entrywidthmode": "fraction",
        "entrywidth": 1 / columns,
        "font": {"size": MIX_LEGEND_FONT_SIZE},
    }


def mix_figure(
    mix: pd.DataFrame,
    labels: tuple[str, ...],
    colors: tuple[str, ...],
    value_title: str,
    category_label: str,
    legend_columns: int = 0,
) -> go.Figure:
    """구분별 구성 비중 100% 누적 세로 막대.

    첫 막대가 전체, 나머지가 고른 지점이다. `mix`는 한 줄이 막대 하나이며
    `scope` 컬럼 뒤에 쌓을 값이 열로 놓인다.

    `category_label`은 hover에서 쌓은 항목을 부르는 이름이다(예: '상품').

    `legend_columns`를 주면 범례를 그 칸 수로 끊는다. 0이면 Plotly가 정한다
    (→ _legend_grid).
    """
    if mix.empty:
        return empty_figure()

    scopes = [str(name) for name in mix["scope"]]
    # 막대 자리는 이름이 아니라 순서로 잡는다. 두 칸에서 같은 지점을 고르면
    # 이름이 겹치는데, Plotly는 같은 이름을 한 자리로 보고 두 막대를 포개
    # 쌓는다. 그러면 고른 칸이 사라지고 남은 칸의 비중이 두 배로 그려진다.
    # 이름은 축 눈금과 hover에만 쓴다.
    positions = list(range(len(scopes)))
    share_columns = [column for column in mix.columns if column != "scope"]
    figure = go.Figure()
    for index, (column, label) in enumerate(zip(share_columns, labels)):
        values = [
            None if pd.isna(value) else float(value) for value in mix[column]
        ]
        figure.add_trace(
            go.Bar(
                x=positions,
                y=values,
                name=label,
                marker={
                    "color": colors[index % len(colors)],
                    "line": {"width": 0},
                },
                # 비중을 막대 안에 바로 적는다. 글자색은 Plotly가 막대 색에
                # 맞춰 검정·흰색 중 대비가 큰 쪽을 고르므로 지정하지 않는다.
                text=[share_label(value) for value in values],
                texttemplate="%{text}",
                textposition="inside",
                insidetextanchor="middle",
                customdata=list(scopes),
                hovertemplate=(
                    f"<b>%{{customdata}}</b><br>{category_label}: {label}"
                    "<br>비중: %{y:.1f}%<extra></extra>"
                ),
            )
        )

    figure.update_layout(
        **base_layout(
            margin={"l": 76, "r": 32, "t": 24, "b": 48},
            legend={
                "orientation": "h",
                "yanchor": "bottom",
                "y": 1.02,
                "xanchor": "left",
                "x": 0,
                "traceorder": "normal",
                "bgcolor": "rgba(0,0,0,0)",
                **(_legend_grid(legend_columns) if legend_columns else {}),
            },
        ),
        barmode="stack",
        bargap=0.42,
        # 칸마다 글자 크기가 달라지지 않게 한 크기로 맞추고, 그 크기로
        # 안 들어가는 칸은 Plotly가 감춘다.
        uniformtext={"mode": "hide", "minsize": 10},
        xaxis=axis(
            None,
            showgrid=False,
            tickmode="array",
            tickvals=positions,
            ticktext=scopes,
            range=[-0.5, len(positions) - 0.5],
        ),
        yaxis=axis(value_title, range=[0, 100], ticksuffix="%"),
    )
    return figure


# --- 규모와 증가율 산점도 골격 -----------------------------------------------
# 지점마다 기준 월 값(가로)과 전년 동월 대비 증가율(세로)을 찍는 그림.
# 거래와 수익이 이 골격을 쓴다.

# 산점도 축 여백. 점 위에 얹은 지점 이름이 축 끝에서 잘리지 않을 만큼만
# 준다.
SCATTER_PADDING = 0.12


def growth_scatter_figure(
    scatter: pd.DataFrame,
    measure_label: str,
    unit_label: str,
    to_text,
    median: float | None,
    base_month: str | None = None,
    current_month: str | None = None,
    value_suffix: str = "",
) -> go.Figure:
    """지점별 규모와 전년 동월 대비 증가율 산점도.

    기준선 두 개가 사분면을 만든다. 가로는 증가·감소, 세로는 규모
    많음·적음이다.

    `value_suffix`는 가로축 눈금에 붙일 단위다. 가로축 값이 비율일 때
    `%`를 넘긴다. 금액·인원수는 축 이름이 단위를 말하므로 비워 둔다.
    """
    if scatter.empty:
        return empty_figure()

    base_label = format_month(base_month) if base_month else "전년 동월"
    now_label = format_month(current_month) if current_month else "기준 월"

    figure = go.Figure(
        go.Scatter(
            x=scatter["value"],
            y=scatter["growth"],
            mode="markers+text",
            name="지점",
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
                    [to_text(value) for value in scatter["value"]],
                    [
                        format_signed_percent(value)
                        for value in scatter["growth"]
                    ],
                ],
                axis=-1,
            ),
            hovertemplate=(
                "<b>%{customdata[0]}</b>"
                f"<br>{now_label} {measure_label}: %{{customdata[1]}}"
                f"<br>{base_label} 대비: %{{customdata[2]}}<extra></extra>"
            ),
        )
    )

    figure.update_layout(
        **base_layout(
            showlegend=False,
            margin={"l": 92, "r": 32, "t": 40, "b": 56},
            dragmode="pan",
        ),
        xaxis=axis(
            f"{measure_label}({unit_label})",
            tickformat=",.0f",
            ticksuffix=value_suffix,
            range=padded_range(scatter["value"], SCATTER_PADDING),
        ),
        yaxis=axis(
            f"{measure_label} 증가율(전년 동월 대비, YoY%)",
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
    if median is not None and median > 0:
        figure.add_shape(
            type="line",
            xref="x",
            yref="paper",
            x0=median,
            x1=median,
            y0=0,
            y1=1,
            line={"color": COLOR_AXIS, "width": 1, "dash": "dash"},
        )
        figure.add_annotation(
            xref="x",
            yref="paper",
            x=median,
            y=1.06,
            text=f"{measure_label} 중앙값 {to_text(median)}",
            showarrow=False,
            font={"size": 10, "color": COLOR_TEXT_MUTED},
        )
    return figure


def empty_figure(message: str = EMPTY_MESSAGE) -> go.Figure:
    """데이터가 없을 때 안내 문구만 표시한다."""
    figure = go.Figure()
    figure.update_layout(
        **base_layout(
            showlegend=False, margin={"l": 24, "r": 24, "t": 24, "b": 24}
        ),
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
