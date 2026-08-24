"""원본 파일 — 해외주식 비중 구간별 수익률.

기준월·지점·해외주식 잔고 비중 구간마다 한 행이고 그 행에 1년·3년 수익률이
붙어 있다. 국내주식·ETF·개인연금 비중 원본과 같은 모양이라 조립은 함께
쓴다(→ dashboard/sources/segment_return.py).

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
#   FILE = "수익률_seg_해외주식비중.pkl"
#       → data/수익률_seg_해외주식비중.pkl
# 환경 변수를 지정하면 아래 값보다 환경 변수가 우선한다.
FILE = "수익률_seg_해외주식비중.pkl"
FILE_ENV = "DASHBOARD_OVERSEAS_SHARE_RETURN_FILE"

LABEL = "해외주식비중별 수익률"

# 가르는 축의 표준 컬럼 이름
# (→ data.OVERSEAS_SHARE_RETURN_COLUMNS).
GROUP_COLUMN = "overseas_share_group"

# 원본 컬럼명 → 내부 표준 컬럼명.
COLUMNS: dict[str, str] = {
    "기준월": "base_month",
    "CSMT_ORZ_CD": "branch_id",
    "CSMT_ORZ_NM": "branch_name",
    "해외주식잔고비중": GROUP_COLUMN,
    "수익률_1년": "return_1y",
    "수익률_3년": "return_3y",
}


def build(frame: pd.DataFrame) -> pd.DataFrame:
    """표준 이름으로 바뀐 원본에서 해외주식비중별 수익률 프레임을 만든다."""
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
