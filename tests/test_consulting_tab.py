"""상담 탭 검증.

원본은 기준월 × 지점 × 상담구분마다 번호 순으로 토픽이 들어 있다. 탭 맨 위의
지점·기준월 선택이 표 셋에 함께 걸리고, 표는 상담구분 값마다 하나씩 생긴다.

분류 이름을 앱 코드에 적지 않는지도 함께 본다. 원본이 분류를 바꿔도 코드를
고칠 일이 없어야 한다(→ AGENTS.md §4).
"""

from __future__ import annotations

import re

import pytest

from dashboard import callbacks, grid
from dashboard.data import TOTAL_LABEL, load_dashboard_data
from dashboard.tabs import consulting
from fixture_data import (
    CONSULTING_MONTHS,
    CONSULTING_TOPIC_COUNT,
    CONSULTING_TYPE_COUNT,
)

TAB = consulting.TAB
TABLE = TAB.tables[0]


@pytest.fixture(scope="module")
def dataset():
    return load_dashboard_data()


# --- 데이터 ------------------------------------------------------------------
def test_source_rows_reach_the_frame(dataset):
    """상담 원본이 표준 프레임으로 들어온다. '전체'는 따로 들고 간다."""
    assert not dataset.consulting.empty
    assert not dataset.consulting_total.empty
    assert TOTAL_LABEL not in set(dataset.consulting["branch_name"])
    assert set(dataset.consulting_total["branch_name"]) == {TOTAL_LABEL}


def test_topic_numbers_keep_their_order(dataset):
    """번호 순서가 흐트러지면 표가 원본과 다른 순위를 보여준다."""
    keys = ["base_month", "branch_id", "consulting_type"]
    for _key, group in dataset.consulting.groupby(keys, observed=True):
        numbers = group["topic_rank"].tolist()
        assert numbers == sorted(numbers)
        assert len(numbers) == CONSULTING_TOPIC_COUNT


def test_share_is_a_percent_number(dataset):
    """비중은 0~100 사이 숫자다. 0~1 비율이면 어댑터가 멈춘다."""
    shares = dataset.consulting["topic_share"]
    assert shares.between(0, 100).all()
    assert shares.max() > 1


# --- 선언 --------------------------------------------------------------------
def test_tab_has_branch_and_month_selects():
    keys = [select.key for select in TAB.selects]
    assert keys == [consulting.SELECT_BRANCH, consulting.SELECT_MONTH]


def test_table_columns_match_the_sketch():
    fields = [column.field for column in consulting.TABLE_COLUMNS]
    assert fields == ["topic_rank", "topic", "topic_summary", "topic_share"]


def test_summary_column_takes_the_leftover_width():
    """문장이 들어가는 칸이 가장 넓어야 읽을 수 있다."""
    flex = grid.table_flex(consulting.TABLE_COLUMNS)
    assert flex["topic_summary"] == max(flex.values())
    # 번호는 나눔에서 빠지고 제 폭을 지킨다.
    assert flex["topic_rank"] == 0


def test_type_names_are_not_written_in_the_code(dataset):
    """상담구분 값은 데이터에서 온다(→ AGENTS.md §4)."""
    import inspect

    source = inspect.getsource(consulting)
    for name in dataset.consulting["consulting_type"].unique():
        assert name not in source


# --- 화면 값 -----------------------------------------------------------------
def test_one_table_per_consulting_type(dataset):
    view = callbacks.build_tab_view(TAB, dataset)
    cards = view["tables"]
    assert len(cards) == CONSULTING_TYPE_COUNT
    titles = [card["title"] for card in cards]
    assert titles == list(
        dict.fromkeys(dataset.consulting["consulting_type"].tolist())
    )
    ids = [card["table_id"] for card in cards]
    assert len(set(ids)) == len(ids)


def test_each_table_shows_one_month_of_one_branch(dataset):
    view = callbacks.build_tab_view(TAB, dataset)
    for card in view["tables"]:
        assert len(card["row_data"]) == CONSULTING_TOPIC_COUNT


def test_default_selection_is_the_total_and_the_reference_month(dataset):
    selection = TAB.defaults(dataset)
    assert selection[consulting.SELECT_BRANCH] == TOTAL_LABEL
    assert selection[consulting.SELECT_MONTH] == dataset.months[-1]
    options = TAB.option_map(dataset)
    assert len(options[consulting.SELECT_MONTH]) == CONSULTING_MONTHS
    # 지점 목록은 '전체'와 지점들이다.
    assert options[consulting.SELECT_BRANCH][0] == TOTAL_LABEL


def test_selecting_a_branch_changes_the_rows(dataset):
    branch = dataset.consulting["branch_name"].iloc[0]
    month = dataset.consulting["base_month"].max()
    picked = callbacks.build_table_views(
        TAB,
        dataset,
        {
            consulting.SELECT_BRANCH: branch,
            consulting.SELECT_MONTH: month,
        },
    )
    total = callbacks.build_table_views(
        TAB,
        dataset,
        {
            consulting.SELECT_BRANCH: TOTAL_LABEL,
            consulting.SELECT_MONTH: month,
        },
    )
    assert picked[0]["row_data"] != total[0]["row_data"]
    assert len(picked[0]["row_data"]) == CONSULTING_TOPIC_COUNT


