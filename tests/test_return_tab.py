"""수익률 탭 검증.

윗줄 왼쪽이 지점 수익률 순위(막대), 오른쪽이 장단기 수익률 비교(산점도)다.
두 그림 모두 지점별 수익률 원본 하나를 쓴다.

막대는 수익률이 높은 순으로 왼쪽부터 늘어서고, 손실이 난 지점은 0선 아래로
내려간다. 지점 27곳에 '전체'까지 28칸이라 카드 폭에 들어가지 않아 카드
안에서 가로로 스크롤한다.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import pytest

from dashboard import callbacks, layout
from dashboard import figures as shared_figures
from dashboard.data import TOTAL_LABEL, load_dashboard_data
from dashboard.tabs import returns
from dashboard.tabs.returns import figures as return_figures
from dashboard.tabs.returns import metrics
from fixture_data import BRANCH_COUNT

TAB = returns.TAB
RANK_CHART = TAB.charts[0]
SCATTER_CHART = TAB.charts[1]

# '전체'까지 더한 막대 수.
BAR_COUNT = BRANCH_COUNT + 1


@pytest.fixture(scope="module")
def dataset():
    return load_dashboard_data()


def _rank(dataset, period: str = "1년") -> go.Figure:
    return RANK_CHART.build(dataset, {"period": period})


def _scatter(dataset) -> go.Figure:
    return SCATTER_CHART.build(dataset, {})


# --- 계산 -------------------------------------------------------------------
def test_rank_orders_every_branch_and_the_total(dataset):
    """'전체'도 함께 줄 세운다. 지점 27곳에 한 칸 더해 28칸이다."""
    rank = metrics.return_rank(
        dataset.branch_return, dataset.branch_return_total, "return_1y"
    )
    assert len(rank) == BAR_COUNT
    assert list(rank[metrics.TOTAL_FLAG]).count(True) == 1
    # 왼쪽부터 수익률이 높다.
    values = list(rank["value"])
    assert values == sorted(values, reverse=True)


def test_rank_numbers_branches_only(dataset):
    """순위는 지점끼리만 매긴다.

    '전체'는 지점이 아니라 견주는 기준이라 몇 위인지가 뜻을 갖지 않는다.
    함께 세면 그 아래 지점이 모두 한 칸씩 밀린다.
    """
    rank = metrics.return_rank(
        dataset.branch_return, dataset.branch_return_total, "return_3y"
    )
    total = rank[rank[metrics.TOTAL_FLAG]]
    branches = rank[~rank[metrics.TOTAL_FLAG]]
    assert total["rank"].isna().all()
    assert sorted(branches["rank"]) == list(range(1, BRANCH_COUNT + 1))
    assert metrics.branch_count(rank) == BRANCH_COUNT


def test_rank_keeps_missing_values_out_of_the_ranking():
    """수익률이 없는 지점은 등수를 받지 않고 뒤로 간다.

    0으로 채우면 '수익이 0%였다'는 뜻이 되어 '값이 없다'와 달라진다
    (→ AGENTS.md §9).
    """
    returns_frame = pd.DataFrame(
        {
            "branch_name": ["지점 01", "지점 02", "지점 03"],
            "return_1y": [5.0, np.nan, 12.0],
        }
    )
    rank = metrics.return_rank(returns_frame, None, "return_1y")
    assert list(rank["branch_name"]) == ["지점 03", "지점 01", "지점 02"]
    assert list(rank["rank"])[:2] == [1.0, 2.0]
    assert pd.isna(rank["rank"].iloc[2])
    assert metrics.branch_count(rank) == 3


def test_rank_gives_tied_returns_the_same_place():
    """수익률이 같으면 같은 등수를 준다."""
    returns_frame = pd.DataFrame(
        {
            "branch_name": ["지점 01", "지점 02", "지점 03"],
            "return_1y": [7.5, 7.5, 1.0],
        }
    )
    rank = metrics.return_rank(returns_frame, None, "return_1y")
    assert sorted(rank["rank"]) == [1.0, 1.0, 3.0]


def test_scatter_pairs_both_periods(dataset):
    """가로가 1년, 세로가 3년이다. '전체'도 한 점으로 들어온다."""
    scatter = metrics.return_scatter(
        dataset.branch_return,
        dataset.branch_return_total,
        returns.SCATTER_X_COLUMN,
        returns.SCATTER_Y_COLUMN,
    )
    assert len(scatter) == BAR_COUNT
    assert list(scatter[metrics.TOTAL_FLAG]).count(True) == 1
    first = dataset.branch_return.iloc[0]
    row = scatter[scatter["branch_name"] == first["branch_name"]].iloc[0]
    assert row["x"] == first["return_1y"]
    assert row["y"] == first["return_3y"]


def test_scatter_drops_points_that_miss_a_value():
    """한쪽 수익률이 없으면 찍을 자리가 없다. 0으로 놓지 않고 뺀다."""
    returns_frame = pd.DataFrame(
        {
            "branch_name": ["지점 01", "지점 02"],
            "return_1y": [5.0, np.nan],
            "return_3y": [11.0, 20.0],
        }
    )
    scatter = metrics.return_scatter(
        returns_frame, None, "return_1y", "return_3y"
    )
    assert list(scatter["branch_name"]) == ["지점 01"]


def test_metrics_handle_missing_source():
    """원본이 없으면 빈 프레임을 돌려주고 멈추지 않는다."""
    empty = pd.DataFrame()
    assert metrics.return_rank(empty, empty, "return_1y").empty
    assert metrics.return_scatter(
        empty, empty, "return_1y", "return_3y"
    ).empty
    assert metrics.branch_count(pd.DataFrame()) == 0


# --- 막대그래프 --------------------------------------------------------------
def test_rank_figure_draws_one_bar_per_branch(dataset):
    figure = _rank(dataset)
    assert isinstance(figure, go.Figure)
    assert len(figure.data) == 1
    bar = figure.data[0]
    assert bar.type == "bar"
    assert len(bar.x) == BAR_COUNT
    assert TOTAL_LABEL in list(bar.x)


def test_rank_figure_sorts_from_high_to_low(dataset):
    """왼쪽부터 수익률이 높다. 축도 그 순서를 그대로 쓴다."""
    figure = _rank(dataset, "3년")
    values = [value for value in figure.data[0].y if value is not None]
    assert values == sorted(values, reverse=True)
    assert list(figure.layout.xaxis.categoryarray) == list(
        figure.data[0].x
    )


def test_rank_figure_shows_losses_below_the_axis(dataset):
    """수익률이 음수인 지점은 0선 아래로 막대가 내려간다.

    축 범위가 0에서 잘리면 손실 막대가 통째로 사라진다
    (→ figures._padded).
    """
    figure = _rank(dataset)
    values = list(figure.data[0].y)
    assert min(values) < 0, "표본에 손실이 난 지점이 있어야 한다"
    low, high = figure.layout.yaxis.range
    assert low < min(values)
    assert high > max(values)
    assert low < 0 < high
    assert figure.layout.yaxis.zeroline is True


def test_rank_figure_marks_the_total_apart(dataset):
    """'전체' 막대만 색이 다르다.

    색만으로 구분하지 않는다 — 축 눈금에 '전체'라는 이름이 그대로 적힌다
    (→ AGENTS.md §5.2).
    """
    figure = _rank(dataset)
    bar = figure.data[0]
    names = list(bar.x)
    colors = list(bar.marker.color)
    at = names.index(TOTAL_LABEL)
    assert colors[at] == return_figures.COLOR_TOTAL
    assert set(colors) == {
        return_figures.COLOR_TOTAL,
        return_figures.COLOR_BRANCH,
    }
    assert colors.count(return_figures.COLOR_TOTAL) == 1


def test_rank_figure_labels_each_bar_with_its_sign(dataset):
    """막대 위에 값을 적는다. 부호가 붙어 손실이 글자로도 드러난다."""
    figure = _rank(dataset)
    texts = list(figure.data[0].text)
    assert len(texts) == BAR_COUNT
    assert all(text.endswith("%") for text in texts)
    assert any(text.startswith("-") for text in texts)
    assert any(text.startswith("+") for text in texts)
    # 막대가 좁아 글자가 축 밖으로 나가도 지우지 않는다.
    assert figure.data[0].cliponaxis is False


def test_rank_figure_hover_names_the_period_and_place(dataset):
    """hover에 기간과 지점 순위를 함께 적는다. '전체'에는 순위가 없다."""
    figure = _rank(dataset, "3년")
    bar = figure.data[0]
    assert "3년 수익률" in bar.hovertemplate
    assert f"{BRANCH_COUNT}곳" in bar.hovertemplate
    names = list(bar.x)
    at = names.index(TOTAL_LABEL)
    assert bar.customdata[at][1] == "-"
    assert bar.customdata[0][1] == "1위"


def test_rank_figure_follows_the_period_radio(dataset):
    """라디오를 바꾸면 그 기간의 값으로 다시 그린다."""
    one_year = _rank(dataset, "1년")
    three_year = _rank(dataset, "3년")
    assert list(one_year.data[0].y) != list(three_year.data[0].y)
    assert "1년 수익률" in one_year.layout.yaxis.title.text
    assert "3년 수익률" in three_year.layout.yaxis.title.text


def test_period_radio_offers_both_periods(dataset):
    """기간은 두 개뿐이라 펼치지 않고 라디오로 그린다."""
    select = RANK_CHART.selects[0]
    assert select.kind == "radio"
    assert select.options(dataset) == ["1년", "3년"]
    assert RANK_CHART.defaults(dataset) == {"period": "1년"}


# --- 산점도 -----------------------------------------------------------------
def test_scatter_figure_puts_one_year_across_and_three_years_up(dataset):
    figure = _scatter(dataset)
    assert "1년 수익률" in figure.layout.xaxis.title.text
    assert "3년 수익률" in figure.layout.yaxis.title.text
    assert figure.layout.xaxis.ticksuffix == "%"
    assert figure.layout.yaxis.ticksuffix == "%"


def test_scatter_figure_separates_the_total_point(dataset):
    """'전체'는 계열을 나눠 그린다.

    범례에 이름이 남고 점 모양도 달라 색만으로 구분되지 않는다.
    """
    figure = _scatter(dataset)
    names = [trace.name for trace in figure.data]
    assert names == ["지점", TOTAL_LABEL]
    branch, total = figure.data
    assert len(branch.x) == BRANCH_COUNT
    assert len(total.x) == 1
    assert branch.marker.symbol != total.marker.symbol
    assert total.marker.color == return_figures.COLOR_TOTAL


def test_scatter_figure_labels_every_point(dataset):
    """점만 찍혀 있으면 어느 지점인지 알 수 없다."""
    figure = _scatter(dataset)
    labels = list(figure.data[0].text)
    assert len(labels) == BRANCH_COUNT
    assert all(labels)
    assert set(labels) == set(dataset.branch_return["branch_name"])


def test_scatter_figure_draws_zero_reference_lines(dataset):
    """이익과 손실을 가르는 기준선 둘이 사분면을 만든다."""
    figure = _scatter(dataset)
    horizontal = [
        shape
        for shape in figure.layout.shapes
        if shape.y0 == shape.y1 == 0
    ]
    vertical = [
        shape
        for shape in figure.layout.shapes
        if shape.x0 == shape.x1 == 0
    ]
    assert horizontal and vertical


def test_scatter_axes_are_not_cut_at_zero(dataset):
    """손실이 난 지점이 축 밖으로 밀리지 않는다."""
    figure = _scatter(dataset)
    for axis, trace_axis in (("xaxis", "x"), ("yaxis", "y")):
        low, high = figure.layout[axis].range
        values = [
            value
            for trace in figure.data
            for value in getattr(trace, trace_axis)
        ]
        assert low < min(values) and high > max(values)


def test_only_the_scatter_allows_zooming():
    """점 27개가 겹치면 확대해서 본다. 막대는 가로 스크롤로 훑는다."""
    zoomable = [chart.key for chart in TAB.charts if chart.zoomable]
    assert zoomable == ["scatter"]
    assert SCATTER_CHART.note == returns.ZOOM_GUIDE
    assert _scatter(load_dashboard_data()).layout.dragmode == "pan"


# --- 가로 스크롤 -------------------------------------------------------------
def test_rank_chart_is_wider_than_the_card(dataset):
    """막대 28칸이 카드 폭에 들어가지 않아 그래프를 넓게 그린다."""
    width = RANK_CHART.scroll_width(dataset)
    assert width.endswith("px")
    assert int(width.removesuffix("px")) == (
        returns.RANK_SIDE_WIDTH + BAR_COUNT * returns.RANK_BAR_WIDTH
    )
    # 산점도는 카드 폭을 그대로 쓴다.
    assert SCATTER_CHART.scroll_width is None


def test_rank_chart_width_follows_the_data(dataset):
    """지점이 줄면 폭도 줄어든다. 칸 수를 코드에 적어 두지 않는다."""
    trimmed = load_dashboard_data(
        filters={"branch_names": dataset.branch_names[:5]}
    )
    # 지점을 걸러내면 '전체' 행은 화면과 맞지 않아 빠진다
    # (→ data._apply_filters).
    assert int(RANK_CHART.scroll_width(trimmed).removesuffix("px")) < int(
        RANK_CHART.scroll_width(dataset).removesuffix("px")
    )


def test_wide_chart_scrolls_inside_the_card(dataset):
    """카드 안에서 가로로 스크롤한다. 페이지가 옆으로 늘어나지 않는다."""
    assert layout.chart_body_class(RANK_CHART, "1408px") == (
        "card-body chart-scroll"
    )
    assert layout.chart_body_class(SCATTER_CHART, "") == "card-body"
    assert layout.chart_style(RANK_CHART, "1408px")["width"] == "1408px"
    assert layout.chart_style(SCATTER_CHART, "")["width"] == "100%"


def test_scroll_width_reaches_the_screen(dataset):
    """선언이 정한 폭이 첫 화면 값에 그대로 실린다."""
    view = callbacks.build_chart_view(RANK_CHART, dataset)
    assert view["scroll_width"] == RANK_CHART.scroll_width(dataset)
    assert callbacks.build_chart_view(SCATTER_CHART, dataset)[
        "scroll_width"
    ] == ""


# --- 원본이 없을 때 ----------------------------------------------------------
def _without_source(dataset):
    """수익률 원본만 빠진 데이터."""
    from dashboard.data import FRAME_NAMES, DashboardData

    frames = {name: getattr(dataset, name) for name in FRAME_NAMES}
    totals = {
        f"{name}_total": dataset.total_of(name) for name in FRAME_NAMES
    }
    frames["branch_return"] = pd.DataFrame()
    totals["branch_return_total"] = pd.DataFrame()
    return DashboardData(**frames, **totals)


def test_charts_say_why_they_are_empty(dataset):
    """원본이 없으면 왜 비었는지 그래프 자리에 적는다.

    아무것도 없이 두면 고장인지 데이터가 없는 것인지 구분할 수 없다
    (→ AGENTS.md §11).
    """
    data = _without_source(dataset)
    for figure in (_rank(data), _scatter(data)):
        texts = [note.text for note in figure.layout.annotations]
        assert returns.EMPTY_NOTE in texts
    assert returns._scatter_text(data) == returns.EMPTY_NOTE
    # 안내 문구뿐인 그래프는 넓게 늘리지 않는다.
    assert RANK_CHART.scroll_width(data) == ""


def test_figures_handle_empty_input():
    empty = pd.DataFrame()
    assert isinstance(
        return_figures.create_return_rank_figure(empty, "1년 수익률"),
        go.Figure,
    )
    assert isinstance(
        return_figures.create_return_scatter_figure(empty, "가로", "세로"),
        go.Figure,
    )


# --- 화면 조립 --------------------------------------------------------------
def test_tab_is_registered_with_two_charts_in_one_row(dataset):
    """한 줄에 두 카드다. 선택 줄이 따로 없어 라디오는 카드 안에 붙는다."""
    from dashboard import tabs as tab_registry

    assert tab_registry.find("return") is TAB
    assert [chart.key for chart in TAB.charts] == ["rank", "scatter"]
    assert TAB.tables == ()
    assert TAB.selects == ()
    assert len(TAB.grid_rows) == 1
    # 탭 순서에서 상품 다음 자리다.
    order = [value for value, _label in tab_registry.TAB_ORDER]
    assert order[order.index("product") + 1] == "return"
    assert dict(tab_registry.TAB_ORDER)["return"] == "수익률"


def test_hover_labels_are_readable(dataset):
    """hover 글자색을 직접 정한다.

    비워 두면 Plotly가 계열 색으로 글자를 그려 흰 배경 위에서 흐려진다.
    """
    for figure in (_rank(dataset), _scatter(dataset)):
        hover = figure.layout.hoverlabel
        assert hover.bgcolor == shared_figures.COLOR_SURFACE
        assert hover.font.color == shared_figures.COLOR_TEXT
