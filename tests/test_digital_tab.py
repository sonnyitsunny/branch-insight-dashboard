"""디지털 채널 탭 검증.

맨 위 드롭다운 하나가 이 탭의 카드 전체를 움직인다. '전체'와 지점 27곳
중 하나를 고르면 표와 그림이 함께 그 대상을 가리킨다.

카드 여섯의 자리는 선언이 적어 둔 `order`가 정한다(→ registry.grid_order).

1. 상단 왼쪽 — 채널이용 고객 추이. 막대가 이용 고객 수, 선이 이용 비중이며
   라디오로 채널을 고른다.
2. 상단 오른쪽 — 채널이용과 거래활성화의 지점 산점도. 고른 대상만
   달리 찍는다.
3. 중단 왼쪽 — 이용고객 프로필 표. 행이 항목, 열이 채널이다.
4. 중단 오른쪽 — 이용일수 구간별 거래활성화. 채널마다 선 하나다.
5. 하단 왼쪽 — 앱 메뉴 이용 순위 표. 행이 순위, 열이 고객 세그먼트다.
6. 하단 오른쪽 — 앱 메뉴별 거래활성화 분석. 한 점이 메뉴 하나이고
   드롭다운으로 세그먼트를 고른다.

'공통고객' 분류는 화면에 '공통고객 전체'로 적는다. 표 컬럼 이름과 드롭다운
값이 모두 그렇다(→ digital.MENU_LABELS). 표 컬럼에는 나머지 다섯에도
'선호형'이 붙는다(→ digital.menu_column_header).
"""

from __future__ import annotations

import math

import plotly.graph_objects as go
import pytest

