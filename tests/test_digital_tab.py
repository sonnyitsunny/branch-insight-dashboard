"""디지털 채널 탭 검증.

맨 위 드롭다운 하나가 이 탭의 카드 전체를 움직인다. '전체'와 지점 27곳
중 하나를 고르면 표와 그림이 함께 그 대상을 가리킨다.

카드 넷의 자리는 선언이 적어 둔 `order`가 정한다(→ registry.grid_order).

1. 상단 왼쪽 — 이용고객 추이. 막대가 이용 고객 수, 선이 이용 비중이며
   라디오로 채널을 고른다.
2. 상단 오른쪽 — 채널 이용과 거래활성화. 지점 산점도이고 고른 대상만
   달리 찍는다.
3. 중단 왼쪽 — 이용고객 프로필 표. 행이 항목, 열이 채널이다.
4. 중단 오른쪽 — 이용일수 구간별 이용비중. 채널마다 선 하나다.
"""

from __future__ import annotations

import plotly.graph_objects as go
import pytest

from dashboard import callbacks, grid
from dashboard.data import (
    DIGITAL_CHANNELS,
    DIGITAL_USAGE_DAY_GROUPS,
    TOTAL_LABEL,
    load_dashboard_data,
)
from dashboard.tabs import digital
from dashboard.tabs.digital import metrics
from dashboard.tabs.registry import (
    GRID_CHART,
    GRID_TABLE,
    KIND_DROPDOWN,
    KIND_RADIO,
    grid_order,
)
from fixture_data import BRANCH_COUNT, MONTH_COUNT

TAB = digital.TAB
TREND_CHART = TAB.charts[0]
ACTIVATION_CHART = TAB.charts[1]
DAYS_CHART = TAB.charts[2]
PROFILE_TABLE = TAB.tables[0]

FIRST_BRANCH = "지점 01"


@pytest.fixture(scope="module")
def dataset():
    return load_dashboard_data()


def _scope(scope: str, channel: str = "") -> dict:
    """선택값 묶음. 채널을 비우면 첫 채널을 고른 것으로 본다."""
    chosen = {digital.SELECT_SCOPE: scope}
    if channel:
        chosen[digital.SELECT_CHANNEL] = channel
    return chosen


# --- 탭 뼈대 ----------------------------------------------------------------
def test_tab_is_registered_and_implemented():
    """탭 목록에 들어 있고 이름이 순서 목록의 이름과 같다."""
    from dashboard import tabs as tab_registry

    assert TAB in tab_registry.TABS
    assert tab_registry.find(TAB.value) is TAB
    assert dict(tab_registry.TAB_ORDER)[TAB.value] == TAB.label
    assert TAB.implemented


def test_scope_dropdown_offers_total_and_every_branch(dataset):
    """맨 위 드롭다운은 '전체'와 지점 27곳을 고른다. '전체'가 맨 앞이다.

    지점 이름은 데이터에서 읽는다. 지점이 늘어도 선언을 고치지 않는다.
    """
    (select,) = TAB.selects
    assert select.key == digital.SELECT_SCOPE
    assert select.kind == KIND_DROPDOWN
    options = select.options(dataset)
    assert options[0] == TOTAL_LABEL
    assert len(options) == BRANCH_COUNT + 1
    assert set(options[1:]) == set(dataset.branch_names)
    assert TAB.defaults(dataset)[digital.SELECT_SCOPE] == TOTAL_LABEL


def test_every_card_follows_the_scope_dropdown():
    """카드마다 컨트롤을 또 두지 않는다.

    표와 그림이 한 화면에서 서로 다른 지점을 가리키지 않게 하는 규칙이다
    (→ registry.Chart.follows_tab).
    """
    for chart in TAB.charts:
        assert chart.follows_tab, chart.key
        for select in chart.selects:
            assert select.key == digital.SELECT_CHANNEL, chart.key
    # 표는 탭 선택을 그대로 받으므로 자기 컨트롤이 없다.
    assert PROFILE_TABLE.group == ""


def test_channel_radio_is_on_the_two_top_cards():
    """윗줄 두 카드만 채널을 고른다. 아래 둘은 세 채널을 함께 보여준다."""
    for chart in (TREND_CHART, ACTIVATION_CHART):
        (select,) = chart.selects
        assert select.kind == KIND_RADIO
        assert select.options(None) == list(DIGITAL_CHANNELS)
    assert DAYS_CHART.selects == ()


