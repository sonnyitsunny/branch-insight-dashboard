"""원본 파일 — 상품 분류별 전월 대비 증감율.

앞선 원본들과 형태가 다르다. **월이 가로로 펼쳐져 있다.** `202508`~`202607`
열마다 그 달의 전월 대비 증감율이 들어 있어, 한 줄에 한 시점인 표준 형태로
편다.

상품 분류는 '상품분류' 컬럼이 이름으로 갖고 있다. 행 순서에 기대지 않으므로
원본의 행이 뒤섞이거나 일부 분류가 빠져도 값이 밀리지 않는다. 대신 이름이
`dashboard.data.ALL_ASSET_TYPES`에 없으면 무엇이 낯선 값인지 알리며 멈춘다.

원본 컬럼 이름이 바뀌면 이 파일의 표만 고친다(→ AGENTS.md §9).
"""

from __future__ import annotations

import pandas as pd

from dashboard.data import ALL_ASSET_TYPES, plain_text, to_month_column

# 실제 데이터를 붙일 때 여기만 고치면 된다.
#
# 파일 이름만 적으면 app.py 옆의 `data/` 폴더에서 찾는다.
#   FILE = "자산3.pkl"              → data/자산3.pkl
# 환경 변수를 지정하면 아래 값보다 환경 변수가 우선한다.
FILE = "자산3.pkl"
FILE_ENV = "DASHBOARD_ASSET3_FILE"

LABEL = "지점 자산3"

# 원본 컬럼명 → 내부 표준 컬럼명.
# 월 열은 이름이 곧 기준 월이라 여기 적지 않는다. 아래 `month_columns`가
# 아래 키 컬럼이 아닌 나머지를 월로 읽는다.
COLUMNS: dict[str, str] = {
    "CSMT_ORZ_CD": "branch_id",
    "CSMT_ORZ_NM": "branch_name",
    "상품분류": "asset_type",
}

# 값이 들어갈 표준 컬럼. 원본이 이미 %로 담고 있어 그대로 쓴다.
VALUE_COLUMN = "change_rate"

_KEY_COLUMNS = ("branch_id", "branch_name", "asset_type")


def month_columns(frame: pd.DataFrame) -> list[str]:
    """월 열 목록. 지점 컬럼이 아닌 나머지를 월로 본다."""
    found = [
        column for column in frame.columns if column not in _KEY_COLUMNS
    ]
    if not found:
        raise ValueError(
            f"{LABEL} 파일에 월 열이 없습니다. "
            f"찾은 컬럼: {', '.join(map(str, frame.columns))}"
        )
    return found


def build(frame: pd.DataFrame) -> pd.DataFrame:
    """표준 이름으로 바뀐 원본을 한 줄에 한 시점인 형태로 편다.

    되돌려주는 컬럼은 base_month·branch_id·branch_name·asset_type·
    change_rate 다섯 개다.
    """
    months = month_columns(frame)
    checked = _checked_asset_types(frame)
    long = checked.melt(
        id_vars=list(_KEY_COLUMNS),
        value_vars=months,
        var_name="base_month",
        value_name=VALUE_COLUMN,
    )
    long["base_month"] = to_month_column(long["base_month"], "asset3")
    return long


def _checked_asset_types(frame: pd.DataFrame) -> pd.DataFrame:
    """상품 분류 값이 쓸 수 있는 이름인지, 한 지점에 한 번씩인지 확인한다.

    낯선 이름은 코드표에 없으니 화면에서 조용히 사라진다. 어떤 값이
    문제인지 알리며 멈춘다.

    같은 지점에 같은 분류가 두 번 있으면 어느 값이 맞는지 알 수 없으므로
    역시 멈춘다. 반대로 일부 분류가 빠진 것은 막지 않는다. 이름이 붙어
    있어 값이 밀리지 않고, 없는 값은 화면에서 빈 칸으로 나타난다.
    """
    checked = frame.copy()
    checked["asset_type"] = plain_text(checked["asset_type"])

    unknown = sorted(set(checked["asset_type"]) - set(ALL_ASSET_TYPES))
    if unknown:
        raise ValueError(
            f"{LABEL} 파일의 '상품분류'에 쓸 수 없는 값이 있습니다: "
            f"{', '.join(unknown[:5])}. "
            f"사용할 수 있는 값: {', '.join(ALL_ASSET_TYPES)}. "
            "원본의 분류 이름이 바뀌었으면 dashboard/data.py 의 "
            "ASSET_TYPES 를 고쳐 주세요."
        )

    keys = pd.MultiIndex.from_arrays(
        [plain_text(checked["branch_id"]), checked["asset_type"]]
    )
    duplicated = keys.duplicated()
    if duplicated.any():
        branch_id, asset_type = keys[duplicated][0]
        raise ValueError(
            f"{LABEL} 파일에 같은 지점의 같은 상품분류가 두 번 이상 "
            f"있습니다: 지점 {branch_id} {asset_type}. "
            "한 지점의 한 분류는 한 행이어야 합니다."
        )
    return checked
