"""정적 HTML 보고서 생성.

서버 없이 브라우저에서 여는 특정 시점의 스냅샷을 만든다.

지점 선택과 표 정렬은 Dash에서 Python 콜백과 AgGrid가 하던 일이다. 서버가
없는 정적 HTML에서는 그대로 쓸 수 없으므로, 같은 동작을 브라우저 안에서
도는 코드로 다시 만든다.

- 지점 선택 — 지점마다 Figure를 미리 만들어 문서에 담고, 고를 때
  `Plotly.react`로 갈아 끼운다. 서버에 다시 묻지 않는다.
- 표 정렬 — 셀에 정렬용 원본 값을 함께 넣어 두고 헤더를 누르면 다시
  줄 세운다. '전체' 행은 정렬에서 빼 맨 위에 남긴다.
- 외부 라이브러리를 쓰지 않는다. 문서 안의 Plotly.js와 직접 쓴 코드뿐이다.

담기지 않는 것 — 서버 측 재조회, 기간 변경. 데이터를 다시 읽어야 하는
동작은 파일을 새로 만들어야 한다.

데이터 처리와 Figure 생성은 Dash 화면과 같은 함수를 쓴다. 표만 AgGrid 대신
일반 HTML `<table>`로 그리며, 표기 규칙은 `dashboard.grid`에서 가져온다.

실행:
    python export_html.py [저장할 파일 경로]
"""

from __future__ import annotations

import base64
import html
import json
import re
import sys
from pathlib import Path

from plotly.offline import get_plotlyjs
from plotly.utils import PlotlyJSONEncoder

from dashboard import callbacks, figures, grid, layout
from dashboard import tabs as tab_registry
from dashboard.data import (
    PROJECT_DIR,
    DashboardData,
    load_dashboard_data,
    reference_month,
)
from dashboard.tabs.registry import (
    GRID_TABLE,
    Chart,
    Tab,
    card_order,
    grid_order,
    row_order,
)

# 기본 저장 위치. 파일 이름에 기준 월을 넣어 언제 찍은 스냅샷인지 남긴다.
DEFAULT_STEM = "지점_공통고객_현황"

# 내보낸 문서에서 주석·군더더기 공백·줄바꿈을 덜어낸다(→ _minify_css,
# _minify_js). 소스는 주석을 그대로 두고 결과물에서만 뺀다.
# 만들어진 HTML을 사람이 읽으며 확인해야 할 때만 False로 둔다.
MINIFY_OUTPUT = True


def build_html(data: DashboardData | None = None) -> str:
    """대시보드 한 장을 담은 HTML 문서 전체를 문자열로 만든다.

    무엇을 그릴지 여기 적지 않는다. 화면과 같은 탭 등록표를 돌면서
    선언대로 그린다(→ dashboard.tabs).
    """
    if data is None:
        data = load_dashboard_data()
    view = callbacks.build_initial_view(data)
    variants = _figure_variants(data)
    slots = _slot_values(data)
    selected = tab_registry.default_value()

    return ("" if MINIFY_OUTPUT else "\n").join(
        [
            "<!doctype html>",
            '<html lang="ko">',
            "<head>",
            '<meta charset="utf-8">',
            '<meta name="viewport" content="width=device-width,'
            ' initial-scale=1">',
            f"<title>{html.escape(_title(view))}</title>",
            _favicon_tag(),
            _style_block(),
            _plotly_block(),
            "</head>",
            "<body>",
            '<div class="page">',
            _header(view),
            _kpi_row(view["kpis"]),
            _tab_bar(selected),
            *[
                _tab_panel(tab, view["tabs"][tab.value], selected, data)
                for tab in tab_registry.TABS
            ],
            "</div>",
            _behaviour_block(variants, slots, view, data),
            "</body>",
            "</html>",
        ]
    )


def write_html(destination: Path | str | None = None) -> Path:
    """HTML 파일을 만들고 저장한 경로를 돌려준다."""
    data = load_dashboard_data()
    if destination is None:
        month = reference_month(data) or "unknown"
        destination = PROJECT_DIR / f"{DEFAULT_STEM}_{month}.html"
    path = Path(destination)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(build_html(data), encoding="utf-8", newline="\n")
    return path


# --- 선택값별 Figure 미리 만들기 ---------------------------------------------
def _figure_variants(data: DashboardData) -> dict:
    """고를 수 있는 값마다 Figure를 미리 만들어 둔다.

    Dash는 고를 때마다 서버가 다시 그리지만, 정적 HTML에는 서버가 없다.
    미리 다 만들어 담아 두고 브라우저가 갈아 끼운다.

    어느 차트에 무엇을 담을지 여기 적지 않는다. 선택 컨트롤이 있는 차트를
    등록표에서 찾아 그 목록만큼 만든다. 탭이 늘어도 이 함수는 그대로다.
    """
    variants: dict = {}
    followers: set[str] = set()
    for tab in tab_registry.TABS:
        # 선택 줄을 따르는 차트는 그 줄의 조합만큼 담는다. 카드에 붙은
        # 컨트롤이 있으면 그 컨트롤의 값까지 곱한다. 화면에서 두 선택이
        # 함께 걸리므로(→ callbacks._register_group_selection) 담아 두는
        # 조합도 같아야 한다. 키는 줄의 값이 앞, 카드의 값이 뒤다
        # (→ _BEHAVIOUR_JS의 keyFor).
        for group in tab.select_groups:
            for chart in group.followers:
                chart_id = chart.chart_id(tab.value)
                followers.add(chart_id)
                variants[chart_id] = {
                    tab_registry.variant_key({**selection, **chosen}): (
                        chart.build(data, {**selection, **chosen})
                    )
                    for selection in group.combinations(data)
                    for chosen in chart.combinations(data)
                    or [chart.defaults(data)]
                }
        for chart in tab.charts:
            chart_id = chart.chart_id(tab.value)
            # 줄을 따르는 차트는 위에서 이미 담았다. 여기서 다시 담으면
            # 줄의 선택이 빠진 채로 덮어써진다.
            if chart_id in followers:
                continue
            combinations = chart.combinations(data)
            if not combinations:
                continue
            variants[chart_id] = {
                tab_registry.variant_key(selection): chart.build(
                    data, selection
                )
                for selection in combinations
            }
    return variants


def _slot_values(data: DashboardData) -> dict:
    """`variants=slot` 차트가 자리마다 갈아 끼울 숫자.

    선택이 셋이면 조합이 27×27×27이라 Figure를 다 담을 수 없다. 대신 고를
    수 있는 값마다 그 자리에 들어갈 숫자만 담아 두고, 브라우저가 그래프의
    해당 자리만 바꾼다.
    """
    values: dict = {}
    for tab in tab_registry.TABS:
        for chart in tab.charts:
            if chart.slot_values is None:
                continue
            values[chart.chart_id(tab.value)] = {
                "order": [select.key for select in chart.selects],
                "values": chart.slot_values(data),
            }
    return values


def _select_order() -> dict:
    """차트마다 선택 컨트롤의 순서. 조합 키를 만들 때 쓴다."""
    return {
        chart.chart_id(tab.value): [
            select.key for select in chart.selects
        ]
        for tab in tab_registry.TABS
        for chart in tab.charts
        if chart.selects
    }


def _chart_groups() -> dict:
    """선택 줄을 따르는 차트 → 그 줄의 이름.

    이런 차트의 조합 키는 줄의 값으로 시작하고, 카드에 자기 컨트롤이
    있으면 그 값이 뒤에 붙는다. 어느 줄을 봐야 하는지 문서 안의 코드가
    알아야 키를 만들 수 있다(→ _figure_variants, _BEHAVIOUR_JS의 keyFor).

    **자기 컨트롤이 없는 차트도 넣는다.** 그 차트의 키는 줄의 값 하나뿐인데,
    여기 없으면 문서 안의 코드가 줄을 찾지 못해 키가 빈 문자열이 된다. 그러면
    담아 둔 변형을 하나도 찾지 못해 선택을 바꿔도 그림이 그대로 남는다.
    """
    return {
        chart.chart_id(tab.value): group.key
        for tab in tab_registry.TABS
        for group in tab.select_groups
        for chart in group.followers
        if group.selects
    }


# --- 크기 줄이기 -------------------------------------------------------------
# 이 문서는 서버 없이 열리도록 필요한 것을 전부 안에 담는다. 그래서 쉽게
# 커진다. 무게는 세 곳에 있고 줄이는 방법이 각각 다르다.
#
# 1. 변형 Figure의 JSON — 가장 무겁다. Plotly가 Figure마다 붙이는 같은
#    template을 빼내고(→ _lift_template), 남는 JSON은 공백 없이 적는다.
# 2. Plotly.js — 이미 압축된 상태로 들어오므로 손대지 않는다.
# 3. 우리가 쓴 CSS·JS — 주석과 들여쓰기를 뺀다. 몇십 KB 수준이라 위의
#    둘에 비하면 작지만, 소스의 주석을 지우지 않고 얻을 수 있다.
_CSS_COMMENT = re.compile(r"/\*.*?\*/", re.S)
_CSS_TEXT = re.compile(r"\"[^\"\n]*\"|'[^'\n]*'")


