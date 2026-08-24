"""원본 파일 — 개인연금 비중 구간별 수익률.

기준월·지점·개인연금 잔고 비중 구간마다 한 행이고 그 행에 1년·3년 수익률이
붙어 있다. 국내주식·해외주식·ETF 비중 원본과 같은 모양이라 조립은 함께
쓴다(→ dashboard/sources/segment_return.py).

여기서 말하는 개인연금은 연금 구분 축의 '개인연금'과 같은 상품이지만
(→ data.PENSION_TYPES) 이 원본에는 그 축이 없다. 잔고에서 개인연금이
차지하는 몫으로만 가른다.

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
#   FILE = "수익률_seg_개인연금비중.pkl"
#       → data/수익률_seg_개인연금비중.pkl
# 환경 변수를 지정하면 아래 값보다 환경 변수가 우선한다.
FILE = "수익률_seg_개인연금비중.pkl"
FILE_ENV = "DASHBOARD_PENSION_SHARE_RETURN_FILE"

LABEL = "개인연금비중별 수익률"

# 가르는 축의 표준 컬럼 이름(→ data.PENSION_SHARE_RETURN_COLUMNS).
GROUP_COLUMN = "pension_share_group"

# 원본 컬럼명 → 내부 표준 컬럼명.
COLUMNS: dict[str, str] = {
    "기준월": "base_month",
    "CSMT_ORZ_CD": "branch_id",
    "CSMT_ORZ_NM": "branch_name",
    "개인연금잔고비중": GROUP_COLUMN,
    "수익률_1년": "return_1y",
    "수익률_3년": "return_3y",
}


def build(frame: pd.DataFrame) -> pd.DataFrame:
    """표준 이름으로 바뀐 원본에서 개인연금비중별 수익률 프레임을 만든다."""
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