def test_cards_stand_in_the_declared_order(dataset):
    """카드 자리는 선언이 적어 둔 번호대로다.

    번갈아 놓는 기본 규칙으로는 표가 맨 앞으로 가서 스케치와 달라진다
    (→ registry.grid_order).
    """
    view = callbacks.build_tab_view(TAB, dataset)
    cards = view["tables"]
    order = grid_order(cards, TAB.charts)
    kinds = [kind for kind, _item in order]
    assert kinds == [GRID_CHART, GRID_CHART, GRID_TABLE, GRID_CHART]
    keys = [
        item["title"] if kind == GRID_TABLE else item.key
        for kind, item in order
    ]
    assert keys == [
        "trend",
        "activation",
        "이용고객 프로필",
        "usage-days",
    ]


def test_every_card_builds_something(dataset):
    """빈 화면이 나오지 않는다. 그림은 Figure, 표는 행을 돌려준다."""
    for chart in TAB.charts:
        figure = chart.build(dataset, TAB.defaults(dataset))
        assert isinstance(figure, go.Figure), chart.key
        assert figure.data, chart.key
    _total, rows = PROFILE_TABLE.build(dataset, TAB.defaults(dataset))
    assert len(rows) == len(digital.PROFILE_ITEMS)


# --- 상단 왼쪽 · 이용고객 추이 ------------------------------------------------
def test_trend_draws_count_as_bars_and_share_as_a_line(dataset):
    """막대가 이용 고객 수, 선이 이용 비중이다. 축을 둘로 나눈다."""
    figure = TREND_CHART.build(dataset, _scope(TOTAL_LABEL, "MTS"))
    bar, line = figure.data
    assert isinstance(bar, go.Bar)
    assert isinstance(line, go.Scatter)
    assert line.yaxis == "y2"
    assert len(bar.x) == MONTH_COUNT
    assert figure.layout.yaxis.ticksuffix != "%"
    assert figure.layout.yaxis2.ticksuffix == "%"


def test_trend_follows_the_channel_radio(dataset):
    """채널을 바꾸면 값이 바뀐다. 세 채널이 서로 다른 그림이다."""
    drawn = {
        channel: list(
            TREND_CHART.build(dataset, _scope(TOTAL_LABEL, channel)).data[0].y
        )
        for channel in DIGITAL_CHANNELS
    }
    assert drawn["HTS"] != drawn["MTS"]
    assert drawn["MTS"] != drawn["WEB"]


def test_trend_follows_the_scope_dropdown(dataset):
    """지점을 고르면 '전체'와 다른 값이 그려진다."""
    total = TREND_CHART.build(dataset, _scope(TOTAL_LABEL, "MTS"))
    branch = TREND_CHART.build(dataset, _scope(FIRST_BRANCH, "MTS"))
    assert list(total.data[0].y) != list(branch.data[0].y)
    # '전체'가 지점보다 크다. 지점 하나가 전체보다 많을 수는 없다.
    assert max(total.data[0].y) > max(branch.data[0].y)


def test_trend_keeps_the_source_share(dataset):
    """비중은 원본 값을 그대로 쓴다. 인원수에서 다시 만들지 않는다."""
    trend = metrics.channel_trend(dataset, FIRST_BRANCH, "HTS")
    rows = dataset.digital_channel
    picked = rows[
        (rows["branch_name"] == FIRST_BRANCH) & (rows["channel"] == "HTS")
    ].sort_values("base_month")
    assert list(trend["user_share"]) == list(picked["user_share"])


# --- 상단 오른쪽 · 거래활성화 -------------------------------------------------
def test_activation_puts_every_branch_on_the_chart(dataset):
    """지점 27곳과 '전체'가 모두 점으로 놓인다."""
    figure = ACTIVATION_CHART.build(dataset, _scope(TOTAL_LABEL, "MTS"))
    names = [name for trace in figure.data for name in trace.customdata[:, 0]]
    assert len(names) == BRANCH_COUNT + 1
    assert TOTAL_LABEL in names
    assert set(dataset.branch_names) <= set(names)