def _minify_css(css: str) -> str:
    """CSS에서 주석과 군더더기 공백을 덜어낸다.

    따옴표 안은 건드리지 않는다. 글꼴 이름처럼 공백이 뜻을 갖는 자리가
    있다. 주석에 따옴표가 들어 있을 수 있으므로 주석을 먼저 지운다.

    `:` 뒤의 한 칸은 남긴다. 값을 눈으로 찾아 확인하는 검증이 있고
    (→ tests/test_export_html.py), 줄어드는 양은 얼마 되지 않는다.
    """
    if not MINIFY_OUTPUT:
        return css
    css = _CSS_COMMENT.sub("", css)
    parts = []
    last = 0
    for found in _CSS_TEXT.finditer(css):
        parts.append(_squeeze_css(css[last : found.start()]))
        parts.append(found.group(0))
        last = found.end()
    parts.append(_squeeze_css(css[last:]))
    return "".join(parts)


def _squeeze_css(text: str) -> str:
    """따옴표 밖의 공백만 줄인다.

    `{` 앞의 한 칸은 남긴다. 선택자를 그 모양 그대로 찾아 확인하는
    검증이 있고(→ tests/test_export_html.py), 규칙마다 한 글자다.
    """
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"\s*([};,])\s*", r"\1", text)
    text = re.sub(r"\s*\{\s*", " {", text)
    return text.replace(";}", "}")


def _minify_js(js: str) -> str:
    """JS에서 주석 줄과 들여쓰기를 덜어낸다.

    줄바꿈은 남긴다. 세미콜론 없이 끝나는 줄을 붙이면 뜻이 달라질 수
    있는데, 줄바꿈을 지워 얻는 양은 그 위험에 비해 작다.

    줄 단위로만 본다. 이 문서의 JS에는 코드 뒤에 붙는 주석도 정규식
    리터럴도 없어서 문자열 안의 `/`를 주석으로 잘못 볼 일이 없다.
    """
    if not MINIFY_OUTPUT:
        return js
    kept = []
    for line in js.split("\n"):
        text = line.strip()
        if text and not text.startswith("//"):
            kept.append(text)
    return "\n".join(kept)


def _lift_template(payload: dict) -> dict | None:
    """변형마다 똑같이 붙는 Plotly template을 빼서 한 번만 담는다.

    Plotly는 Figure를 JSON으로 만들 때 layout에 template 전체를 넣는다.
    7KB짜리가 변형 수만큼 복사되므로, 변형이 천 개를 넘으면 그것만으로
    문서의 절반이 template이 된다. 가장 많이 쓰인 것을 빼서 한 번만
    담고, 브라우저가 다시 그릴 때 도로 붙인다
    (→ _BEHAVIOUR_JS의 withTemplate).

    다른 template을 쓰는 Figure가 있으면 그것은 건드리지 않는다. 그
    Figure만 크게 두는 편이 화면이 달라지는 것보다 낫다.
    """
    found: list[tuple[dict, str]] = []
    counts: dict[str, int] = {}
    shapes: dict[str, dict] = {}
    for by_name in payload.values():
        for figure in by_name.values():
            figure_layout = figure.get("layout") or {}
            template = figure_layout.get("template")
            if template is None:
                continue
            key = json.dumps(
                template, cls=PlotlyJSONEncoder, sort_keys=True
            )
            found.append((figure_layout, key))
            counts[key] = counts.get(key, 0) + 1
            shapes.setdefault(key, template)
    if not counts:
        return None
    shared = max(counts, key=lambda key: counts[key])
    for figure_layout, key in found:
        if key == shared:
            figure_layout.pop("template", None)
    return shapes[shared]


# --- 조각 만들기 -------------------------------------------------------------
def _style_block() -> str:
    """CSS를 문서 안에 넣는다.

    외부 스타일시트를 참조하지 않는다. 정적 HTML은 CSS 파일 없이 혼자
    열려야 한다(→ AGENTS.md §7, §14).
    """
    css = (PROJECT_DIR / "assets" / "style.css").read_text(encoding="utf-8")
    # 크기는 화면 설정에서 그대로 가져온다. 두 곳에 적으면 어긋난다.
    # 특히 '전체' 행이 붙는 위치는 헤더 높이와 정확히 같아야 한다.
    # 값이 다르면 그 틈으로 스크롤되는 행이 비친다.
    extra = (
        _EXPORT_CSS.replace("__TABLE_HEIGHT__", layout.TABLE_HEIGHT)
        .replace("__CHART_HEIGHT__", layout.CHART_HEIGHT)
        .replace("__HEADER_HEIGHT__", str(grid.HEADER_HEIGHT))
        .replace("__ROW_HEIGHT__", str(grid.ROW_HEIGHT))
        .replace("__LIST_HEIGHT__", str(layout.DROPDOWN_MAX_HEIGHT))
    )
    # 자리를 채운 뒤에 줄인다. 채워 넣는 값에도 공백이 있을 수 있다.
    body = _minify_css(css) + _minify_css(extra)
    if not MINIFY_OUTPUT:
        body = f"\n{css}\n{extra}\n"
    return f"<style>{body}</style>"


def _plotly_block() -> str:
    """Plotly.js를 문서 안에 한 번만 넣는다.

    CDN에서 불러오지 않는다. 차트마다 넣으면 같은 스크립트가 네 번 들어가
    파일이 네 배가 된다.
    """
    return f"<script>{get_plotlyjs()}</script>"


def _title(view: dict) -> str:
    """제목. 화면과 같은 함수로 만든다(→ layout.page_title)."""
    return layout.page_title(view["current_month"])


def _favicon_tag() -> str:
    """브라우저 탭 아이콘.

    화면에서는 Dash가 assets/에서 같은 파일을 찾아 넣는다. 정적 HTML은
    파일 하나로 혼자 열려야 하므로 `assets/`를 가리키지 못하고 문서 안에
    심는다(→ layout.FAVICON_FILE).
    """
    raw = (PROJECT_DIR / "assets" / layout.FAVICON_FILE).read_bytes()
    data = base64.b64encode(raw).decode("ascii")
    return (
        '<link rel="icon" type="image/x-icon"'
        f' href="data:image/x-icon;base64,{data}">'
    )


def _logo_tag() -> str:
    """로고를 문서 안에 심는다.

    정적 HTML은 파일 하나로 혼자 열려야 해서 `assets/`를 가리킬 수 없다.
    화면과 같은 파일을 base64로 넣고 클래스도 같은 것을 쓴다. 크기는
    `style.css`의 `.page-logo`가 정하므로 여기 숫자를 적지 않는다.
    """
    raw = (PROJECT_DIR / "assets" / layout.LOGO_FILE).read_bytes()
    data = base64.b64encode(raw).decode("ascii")
    return (
        f'<img class="page-logo" alt="{html.escape(layout.LOGO_ALT)}"'
        f' src="data:image/png;base64,{data}">'
    )


def _header(view: dict) -> str:
    return (
        '<header class="page-header">'
        f"{_logo_tag()}"
        f'<h1 class="page-title">{html.escape(_title(view))}</h1>'
        "</header>"
    )


def _kpi_row(kpis: dict) -> str:
    cards = []
    for card in layout.KPI_CARDS:
        # 값도 문구도 화면과 같은 함수로 만든다. 여기서 다시 조립하면
        # 카드를 고칠 때 두 산출물이 갈라진다.
        value, sub_text, line, delta = layout.kpi_parts(card, kpis)
        value_html = html.escape(value)
        if sub_text:
            value_html += (
                '<span class="kpi-sub">'
                f"{html.escape(sub_text)}</span>"
            )
        cards.append(
            '<div class="kpi-card">'
            f'<p class="kpi-label">{html.escape(card.label)}</p>'
            f'<p class="kpi-value">{value_html}</p>'
            f'<p class="kpi-delta {layout.delta_class(delta)}">'
            f"{html.escape(line)}</p>"
            "</div>"
        )
    return f'<section class="kpi-row">{"".join(cards)}</section>'


def _tab_bar(selected: str) -> str:
    """탭 줄. 구현하지 않은 탭은 화면과 같이 이름만 비활성으로 둔다.

    화면과 같은 `tab` 클래스를 함께 붙인다. 여백·글꼴·색을 `style.css`가
    그대로 몰게 해서, 화면 디자인을 고치면 이쪽도 따라오게 한다.
    `export-tab`은 Dash가 스스로 그리던 테두리만 대신 그린다.
    """
    tabs = []
    for value, label in tab_registry.TAB_ORDER:
        if tab_registry.find(value) is None:
            tabs.append(
                '<span class="tab tab--disabled export-tab'
                f' export-tab--disabled">{html.escape(label)}</span>'
            )
            continue
        state = " tab--selected export-tab--selected"
        chosen = value == selected
        tabs.append(
            f'<button type="button" class="tab export-tab'
            f'{state if chosen else ""}" data-tab="{html.escape(value)}">'
            f"{html.escape(label)}</button>"
        )
    return f'<nav class="tab-bar export-tab-bar">{"".join(tabs)}</nav>'


