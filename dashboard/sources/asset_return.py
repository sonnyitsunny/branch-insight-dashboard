"""원본 파일 — 자산 규모 구간별 수익률.

기준월·지점·자산 규모 구간마다 한 행이고 그 행에 1년·3년 수익률이 붙어
있다. 지점별 수익률(→ dashboard/sources/branch_return.py)에 자산 규모 축이
하나 더 붙은 모양이며, 단위·부호·빈 칸 규칙이 모두 같다.

지점 행 외에 '전체' 행도 같은 모양으로 들어 있으며, 데이터 계층이 그 행을
따로 떼어 둔다(→ dashboard/data.py).

자산그룹 — 원본은 `1)1백만 ~ 1천만`처럼 앞에 차례를 적어 담는다. 그 번호는
떼고 읽되, 차례가 화면 차례와 같은지는 확인한다. 공백만 다른 표기도 같은
구간으로 읽는다(→ data.to_ordered_label_column).

단위 — 수익률은 **%**다. 원본이 이미 %로 계산해 담고 있으므로 그대로
넘기고, 화면은 값에 `%`만 붙여 적는다. 손실이 난 기간에는 음수가 되며
0~100 범위 검사도 하지 않는다.

빈 칸 — 그 지점·구간에 고객이 없으면 수익률도 없다. 비운 채로 넘겨 화면에
`-`로 나타나게 하고 0으로 채우지 않는다. 0%는 '수익이 없었다'는 뜻이라
'값이 없다'와 다르다(→ AGENTS.md §9).

'전체' 행 — 지점 수익률의 평균이 아니라 따로 계산된 값이다. 수익률은 더할
수 없으므로 지점 합계와 대조하지 않는다.

원본 컬럼 이름이 바뀌면 이 파일의 표만 고친다. 다른 파일은 고치지
않는다(→ AGENTS.md §9).
"""

from __future__ import annotations

import pandas as pd

from dashboard.data import (
    ASSET_GROUPS,
    plain_text,
    to_month_column,
    to_optional_number_column,
    to_ordered_label_column,
)

# 실제 데이터를 붙일 때 여기만 고치면 된다.
#
# 파일 이름만 적으면 app.py 옆의 `data/` 폴더에서 찾는다.
#   FILE = "수익률_seg_자산규모.pkl" → data/수익률_seg_자산규모.pkl
# 환경 변수를 지정하면 아래 값보다 환경 변수가 우선한다.
FILE = "수익률_seg_자산규모.pkl"
FILE_ENV = "DASHBOARD_ASSET_RETURN_FILE"

LABEL = "자산규모별 수익률"

# 원본 컬럼명 → 내부 표준 컬럼명.
#
# 수익률 두 컬럼은 지점별 수익률 원본과 이름이 같지만 표를 함께 쓰지 않는다.
# 두 파일이 서로 다른 때에 컬럼 이름을 바꿀 수 있어야 한다(→ AGENTS.md §9).
COLUMNS: dict[str, str] = {
    "기준월": "base_month",
    "CSMT_ORZ_CD": "branch_id",
    "CSMT_ORZ_NM": "branch_name",
    "자산그룹": "asset_group",
    "수익률_1년": "return_1y",
    "수익률_3년": "return_3y",
}

# 수익률 컬럼 → 원본 컬럼 이름. 오류 문구에 원본 이름을 적어야 파일의
# 어디를 봐야 하는지 알 수 있다.
RATE_COLUMNS: dict[str, str] = {
    "return_1y": "수익률_1년",
    "return_3y": "수익률_3년",
}


def build(frame: pd.DataFrame) -> pd.DataFrame:
    """표준 이름으로 바뀐 원본에서 자산규모별 수익률 프레임을 만든다.

    되돌려주는 컬럼은 `COLUMNS`의 표준 이름 6개다.

    기준 월은 `202607`이든 `2026-07`이든 날짜든 읽어서 `YYYY-MM`으로 맞춘다.
    수익률 값은 고치지 않는다. 표기만 떼고 숫자로 읽는다.
    """
    asset = frame.loc[:, list(COLUMNS.values())].copy()
    asset["base_month"] = to_month_column(
        asset["base_month"], "asset_return"
    )
    asset["asset_group"] = to_ordered_label_column(
        asset["asset_group"],
        LABEL,
        "자산그룹",
        ASSET_GROUPS,
        "ASSET_GROUPS",
    )
    for column, label in RATE_COLUMNS.items():
        asset[column] = to_optional_number_column(
            asset[column],
            LABEL,
            label,
            "수익률은 %로 계산된 숫자여야 합니다.",
        )
    _check_keys(asset)
    return asset


def _check_keys(asset: pd.DataFrame) -> None:
    """한 지점의 한 구간이 한 번씩만 있는지 본다.

    두 번 있으면 어느 값이 맞는지 알 수 없고, 화면에는 그중 하나가 조용히
    골라져 나타난다.
    """
    keys = pd.MultiIndex.from_arrays(
        [
            asset["base_month"],
            plain_text(asset["branch_id"]),
            asset["asset_group"],
        ]
    )
    duplicated = keys.duplicated()
    if duplicated.any():
        month, branch_id, group = keys[duplicated][0]
        raise ValueError(
            f"{LABEL} 파일에 같은 지점·자산그룹이 두 번 이상 있습니다: "
            f"{month} 지점 {branch_id} {group}. "
            "한 구간은 한 번만 있어야 합니다."
        )


__all__ = [
    "COLUMNS",
    "FILE",
    "FILE_ENV",
    "LABEL",
    "RATE_COLUMNS",
    "build",
]
