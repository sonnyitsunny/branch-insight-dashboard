"""상품 탭의 Figure 생성.

데이터를 직접 조회하지 않는다. 계산이 끝난 프레임을 받아 Figure만
만든다(→ AGENTS.md §12). 색과 글꼴은 공통 토큰에서 가져온다.
"""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from dashboard import figures
from dashboard import format as fmt
from dashboard.tabs.product import metrics

# 칸 안 글씨 크기. 종목 칸과 업종 칸을 한 단계 다르게 두어 어느 것이
# 묶음인지 구분되게 한다.
TILE_FONT_SIZE = 11

# 칸 테두리 두께. 흰 선으로 갈라 놓아야 비슷한 색 칸이 붙어 있어도
# 경계가 보인다.
TILE_LINE_WIDTH = 1.5

# hover에 실을 문구 컬럼. 여기 순서가 `customdata`의 자리를 정하므로
# `HOVER_TEMPLATE`의 번호와 함께 고친다.
HOVER_FIELDS = (
    "hover_sector",
    "hover_market_cap",
    "hover_customer",
    "hover_trade_value",
    "hover_net_buy",
)

HOVER_TEMPLATE = (
    "<b>%{label}</b>"
    "<br>업종: %{customdata[0]}"
    "<br>시가총액: %{customdata[1]}"
    "<br>거래고객수: %{customdata[2]}"
    "<br>거래대금: %{customdata[3]}"
    "<br>순매수금액: %{customdata[4]}"
    "<extra></extra>"
)

# 칸 안 글씨. 종목명만 적고 숫자는 넣지 않는다. 칸이 좁아 이름과 금액을
# 함께 넣으면 두 줄이 다 들어가지 못해 `uniformtext`가 글씨를 통째로
# 감춘다. 금액은 hover로 읽는다(→ HOVER_TEMPLATE).
TILE_TEMPLATE = "%{label}"


def treemap_figure(rows: pd.DataFrame) -> go.Figure:
    """업종으로 묶은 종목 트리맵.

    칸 크기는 시가총액을 로그로 바꾼 값, 색은 순매수금액을 부호를 지킨
    로그로 바꾼 값이다(→ metrics). 사는 쪽이 붉은 계열, 파는 쪽이 푸른
    계열이며 순매수 0이 중립색이다.

    묶는 일은 `path`로 px에 맡긴다. 업종 칸의 크기는 px가 자식 합으로
    채우지만 색과 문구는 그대로 쓸 수 없어 뒤에서 덮는다
    (→ _fix_sector_cells).

    칸 안에는 종목명만 적고 네 값은 hover에 적는다. 색이 뜻하는 금액이
    칸에 함께 보이지 않으므로, 순매수·순매도를 화면에서 바로 구분하려면
    hover를 거쳐야 한다(→ AGENTS.md §5.2).
    """
    if rows is None or rows.empty:
        return figures.empty_figure()

    limit = metrics.color_limit(rows["color"])
    figure = px.treemap(
        _tile_texts(rows),
        path=["sector_label", "stock_name"],
        values="area",
        color="color",
        color_continuous_scale=[
            list(step) for step in figures.NET_FLOW_COLORSCALE
        ],
        # 눈금의 가운데를 0에 맞춘다. 이게 없으면 순매수 0인 종목이
        # 중립색이 아니라 한쪽 색으로 그려진다.
        color_continuous_midpoint=0,
        range_color=(-limit, limit),
        custom_data=list(HOVER_FIELDS),
    )
    figure.update_traces(
        texttemplate=TILE_TEMPLATE,
        textposition="middle center",
        textfont={"size": TILE_FONT_SIZE},
        hovertemplate=HOVER_TEMPLATE,
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
    _fix_sector_cells(figure, rows, limit)
    figure.update_layout(
        **figures.base_layout(
            showlegend=False, margin={"l": 8, "r": 8, "t": 8, "b": 8}
        ),
        # 칸마다 글자 크기가 달라지지 않게 한 크기로 맞추고, 그 크기로
        # 들어가지 않는 칸은 Plotly가 글씨를 감춘다.
        uniformtext={"mode": "hide", "minsize": 9},
        # 색 눈금 막대는 두지 않는다. 금액을 칸 안 글씨와 hover로 읽으므로
        # 막대가 없어도 되고, 그만큼 그림이 넓어진다.
        coloraxis_showscale=False,
    )
    return figure


def _tile_texts(rows: pd.DataFrame) -> pd.DataFrame:
    """hover에 쓸 문구 컬럼을 붙인다.

    숫자가 아니라 다 만들어진 문구로 넘긴다. 숫자로 넘기면 px가 업종
    칸을 채울 때 그 값들을 평균 내어, 화면에 쓰지 않는 수가 hover에
    나타난다.
    """
    frame = rows.copy()
    frame["hover_sector"] = frame["sector_label"]
    frame["hover_market_cap"] = [
        fmt.format_assets(value) for value in frame["market_cap"]
    ]
    frame["hover_customer"] = [
        fmt.format_count(value) for value in frame["trade_customer_count"]
    ]
    frame["hover_trade_value"] = [
        fmt.format_revenue(value) for value in frame["trade_value"]
    ]
    frame["hover_net_buy"] = [
        fmt.format_revenue_delta(value) for value in frame["net_buy_amount"]
    ]
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


def _fix_sector_cells(
    figure: go.Figure, rows: pd.DataFrame, limit: float
) -> None:
    """업종 칸의 색과 문구를 바로잡는다.

    px는 부모 칸 값을 자식에서 만들어 채운다. 색은 면적 가중 평균이라
    합계와 다르고(→ _sector_colors), 문구는 자식이 여럿이면 `(?)`,
    하나면 그 자식 값이 그대로 들어간다. 그대로 두면 업종 칸 hover에
    "시가총액: (?)"가 뜨거나 종목 하나의 값이 업종 값인 것처럼 나온다.

    부모 칸은 위 칸이 없어 `parents`가 빈 문자열이다. 그것으로 가려낸다.
    px가 `custom_data` 뒤에 색 컬럼을 하나 더 붙이므로 함께 잘라 낸다.
    """
    trace = figure.data[0]
    sector_colors = _sector_colors(rows, limit)
    colors = list(trace.marker.colors)
    custom = [list(cells)[: len(HOVER_FIELDS)] for cells in trace.customdata]
    blank = [fmt.EMPTY_TEXT] * len(HOVER_FIELDS)
    for index, parent in enumerate(trace.parents):
        if parent:
            continue
        colors[index] = sector_colors[trace.labels[index]]
        custom[index] = list(blank)
    trace.marker.colors = colors
    trace.customdata = custom