def _tab_panel(
    tab: Tab, tab_view: dict, selected: str, data: DashboardData
) -> str:
    """탭 하나의 내용. 고르지 않은 탭은 숨겨 두고 눌렀을 때 보여준다."""
    parts = []
    for groups in tab.grid_rows:
        parts.extend(_row_parts(tab, groups, tab_view, data))
    hidden = "" if tab.value == selected else " hidden"
    return (
        f'<div class="tab-panel export-panel" '
        f'data-panel="{html.escape(tab.value)}"{hidden}>'
        f'{"".join(parts)}</div>'
    )


def _row_parts(
    tab: Tab, groups: tuple, tab_view: dict, data: DashboardData
) -> list[str]:
    """그리드 한 줄과 그 위에 놓이는 컨트롤.

    줄이 하나뿐인 탭은 지금까지와 같이 컨트롤 한 줄과 그리드가 온다.
    카드 안에 컨트롤을 넣은 줄은 한 그리드에 둘 이상 들어올 수 있다
    (→ registry.Tab.grid_rows). 그때는 자리 번호로 그리드 전체를 다시
    세운다(→ registry.row_order). 화면과 같은 규칙이다
    (→ layout._row_children).
    """
    parts: list[str] = []
    grid: list[tuple[int, str]] = []
    full: list[str] = []
    for group in groups:
        if group.row_selects:
            parts.append(_tab_controls(group, tab_view["selects"]))
        cards = layout.group_table_cards(
            tab_view.get("tables", []), group.name
        )
        # 카드 안에 넣는 컨트롤은 그 줄의 첫 표 카드에만 붙인다
        # (→ registry.PLACE_TABLE).
        inside = _card_controls(group, tab_view["selects"])
        first_table = cards[0]["table_id"] if cards else ""
        scopes = (
            _table_scopes(tab, group, data)
            if group.selects and cards
            else {}
        )
        # 카드 번호는 그 줄의 표에 걸친 순서다. 그리드로 옮겨도 조합별 행을
        # 찾는 자리가 달라지지 않도록 나누기 전에 매긴다(→ _body_rows).
        numbered = list(enumerate(cards))
        grid_cards = [
            (i, card) for i, card in numbered if card.get("in_grid")
        ]
        full_cards = [
            (i, card) for i, card in numbered if not card.get("in_grid")
        ]

        def table(
            card: dict,
            index: int,
            in_grid: bool = False,
            group=group,
            scopes=scopes,
            inside=inside,
            first=first_table,
        ) -> str:
            return _table_card(
                group,
                card,
                index,
                scopes,
                in_grid=in_grid,
                controls=inside if card["table_id"] == first else "",
            )

        grid.extend(
            # 표와 차트를 번갈아 놓는다(→ registry.grid_order).
            (
                card_order(item),
                table(item[1], item[0], in_grid=True)
                if kind == GRID_TABLE
                else _chart_card(tab, item, tab_view["charts"][item.key]),
            )
            for kind, item in grid_order(grid_cards, group.charts)
        )
        full.extend(table(card, index) for index, card in full_cards)
    if grid:
        drawn = "".join(row_order(grid))
        parts.append(f'<section class="chart-grid">{drawn}</section>')
    parts.extend(full)
    return parts


def _card_controls(group, selects: dict) -> str:
    """표 카드 헤더 안에 그리는 선택 컨트롤. 없으면 빈 문자열."""
    if not group.table_selects:
        return ""
    drawn = [
        _group_control(group, select, selects)
        for select in group.table_selects
    ]
    classes = layout.card_controls_class(group.table_selects)
    return f'<div class="{classes}">{"".join(drawn)}</div>'


def _group_control(group, select, selects: dict) -> str:
    """선택 줄의 컨트롤 하나. 화면과 같은 규칙으로 고른다
    (→ layout._group_control)."""
    options = selects["options"].get(select.key, [])
    current = selects["values"].get(select.key) or (
        options[0] if options else ""
    )
    if select.kind == tab_registry.KIND_RADIO:
        return _radio(group.key, select, options, current)
    return _dropdown(group.key, select, options, current)


def _table_scopes(
    tab: Tab, group, data: DashboardData
) -> dict[str, list]:
    """고를 수 있는 조합마다 그 줄의 표 행을 미리 만들어 둔다.

    Dash는 고를 때마다 서버가 다시 그리지만 정적 HTML에는 서버가 없다.
    조합 수는 그 줄의 선택 목록만큼이라 그만큼 행이 늘어난다. 지점이나
    기간이 크게 늘면 파일 크기를 확인한다(→ AGENTS.md §14).
    """
    return {
        tab_registry.variant_key(selection): [
            view["row_data"]
            for view in callbacks.build_table_views(
                tab, data, selection, group.tables
            )
        ]
        for selection in group.combinations(data)
    }


def _tab_controls(group, selects: dict) -> str:
    """선택 줄. 화면과 같은 클래스를 쓴다(→ layout)."""
    parts = [
        _group_control(group, select, selects)
        for select in group.selects
    ]
    return f'<div class="tab-controls">{"".join(parts)}</div>'


def _chart_card(tab: Tab, chart: Chart, card: dict) -> str:
    # 카드보다 넓게 그리는 그림은 그 폭으로 만든다. 카드 안에서 가로로
    # 스크롤하는 일은 화면과 같은 클래스가 맡는다
    # (→ layout._body_class, assets/style.css의 .chart-scroll).
    scroll_width = card.get("scroll_width", "")
    body = card["figure"].to_html(
        full_html=False,
        include_plotlyjs=False,
        config=figures.chart_config(chart.zoomable),
        div_id=chart.chart_id(tab.value),
        default_height=chart.height or layout.CHART_HEIGHT,
        default_width=scroll_width or "100%",
    )
    # 축을 고르는 컨트롤은 헤더가 아니라 그래프 위 그 축 옆에 겹쳐 그린다.
    # 화면과 같은 클래스를 쓰므로 자리는 style.css가 정한다.
    axis = _axis_controls(tab, chart, card)
    body_class = layout.chart_body_class(chart, scroll_width)
    return (
        '<section class="card">'
        '<header class="card-header">'
        f"{_card_heading(chart.title, chart.subtitle)}"
        f"{_card_header_right(_select(tab, chart, card), chart.note)}"
        "</header>"
        f'<div class="{body_class}">{body}{axis}</div>'
        "</section>"
    )


def _card_header_right(controls: str, note: str) -> str:
    """카드 헤더 오른쪽. 화면과 같은 규칙으로 묶는다(→ layout._chart_card).

    빈 상자를 두지 않는다. 두면 그 아래 안내 문구가 상자 사이 간격만큼
    내려와 옆 카드와 줄이 어긋난다(→ assets/style.css의 .card-header-right).
    """
    parts = [part for part in (controls, _card_note(note)) if part]
    if len(parts) == 1:
        return parts[0]
    return f'<div class="card-header-right">{"".join(parts)}</div>'


def _card_note(note: str) -> str:
    """카드 헤더 오른쪽 아래에 작게 붙는 안내 문구. 없으면 그리지 않는다."""
    if not note:
        return ""
    return f'<span class="card-note">{html.escape(note)}</span>'


def _card_heading(title: str, subtitle: str = "") -> str:
    """카드 헤더 왼쪽. 화면과 같은 클래스를 쓴다(→ layout.card_heading)."""
    heading = f'<h2 class="card-title">{html.escape(title)}</h2>'
    if not subtitle:
        return heading
    return (
        '<div class="card-heading">'
        f"{heading}"
        f'<span class="card-subtitle">{html.escape(subtitle)}</span>'
        "</div>"
    )


def _select(tab: Tab, chart: Chart, card: dict) -> str:
    """카드 헤더의 선택 컨트롤들.

    화면과 같은 순서로 컨트롤을 그린다. 컨트롤이 없으면 보조 문구를 두고,
    그 문구도 없으면 아무것도 그리지 않는다(→ layout._chart_card).
    """
    if not chart.header_selects:
        text = card.get("description", "")
        if not text:
            return ""
        return f'<span class="card-description">{html.escape(text)}</span>'
    parts = [
        _control(tab, chart, select, card)
        for select in chart.header_selects
    ]
    classes = layout.card_controls_class(chart.header_selects)
    return f'<div class="{classes}">{"".join(parts)}</div>'


def _axis_controls(tab: Tab, chart: Chart, card: dict) -> str:
    """그래프 위 축 옆에 겹쳐 그리는 선택 컨트롤들."""
    return "".join(
        _control(tab, chart, select, card, layout.axis_control_class(select))
        for select in chart.axis_selects
    )


def _control(
    tab: Tab, chart: Chart, select, card: dict, class_name: str = ""
) -> str:
    """선택 컨트롤 하나. 자리를 정하는 클래스만 밖에서 받는다."""
    div_id = chart.chart_id(tab.value)
    options = card["options"].get(select.key, [])
    current = card["values"].get(select.key) or (
        options[0] if options else ""
    )
    if select.kind == tab_registry.KIND_RADIO:
        return _radio(div_id, select, options, current, class_name)
    return _dropdown(div_id, select, options, current, class_name)


