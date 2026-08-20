"""상품 탭의 Figure 생성.

데이터를 직접 조회하지 않는다. 계산이 끝난 프레임을 받아 Figure만
만든다(→ AGENTS.md §12). 색과 글꼴은 공통 토큰에서 가져온다.
"""

from __future__ import annotations

from typing import Callable

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from dashboard import figures
from dashboard import format as fmt
from dashboard.tabs.product import metrics

# 칸 안 글씨 크기의 **위쪽 한계**. 고정 크기가 아니다.
#
# Plotly 트리맵은 이 크기로 그려 보고 칸을 넘치면 들어갈 때까지 줄인다.
# 넓히지는 않으므로 큰 칸이 이 크기, 작은 칸이 그보다 작은 글씨가 된다.
# 올리면 큰 칸만 커지고 작은 칸은 그대로다.
TILE_FONT_SIZE = 14

# 뿌리 칸 이름. 업종 칸 위에 칸을 하나 더 두고 그 이름을 여기서 정한다.
#
# 두지 않으면 px가 이름 없는 뿌리를 만든다. 데이터에 없는 칸이라 색도
# hover도 줄 수 없어서, 업종 칸 사이 여백이 검게 칠해지고 그 위에서
# hover가 `%{label}` 같은 서식 원문을 그대로 띄운다.
ROOT_LABEL = "전체"

# 칸 안 글씨 자리. 이름을 왼쪽 위에 붙인다. 가운데에 두면 업종 이름이
# 종목 칸에 완전히 덮여 화면에서 한 번도 보이지 않는다. 위로 올리면
# Plotly가 업종 칸 위쪽에 머리띠를 남기고 거기에 업종 이름을 적는다.
TILE_TEXT_POSITION = "top left"

# 칸 테두리 두께. 흰 선으로 갈라 놓아야 비슷한 색 칸이 붙어 있어도
# 경계가 보인다.
TILE_LINE_WIDTH = 1.5

# hover 한 줄의 선언 — (줄 이름, 값 컬럼, 표기 함수).
#
# 여기 적은 순서가 hover에 나오는 순서이고 `customdata`의 자리도 그 순서다.
# 줄 이름과 자리 번호를 두 곳에 적지 않도록 문구는 이 선언에서 만든다
# (→ _hover_template).
HoverLine = tuple[str, str, Callable[[object], str]]

# 국내주식 트리맵. 시가총액은 억원이라 원화 표기 함수를 쓴다.
DOMESTIC_HOVER: tuple[HoverLine, ...] = (
    ("업종", "sector_label", str),
    ("시가총액", "market_cap", fmt.format_assets),
    ("거래고객수", "trade_customer_count", fmt.format_count),
    ("거래대금", "trade_value", fmt.format_revenue),
    ("순매수금액", "net_buy_amount", fmt.format_revenue_delta),
)

# 해외주식 트리맵. 시가총액이 달러라 표기 함수가 다르고, 원본에 거래대금이
# 없어 그 줄이 빠진다(→ dashboard/sources/overseas_stock2.py).
OVERSEAS_HOVER: tuple[HoverLine, ...] = (
    ("업종", "sector_label", str),
    ("시가총액", "market_cap_usd", fmt.format_usd),
    ("거래고객수", "trade_customer_count", fmt.format_count),
    ("순매수금액", "net_buy_amount", fmt.format_revenue_delta),
)

# 칸 안 글씨. 종목명만 적고 숫자는 넣지 않는다. 두 줄이 되면 Plotly가
# 칸에 맞추느라 글씨를 더 세게 줄여 이름까지 읽을 수 없게 된다.
# 금액은 hover로 읽는다(→ _hover_template).
TILE_TEMPLATE = "%{label}"


