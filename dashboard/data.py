"""데이터 계층.

대시보드가 데이터에 접근하는 유일한 경로다. 레이아웃·차트·그리드·콜백은
이 모듈이 반환한 데이터만 사용하고 파일이나 데이터베이스를 직접 읽지 않는다.

원본 파일마다 다른 컬럼 이름과 형태는 `dashboard/sources`의 해당 모듈이
흡수한다. 이 파일에는 파일 찾기, 정규화·검증 엔진, 표준 계약(`DashboardData`)만
둔다. 원본이 늘어도 이 파일은 커지지 않는다.
반환 구조가 같으면 UI 코드는 수정하지 않는다.

정규화는 값을 조용히 고치지 않는다. 읽을 수 없는 값이나 모르는 분류값을 만나면
0이나 결측으로 덮지 않고 어느 컬럼의 어떤 값이 문제인지 알려주며 멈춘다.
틀린 숫자가 맞는 것처럼 화면에 뜨는 쪽이 더 위험하기 때문이다.

금액 단위: `total_assets`는 억원 단위 정수다.
"""

from __future__ import annotations

import os
import warnings
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

# --- 기준 월 계산
# -------------------------------------------------------------
# 전년 동월 비교 간격(개월). 이 값 하나로 YoY 기준을 정한다.
YOY_MONTHS = 12


def shift_month(base_month: str, months: int) -> str:
    """`YYYY-MM`에서 `months`만큼 이동한 월을 반환한다. 음수면 과거로 간다."""
    return str(pd.Period(str(base_month)[:7], freq="M") + months)


# 기준 월을 특정 월로 고정하고 싶을 때 쓰는 환경 변수(`YYYY-MM`).
# 지정하지 않으면 데이터의 최신 월을 기준 월로 삼는다.
BASE_MONTH_ENV = "DASHBOARD_BASE_MONTH"

TOTAL_LABEL = "전체"

AGE_GROUPS = ("10대 이하", "20대", "30대", "40대", "50대", "60대 이상")
# 연령을 선택하지 않은 고객. 원본의 '합계'에는 안 들어가지만 고객 수에는
# 들어간다. 분포 차트에서는 빼고, 고객 수 대조에는 넣어 고객이 새지 않는지
# 확인한다(→ EXCLUDED_AGE_GROUPS 사용처).
EXCLUDED_AGE_GROUPS = ("기타",)
ALL_AGE_GROUPS = (*AGE_GROUPS, *EXCLUDED_AGE_GROUPS)

INVESTMENT_TYPES = (
    "성장형",
    "성장추구형",
    "위험중립형",
    "안정추구형",
    "안정형",
)
CONSENT_LABEL = "마케팅 동의"
NON_CONSENT_LABEL = "마케팅 불원"

# 자산 상품 분류. 자산3 원본의 '상품분류' 컬럼이 갖는 값이며, 여기 적은
# 순서대로 히트맵 세로축에 쌓인다(→ dashboard/sources/asset3.py).
# 원본에 여기 없는 값이 있으면 이름을 알리며 멈춘다.
ASSET_TYPES = (
    "국내주식",
    "해외주식",
    "ETF국내주식",
    "ETF해외주식",
    "ETF국내채권",
    "ETF해외채권",
    "ETF기타",
    "외화채권",
    "원화채권",
    "펀드",
    "신탁",
    "파생결합상품",
    "금현물",
    "현금성자산",
)
# 상품 구분과 무관한 지점 전체 값. 위 14개의 합이 아니라 따로 계산된 값이라
# 더해서 만들지 않고 원본 값을 그대로 쓴다. 지점 축의 '전체'(TOTAL_LABEL)와
# 이름은 같지만 다른 축이다.
ASSET_TYPE_TOTAL = TOTAL_LABEL
ALL_ASSET_TYPES = (*ASSET_TYPES, ASSET_TYPE_TOTAL)

# 거래 상품 분류. 거래1 원본이 상품마다 거래금액·거래고객수 컬럼을 갖고
# 있고, 그 원본 모듈이 한 줄에 한 상품인 형태로 편다
# (→ dashboard/sources/transaction1.py).
TRADE_PRODUCT_TYPES = (
    "국내주식",
    "해외주식",
    "국내ETF",
    "채권",
    "펀드",
)
# 상품 구분과 무관한 지점 전체 값. 위 5개의 합이라는 보장이 없어 더해서
# 만들지 않고 원본 값을 그대로 쓴다. 한 고객이 여러 상품을 거래하면
# 거래고객수는 상품별 합보다 작다. 지점 축의 '전체'와 이름은 같지만
# 다른 축이다.
TRADE_PRODUCT_TOTAL = TOTAL_LABEL
ALL_TRADE_PRODUCT_TYPES = (*TRADE_PRODUCT_TYPES, TRADE_PRODUCT_TOTAL)

# 연금 거래 구분과 상품 분류(거래2 원본). 구분마다 상품 분류가 따로 있어
# 축이 둘이다.
PENSION_TYPES = ("개인연금", "IRP", "DC")
PENSION_TRADE_PRODUCT_TYPES = ("국내ETF", "펀드", "기타")
ALL_PENSION_TRADE_PRODUCT_TYPES = (
    *PENSION_TRADE_PRODUCT_TYPES,
    TRADE_PRODUCT_TOTAL,
)

# 입출금 채널(거래3 원본). '전체'에는 순입금만 있고 입금·출금은 원본에
# 없어 비어 있다.
CASH_FLOW_CHANNELS = ("증권", "은행")
CASH_FLOW_CHANNEL_TOTAL = TOTAL_LABEL
ALL_CASH_FLOW_CHANNELS = (*CASH_FLOW_CHANNELS, CASH_FLOW_CHANNEL_TOTAL)

# 수익 분류(수익1 원본). 리테일 상품이 가로로 펼쳐져 있고, 그 원본 모듈이
# 한 줄에 한 분류인 형태로 편다(→ dashboard/sources/revenue1.py).
REVENUE_PRODUCT_TYPES = (
    "국내주식",
    "국내ETF",
    "해외주식",
    "예수금",
    "신용",
    "펀드",
    "채권",
    "CMA발행어음RP",
    "기타",
)
# 상품으로 나뉘지 않는 묶음 값. 리테일은 위 상품들의 소계, 퇴직은 퇴직연금,
# 최종은 '리테일 + 퇴직'이다. 셋 다 원본이 따로 담고 있으므로 더해서 만들지
# 않고 원본 값을 그대로 쓰되, 관계가 맞는지는 어댑터가 대조한다
# (→ dashboard/sources/revenue1.py 의 GROUP_SUMS).
# 지점 축의 '전체'와는 다른 축이다.
REVENUE_RETAIL = "리테일"
REVENUE_PENSION = "퇴직"
REVENUE_FINAL = "최종"
REVENUE_GROUP_TYPES = (REVENUE_RETAIL, REVENUE_PENSION, REVENUE_FINAL)
ALL_REVENUE_TYPES = (*REVENUE_PRODUCT_TYPES, *REVENUE_GROUP_TYPES)

# 원본이 연령 구간·투자성향을 숫자 코드로 담고 있으면 코드→이름을 여기에만
# 적는다.
# 예: {"1": "10대 이하", "2": "20대", ...}. 코드는 문자열로 적는다.
# 비어 있으면 원본이 위의 이름을 그대로 쓴다는 뜻이다.
AGE_GROUP_CODES: dict[str, str] = {}
INVESTMENT_TYPE_CODES: dict[str, str] = {}

# --- 실제 데이터 파일
# ---------------------------------------------------------
# 읽을 파일 이름은 원본마다 그 모듈에 적는다.
#   dashboard/sources/monthly.py — 월별 공통고객 수
#   dashboard/sources/profile.py — 지점별 프로필
# 환경 변수를 지정하면 그 값이 우선한다.

# --- 데이터 소스 -------------------------------------------------------------
DATA_SOURCE_ENV = "DASHBOARD_DATA_SOURCE"
# internal_source 는 실제 연결 방식이 확정된 뒤 구현한다.
SUPPORTED_DATA_SOURCES = ("local_file",)
DEFAULT_DATA_SOURCE = "local_file"

# app.py가 있는 폴더와 그 아래 데이터 폴더.
PROJECT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_DIR / "data"

# 원본 컬럼명 → 내부 표준 컬럼명.
# 실제 파일의 컬럼 이름이 아래 표준 이름과 다르면 여기에만 적는다.
# 다른 파일은 고치지 않는다. 예: {"기준년월": "base_month", "지점코드":
# "branch_id"}
SOURCE_COLUMN_MAP: dict[str, str] = {}

# --- 원본별 설정
# ------------------------------------------------------------
# 원본 파일마다 다른 컬럼 이름·형태는 `dashboard/sources`의 해당 모듈에
# 있다. 원본을 더 반입해도 이 파일은 커지지 않는다(→ AGENTS.md §9).

# 화면에서 빼는 투자성향 분류. 합계 대조에는 포함해 고객이 새는지 확인하고,
# 화면에는 무엇을 뺐는지 문구로 알린다(→ tabs.customer).
EXCLUDED_INVESTMENT_TYPES = ("미제공",)

