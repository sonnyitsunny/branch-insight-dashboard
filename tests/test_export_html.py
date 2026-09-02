"""정적 HTML 내보내기 검증.

인터넷 없이 열려야 하므로 외부 참조가 없는지 확인하고, 표 값이 Dash 화면과
같은 함수에서 나오는지 확인한다(→ AGENTS.md §14, §16).
"""

from __future__ import annotations

import base64
import json
import re
import sys

import pytest

import export_html
from dashboard import grid, layout
from dashboard import tabs as tab_registry
from dashboard.tabs import customer
from fixture_data import BRANCH_COUNT

TAB = customer.TAB
COLUMNS = customer.TABLE_COLUMNS
TABLE_ID = TAB.tables[0].table_id(TAB.value)
# 표가 둘 이상이므로 표마다 자기 컬럼 선언으로 확인한다. 한 표의 컬럼
# 순서를 다른 표에 대면 엉뚱한 칸을 보게 된다.
# 표를 나누는 선언은 데이터를 봐야 몇 개인지 알 수 있으므로 여기서 세지
# 않는다(→ test_consulting_tab.py).
# 컬럼 이름이 선택에 따라 바뀌는 표가 있다. 첫 화면에 그려지는 목록으로
# 본다(→ registry.Table.columns_of).
TABLES = [
    (table.table_id(tab.value), table.columns_of())
    for tab in tab_registry.TABS
    for table in tab.tables
    if not table.group_field
]


def table_markup(body: str, table_id: str) -> str:
    """표 하나의 마크업만 잘라낸다."""
    found = re.search(
        rf'<table class="export-table" id="{table_id}"[^>]*>(.*?)</table>',
        body,
        re.S,
    )
    assert found, f"{table_id} 표가 없다"
    return found.group(1)
CHARTS = [
    (tab, chart)
    for tab in tab_registry.TABS
    for chart in tab.charts
]


@pytest.fixture(scope="module")
def document() -> str:
    return export_html.build_html()


@pytest.fixture(scope="module")
def body(document: str) -> str:
    return document[document.find("<body>") :]


def test_document_is_a_complete_page(document: str):
    assert document.startswith("<!doctype html>")
    assert document.rstrip().endswith("</html>")
    assert '<html lang="ko">' in document
    assert '<meta charset="utf-8">' in document


def test_no_external_resources(document: str):
    """CDN·외부 URL을 참조하지 않는다. 인터넷 없이 열려야 한다."""
    assert not re.search(r"<script[^>]*\ssrc\s*=", document)
    # 이미지와 아이콘은 문서 안에 심은 것만 허용한다. 파일이나 URL을
    # 가리키면 인터넷 없이 열었을 때 깨진다.
    for tag in re.findall(r"<img[^>]*>", document):
        assert re.search(r'src="data:image/', tag), tag
    for tag in re.findall(r"<link[^>]*>", document):
        assert re.search(r'href="data:', tag), tag
    assert "<iframe" not in document
    assert "@import" not in document
    assert not re.search(r"url\(\s*['\"]?https?:", document)
    assert "fonts.googleapis" not in document


def test_plotly_js_is_embedded_once(document: str):
    """Plotly.js는 한 번만 들어간다. 차트마다 넣으면 파일이 네 배가 된다."""
    # 스크립트는 둘이다 — plotly.js 하나, 동작을 담은 코드 하나.
    assert document.count("<script>") == 2
    assert document.count("Plotly.newPlot") >= len(CHARTS)
    assert len(document) > 1_000_000  # plotly.js가 실제로 들어 있다


def test_css_is_inlined_from_the_project_file(document: str):
    assert "<style>" in document
    # assets/style.css의 토큰이 그대로 들어와 있다.
    assert "--color-primary" in document
    assert ".export-table" in document


def test_accent_term_is_marked_like_the_screen(body: str):
    """'공통고객'을 화면과 같은 클래스로 감싼다(→ layout.accent_split).

    색은 내보내기 쪽에 적지 않는다. 함께 심는 style.css의
    `.term-accent`가 정하므로 화면 색을 고치면 이쪽도 따라온다.
    """
    span = (
        f'<span class="{layout.ACCENT_CLASS}">'
        f"{layout.ACCENT_TERM}</span>"
    )
    title = re.search(r'<h1 class="page-title">(.*?)</h1>', body)
    assert title is not None and span in title.group(1)
    labels = sum(
        layout.ACCENT_TERM in card.label for card in layout.KPI_CARDS
    )
    # 큰 제목 하나와 그 낱말이 든 카드 라벨들.
    assert body.count(span) >= labels + 1