def test_activation_marks_the_picked_scope_apart(dataset):
    """고른 대상만 계열을 나눠 다른 색·모양으로 찍는다.

    색만으로 구분하지 않는다 — 범례에 이름이 남고 점 모양도 다르다.
    """
    figure = ACTIVATION_CHART.build(dataset, _scope(FIRST_BRANCH, "MTS"))
    picked = [
        trace for trace in figure.data if trace.name == FIRST_BRANCH
    ]
    assert len(picked) == 1
    assert len(picked[0].x) == 1
    assert picked[0].marker.symbol == "diamond"
    others = [trace for trace in figure.data if trace.name != FIRST_BRANCH]
    assert others and others[0].marker.symbol == "circle"
    assert picked[0].marker.color != others[0].marker.color


def test_activation_uses_the_trade_share_as_the_y_axis(dataset):
    """세로축 값은 월별 프레임의 거래고객비중이다.

    가로축은 채널 축이 있는 프레임에, 세로축은 채널로 나뉘지 않는 월별
    프레임에 있어 기준월·지점으로 맞춘다(→ metrics.activation_scatter).
    """
    scatter = metrics.activation_scatter(dataset, "MTS")
    month = metrics.latest_month(dataset.digital_channel)
    monthly = dataset.monthly
    same = monthly[monthly["base_month"] == month].set_index("branch_name")
    row = scatter[scatter["branch_name"] == FIRST_BRANCH].iloc[0]
    assert float(row["activation"]) == pytest.approx(
        float(same.loc[FIRST_BRANCH, "digital_trade_customer_share"])
    )


def test_activation_follows_the_channel_radio(dataset):
    """채널을 바꾸면 가로축 값이 바뀐다. 세로축은 그대로다."""
    mts = metrics.activation_scatter(dataset, "MTS")
    web = metrics.activation_scatter(dataset, "WEB")
    assert list(mts["user_share"]) != list(web["user_share"])
    assert list(mts["activation"]) == list(web["activation"])


# --- 중단 왼쪽 · 이용고객 프로필 표 -------------------------------------------
def test_profile_table_has_a_column_for_each_channel():
    """열은 항목 하나와 채널 셋이다. 항목 열은 왼쪽에 고정한다."""
    fields = [column.field for column in digital.PROFILE_COLUMNS]
    assert fields == [
        "item",
        *[channel.lower() for channel in DIGITAL_CHANNELS],
    ]
    headers = [column.header for column in digital.PROFILE_COLUMNS]
    assert headers == ["항목", *DIGITAL_CHANNELS]
    assert digital.PROFILE_COLUMNS[0].pinned
    assert digital.PROFILE_COLUMNS[0].flex == 0


def test_profile_table_rows_follow_the_declared_items(dataset):
    """행 차례는 선언한 항목 차례다. 정렬을 끄고 그 차례를 지킨다."""
    _total, rows = PROFILE_TABLE.build(dataset, _scope(TOTAL_LABEL))
    assert list(rows["item"]) == [
        label for _field, label, _to_text in digital.PROFILE_ITEMS
    ]
    assert PROFILE_TABLE.sortable is False
    assert PROFILE_TABLE.auto_height is True


def test_profile_table_writes_each_row_in_its_own_unit(dataset):
    """항목마다 단위가 다르다. 행이 자기 문구를 들고 간다.

    연령은 세, 자산평균은 원, 나머지는 %다. 컬럼 하나의 표기 함수로는
    적을 수 없어 `grid.MONEY_FORMAT`을 쓴다.
    """
    view = callbacks.build_table_view(
        PROFILE_TABLE, dataset, _scope(TOTAL_LABEL)
    )
    by_item = {row["item"]: row for row in view["row_data"]}
    key = f"hts{grid.TEXT_SUFFIX}"
    assert by_item["연령"][key].endswith("세")
    assert by_item["자산평균"][key].endswith("원")
    assert by_item["국내주식비중"][key].endswith("%")
    # 값은 숫자 그대로 담긴다. 글자는 보이는 것만이다.
    assert isinstance(by_item["연령"]["hts"], float)


def test_profile_table_follows_the_scope_dropdown(dataset):
    """지점을 고르면 값이 바뀐다."""
    _total, total_rows = PROFILE_TABLE.build(dataset, _scope(TOTAL_LABEL))
    _t, branch_rows = PROFILE_TABLE.build(dataset, _scope(FIRST_BRANCH))
    assert list(total_rows["hts"]) != list(branch_rows["hts"])


