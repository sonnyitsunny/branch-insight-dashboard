"""정적 HTML 내보내기 검증.

인터넷 없이 열려야 하므로 외부 참조가 없는지 확인하고, 표 값이 Dash 화면과
같은 함수에서 나오는지 확인한다(→ AGENTS.md §14, §16).
"""

from __future__ import annotations

import json
import re

import pytest

import export_html
from dashboard import grid, layout


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
    assert not re.search(r"<link[^>]", document)
    assert "<img" not in document
    assert "<iframe" not in document
    assert "@import" not in document
    assert not re.search(r"url\(\s*['\"]?https?:", document)
    assert "fonts.googleapis" not in document


def test_plotly_js_is_embedded_once(document: str):
    """Plotly.js는 한 번만 들어간다. 차트마다 넣으면 파일이 네 배가 된다."""
    # 스크립트는 둘이다 — plotly.js 하나, 동작을 담은 코드 하나.
    assert document.count("<script>") == 2
    assert document.count("Plotly.newPlot") >= len(export_html._CHARTS)
    assert len(document) > 1_000_000  # plotly.js가 실제로 들어 있다


def test_css_is_inlined_from_the_project_file(document: str):
    assert "<style>" in document
    # assets/style.css의 토큰이 그대로 들어와 있다.
    assert "--color-primary" in document
    assert ".export-table" in document


def test_every_chart_is_rendered(body: str):
    assert body.count("plotly-graph-div") == len(export_html._CHARTS)
    for _key, title, div_id, _zoom, _selector in export_html._CHARTS:
        assert title in body
        assert f'id="{div_id}"' in body


def test_tab_bar_matches_the_screen(body: str):
    """화면과 같은 탭을 같은 순서로 보여준다. 고객 탭만 열려 있다."""
    labels = re.findall(r'export-tab[^"]*">([^<]+)<', body)
    expected = ["고객"] + [label for _value, label in layout.OTHER_TABS]
    assert labels == expected
    assert body.count("export-tab--selected") == 1
    assert body.count("export-tab--disabled") == len(layout.OTHER_TABS)


def test_branch_select_has_a_figure_for_every_option(document: str):
    """고를 수 있는 값마다 Figure가 문서에 담겨 있어야 갈아 끼울 수 있다.

    하나라도 빠지면 그 지점을 골랐을 때 화면이 그대로 멈춘다.
    """
    raw = re.search(
        r"var CHART_VARIANTS = (\{.*?\});\nvar CHART_CONFIGS", document, re.S
    )
    assert raw, "미리 만든 Figure 묶음이 없다"
    variants = json.loads(raw.group(1).replace("\\u003c", "<"))

    body = document[document.find("<body>") :]
    selects = re.findall(
        r'<div class="card-control export-dropdown" data-chart="([^"]+)">'
        r"(.*?)</div>",
        body,
        re.S,
    )
    assert selects, "지점 선택 상자가 없다"
    for chart_id, inner in selects:
        options = re.findall(r'data-value="([^"]*)"', inner)
        assert options
        for option in options:
            assert option in variants[chart_id], (chart_id, option)
        figure = variants[chart_id][options[0]]
        assert "data" in figure and "layout" in figure


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
    assert '"tab tab--selected export-tab export-tab--selected"' in body
    assert body.count("export-tab--disabled") == len(layout.OTHER_TABS)


def test_columns_share_leftover_width_like_the_screen(document: str):
    """남는 폭을 화면의 flex와 같은 규칙으로 나눠 갖는다.

    화면은 창을 넓히면 컬럼도 넓어진다. 정적 HTML에는 그 기능이 없어
    문서 안의 코드가 같은 규칙으로 나눈다.
    """
    raw = re.search(r"var COLUMN_LAYOUT = (\[.*?\]);\n", document, re.S)
    assert raw, "컬럼 폭 규칙이 없다"
    specs = json.loads(raw.group(1))

    widths = grid.table_widths()
    minimums = grid.table_min_widths()
    flexes = grid.table_flex()
    fields = [field for field, _name in grid.table_headers()]
    assert len(specs) == len(fields)
    for spec, field in zip(specs, fields):
        assert spec["width"] == widths[field]
        assert spec["min"] == minimums[field]
        assert spec["flex"] == flexes[field]

    # 고정 컬럼만 나눔에서 빠진다.
    assert [spec["flex"] for spec in specs].count(0) == 1
    behaviour = document[document.rfind("<script>") :]
    assert "fitColumns" in behaviour
    assert "window.addEventListener('resize', fitColumns)" in behaviour


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
    """
    cells = re.findall(r'data-sort="([^"]*)">([^<]*)</td>', body)
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
    rows = re.findall(r'data-row="(\d+)"', body)
    assert rows == [str(index) for index in range(len(rows))]
    # '전체' 행은 정렬 대상이 아니므로 자리를 갖지 않는다.
    assert 'export-row--total" data-row' not in body


def test_columns_can_be_resized(document: str):
    """헤더 경계를 끌어 너비를 바꾼다. 시작 너비는 화면과 같은 값이다."""
    body = document[document.find("<body>") :]
    table = re.search(
        r'<table class="export-table".*?</table>', body, re.S
    ).group(0)

    widths = [int(value) for value in re.findall(r"width:(\d+)px", table)]
    expected = grid.table_widths()
    assert widths == [expected[field] for field, _n in grid.table_headers()]
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
    """증가율은 오르면 --color-up, 내리면 --color-down 색을 쓴다."""
    index = [field for field, _n in grid.table_headers()].index(
        grid.GROWTH_FIELD
    )
    rows = re.findall(r"<tr[^>]*>(.*?)</tr>", body, re.S)
    coloured = 0
    for row in rows:
        cells = re.findall(r'<td class="([^"]*)" data-sort="([^"]*)"', row)
        if len(cells) <= index:
            continue
        classes, key = cells[index]
        if key == "":
            continue
        value = float(key)
        if value > 0:
            assert "export-up" in classes
            coloured += 1
        elif value < 0:
            assert "export-down" in classes
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

    headers = grid.table_headers()
    for _field, name in headers:
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
    headers = [("branch_name", "지점명")]
    row = {"branch_name": "<script>alert(1)</script>"}
    rendered = export_html._table_row(row, headers)
    assert "<script>" not in rendered
    assert "&lt;script&gt;" in rendered


def test_write_html_creates_the_file(tmp_path):
    target = tmp_path / "snapshot.html"
    written = export_html.write_html(target)
    assert written == target
    assert target.exists()
    assert target.read_text(encoding="utf-8").startswith("<!doctype html>")