def test_logo_is_embedded_in_the_document(body: str):
    """로고는 화면과 같은 파일을 base64로 심는다.

    `assets/`를 가리키면 HTML만 다른 곳으로 옮겼을 때 깨진다.
    """
    assets = export_html.PROJECT_DIR / "assets"
    raw = (assets / layout.LOGO_FILE).read_bytes()
    encoded = base64.b64encode(raw).decode("ascii")
    assert f'src="data:image/png;base64,{encoded}"' in body
    assert 'class="page-logo"' in body
    assert f'alt="{layout.LOGO_ALT}"' in body


def test_favicon_is_embedded_in_the_document(document: str):
    """탭 아이콘은 화면과 같은 파일을 문서 안에 심는다.

    Dash는 assets/favicon.ico를 이름으로 찾는다. 정적 HTML은 그 파일을
    가리킬 수 없으므로 같은 내용을 넣어 두 산출물의 아이콘을 맞춘다.
    """
    assets = export_html.PROJECT_DIR / "assets"
    raw = (assets / layout.FAVICON_FILE).read_bytes()
    encoded = base64.b64encode(raw).decode("ascii")
    assert f'href="data:image/x-icon;base64,{encoded}"' in document
    assert '<link rel="icon"' in document


def test_every_chart_is_rendered(body: str):
    """선언한 차트가 하나도 빠지지 않고 그려진다."""
    drawn = re.findall(r'class="[^"]*plotly-graph-div', body)
    assert len(drawn) == len(CHARTS)
    for tab, chart in CHARTS:
        assert chart.title in body
        assert f'id="{chart.chart_id(tab.value)}"' in body


def test_tab_bar_matches_the_screen(body: str):
    """화면과 같은 탭을 같은 순서로 보여준다.

    구현한 탭만 누를 수 있고 나머지는 이름만 나온다. 목록은 화면과 같은
    등록표에서 온다.
    """
    bar = re.search(r"<nav class=\"tab-bar[^>]*>(.*?)</nav>", body, re.S)
    assert bar
    labels = re.findall(r"<(?:span|button)[^>]*>([^<]+)<", bar.group(1))
    assert labels == [label for _value, label in tab_registry.TAB_ORDER]

    built = len(tab_registry.TABS)
    disabled = len(tab_registry.TAB_ORDER) - built
    # 탭 줄 안에서만 센다. 문서 뒤쪽 코드에도 같은 이름이 나온다.
    assert bar.group(1).count("export-tab--selected") == 1
    assert bar.group(1).count("export-tab--disabled") == disabled
    assert bar.group(1).count('data-tab="') == built


