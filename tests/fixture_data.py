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

# tests/data/ 표본의 모양
START_MONTH = "2025-07"
MONTH_COUNT = 13
END_MONTH = shift_month(START_MONTH, MONTH_COUNT - 1)
CURRENT_MONTH = END_MONTH
PREVIOUS_MONTH = shift_month(CURRENT_MONTH, -1)
YOY_BASE_MONTH = shift_month(CURRENT_MONTH, -YOY_MONTHS)
BRANCH_COUNT = 27


def month_range() -> list[str]:
    """표본이 담고 있는 월 목록을 `YYYY-MM` 문자열로 반환한다."""
    periods = pd.period_range(start=START_MONTH, periods=MONTH_COUNT, freq="M")
    return [str(period) for period in periods]
