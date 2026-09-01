"""테스트가 쓰는 표본 파일과 그 모양.

앱은 실제 pkl 두 개를 읽는다. 테스트는 `tests/data/`에 넣어 둔 표본 파일을
같은 경로로 읽어 확인한다. 표본도 실제 원본과 같은 형식이라 컬럼 매핑·비율
환산·대조 검증을 그대로 거친다.

여기 적은 상수는 표본 파일의 내용을 그대로 옮긴 것이다. 앱 코드에는
기간이나 지점 수를 적어 두지 않는다. 실제 데이터에서 달라지기 때문이다.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from dashboard.data import YOY_MONTHS, shift_month

FIXTURE_DIR = Path(__file__).resolve().parent / "data"
MONTHLY_FILE = FIXTURE_DIR / "monthly.pkl"
CUSTOMER2_FILE = FIXTURE_DIR / "customer2.pkl"
CUSTOMER2_AI_FILE = FIXTURE_DIR / "customer2_ai.pkl"
ASSET1_FILE = FIXTURE_DIR / "asset1.pkl"
ASSET2_FILE = FIXTURE_DIR / "asset2.pkl"
ASSET3_FILE = FIXTURE_DIR / "asset3.pkl"
ASSET4_FILE = FIXTURE_DIR / "asset4.pkl"
CONSULTING1_FILE = FIXTURE_DIR / "consulting1.pkl"
TRANSACTION1_FILE = FIXTURE_DIR / "transaction1.pkl"
TRANSACTION2_FILE = FIXTURE_DIR / "transaction2.pkl"
TRANSACTION3_FILE = FIXTURE_DIR / "transaction3.pkl"
REVENUE1_FILE = FIXTURE_DIR / "revenue1.pkl"
DOMESTIC_STOCK1_FILE = FIXTURE_DIR / "domestic_stock1.pkl"
DOMESTIC_STOCK2_FILE = FIXTURE_DIR / "domestic_stock2.pkl"
OVERSEAS_STOCK1_FILE = FIXTURE_DIR / "overseas_stock1.pkl"
OVERSEAS_STOCK2_FILE = FIXTURE_DIR / "overseas_stock2.pkl"
ETF2_FILE = FIXTURE_DIR / "etf2.pkl"
FUND1_FILE = FIXTURE_DIR / "fund1.pkl"
PENSION1_FILE = FIXTURE_DIR / "pension1.pkl"
BRANCH_RETURN_FILE = FIXTURE_DIR / "branch_return.pkl"
RETURN_GROUP_FILE = FIXTURE_DIR / "return_group.pkl"
ASSET_RETURN_FILE = FIXTURE_DIR / "asset_return.pkl"
STOCK_SHARE_RETURN_FILE = FIXTURE_DIR / "stock_share_return.pkl"
OVERSEAS_SHARE_RETURN_FILE = FIXTURE_DIR / "overseas_share_return.pkl"
ETF_SHARE_RETURN_FILE = FIXTURE_DIR / "etf_share_return.pkl"
PENSION_SHARE_RETURN_FILE = FIXTURE_DIR / "pension_share_return.pkl"
STOCK_TURNOVER_RETURN_FILE = FIXTURE_DIR / "stock_turnover_return.pkl"
AGE_RETURN_FILE = FIXTURE_DIR / "age_return.pkl"
DIGITAL1_FILE = FIXTURE_DIR / "digital1.pkl"
DIGITAL2_FILE = FIXTURE_DIR / "digital2.pkl"
DIGITAL3_FILE = FIXTURE_DIR / "digital3.pkl"
DIGITAL4_FILE = FIXTURE_DIR / "digital4.pkl"

# tests/data/ 표본의 모양
START_MONTH = "2025-07"
MONTH_COUNT = 13
END_MONTH = shift_month(START_MONTH, MONTH_COUNT - 1)
CURRENT_MONTH = END_MONTH
PREVIOUS_MONTH = shift_month(CURRENT_MONTH, -1)
YOY_BASE_MONTH = shift_month(CURRENT_MONTH, -YOY_MONTHS)
BRANCH_COUNT = 27

# 상담 표본의 모양. 상담은 최근 두 달만 담고 있고, 지점·'전체'마다
# 상담구분 3개 × 번호 10개다.
CONSULTING_MONTHS = 2
CONSULTING_TYPE_COUNT = 3
CONSULTING_TOPIC_COUNT = 10

# 거래 표본의 모양. 거래1·거래3은 지점·'전체'마다 월 하나에 한 행이고,
# 거래2는 연금 구분 3개씩이라 세 배다.
TRADE_PRODUCT_COUNT = 6
PENSION_TYPE_COUNT = 3
PENSION_TRADE_PRODUCT_COUNT = 4
CASH_FLOW_CHANNEL_COUNT = 3

# 수익 표본의 모양. 지점·'전체'마다 월 하나에 한 행이고, 데이터 계층이
# 리테일 상품 9개 + 리테일·퇴직·최종 3개로 편다.
REVENUE_TYPE_COUNT = 12

# 상품 표본의 모양. 원본이 마지막 한 달만 담고 있고, 지점·'전체'마다
# 순위 20개다.
STOCK_MONTHS = 1
STOCK_RANK_COUNT = 20
# 시가총액 상위 종목 표본의 종목 수. 지점마다 거래한 종목만 행으로 있어
# 행 수는 지점 × 종목보다 적다.
STOCK_CAP_COUNT = 12

# 해외주식 표본의 모양. 국내주식 순위표와 같이 마지막 한 달, 지점·'전체'마다
# 순위 20개다(→ STOCK_RANK_COUNT). 앞 달에 없던 종목이 있어 순위변동이 비어
# 있는 행이 지점마다 하나씩 들어 있다.
OVERSEAS_NEW_ENTRY_RANK = 20

# 해외주식 시가총액 상위 종목 표본의 종목 수. 국내주식 쪽과 같이 지점마다
# 거래한 종목만 행으로 있어 행 수는 지점 × 종목보다 적다.
OVERSEAS_STOCK_CAP_COUNT = 12

# ETF 표본의 모양. 주식 순위표와 같이 마지막 한 달, 지점·'전체'마다 순위
# 20개다(→ STOCK_RANK_COUNT). 앞 달에 없던 종목이 있어 순위변동이 비어 있는
# 행이 지점마다 하나씩 들어 있다.
ETF_NEW_ENTRY_RANK = 20

# 펀드 표본의 모양. ETF와 같이 마지막 한 달을 담되 **지점마다 순위 수가
# 다르다.** 파는 종목이 적은 지점을 나타내려고 네 곳마다 한 곳은 순위가
# 12까지만 있다. 앞 달에 없던 종목은 지점마다 마지막 순위에 하나씩 둔다.
FUND_SHORT_RANK_COUNT = 12
FUND_SHORT_BRANCH_STEP = 4

# **동순위.** 실제 원본은 값이 같은 종목이 여럿이면 같은 등수를 나란히
# 담는다. 두 곳마다 한 곳에서 이 등수를 두 번 쓰고 그다음 등수를 건너뛴다.
# 행 수는 그대로다(→ dashboard/sources/fund1.py 의 check_ranks).
FUND_TIED_RANK = 5
FUND_TIE_BRANCH_STEP = 2


def fund_rank_counts() -> list[int]:
    """펀드 표본에서 지점마다 행이 몇 개인지. '전체'는 빼고 센다.

    동순위가 있어도 행 수는 그대로다. 한 등수를 두 번 쓰고 그다음 등수를
    건너뛰기 때문이다(→ FUND_TIED_RANK).
    """
    return [
        (
            FUND_SHORT_RANK_COUNT
            if index % FUND_SHORT_BRANCH_STEP == 0
            else STOCK_RANK_COUNT
        )
        for index in range(BRANCH_COUNT)
    ]


# 연금 상품 표본의 모양. 원본이 상품 여섯 개(연금 구분 3 × 상품 2)를 가로로
# 펼쳐 담고 있어, 지점·'전체'마다 순위 20개짜리 목록이 여섯 벌이다.
# 개인연금 펀드만 세 곳마다 한 곳이 13위까지고, 그 뒤 순위는 종목명이 빈
# 칸이라 표준 프레임에 줄이 없다.
PENSION_BLOCK_COUNT = 6
PENSION_SHORT_BLOCK = ("개인연금", "펀드")
PENSION_SHORT_RANK_COUNT = 13
PENSION_SHORT_BRANCH_STEP = 3


def pension_rank_counts() -> list[int]:
    """연금 표본에서 지점·상품마다 몇 위까지 있는지. '전체'는 빼고 센다.

    개인연금 펀드만 지점에 따라 짧고 나머지 다섯 상품은 끝까지 찬다.
    """
    counts = []
    for index in range(BRANCH_COUNT):
        short = index % PENSION_SHORT_BRANCH_STEP == 0
        counts.append(
            PENSION_SHORT_RANK_COUNT if short else STOCK_RANK_COUNT
        )
        counts.extend(
            [STOCK_RANK_COUNT] * (PENSION_BLOCK_COUNT - 1)
        )
    return counts


# 수익률 표본의 모양. 마지막 두 달을 담고, 달마다 지점·'전체'가 한 행씩
# 있다. 분류축이 없어 한 달의 행 수가 곧 지점 수다. 손실이 난 지점이 있어
# 1년·3년 모두 음수가 섞여 있다.
#
# 두 달을 담는 이유 — 화면은 최근월만 그린다. 표본이 한 달뿐이면 그 규칙이
# 깨져도 드러나지 않는다. 두 달의 값은 일부러 다르게 두어, 어느 달을
# 그렸는지 값으로 가릴 수 있게 한다(→ tests/test_return_tab.py).
BRANCH_RETURN_MONTHS = 2

# 수익률 그룹별 비중 표본의 모양. 마지막 한 달을 담고, 지점·'전체'마다
# 기간 둘 × 구간 열 = 스무 행이다.
RETURN_GROUP_ROWS = 20

# 자산규모별 수익률 표본의 모양. 마지막 한 달을 담고, 지점·'전체'마다
# 자산 규모 구간 여섯 행이다.
ASSET_RETURN_ROWS = 6

# 구간별 수익률 표본 여섯 개의 모양. 가르는 기준마다 원본 파일이 따로 오고
# 표준 프레임도 따로다. 모두 마지막 한 달을 담고, 지점·'전체'마다 구간
# 수만큼 행이 있다. 연령대만 일곱이고 나머지는 다섯이다.
#
# 표준 프레임 이름 → (구간을 담는 컬럼, 지점마다 몇 행인지).
SEGMENT_RETURN_FRAMES: dict[str, tuple[str, int]] = {
    "stock_share_return": ("stock_share_group", 5),
    "overseas_share_return": ("overseas_share_group", 5),
    "etf_share_return": ("etf_share_group", 5),
    "pension_share_return": ("pension_share_group", 5),
    "stock_turnover_return": ("stock_turnover_group", 5),
    "age_return": ("return_age_group", 7),
}


# 디지털 채널 표본의 모양. 두 원본 모두 열세 달을 모두 담고, 지점·'전체'마다
# 월 하나에 한 행이다. 디지털채널1은 채널 셋이 한 행에 가로로 붙어 있어
# 데이터 계층이 세 줄로 펴고, 디지털채널2도 같은 채널 축으로 편다.
# 따라서 표준 프레임의 행 수는 원본 행 수의 세 배다.
DIGITAL_CHANNEL_COUNT = 3

# 디지털채널3 표본의 모양. 이쪽만 **마지막 한 달**을 담고, 지점·'전체'마다
# 이용일수 구간 여섯 행이다. 데이터 계층이 채널로 펴므로 표준 프레임의 행
# 수는 지점 × 구간 × 채널이다.
DIGITAL_USAGE_DAYS_MONTHS = 1
DIGITAL_USAGE_DAY_ROWS = 6

# 디지털채널4 표본의 모양. 이쪽도 **마지막 한 달**을 담고, 지점·'전체'마다
# 순위 30개다. 원본이 메뉴 분류 여섯을 가로로 펼쳐 담고 있어, 데이터 계층이
# 편 표준 프레임의 행 수는 지점 × 순위 × 분류다.
DIGITAL_MENU_MONTHS = 1
DIGITAL_MENU_RANK_COUNT = 30
DIGITAL_MENU_CATEGORY_COUNT = 6


def month_range() -> list[str]:
    """표본이 담고 있는 월 목록을 `YYYY-MM` 문자열로 반환한다."""
    periods = pd.period_range(start=START_MONTH, periods=MONTH_COUNT, freq="M")
    return [str(period) for period in periods]