def test_branch_select_has_a_figure_for_every_option(document: str):
    """고를 수 있는 값마다 Figure가 문서에 담겨 있어야 갈아 끼울 수 있다.

    하나라도 빠지면 그 지점을 골랐을 때 화면이 그대로 멈춘다.
    """
    raw = re.search(
        r"var CHART_VARIANTS = (\{.*?\});\nvar CHART_SLOTS", document, re.S
    )
    assert raw, "미리 만든 Figure 묶음이 없다"
    variants = json.loads(raw.group(1).replace("\\u003c", "<"))

    body = document[document.find("<body>") :]
    selects = re.findall(
        r'<div class="card-control export-dropdown" data-chart="([^"]+)"'
        r' data-select="[^"]*">(.*?)</div>',
        body,
        re.S,
    )
    slots_raw = re.search(
        r"var CHART_SLOTS = (\{.*?\});\nvar CHART_ORDER", document, re.S
    )
    assert slots_raw, "자리마다 갈아 끼울 값 묶음이 없다"
    slots = json.loads(slots_raw.group(1).replace("\\u003c", "<"))

    tables_raw = re.search(
        r"var TAB_TABLES = (\{.*?\});\nvar AI_SUMMARIES", document, re.S
    )
    assert tables_raw, "탭 선택이 다시 그릴 표 묶음이 없다"
    tab_tables = json.loads(tables_raw.group(1))
    summaries = _summaries(document)

    assert selects, "지점 선택 상자가 없다"
    for chart_id, inner in selects:
        options = re.findall(r'data-value="([^"]*)"', inner)
        assert options
        if chart_id in summaries:
            # AI 요약은 차트가 아니라 글을 갈아 끼운다. 고를 수 있는
            # 영업점마다 글이 담겨 있어야 한다(→ 아래 요약 검증).
            for option in options:
                assert option in summaries[chart_id]["lines"], (
                    chart_id,
                    option,
                )
            continue
        if chart_id in tab_tables:
            # 탭 전체 선택은 차트가 아니라 표를 다시 그린다. Figure를 담지
            # 않고 조합마다 표의 행을 담는다(→ test_consulting_tab.py).
            continue
        if chart_id in slots:
            # 조합이 폭발하는 차트는 Figure 대신 숫자를 담는다. 고를 수
            # 있는 값마다 그 숫자가 있어야 갈아 끼울 수 있다.
            columns = slots[chart_id]["values"]
            for option in options:
                assert any(
                    option in by_value for by_value in columns.values()
                ), (chart_id, option)
            continue
        # 조합 키는 컨트롤 값을 '|'로 이은 것이다. 고를 수 있는 값은
        # 어느 조합에든 한 번은 나와야 한다.
        reachable = {
            part for key in variants[chart_id] for part in key.split("|")
        }
        for option in options:
            assert option in reachable, (chart_id, option)
        figure = next(iter(variants[chart_id].values()))
        assert "data" in figure and "layout" in figure


def _summaries(document: str) -> dict:
    """문서에 담아 둔 AI 요약 글 묶음."""
    raw = re.search(
        r"var AI_SUMMARIES = (\{.*?\});\nvar COLUMN_LAYOUT", document, re.S
    )
    assert raw, "AI 요약 글 묶음이 없다"
    return json.loads(raw.group(1).replace("\\u003c", "<"))


def _panel(body: str, tab_value: str) -> str:
    """그 탭의 패널 마크업만 잘라낸다. 다음 패널 앞에서 끊는다."""
    found = re.search(
        r'<div class="tab-panel export-panel" data-panel='
        rf'"{tab_value}"[^>]*>(.*?)(?=<div class="tab-panel|</div><script)',
        body,
        re.S,
    )
    assert found, f"{tab_value} 패널이 없다"
    return found.group(1)


@pytest.mark.parametrize(
    "tab",
    [tab for tab in tab_registry.TABS if tab.insight is not None],
    ids=lambda tab: tab.value,
)
def test_ai_summary_row_sits_above_the_chart_grid(body: str, tab):
    """탭 줄과 카드 그리드 사이에 두 칸짜리 줄이 한 번 놓인다.

    AI 요약을 선언한 탭마다 확인한다. 탭을 더할 때 자리가 어긋나면
    여기서 걸린다.
    """
    inner = _panel(body, tab.value)
    row = inner.find(f'<section class="{layout.INSIGHT_ROW_CLASS}">')
    grid_at = inner.find('<section class="chart-grid">')
    assert row != -1 and grid_at != -1
    assert row < grid_at, "AI 요약이 차트 그리드보다 뒤에 있다"
    cards = re.findall(
        rf'<section class="{layout.insight_card_class()}">', inner
    )
    assert len(cards) == 2
    assert inner.count(tab.insight.text_id(tab.value)) == 1


def test_ai_summary_holds_a_text_for_every_branch(document: str):
    """서버가 없으므로 고를 수 있는 영업점의 글을 탭마다 담아 둔다."""
    summaries = _summaries(document)
    insights = [
        (tab, tab.insight)
        for tab in tab_registry.TABS
        if tab.insight is not None
    ]
    assert insights
    assert len(summaries) == len(insights)
    for tab, insight in insights:
        spec = summaries[insight.panel_id(tab.value)]
        assert spec["textId"] == insight.text_id(tab.value)
        assert spec["select"] == insight.select.key
        assert len(spec["lines"]) == BRANCH_COUNT
        for lines in spec["lines"].values():
            assert lines
        # 클래스 이름은 화면에서 가져온다. 문서 안에 다시 적으면 디자인을
        # 고쳤을 때 갈아 끼운 뒤에만 모양이 달라진다.
        assert spec["listClass"] == layout.INSIGHT_LIST_CLASS
        assert spec["lineClass"] == layout.INSIGHT_LINE_CLASS
        assert spec["emptyClass"] == layout.INSIGHT_EMPTY_CLASS


