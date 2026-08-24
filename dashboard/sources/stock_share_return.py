"""원본 파일 — 국내주식 비중 구간별 수익률.

기준월·지점·국내주식 잔고 비중 구간마다 한 행이고 그 행에 1년·3년 수익률이
붙어 있다. 해외주식·ETF·개인연금 비중 원본과 같은 모양이라 조립은 함께
쓴다(→ dashboard/sources/segment_return.py). 자산규모별 수익률
(→ dashboard/sources/asset_return.py)과는 가르는 축이 다르다. 저쪽은 얼마를
가진 고객인지로, 이쪽은 가진 자산 중 국내주식이 얼마를 차지하는지로 가른다.

원본 컬럼 이름이 바뀌면 이 파일의 표만 고친다. 다른 파일은 고치지
않는다(→ AGENTS.md §9).
"""

from __future__ import annotations

import pandas as pd

from dashboard.data import BALANCE_SHARE_GROUPS
from dashboard.sources import segment_return

# 실제 데이터를 붙일 때 여기만 고치면 된다.
#
# 파일 이름만 적으면 app.py 옆의 `data/` 폴더에서 찾는다.
#   FILE = "수익률_seg_국내주식비중.pkl"
#       → data/수익률_seg_국내주식비중.pkl
# 환경 변수를 지정하면 아래 값보다 환경 변수가 우선한다.
FILE = "수익률_seg_국내주식비중.pkl"
FILE_ENV = "DASHBOARD_STOCK_SHARE_RETURN_FILE"

LABEL = "국내주식비중별 수익률"

# 가르는 축의 표준 컬럼 이름. 네 원본이 같은 구간을 담고 있어도 파일이
# 따로 오므로 프레임도 컬럼도 따로 둔다(→ data.STOCK_SHARE_RETURN_COLUMNS).
GROUP_COLUMN = "stock_share_group"

# 원본 컬럼명 → 내부 표준 컬럼명.
#
# 수익률 두 컬럼은 다른 수익률 원본과 이름이 같지만 표를 함께 쓰지 않는다.
# 두 파일이 서로 다른 때에 컬럼 이름을 바꿀 수 있어야 한다(→ AGENTS.md §9).
COLUMNS: dict[str, str] = {
    "기준월": "base_month",
    "CSMT_ORZ_CD": "branch_id",
    "CSMT_ORZ_NM": "branch_name",
    "국내주식잔고비중": GROUP_COLUMN,
    "수익률_1년": "return_1y",
    "수익률_3년": "return_3y",
}


def build(frame: pd.DataFrame) -> pd.DataFrame:
    """표준 이름으로 바뀐 원본에서 국내주식비중별 수익률 프레임을 만든다."""
    return segment_return.build(
        frame,
        COLUMNS,
        LABEL,
        GROUP_COLUMN,
        BALANCE_SHARE_GROUPS,
        "BALANCE_SHARE_GROUPS",
    )


__all__ = [
    "COLUMNS",
    "FILE",
    "FILE_ENV",
    "GROUP_COLUMN",
    "LABEL",
    "build",
]
