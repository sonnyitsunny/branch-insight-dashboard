"""수익률 탭 검증.

윗줄 왼쪽이 지점 수익률 분석(막대), 오른쪽이 두 기간을 견주는 지점 수익률
분석(산점도)이다. 두 그림 모두 지점별 수익률 원본 하나를 쓴다.

막대는 수익률이 높은 순으로 왼쪽부터 늘어서고, 손실이 난 지점은 0선 아래로
내려간다. 지점 27곳에 '전체'까지 28칸이라 카드 폭에 들어가지 않아 카드
안에서 가로로 스크롤한다.

둘째 줄 왼쪽은 수익률 구간별 고객 비중(그룹형 세로 막대)이고 다른 원본을
쓴다(→ dashboard/sources/return_group.py). 그 오른쪽부터 다섯째 줄까지는
구간별 수익률 카드 일곱이 가로 막대로 이어진다. 카드 모양이 같아 선언표
하나로 만든다(→ returns.SEGMENT_CARDS).

모든 카드가 라디오로 기간을, 드롭다운으로 지점을 고르며 '전체'는 늘 함께
그린다.
"""

from __future__ import annotations

from dataclasses import replace

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import pytest

from dashboard import callbacks, layout
from dashboard import figures as shared_figures
from dashboard.data import (
    ASSET_GROUPS,
    RETURN_GROUPS,
    RETURN_PERIODS,
    TOTAL_LABEL,
    load_dashboard_data,
)
from dashboard.tabs import returns
from dashboard.tabs.registry import KIND_DROPDOWN, KIND_RADIO
from dashboard.tabs.returns import figures as return_figures
from dashboard.tabs.returns import measure_label, metrics
from fixture_data import BRANCH_COUNT

TAB = returns.TAB
RANK_CHART = TAB.charts[0]
SCATTER_CHART = TAB.charts[1]
GROUP_CHART = TAB.charts[2]
# 구간별 수익률 카드 일곱. 선언표 차례가 곧 화면 차례다.
SEGMENT_CHARTS = {
    chart.key: chart for chart in TAB.charts[3:]
}
SEGMENT_CARDS = {card.key: card for card in returns.SEGMENT_CARDS}
ASSET_CHART = SEGMENT_CHARTS["asset"]
ASSET_CARD = SEGMENT_CARDS["asset"]

# '전체'까지 더한 막대 수.
BAR_COUNT = BRANCH_COUNT + 1


@pytest.fixture(scope="module")
def dataset():
    return load_dashboard_data()


def _rank(dataset, period: str = "1년") -> go.Figure:
    return RANK_CHART.build(dataset, {"period": period})


def _scatter(dataset) -> go.Figure:
    return SCATTER_CHART.build(dataset, {})


def _group(
    dataset, period: str = "1년", branch_name: str = ""
) -> go.Figure:
    return GROUP_CHART.build(
        dataset, {"period": period, "branch": branch_name}
    )


def _asset(
    dataset, period: str = "1년", branch_name: str = ""
) -> go.Figure:
    return ASSET_CHART.build(
        dataset, {"period": period, "branch": branch_name}
    )


def _segment(
    chart, dataset, period: str = "1년", branch_name: str = ""
) -> go.Figure:
    return chart.build(dataset, {"period": period, "branch": branch_name})


def _latest(frame: pd.DataFrame) -> pd.DataFrame:
    """최근월 행만. 표본이 두 달을 담고 있어 견줄 때 골라 써야 한다."""
    month = frame["base_month"].max()
    return frame[frame["base_month"] == month].reset_index(drop=True)


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


def test_rank_and_scatter_use_only_the_latest_month(dataset):
    """원본이 여러 달을 담고 있어도 최근월만 그린다.

    거르지 않으면 지점마다 막대가 달 수만큼 서고 산점도에도 같은 지점
    점이 여럿 찍힌다. 오류 없이 그럴듯하게 그려져 알아채기 어렵다.
    """
    frame = dataset.branch_return
    assert frame["base_month"].nunique() > 1, "표본이 두 달을 담아야 한다"

    rank = metrics.return_rank(
        frame, dataset.branch_return_total, "return_1y"
    )
    assert len(rank) == BAR_COUNT
    assert len(set(rank["branch_name"])) == BAR_COUNT

    # 값까지 최근월 것이어야 한다. 표본은 두 달의 값이 서로 다르다.
    latest = _latest(frame).set_index("branch_name")["return_1y"]
    picked = rank.set_index("branch_name")["value"]
    for name, value in latest.items():
        assert picked[name] == value

    # 카드 폭도 파일의 행 수가 아니라 막대 수로 잡는다.
    assert returns._rank_width(dataset) == (
        f"{returns.RANK_SIDE_WIDTH + BAR_COUNT * returns.RANK_BAR_WIDTH}px"
    )


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
    first = _latest(dataset.branch_return).iloc[0]
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