def test_ai_summary_keeps_the_tabs_apart(document: str):
    """탭마다 자기 글을 담는다. 같으면 한 탭의 글이 두 곳에 나온다."""
    summaries = _summaries(document)
    texts = [
        tuple(sorted(map(tuple, spec["lines"].values())))
        for spec in summaries.values()
    ]
    assert len(set(texts)) == len(texts)


def test_ai_summary_is_swapped_without_a_server(document: str):
    """고를 때 서버에 묻지 않고 담아 둔 글로 갈아 끼운다."""
    assert "showSummary" in document
    # 글 안에 태그가 들어 있어도 실행되지 않도록 textContent로 넣는다.
    # 문서 안의 코드는 공백을 줄여 담기므로(→ export_html._minify_js)
    # 들여쓰기로 자르지 않고 다음 함수까지를 본다.
    swap = re.search(
        r"function showSummary\(panelId\).*?function redraw\(",
        document,
        re.S,
    )
    assert swap
    assert "innerHTML = ''" in swap.group(0)
    assert "textContent" in swap.group(0)


def test_dropdown_list_is_drawn_by_the_document_not_the_browser(body: str):
    """펼친 목록까지 직접 그린다.

    기본 <select>를 쓰면 목록을 운영체제가 그려서 CSS가 닿지 않고,
    화면의 dcc.Dropdown과 모양이 달라진다.
    """
    assert "<select" not in body
    assert '<ul class="export-list" role="listbox" hidden>' in body
    lists = re.findall(r'<ul class="export-list".*?</ul>', body, re.S)
    assert lists
    for options in lists:
        # 고른 값은 항상 하나다. 없으면 트리거에 표시할 값이 없다.
        assert options.count("export-option--selected") == 1
        assert options.count('aria-selected="true"') == 1


def test_dropdown_list_height_matches_the_screen(document: str):
    """목록 높이는 화면의 maxHeight와 같은 값에서 온다."""
    assert f"max-height: {layout.DROPDOWN_MAX_HEIGHT}px" in document
    assert "__LIST_HEIGHT__" not in document


def test_tabs_reuse_the_screen_stylesheet(body: str):
    """탭은 화면과 같은 클래스를 함께 붙여 style.css가 몰게 한다.

    여백·글꼴을 export 쪽에 따로 적으면 화면 디자인을 고쳤을 때 갈라진다.
    """
    assert '<nav class="tab-bar export-tab-bar">' in body
    assert 'class="tab export-tab tab--selected' in body
    disabled = len(tab_registry.TAB_ORDER) - len(tab_registry.TABS)
    assert body.count('class="tab tab--disabled export-tab') == disabled


def test_columns_share_leftover_width_like_the_screen(document: str):
    """남는 폭을 화면의 flex와 같은 규칙으로 나눠 갖는다.

    화면은 창을 넓히면 컬럼도 넓어진다. 정적 HTML에는 그 기능이 없어
    문서 안의 코드가 같은 규칙으로 나눈다.
    """
    raw = re.search(r"var COLUMN_LAYOUT = (\{.*?\});\n", document, re.S)
    assert raw, "컬럼 폭 규칙이 없다"
    layouts = json.loads(raw.group(1))
    assert TABLE_ID in layouts
    specs = layouts[TABLE_ID]

    widths = grid.table_widths(COLUMNS)
    minimums = grid.table_min_widths(COLUMNS)
    flexes = grid.table_flex(COLUMNS)
    assert len(specs) == len(COLUMNS)
    for spec, column in zip(specs, COLUMNS):
        assert spec["width"] == widths[column.field]
        assert spec["min"] == minimums[column.field]
        assert spec["flex"] == flexes[column.field]

    # 고정 컬럼만 나눔에서 빠진다.
    assert [spec["flex"] for spec in specs].count(0) == 1
    behaviour = document[document.rfind("<script>") :]
    assert "fitColumns" in behaviour
    assert "window.addEventListener('resize', fitAllTables)" in behaviour


