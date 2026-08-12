"""dash-ag-grid 설정.

`columnDefs`와 `rowData` 생성을 분리한다. 값은 정렬이 정확하도록 숫자로 넣고
표시 형식은 dash-ag-grid의 선언형 `valueFormatter`(dict 형식)로 처리한다.
dict 형식은 라이브러리 내부의 제한된 표현식 평가기가 처리하므로
`dangerously_allow_code`를 켜지 않으며, 외부 JavaScript도 넣지 않는다.

여기에는 어느 표에나 쓰는 일반 함수만 둔다. 어떤 컬럼을 보여줄지는 탭이
`Column` 목록으로 선언한다(→ dashboard.tabs). 표가 둘 이상이 되어도 이
파일은 커지지 않는다.

정적 HTML 테이블에서도 쓸 공통 표시 규칙은 `dashboard.format`에 있다.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable

import pandas as pd

from dashboard import figures
from dashboard import format as fmt
from dashboard.data import TOTAL_LABEL

EMPTY_TEXT = fmt.EMPTY_TEXT

# valueFormatter 표현식. params.value가 없으면 "-"로 표시한다.
# d3는 음수에 유니코드 마이너스(U+2212)를 쓰므로 일반 하이픈으로 바꿔
# dashboard.format의 표기와 일치시킨다.
_NULL_CHECK = f'params.value == null ? "{EMPTY_TEXT}" : '
COUNT_FORMAT = _NULL_CHECK + 'd3.format(",")(params.value) + "명"'
SIGNED_PERCENT_FORMAT = (
    _NULL_CHECK
    + 'd3.format("+,.1f")(params.value).replace("−", "-") + "%"'
)
PERCENT_FORMAT = _NULL_CHECK + 'd3.format(",.1f")(params.value) + "%"'
AGE_FORMAT = _NULL_CHECK + 'd3.format(",.1f")(params.value) + "세"'
# 자산 표기. `dashboard.format`의 같은 이름 함수와 규칙을 맞춘다.
ASSETS_FORMAT = _NULL_CHECK + 'd3.format(",.0f")(params.value) + "억원"'
MILLION_FORMAT = _NULL_CHECK + 'd3.format(",.1f")(params.value) + "백만원"'

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


@dataclass(frozen=True)
class Column:
    """표 컬럼 하나의 선언.

    화면의 AgGrid와 정적 HTML 표가 같은 선언을 읽는다. 컬럼 순서·표기·색을
    두 곳에 적지 않으므로 두 산출물이 어긋나지 않는다.

    `js_format`은 AgGrid의 valueFormatter 표현식, `to_text`는 정적 HTML용
    파이썬 함수다. 서식 규칙 자체는 `dashboard.format` 한 곳에 있다.
    `js_format`이 없으면 문자 컬럼으로 보고 왼쪽에 붙인다.

    `pinned`를 켜면 왼쪽에 고정한다. 고정 컬럼은 남는 폭을 나눠 갖지
    않으므로 `width`를 함께 준다. 좁으면 값이 말줄임(…)으로 잘린다.
    `growth`를 켜면 값의 부호에 따라 증감 색을 입힌다.
    """

    field: str
    header: str
    min_width: int
    to_text: Callable[[object], str]
    js_format: str | None = None
    width: int | None = None
    pinned: bool = False
    growth: bool = False

    @property
    def numeric(self) -> bool:
        return self.js_format is not None


# 헤더·행 높이(px). 정적 HTML 표도 같은 값을 써야 행 높이와 '전체' 행이
# 붙는 위치가 화면과 어긋나지 않는다(→ export_html).
HEADER_HEIGHT = 44
ROW_HEIGHT = 38

DEFAULT_COL_DEF = {
    "sortable": True,
    "resizable": True,
    "suppressMovable": True,
    "headerClass": "grid-header",
    "flex": 1,
}

GRID_OPTIONS = {
    "headerHeight": HEADER_HEIGHT,
    "rowHeight": ROW_HEIGHT,
    "suppressCellFocus": True,
    "suppressDragLeaveHidesColumns": True,
    "domLayout": "normal",
    "localeText": {"noRowsToShow": "표시할 데이터가 없습니다"},
}


def build_column_defs(columns: tuple[Column, ...]) -> list[dict]:
    """컬럼 정의.

    고정 컬럼은 왼쪽에 붙인다. 컬럼이 많아 가로 스크롤이 생겨도 어느 행의
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
    for column in columns:
        defined: dict = {
            "field": column.field,
            "headerName": column.header,
            "minWidth": column.min_width,
        }
        if column.numeric:
            defined["valueFormatter"] = {"function": column.js_format}
            defined["cellClass"] = "grid-cell-number"
        else:
            defined["cellClass"] = "grid-cell-text"
        if column.growth:
            defined["cellStyle"] = _GROWTH_STYLE
        if column.pinned:
            # 고정 컬럼은 flex 계산에서 빠지므로 너비를 직접 준다.
            # flex를 남겨 두면 너비가 0으로 접힌다.
            defined["pinned"] = "left"
            defined["flex"] = 0
            defined["width"] = column.width or column.min_width
            defined["lockPosition"] = True
        column_defs.append(defined)
    return column_defs