AGE_COLUMNS = (
    "base_month",
    "branch_id",
    "branch_name",
    "age_group",
    "customer_count",
)
INVESTMENT_COLUMNS = (
    "base_month",
    "branch_id",
    "branch_name",
    "investment_type",
    "marketing_consent",
    "customer_count",
)
# 원본이 동의·불원을 각각 별도 인원수 컬럼으로 담고 있을 때 쓰는 형태.
# 데이터 계층에서 위의 표준 형태(한 줄에 하나의 구분)로 바꾼다.
INVESTMENT_WIDE_COLUMNS = (
    "base_month",
    "branch_id",
    "branch_name",
    "investment_type",
    "consent_customer_count",
    "non_consent_customer_count",
)
# 화면이 쓰는 비율 컬럼(%). 원본이 비율을 직접 주면 그 값을 그대로 전달하고,
# 인원수로 주면 아래 대응표를 써서 만들어 낸다.
SUMMARY_SHARE_COLUMNS = (
    "male_share",
    "recent_signup_share",
    "recommendation_share",
    "grade_s_share",
)
# 자산 구성 비중. 원본은 0~1 비율로 담고 어댑터가 %로 맞춘다
# (→ dashboard/sources/asset2.py).
ASSET_SHARE_COLUMNS = (
    "domestic_stock_share",
    "foreign_stock_share",
    "domestic_etf_share",
    "bond_share",
    "fund_share",
    "other_asset_share",
)

# 자산2가 주는 소수 컬럼. 총액은 억원, 1인 평균은 백만원,
# 순자산증가율은 원본이 이미 %로 담고 있어 그대로 쓴다.
ASSET_VALUE_COLUMNS = (
    "net_assets_start",
    "net_assets_end",
    "net_assets_growth",
    "pension_assets",
    "pension_assets_average",
    "irp_assets",
    "irp_assets_average",
    "dc_assets",
    "dc_assets_average",
)
ASSET_COUNT_COLUMNS = (
    "asset_customer_count",
    "pension_customer_count",
    "irp_customer_count",
    "dc_customer_count",
)

# 자산4가 주는 월별 연금 값. 자산은 억원이며 원본이 이미 억원으로 담고 있다
# (→ dashboard/sources/asset4.py). 자산2에도 같은 이름의 컬럼이 있지만
# 그쪽은 기준 월이 없는 한 시점 스냅샷이라 지점 요약 프레임에 붙는다.
MONTHLY_PENSION_COLUMNS = (
    "pension_customer_count",
    "pension_assets",
    "irp_customer_count",
    "irp_assets",
    "dc_customer_count",
    "dc_assets",
)

# '전체' 행을 지점 합계와 대조할 수 있는 자산 컬럼. 인원수와 총액만 넣는다.
# 증가율·비중·1인 평균은 더할 수 없으므로 원본 값을 그대로 믿는다.
ASSET_ADDITIVE_COLUMNS = (
    *ASSET_COUNT_COLUMNS,
    "net_assets_start",
    "net_assets_end",
    "pension_assets",
    "irp_assets",
    "dc_assets",
)

# 상담 원본이 주는 표준 컬럼. 지점 × 기준월 × 상담구분마다 번호 순으로
# 여러 행이 들어온다. 숫자가 아니라 글이 본체라 다른 프레임과 성격이 다르다
# (→ dashboard/sources/consulting1.py).
CONSULTING_COLUMNS = (
    "base_month",
    "branch_id",
    "branch_name",
    "consulting_type",
    "topic_rank",
    "topic",
    "topic_summary",
    "topic_share",
)

# 거래 원본이 주는 표준 컬럼. 거래금액은 **억원**이고 거래고객수는 명이다.
# 셋 다 지점 × 기준월에 분류축이 하나 이상 더 붙는다
# (→ dashboard/sources/transaction1.py, transaction2.py, transaction3.py).
TRANSACTION_COLUMNS = (
    "base_month",
    "branch_id",
    "branch_name",
    "product_type",
    "trade_amount",
    "trade_customer_count",
)
# '기타' 상품에는 원본에 거래고객수가 없다. 그래서 거래고객수는 반드시
# 있어야 하는 컬럼에서 뺀다.
PENSION_TRANSACTION_COLUMNS = (
    "base_month",
    "branch_id",
    "branch_name",
    "pension_type",
    "product_type",
    "trade_amount",
)
# 순입금은 빠져나간 달에 음수가 된다. 인원수와 달리 음수를 막지 않는다.
# 입금·출금은 '전체' 채널에 원본이 주지 않으므로 선택 컬럼이다.
CASH_FLOW_COLUMNS = (
    "base_month",
    "branch_id",
    "branch_name",
    "channel",
    "net_amount",
)

# 수익 원본이 주는 표준 컬럼. 지점 × 기준월에 수익 분류 축이 하나 더 붙는다
# (→ dashboard/sources/revenue1.py).
#
# 단위 — 금액은 **원**이다. 거래·자산 프레임의 억원과 다르므로 화면에서
# 포맷할 때 단위를 맞춰야 한다(→ dashboard/format.py 의 format_won).
# 원본이 원 단위로 담고 있어 억원으로 바꾸지 않는다. 나누어 두면 원본과
# 화면 숫자가 반올림만큼 달라진다(→ AGENTS.md §9).
#
# 수익은 손실이 나면 음수가 될 수 있다. 인원수와 달리 음수를 막지 않는다.
REVENUE_COLUMNS = (
    "base_month",
    "branch_id",
    "branch_name",
    "revenue_type",
    # 공통고객 수익(원). 모든 분류에 있다.
    "revenue_amount",
)
# 전체고객 수익(원)은 상품별로 나뉘어 있지 않아 '리테일'·'퇴직'·'최종'
# 행에만 있다. 비중(%)은 '리테일'에 없다. 없는 칸은 0으로 채우지 않고 비운다.
REVENUE_OPTIONAL_COLUMNS = (
    "all_revenue_amount",
    # 공통고객 수익 안에서 그 분류가 차지하는 비중(%). 분모는 '최종'이라
    # 상품 9개와 '퇴직'을 합하면 100%가 된다.
    "revenue_share",
    # 공통고객 수익 비중(%) = 공통고객 '최종' ÷ 전체고객 '최종'. 위와 분모가
    # 달라 따로 담는다. 분류축이 없는 값이라 '최종' 행에만 있다
    # (→ revenue1.COMMON_SHARE_TYPE).
    "common_revenue_share",
)

# 상품 원본이 주는 표준 컬럼. 지점 × 기준월에 순위 축이 하나 더 붙는다
# (→ dashboard/sources/domestic_stock1.py).
#
# 단위 — 시가총액은 **억원**, 거래대금·순매수금액은 **원**이다. 한 프레임
# 안에서 단위가 갈리므로 이름을 나눠 둔다. 거래 프레임의
# `trade_amount`(억원)와 뜻이 겹치지 않도록 거래대금은 `trade_value`다.
#
# 순매수금액은 순매도인 달에 음수가 된다. 인원수와 달리 음수를 막지 않는다.
# 업종은 원본에 비어 있는 행이 있어 빈 문자열이 들어올 수 있다.
DOMESTIC_STOCK_RANK_COLUMNS = (
    "base_month",
    "branch_id",
    "branch_name",
    "stock_rank",
    "stock_name",
    "sector",
    "market_cap",
    "trade_customer_count",
    "trade_value",
    "net_buy_amount",
)
# 앞 달에 없던 종목은 순위변동을 비교할 값이 없어 비어 있다. 0으로 채우지
# 않는다. 0은 '순위가 그대로'라는 뜻이라 '앞 달에 없었다'와 다르다.
DOMESTIC_STOCK_RANK_OPTIONAL_COLUMNS = ("rank_change",)

# 시가총액 상위 종목의 지점별 거래(→ sources/domestic_stock2.py). 위의
# 순위표와 컬럼 이름·단위가 같지만 행을 고르는 기준이 다르다. 순위표는
# 지점마다 그 지점의 상위 N종목을 담고, 이쪽은 **시장 전체의 시가총액 상위
# N종목**을 지점마다 담는다. 그래서 순위 축이 없고 종목이 축이다.
#
# 지점이 그중 한 종목도 거래하지 않았으면 그 행이 아예 없다. 지점마다 행
# 수가 다른 것이 정상이며, 없는 행을 0으로 채우지 않는다. 0은 '거래 없음'이
# 아니라 '0으로 측정됨'을 뜻한다(→ AGENTS.md §9).
DOMESTIC_STOCK_CAP_COLUMNS = (
    "base_month",
    "branch_id",
    "branch_name",
    "stock_name",
    "sector",
    "market_cap",
    "trade_customer_count",
    "trade_value",
    "net_buy_amount",
)

SHARE_SOURCE_COUNT: dict[str, str] = {
    "male_share": "male_customer_count",
    "recent_signup_share": "recent_signup_customer_count",
    "recommendation_share": "recommendation_consent_customer_count",
    "grade_s_share": "grade_s_or_higher_customer_count",
}

# 소수로 다루는 컬럼. 나머지 수치 컬럼은 인원수·금액이므로 정수로 맞춘다.
# 자산 두 컬럼은 원본이 소수로 줄 수 있어 여기에 둔다. 정수로 반올림하면
# 원본과 화면 숫자가 달라진다.
_FLOAT_COLUMNS = (
    "average_age",
    "customer_growth_yoy",
    "share",
    "topic_share",
    "net_assets",
    "average_assets",
    "change_rate",
    "trade_amount",
    "deposit_amount",
    "withdrawal_amount",
    "net_amount",
    "revenue_amount",
    "common_revenue",
    "market_cap",
    "trade_value",
    "net_buy_amount",
    *DOMESTIC_STOCK_RANK_OPTIONAL_COLUMNS,
    *REVENUE_OPTIONAL_COLUMNS,
    *SUMMARY_SHARE_COLUMNS,
    *ASSET_SHARE_COLUMNS,
    *ASSET_VALUE_COLUMNS,
)

