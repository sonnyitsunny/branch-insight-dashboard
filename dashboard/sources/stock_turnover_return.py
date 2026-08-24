"""원본 파일 — 국내주식 회전율 구간별 수익률.

기준월·지점·국내주식 회전율 구간마다 한 행이고 그 행에 1년·3년 수익률이
붙어 있다. 비중 구간별 수익률과 같은 모양이라 조립은 함께 쓴다
(→ dashboard/sources/segment_return.py). 가르는 기준만 다르다. 저쪽은
무엇을 얼마나 담고 있는지로, 이쪽은 얼마나 자주 사고파는지로 가른다.

구간 목록은 비중 원본과 다르다. 0%부터 시작해 100%이상까지 다섯이다
(→ data.STOCK_TURNOVER_GROUPS).

원본 컬럼 이름이 바뀌면 이 파일의 표만 고친다. 다른 파일은 고치지
않는다(→ AGENTS.md §9).
"""

from __future__ import annotations

import pandas as pd

from dashboard.data import STOCK_TURNOVER_GROUPS
from dashboard.sources import segment_return

# 실제 데이터를 붙일 때 여기만 고치면 된다.
#
# 파일 이름만 적으면 app.py 옆의 `data/` 폴더에서 찾는다.
#   FILE = "수익률_seg_국내주식회전율.pkl"
#       → data/수익률_seg_국내주식회전율.pkl
# 환경 변수를 지정하면 아래 값보다 환경 변수가 우선한다.
FILE = "수익률_seg_국내주식회전율.pkl"
FILE_ENV = "DASHBOARD_STOCK_TURNOVER_RETURN_FILE"

LABEL = "국내주식회전율별 수익률"

# 가르는 축의 표준 컬럼 이름
# (→ data.STOCK_TURNOVER_RETURN_COLUMNS).
GROUP_COLUMN = "stock_turnover_group"

# 원본 컬럼명 → 내부 표준 컬럼명.
COLUMNS: dict[str, str] = {
    "기준월": "base_month",
    "CSMT_ORZ_CD": "branch_id",
    "CSMT_ORZ_NM": "branch_name",
    "국내주식회전율그룹": GROUP_COLUMN,
    "수익률_1년": "return_1y",
    "수익률_3년": "return_3y",
}


def build(frame: pd.DataFrame) -> pd.DataFrame:
    """표준 이름으로 바뀐 원본에서 회전율 구간별 수익률 프레임을 만든다."""
    return segment_return.build(
        frame,
        COLUMNS,
        LABEL,
        GROUP_COLUMN,
        STOCK_TURNOVER_GROUPS,
        "STOCK_TURNOVER_GROUPS",
    )


__all__ = [
    "COLUMNS",
    "FILE",
    "FILE_ENV",
    "GROUP_COLUMN",
    "LABEL",
    "build",
]
