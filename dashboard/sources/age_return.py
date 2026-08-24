"""원본 파일 — 연령대별 수익률.

기준월·지점·연령대마다 한 행이고 그 행에 1년·3년 수익률이 붙어 있다.
비중·회전율 구간별 수익률과 같은 모양이라 조립은 함께 쓴다
(→ dashboard/sources/segment_return.py).

**연령 구분이 지점 프로필과 다르다.** 이 원본은 10대이하부터 70대이상까지
일곱으로 가르고, 프로필의 연령 분포는 여섯이다(→ data.AGE_GROUPS). 두
축을 같은 것으로 다루면 60대 이상이 한 칸이 되었다 두 칸이 되었다 한다.
그래서 구간 목록도 컬럼 이름도 따로 둔다(→ data.RETURN_AGE_GROUPS,
data.AGE_RETURN_COLUMNS).

번호 — 이 원본은 구간 앞에 차례를 적지 않는다. 없으면 데이터 계층이
차례를 확인하지 않고 넘어가므로, 화면 차례는 `RETURN_AGE_GROUPS`에 적은
순서가 된다(→ data.to_ordered_label_column).

원본 컬럼 이름이 바뀌면 이 파일의 표만 고친다. 다른 파일은 고치지
않는다(→ AGENTS.md §9).
"""

from __future__ import annotations

import pandas as pd

from dashboard.data import RETURN_AGE_GROUPS
from dashboard.sources import segment_return

# 실제 데이터를 붙일 때 여기만 고치면 된다.
#
# 파일 이름만 적으면 app.py 옆의 `data/` 폴더에서 찾는다.
#   FILE = "수익률_seg_연령.pkl" → data/수익률_seg_연령.pkl
# 환경 변수를 지정하면 아래 값보다 환경 변수가 우선한다.
FILE = "수익률_seg_연령.pkl"
FILE_ENV = "DASHBOARD_AGE_RETURN_FILE"

LABEL = "연령대별 수익률"

# 가르는 축의 표준 컬럼 이름. 지점 프로필의 `age_group`과 구분이 달라
# 이름도 따로 쓴다(→ data.AGE_RETURN_COLUMNS).
GROUP_COLUMN = "return_age_group"

# 원본 컬럼명 → 내부 표준 컬럼명.
COLUMNS: dict[str, str] = {
    "기준월": "base_month",
    "CSMT_ORZ_CD": "branch_id",
    "CSMT_ORZ_NM": "branch_name",
    "연령대": GROUP_COLUMN,
    "수익률_1년": "return_1y",
    "수익률_3년": "return_3y",
}


def build(frame: pd.DataFrame) -> pd.DataFrame:
    """표준 이름으로 바뀐 원본에서 연령대별 수익률 프레임을 만든다."""
    return segment_return.build(
        frame,
        COLUMNS,
        LABEL,
        GROUP_COLUMN,
        RETURN_AGE_GROUPS,
        "RETURN_AGE_GROUPS",
    )


__all__ = [
    "COLUMNS",
    "FILE",
    "FILE_ENV",
    "GROUP_COLUMN",
    "LABEL",
    "build",
]