# 원본이 비중을 직접 담고 있을 때, 인원수에서 계산한 값과
# 이만큼까지는 다를 수 있다.
# 화면이 소수점 첫째 자리까지 보여주므로 그 아래 차이는 드러나지 않는다.
# 이보다 크게 벌어지면 집계 기준이 다르다는 뜻이라 알리며 멈춘다.
SHARE_TOLERANCE_PP = 0.05

# --- 파일 간 고객 수 대조 ----------------------------------------------------
# 원본 파일들이 서로 다른 날 뽑히면, 그 사이에 정보 제공을 철회하거나 거래를
# 끊은 고객만큼 수가 어긋난다. 몇 명 차이로 화면을 못 열게 하는 것은 과하다.
# 아래 범위 안이면 각 파일의 값을 그대로 쓰고 어디가 얼마나 다른지 알린다.
# 범위를 넘으면 두 파일의 집계 기준 자체가 다르다는 뜻이므로 멈춘다.
#
# 허용치는 둘 중 큰 쪽이다. 지점 규모가 제각각이라 한 가지 기준만 쓰면 큰
# 지점에서는 너무 빡빡하고 작은 지점에서는 너무 헐거워진다.
#
# **한 파일 안에서 앞뒤가 맞는지 보는 대조에는 쓰지 않는다.** 원본의 '전체'
# 행과 지점 합계, 연령 6개의 합과 '합계' 컬럼처럼 같은 파일 안의 숫자는
# 정확히 맞아야 한다(→ _check_source_totals, profile.check_equal_counts).
COUNT_TOLERANCE = 10
COUNT_TOLERANCE_RATIO = 0.005


def count_tolerance(expected: pd.Series) -> pd.Series:
    """대조할 값마다 허용할 차이(명)."""
    return (
        pd.to_numeric(expected, errors="coerce")
        .abs()
        .mul(COUNT_TOLERANCE_RATIO)
        .clip(lower=COUNT_TOLERANCE)
    )


def _key_text(key: object) -> str:
    """대조 키를 오류 메시지에 넣을 한 줄로 만든다."""
    if isinstance(key, tuple):
        return " ".join(str(part) for part in key)
    return str(key)


def _tolerance_hint() -> str:
    return (
        "원본이 원래 조금씩 어긋난다면 dashboard/data.py 의 "
        f"COUNT_TOLERANCE({COUNT_TOLERANCE}명) 또는 "
        f"COUNT_TOLERANCE_RATIO({COUNT_TOLERANCE_RATIO:.1%})를 올려 주세요."
    )


def check_count_gap(
    actual: pd.Series,
    expected: pd.Series,
    label: str,
    actual_label: str,
    expected_label: str,
) -> None:
    """두 원본의 고객 수를 대조한다. 작은 차이는 알리고 넘어간다.

    추출 시점이 하루만 달라도 그 사이에 빠져나간 고객만큼 수가 어긋난다.
    그 정도로 화면을 못 열게 하지 않는다. 대신 어느 파일의 어느 지점이
    얼마나 다른지 한 번 알려, 차이가 커지는 것을 놓치지 않게 한다.

    한쪽에만 있는 키는 값을 견줄 수 없으므로 멈춘다. 그 경우는 시점 차이가
    아니라 두 파일의 범위가 다르다는 뜻이다.
    """
    aligned = expected.reindex(actual.index)
    missing = aligned.isna() | actual.isna()
    if missing.any():
        raise ValueError(
            f"{expected_label} 파일과 {actual_label} 파일 중 한쪽에만 있는"
            f" 값이 {int(missing.sum())}건 있습니다. "
            f"예: {_key_text(actual.index[missing][0])}. "
            "두 파일이 같은 범위인지 확인해 주세요."
        )

    gap = (actual - aligned).round().abs()
    allowed = count_tolerance(aligned)
    over = gap > allowed
    if over.any():
        key = gap[over].idxmax()
        raise ValueError(
            f"두 파일의 {label}가 너무 다릅니다. {_key_text(key)} — "
            f"{actual_label} {actual[key]:,.0f} vs "
            f"{expected_label} {aligned[key]:,.0f} "
            f"(차이 {gap[key]:,.0f}명, 허용 {allowed[key]:,.0f}명). "
            f"어긋난 곳이 {int(over.sum())}곳입니다. "
            "두 파일이 같은 시점·같은 기준에서 뽑혔는지 확인해 주세요. "
            + _tolerance_hint()
        )

    differs = gap[gap > 0]
    if differs.empty:
        return
    key = differs.idxmax()
    warnings.warn(
        f"두 파일의 {label}가 조금 다릅니다. 어긋난 곳 "
        f"{len(differs)}곳, 가장 큰 차이 {_key_text(key)} — "
        f"{actual_label} {actual[key]:,.0f} vs "
        f"{expected_label} {aligned[key]:,.0f} "
        f"(차이 {differs[key]:,.0f}명, 허용 {allowed[key]:,.0f}명). "
        "허용 범위 안이라 각 파일의 값을 그대로 씁니다.",
        stacklevel=2,
    )

FRAME_NAMES = (
    "monthly",
    "age",
    "investment",
    "summary",
    "asset_change",
    "consulting",
    "transaction",
    "pension_transaction",
    "cash_flow",
    "revenue",
    "domestic_stock_rank",
    "domestic_stock_cap",
)

# 원본이 없으면 비어 있어도 되는 프레임. 나머지는 비어 있으면 멈춘다.
# 화면은 빈 프레임을 받으면 그 부분만 안내 상태로 그린다.
OPTIONAL_FRAMES = (
    "asset_change",
    "consulting",
    "transaction",
    "pension_transaction",
    "cash_flow",
    "revenue",
    "domestic_stock_rank",
    "domestic_stock_cap",
)

# 지점 하나가 통째로 빠질 수 있는 프레임. 다른 프레임은 모든 지점이 있어야
# 하고, 하나라도 없으면 두 원본의 범위가 어긋났다는 뜻이라 멈춘다. 시가총액
# 상위 종목은 그 지점이 한 종목도 거래하지 않으면 행이 하나도 없을 수
# 있으므로, 그때는 어느 지점이 빠졌는지 알리고 넘어간다.
PARTIAL_BRANCH_FRAMES = ("domestic_stock_cap",)

# 반드시 있어야 하는 컬럼. 없으면 어느 데이터의 무엇이 빠졌는지 알리며 멈춘다.
FRAME_REQUIRED: dict[str, tuple[str, ...]] = {
    "monthly": ("base_month", "branch_id", "branch_name", "customer_count"),
    "age": AGE_COLUMNS,
    "investment": INVESTMENT_COLUMNS,
    "summary": (
        "base_month",
        "branch_id",
        "branch_name",
        "customer_count",
        "average_age",
    ),
    "asset_change": (
        "base_month",
        "branch_id",
        "branch_name",
        "asset_type",
        "change_rate",
    ),
    "consulting": CONSULTING_COLUMNS,
    "transaction": TRANSACTION_COLUMNS,
    "pension_transaction": PENSION_TRANSACTION_COLUMNS,
    "cash_flow": CASH_FLOW_COLUMNS,
    "revenue": REVENUE_COLUMNS,
    "domestic_stock_rank": DOMESTIC_STOCK_RANK_COLUMNS,
    "domestic_stock_cap": DOMESTIC_STOCK_CAP_COLUMNS,
}

# 없어도 되는 컬럼. 원본에 없으면 비워 두고 화면에는 `-`로 표시한다.
# 값을 0으로 채우지 않는다. 0은 "없음"이 아니라 "0이라고 측정됨"을 뜻한다.
FRAME_OPTIONAL: dict[str, tuple[str, ...]] = {
    # net_assets는 억원, average_assets는 백만원 단위다
    # (→ dashboard/sources/asset.py).
    "monthly": (
        "total_assets",
        "transaction_customer_count",
        "app_user_count",
        "net_assets",
        "average_assets",
        # 자산4가 주는 값 (→ dashboard/sources/asset4.py).
        *MONTHLY_PENSION_COLUMNS,
        # 수익1의 '최종' 공통고객 수익. 단위는 **원**이라 위의 억원 컬럼과
        # 다르다(→ dashboard/sources/__init__.py 의 merge_revenue).
        "common_revenue",
    ),
    # 원본이 연령 구간 비중을 직접 담고 있으면 그 값을 화면까지 전달한다.
    "age": ("share",),
    "investment": (),
    "summary": (
        *SUMMARY_SHARE_COLUMNS,
        *SHARE_SOURCE_COUNT.values(),
        "customer_growth_yoy",
        # 자산2가 주는 값 (→ dashboard/sources/asset2.py).
        *ASSET_COUNT_COLUMNS,
        *ASSET_VALUE_COLUMNS,
        *ASSET_SHARE_COLUMNS,
    ),
    "asset_change": (),
    "consulting": (),
    "transaction": (),
    # 원본이 '기타' 상품의 거래고객수를 주지 않는다. 0으로 채우지 않고
    # 비워 둔 채 화면까지 넘긴다.
    "pension_transaction": ("trade_customer_count",),
    # 원본이 '전체' 채널의 입금·출금을 주지 않는다.
    "cash_flow": ("deposit_amount", "withdrawal_amount"),
    "revenue": REVENUE_OPTIONAL_COLUMNS,
    "domestic_stock_rank": DOMESTIC_STOCK_RANK_OPTIONAL_COLUMNS,
    "domestic_stock_cap": (),
}