def test_total_row_sticks_exactly_under_the_header(document: str):
    """'전체' 행이 붙는 위치는 헤더 높이와 같아야 한다.

    값이 다르면 그 틈으로 스크롤되는 행이 비친다.
    """
    assert f"height: {grid.HEADER_HEIGHT}px" in document
    assert f"height: {grid.ROW_HEIGHT}px" in document
    total = re.search(r"\.export-row--total td \{([^}]*)\}", document, re.S)
    assert total
    assert f"top: {grid.HEADER_HEIGHT}px" in total.group(1)
    assert "__HEADER_HEIGHT__" not in document
    assert "__ROW_HEIGHT__" not in document


def test_selection_does_not_call_a_server(document: str):
    """선택은 브라우저 안에서 끝난다. 서버에 다시 묻지 않는다."""
    assert "Plotly.react" in document
    assert "fetch(" not in document.split("</script>")[-2]
    assert "XMLHttpRequest" not in _BEHAVIOUR(document)


def _BEHAVIOUR(document: str) -> str:
    return document[document.rfind("<script>") :]


def test_table_sort_uses_raw_values_not_formatted_text(body: str):
    """정렬 기준값은 서식 없는 원본이다.

    "12,345명"을 글자로 비교하면 1,000이 900보다 앞에 온다.

    숫자 컬럼만 본다. 어느 컬럼이 숫자인지는 셀에 붙은 클래스가 말해 준다
    (→ export_html._cell_class). 보이는 글자의 끝으로 가리면 'ETF시세'처럼
    단위와 같은 글자로 끝나는 이름이 숫자로 잘못 걸린다.
    """
    cells = re.findall(
        r'class="export-cell-number[^"]*"'
        r' data-sort="([^"]*)">([^<]*)</td>',
        body,
    )
    assert cells
    numeric = [
        (key, text) for key, text in cells if text.endswith(("명", "%", "세"))
    ]
    assert numeric
    for key, text in numeric:
        if key == "":
            assert text == "-"
            continue
        float(key)  # 숫자로 읽힌다
        assert key != text  # 서식이 붙기 전 값이다


def test_sorting_has_three_steps_like_the_screen(document: str):
    """오름 → 내림 → 처음 순서. AgGrid와 같다.

    처음 순서로 되돌리려면 각 행이 원래 자리를 기억하고 있어야 한다.
    """
    behaviour = document[document.rfind("<script>") :]
    assert "'': 'asc', asc: 'desc', desc: ''" in behaviour
    assert "restore()" in behaviour

    body = document[document.find("<body>") :]
    # 자리 번호는 표마다 0부터 다시 매긴다.
    for table_id, _columns in TABLES:
        rows = re.findall(r'data-row="(\d+)"', table_markup(body, table_id))
        assert rows == [str(index) for index in range(len(rows))], table_id
    # '전체' 행은 정렬 대상이 아니므로 자리를 갖지 않는다.
    assert 'export-row--total" data-row' not in body


def test_columns_can_be_resized(document: str):
    """헤더 경계를 끌어 너비를 바꾼다. 시작 너비는 화면과 같은 값이다."""
    body = document[document.find("<body>") :]
    table = re.search(
        r'<table class="export-table".*?</table>', body, re.S
    ).group(0)

    widths = [int(value) for value in re.findall(r"width:(\d+)px", table)]
    expected = grid.table_widths(COLUMNS)
    assert widths == [expected[column.field] for column in COLUMNS]
    assert table.count("export-resize") == len(widths)

    # 너비를 직접 정하려면 fixed가 필요하다.
    assert "table-layout: fixed" in document
    behaviour = document[document.rfind("<script>") :]
    assert "MIN_WIDTH" in behaviour
    # 너비를 조절한 직후의 클릭이 정렬로 이어지면 안 된다.
    assert "data-resizing" in behaviour