# --- 수익률 구간별 고객 비중 -------------------------------------------------
def _group_source() -> pd.DataFrame:
    """구간 셋만 담은 작은 그룹별 비중 원본.

    표본 파일은 구간이 열 개라 값을 눈으로 따라가기 어렵다. 계산 규칙만
    보는 검사는 손으로 적은 작은 프레임을 쓴다.
    """
    groups = list(RETURN_GROUPS[:3])
    rows = []
    for branch, counts, shares in (
        ("지점 01", [10, 30, 60], [10.0, 30.0, 60.0]),
        ("지점 02", [40, 40, 20], [40.0, 40.0, 20.0]),
    ):
        for group, count, share in zip(groups, counts, shares):
            rows.append(
                {
                    "base_month": "2026-07",
                    "branch_id": branch[-2:],
                    "branch_name": branch,
                    "return_period": RETURN_PERIODS[0],
                    "return_group": group,
                    "customer_count": count,
                    "branch_customer_count": 100,
                    "customer_share": share,
                }
            )
    return pd.DataFrame(rows)


def test_group_distribution_shows_the_total_and_the_branch(dataset):
    """구간마다 계열이 둘이다. '전체'는 고른 지점과 늘 함께 나온다."""
    distribution = metrics.return_group_distribution(
        dataset.return_group,
        dataset.return_group_total,
        dataset.branch_names[0],
        RETURN_PERIODS[0],
    )
    assert list(distribution.columns) == list(metrics.GROUP_COLUMNS)
    assert set(distribution["scope"]) == {
        TOTAL_LABEL,
        dataset.branch_names[0],
    }
    assert len(distribution) == 2 * len(RETURN_GROUPS)
    # 구간은 원본 차례 그대로다. 가나다순이면 '+100%이상'이 맨 앞에 온다.
    for scope in (TOTAL_LABEL, dataset.branch_names[0]):
        rows = distribution[distribution["scope"] == scope]
        assert list(rows["return_group"]) == list(RETURN_GROUPS)
        # 한 계열의 비중을 모두 더하면 100%가 된다.
        assert abs(rows["share"].sum() - 100.0) < 0.5


def test_group_distribution_splits_the_periods(dataset):
    """1년과 3년은 다른 분포다. 기간을 거르지 않으면 둘이 겹쳐 세어진다."""
    figures_by_period = {
        period: metrics.return_group_distribution(
            dataset.return_group,
            dataset.return_group_total,
            dataset.branch_names[0],
            period,
        )
        for period in RETURN_PERIODS
    }
    for distribution in figures_by_period.values():
        assert len(distribution) == 2 * len(RETURN_GROUPS)
    one, three = (figures_by_period[period] for period in RETURN_PERIODS)
    assert not one["share"].equals(three["share"])


def test_group_distribution_keeps_the_source_share():
    """원본이 담은 비중을 그대로 쓴다. 인원수에서 다시 만들지 않는다.

    반올림 때문에 화면 숫자가 원본과 달라진다(→ AGENTS.md §9). 원본 값과
    인원수 기준 값이 다르게 만들어 어느 쪽을 쓰는지 가른다.
    """
    source = _group_source()
    source.loc[source["branch_name"] == "지점 01", "customer_share"] = [
        11.0,
        29.0,
        60.0,
    ]
    distribution = metrics.return_group_distribution(
        source, None, "지점 01", RETURN_PERIODS[0]
    )
    branch = distribution[distribution["scope"] == "지점 01"]
    assert list(branch["share"].dropna()) == [11.0, 29.0, 60.0]


