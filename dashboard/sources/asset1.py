"""원본 파일 — 지점 자산.

월별 고객 수 파일과 같은 골격이다. 기준월·지점마다 한 행이고 '전체' 합계
행이 월마다 하나 더 있다. 여기에 순자산과 고객 평균 자산이 붙어 있다.

원본 컬럼 이름이 바뀌면 이 파일의 `COLUMNS`만 고친다. 다른 파일은 고치지
않는다.

공통고객수는 월별 고객 수 파일에도 있다. 같은 지표가 두 원본에 겹쳐 있으면
값이 같은지 확인해야 하므로, 여기서는 화면으로 넘기지 않고 대조에만 쓴다.
그 대조는 원본 하나에 속하지 않으므로 `dashboard.sources`가 맡는다
(→ AGENTS.md §9).
"""

from __future__ import annotations

import pandas as pd

from dashboard.data import to_month_column

# 실제 데이터를 붙일 때 여기만 고치면 된다.
#
# 파일 이름만 적으면 app.py 옆의 `data/` 폴더에서 찾는다.
#   FILE = "자산1.pkl"              → data/자산1.pkl
# 다른 위치에 두면 프로젝트 폴더 기준 경로나 전체 경로를 적는다.
#   FILE = "반입/자산1.pkl"
#   FILE = r"D:\데이터\자산1.pkl"
#
# 환경 변수를 지정하면 아래 값보다 환경 변수가 우선한다.
FILE = "자산1.pkl"
FILE_ENV = "DASHBOARD_ASSET1_FILE"

LABEL = "지점 자산1"

# 원본 컬럼명 → 내부 표준 컬럼명.
#
# 단위를 이름에서 지운다. 순자산은 억원, 고객 평균 자산은 백만원이며 그
# 약속은 아래 주석과 포맷 함수가 함께 지킨다.
COLUMNS: dict[str, str] = {
    "기준월": "base_month",
    "CSMT_ORZ_CD": "branch_id",
    "CSMT_ORZ_NM": "branch_name",
    "공통고객수": "customer_count",
    "순자산_억원": "net_assets",
    "고객평균자산_백만원": "average_assets",
}

# 월별 프레임에 붙여 화면까지 넘길 컬럼.
# `net_assets`는 억원, `average_assets`는 백만원 단위다.
# `customer_count`는 월별 고객 수 파일과 겹치므로 여기 넣지 않는다.
VALUE_COLUMNS: tuple[str, ...] = ("net_assets", "average_assets")


def build(frame: pd.DataFrame) -> pd.DataFrame:
    """표준 이름으로 바뀐 원본에서 자산 프레임을 만든다.

    기준 월은 `202601`이든 `2026-01`이든 날짜든 읽어서 `YYYY-MM`으로 맞춘다.
    값은 고치지 않는다. 순자산과 평균 자산이 서로 앞뒤가 맞는지는 확인하지
    않는다 — 평균 자산의 분모가 공통고객수와 같다는 보장이 없다.
    """
    asset = frame.loc[:, list(COLUMNS.values())].copy()
    asset["base_month"] = to_month_column(asset["base_month"], "asset")
    return asset