FRAME_COLUMNS: dict[str, tuple[str, ...]] = {
    name: (*FRAME_REQUIRED[name], *FRAME_OPTIONAL[name])
    for name in FRAME_NAMES
}


@dataclass(frozen=True)
class DashboardData:
    """UI 계층에 전달하는 표준 데이터 묶음.

    반환된 DataFrame은 캐시된 객체다. 사용하는 쪽에서 직접 수정하지 않는다.
    """

    monthly: pd.DataFrame
    age: pd.DataFrame
    investment: pd.DataFrame
    summary: pd.DataFrame
    # 지점 × 월 × 상품 분류의 전월 대비 증감율. 원본이 없으면 비어 있다.
    asset_change: pd.DataFrame = field(default_factory=pd.DataFrame)
    # 지점 × 월 × 상담구분의 상담 토픽 목록. 원본이 없으면 비어 있다.
    consulting: pd.DataFrame = field(default_factory=pd.DataFrame)
    # 지점 × 월 × 상품 분류의 거래금액·거래고객수. 원본이 없으면 비어 있다.
    transaction: pd.DataFrame = field(default_factory=pd.DataFrame)
    # 위와 같되 연금 구분(개인연금·IRP·DC) 축이 하나 더 있다.
    pension_transaction: pd.DataFrame = field(default_factory=pd.DataFrame)
    # 지점 × 월 × 채널의 입금·출금·순입금. 원본이 없으면 비어 있다.
    cash_flow: pd.DataFrame = field(default_factory=pd.DataFrame)
    # 지점 × 월 × 수익 분류의 수익(원)과 비중. 원본이 없으면 비어 있다.
    revenue: pd.DataFrame = field(default_factory=pd.DataFrame)
    # 지점 × 월 × 순위의 국내주식 상위 종목. 원본이 없으면 비어 있다.
    domestic_stock_rank: pd.DataFrame = field(default_factory=pd.DataFrame)
    # 시가총액 상위 종목의 지점별 거래. 지점마다 행 수가 다를 수 있다.
    domestic_stock_cap: pd.DataFrame = field(default_factory=pd.DataFrame)
    # 원본에 '전체' 합계 행이 있으면 여기에 담는다. 지점 데이터와 섞으면 모든
    # 숫자가 두 배가 되므로 분리해 두고, 화면의 '전체' 값을 그릴 때 쓴다.
    # 원본에 없으면 빈 DataFrame이며, 그때는 지점에서 계산한다.
    monthly_total: pd.DataFrame = field(default_factory=pd.DataFrame)
    age_total: pd.DataFrame = field(default_factory=pd.DataFrame)
    investment_total: pd.DataFrame = field(default_factory=pd.DataFrame)
    summary_total: pd.DataFrame = field(default_factory=pd.DataFrame)
    asset_change_total: pd.DataFrame = field(default_factory=pd.DataFrame)
    consulting_total: pd.DataFrame = field(default_factory=pd.DataFrame)
    transaction_total: pd.DataFrame = field(default_factory=pd.DataFrame)
    pension_transaction_total: pd.DataFrame = field(
        default_factory=pd.DataFrame
    )
    cash_flow_total: pd.DataFrame = field(default_factory=pd.DataFrame)
    revenue_total: pd.DataFrame = field(default_factory=pd.DataFrame)
    domestic_stock_rank_total: pd.DataFrame = field(
        default_factory=pd.DataFrame
    )
    domestic_stock_cap_total: pd.DataFrame = field(
        default_factory=pd.DataFrame
    )

    def total_of(self, name: str) -> pd.DataFrame:
        """`monthly`·`age`·`investment`·`summary`에 대응하는 '전체' 행."""
        return getattr(self, f"{name}_total")

    @property
    def branch_names(self) -> list[str]:
        return sorted(self.monthly["branch_name"].unique().tolist())

    @property
    def months(self) -> list[str]:
        return sorted(self.monthly["base_month"].unique().tolist())


def reference_month(data: DashboardData) -> str:
    """화면 전체가 쓰는 기준 월.

    기본은 데이터에 들어 있는 최신 월이다. 상수를 손으로 고치지 않아도
    데이터가 갱신되면 기준 월이 따라간다.
    마감 월을 따로 지정해야 하면 환경 변수 `DASHBOARD_BASE_MONTH`로 고정한다.
    """
    months = data.months
    if not months:
        raise ValueError("데이터에 기준 월이 없습니다.")
    fixed = os.environ.get(BASE_MONTH_ENV, "").strip()
    if not fixed:
        return months[-1]
    if fixed not in months:
        raise ValueError(
            f"{BASE_MONTH_ENV}={fixed!r} 에 해당하는 데이터가 없습니다. "
            f"사용 가능한 월: {months[0]} ~ {months[-1]}"
        )
    return fixed


def load_dashboard_data(filters: dict | None = None) -> DashboardData:
    """대시보드 데이터를 반환한다.

    filters 예: {"branch_names": [...], "base_months": [...]}

    읽을 파일 이름은 원본 모듈(`dashboard/sources/<이름>.py`)의 `FILE`에
    적거나 그 모듈의 `FILE_ENV` 환경 변수로 지정한다.
    """
    source = (
        os.environ.get(DATA_SOURCE_ENV, "").strip().lower()
        or DEFAULT_DATA_SOURCE
    )
    if source not in SUPPORTED_DATA_SOURCES:
        raise ValueError(
            f"지원하지 않는 데이터 소스입니다: {source!r}. "
            f"사용 가능한 값: {', '.join(SUPPORTED_DATA_SOURCES)}"
        )

    data = _load_local_file()
    if filters:
        data = _apply_filters(data, filters)
    return data


# --- 실제 데이터(pkl) 읽기
# ----------------------------------------------------
def _candidate_paths(name: str) -> list[Path]:
    """파일 이름을 찾아볼 위치로 바꾼다.

    현재 작업 폴더를 기준으로 찾지 않는다. 그러면 어디서 실행했는지에 따라
    다른 파일을 읽게 된다. 항상 app.py가 있는 폴더를 기준으로 삼는다.
    """
    path = Path(name)
    if path.is_absolute():
        return [path]
    if path.parent == Path("."):
        # 파일 이름만 적었으면 data/ 안을 먼저 본다.
        return [DATA_DIR / path, PROJECT_DIR / path]
    return [PROJECT_DIR / path]


def _find_file(name: str, label: str) -> str:
    for candidate in (paths := _candidate_paths(name)):
        if candidate.is_file():
            return str(candidate)
    raise ValueError(
        f"{label} 파일을 찾을 수 없습니다: {name!r}. "
        f"찾아본 위치: {' , '.join(str(path) for path in paths)}"
    )


def _source_path(key: str) -> str:
    """원본 하나의 파일 경로.

    파일 이름과 환경 변수 이름은 그 원본 모듈에 있다. 필수가 아닌 원본은
    지정하지 않으면 빈 문자열을 돌려준다(→ dashboard.sources).

    필수가 아닌 원본의 파일을 아직 반입하지 않았으면 알리고 넘어간다.
    원본은 하나씩 들어오므로, 아직 없는 파일 하나 때문에 이미 들어온
    원본까지 못 보게 되는 쪽이 더 불편하다. 대신 환경 변수로 경로를 직접
    지정했는데 그 파일이 없으면 오타일 가능성이 크므로 그때는 멈춘다.
    """
    from dashboard import sources

    source = sources.find(key)
    given = os.environ.get(source.env, "").strip()
    name = given or source.file.strip()
    if name and not given and not source.required:
        if not any(path.is_file() for path in _candidate_paths(name)):
            warnings.warn(
                f"{source.label} 파일이 아직 없어 그 부분은 비워 둡니다: "
                f"{name!r}. 반입한 뒤 {DATA_DIR} 에 넣으면 화면에 나타납니다.",
                stacklevel=2,
            )
            return ""
    if not name:
        if not source.required:
            return ""
        raise ValueError(
            f"읽을 {source.label} 파일이 지정되지 않았습니다. "
            f"dashboard/sources/{key}.py 의 FILE 에 파일 이름을 적거나 "
            f"환경 변수 {source.env} 로 지정해 주세요."
        )
    return _find_file(name, source.label)


def _file_stamp(path: str) -> tuple[int, int]:
    """파일이 바뀌면 달라지는 값. 캐시 키로만 쓴다.

    지정하지 않은 원본은 빈 경로로 들어오며, 그때는 캐시 키도 비운다.
    """
    if not path:
        return (0, 0)
    stat = os.stat(path)
    return stat.st_mtime_ns, stat.st_size


def _load_local_file() -> DashboardData:
    """pkl 파일을 읽는다. 파일이 갱신되면 자동으로 다시 읽는다.

    `DASHBOARD_PROFILE_FILE`까지 지정하면 원본 파일들을 표준 형태로 바꿔 읽고,
    지정하지 않으면 표준 4개 프레임을 담은 dict 하나로 읽는다.
    지점 자산 파일은 없어도 되며, 없으면 자산 컬럼이 비어 있다.

    주의: pickle은 파일을 여는 것만으로 그 안의 코드가 실행될 수 있는 형식이다.
    사내에서 직접 만든 파일만 사용한다.
    """
    from dashboard import sources

    paths = {
        source.key: _source_path(source.key) for source in sources.SOURCES
    }
    if not paths["profile"]:
        monthly_path = paths["monthly"]
        return _read_pickle(monthly_path, _file_stamp(monthly_path))
    # lru_cache는 해시할 수 있는 인자만 받는다. 경로와 파일 도장을 키 순서가
    # 고정된 튜플로 만들어 넘긴다.
    return _read_source_pickles(
        tuple(paths.items()),
        tuple((key, _file_stamp(path)) for key, path in paths.items()),
    )


