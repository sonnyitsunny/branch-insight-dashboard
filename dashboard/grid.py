"""dash-ag-grid 설정.

`columnDefs`와 `rowData` 생성을 분리한다. 값은 정렬이 정확하도록 숫자로 넣고
표시 형식은 dash-ag-grid의 선언형 `valueFormatter`(dict 형식)로 처리한다.
dict 형식은 라이브러리 내부의 제한된 표현식 평가기가 처리하므로
`dangerously_allow_code`를 켜지 않으며, 외부 JavaScript도 넣지 않는다.

정적 HTML 테이블에서도 쓸 공통 표시 규칙은 `dashboard.format`에 있다.
"""

from __future__ import annotations

import math

import pandas as pd

from dashboard import figures
from dashboard import format as fmt
from dashboard.data import TOTAL_LABEL
from dashboard.metrics import TABLE_COLUMNS

EMPTY_TEXT = fmt.EMPTY_TEXT

# valueFormatter 표현식. params.value가 없으면 "-"로 표시한다.
# d3는 음수에 유니코드 마이너스(U+2212)를 쓰므로 일반 하이픈으로 바꿔
# dashboard.format의 표기와 일치시킨다.
_NULL_CHECK = f'params.value == null ? "{EMPTY_TEXT}" : '
_COUNT_FORMAT = _NULL_CHECK + 'd3.format(",")(params.value) + "명"'
_SIGNED_PERCENT_FORMAT = (
    _NULL_CHECK
    + 'd3.format("+,.1f")(params.value).replace("−", "-") + "%"'
)
_PERCENT_FORMAT = _NULL_CHECK + 'd3.format(",.1f")(params.value) + "%"'
_AGE_FORMAT = _NULL_CHECK + 'd3.format(",.1f")(params.value) + "세"'

# 증감 색상을 입히는 컬럼. 정적 HTML 표도 같은 컬럼에 같은 색을 쓴다.
GROWTH_FIELD = "customer_growth_yoy"

# 증감 색상. 값의 부호가 서식(+/-)에도 함께 나타나므로 색상만으로 구분하지
# 않는다.
_GROWTH_STYLE = {
    "styleConditions": [
        {
            "condition": "params.value > 0",
            "style": {"color": figures.COLOR_UP},
        },
        {
            "condition": "params.value < 0",
            "style": {"color": figures.COLOR_DOWN},
        },
    ],
    "defaultStyle": {"color": figures.COLOR_TEXT},
}

# 왼쪽에 고정할 컬럼. 가로 스크롤을 해도 어느 지점의 값인지 보이게 한다.
PINNED_FIELD = "branch_name"
# 고정 컬럼은 남는 폭을 나눠 갖지 않으므로 폭을 직접 정한다. 좁으면 지점명이
# 말줄임(…)으로 잘린다. 고정하기 전 flex로 늘어나던 폭이 약 183px이었고,
# 경계선(style.css의 --ag-pinned-column-border)이 셀에서 1px를 가져가므로
# 여유를 더해 잡았다. 지점명이 길어 잘리면 이 값만 키우면 된다.
PINNED_WIDTH = 192

# (field, 표시할 컬럼명, valueFormatter, 최소 너비, 정적 HTML용 포맷 함수)
# 마지막 항목은 Dash가 아니라 정적 HTML 표가 쓴다. 두 산출물이 같은 컬럼
# 순서와 같은 표기를 갖도록 여기 한 곳에서만 정한다(→ export_html).
_COLUMN_SPECS: tuple[tuple[str, str, str | None, int, object], ...] = (
    ("branch_name", "지점명", None, 120, str),
    ("customer_count", "고객 수", _COUNT_FORMAT, 130, fmt.format_count),
    (
        "customer_growth_yoy",
        "고객 수 증가율(YoY)",
        _SIGNED_PERCENT_FORMAT,
        160,
        fmt.format_signed_percent,
    ),
    ("male_share", "남성(%)", _PERCENT_FORMAT, 110, fmt.format_percent),
    ("average_age", "평균 연령", _AGE_FORMAT, 120, fmt.format_age),
    (
        "recent_signup_share",
        "최근 가입 비중(%)",
        _PERCENT_FORMAT,
        150,
        fmt.format_percent,
    ),
    (
        "recommendation_share",
        "투자권유 희망(%)",
        _PERCENT_FORMAT,
        150,
        fmt.format_percent,
    ),
    (
        "grade_s_share",
        "고객등급 S 이상(%)",
        _PERCENT_FORMAT,
        160,
        fmt.format_percent,
    ),
)

DEFAULT_COL_DEF = {
    "sortable": True,
    "resizable": True,
    "suppressMovable": True,
    "headerClass": "grid-header",
    "flex": 1,
}

# 헤더·행 높이(px). 정적 HTML 표도 같은 값을 써야 행 높이와 '전체' 행이
# 붙는 위치가 화면과 어긋나지 않는다(→ export_html).
HEADER_HEIGHT = 44
ROW_HEIGHT = 38

GRID_OPTIONS = {
    "headerHeight": HEADER_HEIGHT,
    "rowHeight": ROW_HEIGHT,
    "suppressCellFocus": True,
    "suppressDragLeaveHidesColumns": True,
    "domLayout": "normal",
    "localeText": {"noRowsToShow": "표시할 데이터가 없습니다"},
}