def table_headers(columns: tuple[Column, ...]) -> list[tuple[str, str]]:
    """(field, 표시할 컬럼명) 목록. 정적 HTML 표가 컬럼 순서를 맞출 때 쓴다."""
    return [(column.field, column.header) for column in columns]


def table_widths(columns: tuple[Column, ...]) -> dict[str, int]:
    """컬럼별 시작 너비(px).

    Dash는 남는 폭을 flex로 나눠 갖지만 정적 HTML 표에는 그 기능이 없다.
    같은 값에서 시작하도록 여기서 한 번만 정한다.
    """
    return {
        column.field: (column.width or column.min_width)
        for column in columns
    }


def table_min_widths(columns: tuple[Column, ...]) -> dict[str, int]:
    """컬럼별 최소 너비(px). 화면 columnDefs의 `minWidth`와 같은 값이다."""
    return {column.field: column.min_width for column in columns}


def table_flex(columns: tuple[Column, ...]) -> dict[str, int]:
    """컬럼별 flex 값.

    화면은 남는 폭을 flex로 나눠 갖는다. 정적 HTML 표에는 그 기능이 없어
    문서 안의 코드가 같은 규칙으로 나눠 준다. 고정 컬럼만 0이고 나머지는
    `DEFAULT_COL_DEF`의 값을 그대로 쓴다(→ export_html).
    """
    default = DEFAULT_COL_DEF["flex"]
    return {
        column.field: (0 if column.pinned else default) for column in columns
    }


def growth_fields(columns: tuple[Column, ...]) -> tuple[str, ...]:
    """증감 색을 입히는 컬럼. 정적 HTML 표도 같은 컬럼에 같은 색을 쓴다."""
    return tuple(column.field for column in columns if column.growth)


def pinned_field(columns: tuple[Column, ...]) -> str | None:
    """왼쪽에 고정하는 컬럼. 없으면 None."""
    for column in columns:
        if column.pinned:
            return column.field
    return None


def format_cell(
    columns: tuple[Column, ...], field: str, value: object
) -> str:
    """정적 HTML 표의 셀 문구.

    Dash 화면은 브라우저에서 d3로, 정적 HTML은 여기서 파이썬으로 서식을
    입힌다. 서식 규칙 자체는 `dashboard.format` 한 곳에 있으므로 두 산출물의
    숫자 표기가 같다.
    """
    for column in columns:
        if column.field != field:
            continue
        if value is None:
            return EMPTY_TEXT
        return column.to_text(value)
    return EMPTY_TEXT


def build_row_data(
    rows: pd.DataFrame, columns: tuple[Column, ...]
) -> list[dict]:
    """행 데이터. 값은 숫자 그대로 넣어 정렬이 정확하게 동작하게 한다."""
    if rows.empty:
        return []
    return [
        _clean_row(row, columns)
        for row in rows.to_dict(orient="records")
    ]


def build_pinned_top_row(
    total_row: dict | None, columns: tuple[Column, ...]
) -> list[dict]:
    """전체 행. 상단에 고정되어 정렬해도 움직이지 않는다."""
    if not total_row:
        return []
    return [_clean_row(total_row, columns)]


# 정수로 보여주는 컬럼의 표기 함수. 화면에 소수점이 없으면 값도 정수로
# 담는다. 소수를 남겨 두면 .5에서 AgGrid(d3, 0에서 먼 쪽으로 반올림)와 정적
# HTML(파이썬, 짝수 쪽으로 반올림)의 결과가 1 차이로 갈린다.
_INTEGER_FORMATS = (fmt.format_count, fmt.format_assets_plain)


def _clean_row(row: dict, columns: tuple[Column, ...]) -> dict:
    """NaN·inf를 None으로 바꿔 화면에서 `-`로 표시되게 한다.

    정수로 보여줄 컬럼인지는 값의 성격이 아니라 선언의 표기 함수로 정한다.
    """
    cleaned: dict = {}
    for column in columns:
        value = row.get(column.field)
        if isinstance(value, str) or value is None:
            cleaned[column.field] = value
            continue
        try:
            number = float(value)
        except (TypeError, ValueError):
            cleaned[column.field] = None
            continue
        if math.isnan(number) or math.isinf(number):
            cleaned[column.field] = None
        elif column.to_text in _INTEGER_FORMATS:
            cleaned[column.field] = int(round(number))
        else:
            cleaned[column.field] = round(number, 1)
    return cleaned


def build_grid_options(
    total_row: dict | None, columns: tuple[Column, ...]
) -> dict:
    """전체 행 고정을 포함한 그리드 옵션."""
    options = dict(GRID_OPTIONS)
    options["pinnedTopRowData"] = build_pinned_top_row(total_row, columns)
    return options


def total_row_label() -> str:
    return TOTAL_LABEL
