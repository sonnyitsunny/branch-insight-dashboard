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
PROFILE_FILE = FIXTURE_DIR / "profile.pkl"
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


def month_range() -> list[str]:
    """표본이 담고 있는 월 목록을 `YYYY-MM` 문자열로 반환한다."""
    periods = pd.period_range(start=START_MONTH, periods=MONTH_COUNT, freq="M")
    return [str(period) for period in periods]