def build_column_defs() -> list[dict]:
    """컬럼 정의.

    지점명은 왼쪽에 고정한다. 컬럼이 많아 가로 스크롤이 생겨도 어느 지점의
    값인지 보여야 한다.

    정렬은 `cellClass`·`headerClass`와 CSS로만 정한다. ag-grid의
    `type: "rightAligned"`는 쓰지 않는다. 그 타입은 `headerClass`와
    `cellClass`를 직접 채워 넣는데, 적용 순서가
    defaultColDef → 타입 → colDef라서
    타입의 `headerClass`가 `DEFAULT_COL_DEF`의 `grid-header`를 지우고,
    colDef의 `cellClass`가 다시 타입의 오른쪽 정렬 클래스를 지운다.
    결과적으로 헤더만 오른쪽으로 가고 셀은 왼쪽에 남는다.
    """
    column_defs: list[dict] = []
    for field, header_name, value_formatter, min_width, _text in _COLUMN_SPECS:
        column: dict = {
            "field": field,
            "headerName": header_name,
            "minWidth": min_width,
        }
        if value_formatter is None:
            column["cellClass"] = "grid-cell-text"
        else:
            column["valueFormatter"] = {"function": value_formatter}
            column["cellClass"] = "grid-cell-number"
        if field == GROWTH_FIELD:
            column["cellStyle"] = _GROWTH_STYLE
        if field == PINNED_FIELD:
            # 고정 컬럼은 flex 계산에서 빠지므로 너비를 직접 준다.
            # flex를 남겨 두면 너비가 0으로 접힌다.
            column["pinned"] = "left"
            column["flex"] = 0
            column["width"] = PINNED_WIDTH
            column["lockPosition"] = True
        column_defs.append(column)
    return column_defs


def table_headers() -> list[tuple[str, str]]:
    """(field, 표시할 컬럼명) 목록. 정적 HTML 표가 컬럼 순서를 맞출 때 쓴다."""
    return [(field, header) for field, header, _js, _w, _text in _COLUMN_SPECS]


def table_widths() -> dict[str, int]:
    """컬럼별 시작 너비(px).

    Dash는 남는 폭을 flex로 나눠 갖지만 정적 HTML 표에는 그 기능이 없다.
    같은 값에서 시작하도록 여기서 한 번만 정한다.
    """
    widths = {
        field: width for field, _h, _js, width, _text in _COLUMN_SPECS
    }
    widths[PINNED_FIELD] = PINNED_WIDTH
    return widths


def table_min_widths() -> dict[str, int]:
    """컬럼별 최소 너비(px). 화면 columnDefs의 `minWidth`와 같은 값이다."""
    return {field: width for field, _h, _js, width, _t in _COLUMN_SPECS}


def table_flex() -> dict[str, int]:
    """컬럼별 flex 값.

    화면은 남는 폭을 flex로 나눠 갖는다. 정적 HTML 표에는 그 기능이 없어
    문서 안의 코드가 같은 규칙으로 나눠 준다. 고정 컬럼만 0이고 나머지는
    `DEFAULT_COL_DEF`의 값을 그대로 쓴다(→ export_html).
    """
    default = DEFAULT_COL_DEF["flex"]
    return {
        field: (0 if field == PINNED_FIELD else default)
        for field, _h, _js, _w, _t in _COLUMN_SPECS
    }


def format_cell(field: str, value: object) -> str:
    """정적 HTML 표의 셀 문구.

    Dash 화면은 브라우저에서 d3로, 정적 HTML은 여기서 파이썬으로 서식을
    입힌다. 서식 규칙 자체는 `dashboard.format` 한 곳에 있으므로 두 산출물의
    숫자 표기가 같다.
    """
    for spec_field, _header, _js, _width, to_text in _COLUMN_SPECS:
        if spec_field != field:
            continue
        if value is None:
            return EMPTY_TEXT
        return to_text(value)
    return EMPTY_TEXT


def build_row_data(branch_rows: pd.DataFrame) -> list[dict]:
    """지점별 rowData. 값은 숫자 그대로 넣어 정렬이 정확하게 동작하게 한다."""
    if branch_rows.empty:
        return []
    return [_clean_row(row) for row in branch_rows.to_dict(orient="records")]


def build_pinned_top_row(total_row: dict | None) -> list[dict]:
    """전체 행. 상단에 고정되어 정렬해도 움직이지 않는다."""
    if not total_row:
        return []
    return [_clean_row(total_row)]


def _clean_row(row: dict) -> dict:
    """NaN·inf를 None으로 바꿔 화면에서 `-`로 표시되게 한다."""
    cleaned: dict = {}
    for column in TABLE_COLUMNS:
        value = row.get(column)
        if isinstance(value, str) or value is None:
            cleaned[column] = value
            continue
        try:
            number = float(value)
        except (TypeError, ValueError):
            cleaned[column] = None
            continue
        if math.isnan(number) or math.isinf(number):
            cleaned[column] = None
        elif column == "customer_count":
            cleaned[column] = int(round(number))
        else:
            cleaned[column] = round(number, 1)
    return cleaned


def build_grid_options(total_row: dict | None) -> dict:
    """전체 행 고정을 포함한 그리드 옵션."""
    options = dict(GRID_OPTIONS)
    options["pinnedTopRowData"] = build_pinned_top_row(total_row)
    return options


def total_row_label() -> str:
    return TOTAL_LABEL