@lru_cache(maxsize=4)
def _read_pickle(path: str, stamp: tuple[int, int]) -> DashboardData:
    """캐시 키에 수정 시각과 크기를 넣어 파일이 바뀌면 다시 읽게 한다."""
    del stamp  # 캐시 키로만 쓴다.
    data = _from_pickle_object(pd.read_pickle(path), path)
    data = _normalize(data)
    validate_dashboard_data(data)
    return data


@lru_cache(maxsize=4)
def _read_source_pickles(
    paths: tuple[tuple[str, str], ...],
    stamps: tuple[tuple[str, tuple[int, int]], ...],
) -> DashboardData:
    del stamps  # 캐시 키로만 쓴다.
    # 원본을 표준 형태로 맞추는 일은 `sources`가 맡는다. 여기서 부르는 이유로
    # 두 모듈이 서로를 참조하므로, 순환을 피하려고 함수 안에서 가져온다.
    from dashboard import sources

    found = {key: path for key, path in paths if path}
    data = sources.assemble(
        {
            key: _read_source_frame(path, sources.find(key).label)
            for key, path in found.items()
        },
        found,
    )
    data = _normalize(data)
    validate_dashboard_data(data)
    return data


def _read_source_frame(path: str, label: str) -> pd.DataFrame:
    raw = pd.read_pickle(path)
    if not isinstance(raw, pd.DataFrame):
        raise ValueError(
            f"{label} 파일({path})의 내용이 DataFrame이 아니라"
            f" {type(raw).__name__} 입니다."
        )
    return raw


def _from_pickle_object(raw: object, path: str) -> DashboardData:
    """pkl에 담긴 객체를 `DashboardData`로 바꾼다.

    기대하는 형식은 4개 DataFrame을 담은 dict다.
        {"monthly": df, "age": df, "investment": df, "summary": df}
    각 DataFrame의 필수 컬럼은 `FRAME_COLUMNS`에 있다.
    """
    if isinstance(raw, DashboardData):
        return raw
    if not isinstance(raw, dict):
        raise ValueError(
            f"{path} 의 내용이 dict가 아니라 {type(raw).__name__} 입니다. "
            f"{', '.join(FRAME_NAMES)} 를 키로 갖는 dict로 저장하세요. "
            f"{', '.join(OPTIONAL_FRAMES)} 는 없어도 됩니다."
        )
    required = [name for name in FRAME_NAMES if name not in OPTIONAL_FRAMES]
    missing = [name for name in required if name not in raw]
    if missing:
        raise ValueError(
            f"{path} 에 다음 데이터가 없습니다: {', '.join(missing)}. "
            f"필요한 키: {', '.join(required)}"
        )

    frames: dict[str, pd.DataFrame] = {}
    for name in FRAME_NAMES:
        frame = raw.get(name, pd.DataFrame())
        if frame.empty and name in OPTIONAL_FRAMES:
            frames[name] = frame
            continue
        if not isinstance(frame, pd.DataFrame):
            raise ValueError(
                f"{path} 의 {name!r} 이 DataFrame이 아니라"
                f" {type(frame).__name__} 입니다."
            )
        frames[name] = (
            frame.rename(columns=SOURCE_COLUMN_MAP)
            if SOURCE_COLUMN_MAP
            else frame
        )
    return DashboardData(**frames)


# --- 정규화와 검증 -----------------------------------------------------------
_SORT_KEY = ["base_month", "branch_id"]

# 기본 정렬 키로는 순서가 정해지지 않는 프레임. 한 지점 안에서 행 순서 자체가
# 뜻을 갖는 경우에만 적는다. pandas의 기본 정렬은 같은 키끼리의 순서를
# 보장하지 않아, 적어 두지 않으면 번호 순이 흐트러진다.
_FRAME_SORT_KEY: dict[str, list[str]] = {
    "consulting": [
        "base_month",
        "branch_id",
        "consulting_type",
        "topic_rank",
    ],
    "transaction": ["base_month", "branch_id", "product_type"],
    "pension_transaction": [
        "base_month",
        "branch_id",
        "pension_type",
        "product_type",
    ],
    "cash_flow": ["base_month", "branch_id", "channel"],
    "revenue": ["base_month", "branch_id", "revenue_type"],
    "domestic_stock_rank": ["base_month", "branch_id", "stock_rank"],
    "domestic_stock_cap": ["base_month", "branch_id", "stock_name"],
}

# 정해진 값만 허용하는 분류 컬럼. (프레임, 컬럼, 허용값) 순이며, 허용값의
# 순서가 곧 화면에 나오는 순서다. 여기 없는 값을 만나면 그 값을 알리며
# 멈춘다(→ _to_category).
_CATEGORY_COLUMNS: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("asset_change", "asset_type", ALL_ASSET_TYPES),
    ("transaction", "product_type", ALL_TRADE_PRODUCT_TYPES),
    ("pension_transaction", "pension_type", PENSION_TYPES),
    (
        "pension_transaction",
        "product_type",
        ALL_PENSION_TRADE_PRODUCT_TYPES,
    ),
    ("cash_flow", "channel", ALL_CASH_FLOW_CHANNELS),
    ("revenue", "revenue_type", ALL_REVENUE_TYPES),
)

# 정수로 담을 컬럼. 이름이 count로 끝나는 컬럼은 자동으로 정수가 된다.
_INT_COLUMNS = ("total_assets", "topic_rank", "stock_rank")

_MONTH_PATTERN = r"\d{4}-(0[1-9]|1[0-2])"

# 마케팅 동의 여부를 참·거짓으로 읽을 때 허용하는 표기.
# 원본이 "Y"/"N" 같은 문자열이면 bool로 그냥 바꿀 수 없다. 빈 문자열이 아닌
# 모든 문자열은 참이 되어 "N"까지 동의로 뒤집히기 때문이다.
_TRUE_TEXTS = frozenset({"true", "t", "y", "yes", "1", "동의", "o"})
_FALSE_TEXTS = frozenset(
    {"false", "f", "n", "no", "0", "미동의", "비동의", "불원", "x"}
)


def _normalize(data: DashboardData) -> DashboardData:
    """컬럼 순서, 타입, 정렬을 표준 형태로 맞춘다.

    값을 조용히 고치지 않는다. 읽을 수 없는 값을 만나면 어느 컬럼의 어떤
    값이 문제인지 알려주며 멈춘다.

    원본에 들어 있는 '전체' 합계 행은 지점 데이터에서 분리한다. 그대로 두면
    합계가 지점 하나로 섞여 모든 숫자가 두 배가 된다.
    """
    frames = {
        "monthly": _normalize_frame(data.monthly, "monthly"),
        "age": _normalize_frame(data.age, "age"),
        "investment": _normalize_frame(
            _reshape_investment(data.investment), "investment"
        ),
        "summary": _normalize_frame(data.summary, "summary"),
        "asset_change": _normalize_frame(data.asset_change, "asset_change"),
        "consulting": _normalize_frame(data.consulting, "consulting"),
        "transaction": _normalize_frame(data.transaction, "transaction"),
        "pension_transaction": _normalize_frame(
            data.pension_transaction, "pension_transaction"
        ),
        "cash_flow": _normalize_frame(data.cash_flow, "cash_flow"),
        "revenue": _normalize_frame(data.revenue, "revenue"),
        "domestic_stock_rank": _normalize_frame(
            data.domestic_stock_rank, "domestic_stock_rank"
        ),
        "domestic_stock_cap": _normalize_frame(
            data.domestic_stock_cap, "domestic_stock_cap"
        ),
    }
    for name, column, categories in _CATEGORY_COLUMNS:
        if frames[name].empty:
            continue
        frames[name][column] = _to_category(
            frames[name][column], categories, name, column
        )
    # 분류·참거짓·비율 변환을 먼저 끝낸다. '전체' 행도 같은 처리를 거쳐야
    # 화면에서 지점과 똑같이 다룰 수 있다.
    frames["age"]["age_group"] = _to_category(
        frames["age"]["age_group"],
        ALL_AGE_GROUPS,
        "age",
        "age_group",
        AGE_GROUP_CODES,
    )
    frames["investment"]["investment_type"] = _to_category(
        frames["investment"]["investment_type"],
        INVESTMENT_TYPES,
        "investment",
        "investment_type",
        INVESTMENT_TYPE_CODES,
    )
    frames["investment"]["marketing_consent"] = _to_bool_column(
        frames["investment"]["marketing_consent"],
        "investment",
        "marketing_consent",
    )
    frames["summary"] = _fill_summary_shares(frames["summary"])

    # 분류 컬럼은 위에서 Categorical이 되므로 여기서 한 번 더 줄을 세운다.
    # 글자 그대로 정렬하면 '국내ETF'가 '전체'보다 앞이라는 식으로 원본이
    # 정한 순서와 달라진다.
    for name, sort_key in _FRAME_SORT_KEY.items():
        if not frames[name].empty:
            frames[name] = (
                frames[name]
                .sort_values(sort_key)
                .reset_index(drop=True)
            )

    # 원본의 '전체' 행은 지점 데이터와 섞지 않고 따로 들고 간다. 화면의 '전체'
    # 값은 이 행을 그대로 쓴다. 지점에서 되계산하면 원본과 달라지기 때문이다.
    totals: dict[str, pd.DataFrame] = {}
    for name in FRAME_NAMES:
        frames[name], totals[name] = _split_source_total(frames[name], name)

    normalized = DashboardData(
        **frames, **{f"{name}_total": totals[name] for name in FRAME_NAMES}
    )
    _check_source_totals(normalized)
    return normalized


