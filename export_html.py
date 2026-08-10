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

import html
import json
import sys
from datetime import datetime
from pathlib import Path

from plotly.offline import get_plotlyjs
from plotly.utils import PlotlyJSONEncoder

from dashboard import callbacks, figures, grid, layout
from dashboard import format as fmt
from dashboard import tabs as tab_registry
from dashboard.data import (
    PROJECT_DIR,
    DashboardData,
    load_dashboard_data,
    reference_month,
)
from dashboard.tabs.registry import Chart, Tab, Table

# 기본 저장 위치. 파일 이름에 기준 월을 넣어 언제 찍은 스냅샷인지 남긴다.
DEFAULT_STEM = "지점_공통고객_현황"


def build_html(data: DashboardData | None = None) -> str:
    """대시보드 한 장을 담은 HTML 문서 전체를 문자열로 만든다.

    무엇을 그릴지 여기 적지 않는다. 화면과 같은 탭 등록표를 돌면서
    선언대로 그린다(→ dashboard.tabs).
    """
    if data is None:
        data = load_dashboard_data()
    view = callbacks.build_initial_view(data)
    variants = _figure_variants(data)
    selected = tab_registry.default_value()

    return "\n".join(
        [
            "<!doctype html>",
            '<html lang="ko">',
            "<head>",
            '<meta charset="utf-8">',
            '<meta name="viewport" content="width=device-width,'
            ' initial-scale=1">',
            f"<title>{html.escape(layout.PAGE_TITLE)}</title>",
            _style_block(),
            _plotly_block(),
            "</head>",
            "<body>",
            '<div class="page">',
            _header(view),
            _kpi_row(view["kpis"]),
            _tab_bar(selected),
            *[
                _tab_panel(tab, view["tabs"][tab.value], selected)
                for tab in tab_registry.TABS
            ],
            "</div>",
            _behaviour_block(variants),
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
    for tab in tab_registry.TABS:
        for chart in tab.charts:
            if chart.options is None:
                continue
            variants[chart.chart_id(tab.value)] = {
                option: chart.build(data, option)
                for option in chart.options(data)
            }
    return variants


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
        .replace("__HEADER_HEIGHT__", str(grid.HEADER_HEIGHT))
        .replace("__ROW_HEIGHT__", str(grid.ROW_HEIGHT))
        .replace("__LIST_HEIGHT__", str(layout.DROPDOWN_MAX_HEIGHT))
    )
    return f"<style>\n{css}\n{extra}\n</style>"


def _plotly_block() -> str:
    """Plotly.js를 문서 안에 한 번만 넣는다.

    CDN에서 불러오지 않는다. 차트마다 넣으면 같은 스크립트가 네 번 들어가
    파일이 네 배가 된다.
    """
    return f"<script>{get_plotlyjs()}</script>"


def _header(view: dict) -> str:
    made_at = datetime.now().strftime("%Y-%m-%d %H:%M")
    subtitle = (
        f"기준 월 {fmt.format_month(view['current_month'])}"
        f" · 전월 비교 {fmt.format_month(view['previous_month'])}"
    )
    note = f"{made_at} 기준 스냅샷"
    return (
        '<header class="page-header">'
        f'<h1 class="page-title">{html.escape(layout.PAGE_TITLE)}</h1>'
        f'<p class="page-subtitle">{html.escape(subtitle)}</p>'
        f'<p class="page-subtitle">{html.escape(note)}</p>'
        "</header>"
    )


def _kpi_row(kpis: dict) -> str:
    cards = []
    for key, label, value_format, delta_format in layout.KPI_CARDS:
        metric = kpis.get(key, {})
        value = value_format(metric.get("value"))
        delta = metric.get("delta")
        cards.append(
            '<div class="kpi-card">'
            f'<p class="kpi-label">{html.escape(label)}</p>'
            f'<p class="kpi-value">{html.escape(value)}</p>'
            f'<p class="kpi-delta {layout.delta_class(delta)}">'
            f"전월 대비 {html.escape(delta_format(delta))}</p>"
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


def _tab_panel(tab: Tab, tab_view: dict, selected: str) -> str:
    """탭 하나의 내용. 고르지 않은 탭은 숨겨 두고 눌렀을 때 보여준다."""
    parts = []
    if tab.charts:
        cards = "".join(
            _chart_card(tab, chart, tab_view["charts"][chart.key])
            for chart in tab.charts
        )
        parts.append(f'<section class="chart-grid">{cards}</section>')
    if tab.table is not None:
        parts.append(_table_card(tab, tab.table, tab_view["table"]))
    hidden = "" if tab.value == selected else " hidden"
    return (
        f'<div class="tab-panel export-panel" '
        f'data-panel="{html.escape(tab.value)}"{hidden}>'
        f'{"".join(parts)}</div>'
    )


def _chart_card(tab: Tab, chart: Chart, card: dict) -> str:
    body = card["figure"].to_html(
        full_html=False,
        include_plotlyjs=False,
        config=figures.chart_config(chart.zoomable),
        div_id=chart.chart_id(tab.value),
        default_height=layout.CHART_HEIGHT,
    )
    return (
        '<section class="card">'
        '<header class="card-header">'
        f'<h2 class="card-title">{html.escape(chart.title)}</h2>'
        '<div class="card-header-right">'
        f"{_select(tab, chart, card)}"
        f'<span class="card-note">{html.escape(chart.note)}</span>'
        "</div></header>"
        f'<div class="card-body">{body}</div>'
        "</section>"
    )


def _select(tab: Tab, chart: Chart, card: dict) -> str:
    """선택 상자.

    Dash의 dcc.Dropdown은 Dash의 JavaScript가 있어야 열린다. 그렇다고
    브라우저 기본 select 요소를 쓰면 펼친 목록을 운영체제가 그려서 CSS가
    닿지 않는다. 화면과 같은 모양을 내려고 목록까지 직접 그린다.
    외부 라이브러리는 쓰지 않는다(→ AGENTS.md §14).
    """
    if chart.options is None:
        text = card.get("description", "")
        return f'<span class="card-description">{html.escape(text)}</span>'
    options = card["options"]
    current = card["value"] or (options[0] if options else "")
    div_id = chart.chart_id(tab.value)
    items = "".join(
        f'<li class="export-option'
        f'{" export-option--selected" if name == current else ""}"'
        f' role="option" aria-selected='
        f'"{"true" if name == current else "false"}"'
        f' data-value="{html.escape(name)}">{html.escape(name)}</li>'
        for name in options
    )
    return (
        f'<div class="card-control export-dropdown" data-chart="{div_id}">'
        '<button type="button" class="export-trigger" aria-haspopup="listbox"'
        ' aria-expanded="false">'
        f'<span class="export-value">{html.escape(current)}</span>'
        '<span class="export-arrow" aria-hidden="true"></span>'
        "</button>"
        f'<ul class="export-list" role="listbox" hidden>{items}</ul>'
        "</div>"
    )


def _table_card(tab: Tab, table: Table, card: dict) -> str:
    """AgGrid 대신 일반 표로 그린다.

    AgGrid 컴포넌트 자체는 정적 HTML에 담지 않는다. 같은 원본 데이터와 같은
    표기 함수를 써서 `<table>`로 만든다(→ AGENTS.md §14).
    정렬과 너비 조절은 문서 안의 코드가 처리한다.

    컬럼 너비를 직접 정하려면 `table-layout: fixed`가 필요하고, 그러려면
    시작 너비가 있어야 한다. 화면과 같은 값을 `grid`에서 가져온다.
    """
    columns = table.columns
    widths = grid.table_widths(columns)
    colgroup = "".join(
        f'<col style="width:{widths[column.field]}px">' for column in columns
    )
    head = "".join(
        f'<th class="{_cell_class(column)}" data-index="{index}"'
        f' data-kind="{_sort_kind(column)}" tabindex="0" role="button">'
        f'<span class="export-head">{html.escape(column.header)}'
        '<span class="export-sort"></span></span>'
        '<span class="export-resize" title="드래그해 너비를 조절합니다">'
        "</span></th>"
        for index, column in enumerate(columns)
    )

    # '전체' 행은 정렬에서 빼려고 별도 tbody에 둔다.
    total = card["grid_options"].get("pinnedTopRowData") or []
    total_rows = "".join(_table_row(row, columns, True) for row in total)
    body_rows = "".join(
        _table_row(row, columns, order=index)
        for index, row in enumerate(card["row_data"])
    )

    description = card.get("description", "")
    return (
        '<section class="card card--table">'
        '<header class="card-header">'
        f'<h2 class="card-title">{html.escape(table.title)}</h2>'
        '<div class="card-header-right">'
        f'<span class="card-description">{html.escape(description)}</span>'
        f'<span class="card-note">{html.escape(table.guide)}</span>'
        "</div></header>"
        '<div class="card-body"><div class="export-table-scroll">'
        f'<table class="export-table" id="{table.table_id(tab.value)}">'
        f"<colgroup>{colgroup}</colgroup>"
        f"<thead><tr>{head}</tr></thead>"
        f'<tbody class="export-total">{total_rows}</tbody>'
        f'<tbody class="export-rows">{body_rows}</tbody>'
        "</table></div></div></section>"
    )


def _table_row(
    row: dict | None,
    columns: tuple,
    total: bool = False,
    order: int | None = None,
) -> str:
    if not row:
        return ""
    cells = []
    for column in columns:
        value = row.get(column.field)
        text = grid.format_cell(columns, column.field, value)
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
    return f'<tr class="{css}"{position}>{"".join(cells)}</tr>'


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


def _behaviour_block(variants: dict) -> str:
    """지점 선택과 표 정렬을 처리하는 코드.

    외부 라이브러리를 쓰지 않는다. `</script>`가 데이터 안에 들어 있어도
    문서가 깨지지 않도록 `<`를 이스케이프한다.
    """
    payload = {
        div_id: {
            name: figure.to_plotly_json()
            for name, figure in by_name.items()
        }
        for div_id, by_name in variants.items()
    }
    encoded = json.dumps(
        payload, cls=PlotlyJSONEncoder, ensure_ascii=False
    ).replace("<", "\\u003c")
    configs = json.dumps(
        _chart_configs(), ensure_ascii=False
    ).replace("<", "\\u003c")
    return (
        "<script>\n"
        f"var CHART_VARIANTS = {encoded};\n"
        f"var CHART_CONFIGS = {configs};\n"
        f"var COLUMN_LAYOUT = {_column_layout()};\n"
        f"{_BEHAVIOUR_JS}\n"
        "</script>"
    )


def _chart_configs() -> dict:
    """차트를 갈아 끼울 때 쓸 Plotly 설정. 화면과 같은 함수에서 고른다."""
    return {
        chart.chart_id(tab.value): figures.chart_config(chart.zoomable)
        for tab in tab_registry.TABS
        for chart in tab.charts
        if chart.options is not None
    }


def _column_layout() -> str:
    """표별·컬럼별 시작 너비·최소 너비·flex 값.

    화면은 AgGrid가 남는 폭을 flex로 나눠 갖는다. 창을 넓히면 컬럼도
    넓어진다. 정적 HTML 표에는 그 기능이 없으므로 같은 규칙을 문서 안의
    코드로 다시 만들고, 값은 `grid`에서 그대로 가져온다.

    표가 둘 이상일 수 있으므로 표 id를 키로 담는다.
    """
    layouts: dict[str, list[dict]] = {}
    for tab in tab_registry.TABS:
        if tab.table is None:
            continue
        columns = tab.table.columns
        widths = grid.table_widths(columns)
        minimums = grid.table_min_widths(columns)
        flexes = grid.table_flex(columns)
        layouts[tab.table.table_id(tab.value)] = [
            {
                "width": widths[column.field],
                "min": minimums[column.field],
                "flex": flexes[column.field],
            }
            for column in columns
        ]
    return json.dumps(layouts, ensure_ascii=False)


_BEHAVIOUR_JS = """
(function () {
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

      var id = root.getAttribute('data-chart');
      var figure =
        (CHART_VARIANTS[id] || {})[option.getAttribute('data-value')];
      if (!figure) { return; }
      Plotly.react(id, figure.data, figure.layout, CHART_CONFIGS[id]);
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

  Array.prototype.forEach.call(heads, function (head) {
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
"""


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else None
    written = write_html(target)
    size_mb = written.stat().st_size / 1024 / 1024
    print(f"만들었습니다: {written}")
    print(f"크기: {size_mb:.1f} MB (Plotly.js 포함)")