def _dropdown(
    div_id: str,
    select,
    options: list[str],
    current: str,
    class_name: str = "",
) -> str:
    """펼치는 선택 상자.

    Dash의 dcc.Dropdown은 Dash의 JavaScript가 있어야 열린다. 그렇다고
    브라우저 기본 select 요소를 쓰면 펼친 목록을 운영체제가 그려서 CSS가
    닿지 않는다. 화면과 같은 모양을 내려고 목록까지 직접 그린다.
    외부 라이브러리는 쓰지 않는다(→ AGENTS.md §14).

    라벨은 고르는 칸 왼쪽에 선다(→ assets/style.css의 .card-control).
    **그래서 누르는 버튼과 펼친 목록을 한 상자로 감싼다.** 목록은 그 상자를
    기준으로 자리를 잡으므로, 감싸지 않으면 라벨 폭까지 덮어 버튼보다 넓게
    펼쳐진다.
    """
    items = "".join(
        f'<li class="export-option'
        f'{" export-option--selected" if name == current else ""}"'
        f' role="option" aria-selected='
        f'"{"true" if name == current else "false"}"'
        f' data-value="{html.escape(name)}">{html.escape(name)}</li>'
        for name in options
    )
    label = (
        f'<span class="control-label">{html.escape(select.label)}</span>'
        if len(select.label) > 0
        else ""
    )
    classes = _control_class("export-dropdown", class_name)
    return (
        f'<div class="{classes}" data-chart="{div_id}"'
        f' data-select="{html.escape(select.key)}">'
        f"{label}"
        '<div class="export-dropdown-box">'
        '<button type="button" class="export-trigger" aria-haspopup="listbox"'
        ' aria-expanded="false">'
        f'<span class="export-value">{html.escape(current)}</span>'
        '<span class="export-arrow" aria-hidden="true"></span>'
        "</button>"
        f'<ul class="export-list" role="listbox" hidden>{items}</ul>'
        "</div></div>"
    )


def _control_class(*names: str) -> str:
    """컨트롤 바깥 상자의 클래스. 화면과 같은 이름을 쓴다(→ layout)."""
    return " ".join(name for name in ("card-control", *names) if name)


def _radio(
    div_id: str,
    select,
    options: list[str],
    current: str,
    class_name: str = "",
) -> str:
    """값이 두세 개뿐인 선택. 화면과 같이 펼치지 않고 나란히 그린다."""
    buttons = "".join(
        f'<button type="button" class="export-radio'
        f'{" export-radio--selected" if name == current else ""}"'
        f' role="radio" aria-checked='
        f'"{"true" if name == current else "false"}"'
        f' data-value="{html.escape(name)}">{html.escape(name)}</button>'
        for name in options
    )
    classes = _control_class(
        "card-control--radio", "export-radios", class_name
    )
    return (
        f'<div class="{classes}"'
        f' role="radiogroup" data-chart="{div_id}"'
        f' data-select="{html.escape(select.key)}">{buttons}</div>'
    )


def _table_card(
    group,
    card: dict,
    index: int,
    scopes: dict[str, list],
    in_grid: bool = False,
    controls: str = "",
) -> str:
    """AgGrid 대신 일반 표로 그린다.

    AgGrid 컴포넌트 자체는 정적 HTML에 담지 않는다. 같은 원본 데이터와 같은
    표기 함수를 써서 `<table>`로 만든다(→ AGENTS.md §14).
    정렬과 너비 조절은 문서 안의 코드가 처리한다.

    컬럼 너비를 직접 정하려면 `table-layout: fixed`가 필요하고, 그러려면
    시작 너비가 있어야 한다. 화면과 같은 값을 `grid`에서 가져온다.

    그 줄에 선택 컨트롤이 있으면 서버가 다시 그려 줄 수 없으므로, 고를 수
    있는 조합의 행을 모두 담아 두고 보이는 것만 바꾼다(→ _behaviour_block).
    """
    columns = card["columns"]
    widths = grid.table_widths(columns)
    colgroup = "".join(
        f'<col style="width:{widths[column.field]}px">' for column in columns
    )
    sortable = card.get("sortable", True)
    head = "".join(
        _table_header(column, position, sortable)
        for position, column in enumerate(columns)
    )

    # '전체' 행은 정렬에서 빼려고 별도 tbody에 둔다.
    total = card["grid_options"].get("pinnedTopRowData") or []
    total_rows = "".join(_table_row(row, columns, True) for row in total)
    body_rows = _body_rows(card, index, scopes)

    # 헤더 오른쪽. 컨트롤이 있으면 조작 안내를 빼고 상태 문구만 남긴다.
    # 화면과 같은 규칙이다(→ layout._table_header_right).
    description = card.get("description", "")
    note = (
        ""
        if controls
        else f'<span class="card-note">'
        f'{html.escape(card.get("guide", ""))}</span>'
    )
    # 정렬을 끈 표. 문서 안의 코드가 이 표시를 보고 정렬을 붙이지 않는다.
    sort_mark = "" if sortable else ' data-sortable="no"'
    scroll_class = "export-table-scroll"
    if card.get("auto_height"):
        # 행이 늘 몇 개뿐인 표는 높이를 내용에 맞춘다(→ layout.table_style).
        scroll_class += " export-table-scroll--auto"
    # 선언이 높이를 적은 표. CSS의 기본 높이를 이 값으로 덮는다. 숫자를
    # 여기 적지 않고 선언에서 받아 화면과 같은 높이가 되게 한다
    # (→ registry.Table.height).
    scroll_style = ""
    if card.get("height") and not card.get("auto_height"):
        scroll_style = f' style="max-height:{card["height"]}"'
    return (
        f'<section class="{layout.table_card_class(in_grid)}">'
        '<header class="card-header">'
        f'{_card_heading(card["title"], card.get("subtitle", ""))}'
        '<div class="card-header-right">'
        f"{controls}"
        f'<span class="card-description">{html.escape(description)}</span>'
        f"{note}"
        "</div></header>"
        f'<div class="card-body">'
        f'<div class="{scroll_class}"{scroll_style}>'
        f'<table class="export-table" id="{card["table_id"]}"'
        f' data-tab="{html.escape(group.key)}"{sort_mark}>'
        f"<colgroup>{colgroup}</colgroup>"
        f"<thead><tr>{head}</tr></thead>"
        f'<tbody class="export-total">{total_rows}</tbody>'
        f'<tbody class="export-rows">{body_rows}</tbody>'
        "</table></div></div></section>"
    )


def _body_rows(card: dict, index: int, scopes: dict[str, list]) -> str:
    """표 본문의 행들.

    탭에 선택 컨트롤이 없으면 첫 화면의 행만 담는다. 있으면 조합마다 행을
    담고 지금 고른 조합만 보여준다. 정렬해도 자리를 되돌릴 수 있도록 원래
    순서를 표 전체에 걸쳐 매긴다.
    """
    if not scopes:
        return "".join(
            _table_row(row, card["columns"], order=order)
            for order, row in enumerate(card["row_data"])
        )
    current = card.get("scope_key", "")
    parts = []
    order = 0
    for key, tables in scopes.items():
        for row in tables[index]:
            parts.append(
                _table_row(
                    row,
                    card["columns"],
                    order=order,
                    scope=key,
                    hidden=key != current,
                )
            )
            order += 1
    return "".join(parts)


def _table_row(
    row: dict | None,
    columns: tuple,
    total: bool = False,
    order: int | None = None,
    scope: str = "",
    hidden: bool = False,
) -> str:
    if not row:
        return ""
    cells = []
    for column in columns:
        value = row.get(column.field)
        # 행이 문구를 들고 있으면 그것을 쓴다. 값만 보고는 무엇을 적을지
        # 가릴 수 없는 컬럼이 있다(→ grid._cell_text).
        given = row.get(f"{column.field}{grid.TEXT_SUFFIX}")
        text = (
            given
            if isinstance(given, str)
            else grid.format_cell(columns, column.field, value)
        )
        # 정렬은 서식이 아니라 원본 값으로 한다. "12,345명"을 글자로 비교하면
        # 1,000이 900보다 앞에 온다.
        key = "" if value is None else str(value)
        classes = f"{_cell_class(column)} {_growth_class(column, value)}"
        cells.append(
            f'<td class="{classes.strip()}"'
            f' data-sort="{html.escape(key, quote=True)}">'
            f"{html.escape(text)}</td>"
        )
    css = "export-row--total" if total else ""
    # 정렬을 세 번 누르면 처음 순서로 돌아간다. 그때 쓸 원래 자리를 남긴다.
    position = "" if order is None else f' data-row="{order}"'
    # 어느 선택에 속한 행인지. 선택이 바뀌면 이 값으로 골라 보여준다.
    where = "" if not scope else f' data-scope="{html.escape(scope, True)}"'
    return (
        f'<tr class="{css}"{position}{where}{" hidden" if hidden else ""}>'
        f'{"".join(cells)}</tr>'
    )


