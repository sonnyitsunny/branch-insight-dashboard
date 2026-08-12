"""원본 파일 — 지점별 자산 프로필.

지점 프로필 파일과 같은 골격이다. 기준 월 컬럼이 없고 지점마다 한 행인
한 시점 스냅샷이라, 월별 파일의 마지막 월을 기준 월로 받아 쓴다.

원본 컬럼 이름이 바뀌면 이 파일의 표만 고친다. 다른 파일은 고치지 않는다
(→ AGENTS.md §9).

단위 — **컬럼마다 다르다.** 순자산 두 개는 원본이 이미 억원으로 담고
있고, 연금 자산과 1인 평균은 원 단위로 들어온다. 프로젝트 표준은 자산1
파일과 같이 총액을 억원, 평균을 백만원으로 쓰므로 원 단위인 것만 여기서
환산한다. 같은 지표가 프레임마다 다른 단위면 두 값을 함께 그리는 순간
눈금이 어긋난다.

단위를 잘못 잡으면 값이 1억 배 어긋나는데도 멈추지 않고 그대로 그려진다.
축 눈금이 전부 0이 되면 여기부터 확인한다.

`고객수`와 `순자산_종료월`은 다른 원본에도 있지만 집계 기준이 달라
대조하지 않는다. 각 파일의 값을 그대로 쓴다.
"""

from __future__ import annotations

import pandas as pd

from dashboard.data import to_numeric_column

# 실제 데이터를 붙일 때 여기만 고치면 된다.
#
# 파일 이름만 적으면 app.py 옆의 `data/` 폴더에서 찾는다.
#   FILE = "자산2.pkl"              → data/자산2.pkl
# 환경 변수를 지정하면 아래 값보다 환경 변수가 우선한다.
FILE = "자산2.pkl"
FILE_ENV = "DASHBOARD_ASSET2_FILE"

LABEL = "지점 자산2"

# 원본 컬럼명 → 내부 표준 컬럼명.
COLUMNS: dict[str, str] = {
    "CSMT_ORZ_CD": "branch_id",
    "CSMT_ORZ_NM": "branch_name",
    "고객수": "asset_customer_count",
    "순자산_시작월": "net_assets_start",
    "순자산_종료월": "net_assets_end",
    "순자산증가율": "net_assets_growth",
    "국내주식비중": "domestic_stock_share",
    "해외주식비중": "foreign_stock_share",
    "국내ETF비중": "domestic_etf_share",
    "채권비중": "bond_share",
    "펀드비중": "fund_share",
    "기타비중": "other_asset_share",
    "개인연금고객수": "pension_customer_count",
    "개인연금자산": "pension_assets",
    "개인연금자산평균": "pension_assets_average",
    "IRP고객수": "irp_customer_count",
    "IRP자산": "irp_assets",
    "IRP자산평균": "irp_assets_average",
    "DC고객수": "dc_customer_count",
    "DC자산": "dc_assets",
    "DC자산평균": "dc_assets_average",
}

# 원 단위로 들어오는 총액. 억원으로 환산한다.
#
# 순자산 두 개(`net_assets_start`·`net_assets_end`)는 원본이 이미 억원이라
# 여기 넣지 않는다. 넣으면 1억으로 한 번 더 나뉘어 축 눈금이 전부 0이 된다.
WON_TO_100M_COLUMNS: tuple[str, ...] = (
    "pension_assets",
    "irp_assets",
    "dc_assets",
)

# 원본이 이미 억원으로 담고 있어 손대지 않는 컬럼. 목록에 이름을 남겨,
# 환산하지 않는 것이 빠뜨린 게 아니라 정해 둔 것임을 드러낸다.
GIVEN_IN_100M_COLUMNS: tuple[str, ...] = (
    "net_assets_start",
    "net_assets_end",
)

# 원 단위로 들어오는 1인 평균. 백만원으로 환산한다.
WON_TO_1M_COLUMNS: tuple[str, ...] = (
    "pension_assets_average",
    "irp_assets_average",
    "dc_assets_average",
)

# 0~1 비율로 들어오므로 100을 곱해 %로 맞춘다.
# 순자산증가율은 이미 %라서 여기에 넣지 않는다.
RATIO_COLUMNS: tuple[str, ...] = (
    "domestic_stock_share",
    "foreign_stock_share",
    "domestic_etf_share",
    "bond_share",
    "fund_share",
    "other_asset_share",
)

# 지점 요약 프레임에 붙여 화면까지 넘길 컬럼.
# 지점 코드·이름·기준 월은 요약 프레임에 이미 있으므로 뺀다.
VALUE_COLUMNS: tuple[str, ...] = tuple(
    name
    for name in COLUMNS.values()
    if name not in ("branch_id", "branch_name")
)

_WON_PER_100M = 100_000_000
_WON_PER_1M = 1_000_000


def build(frame: pd.DataFrame, base_month: str) -> pd.DataFrame:
    """표준 이름으로 바뀐 원본에 기준 월을 붙이고 단위를 맞춘다.

    원본에 기준 월 컬럼이 없으므로 월별 파일의 마지막 월을 받아 쓴다.
    값을 고치지는 않는다. 단위 환산과 비율의 % 변환만 한다.
    """
    asset = frame.loc[:, list(COLUMNS.values())].copy()
    asset["base_month"] = base_month
    for column, divisor in (
        *((name, _WON_PER_100M) for name in WON_TO_100M_COLUMNS),
        *((name, _WON_PER_1M) for name in WON_TO_1M_COLUMNS),
    ):
        asset[column] = (
            to_numeric_column(asset[column], LABEL, column) / divisor
        )
    for column in GIVEN_IN_100M_COLUMNS:
        asset[column] = to_numeric_column(asset[column], LABEL, column)
    for column in RATIO_COLUMNS:
        asset[column] = (
            to_numeric_column(asset[column], LABEL, column) * 100.0
        )
    return asset