def test_group_distribution_builds_the_total_from_counts():
    """'전체' 행이 없으면 지점 인원수를 모아 만든다.

    비중은 더할 수 없으므로 그때만 인원수에서 다시 계산한다.
    """
    distribution = metrics.return_group_distribution(
        _group_source(), None, "지점 01", RETURN_PERIODS[0]
    )
    total = distribution[distribution["scope"] == TOTAL_LABEL]
    # 두 지점의 구간별 인원수 합은 50·70·80이고 분모는 200이다.
    assert list(total["customer_count"].dropna()) == [50.0, 70.0, 80.0]
    assert list(total["share"].dropna()) == [25.0, 35.0, 40.0]


def test_group_distribution_leaves_missing_groups_empty():
    """원본에 없는 구간은 비워 둔다. 0으로 채우지 않는다."""
    distribution = metrics.return_group_distribution(
        _group_source(), None, "지점 01", RETURN_PERIODS[0]
    )
    branch = distribution[distribution["scope"] == "지점 01"]
    missing = branch[~branch["return_group"].isin(RETURN_GROUPS[:3])]
    assert len(missing) == len(RETURN_GROUPS) - 3
    assert missing["customer_count"].isna().all()
    assert missing["share"].isna().all()


def test_group_distribution_ignores_an_unknown_branch():
    """모르는 지점을 고르면 '전체'만 남는다. 화면이 깨지지 않는다."""
    distribution = metrics.return_group_distribution(
        _group_source(), None, "없는 지점", RETURN_PERIODS[0]
    )
    assert set(distribution["scope"]) == {TOTAL_LABEL}


def test_group_chart_draws_both_series(dataset):
    """카드가 라디오와 드롭다운을 갖고, 그림은 계열 둘을 그린다."""
    assert [select.key for select in GROUP_CHART.selects] == [
        "period",
        "branch",
    ]
    assert GROUP_CHART.selects[0].kind == KIND_RADIO
    assert GROUP_CHART.selects[1].kind == KIND_DROPDOWN
    # '전체'는 늘 그리므로 지점 목록에 넣지 않는다.
    assert TOTAL_LABEL not in GROUP_CHART.selects[1].options(dataset)

    branch_name = dataset.branch_names[0]
    figure = _group(dataset, branch_name=branch_name)
    assert [trace.name for trace in figure.data] == [
        TOTAL_LABEL,
        branch_name,
    ]
    assert figure.layout.barmode == "group"
    assert list(figure.data[0].x) == list(RETURN_GROUPS)
    assert figure.layout.yaxis.ticksuffix == "%"
    # 색은 두 계열이 달라야 하고, '전체'는 이 탭의 다른 그림과 같은 색이다.
    assert figure.data[0].marker.color == return_figures.COLOR_TOTAL
    assert figure.data[1].marker.color == return_figures.COLOR_BRANCH


def test_group_chart_follows_the_selected_branch(dataset):
    """드롭다운을 바꾸면 둘째 계열만 바뀌고 '전체'는 그대로다."""
    first, second = dataset.branch_names[0], dataset.branch_names[1]
    one = _group(dataset, branch_name=first)
    other = _group(dataset, branch_name=second)
    assert list(one.data[0].y) == list(other.data[0].y)
    assert one.data[1].name == first
    assert other.data[1].name == second
    assert list(one.data[1].y) != list(other.data[1].y)


def test_group_chart_shows_a_note_without_the_source(dataset):
    """원본이 없으면 빈 그림에 안내 문구를 적는다(→ AGENTS.md §11)."""
    without = replace(dataset, return_group=pd.DataFrame())
    figure = GROUP_CHART.build(
        without, {"period": RETURN_PERIODS[0], "branch": "지점 01"}
    )
    assert not figure.data
    assert returns.GROUP_EMPTY_NOTE in str(figure.layout.annotations)


# --- 자산 규모 구간별 수익률 -------------------------------------------------
def _asset_source() -> pd.DataFrame:
    """구간 셋만 담은 작은 자산규모별 수익률 원본."""
    rows = []
    for branch, values in (
        ("지점 01", [-4.0, 2.5, 9.0]),
        ("지점 02", [1.0, 3.0, 5.0]),
    ):
        for group, value in zip(ASSET_GROUPS[:3], values):
            rows.append(
                {
                    "base_month": "2026-07",
                    "branch_id": branch[-2:],
                    "branch_name": branch,
                    "asset_group": group,
                    "return_1y": value,
                    "return_3y": value * 2,
                }
            )
    return pd.DataFrame(rows)