def _table_header(column, position: int, sortable: bool) -> str:
    """컬럼 헤더 하나.

    정렬을 끈 표에는 누를 수 있는 표시를 두지 않는다. 눌러도 되는 것처럼
    보이는데 아무 일도 일어나지 않는 쪽이 더 헷갈린다. 너비 조절 손잡이는
    정렬과 무관하므로 그대로 둔다.
    """
    resize = (
        '<span class="export-resize" title="드래그해 너비를 조절합니다">'
        "</span>"
    )
    # 컬럼 이름은 따로 감싼다. 선택에 따라 이름이 바뀌는 표에서 문서 안의
    # 코드가 이 자리의 글자만 갈아 끼운다(→ _table_headers).
    label = (
        f'<span class="export-head-label">'
        f"{html.escape(column.header)}</span>"
    )
    if not sortable:
        return (
            f'<th class="{_cell_class(column)}">'
            f'<span class="export-head">{label}</span>'
            f"{resize}</th>"
        )
    return (
        f'<th class="{_cell_class(column)}" data-index="{position}"'
        f' data-kind="{_sort_kind(column)}" tabindex="0" role="button">'
        f'<span class="export-head">{label}'
        '<span class="export-sort"></span></span>'
        f"{resize}</th>"
    )


def _growth_class(column, value: object) -> str:
    """증감 색상 클래스.

    화면에서는 ag-grid의 cellStyle이 같은 일을 한다(→ grid._GROWTH_STYLE).
    부호가 서식(+/-)에도 나타나므로 색상만으로 구분하지 않는다.
    """
    if not column.growth or value is None:
        return ""
    try:
        number = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return ""
    if number > 0:
        return "export-up"
    if number < 0:
        return "export-down"
    return ""


def _cell_class(column) -> str:
    return "export-cell-number" if column.numeric else "export-cell-text"


def _sort_kind(column) -> str:
    return "number" if column.numeric else "text"


def _behaviour_block(
    variants: dict, slots: dict, view: dict, data: DashboardData
) -> str:
    """지점 선택과 표 정렬을 처리하는 코드.

    외부 라이브러리를 쓰지 않는다. `</script>`가 데이터 안에 들어 있어도
    문서가 깨지지 않도록 `<`를 이스케이프한다.

    변형 Figure가 이 문서에서 가장 무거우므로, 공통 template을 빼내고
    공백 없는 JSON으로 적는다(→ _lift_template, MINIFY_OUTPUT).
    """
    payload = {
        div_id: {
            name: figure.to_plotly_json()
            for name, figure in by_name.items()
        }
        for div_id, by_name in variants.items()
    }
    template = _lift_template(payload)

    def _encode(value) -> str:
        return json.dumps(
            value,
            cls=PlotlyJSONEncoder,
            ensure_ascii=False,
            separators=(",", ":"),
        ).replace("<", "\\u003c")

    return (
        "<script>\n"
        f"var CHART_TEMPLATE = {_encode(template)};\n"
        f"var CHART_VARIANTS = {_encode(payload)};\n"
        f"var CHART_SLOTS = {_encode(slots)};\n"
        f"var CHART_ORDER = {_encode(_select_order())};\n"
        f"var CHART_GROUPS = {_encode(_chart_groups())};\n"
        f"var CHART_CONFIGS = {_encode(_chart_configs())};\n"
        f"var TAB_TABLES = {_encode(_tab_tables(data))};\n"
        f"var COLUMN_LAYOUT = {_column_layout(view)};\n"
        f"{_minify_js(_BEHAVIOUR_JS)}\n"
        "</script>"
    )


def _tab_tables(data: DashboardData) -> dict:
    """선택 줄이 다시 그릴 표와 차트.

    선택 순서(`order`)로 조합 키를 만들고, 그 키가 붙은 행만 보여준다.
    표 ID는 화면과 같은 규칙으로 만든다(→ registry.Table.table_id).

    `charts`에는 그 선택을 따르는 차트 ID를 담는다. 표와 차트를 같은
    자리에서 갈아 끼워야 둘이 다른 지점을 가리키는 순간이 생기지 않는다
    (→ callbacks._register_group_selection).

    `headers`에는 컬럼 이름이 선택에 따라 바뀌는 표의 이름을 조합마다
    담는다. 서버가 없으므로 행과 마찬가지로 미리 만들어 두고 갈아 끼운다
    (→ registry.Table.columns).

    줄이 둘 이상인 탭은 줄마다 하나씩 담긴다. 키는 그 줄의 이름이며, 표의
    `data-tab`과 컨트롤의 `data-chart`가 같은 값을 쓴다
    (→ registry.SelectGroup.key).
    """
    tables = {}
    for tab in tab_registry.TABS:
        for group in tab.select_groups:
            if not group.selects or not (group.tables or group.followers):
                continue
            spec = {
                "order": [select.key for select in group.selects],
                "charts": [
                    chart.chart_id(tab.value) for chart in group.followers
                ],
            }
            headers = _table_headers(tab, group, data)
            if headers:
                spec["headers"] = headers
            tables[group.key] = spec
    return tables


def _table_headers(tab: Tab, group, data: DashboardData) -> dict:
    """컬럼 이름이 선택에 따라 바뀌는 표의 이름을 조합마다 담는다.

    조합 키는 행을 고를 때 쓰는 것과 같다(→ _table_scopes). 컬럼 수와
    순서는 바뀌지 않으므로 이름만 자리 순서대로 담는다.
    """
    dynamic = [table for table in group.tables if table.dynamic_columns]
    if not dynamic:
        return {}
    headers: dict[str, dict[str, list[str]]] = {}
    for table in dynamic:
        by_key = {}
        for selection in group.combinations(data):
            by_key[tab_registry.variant_key(selection)] = [
                column.header for column in table.columns_of(selection)
            ]
        headers[table.table_id(tab.value)] = by_key
    return headers


def _chart_configs() -> dict:
    """차트를 갈아 끼울 때 쓸 Plotly 설정. 화면과 같은 함수에서 고른다."""
    return {
        chart.chart_id(tab.value): figures.chart_config(chart.zoomable)
        for tab in tab_registry.TABS
        for chart in tab.charts
        if chart.selects or chart.follows_tab
    }


def _column_layout(view: dict) -> str:
    """표별·컬럼별 시작 너비·최소 너비·flex 값.

    화면은 AgGrid가 남는 폭을 flex로 나눠 갖는다. 창을 넓히면 컬럼도
    넓어진다. 정적 HTML 표에는 그 기능이 없으므로 같은 규칙을 문서 안의
    코드로 다시 만들고, 값은 `grid`에서 그대로 가져온다.

    표가 둘 이상일 수 있으므로 표 id를 키로 담는다. 표를 몇 개 그릴지는
    데이터가 정하므로 선언이 아니라 계산이 끝난 view에서 읽는다.
    """
    layouts: dict[str, list[dict]] = {}
    for tab in tab_registry.TABS:
        for card in view["tabs"][tab.value].get("tables", []):
            columns = card["columns"]
            widths = grid.table_widths(columns)
            minimums = grid.table_min_widths(columns)
            flexes = grid.table_flex(columns)
            layouts[card["table_id"]] = [
                {
                    "width": widths[column.field],
                    "min": minimums[column.field],
                    "flex": flexes[column.field],
                }
                for column in columns
            ]
    return json.dumps(
        layouts, ensure_ascii=False, separators=(",", ":")
    )


