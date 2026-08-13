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
from dashboard.format import format_month_short

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


def base_layout(**overrides) -> dict:
    """모든 차트가 공유하는 레이아웃 설정."""
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
        xaxis=axis("기준 월", showgrid=False),
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