def test_segment_returns_pairs_the_total_with_the_branch(dataset):
    """구간마다 계열이 둘이다. 구간은 목록 차례 그대로 늘어선다."""
    distribution = metrics.segment_returns(
        dataset.asset_return,
        dataset.asset_return_total,
        dataset.branch_names[0],
        "asset_group",
        ASSET_GROUPS,
        "return_1y",
    )
    assert list(distribution.columns) == list(metrics.SEGMENT_COLUMNS)
    assert len(distribution) == 2 * len(ASSET_GROUPS)
    for scope in (TOTAL_LABEL, dataset.branch_names[0]):
        rows = distribution[distribution["scope"] == scope]
        assert list(rows["segment"]) == list(ASSET_GROUPS)
        assert rows["value"].notna().all()


def test_segment_returns_take_the_source_value(dataset):
    """원본 값을 그대로 옮긴다. 수익률은 더하거나 평균 내지 않는다."""
    branch_name = dataset.branch_names[0]
    distribution = metrics.segment_returns(
        dataset.asset_return,
        dataset.asset_return_total,
        branch_name,
        "asset_group",
        ASSET_GROUPS,
        "return_3y",
    )
    source = dataset.asset_return[
        dataset.asset_return["branch_name"] == branch_name
    ].set_index("asset_group")["return_3y"]
    branch = distribution[distribution["scope"] == branch_name]
    assert list(branch["value"]) == [
        source[group] for group in ASSET_GROUPS
    ]


def test_segment_returns_leave_missing_groups_empty():
    """원본에 없는 구간은 비워 둔다. 0으로 채우지 않는다."""
    distribution = metrics.segment_returns(
        _asset_source(), None, "지점 01", "asset_group", ASSET_GROUPS,
        "return_1y",
    )
    branch = distribution[distribution["scope"] == "지점 01"]
    assert list(branch["value"].dropna()) == [-4.0, 2.5, 9.0]
    assert branch["value"].isna().sum() == len(ASSET_GROUPS) - 3


def test_segment_returns_skip_the_total_when_the_source_has_none():
    """'전체' 행이 없으면 그 계열을 빼고 지점만 그린다.

    수익률은 더할 수 없어 지점 값에서 '전체'를 되만들 수 없다
    (→ AGENTS.md §9).
    """
    distribution = metrics.segment_returns(
        _asset_source(), None, "지점 01", "asset_group", ASSET_GROUPS,
        "return_1y",
    )
    assert set(distribution["scope"]) == {"지점 01"}


def test_asset_chart_draws_horizontal_bars(dataset):
    """막대가 가로다. 세로축은 자산 규모 구간이고 가로축이 수익률이다."""
    branch_name = dataset.branch_names[0]
    figure = _asset(dataset, branch_name=branch_name)
    assert [trace.name for trace in figure.data] == [
        TOTAL_LABEL,
        branch_name,
    ]
    assert {trace.orientation for trace in figure.data} == {"h"}
    assert figure.layout.barmode == "group"
    assert list(figure.data[0].y) == list(ASSET_GROUPS)
    assert figure.layout.xaxis.ticksuffix == "%"
    assert figure.data[0].marker.color == return_figures.COLOR_TOTAL
    assert figure.data[1].marker.color == return_figures.COLOR_BRANCH


def test_asset_chart_puts_the_smallest_group_on_top(dataset):
    """위에서 아래로 갈수록 자산 규모가 커진다.

    Plotly는 세로 분류축을 아래에서 위로 쌓는다. 뒤집지 않으면 목록
    차례가 거꾸로 보인다.
    """
    figure = _asset(dataset, branch_name=dataset.branch_names[0])
    axis = figure.layout.yaxis
    assert list(axis.categoryarray) == list(ASSET_GROUPS)
    assert axis.autorange == "reversed"


def test_asset_chart_keeps_losses_left_of_zero():
    """손실이 난 구간은 0선 왼쪽으로 뻗는다. 0선이 화면에 남는다."""
    distribution = metrics.segment_returns(
        _asset_source(), None, "지점 01", "asset_group", ASSET_GROUPS,
        "return_1y",
    )
    figure = return_figures.create_segment_return_figure(
        distribution, "지점 01", ASSET_CARD.axis_title, "1년 수익률"
    )
    assert min(figure.data[0].x) < 0
    assert figure.layout.xaxis.zeroline is True
    low, high = figure.layout.xaxis.range
    assert low < -4.0 and high > 9.0