def _reshape_investment(frame: pd.DataFrame) -> pd.DataFrame:
    """동의·불원이 각각 인원수 컬럼이면 표준 형태(한 줄에 한 구분)로 편다.

    이미 `marketing_consent` 컬럼이 있으면 그대로 둔다.
    """
    if "marketing_consent" in frame.columns:
        return frame
    wide = [
        column
        for column in INVESTMENT_WIDE_COLUMNS
        if column not in frame.columns
    ]
    if wide:
        # 표준 형태도 넓은 형태도 아니면 아래 컬럼 검사에서 걸린다.
        return frame

    keys = ["base_month", "branch_id", "branch_name", "investment_type"]
    parts = []
    for column, consent in (
        ("consent_customer_count", True),
        ("non_consent_customer_count", False),
    ):
        part = frame.loc[:, [*keys, column]].rename(
            columns={column: "customer_count"}
        )
        part["marketing_consent"] = consent
        parts.append(part)
    return pd.concat(parts, ignore_index=True)


def _fill_summary_shares(summary: pd.DataFrame) -> pd.DataFrame:
    """비율 컬럼을 채운다.

    원본이 비율을 직접 주면 그 값을 그대로 쓴다. 인원수로 되돌렸다가
    비율을 다시 만들면 반올림 때문에 화면 숫자가 원본과 달라진다.
    원본이 인원수만 주는 경우에만 인원수에서 비율을 계산한다.
    """
    result = summary.copy()
    for share, count in SHARE_SOURCE_COUNT.items():
        if result[share].notna().any():
            continue
        if count not in result.columns or result[count].isna().all():
            continue
        result[share] = (
            result[count] / result["customer_count"] * 100.0
        ).where(result["customer_count"] > 0)
    return result


