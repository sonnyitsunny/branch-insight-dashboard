"""원본 파일 — 월별 공통고객 수.

지점과 '전체' 행이 월마다 들어 있다. 원본 컬럼 이름이 바뀌면 이 파일의
`COLUMNS`만 고친다. 다른 파일은 고치지 않는다.

읽어 들인 값을 표준 컬럼 이름으로 바꾸고 기준 월 형식만 맞춘다. 여러 원본을
맞춰 보는 대조는 `dashboard.sources`가 맡는다(→ AGENTS.md §9).
"""

from __future__ import annotations

import pandas as pd

from dashboard.data import to_month_column

# 실제 데이터를 붙일 때 여기만 고치면 된다.
#
# 파일 이름만 적으면 app.py 옆의 `data/` 폴더에서 찾는다.
#   FILE = "월별고객수.pkl"          → data/월별고객수.pkl
# 다른 위치에 두면 프로젝트 폴더 기준 경로나 전체 경로를 적는다.
#   FILE = "반입/월별고객수.pkl"
#   FILE = r"D:\데이터\월별고객수.pkl"
#
# 환경 변수를 지정하면 아래 값보다 환경 변수가 우선한다.
FILE = "월별고객수.pkl"
FILE_ENV = "DASHBOARD_DATA_FILE"

LABEL = "월별 고객 수"

# 원본 컬럼명 → 내부 표준 컬럼명.
COLUMNS: dict[str, str] = {
    "기준월": "base_month",
    "CSMT_ORZ_CD": "branch_id",
    "CSMT_ORZ_NM": "branch_name",
    "공통고객수": "customer_count",
}


def build(frame: pd.DataFrame) -> pd.DataFrame:
    """표준 이름으로 바뀐 원본에서 월별 프레임을 만든다.

    기준 월은 `202601`이든 `2026-01`이든 날짜든 읽어서 `YYYY-MM`으로 맞춘다.
    """
    monthly = frame.loc[:, list(COLUMNS.values())].copy()
    monthly["base_month"] = to_month_column(monthly["base_month"], "monthly")
    return monthly


def months(monthly: pd.DataFrame) -> list[str]:
    """원본에 들어 있는 기준 월. 오름차순.

    두 개 미만이면 전년 대비를 만들 수 없으므로 알리며 멈춘다.
    """
    found = sorted(monthly["base_month"].unique())
    if len(found) < 2:
        raise ValueError(
            f"{LABEL} 파일에 월이 {len(found)}개뿐입니다. 최소 두 개"
            " 월이 필요합니다."
        )
    return found