def test_asset_chart_follows_both_controls(dataset):
    """기간과 지점을 각각 바꾸면 그림이 따라 바뀐다."""
    assert [select.key for select in ASSET_CHART.selects] == [
        "period",
        "branch",
    ]
    first, second = dataset.branch_names[0], dataset.branch_names[1]
    one = _asset(dataset, branch_name=first)
    other = _asset(dataset, branch_name=second)
    # '전체'는 그대로고 지점 계열만 바뀐다.
    assert list(one.data[0].x) == list(other.data[0].x)
    assert list(one.data[1].x) != list(other.data[1].x)

    three = _asset(dataset, period=RETURN_PERIODS[1], branch_name=first)
    assert list(three.data[1].x) != list(one.data[1].x)
    assert "3년 수익률" in three.layout.xaxis.title.text


def test_asset_chart_shows_a_note_without_the_source(dataset):
    """원본이 없으면 빈 그림에 안내 문구를 적는다(→ AGENTS.md §11)."""
    without = replace(dataset, asset_return=pd.DataFrame())
    figure = ASSET_CHART.build(
        without, {"period": RETURN_PERIODS[0], "branch": "지점 01"}
    )
    assert not figure.data
    assert ASSET_CARD.empty_note in str(figure.layout.annotations)


# --- 구간별 수익률 카드 일곱 -------------------------------------------------
# 카드가 같은 선언표에서 만들어지므로 검사도 일곱을 함께 돈다. 하나만
# 검사하면 표에 줄을 더할 때 잘못 적어도 드러나지 않는다.
SEGMENT_KEYS = [card.key for card in returns.SEGMENT_CARDS]


def test_segment_cards_cover_every_source():
    """선언표가 `수익률_seg_...` 원본 일곱을 모두 담는다.

    데이터 계층에 프레임이 있는데 카드가 없으면 화면에 나오지 않는다.
    """
    assert SEGMENT_KEYS == [
        "asset",
        "stock-share",
        "overseas-share",
        "etf-share",
        "pension-share",
        "stock-turnover",
        "age",
    ]
    frames = [card.frame for card in returns.SEGMENT_CARDS]
    assert frames == [
        "asset_return",
        "stock_share_return",
        "overseas_share_return",
        "etf_share_return",
        "pension_share_return",
        "stock_turnover_return",
        "age_return",
    ]
    # 제목·축 이름·구간 컬럼은 카드마다 달라야 한다. 복사하다 한 줄을
    # 그대로 두면 두 카드가 같은 그림을 그린다.
    for field in ("title", "axis_title", "group_column", "direction"):
        values = [getattr(card, field) for card in returns.SEGMENT_CARDS]
        assert len(set(values)) == len(values)


def test_only_the_age_card_stands_vertical(dataset):
    """연령대만 세로 막대다. 나머지 여섯은 가로 막대다.

    연령 구간은 `10대이하`처럼 짧아 가로축 눈금에 눕히지 않고 들어간다.
    자산 규모나 비중 구간은 이름이 길어 가로 막대로 둔다.
    """
    assert [
        card.key for card in returns.SEGMENT_CARDS if card.vertical
    ] == ["age"]
    age = _segment(
        SEGMENT_CHARTS["age"], dataset, branch_name=dataset.branch_names[0]
    )
    assert {trace.orientation for trace in age.data} == {"v"}
    # 세로축이 수익률이고 0선이 손실을 가른다.
    assert age.layout.yaxis.zeroline is True
    assert min(age.data[1].y) < max(age.data[1].y)


@pytest.mark.parametrize("key", SEGMENT_KEYS)
def test_segment_card_draws_the_total_and_the_branch(dataset, key):
    """카드마다 '전체'와 고른 지점을 막대 두 계열로 그린다.

    구간 축과 수익률 축이 어느 쪽인지는 카드가 정한다
    (→ returns.SegmentCard.vertical).
    """
    card = SEGMENT_CARDS[key]
    branch_name = dataset.branch_names[0]
    figure = _segment(
        SEGMENT_CHARTS[key], dataset, branch_name=branch_name
    )
    assert [trace.name for trace in figure.data] == [
        TOTAL_LABEL,
        branch_name,
    ]
    if card.vertical:
        assert {trace.orientation for trace in figure.data} == {"v"}
        # 구간이 가로축에 왼쪽부터 목록 차례대로 늘어선다.
        assert list(figure.data[0].x) == list(card.groups)
        assert figure.layout.xaxis.autorange is None
        assert figure.layout.yaxis.ticksuffix == "%"
        assert card.axis_title in figure.layout.xaxis.title.text
    else:
        assert {trace.orientation for trace in figure.data} == {"h"}
        # 구간이 세로축에 위에서 아래로 늘어선다.
        assert list(figure.data[0].y) == list(card.groups)
        assert figure.layout.yaxis.autorange == "reversed"
        assert figure.layout.xaxis.ticksuffix == "%"
        assert card.axis_title in figure.layout.yaxis.title.text