from dashboard import callbacks, grid, layout
from dashboard import format as fmt
from dashboard.data import (
    DIGITAL_CHANNELS,
    DIGITAL_MENU_CATEGORIES,
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
from fixture_data import (
    BRANCH_COUNT,
    DIGITAL_MENU_RANK_COUNT,
    MONTH_COUNT,
)

TAB = digital.TAB
TREND_CHART = TAB.charts[0]
ACTIVATION_CHART = TAB.charts[1]
DAYS_CHART = TAB.charts[2]
MENU_CHART = TAB.charts[3]
PROFILE_TABLE = TAB.tables[0]
MENU_TABLE = TAB.tables[1]

FIRST_BRANCH = "지점 01"


@pytest.fixture(scope="module")
def dataset():
    return load_dashboard_data()


def _scope(scope: str, channel: str = "") -> dict:
    """선택값 묶음. 채널을 비우면 첫 채널을 고른 것으로 본다.

    카드마다 구분 칸이 따로라 키가 여럿이다. 어느 카드에 넘겨도 되도록
    모두 같은 값으로 채운다(→ digital.SELECT_PROFILE_SCOPE).
    """
    chosen = {
        digital.SELECT_SCOPE: scope,
        digital.SELECT_PROFILE_SCOPE: scope,
        digital.SELECT_MENU_SCOPE: scope,
    }
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


def _scope_selects() -> list:
    """여섯 카드의 구분 선택. 차트는 자기 선언에서, 표는 그 줄에서 온다."""
    picked = [chart.selects[0] for chart in TAB.charts]
    picked += [group.selects[0] for group in _table_groups()]
    return picked


def _table_groups() -> list:
    """표 카드마다 하나씩 있는 선택 줄."""
    return [group for group in TAB.select_groups if group.tables]


def test_every_card_has_its_own_scope_dropdown(dataset):
    """카드마다 구분 드롭다운이 하나씩이다. 맨 위 줄은 없다.

    카드끼리 서로 다른 지점을 놓고 견줄 수 있다. 다른 탭도 이렇게 카드
    안에서 고른다(→ registry.Chart.selects, registry.PLACE_TABLE).
    """
    assert len(_scope_selects()) == len(TAB.charts) + len(TAB.tables)
    for select in _scope_selects():
        assert select.kind == KIND_DROPDOWN
        assert select.label == digital.SCOPE_LABEL
    # 표는 자기 줄에 속하고, 그 줄의 컨트롤은 카드 안에 들어간다.
    assert PROFILE_TABLE.group == digital.PROFILE_GROUP
    assert MENU_TABLE.group == digital.MENU_GROUP
    for group in _table_groups():
        assert group.row_selects == ()
        assert len(group.table_selects) == 1
    # 탭 전체를 움직이는 컨트롤은 남기지 않는다.
    assert TAB.followers == ()


def test_every_scope_dropdown_offers_total_and_every_branch(dataset):
    """구분 드롭다운은 '전체'와 지점 27곳을 고른다. '전체'가 맨 앞이다.

    지점 이름은 데이터에서 읽는다. 지점이 늘어도 선언을 고치지 않는다.
    """
    for select in _scope_selects():
        options = select.options(dataset)
        assert options[0] == TOTAL_LABEL
        assert len(options) == BRANCH_COUNT + 1
        assert set(options[1:]) == set(dataset.branch_names)
        assert select.default(dataset) == TOTAL_LABEL


def test_each_scope_dropdown_has_its_own_id(dataset):
    """여섯 칸의 컴포넌트 ID가 겹치지 않는다.

    겹치면 Dash가 같은 ID에 Output을 둘 걸어 멈춘다(→ AGENTS.md §16).
    """
    ids = [
        chart.select_id(TAB.value, digital.SELECT_SCOPE)
        for chart in TAB.charts
    ]
    ids += [
        group.select_id(group.selects[0].key)
        for group in _table_groups()
    ]
    assert len(set(ids)) == len(ids)
    # 표 줄의 키도 서로 달라야 목록과 기본값이 한 칸으로 겹치지 않는다
    # (→ registry.Tab.option_map).
    keys = [select.key for select in TAB.selects]
    assert len(set(keys)) == len(keys)
    assert set(TAB.option_map(dataset)) == set(keys)


def test_channel_radio_is_on_the_two_top_cards():
    """윗줄 두 카드만 채널을 고른다. 아래 둘은 세 채널을 함께 보여준다."""
    for chart in (TREND_CHART, ACTIVATION_CHART):
        _scope, select = chart.selects
        assert select.key == digital.SELECT_CHANNEL
        assert select.kind == KIND_RADIO
        assert select.options(None) == list(DIGITAL_CHANNELS)
    assert len(DAYS_CHART.selects) == 1


def test_menu_chart_uses_a_dropdown_not_a_radio(dataset):
    """분류가 여섯이라 펼쳐 고른다.

    라디오로 늘어놓으면 카드 헤더를 넘어간다. 채널은 셋뿐이라 라디오다
    (→ digital.MENU_SELECT).
    """
    _scope, select = MENU_CHART.selects
    assert select.key == digital.SELECT_MENU
    assert select.kind == KIND_DROPDOWN
    assert len(select.options(dataset)) == len(DIGITAL_MENU_CATEGORIES)


def test_cards_stand_in_the_declared_order(dataset):
    """카드 자리는 선언이 적어 둔 번호대로다.

    번갈아 놓는 기본 규칙으로는 표가 맨 앞으로 가서 스케치와 달라진다
    (→ registry.grid_order).
    """
    view = callbacks.build_tab_view(TAB, dataset)
    cards = view["tables"]
    order = grid_order(cards, TAB.charts)
    kinds = [kind for kind, _item in order]
    assert kinds == [
        GRID_CHART,
        GRID_CHART,
        GRID_TABLE,
        GRID_CHART,
        GRID_TABLE,
        GRID_CHART,
    ]
    keys = [
        item["title"] if kind == GRID_TABLE else item.key
        for kind, item in order
    ]
    assert keys == [
        "trend",
        "activation",
        "이용고객 프로필",
        "usage-days",
        "앱 메뉴 이용 순위: 고객 세그먼트별",
        "menu-scatter",
    ]


def test_the_drawn_grid_keeps_the_declared_order(dataset):
    """그려 놓은 카드도 선언한 자리에 선다. 한 그리드에 여섯 장이다.

    선택 줄이 여섯이라 `grid_order`가 줄마다 따로 돌아 줄 단위로 카드가
    뭉친다. 자리 번호로 그리드 전체를 다시 세운다(→ registry.row_order).
    """
    view = callbacks.build_initial_view(dataset)
    panel = layout._tab_panel(TAB, view["tabs"][TAB.value])
    grids = [
        node
        for node in panel.children
        if getattr(node, "className", "") == "chart-grid"
    ]
    (drawn,) = grids
    assert _card_titles(drawn) == [
        "채널이용 고객 추이",
        "지점별 채널이용X거래활성화 분석",
        "이용고객 프로필",
        "이용일수 구간별 거래활성화",
        "앱 메뉴 이용 순위: 고객 세그먼트별",
        digital.MENU_SCATTER_TITLE,
    ]
    # 카드 위에 놓이는 컨트롤 줄이 없다. 컨트롤이 모두 카드 안에 있다.
    assert not [
        node
        for node in panel.children
        if getattr(node, "className", "") == "tab-controls"
    ]


def _card_titles(section) -> list[str]:
    """그리드에 놓인 카드의 제목을 자리 순서대로.

    제목 아래 줄이 있는 카드는 제목이 상자 한 겹 안에 들어간다
    (→ layout.card_heading).
    """
    titles = []
    for card in section.children:
        heading = card.children[0].children[0]
        if getattr(heading, "className", "") == "card-heading":
            heading = heading.children[0]
        titles.append(heading.children)
    return titles


def test_bottom_cards_share_one_height(dataset):
    """나란히 서는 표와 산점도의 아랫선이 맞는다.

    한쪽만 높이면 그 줄만 어긋난다(→ digital.MENU_CARD_HEIGHT).
    """
    assert MENU_TABLE.height == digital.MENU_CARD_HEIGHT
    assert MENU_CHART.height == digital.MENU_CARD_HEIGHT
    assert not MENU_TABLE.auto_height
    assert layout.table_style(False, True, MENU_TABLE.height)["height"] == (
        digital.MENU_CARD_HEIGHT
    )
    assert layout.chart_style(MENU_CHART)["height"] == (
        digital.MENU_CARD_HEIGHT
    )


def test_every_card_builds_something(dataset):
    """빈 화면이 나오지 않는다. 그림은 Figure, 표는 행을 돌려준다."""
    for chart in TAB.charts:
        figure = chart.build(dataset, chart.defaults(dataset))
        assert isinstance(figure, go.Figure), chart.key
        assert figure.data, chart.key
    _total, rows = PROFILE_TABLE.build(dataset, TAB.defaults(dataset))
    assert len(rows) == len(digital.PROFILE_ITEMS)
    _total, rows = MENU_TABLE.build(dataset, TAB.defaults(dataset))
    assert len(rows) == DIGITAL_MENU_RANK_COUNT


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

    연령은 세, 자산평균은 단위 없는 억원 숫자, 나머지는 %다. 컬럼 하나의
    표기 함수로는 적을 수 없어 `grid.MONEY_FORMAT`을 쓴다.
    """
    view = callbacks.build_table_view(
        PROFILE_TABLE, dataset, _scope(TOTAL_LABEL)
    )
    by_item = {row["item"]: row for row in view["row_data"]}
    key = f"hts{grid.TEXT_SUFFIX}"
    assert by_item["연령"][key].endswith("세")
    # 단위는 행 이름이 말하므로 값에는 붙이지 않는다.
    assets = by_item["자산평균(억원)"]
    assert assets[key] == f"{assets['hts'] / fmt.WON_PER_100M:.1f}"
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


# --- 분류 이름 --------------------------------------------------------------
def test_common_category_is_shown_as_common_total():
    """'공통고객' 분류는 화면에 '공통고객 전체'로 적는다.

    나머지 다섯과 나란한 하나의 분류이지 합계가 아니라, 그냥 '전체'로
    적으면 다섯을 더한 값으로 읽힌다. 값은 바꾸지 않는다 — 데이터를 고를
    때는 원본 이름을 그대로 쓴다(→ digital.MENU_LABELS).
    """
    common = digital.MENU_TOTAL_CATEGORY
    shown = f"{common} {TOTAL_LABEL}"
    assert digital.menu_label(common) == shown
    assert digital.menu_category(shown) == common
    # 나머지 분류는 드롭다운에 원본 이름 그대로 나온다.
    for category in DIGITAL_MENU_CATEGORIES:
        if category == common:
            continue
        assert digital.menu_label(category) == category
        assert digital.menu_category(category) == category


def test_table_headers_add_the_segment_suffix():
    """순위표 컬럼에만 '선호형'을 붙인다.

    열 여섯이 나란히 서므로 머리글만으로 무엇을 가른 열인지 읽혀야 한다.
    드롭다운은 카드 제목이 세그먼트라고 말하므로 붙이지 않는다.
    """
    common = digital.MENU_TOTAL_CATEGORY
    assert digital.menu_column_header(common) == f"{common} {TOTAL_LABEL}"
    for category in DIGITAL_MENU_CATEGORIES:
        if category == common:
            continue
        assert digital.menu_column_header(category) == (
            f"{category} {digital.MENU_SEGMENT_SUFFIX}"
        )


def test_menu_names_keep_the_declared_order(dataset):
    """드롭다운 차례는 데이터 계층이 정한 분류 차례다."""
    _scope, select = MENU_CHART.selects
    assert select.options(dataset) == [
        digital.menu_label(name) for name in DIGITAL_MENU_CATEGORIES
    ]
    assert select.default(dataset) == digital.menu_label(
        digital.MENU_TOTAL_CATEGORY
    )


# --- 하단 왼쪽 · 메뉴 이용순위 표 ---------------------------------------------
def test_menu_table_has_a_column_for_each_category():
    """열은 순위 하나와 메뉴 분류 여섯이다. 첫 분류는 '공통고객 전체'다."""
    headers = [column.header for column in digital.MENU_COLUMNS]
    assert headers == [
        "순위",
        *[
            digital.menu_column_header(name)
            for name in DIGITAL_MENU_CATEGORIES
        ],
    ]
    assert headers[1] == f"{digital.MENU_TOTAL_CATEGORY} {TOTAL_LABEL}"
    # 분류 이름이 한글이라 컬럼 이름은 자리 번호로 만든다.
    fields = [column.field for column in digital.MENU_COLUMNS]
    assert fields[0] == "menu_rank"
    assert fields[1:] == [field for _category, field in digital.MENU_FIELDS]
    assert digital.MENU_COLUMNS[0].flex == 0


def test_menu_table_rows_stand_in_rank_order(dataset):
    """행 차례가 순위 차례다. 정렬을 끄고 그 차례를 지킨다."""
    _total, rows = MENU_TABLE.build(dataset, _scope(TOTAL_LABEL))
    assert list(rows["menu_rank"]) == list(
        range(1, DIGITAL_MENU_RANK_COUNT + 1)
    )
    assert MENU_TABLE.sortable is False


def test_menu_table_cells_hold_the_menu_name(dataset):
    """셀에는 그 분류·그 순위의 메뉴 이름이 들어간다."""
    _total, rows = MENU_TABLE.build(dataset, _scope(FIRST_BRANCH))
    frame = dataset.digital_menu_rank
    month = metrics.latest_month(frame)
    for category, field in digital.MENU_FIELDS:
        picked = frame[
            (frame["branch_name"] == FIRST_BRANCH)
            & (frame["base_month"] == month)
            & (frame["menu_category"] == category)
        ].sort_values("menu_rank")
        assert list(rows[field]) == list(picked["menu_name"])


def test_menu_table_follows_the_scope_dropdown(dataset):
    """지점을 고르면 메뉴가 바뀐다."""
    _total, total_rows = MENU_TABLE.build(dataset, _scope(TOTAL_LABEL))
    _t, branch_rows = MENU_TABLE.build(dataset, _scope(FIRST_BRANCH))
    field = digital.MENU_FIELDS[0][1]
    assert list(total_rows[field]) != list(branch_rows[field])


def test_menu_table_uses_only_the_latest_month(dataset):
    """가장 최근 달만 쓴다. 달마다 행이 늘어나지 않는다."""
    _total, rows = MENU_TABLE.build(dataset, _scope(TOTAL_LABEL))
    assert len(rows) == DIGITAL_MENU_RANK_COUNT


# --- 하단 오른쪽 · 메뉴 몰입도 분석 -------------------------------------------
def test_menu_scatter_puts_views_across_and_conversion_up(dataset):
    """가로가 조회수, 세로가 거래비중이다. 한 점이 메뉴 하나다."""
    figure = MENU_CHART.build(dataset, _scope(TOTAL_LABEL))
    (trace,) = figure.data
    assert isinstance(trace, go.Scatter)
    assert trace.mode.startswith("markers")
    assert len(trace.x) == DIGITAL_MENU_RANK_COUNT
    assert figure.layout.yaxis.ticksuffix == "%"
    assert figure.layout.xaxis.ticksuffix != "%"


def test_menu_scatter_spreads_the_views_on_a_log_axis(dataset):
    """가로축이 로그 눈금이다. 아래 순위 메뉴가 한자리에 뭉치지 않는다.

    Plotly의 로그 축은 범위를 값이 아니라 자릿수(log10)로 읽는다. 조회
    건수를 그대로 넣으면 축이 엉뚱하게 벌어진다(→ figures._log_padded).
    """
    figure = MENU_CHART.build(dataset, _scope(TOTAL_LABEL))
    axis = figure.layout.xaxis
    assert axis.type == "log"
    views = [float(value) for value in figure.data[0].x]
    low, high = axis.range
    assert low < math.log10(min(views))
    assert high > math.log10(max(views))
    # 축 이름에 로그 눈금이라고 적는다. 적지 않으면 같은 거리를 같은
    # 차이로 읽는다.
    assert "로그" in axis.title.text


def test_menu_scatter_sets_the_log_ticks_itself(dataset):
    """세로선 자리를 직접 적는다. 한 자릿수에 1·2·5배 자리만 선다.

    맡겨 두면 Plotly가 한 자릿수 안을 1·2·3…9로 잘게 나눠 세로선이
    빽빽해지고 축 아래 숫자가 서로 붙는다(→ figures.MENU_LOG_STEPS).
    """
    axis = MENU_CHART.build(dataset, _scope(TOTAL_LABEL)).layout.xaxis
    assert axis.tickmode == "array"
    assert axis.minor.showgrid is False
    ticks = list(axis.tickvals)
    # 눈금은 자릿수가 아니라 조회 건수 그대로다. 축 범위와 단위가 다르다
    # (→ figures._log_ticks).
    low, high = axis.range
    assert all(low <= math.log10(tick) <= high for tick in ticks)
    # 선이 너무 성기지도 빽빽하지도 않다.
    assert 4 <= len(ticks) <= 10
    first = [
        tick / 10 ** math.floor(math.log10(tick)) for tick in ticks
    ]
    assert set(round(value) for value in first) <= set(
        digital.figures.MENU_LOG_STEPS
    )


def test_menu_scatter_keeps_a_linear_axis_when_views_reach_zero(dataset):
    """조회수가 0인 메뉴가 섞이면 선형 눈금으로 되돌린다.

    로그 축은 0을 그리지 못해 그 점을 아무 말 없이 뺀다. 점 하나가
    사라진 그림이 뭉친 그림보다 위험하다(→ figures._view_axis).
    """
    scatter = metrics.menu_scatter(
        dataset, TOTAL_LABEL, DIGITAL_MENU_CATEGORIES[0]
    ).copy()
    scatter.loc[scatter.index[-1], "view_count"] = 0
    figure = digital.figures.create_menu_scatter_figure(
        scatter, TOTAL_LABEL, TOTAL_LABEL
    )
    assert figure.layout.xaxis.type != "log"
    assert len(figure.data[0].x) == len(scatter)


def test_menu_scatter_labels_points_with_the_menu_name(dataset):
    """점 위에 메뉴 이름을 적는다.

    순위 숫자만 적으면 어느 메뉴인지 알려고 매번 hover해야 한다.
    """
    figure = MENU_CHART.build(dataset, _scope(TOTAL_LABEL))
    (trace,) = figure.data
    names = _menu_names(dataset, TOTAL_LABEL, DIGITAL_MENU_CATEGORIES[0])
    assert list(trace.text) == names
    # 순위와 값은 hover로 함께 읽는다.
    assert [row[0] for row in trace.customdata] == names
    assert [row[1] for row in trace.customdata] == [
        str(rank) for rank in range(1, DIGITAL_MENU_RANK_COUNT + 1)
    ]


def test_menu_scatter_alternates_the_label_side(dataset):
    """이름을 위아래로 번갈아 적어 겹치는 자리를 줄인다.

    메뉴 이름은 점보다 넓어 이웃한 점끼리 글자가 겹친다
    (→ figures._label_positions).
    """
    figure = MENU_CHART.build(dataset, _scope(TOTAL_LABEL))
    (trace,) = figure.data
    positions = list(trace.textposition)
    assert len(positions) == DIGITAL_MENU_RANK_COUNT
    assert positions[0] == "top center"
    assert positions[1] == "bottom center"
    assert set(positions) == {"top center", "bottom center"}


def _menu_names(dataset, scope: str, category: str) -> list[str]:
    """그 대상·분류의 메뉴 이름을 순위 차례로."""
    scatter = metrics.menu_scatter(dataset, scope, category)
    return list(scatter["menu_name"])


def test_menu_scatter_follows_the_category_dropdown(dataset):
    """분류를 고르면 그 분류의 메뉴만 그린다."""
    chosen = {
        digital.SELECT_SCOPE: TOTAL_LABEL,
        digital.SELECT_MENU: DIGITAL_MENU_CATEGORIES[1],
    }
    stock = MENU_CHART.build(dataset, chosen)
    common = MENU_CHART.build(dataset, _scope(TOTAL_LABEL))
    assert [row[0] for row in stock.data[0].customdata] != [
        row[0] for row in common.data[0].customdata
    ]


def test_menu_scatter_reads_total_as_the_common_category(dataset):
    """드롭다운의 '공통고객 전체'는 원본의 '공통고객' 분류를 가리킨다.

    보이는 이름만 바꿨을 뿐 고르는 데이터는 원본 이름 그대로다
    (→ digital.menu_category).
    """
    common = digital.MENU_TOTAL_CATEGORY
    figure = MENU_CHART.build(
        dataset,
        {
            digital.SELECT_SCOPE: TOTAL_LABEL,
            digital.SELECT_MENU: digital.menu_label(common),
        },
    )
    names = [row[0] for row in figure.data[0].customdata]
    assert names == _menu_names(dataset, TOTAL_LABEL, common)


def test_menu_scatter_follows_the_scope_dropdown(dataset):
    """지점을 고르면 값이 바뀐다."""
    total = MENU_CHART.build(dataset, _scope(TOTAL_LABEL))
    branch = MENU_CHART.build(dataset, _scope(FIRST_BRANCH))
    assert list(total.data[0].x) != list(branch.data[0].x)


def test_menu_scatter_keeps_the_source_values(dataset):
    """조회수와 거래비중은 원본 값을 그대로 쓴다."""
    scatter = metrics.menu_scatter(
        dataset, FIRST_BRANCH, DIGITAL_MENU_CATEGORIES[0]
    )
    frame = dataset.digital_menu_rank
    month = metrics.latest_month(frame)
    picked = frame[
        (frame["branch_name"] == FIRST_BRANCH)
        & (frame["base_month"] == month)
        & (frame["menu_category"] == DIGITAL_MENU_CATEGORIES[0])
    ].sort_values("menu_rank")
    assert list(scatter["view_count"]) == list(picked["view_count"])
    assert list(scatter["trade_conversion_share"]) == list(
        picked["trade_conversion_share"]
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
        digital_menu_rank=pd.DataFrame(),
        digital_menu_rank_total=pd.DataFrame(),
    )
    notes = {
        TREND_CHART.key: digital.CHANNEL_EMPTY_NOTE,
        ACTIVATION_CHART.key: digital.CHANNEL_EMPTY_NOTE,
        DAYS_CHART.key: digital.DAYS_EMPTY_NOTE,
        MENU_CHART.key: digital.MENU_EMPTY_NOTE,
    }
    for chart in TAB.charts:
        figure = chart.build(empty, TAB.defaults(dataset))
        assert figure.layout.annotations[0].text == notes[chart.key]
    for table, note in (
        (PROFILE_TABLE, digital.PROFILE_EMPTY_NOTE),
        (MENU_TABLE, digital.MENU_EMPTY_NOTE),
    ):
        _total, rows = table.build(empty, TAB.defaults(dataset))
        assert rows is None or len(rows) == 0
        assert table.description(empty) == note
