"""원본 파일 — 월별 연금 자산.

자산1과 같은 골격이다. 기준월·지점마다 한 행이고 '전체' 합계 행이 월마다
하나 더 있다. 여기에 개인연금·IRP·DC의 가입 고객 수와 자산이 붙어 있다.

같은 지표가 자산2에도 있지만 그쪽은 기준 월이 없는 한 시점 스냅샷이라
추이를 그릴 수 없다. 월별로 움직이는 그림은 이 파일을 쓴다. 두 파일은
집계 기준이 달라 서로 대조하지 않는다(→ dashboard/sources/asset2.py).

단위 — 자산은 **억원**이다. 자산2는 원 단위로 들어와 어댑터가 환산하지만
이 파일은 이미 억원이라 그대로 쓴다. 같은 지표가 프레임마다 다른 단위면
두 값을 함께 그리는 순간 눈금이 어긋난다.

원본 컬럼 이름이 바뀌면 이 파일의 `COLUMNS`만 고친다. 다른 파일은 고치지
않는다(→ AGENTS.md §9).
"""

from __future__ import annotations

import pandas as pd

from dashboard.data import to_month_column

# 실제 데이터를 붙일 때 여기만 고치면 된다.
#
# 파일 이름만 적으면 app.py 옆의 `data/` 폴더에서 찾는다.
#   FILE = "자산4.pkl"              → data/자산4.pkl
# 환경 변수를 지정하면 아래 값보다 환경 변수가 우선한다.
FILE = "자산4.pkl"
FILE_ENV = "DASHBOARD_ASSET4_FILE"

LABEL = "지점 자산4"

# 원본 컬럼명 → 내부 표준 컬럼명.
#
# 표준 이름은 자산2가 쓰는 이름과 같다. 두 원본이 같은 지표를 담고 있어
# 이름까지 다르면 화면 쪽에서 어느 쪽 값인지 알 수 없게 된다. 붙는 프레임이
# 달라(월별 vs 지점 요약) 서로 덮어쓰지 않는다.
COLUMNS: dict[str, str] = {
    "기준월": "base_month",
    "CSMT_ORZ_CD": "branch_id",
    "CSMT_ORZ_NM": "branch_name",
    "개인연금고객수": "pension_customer_count",
    "개인연금자산": "pension_assets",
    "IRP고객수": "irp_customer_count",
    "IRP자산": "irp_assets",
    "DC고객수": "dc_customer_count",
    "DC자산": "dc_assets",
}

# 월별 프레임에 붙여 화면까지 넘길 컬럼. 자산은 억원 단위다.
# 지점 코드·이름·기준 월은 월별 프레임에 이미 있으므로 뺀다.
VALUE_COLUMNS: tuple[str, ...] = tuple(
    name
    for name in COLUMNS.values()
    if name not in ("base_month", "branch_id", "branch_name")
)


def build(frame: pd.DataFrame) -> pd.DataFrame:
    """표준 이름으로 바뀐 원본에서 연금 자산 프레임을 만든다.

    기준 월은 `202601`이든 `2026-01`이든 날짜든 읽어서 `YYYY-MM`으로 맞춘다.
    값은 고치지 않는다. 자산과 고객 수가 서로 앞뒤가 맞는지는 확인하지
    않는다 — 1인 평균을 여기서 만들지 않으므로 볼 이유가 없다.
    """
    pension = frame.loc[:, list(COLUMNS.values())].copy()
    pension["base_month"] = to_month_column(pension["base_month"], "asset4")
    return pension
