"""Plotly 공통 설정과 디자인 토큰.

색상·글꼴 토큰은 이 모듈에서 한 번만 정의하고 `assets/style.css`의
CSS 변수와 이름·의미를 맞춘다. 어느 차트에나 쓰는 레이아웃·축 설정도
여기 둔다.

차트 종류별 Figure 생성 함수는 그 탭 모듈에 있다(→ dashboard.tabs).
"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

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
