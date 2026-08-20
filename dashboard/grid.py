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
# 단위를 붙이지 않는 숫자(순번 등). 오른쪽 정렬과 정렬 기준은 숫자 컬럼과
# 같게 두고 글자만 그대로 적는다.
NUMBER_FORMAT = _NULL_CHECK + 'd3.format(",")(params.value)'
# 부호가 붙는 정수(순위변동 등). 0에는 부호를 붙이지 않는다. `+0`은
# '조금 올랐다'로 읽히지만 실제로는 '그대로'라는 뜻이다
# (→ format.format_signed_number).
SIGNED_NUMBER_FORMAT = (
    _NULL_CHECK
    + 'params.value == 0 ? "0" : '
    + 'd3.format("+,")(params.value).replace("−", "-")'
)
# 순위변동 중 빈 칸이 '앞 달에 없던 종목'을 뜻하는 표. 그 자리를 `-`가
# 아니라 NEW로 적는다(→ format.format_rank_change).
RANK_CHANGE_FORMAT = (
    f'params.value == null ? "{fmt.NEW_ENTRY_TEXT}" : '
    + 'params.value == 0 ? "0" : '
    + 'd3.format("+,")(params.value).replace("−", "-")'
)
SIGNED_PERCENT_FORMAT = (
    _NULL_CHECK
    + 'd3.format("+,.1f")(params.value).replace("−", "-") + "%"'
)
PERCENT_FORMAT = _NULL_CHECK + 'd3.format(",.1f")(params.value) + "%"'
AGE_FORMAT = _NULL_CHECK + 'd3.format(",.1f")(params.value) + "세"'

# 금액 컬럼. 표시 문구를 파이썬이 만들어 행 데이터에 함께 담고, 표현식은
# 그 문구를 그대로 읽기만 한다.
#
# 금액은 조·억·만으로 접어 적는데(→ format.format_won), 표현식에 쓸 수 있는
# 것은 `params`와 `d3`뿐이라 그 계산을 담을 수 없다. 덤으로, 화면과 정적
# HTML이 같은 파이썬 함수의 결과를 쓰게 되어 반올림 자리에서 글자가 갈리는
# 일도 없어진다.
MONEY_FORMAT = "__row_text__"
TEXT_SUFFIX = "__text"