def test_branch_name_column_stays_visible_when_scrolling(document: str):
    """지점명 컬럼은 화면과 같이 왼쪽에 고정한다."""
    assert "position: sticky" in document
    assert ".export-table td:first-child" in document
    # 붙어 있는 칸은 배경이 불투명해야 뒤 내용이 비치지 않는다.
    sticky = document[document.find(".export-table th:first-child") :][:400]
    assert "background:" in sticky


def test_table_scrolls_at_the_same_height_as_the_screen(document: str):
    """표는 화면과 같은 높이 안에서 스크롤한다. 헤더와 전체 행은 남는다."""
    assert f"max-height: {layout.TABLE_HEIGHT}" in document
    assert "__TABLE_HEIGHT__" not in document
    for selector in (
        r"\.export-table th \{",
        r"\.export-row--total td \{",
        r"\.export-table td:first-child \{",
    ):
        block = re.search(selector + r"([^}]*)\}", document, re.S)
        assert block, selector
        assert "position: sticky" in block.group(1), selector


def test_growth_column_is_coloured_like_the_screen(body: str):
    """증가율은 오르면 --color-up, 내리면 --color-down 색을 쓴다.

    표마다 증감 컬럼의 자리와 개수가 다르므로 그 표의 선언으로 자리를
    찾는다. 거래 표처럼 증감 컬럼이 여럿인 표도 모두 확인한다.

    증감 컬럼이 아예 없는 표는 건너뛴다. 디지털 채널의 프로필 표처럼 값이
    모두 그 달의 수준이고 증감이 아닌 표가 있다.
    """
    coloured = 0
    for table_id, columns in TABLES:
        fields = [column.field for column in columns]
        growth = grid.growth_fields(columns)
        if not growth:
            continue
        indexes = [fields.index(field) for field in growth]
        markup = table_markup(body, table_id)
        for row in re.findall(r"<tr[^>]*>(.*?)</tr>", markup, re.S):
            cells = re.findall(
                r'<td class="([^"]*)" data-sort="([^"]*)"', row
            )
            for index in indexes:
                if len(cells) <= index:
                    continue
                classes, key = cells[index]
                if key == "":
                    continue
                value = float(key)
                if value > 0:
                    assert "export-up" in classes, (table_id, key)
                    coloured += 1
                elif value < 0:
                    assert "export-down" in classes, (table_id, key)
                    coloured += 1
                else:
                    assert "export-up" not in classes
                    assert "export-down" not in classes
    assert coloured, "색을 입힌 증가율 칸이 하나도 없다"
    # 다른 컬럼에는 색을 입히지 않는다(CSS 규칙은 <head>에 있어 세지 않는다).
    assert body.count("export-up") + body.count("export-down") == coloured


def test_total_row_is_outside_the_sortable_body(body: str):
    """'전체' 행은 정렬해도 맨 위에 남는다."""
    assert 'tbody class="export-total"' in body
    assert 'tbody class="export-rows"' in body
    total = re.search(
        r'<tbody class="export-total">(.*?)</tbody>', body, re.S
    )
    assert total and total.group(1).count("<tr") == 1


def test_table_replaces_aggrid_with_plain_html(body: str):
    """AgGrid 컴포넌트가 아니라 일반 <table>로 그린다."""
    assert "<table" in body
    assert "dashboard-grid" not in body
    assert "ag-grid" not in body

    for _field, name in grid.table_headers(COLUMNS):
        assert name in body
    # 헤더 1행 + 전체 1행 + 지점 행들.
    assert body.count("<tr") >= 2 + 1
    assert "export-row--total" in body


def test_table_uses_the_same_formatting_as_the_screen(body: str):
    """표기 규칙은 dashboard.format 한 곳에서 온다."""
    total_row = re.search(r'export-row--total">(.*?)</tr>', body, re.S)
    assert total_row
    cells = re.findall(r"<td[^>]*>([^<]*)</td>", total_row.group(1))
    assert cells[0] == "전체"
    # 고객 수는 "12,345명" 꼴이거나 값이 없으면 "-"다.
    assert re.fullmatch(r"[\d,]+명", cells[1]) or cells[1] == "-"


def test_values_in_data_cannot_inject_html():
    """데이터에 든 HTML이 문서에서 실행되지 않는다."""
    columns = (COLUMNS[0],)
    row = {columns[0].field: "<script>alert(1)</script>"}
    rendered = export_html._table_row(row, columns)
    assert "<script>" not in rendered
    assert "&lt;script&gt;" in rendered