def test_profile_table_uses_only_the_latest_month(dataset):
    """가장 최근 달만 쓴다. 달마다 행이 늘어나지 않는다."""
    _total, rows = PROFILE_TABLE.build(dataset, _scope(TOTAL_LABEL))
    assert len(rows) == len(digital.PROFILE_ITEMS)
    month = metrics.latest_month(dataset.digital_profile)
    frame = dataset.digital_profile_total
    picked = frame[
        (frame["base_month"] == month) & (frame["channel"] == "HTS")
    ].iloc[0]
    assert float(rows.iloc[0]["hts"]) == pytest.approx(
        float(picked["average_age"])
    )


# --- 중단 오른쪽 · 이용일수 ---------------------------------------------------
def test_usage_days_draws_one_line_for_each_channel(dataset):
    """채널마다 선 하나. 색과 점 모양이 모두 다르다."""
    figure = DAYS_CHART.build(dataset, _scope(TOTAL_LABEL))
    assert len(figure.data) == len(DIGITAL_CHANNELS)
    names = [trace.name for trace in figure.data]
    assert set(names) == set(DIGITAL_CHANNELS)
    colors = {trace.line.color for trace in figure.data}
    symbols = {trace.marker.symbol for trace in figure.data}
    assert len(colors) == len(DIGITAL_CHANNELS)
    assert len(symbols) == len(DIGITAL_CHANNELS)
    for trace in figure.data:
        assert trace.mode == "lines+markers"


def test_usage_days_keeps_the_group_order(dataset):
    """가로축은 적게 쓴 쪽부터 많이 쓴 쪽 순이다.

    가나다순으로 다시 세우면 그 뜻이 사라진다.
    """
    figure = DAYS_CHART.build(dataset, _scope(TOTAL_LABEL))
    assert list(figure.layout.xaxis.categoryarray) == list(
        DIGITAL_USAGE_DAY_GROUPS
    )
    assert list(figure.data[0].x) == list(DIGITAL_USAGE_DAY_GROUPS)
    assert figure.layout.yaxis.ticksuffix == "%"


def test_usage_days_follows_the_scope_dropdown(dataset):
    """지점을 고르면 값이 바뀐다."""
    total = DAYS_CHART.build(dataset, _scope(TOTAL_LABEL))
    branch = DAYS_CHART.build(dataset, _scope(FIRST_BRANCH))
    assert list(total.data[0].y) != list(branch.data[0].y)


def test_usage_days_keeps_the_source_share(dataset):
    """비중은 원본 값을 그대로 쓴다."""
    days = metrics.usage_days(dataset, FIRST_BRANCH, DIGITAL_CHANNELS)
    rows = dataset.digital_usage_days
    picked = rows[rows["branch_name"] == FIRST_BRANCH]
    assert len(days) == len(picked)
    assert sorted(days["day_group_share"]) == sorted(
        picked["day_group_share"]
    )


# --- 원본이 없을 때 ----------------------------------------------------------
def test_cards_say_why_they_are_empty_without_the_sources(dataset):
    """원본이 비면 왜 비었는지 그래프 자리에 적는다.

    아무것도 없이 두면 고장인지 데이터가 없는 것인지 구분할 수 없다
    (→ AGENTS.md §11).
    """
    from dataclasses import replace

    import pandas as pd

    empty = replace(
        dataset,
        digital_channel=pd.DataFrame(),
        digital_channel_total=pd.DataFrame(),
        digital_usage_days=pd.DataFrame(),
        digital_usage_days_total=pd.DataFrame(),
        digital_profile=pd.DataFrame(),
        digital_profile_total=pd.DataFrame(),
    )
    notes = {
        TREND_CHART.key: digital.CHANNEL_EMPTY_NOTE,
        ACTIVATION_CHART.key: digital.CHANNEL_EMPTY_NOTE,
        DAYS_CHART.key: digital.DAYS_EMPTY_NOTE,
    }
    for chart in TAB.charts:
        figure = chart.build(empty, TAB.defaults(dataset))
        assert figure.layout.annotations[0].text == notes[chart.key]
    _total, rows = PROFILE_TABLE.build(empty, TAB.defaults(dataset))
    assert rows is None or len(rows) == 0
    assert PROFILE_TABLE.description(empty) == digital.PROFILE_EMPTY_NOTE