_BEHAVIOUR_JS = """
(function () {
  // 선택 컨트롤 — 차트마다 지금 고른 값을 모아 두고, 하나가 바뀌면
  // 그 차트를 다시 그린다. 컨트롤이 둘 이상이면 조합으로 찾는다.
  var CHART_STATE = {};

  function setChoice(chartId, selectKey, value) {
    if (!CHART_STATE[chartId]) { CHART_STATE[chartId] = {}; }
    CHART_STATE[chartId][selectKey] = value;
  }

  // 변형에서 빼 둔 Plotly template을 도로 붙인다. 빼지 않으면 똑같은
  // 7KB가 변형마다 복사돼 문서의 절반이 template이 된다
  // (→ export_html._lift_template). 한 번 붙으면 그 변형에 그대로 남는다.
  // 다른 template을 쓰는 Figure는 제 것을 들고 있으므로 건너뛴다.
  function withTemplate(layout) {
    if (layout && !layout.template && CHART_TEMPLATE) {
      layout.template = CHART_TEMPLATE;
    }
    return layout;
  }

  // 그 차트가 지금 보여줄 변형의 키. 선택 줄을 따르면서 자기 컨트롤도
  // 가진 차트는 줄의 값이 앞, 카드의 값이 뒤다. 담아 둘 때와 같은 차례여야
  // 한다(→ export_html._figure_variants).
  function keyFor(chartId) {
    var parts = [];
    var groupKey = CHART_GROUPS[chartId];
    if (groupKey && TAB_TABLES[groupKey]) {
      var spec = TAB_TABLES[groupKey];
      var outer = CHART_STATE[groupKey] || {};
      for (var g = 0; g < spec.order.length; g += 1) {
        parts.push(outer[spec.order[g]]);
      }
    }
    var order = CHART_ORDER[chartId] || [];
    var state = CHART_STATE[chartId] || {};
    for (var i = 0; i < order.length; i += 1) {
      parts.push(state[order[i]]);
    }
    return parts.join('|');
  }

  function draw(chartId) {
    var figure = (CHART_VARIANTS[chartId] || {})[keyFor(chartId)];
    if (!figure) { return; }
    Plotly.react(
      chartId, figure.data, withTemplate(figure.layout),
      CHART_CONFIGS[chartId]
    );
  }

  function redraw(chartId) {
    // 탭 전체 선택이면 그릴 것이 차트가 아니라 표다.
    if (TAB_TABLES[chartId]) { showScope(chartId); return; }
    var slots = CHART_SLOTS[chartId];
    if (slots) { redrawSlots(chartId, slots); return; }
    draw(chartId);
  }

  // 탭 전체 선택 — 그 탭의 표를 다시 그린다. 서버가 없으므로 고를 수 있는
  // 조합의 행을 모두 담아 두고, 지금 고른 조합의 행만 보여준다
  // (→ export_html._table_scopes). 정렬해 둔 순서는 그대로 남는다.
  function showScope(tabValue) {
    var spec = TAB_TABLES[tabValue];
    var state = CHART_STATE[tabValue] || {};
    var parts = [];
    for (var i = 0; i < spec.order.length; i += 1) {
      parts.push(state[spec.order[i]]);
    }
    var key = parts.join('|');
    var tables = document.querySelectorAll(
      'table.export-table[data-tab="' + tabValue + '"]'
    );
    var headers = spec.headers || {};
    Array.prototype.forEach.call(tables, function (table) {
      var rows = table.querySelectorAll('tbody.export-rows tr');
      Array.prototype.forEach.call(rows, function (row) {
        row.hidden = row.getAttribute('data-scope') !== key;
      });
      // 컬럼 이름이 선택에 따라 바뀌는 표. 미리 담아 둔 이름으로 갈아
      // 끼운다(→ export_html._table_headers).
      var names = (headers[table.id] || {})[key];
      if (!names) { return; }
      var labels = table.querySelectorAll('thead .export-head-label');
      for (var h = 0; h < labels.length && h < names.length; h += 1) {
        labels[h].textContent = names[h];
      }
    });
    // 같은 선택을 따르는 차트도 함께 갈아 끼운다. 표만 바꾸면 한 화면에서
    // 표와 그림이 서로 다른 지점을 가리킨다. 카드에 자기 컨트롤이 있는
    // 차트는 그 값까지 넣어 키를 만든다(→ keyFor).
    var charts = spec.charts || [];
    for (var c = 0; c < charts.length; c += 1) {
      draw(charts[c]);
    }
  }

  // 선택 하나가 그래프의 한 자리만 바꾸는 차트. 조합마다 Figure를 담으면
  // 폭발하므로 숫자만 담아 두고 그 자리만 갈아 끼운다.
  //
  // 여기서는 Plotly.react를 쓰지 않는다. react는 넘긴 배열이 지금 그려진
  // 것과 같은 객체면 바뀐 게 없다고 보고 다시 그리지 않는다. 제자리에서
  // 값만 바꿔 그대로 넘기면 화면이 그대로 남는다. restyle·relayout은
  // 무엇이 바뀌었는지 직접 알려 주므로 그 함정이 없다.
  function redrawSlots(chartId, slots) {
    var node = document.getElementById(chartId);
    if (!node || !node.data) { return; }
    var state = CHART_STATE[chartId] || {};
    var order = slots.order || [];

    function copyOf(value) {
      return value ? Array.prototype.slice.call(value) : null;
    }

    var ys = [];
    var texts = [];
    var names = [];
    var hasText = false;
    var hasNames = false;
    for (var t = 0; t < node.data.length; t += 1) {
      ys.push(copyOf(node.data[t].y) || []);
      var text = copyOf(node.data[t].text);
      var custom = copyOf(node.data[t].customdata);
      if (text) { hasText = true; }
      if (custom) { hasNames = true; }
      texts.push(text || []);
      names.push(custom || []);
    }
    // 막대 자리는 순서로 잡혀 있다(→ figures.create_asset_mix_figure).
    // 지점 이름은 x가 아니라 축 눈금과 hover에만 들어간다.
    var ticks = node.layout && node.layout.xaxis
      ? copyOf(node.layout.xaxis.ticktext) : null;

    for (var position = 0; position < order.length; position += 1) {
      var key = order[position];
      var chosen = state[key];
      var column = (slots.values[key] || {})[chosen];
      if (!column) { continue; }
      var at = position + 1;
      if (ticks && at < ticks.length) { ticks[at] = chosen; }
      for (var i = 0; i < ys.length; i += 1) {
        if (at >= ys[i].length) { continue; }
        ys[i][at] = column.y[i];
        // 막대 안에 적힌 문구도 함께 바꾼다. 값만 바꾸면 높이는 새 지점,
        // 적힌 숫자는 이전 지점이 되어 화면이 거짓말을 한다.
        if (column.text && at < texts[i].length) {
          texts[i][at] = column.text[i];
        }
        if (at < names[i].length) { names[i][at] = chosen; }
      }
    }

    var update = { y: ys };
    if (hasText) { update.text = texts; }
    if (hasNames) { update.customdata = names; }
    Plotly.restyle(chartId, update);
    if (ticks) {
      Plotly.relayout(chartId, { 'xaxis.ticktext': ticks });
    }
  }

  // 라디오 — 값이 두세 개뿐이라 펼치지 않고 나란히 둔다.
  var radioGroups = document.querySelectorAll('.export-radios');
  Array.prototype.forEach.call(radioGroups, function (group) {
    var chartId = group.getAttribute('data-chart');
    var selectKey = group.getAttribute('data-select');
    var buttons = group.querySelectorAll('.export-radio');
    var picked = group.querySelector('.export-radio--selected');
    if (picked) {
      setChoice(chartId, selectKey, picked.getAttribute('data-value'));
    }
    Array.prototype.forEach.call(buttons, function (button) {
      button.addEventListener('click', function () {
        Array.prototype.forEach.call(buttons, function (other) {
          other.classList.remove('export-radio--selected');
          other.setAttribute('aria-checked', 'false');
        });
        button.classList.add('export-radio--selected');
        button.setAttribute('aria-checked', 'true');
        setChoice(chartId, selectKey, button.getAttribute('data-value'));
        redraw(chartId);
      });
    });
  });

  // 지점 선택 — 미리 담아 둔 Figure로 갈아 끼운다.
  // 펼친 목록까지 직접 그린다. 브라우저 기본 select 요소를 쓰면 목록을
  // 운영체제가 그려서 화면과 모양이 달라진다.
  var dropdowns = document.querySelectorAll('.export-dropdown');
  var openOne = null;

  function closeOpen() {
    if (!openOne) { return; }
    openOne.list.hidden = true;
    openOne.trigger.setAttribute('aria-expanded', 'false');
    openOne.root.removeAttribute('data-state');
    openOne = null;
  }

  Array.prototype.forEach.call(dropdowns, function (root) {
    var trigger = root.querySelector('.export-trigger');
    var label = root.querySelector('.export-value');
    var list = root.querySelector('.export-list');
    var options = list.querySelectorAll('.export-option');
    var current = root;
    var chartId = root.getAttribute('data-chart');
    var selectKey = root.getAttribute('data-select');
    var chosen = list.querySelector('.export-option--selected');
    if (chosen) {
      setChoice(chartId, selectKey, chosen.getAttribute('data-value'));
    }

    function open() {
      if (openOne && openOne.root === root) { closeOpen(); return; }
      closeOpen();
      list.hidden = false;
      trigger.setAttribute('aria-expanded', 'true');
      root.setAttribute('data-state', 'open');
      openOne = { root: current, trigger: trigger, list: list };
      var picked = list.querySelector('.export-option--selected');
      if (picked) { picked.focus(); }
    }

    function choose(option) {
      Array.prototype.forEach.call(options, function (other) {
        other.classList.remove('export-option--selected');
        other.setAttribute('aria-selected', 'false');
      });
      option.classList.add('export-option--selected');
      option.setAttribute('aria-selected', 'true');
      label.textContent = option.getAttribute('data-value');
      closeOpen();
      trigger.focus();

      setChoice(chartId, selectKey, option.getAttribute('data-value'));
      redraw(chartId);
    }

    trigger.addEventListener('click', function (event) {
      event.stopPropagation();
      open();
    });

    Array.prototype.forEach.call(options, function (option, index) {
      option.tabIndex = -1;
      option.addEventListener('click', function (event) {
        event.stopPropagation();
        choose(option);
      });
      option.addEventListener('keydown', function (event) {
        var step = 0;
        if (event.key === 'ArrowDown') { step = 1; }
        if (event.key === 'ArrowUp') { step = -1; }
        if (step) {
          event.preventDefault();
          var next = options[index + step];
          if (next) { next.focus(); }
          return;
        }
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault();
          choose(option);
        }
        if (event.key === 'Escape') { closeOpen(); trigger.focus(); }
      });
    });
  });

  document.addEventListener('click', closeOpen);
  document.addEventListener('keydown', function (event) {
    if (event.key === 'Escape') { closeOpen(); }
  });

  // 탭 전환 — 구현한 탭의 패널을 미리 다 담아 두고 보이기만 바꾼다.
  // 서버에 다시 묻지 않는다. 구현하지 않은 탭은 버튼이 아니라 비활성
  // 글자라 여기 걸리지 않는다.
  var tabButtons = document.querySelectorAll('.export-tab[data-tab]');
  var panels = document.querySelectorAll('.export-panel');

  Array.prototype.forEach.call(tabButtons, function (button) {
    button.addEventListener('click', function () {
      var value = button.getAttribute('data-tab');
      Array.prototype.forEach.call(tabButtons, function (other) {
        var chosen = other === button;
        other.classList.toggle('tab--selected', chosen);
        other.classList.toggle('export-tab--selected', chosen);
      });
      Array.prototype.forEach.call(panels, function (panel) {
        panel.hidden = panel.getAttribute('data-panel') !== value;
      });
      // 숨어 있던 차트는 크기를 0으로 잡아 두었으므로 다시 맞춘다.
      Array.prototype.forEach.call(
        document.querySelectorAll('.plotly-graph-div'),
        function (chart) { Plotly.Plots.resize(chart); }
      );
      fitAllTables();
    });
  });

  // 표 정렬·너비 — 표마다 같은 동작을 붙인다.
  var fitters = [];

  function fitAllTables() {
    fitters.forEach(function (fit) { fit(); });
  }

  Array.prototype.forEach.call(
    document.querySelectorAll('table.export-table'),
    function (table) { setupTable(table); }
  );

  window.addEventListener('resize', fitAllTables);
  fitAllTables();

  function setupTable(table) {
  var layout = COLUMN_LAYOUT[table.id] || [];
  var body = table.querySelector('tbody.export-rows');
  var heads = table.querySelectorAll('th');
  var columns = table.querySelectorAll('col');

  function valueOf(row, index, kind) {
    var raw = row.cells[index].getAttribute('data-sort');
    if (raw === '' || raw === null) { return null; }
    return kind === 'number' ? parseFloat(raw) : raw;
  }

  function reorder(compare) {
    var rows = Array.prototype.slice.call(body.rows);
    rows.sort(compare);
    rows.forEach(function (row) { body.appendChild(row); });
  }

  function sortBy(index, kind, ascending) {
    reorder(function (a, b) {
      var left = valueOf(a, index, kind);
      var right = valueOf(b, index, kind);
      // 값이 없는 행은 방향과 상관없이 뒤로 보낸다.
      if (left === null && right === null) { return 0; }
      if (left === null) { return 1; }
      if (right === null) { return -1; }
      var order = kind === 'number'
        ? left - right
        : left.localeCompare(right, 'ko');
      return ascending ? order : -order;
    });
  }

  function restore() {
    reorder(function (a, b) {
      return parseInt(a.getAttribute('data-row'), 10)
        - parseInt(b.getAttribute('data-row'), 10);
    });
  }

  // 오름 → 내림 → 처음 순서. AgGrid와 같은 세 단계다.
  var NEXT = { '': 'asc', asc: 'desc', desc: '' };
  var MARK = { asc: ' \\u25B2', desc: ' \\u25BC', '': '' };

  // 정렬을 끈 표. 행 순서 자체가 뜻을 가지므로 원본 순서 그대로 둔다.
  // 화면에서는 columnDefs의 sortable: false가 같은 일을 한다.
  var sortable = table.getAttribute('data-sortable') !== 'no';

  Array.prototype.forEach.call(sortable ? heads : [], function (head) {
    function run() {
      var state = NEXT[head.getAttribute('data-order') || ''];
      Array.prototype.forEach.call(heads, function (other) {
        other.removeAttribute('data-order');
        other.querySelector('.export-sort').textContent = '';
      });
      if (state) { head.setAttribute('data-order', state); }
      head.querySelector('.export-sort').textContent = MARK[state];
      if (!state) { restore(); return; }
      sortBy(
        parseInt(head.getAttribute('data-index'), 10),
        head.getAttribute('data-kind'),
        state === 'asc'
      );
    }
    head.addEventListener('click', function (event) {
      // 너비를 조절한 직후의 클릭은 정렬로 치지 않는다.
      if (head.getAttribute('data-resizing') === 'yes') {
        head.removeAttribute('data-resizing');
        return;
      }
      run();
    });
    head.addEventListener('keydown', function (event) {
      if (event.key === 'Enter' || event.key === ' ') {
        event.preventDefault();
        run();
      }
    });
  });

  // 행 클릭 강조 — 컬럼이 많아 옆으로 훑을 때 보던 줄을 놓치지 않게 한다.
  // 화면 AgGrid의 행 선택과 같은 동작이다(→ grid.ROW_SELECTION). 한 번에
  // 한 행만 남기고, 고른 행을 다시 누르면 푼다. 정렬해도 클래스는 그 행에
  // 붙어 있으므로 고른 행이 따라 움직인다. '전체' 행은 다른 tbody에 있어
  // 여기 걸리지 않는다.
  body.addEventListener('click', function (event) {
    var node = event.target;
    while (node && node !== body && node.nodeName !== 'TR') {
      node = node.parentNode;
    }
    if (!node || node.nodeName !== 'TR') { return; }
    var already = node.classList.contains('export-row--picked');
    Array.prototype.forEach.call(
      body.querySelectorAll('tr.export-row--picked'),
      function (other) {
        other.classList.remove('export-row--picked');
      }
    );
    if (!already) { node.classList.add('export-row--picked'); }
  });

  // 컬럼 너비 — 화면의 flex와 같은 규칙으로 남는 폭을 나눠 갖는다.
  // 창을 넓히면 컬럼도 넓어진다. 고정 컬럼(flex 0)과 사용자가 직접
  // 끌어 놓은 컬럼은 나눔에서 빠지고 제 너비를 지킨다. AgGrid와 같다.
  var MIN_WIDTH = 60;
  var scroll = table.parentNode;
  var widths = layout.map(function (spec) { return spec.width; });
  var byHand = layout.map(function () { return false; });

  function applyWidths() {
    widths.forEach(function (width, index) {
      if (columns[index]) { columns[index].style.width = width + 'px'; }
    });
  }

  function fitColumns() {
    // 숨어 있는 탭의 표는 폭을 0으로 재므로 건드리지 않는다.
    if (!scroll.clientWidth) { return; }
    var shares = 0;
    var used = 0;
    layout.forEach(function (spec, index) {
      if (spec.flex && !byHand[index]) { shares += spec.flex; }
      else { used += widths[index]; }
    });
    if (!shares) { applyWidths(); return; }
    var each = (scroll.clientWidth - used) / shares;
    layout.forEach(function (spec, index) {
      if (!spec.flex || byHand[index]) { return; }
      widths[index] = Math.max(spec.min, Math.round(spec.flex * each));
    });
    applyWidths();
  }

  fitters.push(fitColumns);

  var dragging = null;

  Array.prototype.forEach.call(heads, function (head, index) {
    var handle = head.querySelector('.export-resize');
    if (!handle) { return; }
    handle.addEventListener('mousedown', function (event) {
      event.preventDefault();
      event.stopPropagation();
      dragging = {
        index: index,
        head: head,
        startX: event.clientX,
        startWidth: head.getBoundingClientRect().width
      };
      document.body.style.cursor = 'ew-resize';
    });
  });

  document.addEventListener('mousemove', function (event) {
    if (!dragging) { return; }
    var next = dragging.startWidth + (event.clientX - dragging.startX);
    // 직접 끈 컬럼은 그때부터 제 너비를 지킨다(화면의 flex 해제와 같다).
    byHand[dragging.index] = true;
    widths[dragging.index] = Math.max(MIN_WIDTH, Math.round(next));
    dragging.head.setAttribute('data-resizing', 'yes');
    fitColumns();
  });

  document.addEventListener('mouseup', function () {
    if (!dragging) { return; }
    dragging = null;
    document.body.style.cursor = '';
  });
  }
})();
"""