def test_table_has_no_total_row(dataset):
    """토픽은 더할 수 있는 값이 아니라 합계 행을 두지 않는다."""
    view = callbacks.build_tab_view(TAB, dataset)
    for card in view["tables"]:
        assert card["grid_options"]["pinnedTopRowData"] == []


def test_rows_stay_in_the_source_order(dataset):
    """번호 순 그대로 보여준다. 원본이 매긴 순위가 곧 행 순서다."""
    view = callbacks.build_tab_view(TAB, dataset)
    for card in view["tables"]:
        numbers = [row["topic_rank"] for row in card["row_data"]]
        assert numbers == sorted(numbers)


def test_sorting_is_turned_off(dataset):
    """헤더를 눌러도 다시 세우지 않는다(→ Table.sortable)."""
    view = callbacks.build_tab_view(TAB, dataset)
    for card in view["tables"]:
        assert card["sortable"] is False
        for defined in card["column_defs"]:
            assert defined["sortable"] is False


def test_static_html_headers_are_not_clickable(document):
    """정적 HTML 표도 헤더를 누를 수 있는 것처럼 보이지 않게 한다."""
    body = document[document.find("<body>") :]
    for index in (1, 2, 3):
        found = re.search(
            rf'<table class="export-table" id="consulting-table-{index}"'
            r'[^>]*>(.*?)</table>',
            body,
            re.S,
        )
        assert found, index
        markup = found.group(0)
        assert 'data-sortable="no"' in markup
        head = markup[: markup.find("</thead>")]
        assert 'role="button"' not in head
        assert "export-sort" not in head
        # 너비 조절은 정렬과 무관하므로 그대로 남는다.
        assert "export-resize" in head


def test_missing_source_says_why_the_tab_is_empty(dataset):
    """원본이 없으면 빈 화면이 아니라 이유를 보여준다(→ AGENTS.md §11).

    지점·기준월 목록까지 비어 아무 반응이 없는 화면이 되면, 고장인지
    데이터가 없는 것인지 화면만 봐서는 알 수 없다.
    """
    import dataclasses

    import pandas as pd

    empty = dataclasses.replace(
        dataset,
        consulting=pd.DataFrame(columns=dataset.consulting.columns),
        consulting_total=pd.DataFrame(columns=dataset.consulting.columns),
    )
    view = callbacks.build_tab_view(TAB, empty)
    assert view["selects"]["options"][consulting.SELECT_BRANCH] == []
    cards = view["tables"]
    assert len(cards) == 1
    assert cards[0]["row_data"] == []
    assert cards[0]["description"] == consulting.EMPTY_NOTE
    # 데이터가 있으면 그 문구를 띄우지 않는다.
    normal = callbacks.build_tab_view(TAB, dataset)
    assert normal["tables"][0]["description"] != consulting.EMPTY_NOTE

    # 화면도 정적 HTML도 그 문구를 그대로 그린다.
    from dashboard import layout

    card = layout._table_card(cards[0])
    header_right = card.children[0].children[1]
    assert header_right.children[0].children == consulting.EMPTY_NOTE


def test_table_height_follows_the_row_count(dataset):
    """행이 열 개뿐인 표에 고정 높이를 주면 아래가 빈 채로 남는다."""
    from dashboard import layout

    view = callbacks.build_tab_view(TAB, dataset)
    card = view["tables"][0]
    assert card["grid_options"]["domLayout"] == "autoHeight"
    assert "height" not in layout.table_style(card["auto_height"])


# --- 정적 HTML ---------------------------------------------------------------
@pytest.fixture(scope="module")
def document(dataset) -> str:
    import export_html

    return export_html.build_html(dataset)


def test_static_html_carries_every_selection(document, dataset):
    """서버가 없으므로 고를 수 있는 조합의 행을 모두 담아 둔다."""
    scopes = set(re.findall(r'data-scope="([^"]+)"', document))
    expected = {
        f"{branch}|{month}"
        for branch in TAB.option_map(dataset)[consulting.SELECT_BRANCH]
        for month in TAB.option_map(dataset)[consulting.SELECT_MONTH]
    }
    assert expected <= scopes


def test_static_html_shows_only_the_chosen_selection(document, dataset):
    """지금 고른 조합만 보이고 나머지는 숨어 있다."""
    # 다른 탭에도 선택을 따르는 표가 있으므로 이 탭의 칸만 본다.
    rest = document[document.find('data-panel="consulting"') :]
    end = rest.find('data-panel="', 1)
    body = rest if end == -1 else rest[:end]
    rows = re.findall(r"<tr [^>]*data-scope=\"([^\"]+)\"([^>]*)>", body)
    assert rows
    current = "|".join(TAB.defaults(dataset).values())
    shown = [scope for scope, rest in rows if "hidden" not in rest]
    assert set(shown) == {current}
    # 표 셋 × 토픽 수만큼 보인다.
    assert len(shown) == CONSULTING_TYPE_COUNT * CONSULTING_TOPIC_COUNT


def test_static_html_switches_rows_without_a_server(document):
    """선택이 바뀌면 문서 안의 코드가 보이는 행만 바꾼다."""
    assert "TAB_TABLES" in document
    assert "function showScope" in document
    assert "fetch(" not in document.split("<body>")[1]