@pytest.mark.parametrize("key", SEGMENT_KEYS)
def test_segment_card_follows_both_controls(dataset, key):
    """기간과 지점을 각각 바꾸면 그림이 따라 바뀐다."""
    chart = SEGMENT_CHARTS[key]
    assert [select.key for select in chart.selects] == ["period", "branch"]

    card = SEGMENT_CARDS[key]
    # 수익률이 놓인 축. 세로 막대는 y, 가로 막대는 x다.
    values = (
        (lambda trace: list(trace.y))
        if card.vertical
        else (lambda trace: list(trace.x))
    )
    first, second = dataset.branch_names[0], dataset.branch_names[1]
    one = _segment(chart, dataset, branch_name=first)
    other = _segment(chart, dataset, branch_name=second)
    # '전체'는 그대로고 지점 계열만 바뀐다.
    assert values(one.data[0]) == values(other.data[0])
    assert values(one.data[1]) != values(other.data[1])

    three = _segment(
        chart, dataset, period=RETURN_PERIODS[1], branch_name=first
    )
    assert values(three.data[1]) != values(one.data[1])
    measure_axis = (
        three.layout.yaxis if card.vertical else three.layout.xaxis
    )
    assert measure_label(RETURN_PERIODS[1]) in measure_axis.title.text


@pytest.mark.parametrize("key", SEGMENT_KEYS)
def test_segment_card_shows_a_note_without_the_source(dataset, key):
    """원본이 없으면 빈 그림에 그 원본 이름을 적는다(→ AGENTS.md §11)."""
    card = SEGMENT_CARDS[key]
    without = replace(dataset, **{card.frame: pd.DataFrame()})
    figure = SEGMENT_CHARTS[key].build(
        without, {"period": RETURN_PERIODS[0], "branch": "지점 01"}
    )
    assert not figure.data
    assert card.empty_note in str(figure.layout.annotations)
    # 다른 카드는 그대로 그려진다. 원본 하나가 빠져도 화면은 열린다.
    other = [k for k in SEGMENT_KEYS if k != key][0]
    assert SEGMENT_CHARTS[other].build(
        without,
        {"period": RETURN_PERIODS[0], "branch": dataset.branch_names[0]},
    ).data


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
    assert colors[at] == return_figures.COLOR_TOTAL_MARK
    assert set(colors) == {
        return_figures.COLOR_TOTAL_MARK,
        return_figures.COLOR_BRANCH_BAR,
    }
    assert colors.count(return_figures.COLOR_TOTAL_MARK) == 1


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
    assert names == ["영업점", TOTAL_LABEL]
    branch, total = figure.data
    assert len(branch.x) == BRANCH_COUNT
    assert len(total.x) == 1
    assert branch.marker.symbol != total.marker.symbol
    assert total.marker.color == return_figures.COLOR_TOTAL_MARK


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
def test_tab_is_registered_with_ten_charts_in_one_grid(dataset):
    """한 줄에 두 카드씩이라 열 카드가 다섯 줄을 이룬다.

    선택 줄이 따로 없어 라디오와 드롭다운은 카드 안에 붙는다.
    """
    from dashboard import tabs as tab_registry

    assert tab_registry.find("return") is TAB
    assert [chart.key for chart in TAB.charts] == [
        "rank",
        "scatter",
        "group",
        "asset",
        "stock-share",
        "overseas-share",
        "etf-share",
        "pension-share",
        "stock-turnover",
        "age",
    ]
    # 카드가 짝수라 다섯 줄이 꽉 찬다. 모두 같은 높이를 써야 줄마다
    # 아랫선이 맞는다.
    assert len(TAB.charts) % 2 == 0
    assert {chart.height for chart in TAB.charts} == {""}
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
