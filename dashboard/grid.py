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
from dashboard.data import TOTAL_LABEL
from dashboard.metrics import TABLE_COLUMNS

EMPTY_TEXT = "-"

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

# (field, 표시할 컬럼명, valueFormatter, 최소 너비)
_COLUMN_SPECS: tuple[tuple[str, str, str | None, int], ...] = (
    ("branch_name", "지점명", None, 120),
    ("customer_count", "고객 수", _COUNT_FORMAT, 130),
    (
        "customer_growth_yoy",
        "고객 수 증가율(YoY)",
        _SIGNED_PERCENT_FORMAT,
        160,
    ),
    ("male_share", "남성(%)", _PERCENT_FORMAT, 110),
    ("average_age", "평균 연령", _AGE_FORMAT, 120),
    ("recent_signup_share", "최근 가입 비중(%)", _PERCENT_FORMAT, 150),
    ("recommendation_share", "투자권유 희망(%)", _PERCENT_FORMAT, 150),
    ("grade_s_share", "고객등급 S 이상(%)", _PERCENT_FORMAT, 160),
)

DEFAULT_COL_DEF = {
    "sortable": True,
    "resizable": True,
    "suppressMovable": True,
    "headerClass": "grid-header",
    "flex": 1,
}

GRID_OPTIONS = {
    "headerHeight": 44,
    "rowHeight": 38,
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
    for field, header_name, value_formatter, min_width in _COLUMN_SPECS:
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
        if field == "customer_growth_yoy":
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