def _split_source_total(
    frame: pd.DataFrame, name: str
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """원본의 '전체' 합계 행을 지점 행과 분리한다."""
    if frame.empty:
        return frame, frame
    is_total = frame["branch_name"] == TOTAL_LABEL
    if not is_total.any():
        return frame, frame.iloc[0:0]
    branches = frame[~is_total].reset_index(drop=True)
    if branches.empty:
        raise ValueError(
            f"{name} 데이터에 '{TOTAL_LABEL}' 행만 있고 지점 행이 없습니다."
        )
    return branches, frame[is_total].reset_index(drop=True)


# '전체' 행을 지점 합계와 대조할 때 쓰는 묶음 기준.
# 인원수처럼 더할 수 있는 값만 대조한다. 비율은 원본이 어떤 기준으로 계산했는지
# 알 수 없어 지점 값에서 되만들 수 없다(→ 그 값은 파일을 그대로 믿는다).
_TOTAL_CHECK_KEYS: dict[str, tuple[str, ...]] = {
    "monthly": (),
    "age": ("age_group",),
    "investment": ("investment_type", "marketing_consent"),
    "summary": (),
    "asset_change": ("asset_type",),
    "consulting": ("consulting_type", "topic_rank"),
    "transaction": ("product_type",),
    "pension_transaction": ("pension_type", "product_type"),
    "cash_flow": ("channel",),
    "revenue": ("revenue_type",),
    "domestic_stock_rank": ("stock_rank",),
    "domestic_stock_cap": ("stock_name",),
}
_TOTAL_CHECK_COLUMNS: dict[str, tuple[str, ...]] = {
    # average_assets는 평균이라 더할 수 없으므로 대조하지 않는다.
    "monthly": (
        "customer_count",
        "total_assets",
        "net_assets",
        *MONTHLY_PENSION_COLUMNS,
    ),
    "age": ("customer_count",),
    "investment": ("customer_count",),
    "summary": ("customer_count", *ASSET_ADDITIVE_COLUMNS),
    # 증감율은 더할 수 없다. '전체' 상품 행도 14개의 합이 아니라 따로 계산된
    # 값이므로 대조하지 않는다.
    "asset_change": (),
    # 상담은 지점마다 토픽이 다르다. '전체'의 토픽은 지점 토픽의 합이 아니라
    # 따로 뽑은 목록이므로 대조하지 않는다.
    "consulting": (),
    # 거래금액은 억원 소수라 지점 27곳을 더하면 반올림만으로 '전체'와
    # 어긋날 수 있다. 더해서 확인하는 값은 인원수만 둔다(→ AGENTS.md §9).
    "transaction": ("trade_customer_count",),
    "pension_transaction": ("trade_customer_count",),
    # 입금·출금·순입금 모두 금액이라 같은 이유로 대조하지 않는다.
    "cash_flow": (),
    # 수익도 금액이라 대조하지 않는다. 원 단위 실수로 담겨 오면 지점 27곳을
    # 더하는 것만으로 '전체' 행과 어긋날 수 있고, '전체'가 지점 합이라는
    # 보장도 없다. 비중은 더할 수 없으므로 애초에 대조 대상이 아니다.
    "revenue": (),
    # 상품은 지점마다 상위 종목이 다르다. '전체'의 1위와 어느 지점의 1위는
    # 다른 종목이므로 순위를 맞춰 더하는 것 자체가 뜻이 없다.
    "domestic_stock_rank": (),
    # 시가총액 상위 종목은 '전체'와 지점이 같은 종목을 담고 있어 종목별로
    # 더해 볼 수는 있다. 그래도 대조하지 않는다. '전체'가 지점 27곳만
    # 합한 값인지, 그 밖의 고객까지 포함한 값인지 확인되지 않았다. 확인되면
    # 여기에 trade_customer_count 를 넣는다(→ AGENTS.md §17).
    "domestic_stock_cap": (),
}


def _check_source_totals(data: DashboardData) -> None:
    """원본의 '전체' 행이 지점 합계와 맞는지 확인한다.

    화면은 '전체' 행을 그대로 표시하므로, 그 값이 지점과 앞뒤가 맞는지 여기서
    한 번 확인한다. 다르면 어느 쪽이 맞는지 사람이 판단해야 하므로 멈춘다.
    """
    for name in FRAME_NAMES:
        total = data.total_of(name)
        if total.empty:
            continue
        branches = getattr(data, name)
        keys = ["base_month", *_TOTAL_CHECK_KEYS[name]]
        # 원본에 없는 컬럼은 대조하지 않는다. 비어 있는 값을 0으로 보고
        # 비교하면
        # 실제로는 맞는 데이터를 틀렸다고 알리게 된다.
        columns = [
            column
            for column in _TOTAL_CHECK_COLUMNS[name]
            if branches[column].notna().all() and total[column].notna().all()
        ]
        if not columns:
            continue
        computed = branches.groupby(keys, observed=True)[columns].sum()
        given = total.set_index(keys)[columns]
        for key in given.index:
            if key not in computed.index:
                continue
            for column in columns:
                # 소수로 담기는 금액 컬럼이 있으므로 버리지 않고 반올림한다.
                # 정수 컬럼은 반올림해도 값이 그대로다.
                expected = round(computed.loc[key, column])
                actual = round(given.loc[key, column])
                if expected != actual:
                    label = (
                        key
                        if isinstance(key, str)
                        else " ".join(map(str, key))
                    )
                    raise ValueError(
                        f"원본의 '{TOTAL_LABEL}' 행과 지점 합계가 다릅니다. "
                        f"{name} {label} {column} — "
                        f"지점 합계 {expected:,} vs 전체 행 {actual:,}. "
                        "어느 쪽이 맞는지 확인한 뒤 원본을 맞춰 주세요."
                    )


def _normalize_frame(frame: pd.DataFrame, name: str) -> pd.DataFrame:
    """컬럼 순서·타입·정렬을 표준 형태로 맞춘다.

    선택 컬럼은 원본에 있을 때만 검사하고, 없으면 결측으로 남긴다.
    원본이 없어도 되는 프레임은 비어 있으면 그대로 둔다.
    """
    if frame.empty and name in OPTIONAL_FRAMES:
        return pd.DataFrame(columns=list(FRAME_COLUMNS[name]))
    required = FRAME_REQUIRED[name]
    missing = [column for column in required if column not in frame.columns]
    if missing:
        raise ValueError(
            f"{name} 데이터에 필수 컬럼이 없습니다: {', '.join(missing)}. "
            f"필요한 컬럼: {', '.join(required)}"
        )
    present = [
        column for column in FRAME_COLUMNS[name] if column in frame.columns
    ]
    optional = set(FRAME_OPTIONAL[name])
    normalized = frame.loc[:, present].copy()
    normalized["base_month"] = to_month_column(normalized["base_month"], name)
    normalized["branch_id"] = _to_text_column(
        normalized["branch_id"], name, "branch_id"
    )
    normalized["branch_name"] = _to_text_column(
        normalized["branch_name"], name, "branch_name"
    )
    for column in present:
        values = normalized[column]
        if column in optional and values.isna().any():
            # 일부만 비어 있는 선택 컬럼. 빈 칸은 그대로 두고 소수로 담는다.
            normalized[column] = _to_optional_float_column(
                values, name, column
            )
        elif column.endswith("count") or column in _INT_COLUMNS:
            normalized[column] = _to_int_column(values, name, column)
        elif column in _FLOAT_COLUMNS:
            normalized[column] = _to_float_column(values, name, column)
    for column in FRAME_OPTIONAL[name]:
        if column not in normalized.columns:
            normalized[column] = np.nan
    return (
        normalized.loc[:, list(FRAME_COLUMNS[name])]
        .sort_values(_FRAME_SORT_KEY.get(name, _SORT_KEY))
        .reset_index(drop=True)
    )


def _samples(values: pd.Series, mask: pd.Series, limit: int = 3) -> str:
    """오류 메시지에 넣을 실제 값 예시. 원인을 바로 찾을 수 있게 한다."""
    return ", ".join(
        repr(value) for value in values[mask].head(limit).tolist()
    )


def plain_text(series: pd.Series) -> pd.Series:
    """숫자로 들어온 값도 사람이 쓰는 표기로 바꾼다.

    원본이 숫자면 pandas가 `202601.0`, `1.0` 같은 소수점 표기를 만든다.
    그대로 두면 월 형식 검사와 지점 코드 대조가 어긋난다.
    """
    return series.astype(str).str.strip().str.replace(r"\.0+$", "", regex=True)


def to_month_column(series: pd.Series, name: str) -> pd.Series:
    """기준 월을 `YYYY-MM` 문자열로 맞춘다.

    원본이 숫자 `202601`이든 문자열 `2026-01`이든 날짜 `2026-01-31`이든 읽는다.
    """
    text = plain_text(series)
    compact = text.str.fullmatch(r"\d{6}")
    text = text.mask(
        compact, text.str.slice(0, 4) + "-" + text.str.slice(4, 6)
    )
    text = text.str.slice(0, 7)
    invalid = ~text.str.fullmatch(_MONTH_PATTERN)
    if invalid.any():
        raise ValueError(
            f"{name}.base_month 를 YYYY-MM으로 읽을 수 없는 값이"
            f" {int(invalid.sum())}건 "
            f"있습니다. 예: {_samples(series, invalid)}. "
            "허용되는 형태: 202601, '2026-01', '2026-01-31'"
        )
    return text


def _to_text_column(series: pd.Series, name: str, column: str) -> pd.Series:
    """지점 코드·지점명처럼 이름표로 쓰는 값. 숫자 코드도 문자열로 맞춘다."""
    text = plain_text(series)
    blank = text.isin(("", "nan", "None", "NaT"))
    if blank.any():
        raise ValueError(
            f"{name}.{column} 이 비어 있는 행이 {int(blank.sum())}건 있습니다."
        )
    return text


def to_numeric_column(series: pd.Series, name: str, column: str) -> pd.Series:
    """숫자로 바꾼다. 빈 칸이나 읽을 수 없는 값을 0으로 덮지 않고 멈춘다."""
    numbers = pd.to_numeric(series, errors="coerce")
    unreadable = numbers.isna()
    if unreadable.any():
        raise ValueError(
            f"{name}.{column} 에 숫자로 읽을 수 없는 값이"
            f" {int(unreadable.sum())}건 있습니다. "
            f"예: {_samples(series, unreadable)}. "
            "0으로 처리해야 한다면 원본 데이터에서 직접 0을 채워 주세요."
        )
    return numbers


def strip_number_marks(series: pd.Series) -> pd.Series:
    """`-1,234`·`+5`처럼 표기가 붙어 온 값에서 숫자만 남긴다.

    숫자로 들어오는 파일도 있으므로 글일 때만 손댄다. 읽을 수 없는 값은
    여기서 버리지 않고 그대로 넘겨 `to_numeric_column`이 알리게 한다.
    """
    if not pd.api.types.is_object_dtype(series):
        return series
    return (
        series.astype(str)
        .str.strip()
        .str.replace(",", "", regex=False)
        .str.removeprefix("+")
    )


def check_not_negative(
    numbers: pd.Series, label: str, column: str
) -> pd.Series:
    """음수가 있으면 멈춘다. 인원수나 시가총액이 음수일 수는 없다.

    그런 값이 나왔다면 원본을 읽는 방법이 틀렸다는 뜻이다.
    """
    negative = numbers < 0
    if negative.any():
        raise ValueError(
            f"{label} 파일의 {column} 에 음수가"
            f" {int(negative.sum())}건 있습니다. "
            f"예: {numbers[negative].head(3).tolist()}"
        )
    return numbers


def to_label_column(
    series: pd.Series, label: str, column: str, *, required: bool
) -> pd.Series:
    """이름표로 쓰는 글 컬럼. 비어 있는 표기를 빈 문자열 하나로 맞춘다.

    `required`면 비어 있는 행에서 멈춘다. 빈 칸을 그대로 넘기면 화면에는 빈
    셀로 나타나, 원본이 비어 있는 것인지 읽다가 흘린 것인지 구분할 수 없다.
    """
    text = plain_text(series)
    blank = text.isin(("", "nan", "None", "NaT"))
    if required and blank.any():
        raise ValueError(
            f"{label} 파일의 {column} 이 비어 있는 행이"
            f" {int(blank.sum())}건 있습니다."
        )
    return text.mask(blank, "")


def _to_int_column(series: pd.Series, name: str, column: str) -> pd.Series:
    numbers = to_numeric_column(series, name, column)
    negative = numbers < 0
    if negative.any():
        raise ValueError(
            f"{name}.{column} 에 음수가 {int(negative.sum())}건 있습니다. "
            f"예: {_samples(series, negative)}"
        )
    return numbers.round().astype(int)


def _to_float_column(series: pd.Series, name: str, column: str) -> pd.Series:
    return to_numeric_column(series, name, column).astype(float)


def _to_optional_float_column(
    series: pd.Series, name: str, column: str
) -> pd.Series:
    """선택 컬럼을 소수로 바꾼다.

    처음부터 비어 있던 칸은 비운 채로 둔다. 원본에 값이 있는데 숫자로 읽을 수
    없는 경우에만 멈춘다. 읽지 못한 값을 결측으로 바꿔 넘기지 않는다.
    """
    missing = series.isna()
    numbers = pd.to_numeric(series, errors="coerce")
    unreadable = numbers.isna() & ~missing
    if unreadable.any():
        raise ValueError(
            f"{name}.{column} 에 숫자로 읽을 수 없는 값이"
            f" {int(unreadable.sum())}건 있습니다. "
            f"예: {_samples(series, unreadable)}"
        )
    return numbers.astype(float)


def _to_category(
    series: pd.Series,
    categories: tuple[str, ...],
    name: str,
    column: str,
    codes: dict[str, str] | None = None,
) -> pd.Categorical:
    """정해진 분류값만 허용한다. 원본이 숫자 코드면 `codes`로 이름을 붙인다.

    모르는 값을 그냥 Categorical로 만들면 조용히 결측이 되고, 나중에
    "누락값이 있습니다"라는 엉뚱한 메시지로만 드러난다.
    """
    values = plain_text(series)
    if codes:
        values = values.map(lambda value: codes.get(value, value))
    unknown = sorted(set(values) - set(categories))
    if unknown:
        hint = (
            ""
            if codes
            else " 원본이 숫자 코드라면 data.py의 코드표에"
            " 코드→이름을 적어 주세요."
        )
        raise ValueError(
            f"{name}.{column} 에 정의되지 않은 값이 있습니다:"
            f" {', '.join(unknown)}. "
            f"허용되는 값: {', '.join(categories)}.{hint}"
        )
    return pd.Categorical(values, categories=categories, ordered=True)


def _to_bool_column(series: pd.Series, name: str, column: str) -> pd.Series:
    """참·거짓 컬럼. 문자열 표기도 읽되 모르는 표기는 참으로 넘기지 않는다."""
    if pd.api.types.is_bool_dtype(series):
        return series.astype(bool)

    texts = series.astype(str).str.strip().str.lower()
    is_true = texts.isin(_TRUE_TEXTS)
    is_false = texts.isin(_FALSE_TEXTS)
    unknown = ~(is_true | is_false)
    if unknown.any():
        raise ValueError(
            f"{name}.{column} 을 참·거짓으로 읽을 수 없는 값이"
            f" {int(unknown.sum())}건 "
            f"있습니다. 예: {_samples(series, unknown)}. "
            f"허용되는 표기: {', '.join(sorted(_TRUE_TEXTS | _FALSE_TEXTS))}"
        )
    return is_true


def validate_dashboard_data(
    data: DashboardData,
    *,
    expected_months: tuple[str, ...] | None = None,
    expected_branch_count: int | None = None,
) -> None:
    """데이터가 스스로 앞뒤가 맞는지 검증한다.

    기본 검사는 데이터가 스스로 앞뒤가 맞는지만 본다. 기간이 몇 개월인지,
    지점이 몇 개인지는 실제 데이터에서 얼마든지 달라질 수 있으므로 묻지 않는다.
    `expected_months`·`expected_branch_count`를 주면 그 값까지 확인하는데,
    이는 내용이 정해진 표본 파일을 점검할 때만 쓴다(→ tests/).
    """
    for name in FRAME_NAMES:
        frame = getattr(data, name)
        if not isinstance(frame, pd.DataFrame):
            raise ValueError(f"{name}이 DataFrame이 아닙니다.")
        if frame.empty:
            if name in OPTIONAL_FRAMES:
                continue
            raise ValueError(f"{name} 데이터가 비어 있습니다.")
        if frame.loc[:, list(FRAME_REQUIRED[name])].isna().to_numpy().any():
            raise ValueError(f"{name}의 필수 컬럼에 누락값이 있습니다.")

    # 원본이 없어 비어 있는 프레임은 기간·지점 대조에서 뺀다.
    frames = tuple(
        (name, getattr(data, name))
        for name in FRAME_NAMES
        if not getattr(data, name).empty
    )
    months = sorted(data.monthly["base_month"].unique())
    branch_ids = set(data.monthly["branch_id"].unique())

    # 기간은 monthly가 기준이다. 연령·투자성향·요약은 특정 시점
    # 스냅샷만 있을 수 있으므로 monthly의 월 안에 들어 있기만 하면 된다.
    # 지점은 모두 같아야 한다.
    for name, frame in frames:
        extra = sorted(set(frame["base_month"].unique()) - set(months))
        if extra:
            raise ValueError(
                f"{name}에 monthly에 없는 기준 월이 있습니다:"
                f" {', '.join(extra)}. "
                f"monthly: {months[0]} ~ {months[-1]} ({len(months)}개월)"
            )
        _check_branches(frame, branch_ids, name)
    if not _is_one_to_one(data.monthly, "branch_id", "branch_name"):
        raise ValueError("branch_id와 branch_name이 1:1로 대응하지 않습니다.")

    if expected_months is not None and tuple(months) != tuple(expected_months):
        raise ValueError(
            f"기준 월이 예상 범위와 다릅니다: {months[0]} ~ {months[-1]}"
        )
    if (
        expected_branch_count is not None
        and len(branch_ids) != expected_branch_count
    ):
        raise ValueError(
            f"지점 수가 {expected_branch_count}개가 아닙니다:"
            f" {len(branch_ids)}"
        )

    monthly = data.monthly
    for column in ("transaction_customer_count", "app_user_count"):
        _check_not_greater(monthly, column, "customer_count", "monthly")

    key = ["base_month", "branch_id"]
    base = monthly.set_index(key)["customer_count"]

    age_sum = data.age.groupby(key, observed=True)["customer_count"].sum()
    _check_matches_customer_count(age_sum, base, "연령 구간별 고객 수 합계")

    # 투자성향은 일부 분류를 화면에서 제외할 수 있으므로 고객 수를 넘지만
    # 않으면 된다.
    # 분류별 합계가 고객 수와 정확히 맞는지는 원본을 읽는 어댑터에서 확인한다.
    invest_sum = data.investment.groupby(key, observed=True)[
        "customer_count"
    ].sum()
    _check_not_exceeding_customer_count(
        invest_sum, base, "투자성향별 고객 수 합계"
    )

    summary = data.summary.set_index(key)
    _check_matches_customer_count(
        summary["customer_count"], base, "요약 데이터의 고객 수"
    )
    for column in SHARE_SOURCE_COUNT.values():
        if summary[column].notna().any():
            _check_not_greater(summary, column, "customer_count", "summary")
    for column in (*SUMMARY_SHARE_COLUMNS, *ASSET_SHARE_COLUMNS):
        _check_percent_range(summary[column], "summary", column)
    outside = ~summary["average_age"].between(0, 120)
    if outside.any():
        raise ValueError(
            "summary.average_age가 0~120 범위를 벗어난 행이"
            f" {int(outside.sum())}건 있습니다. "
            f"예: {_samples(summary['average_age'], outside)}"
        )


def _check_branches(
    frame: pd.DataFrame, branch_ids: set[str], name: str
) -> None:
    """프레임의 지점이 monthly와 맞는지 본다.

    monthly에 없는 지점이 있으면 두 원본이 다른 범위에서 뽑혔다는 뜻이라
    언제나 멈춘다.

    빠진 지점은 프레임에 따라 다르다. 대부분은 모든 지점이 있어야 하므로
    멈추고, 그 지점이 대상 종목을 하나도 거래하지 않았을 수 있는 프레임은
    어느 지점이 빠졌는지 알리고 넘어간다(→ PARTIAL_BRANCH_FRAMES).
    """
    found = set(frame["branch_id"].unique())
    unknown = sorted(found - branch_ids)
    if unknown:
        raise ValueError(
            f"{name}에 monthly에 없는 지점이 {len(unknown)}곳 있습니다: "
            f"{', '.join(unknown[:5])}. "
            "두 원본이 같은 범위에서 뽑혔는지 확인해 주세요."
        )
    missing = sorted(branch_ids - found)
    if not missing:
        return
    if name not in PARTIAL_BRANCH_FRAMES:
        raise ValueError(
            f"{name}의 지점이 monthly와 다릅니다. monthly 지점 수:"
            f" {len(branch_ids)}"
        )
    warnings.warn(
        f"{name}에 행이 하나도 없는 지점이 {len(missing)}곳 있습니다: "
        f"{', '.join(missing[:5])}. "
        "그 지점은 대상 종목을 거래하지 않았다는 뜻으로 보고 넘어갑니다.",
        stacklevel=2,
    )


def _is_one_to_one(frame: pd.DataFrame, left: str, right: str) -> bool:
    pairs = frame.loc[:, [left, right]].drop_duplicates()
    return bool(pairs[left].is_unique and pairs[right].is_unique)


def _check_not_greater(
    frame: pd.DataFrame, column: str, limit: str, name: str
) -> None:
    over = frame[column] > frame[limit]
    if over.any():
        row = frame[over].iloc[0]
        raise ValueError(
            f"{name}.{column}이 {limit}보다 큰 행이 {int(over.sum())}건"
            " 있습니다. "
            f"예: {row[column]} > {row[limit]}"
        )


def _check_percent_range(series: pd.Series, name: str, column: str) -> None:
    """비율 컬럼이 0~100 범위 안에 있는지 확인한다.

    원본이 0~1 비율인데 100을 곱하지 않았거나 반대로 두 번 곱한 경우를 잡는다.
    """
    values = series.dropna()
    if values.empty:
        return
    outside = ~values.between(0, 100)
    if outside.any():
        raise ValueError(
            f"{name}.{column}이 0~100 범위를 벗어난 행이"
            f" {int(outside.sum())}건 있습니다. "
            f"예: {_samples(values, outside)}. "
            "원본이 0~1 비율이면 100을 곱해야 하고, 이미 %라면 그대로 써야"
            " 합니다."
        )


def _check_not_exceeding_customer_count(
    actual: pd.Series, base: pd.Series, label: str
) -> None:
    """합계가 고객 수를 넘지 않는지 확인한다.

    두 값이 다른 원본에서 오므로 추출 시점이 하루만 달라도 몇 명이 어긋난다.
    허용 범위만큼은 넘어도 멈추지 않는다(→ COUNT_TOLERANCE).
    """
    aligned = actual.reindex(base.index).dropna()
    if aligned.empty:
        return
    compared = base.reindex(aligned.index)
    over = (aligned - compared) > count_tolerance(compared)
    if not over.any():
        return
    month, branch_id = aligned.index[over][0]
    raise ValueError(
        f"{label}가 고객 수보다 크게 많은 행이 {int(over.sum())}건"
        " 있습니다. "
        f"예: {month} {branch_id} — 합계 {aligned[over].iloc[0]:,.0f} vs"
        f" 고객 수 {compared[over].iloc[0]:,.0f}. " + _tolerance_hint()
    )


def _check_matches_customer_count(
    actual: pd.Series, base: pd.Series, label: str
) -> None:
    """합계가 고객 수와 다르면 어느 월·지점이 얼마나 어긋났는지 알려준다.

    비교 대상은 `actual`에 들어 있는 월로 한정한다. 연령·투자성향·요약이
    특정 시점 스냅샷만 담고 있어도 그 시점만 정확히 확인한다.

    두 값이 다른 원본에서 오므로 추출 시점이 하루만 달라도 몇 명이 어긋난다.
    허용 범위 안이면 알리고 넘어간다(→ check_count_gap).
    """
    scope = base.index.get_level_values("base_month").isin(
        actual.index.get_level_values("base_month").unique()
    )
    base = base[scope]
    if base.empty:
        return
    check_count_gap(
        actual.reindex(base.index), base, label, label, "월별 고객 수"
    )


def _apply_filters(data: DashboardData, filters: dict) -> DashboardData:
    branch_names = filters.get("branch_names")
    base_months = filters.get("base_months")

    def _filter(frame: pd.DataFrame) -> pd.DataFrame:
        result = frame
        if frame.empty:
            return frame
        if branch_names:
            result = result[result["branch_name"].isin(branch_names)]
        if base_months:
            result = result[result["base_month"].isin(base_months)]
        return result.reset_index(drop=True)

    def _filter_total(frame: pd.DataFrame) -> pd.DataFrame:
        # 지점을 걸러내면 원본의 '전체' 행은 더 이상 화면과 맞지 않는다. 그대로
        # 두면 걸러낸 지점까지 포함한 값이 '전체'로 남는다.
        if branch_names or frame.empty:
            return pd.DataFrame()
        if base_months:
            return frame[frame["base_month"].isin(base_months)].reset_index(
                drop=True
            )
        return frame

    return DashboardData(
        **{name: _filter(getattr(data, name)) for name in FRAME_NAMES},
        **{
            f"{name}_total": _filter_total(data.total_of(name))
            for name in FRAME_NAMES
        },
    )