def treemap_figure(
    rows: pd.DataFrame, hover: tuple[HoverLine, ...] = DOMESTIC_HOVER
) -> go.Figure:
    """업종으로 묶은 종목 트리맵.

    칸 크기는 시가총액을 눌러 바꾼 값, 색은 순매수금액을 부호를 지킨
    로그로 바꾼 값이다(→ metrics). 사는 쪽이 붉은 계열, 파는 쪽이 푸른
    계열이며 순매수 0이 중립색이다.

    `hover`는 hover에 적을 줄의 선언이다. 국내주식과 해외주식은 시가총액의
    단위가 다르고 원본이 담은 값도 달라 이 목록만 갈아 끼운다. 그림을 그리는
    규칙 자체는 하나로 둔다(→ DOMESTIC_HOVER, OVERSEAS_HOVER).

    묶는 일은 `path`로 px에 맡긴다. 업종 칸 위에 뿌리 칸을 하나 더 두는데
    (→ ROOT_LABEL), 위 칸들의 크기는 px가 자식 합으로 채우지만 색과 문구는
    그대로 쓸 수 없어 뒤에서 덮는다(→ _fix_parent_cells).

    칸 안에는 이름만 왼쪽 위에 적고 값은 hover에 적는다. 종목 칸은
    종목명, 업종 칸은 머리띠에 업종명이 들어간다
    (→ TILE_TEXT_POSITION). 색이 뜻하는 금액이 칸에 함께 보이지 않으므로,
    순매수·순매도를 화면에서 바로 구분하려면 hover를 거쳐야 한다
    (→ AGENTS.md §5.2).
    """
    if rows is None or rows.empty:
        return figures.empty_figure()

    limit = metrics.color_limit(rows["color"])
    figure = px.treemap(
        _tile_texts(rows, hover),
        path=[px.Constant(ROOT_LABEL), "sector_label", "stock_name"],
        values="area",
        color="color",
        color_continuous_scale=[
            list(step) for step in figures.NET_FLOW_COLORSCALE
        ],
        # 눈금의 가운데를 0에 맞춘다. 이게 없으면 순매수 0인 종목이
        # 중립색이 아니라 한쪽 색으로 그려진다.
        color_continuous_midpoint=0,
        range_color=(-limit, limit),
        custom_data=_hover_fields(hover),
    )
    figure.update_traces(
        texttemplate=TILE_TEMPLATE,
        textposition=TILE_TEXT_POSITION,
        textfont={"size": TILE_FONT_SIZE},
        hovertemplate=_hover_template(hover),
        marker={
            "line": {
                "color": figures.COLOR_SURFACE,
                "width": TILE_LINE_WIDTH,
            },
            # 깊이에 따라 색을 흐리지 않는다. 흐리면 같은 순매수금액이
            # 묶음 안 자리에 따라 다른 색으로 보인다.
            "depthfade": False,
        },
        # 위로 올라가는 경로 막대는 숨긴다. 두 단계뿐이라 쓸 일이 없고
        # 그만큼 그림이 좁아진다.
        pathbar={"visible": False},
        tiling={"packing": "squarify", "pad": 2},
    )
    _fix_parent_cells(figure, rows, limit, hover)
    figure.update_layout(
        **figures.base_layout(
            showlegend=False, margin={"l": 8, "r": 8, "t": 8, "b": 8}
        ),
        # `uniformtext`를 두지 않는다. 그 옵션은 칸마다 다른 글자 크기를
        # 가장 작은 칸에 맞춰 **하나로 통일**하고, 그 크기가 `minsize`보다
        # 작으면 글씨를 감춘다. 칸 크기가 크게 벌어지는 그림에서는 큰 칸까지
        # 작은 칸을 따라 내려가고, 그러고도 안 맞는 칸은 이름이 통째로
        # 사라진다. 실제로 55칸 중 아래쪽 칸들이 이름 없이 색만 남았다.
        #
        # 빼 두면 Plotly가 칸마다 따로 줄여 맞춘다. 큰 칸은 TILE_FONT_SIZE,
        # 작은 칸은 그 칸에 들어가는 크기로 그려져 이름이 남는다. 아주 작은
        # 칸의 글씨는 읽기 어려울 만큼 작아지므로 값은 hover로 읽는다
        # (→ _hover_template).
        # 색 눈금 막대는 두지 않는다. 금액을 칸 안 글씨와 hover로 읽으므로
        # 막대가 없어도 되고, 그만큼 그림이 넓어진다.
        coloraxis_showscale=False,
    )
    return figure


def _hover_fields(hover: tuple[HoverLine, ...]) -> list[str]:
    """hover 문구를 담을 컬럼 이름. 선언한 자리 번호를 그대로 쓴다."""
    return [f"hover_{index}" for index in range(len(hover))]