def test_write_html_creates_the_file(tmp_path):
    target = tmp_path / "snapshot.html"
    written = export_html.write_html(target)
    assert written == target
    assert target.exists()
    assert target.read_text(encoding="utf-8").startswith("<!doctype html>")


# --- 반입 조건: dash-ag-grid 없이도 HTML은 만들어진다 -------------------------
def test_export_works_without_dash_ag_grid(tmp_path, monkeypatch):
    """AgGrid가 없는 환경에서도 정적 HTML을 만들 수 있어야 한다.

    내부망에는 dash-ag-grid가 없을 수 있다. 정적 HTML은 표를 AgGrid 없이
    `<table>`로 그리므로 원래 필요가 없는데, `layout.py`가 파일 맨 위에서
    가져오면 그 사실만으로 설치를 요구하게 된다. 그래서 실제로 화면의 표를
    그릴 때만 가져온다(→ dashboard/layout.py의 _table_card).

    이 테스트는 그 임포트가 다시 파일 맨 위로 올라가는 것을 막는다.
    """
    import builtins
    import importlib

    real_import = builtins.__import__

    def guard(name, *args, **kwargs):
        if name.split(".")[0] == "dash_ag_grid":
            raise ImportError("No module named 'dash_ag_grid'")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guard)
    monkeypatch.delitem(sys.modules, "dash_ag_grid", raising=False)

    # 이미 불러온 모듈은 임포트를 다시 하지 않으므로 새로 불러온다.
    for name in ("dashboard.layout", "export_html"):
        monkeypatch.delitem(sys.modules, name, raising=False)
    module = importlib.import_module("export_html")

    destination = tmp_path / "no-aggrid.html"
    module.write_html(destination)
    document = destination.read_text(encoding="utf-8")

    # 표가 빠지지 않고 그대로 들어간다.
    for table_id, _columns in TABLES:
        assert f'id="{table_id}"' in document, table_id


def test_screen_table_still_uses_ag_grid():
    """화면의 표는 AgGrid로 그린다. 정적 HTML만 <table>로 다시 만든다."""
    import inspect

    from dashboard import layout as layout_module

    source = inspect.getsource(layout_module._table_card)
    assert "import dash_ag_grid" in source
    assert "dag.AgGrid(" in source


def test_every_follower_chart_key_can_be_found():
    """선택 줄을 따르는 차트가 담아 둔 변형을 찾을 수 있어야 한다.

    문서 안의 코드는 조합 키를 만들어 `CHART_VARIANTS`에서 찾는다
    (→ export_html의 keyFor). 키를 만드는 규칙과 담을 때 쓴 규칙이
    어긋나면 하나도 찾지 못하고, 선택을 바꿔도 그림이 그대로 남는다.
    화면은 콜백이 다시 그리므로 정적 HTML에서만 드러난다.

    여기서는 그 규칙을 파이썬으로 그대로 흉내 내 모든 조합을 찾아본다.
    """
    from dashboard.data import load_dashboard_data

    dataset = load_dashboard_data()
    groups = export_html._chart_groups()
    order = export_html._select_order()
    variants = export_html._figure_variants(dataset)
    specs = export_html._tab_tables(dataset)

    checked = 0
    for tab in tab_registry.TABS:
        for group in tab.select_groups:
            spec = specs.get(group.key)
            if not spec:
                continue
            for chart in group.followers:
                chart_id = chart.chart_id(tab.value)
                # 줄을 따르는 차트는 어느 줄인지 적혀 있어야 한다. 없으면
                # 키가 빈 문자열이 되어 아무것도 찾지 못한다.
                assert groups.get(chart_id) == group.key, chart_id
                own = order.get(chart_id, [])
                for selection in group.combinations(dataset):
                    outer = [selection[key] for key in spec["order"]]
                    for chosen in chart.combinations(dataset) or [{}]:
                        parts = outer + [chosen[key] for key in own]
                        key = "|".join(parts)
                        assert key in variants[chart_id], (chart_id, key)
                        checked += 1
    assert checked, "줄을 따르는 차트가 하나는 있어야 한다"