# 정적 HTML에만 쓰는 CSS. Dash 화면에는 이 클래스가 없으므로
# assets/style.css에 넣지 않는다. 색·간격은 그 파일의 토큰을 그대로 쓴다.
_EXPORT_CSS = """
/* 여백·글꼴·색은 style.css의 .tab이 몰고, 여기서는 Dash가 스스로
   그리던 테두리만 대신 그린다. 값을 두 곳에 적지 않는다. */
.export-tab-bar {
  border-bottom: 1px solid var(--color-grid);
}

/* 구현한 탭은 button, 아직 없는 탭은 span이다. button은 글꼴을 물려받지
   않으므로 여기서 맞춰 준다. 나머지는 .tab이 몰고 있다. */
.export-tab {
  font-family: var(--font-base);
  border: 1px solid var(--color-grid);
  border-bottom: 0;
  border-right: 0;
}

.export-tab:last-child { border-right: 1px solid var(--color-grid); }

/* .tab-panel의 display가 hidden 속성을 덮으므로 다시 숨긴다. */
.export-panel[hidden] { display: none; }

/* 선택 표시는 화면과 같이 상단 2px 주색상 선이다. 글자 굵기·색은
   style.css의 .tab--selected가 함께 맡는다. */
.export-tab--selected {
  border-top: 2px solid var(--color-primary);
}

/* 직접 그린 드롭다운. 브라우저 기본 <select>는 펼친 목록을 운영체제가
   그려서 CSS가 닿지 않는다. 화면의 .dash-dropdown과 같은 토큰을 쓴다. */
.export-dropdown {
  position: relative;
}

/* 누르는 버튼과 펼친 목록을 함께 감싼 상자. 목록이 이 상자를 기준으로
   자리를 잡아 버튼과 좌우 끝이 맞는다. 라벨은 이 상자 밖 왼쪽에 선다
   (→ export_html._dropdown, assets/style.css의 .card-control). */
.export-dropdown-box {
  position: relative;
}

.export-trigger {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  width: 100%;
  min-width: 148px;
  padding: 7px 10px;
  font-family: var(--font-base);
  font-size: 13px;
  color: var(--color-text);
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius);
  cursor: pointer;
}

.export-trigger:hover { border-color: var(--color-axis); }

.export-dropdown[data-state="open"] .export-trigger {
  border-color: var(--color-primary);
}

/* 펼침 표시. 색만으로 구분하지 않도록 글자 옆에 모양으로도 나타낸다. */
.export-arrow {
  width: 0;
  height: 0;
  border-left: 4px solid transparent;
  border-right: 4px solid transparent;
  border-top: 5px solid var(--color-axis);
}

/* 목록 높이는 화면의 dcc.Dropdown maxHeight와 같은 값을 쓴다. */
.export-list {
  position: absolute;
  top: calc(100% + 2px);
  right: 0;
  left: 0;
  z-index: 20;
  max-height: __LIST_HEIGHT__px;
  overflow-y: auto;
  padding: 4px 0;
  font-size: 13px;
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius);
  box-shadow: 0 2px 8px rgba(72, 83, 91, 0.16);
  scrollbar-width: thin;
  scrollbar-color: var(--color-border) transparent;
}

.export-list[hidden] { display: none; }

.export-option {
  padding: 6px 10px;
  color: var(--color-text);
  cursor: pointer;
}

.export-option:hover,
.export-option:focus { background: var(--color-page); }

.export-option--selected {
  color: var(--color-primary-dark);
  font-weight: 700;
}

/* 화면의 AgGrid와 같은 높이 안에서 세로·가로로 스크롤한다.
   높이는 layout.TABLE_HEIGHT에서 채워 넣는다. */
.export-table-scroll {
  overflow: auto;
  max-height: __TABLE_HEIGHT__;
}

/* 행이 늘 몇 개뿐인 표는 높이를 내용에 맞춘다. 화면에서는 ag-grid의
   autoHeight가 같은 일을 한다(→ grid.build_grid_options). */
.export-table-scroll--auto {
  max-height: none;
}

/* 차트와 나란히 놓는 표. 옆 카드와 아랫선이 맞도록 그래프와 같은 높이
   안에서 스크롤한다. 높이는 layout.CHART_HEIGHT에서 채워 넣는다
   (→ layout.table_style). */
.card--table-grid .export-table-scroll {
  max-height: __CHART_HEIGHT__;
}

/* 고르지 않은 조합의 행. tr의 display가 hidden 속성을 덮으므로 다시 숨긴다.
   행을 지우지 않고 숨기기만 해서, 선택을 되돌리면 그대로 다시 나타난다. */
.export-rows tr[hidden] {
  display: none;
}

/* 컬럼 너비를 직접 정하려면 fixed가 필요하다. 너비 합이 카드보다 넓으면
   위 상자가 가로로 스크롤된다. */
.export-table {
  table-layout: fixed;
  width: max-content;
  min-width: 100%;
  border-collapse: separate;
  border-spacing: 0;
  font-size: 13px;
}

/* 세로로 스크롤해도 헤더는 위에 남는다. AgGrid와 같다.
   붙어 있는 칸은 배경이 불투명해야 뒤 내용이 비치지 않는다. */
.export-table th {
  position: sticky;
  top: 0;
  z-index: 3;
  height: __HEADER_HEIGHT__px;
  padding: 0 14px;
  text-align: center;
  font-weight: 700;
  color: var(--color-secondary);
  background: var(--color-page);
  border-bottom: 1px solid var(--color-grid);
  border-right: 1px solid var(--color-border);
  white-space: nowrap;
  cursor: pointer;
  user-select: none;
}

.export-table th:last-child { border-right: 0; }
.export-table th:hover { background: var(--color-surface-alt); }

/* 정렬을 끈 표의 헤더. 누를 수 있는 것처럼 보이지 않게 한다. */
.export-table[data-sortable="no"] th {
  cursor: default;
}

.export-table[data-sortable="no"] th:hover {
  background: var(--color-page);
}

.export-head {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
}

.export-sort { color: var(--color-primary); }

/* 너비를 잡아 끄는 자리. 화면의 ag-grid 손잡이와 같은 폭·색을 쓴다. */
.export-resize {
  position: absolute;
  top: 0;
  right: -4px;
  width: 8px;
  height: 100%;
  cursor: ew-resize;
  z-index: 4;
}

.export-resize::after {
  content: "";
  position: absolute;
  top: 30%;
  left: 3px;
  width: 2px;
  height: 40%;
  background: var(--color-axis);
}

.export-table td {
  height: __ROW_HEIGHT__px;
  padding: 0 14px;
  border-bottom: 1px solid var(--color-grid);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.export-rows tr:hover td { background: var(--color-surface-alt); }

.export-cell-text { text-align: left; }

/* 증감 색상. 화면의 --color-up/--color-down 토큰을 그대로 쓴다.
   부호가 서식(+/-)에도 나타나므로 색상만으로 구분하지 않는다. */
.export-up { color: var(--color-up); }
.export-down { color: var(--color-down); }

/* 자릿수 폭이 흔들리지 않게 tabular-nums를 함께 쓴다. */
.export-cell-number {
  text-align: right;
  font-variant-numeric: tabular-nums;
}

/* 지점명 컬럼 고정. 가로로 스크롤해도 어느 지점의 값인지 보여야 한다. */
.export-table td:first-child {
  position: sticky;
  left: 0;
  z-index: 2;
  background: var(--color-surface);
  border-right: 1px solid var(--color-grid);
}

/* 왼쪽 위 모서리는 가로·세로 양쪽으로 붙으므로 가장 위에 둔다. */
.export-table th:first-child {
  left: 0;
  z-index: 4;
  border-right: 1px solid var(--color-grid);
}

/* '전체' 행. 세로로 스크롤해도 헤더 바로 아래에 남는다.
   붙는 위치는 헤더 높이와 정확히 같아야 한다. 값이 다르면 그 틈으로
   스크롤되는 행이 비친다. 그래서 숫자를 적지 않고 grid에서 채워 넣는다. */
.export-row--total td {
  position: sticky;
  top: __HEADER_HEIGHT__px;
  z-index: 1;
  background: var(--color-surface-strong);
  font-weight: 700;
  border-bottom: 2px solid var(--color-secondary);
}

.export-row--total td:first-child {
  z-index: 3;
  background: var(--color-surface-strong);
}

.export-rows tr:hover td:first-child {
  background: var(--color-surface-alt);
}

/* 클릭해 고른 행. 화면 AgGrid의 행 선택과 같은 토큰을 쓴다.
   호버보다 뒤에 적어 고른 행 위에 마우스를 올려도 색이 남게 한다.
   고정 컬럼 셀은 자기 배경이 따로 있으므로 함께 지정한다. */
.export-rows tr.export-row--picked td,
.export-rows tr.export-row--picked:hover td,
.export-rows tr.export-row--picked td:first-child,
.export-rows tr.export-row--picked:hover td:first-child {
  background: var(--color-surface-selected);
}

/* 배경색만으로 구분하지 않도록 왼쪽 끝에 세로 표시를 함께 그린다.
   화면 쪽 .ag-row-selected 표시와 같은 폭·색이다. */
.export-rows tr.export-row--picked td:first-child {
  box-shadow: inset 3px 0 0 var(--color-primary);
}
"""


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else None
    written = write_html(target)
    size_mb = written.stat().st_size / 1024 / 1024
    print(f"만들었습니다: {written}")
    note = "" if MINIFY_OUTPUT else " · 압축 끔"
    print(f"크기: {size_mb:.1f} MB (Plotly.js 포함{note})")