def _hover_template(hover: tuple[HoverLine, ...]) -> str:
    """hover 문구. 줄 이름과 자리 번호를 선언에서 만든다."""
    lines = "".join(
        f"<br>{name}: %{{customdata[{index}]}}"
        for index, (name, _column, _to_text) in enumerate(hover)
    )
    return f"<b>%{{label}}</b>{lines}<extra></extra>"


def _tile_texts(
    rows: pd.DataFrame, hover: tuple[HoverLine, ...]
) -> pd.DataFrame:
    """hover에 쓸 문구 컬럼을 붙인다.

    숫자가 아니라 다 만들어진 문구로 넘긴다. 숫자로 넘기면 px가 업종
    칸을 채울 때 그 값들을 평균 내어, 화면에 쓰지 않는 수가 hover에
    나타난다.
    """
    frame = rows.copy()
    fields = _hover_fields(hover)
    for field, (_name, column, to_text) in zip(fields, hover):
        frame[field] = [to_text(value) for value in frame[column]]
    return frame


def _sector_colors(rows: pd.DataFrame, limit: float) -> dict[str, float]:
    """업종 칸 색.

    그 업종 종목들의 순매수금액을 **더한 뒤** 로그로 바꾼다. 로그로
    바꾼 값을 다시 평균 내면 뜻이 없는 수가 나오므로 순서를 지킨다
    (→ metrics.signed_log).

    px에 맡기면 자식 색을 면적으로 가중 평균한다. 그러면 73억을 팔고
    5억을 산 업종이 중립색이 되고, 매수와 매도가 섞인 업종은 큰 칸을
    따라 반대쪽 색으로 그려진다. 로그가 자릿수 차이를 줄여 놓기 때문에
    평균에서 서로 지워진다.

    종목 칸이 쓰는 눈금을 넘지 않도록 양끝에서 자른다. 업종 칸은 종목
    칸에 거의 덮여 테두리 사이로만 보이므로, 눈금을 넓혀 종목 색을
    흐리게 만드는 쪽이 손해다.
    """
    totals = rows.groupby("sector_label", sort=False)["net_buy_amount"].sum()
    colors = metrics.signed_log(totals).clip(lower=-limit, upper=limit)
    return dict(zip(totals.index, colors))


def _fix_parent_cells(
    figure: go.Figure,
    rows: pd.DataFrame,
    limit: float,
    hover: tuple[HoverLine, ...],
) -> None:
    """업종 칸과 뿌리 칸의 색과 문구를 바로잡는다.

    px는 위 칸의 값을 자식에서 만들어 채운다. 색은 면적 가중 평균이라
    합계와 다르고(→ _sector_colors), 문구는 자식이 여럿이면 `(?)`,
    하나면 그 자식 값이 그대로 들어간다. 그대로 두면 업종 칸 hover에
    "시가총액: (?)"가 뜨거나 종목 하나의 값이 업종 값인 것처럼 나온다.

    뿌리 칸은 위 칸이 없어 `parents`가 빈 문자열이고, 업종 칸은 그 값이
    뿌리 칸의 `id`다. 이름이 아니라 그 `id`로 가려내야 업종 이름이
    `ROOT_LABEL`과 같아도 섞이지 않는다.

    **색은 뿌리 칸만 그대로 둔다.** 업종 칸은 합계에서 다시 계산하지만
    (→ _sector_colors), 뿌리 칸은 px가 넣은 값을 건드리지 않는다. 여기서
    고칠 것은 서식 원문이 뜨던 hover뿐이다.

    px가 `custom_data` 뒤에 색 컬럼을 하나 더 붙이므로 함께 잘라 낸다.
    """
    trace = figure.data[0]
    sector_colors = _sector_colors(rows, limit)
    root_ids = {
        cell_id
        for cell_id, parent in zip(trace.ids, trace.parents)
        if not parent
    }
    colors = list(trace.marker.colors)
    custom = [list(cells)[: len(hover)] for cells in trace.customdata]
    blank = [fmt.EMPTY_TEXT] * len(hover)
    for index, parent in enumerate(trace.parents):
        if parent and parent not in root_ids:
            continue
        if parent:
            colors[index] = sector_colors[trace.labels[index]]
        custom[index] = list(blank)
    trace.marker.colors = colors
    trace.customdata = custom