def _text_expression(field: str) -> str:
    """행 데이터에 담아 둔 문구를 그대로 읽는 valueFormatter 표현식."""
    key = f"{field}{TEXT_SUFFIX}"
    return (
        f'params.data == null ? "{EMPTY_TEXT}" : '
        f'(params.data.{key} == null ? "{EMPTY_TEXT}"'
        f' : params.data.{key})'
    )

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

    `flex`는 남는 폭을 나눠 갖는 몫이다. 기본은 모두 같은 몫(1)이며, 글이
    긴 컬럼에 큰 값을 주면 그만큼 넓어진다. 0이면 나눔에서 빠지고 `width`를
    지킨다.
    """

    field: str
    header: str
    min_width: int
    to_text: Callable[[object], str]
    js_format: str | None = None
    width: int | None = None
    pinned: bool = False
    growth: bool = False
    flex: int = 1

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

# 행 클릭 강조. 컬럼이 많아 옆으로 훑을 때 어느 지점의 줄을 보고 있는지
# 놓치지 않게 한다. 체크박스 컬럼은 넣지 않고 클릭으로만 고르며, 고른 행을
# 다시 누르면 풀린다. 한 번에 한 행만 남긴다.
#
# ag-grid 32.2부터 rowSelection은 문자열("single")이 아니라 이 dict 형태다.
# 상단에 고정한 '전체' 행은 행 모델 밖이라 고를 수 없다.
# 정적 HTML 표도 같은 동작을 문서 안의 코드로 다시 만든다(→ export_html).
#
# enableSelectionWithoutKeys를 함께 켜야 고른 행을 다시 눌렀을 때 풀린다.
# enableClickSelection만 켜면 ag-grid는 그 클릭을 "같은 행을 다시 고름"으로
# 보고 강조를 그대로 둔다. 해제는 Ctrl+클릭에서만 일어난다. 이름은 여러 행
# 고르기(multiRow)에서 온 것이지만, 한 행만 고르는 여기서는 다시 누르면
# 풀리게 하는 효과만 있다.
ROW_SELECTION = {
    "mode": "singleRow",
    "checkboxes": False,
    "enableClickSelection": True,
    "enableSelectionWithoutKeys": True,
}

GRID_OPTIONS = {
    "headerHeight": HEADER_HEIGHT,
    "rowHeight": ROW_HEIGHT,
    "suppressCellFocus": True,
    "suppressDragLeaveHidesColumns": True,
    "domLayout": "normal",
    "rowSelection": ROW_SELECTION,
    "localeText": {"noRowsToShow": "표시할 데이터가 없습니다"},
}


def build_column_defs(
    columns: tuple[Column, ...], sortable: bool = True
) -> list[dict]:
    """컬럼 정의.

    고정 컬럼은 왼쪽에 붙인다. 컬럼이 많아 가로 스크롤이 생겨도 어느 행의
    값인지 보여야 한다.

    `sortable`을 끄면 헤더를 눌러도 다시 세우지 않는다. 행 순서 자체가
    뜻을 갖는 표에 쓴다. colDef가 `DEFAULT_COL_DEF`보다 나중에 적용되므로
    여기서 끈 값이 이긴다.

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
        if not sortable:
            defined["sortable"] = False
        if column.numeric:
            defined["valueFormatter"] = {
                "function": (
                    _text_expression(column.field)
                    if column.js_format == MONEY_FORMAT
                    else column.js_format
                )
            }
            defined["cellClass"] = "grid-cell-number"
        else:
            defined["cellClass"] = "grid-cell-text"
        if column.growth:
            defined["cellStyle"] = _GROWTH_STYLE
        if column.flex != DEFAULT_COL_DEF["flex"]:
            defined["flex"] = column.flex
            if column.flex == 0:
                # 나눔에서 빠지는 컬럼은 너비를 직접 준다.
                defined["width"] = column.width or column.min_width
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
    문서 안의 코드가 같은 규칙으로 나눠 준다. 고정 컬럼은 나눔에서 빠지고,
    나머지는 선언한 몫을 그대로 쓴다(→ export_html).
    """
    return {
        column.field: (0 if column.pinned else column.flex)
        for column in columns
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
            # 값이 없을 때 무엇을 적을지는 컬럼 선언이 정한다. 숫자 컬럼의
            # 표기 함수는 빈 값을 스스로 처리하므로 그대로 부른다 — 순위변동
            # 처럼 빈 칸에 `-`가 아닌 글을 적는 컬럼이 있다
            # (→ format.format_rank_change). 글 컬럼의 함수(`str` 등)는
            # 빈 값을 다루지 않으므로 여기서 `-`로 둔다.
            return column.to_text(value) if column.numeric else EMPTY_TEXT
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
# 금액 컬럼은 파이썬이 문구까지 만들어 담으므로 여기 넣지 않는다.
_INTEGER_FORMATS = (
    fmt.format_count,
    fmt.format_number,
    fmt.format_signed_number,
    fmt.format_rank_change,
)


def _clean_row(row: dict, columns: tuple[Column, ...]) -> dict:
    """NaN·inf를 None으로 바꿔 화면에서 `-`로 표시되게 한다.

    정수로 보여줄 컬럼인지는 값의 성격이 아니라 선언의 표기 함수로 정한다.

    금액 컬럼은 표시 문구도 함께 담는다. 셀에 들어가는 값은 숫자 그대로라
    정렬은 정확하고, 보이는 글자만 파이썬이 만든 것을 쓴다.
    """
    cleaned: dict = {}
    for column in columns:
        value = row.get(column.field)
        if isinstance(value, str) or value is None:
            cleaned[column.field] = value
        else:
            try:
                number = float(value)
            except (TypeError, ValueError):
                number = math.nan
            if math.isnan(number) or math.isinf(number):
                cleaned[column.field] = None
            elif column.to_text in _INTEGER_FORMATS:
                cleaned[column.field] = int(round(number))
            elif column.js_format == MONEY_FORMAT:
                # 금액은 d3를 거치지 않으므로 자리를 깎지 않는다. 백만원
                # 단위 값을 소수 첫째 자리로 접으면 만원 자리가 사라진다.
                cleaned[column.field] = number
            else:
                cleaned[column.field] = round(number, 1)
        if column.js_format == MONEY_FORMAT:
            stored = cleaned[column.field]
            cleaned[f"{column.field}{TEXT_SUFFIX}"] = (
                None if stored is None else column.to_text(stored)
            )
    return cleaned


def build_grid_options(
    total_row: dict | None,
    columns: tuple[Column, ...],
    auto_height: bool = False,
) -> dict:
    """전체 행 고정을 포함한 그리드 옵션.

    `auto_height`를 켜면 표 높이를 행 수에 맞춘다. 행이 늘 몇 개뿐인 표는
    고정 높이를 주면 아래가 빈 채로 남는다.
    """
    options = dict(GRID_OPTIONS)
    options["pinnedTopRowData"] = build_pinned_top_row(total_row, columns)
    if auto_height:
        options["domLayout"] = "autoHeight"
    return options


def total_row_label() -> str:
    return TOTAL_LABEL
