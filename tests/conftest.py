"""테스트 공통 설정.

모든 테스트가 `tests/data/`의 표본 파일을 읽도록 환경 변수를 걸어 둔다.
수집 전에 정해져야 하므로 픽스처가 아니라 여기서 바로 설정한다. 픽스처로 두면
범위가 더 넓은 픽스처(module 단위 `dataset`)가 먼저 만들어져 값이 비어 버린다.

개별 테스트가 `monkeypatch.setenv`로 다시 덮으면 그 값이 이긴다.
"""

from __future__ import annotations

import os

from dashboard import sources
from fixture_data import (
    AGE_RETURN_FILE,
    ASSET1_FILE,
    ASSET_RETURN_FILE,
    BRANCH_RETURN_FILE,
    ASSET2_FILE,
    ASSET3_FILE,
    ASSET4_FILE,
    CONSULTING1_FILE,
    DOMESTIC_STOCK1_FILE,
    DOMESTIC_STOCK2_FILE,
    ETF2_FILE,
    ETF_SHARE_RETURN_FILE,
    FUND1_FILE,
    MONTHLY_FILE,
    OVERSEAS_SHARE_RETURN_FILE,
    OVERSEAS_STOCK1_FILE,
    OVERSEAS_STOCK2_FILE,
    PENSION1_FILE,
    PENSION_SHARE_RETURN_FILE,
    PROFILE_FILE,
    RETURN_GROUP_FILE,
    REVENUE1_FILE,
    STOCK_SHARE_RETURN_FILE,
    STOCK_TURNOVER_RETURN_FILE,
    TRANSACTION1_FILE,
    TRANSACTION2_FILE,
    TRANSACTION3_FILE,
)

# 원본 모듈에 적어 둔 파일 이름은 실행 환경마다 다르다. 테스트가 그 값에
# 좌우되지 않도록 비우고, 읽을 파일은 환경 변수로만 정한다.
FIXTURE_FILES = {
    "monthly": MONTHLY_FILE,
    "profile": PROFILE_FILE,
    "asset1": ASSET1_FILE,
    "asset2": ASSET2_FILE,
    "asset3": ASSET3_FILE,
    "asset4": ASSET4_FILE,
    "consulting1": CONSULTING1_FILE,
    "transaction1": TRANSACTION1_FILE,
    "transaction2": TRANSACTION2_FILE,
    "transaction3": TRANSACTION3_FILE,
    "revenue1": REVENUE1_FILE,
    "domestic_stock1": DOMESTIC_STOCK1_FILE,
    "domestic_stock2": DOMESTIC_STOCK2_FILE,
    "overseas_stock1": OVERSEAS_STOCK1_FILE,
    "overseas_stock2": OVERSEAS_STOCK2_FILE,
    "etf2": ETF2_FILE,
    "fund1": FUND1_FILE,
    "pension1": PENSION1_FILE,
    "branch_return": BRANCH_RETURN_FILE,
    "return_group": RETURN_GROUP_FILE,
    "asset_return": ASSET_RETURN_FILE,
    "stock_share_return": STOCK_SHARE_RETURN_FILE,
    "overseas_share_return": OVERSEAS_SHARE_RETURN_FILE,
    "etf_share_return": ETF_SHARE_RETURN_FILE,
    "pension_share_return": PENSION_SHARE_RETURN_FILE,
    "stock_turnover_return": STOCK_TURNOVER_RETURN_FILE,
    "age_return": AGE_RETURN_FILE,
}

for source in sources.SOURCES:
    source.module.FILE = ""
    os.environ[source.env] = str(FIXTURE_FILES[source.key])
