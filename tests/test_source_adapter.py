"""실제 원본 pkl을 표준 형태로 읽는 어댑터 검증.

원본 형태 — 월별 공통고객 수, 지점별 프로필 한 시점, 월별 지점 자산(자산1),
지점별 자산 프로필 한 시점(자산2), 상품 분류별 증감율(자산3), 월별 연금
자산(자산4), 지점 상담 토픽(상담1), 월별 지점 거래(거래1), 월별 지점 연금
거래(거래2), 월별 지점 입출금(거래3), 월별 지점 수익(수익1).
자산·상담·거래·수익 파일은 없어도 되며, 없으면 그 컬럼과 프레임이 비어
있어야 한다.
여기서 만드는 표본은 실제 컬럼 이름만 흉내 내며 개인정보를 담지 않는다.
"""

from __future__ import annotations

import re

import numpy as np
import pandas as pd
import pytest

from dashboard import metrics as shared
from dashboard.tabs.customer import metrics
from dashboard.data import (
    AGE_GROUPS,
    ALL_AGE_GROUPS,
    ASSET_GROUPS,
    BALANCE_SHARE_GROUPS,
    DIGITAL_MENU_CATEGORIES,
    DIGITAL_USAGE_DAY_GROUPS,
    RETURN_AGE_GROUPS,
    STOCK_TURNOVER_GROUPS,
    ALL_ASSET_TYPES,
    ALL_CASH_FLOW_CHANNELS,
    ALL_REVENUE_TYPES,
    ALL_TRADE_PRODUCT_TYPES,
    CASH_FLOW_CHANNEL_TOTAL,
    COUNT_TOLERANCE,
    INVESTMENT_TYPES,
    EXCLUDED_INVESTMENT_TYPES,
    PENSION_RANK_PRODUCT_TYPES,
    PENSION_TYPES,
    RETURN_GROUPS,
    RETURN_PERIODS,
    REVENUE_COLUMNS,
    REVENUE_FINAL,
    REVENUE_GROUP_TYPES,
    REVENUE_OPTIONAL_COLUMNS,
    REVENUE_PENSION,
    REVENUE_RETAIL,
    TRADE_PRODUCT_TOTAL,
    load_dashboard_data,
)
from dashboard.sources import pension1 as pension1_source
from dashboard.sources import customer2 as customer2_source
from dashboard.sources import revenue1 as revenue1_source
from dashboard.sources import transaction1 as transaction1_source
from dashboard.sources import transaction2 as transaction2_source
from dashboard.sources import transaction3 as transaction3_source

MONTHS = ["202511", "202512", "202601"]
BRANCHES = [("0001", "지점 01"), ("0002", "지점 02")]
TOTAL_BRANCH = ("0000", "전체")
# 상담 표본의 상담구분과 토픽 수. 실제 값은 원본이 정하며 앱 코드에는
# 적지 않는다(→ dashboard/tabs/consulting).
CONSULTING_TYPES = ["구분 가", "구분 나"]
CONSULTING_TOPICS = 3
# 상품 표본의 순위 개수. 실제 원본은 마지막 한 달만 담고 있어 표본도
# 마지막 달 하나만 만든다.
STOCK_RANKS = 3
# 원본 파일의 연령 구간 컬럼 이름. 표준 이름과 달라 매핑표를 거친다.
SOURCE_AGE = list(customer2_source.AGE_COLUMNS)
SOURCE_INVESTMENT = [*INVESTMENT_TYPES, *EXCLUDED_INVESTMENT_TYPES]
AGE_MIDPOINTS = [15.0, 25.0, 35.0, 45.0, 55.0, 67.0]
# 연령 미선택 컬럼. '합계'에는 없고 '고객수_종료월'에는 있다.
OTHER_AGE_COLUMN = "기타"


def _counts(branch_index: int, month_index: int) -> int:
    """지점·월마다 다른 고객 수. 값이 고정되어 결과를 재현할 수 있다."""
    return 1200 + branch_index * 400 + month_index * 30


def _split(total: int, parts: int) -> list[int]:
    """합이 정확히 total이 되도록 정수로 나눈다."""
    base, rest = divmod(total, parts)
    return [base + (1 if index < rest else 0) for index in range(parts)]


def _monthly_frame() -> pd.DataFrame:
    rows = []
    for month_index, month in enumerate(MONTHS):
        total = 0
        for branch_index, (code, name) in enumerate(BRANCHES):
            count = _counts(branch_index, month_index)
            total += count
            rows.append(
                {"기준월": int(month), "CSMT_ORZ_CD": code, "CSMT_ORZ_NM": name, "공통고객수": count}
            )
        rows.append(
            {
                "기준월": int(month),
                "CSMT_ORZ_CD": TOTAL_BRANCH[0],
                "CSMT_ORZ_NM": TOTAL_BRANCH[1],
                "공통고객수": total,
            }
        )
    return pd.DataFrame(rows)


def _net_assets(branch_index: int, month_index: int) -> int:
    """지점·월마다 다른 순자산(억원). 값이 고정되어 결과를 재현할 수 있다."""
    return 1500 + branch_index * 900 + month_index * 40


def _average_assets(branch_index: int, month_index: int) -> float:
    """지점·월마다 다른 고객 평균 자산(백만원)."""
    return round(30.0 + branch_index * 12.0 + month_index * 1.5, 1)


def _asset1_frame() -> pd.DataFrame:
    """월별 자산 원본. 공통고객수는 월별 파일과 같아야 한다."""
    rows = []
    for month_index, month in enumerate(MONTHS):
        total_count = 0
        total_net = 0
        weighted = 0.0
        for branch_index, (code, name) in enumerate(BRANCHES):
            count = _counts(branch_index, month_index)
            net = _net_assets(branch_index, month_index)
            average = _average_assets(branch_index, month_index)
            total_count += count
            total_net += net
            weighted += average * count
            rows.append(
                {
                    "기준월": int(month),
                    "CSMT_ORZ_CD": code,
                    "CSMT_ORZ_NM": name,
                    "공통고객수": count,
                    "순자산_억원": net,
                    "고객평균자산_백만원": average,
                }
            )
        # 순자산은 더할 수 있으므로 지점 합계와 맞춘다. 평균 자산은 더할 수
        # 없어 고객 수 가중평균으로 넣는다.
        rows.append(
            {
                "기준월": int(month),
                "CSMT_ORZ_CD": TOTAL_BRANCH[0],
                "CSMT_ORZ_NM": TOTAL_BRANCH[1],
                "공통고객수": total_count,
                "순자산_억원": total_net,
                "고객평균자산_백만원": round(weighted / total_count, 1),
            }
        )
    return pd.DataFrame(rows)


WON_PER_100M = 100_000_000
WON_PER_1M = 1_000_000
# 자산2의 자산 구성 비중. 0~1 비율로 들어오며 합이 1이다.
ASSET_SHARE_COLUMNS = (
    "국내주식비중",
    "해외주식비중",
    "국내ETF비중",
    "채권비중",
    "펀드비중",
    "기타비중",
)
ASSET_SHARES = (0.30, 0.22, 0.12, 0.14, 0.16, 0.06)
# (고객수 컬럼, 자산 컬럼, 평균 컬럼, 가입률, 1인 평균 자산(원))
ASSET_PRODUCTS = (
    ("개인연금고객수", "개인연금자산", "개인연금자산평균", 0.22, 18 * WON_PER_1M),
    ("IRP고객수", "IRP자산", "IRP자산평균", 0.15, 24 * WON_PER_1M),
    ("DC고객수", "DC자산", "DC자산평균", 0.09, 31 * WON_PER_1M),
)


def _asset2_row(branch_index: int, code: str, name: str) -> dict:
    """자산2 원본 한 행.

    단위가 컬럼마다 다르다. 순자산 두 개는 이미 억원이고, 연금 자산과
    1인 평균은 원이다(→ dashboard/sources/asset2.py).
    """
    # 공통고객수와 집계 기준이 달라 조금 다른 값이 들어온다.
    count = _counts(branch_index, len(MONTHS) - 1) + 3
    start_100m = float(_net_assets(branch_index, 0))
    end_100m = float(_net_assets(branch_index, len(MONTHS) - 1))
    row = {
        "CSMT_ORZ_CD": code,
        "CSMT_ORZ_NM": name,
        "고객수": count,
        "순자산_시작월": start_100m,
        "순자산_종료월": end_100m,
        # 이미 %로 들어온다.
        "순자산증가율": round((end_100m / start_100m - 1) * 100, 2),
    }
    row.update(dict(zip(ASSET_SHARE_COLUMNS, ASSET_SHARES)))
    for count_column, asset_column, average_column, rate, average in (
        ASSET_PRODUCTS
    ):
        joined = int(count * rate)
        row[count_column] = joined
        row[asset_column] = joined * average
        row[average_column] = average
    return row


def _asset2_frame() -> pd.DataFrame:
    rows = [
        _asset2_row(branch_index, code, name)
        for branch_index, (code, name) in enumerate(BRANCHES)
    ]
    frame = pd.DataFrame(rows)
    # '전체' 행. 더할 수 있는 값만 더하고 비중·평균은 그대로 둔다.
    total = {
        "CSMT_ORZ_CD": TOTAL_BRANCH[0],
        "CSMT_ORZ_NM": TOTAL_BRANCH[1],
    }
    for column in frame.columns:
        if column in ("CSMT_ORZ_CD", "CSMT_ORZ_NM"):
            continue
        if column in ("순자산증가율", *ASSET_SHARE_COLUMNS):
            total[column] = frame[column].iloc[0]
        elif column.endswith("평균"):
            total[column] = frame[column].iloc[0]
        else:
            total[column] = frame[column].sum()
    return pd.concat([frame, pd.DataFrame([total])], ignore_index=True)


def _change_rate(branch_index: int, type_index: int, month_index: int) -> float:
    """지점·분류·월마다 다른 증감율(%). 값이 고정되어 결과를 재현할 수 있다."""
    return round(
        -3.0 + branch_index * 1.5 + type_index * 0.4 + month_index * 0.7, 1
    )


def _asset3_frame() -> pd.DataFrame:
    """상품 분류별 증감율 원본.

    '상품분류' 컬럼이 분류 이름을 갖는다. 월은 가로로 펼쳐지며, 전월
    대비라 첫 달은 빠진다.
    """
    value_months = [int(month) for month in MONTHS[1:]]
    rows = []
    for branch_index, (code, name) in enumerate(
        [*BRANCHES, TOTAL_BRANCH]
    ):
        for type_index, asset_type in enumerate(ALL_ASSET_TYPES):
            row = {
                month: _change_rate(branch_index, type_index, month_index)
                for month_index, month in enumerate(value_months)
            }
            row["CSMT_ORZ_CD"] = code
            row["CSMT_ORZ_NM"] = name
            row["상품분류"] = asset_type
            rows.append(row)
    return pd.DataFrame(rows)


# 자산4의 연금 상품. (고객수 컬럼, 자산 컬럼, 가입률, 1인 평균(백만원))
# 자산2와 같은 지표지만 집계 기준이 달라 값이 조금 다르게 들어온다.
PENSION_PRODUCTS = (
    ("개인연금고객수", "개인연금자산", 0.20, 18.0),
    ("IRP고객수", "IRP자산", 0.14, 24.0),
    ("DC고객수", "DC자산", 0.08, 31.0),
)
MILLION_PER_100M = 100


def _pension_count(
    branch_index: int, month_index: int, product_index: int
) -> int:
    """지점·월·상품마다 다른 가입 고객 수. 값이 고정되어 재현할 수 있다."""
    rate = PENSION_PRODUCTS[product_index][2]
    return int(_counts(branch_index, month_index) * rate) + product_index


def _pension_assets(
    branch_index: int, month_index: int, product_index: int
) -> int:
    """가입 고객 수 × 1인 평균(백만원)을 억원으로 옮긴 값."""
    average = PENSION_PRODUCTS[product_index][3]
    joined = _pension_count(branch_index, month_index, product_index)
    return int(round(joined * average / MILLION_PER_100M))


def _asset4_frame() -> pd.DataFrame:
    """월별 연금 자산 원본. 자산은 억원이고 '전체'는 지점 합계다."""
    rows = []
    for month_index, month in enumerate(MONTHS):
        total: dict = {}
        for branch_index, (code, name) in enumerate(BRANCHES):
            row = {
                "기준월": int(month),
                "CSMT_ORZ_CD": code,
                "CSMT_ORZ_NM": name,
            }
            for product_index, (count_column, asset_column, _r, _a) in (
                enumerate(PENSION_PRODUCTS)
            ):
                row[count_column] = _pension_count(
                    branch_index, month_index, product_index
                )
                row[asset_column] = _pension_assets(
                    branch_index, month_index, product_index
                )
            for column, value in row.items():
                if column in ("기준월", "CSMT_ORZ_CD", "CSMT_ORZ_NM"):
                    continue
                total[column] = total.get(column, 0) + value
            rows.append(row)
        rows.append(
            {
                "기준월": int(month),
                "CSMT_ORZ_CD": TOTAL_BRANCH[0],
                "CSMT_ORZ_NM": TOTAL_BRANCH[1],
                **total,
            }
        )
    return pd.DataFrame(rows)


def _customer2_row(code: str, name: str, start: int, end: int) -> dict:
    age_counts = _split(end, len(SOURCE_AGE))
    investment_counts = _split(end, len(SOURCE_INVESTMENT))
    row: dict = {
        "CSMT_ORZ_CD": code,
        "CSMT_ORZ_NM": name,
        "고객수_시작월": start,
        "고객수_종료월": end,
        # 이미 %로 들어오는 값
        "고객수증가율": (end / start - 1) * 100,
        # 0~1 비율로 들어오는 값
        "남성여부": 0.5125,
        "최근1년이내가입": 0.2408,
        "권유여부": 0.4171,
        "고객등급S이상": 0.3062,
        "연령": float(np.dot(age_counts, AGE_MIDPOINTS) / end),
        "합계": sum(age_counts),
    }
    row.update(dict(zip(SOURCE_AGE, age_counts)))
    row.update({f"{group}비중": count / end * 100 for group, count in zip(SOURCE_AGE, age_counts)})
    for investment_type, count in zip(SOURCE_INVESTMENT, investment_counts):
        consent = count // 2
        row[investment_type] = count
        row[f"{investment_type}_희망"] = consent
        row[f"{investment_type}_불원"] = count - consent
    return row


def _customer2_frame(offsets: dict[int, int] | None = None) -> pd.DataFrame:
    """지점 프로필 원본.

    `offsets`로 지점의 종료월 고객 수를 옮길 수 있다. 파일 안의 연령·투자성향
    합계와 '전체' 행까지 함께 맞춰 주므로, 한 파일 안은 앞뒤가 맞고 월별
    파일과만 어긋난 상태를 만들 수 있다.
    """
    rows = []
    total_start = total_end = 0
    for branch_index, (code, name) in enumerate(BRANCHES):
        start = _counts(branch_index, 0)
        end = _counts(branch_index, len(MONTHS) - 1)
        end += (offsets or {}).get(branch_index, 0)
        total_start += start
        total_end += end
        rows.append(_customer2_row(code, name, start, end))
    rows.append(_customer2_row(*TOTAL_BRANCH, total_start, total_end))
    return pd.DataFrame(rows)


def _row_with_other(
    code: str,
    name: str,
    start: int,
    end: int,
    other: int,
    age_counts: list[int],
) -> dict:
    """`_customer2_row`와 같되 연령 구간 인원을 직접 받는다.

    실제 원본처럼 '합계'에는 '기타'가 빠지고 '고객수_종료월'에는 들어간다.
    """
    row = _customer2_row(code, name, start, end)
    row.update(dict(zip(SOURCE_AGE, age_counts)))
    row["합계"] = sum(age_counts)
    row[OTHER_AGE_COLUMN] = other
    row.update(
        {
            f"{group}비중": count / row["합계"] * 100
            for group, count in zip(SOURCE_AGE, age_counts)
        }
    )
    row["연령"] = float(np.dot(age_counts, AGE_MIDPOINTS) / row["합계"])
    return row


def _customer2_with_other(other: int) -> pd.DataFrame:
    """'기타'가 있는 원본. '전체' 행은 지점 값을 실제로 더해서 만든다."""
    rows = []
    last = len(MONTHS) - 1
    totals = [0] * len(SOURCE_AGE)
    for branch_index, (code, name) in enumerate(BRANCHES):
        end = _counts(branch_index, last)
        age_counts = _split(end - other, len(SOURCE_AGE))
        totals = [a + b for a, b in zip(totals, age_counts)]
        rows.append(
            _row_with_other(
                code,
                name,
                _counts(branch_index, 0),
                end,
                other,
                age_counts,
            )
        )
    total_start = sum(_counts(index, 0) for index in range(len(BRANCHES)))
    total_end = sum(_counts(index, last) for index in range(len(BRANCHES)))
    rows.append(
        _row_with_other(
            *TOTAL_BRANCH,
            total_start,
            total_end,
            other * len(BRANCHES),
            totals,
        )
    )
    return pd.DataFrame(rows)


def _consulting_frame() -> pd.DataFrame:
    """상담 원본 표본. 지점·'전체'마다 상담구분 2개 × 번호 3개.

    비중은 실제 원본과 같이 `16%`처럼 기호를 달고 온다.
    """
    rows = []
    for month in MONTHS:
        for code, name in [*BRANCHES, TOTAL_BRANCH]:
            for kind in CONSULTING_TYPES:
                for number in range(1, CONSULTING_TOPICS + 1):
                    rows.append(
                        {
                            "번호": number,
                            "토픽": f"토픽 {number}",
                            "주요내용": f"{name} {kind} {number}번 내용",
                            "비중": f"{round(40.0 - number * 5, 1)}%",
                            "지점명": name,
                            "지점코드": code,
                            "상담구분": kind,
                            "기준월": int(month),
                        }
                    )
    return pd.DataFrame(rows)


_TRANSACTION_KEYS = ("기준월", "CSMT_ORZ_CD", "CSMT_ORZ_NM", "구분")


def _trade_amount(branch_index: int, month_index: int, seed: int) -> float:
    """지점·월·상품마다 다른 거래금액(억원). 값이 고정되어 재현할 수 있다."""
    return round(
        12.0 + branch_index * 1.3 + month_index * 0.7 + seed * 4.5, 1
    )


def _trade_count(branch_index: int, month_index: int, seed: int) -> int:
    """지점·월·상품마다 다른 거래고객수. 값이 고정되어 재현할 수 있다."""
    return 300 + branch_index * 17 + month_index * 6 + seed * 41


def _add_to_total(total: dict, row: dict) -> None:
    """'전체' 지점 행을 만들려고 지점 값을 더한다. 키 컬럼은 건너뛴다."""
    for column, value in row.items():
        if column in _TRANSACTION_KEYS:
            continue
        total[column] = round(total.get(column, 0) + value, 1)


def _total_row(month: str, extra: dict) -> dict:
    return {
        "기준월": int(month),
        "CSMT_ORZ_CD": TOTAL_BRANCH[0],
        "CSMT_ORZ_NM": TOTAL_BRANCH[1],
        **extra,
    }


def _transaction1_frame() -> pd.DataFrame:
    """월별 지점 거래 원본.

    상품이 가로로 펼쳐져 상품마다 거래금액·거래고객수 두 컬럼을 갖는다.
    '전체' 지점 행은 지점 값을 실제로 더해서 만든다.
    """
    rows = []
    for month_index, month in enumerate(MONTHS):
        total: dict = {}
        for branch_index, (code, name) in enumerate(BRANCHES):
            row = {
                "기준월": int(month),
                "CSMT_ORZ_CD": code,
                "CSMT_ORZ_NM": name,
            }
            for seed, (amount, count) in enumerate(
                transaction1_source.PRODUCT_COLUMNS.values()
            ):
                row[amount] = _trade_amount(branch_index, month_index, seed)
                row[count] = _trade_count(branch_index, month_index, seed)
            _add_to_total(total, row)
            rows.append(row)
        rows.append(_total_row(month, total))
    return pd.DataFrame(rows)


def _transaction2_frame() -> pd.DataFrame:
    """월별 지점 연금 거래 원본. '구분' 축이 하나 더 있다.

    '기타' 상품에는 거래금액만 있고 거래고객수 컬럼이 없다.
    """
    rows = []
    for month_index, month in enumerate(MONTHS):
        totals: dict[str, dict] = {kind: {} for kind in PENSION_TYPES}
        for branch_index, (code, name) in enumerate(BRANCHES):
            for type_index, pension_type in enumerate(PENSION_TYPES):
                row = {
                    "기준월": int(month),
                    "CSMT_ORZ_CD": code,
                    "CSMT_ORZ_NM": name,
                    "구분": pension_type,
                }
                for seed, (amount, count) in enumerate(
                    transaction2_source.PRODUCT_COLUMNS.values()
                ):
                    key = seed + type_index * 4
                    row[amount] = _trade_amount(
                        branch_index, month_index, key
                    )
                    if count is not None:
                        row[count] = _trade_count(
                            branch_index, month_index, key
                        )
                _add_to_total(totals[pension_type], row)
                rows.append(row)
        for pension_type, total in totals.items():
            rows.append(
                _total_row(month, {"구분": pension_type, **total})
            )
    return pd.DataFrame(rows)


def _transaction3_frame() -> pd.DataFrame:
    """월별 지점 입출금 원본.

    '전체' 채널에는 순입금만 있고 입금·출금 컬럼이 없다. 표본에서는 두
    채널의 합으로 만들지만, 어댑터는 그 값을 그대로 읽기만 한다.
    """
    rows = []
    for month_index, month in enumerate(MONTHS):
        total: dict = {}
        for branch_index, (code, name) in enumerate(BRANCHES):
            row = {
                "기준월": int(month),
                "CSMT_ORZ_CD": code,
                "CSMT_ORZ_NM": name,
            }
            net_all = 0.0
            for seed, columns in enumerate(
                transaction3_source.CHANNEL_COLUMNS.values()
            ):
                deposit_column, withdrawal_column, net_column = columns
                if deposit_column is None:
                    row[net_column] = round(net_all, 1)
                    continue
                deposit = _trade_amount(branch_index, month_index, seed + 2)
                withdrawal = _trade_amount(branch_index, month_index, seed)
                net = round(deposit - withdrawal, 1)
                net_all += net
                row[deposit_column] = deposit
                row[withdrawal_column] = withdrawal
                row[net_column] = net
            _add_to_total(total, row)
            rows.append(row)
        rows.append(_total_row(month, total))
    return pd.DataFrame(rows)


def _revenue(branch_index: int, month_index: int) -> int:
    """지점·월마다 다른 리테일 수익(원). 값이 고정되어 재현할 수 있다."""
    return 800_000_000 + branch_index * 31_000_000 + month_index * 12_000_000


# 상품이 리테일 수익에서 차지하는 비율. 표본을 만들 때만 쓴다.
REVENUE_WEIGHTS = [0.34, 0.06, 0.22, 0.08, 0.11, 0.07, 0.05, 0.04, 0.03]
# 퇴직 수익 / 리테일 수익, 그리고 공통고객이 전체고객 수익에서 차지하는 비율.
REVENUE_PENSION_RATIO = 0.12
REVENUE_COMMON_RATIO = 0.62


def _revenue_amounts(branch_index: int, month_index: int) -> dict:
    """한 지점·한 달의 금액 컬럼. 리테일·최종은 실제로 더해서 만든다."""
    base = _revenue(branch_index, month_index)
    row = {
        columns[0]: round(base * weight)
        for columns, weight in zip(
            revenue1_source.TYPE_COLUMNS.values(), REVENUE_WEIGHTS
        )
    }
    retail = sum(row.values())
    pension = round(base * REVENUE_PENSION_RATIO)
    row["수익_공통_리테일"] = retail
    row["수익_공통_퇴직"] = pension
    row["수익_공통_최종"] = retail + pension
    row["수익_전체_리테일"] = round(retail / REVENUE_COMMON_RATIO)
    row["수익_전체_퇴직"] = round(pension / REVENUE_COMMON_RATIO)
    row["수익_전체_최종"] = row["수익_전체_리테일"] + row["수익_전체_퇴직"]
    return row


def _revenue_shares(row: dict) -> dict:
    """비중을 %로 채운다. 표본은 공통고객 최종 수익을 분모로 삼는다."""
    final = row["수익_공통_최종"]
    result = dict(row)
    for columns in revenue1_source.TYPE_COLUMNS.values():
        amount, _, share = columns
        if share is not None and amount in row:
            result[share] = round(row[amount] / final * 100, 1)
    result[revenue1_source.SOURCE_COMMON_SHARE] = round(
        final / row["수익_전체_최종"] * 100, 1
    )
    return result


def _revenue1_frame() -> pd.DataFrame:
    """월별 지점 수익 원본.

    리테일 상품이 가로로 펼쳐져 상품마다 수익·비중 컬럼을 갖는다.
    '전체' 지점 행은 지점 값을 실제로 더해서 만든다.
    """
    rows = []
    for month_index, month in enumerate(MONTHS):
        total: dict = {}
        for branch_index, (code, name) in enumerate(BRANCHES):
            amounts = _revenue_amounts(branch_index, month_index)
            for column, value in amounts.items():
                total[column] = total.get(column, 0) + value
            rows.append(
                {
                    "기준월": int(month),
                    "CSMT_ORZ_CD": code,
                    "CSMT_ORZ_NM": name,
                    **_revenue_shares(amounts),
                }
            )
        rows.append(_total_row(month, _revenue_shares(total)))
    return pd.DataFrame(rows)


def _domestic_stock1_frame() -> pd.DataFrame:
    """상품 국내주식 원본 표본. 지점·'전체'마다 순위 1..N의 종목이 있다.

    실제 원본과 같이 마지막 한 달만 담고, 순위변동은 부호를 붙인 글이며
    업종이 비어 있는 종목이 하나 있다. 순매수금액은 음수가 될 수 있다.
    '전체' 행은 지점과 다른 종목을 담는다. 상위 종목은 지점 목록의 합이
    아니기 때문이다.
    """
    rows = []
    month = MONTHS[-1]
    for branch_index, (code, name) in enumerate([*BRANCHES, TOTAL_BRANCH]):
        for rank in range(1, STOCK_RANKS + 1):
            index = branch_index + rank
            rows.append(
                {
                    "기준월": int(month),
                    "CSMT_ORZ_CD": code,
                    "CSMT_ORZ_NM": name,
                    "순위": rank,
                    "종목명": f"종목 {index:02d}",
                    # 세 번째 종목마다 업종이 비어 있다.
                    "업종": "" if index % 3 == 0 else f"업종 {index}",
                    "시가총액": 900_000 - index * 40_000,
                    "거래고객수": 300 - rank * 20 + branch_index * 5,
                    "거래대금": (5_000 - rank * 400) * 1_000_000,
                    "순매수금액": (600 - rank * 500) * 100_000,
                    "순위변동": ("0", "+2", "-1")[rank % 3],
                }
            )
    return pd.DataFrame(rows)


# 시가총액 상위 종목 표본의 종목 수. 실제 원본은 100종목이며 그 수는
# 원본이 정하므로 앱 코드에는 적지 않는다.
STOCK_CAP_COUNT = 4
# 그중 첫 지점이 거래하지 않은 종목. 지점마다 행 수가 다른 형태를 만든다.
SKIPPED_STOCK = 2


def _domestic_stock2_frame() -> pd.DataFrame:
    """시가총액 상위 종목의 지점별 거래 표본.

    실제 원본과 같이 마지막 한 달만 담고, 순매수금액은 음수일 때 앞에 `-`가
    붙은 글이다. 첫 지점은 한 종목을 거래하지 않아 그 행이 아예 없다.
    시가총액과 업종은 종목의 성질이라 지점이 달라도 같은 값이다.
    """
    rows = []
    month = MONTHS[-1]
    for branch_index, (code, name) in enumerate([*BRANCHES, TOTAL_BRANCH]):
        for index in range(STOCK_CAP_COUNT):
            if branch_index == 0 and index == SKIPPED_STOCK:
                continue
            traders = 200 - index * 30 + branch_index * 25
            value = (4_000 - index * 500) * 1_000_000
            amount = (700 - index * 400) * 100_000
            rows.append(
                {
                    "기준월": int(month),
                    "CSMT_ORZ_CD": code,
                    "CSMT_ORZ_NM": name,
                    "ITM_ABRV_NM": f"종목 {index + 1:02d}",
                    # 마지막 종목은 업종이 비어 있다.
                    "업종": (
                        ""
                        if index == STOCK_CAP_COUNT - 1
                        else f"업종 {index + 1}"
                    ),
                    "시가총액": 800_000 - index * 120_000,
                    "거래고객수": traders,
                    "거래대금": value,
                    "순매수금액": str(amount),
                }
            )
    return pd.DataFrame(rows)


# 앞 달에 없어 순위변동이 비어 있는 자리. 실제 원본에도 있는 형태다.
# 첫 지점의 이 순위만 비워, 같은 순위의 다른 지점은 값을 갖게 한다.
NEW_ENTRY_RANK = 3


def _overseas_stock1_frame() -> pd.DataFrame:
    """상품 해외주식 원본 표본. 지점·'전체'마다 순위 1..N의 종목이 있다.

    국내주식1과 같은 모양이되 시가총액이 없고 거래소가 있다. 마지막 한 달만
    담고, 순매수금액은 부호가 붙은 글이며 업종이 비어 있는 종목이 있다.
    첫 지점의 한 종목은 앞 달에 없던 종목이라 순위변동이 비어 있다.
    """
    rows = []
    month = MONTHS[-1]
    for branch_index, (code, name) in enumerate([*BRANCHES, TOTAL_BRANCH]):
        for rank in range(1, STOCK_RANKS + 1):
            index = branch_index + rank
            amount = (600 - rank * 400) * 100_000
            new_entry = branch_index == 0 and rank == NEW_ENTRY_RANK
            rows.append(
                {
                    "기준월": int(month),
                    "CSMT_ORZ_CD": code,
                    "CSMT_ORZ_NM": name,
                    "순위": rank,
                    "종목명": f"해외종목 {index:02d}",
                    # 세 번째 종목마다 업종이 비어 있다.
                    "업종": "" if index % 3 == 0 else f"업종 {index}",
                    "거래소": ("NASDAQ", "NYSE", "AMEX")[index % 3],
                    "거래고객수": 250 - rank * 15 + branch_index * 5,
                    "거래대금": (4_000 - rank * 300) * 1_000_000,
                    "순매수금액": str(amount),
                    "순위변동": (
                        "" if new_entry else ("0", "+2", "-1")[rank % 3]
                    ),
                }
            )
    return pd.DataFrame(rows)


# 해외주식 시가총액 상위 종목 표본의 종목 수와, 첫 지점이 거래하지 않은 종목.
OVERSEAS_CAP_COUNT = 4
OVERSEAS_SKIPPED_STOCK = 2


def _overseas_stock2_frame() -> pd.DataFrame:
    """시가총액 상위 종목의 지점별 해외주식 거래 표본.

    시가총액은 달러, 순매수금액은 원화이며 부호가 붙은 글이다. 첫 지점은 한
    종목을 거래하지 않아 그 행이 아예 없다.

    순위는 원본이 준 숫자를 그대로 둔다. 표본에서는 종목마다 같은 값이지만,
    무엇을 기준으로 매긴 순위인지 확인되지 않았으므로 코드가 그렇다고 보고
    다루지는 않는다.
    """
    rows = []
    month = MONTHS[-1]
    for branch_index, (code, name) in enumerate([*BRANCHES, TOTAL_BRANCH]):
        for index in range(OVERSEAS_CAP_COUNT):
            if branch_index == 0 and index == OVERSEAS_SKIPPED_STOCK:
                continue
            traders = 180 - index * 25 + branch_index * 20
            amount = (500 - index * 350) * 100_000
            rows.append(
                {
                    "기준월": int(month),
                    "CSMT_ORZ_CD": code,
                    "CSMT_ORZ_NM": name,
                    "종목명": f"해외종목 {index + 1:02d}",
                    "거래소": ("NASDAQ", "NYSE", "AMEX")[index % 3],
                    # 마지막 종목은 업종이 비어 있다.
                    "업종": (
                        ""
                        if index == OVERSEAS_CAP_COUNT - 1
                        else f"업종 {index + 1}"
                    ),
                    "시가총액": 3_000_000_000_000 - index * 700_000_000_000,
                    "거래고객수": traders,
                    "순매수금액": str(amount),
                    "순위": index + 1,
                }
            )
    return pd.DataFrame(rows)


def _etf2_frame() -> pd.DataFrame:
    """상품 ETF 원본 표본. 지점·'전체'마다 순위 1..N의 종목이 있다.

    주식 순위표와 같은 모양이되 업종과 거래소가 없다. 마지막 한 달만 담고,
    순매수금액은 부호가 붙은 글이다. 첫 지점의 한 종목은 앞 달에 없던
    종목이라 순위변동이 비어 있다.
    """
    rows = []
    month = MONTHS[-1]
    for branch_index, (code, name) in enumerate([*BRANCHES, TOTAL_BRANCH]):
        for rank in range(1, STOCK_RANKS + 1):
            index = branch_index + rank
            amount = (600 - rank * 400) * 100_000
            new_entry = branch_index == 0 and rank == NEW_ENTRY_RANK
            rows.append(
                {
                    "기준월": int(month),
                    "CSMT_ORZ_CD": code,
                    "CSMT_ORZ_NM": name,
                    "순위": rank,
                    "종목명": f"ETF {index:02d}",
                    "시가총액": 500_000 - index * 30_000,
                    "거래고객수": 240 - rank * 12 + branch_index * 5,
                    "거래대금": (3_500 - rank * 250) * 1_000_000,
                    "순매수금액": str(amount),
                    "순위변동": (
                        "" if new_entry else ("0", "+2", "-1")[rank % 3]
                    ),
                }
            )
    return pd.DataFrame(rows)


# 펀드 표본에서 순위가 끝까지 차지 않는 지점과 그 지점의 마지막 순위.
# 파는 종목이 적어 20위까지 차지 않는 실제 지점을 나타낸다.
FUND_SHORT_BRANCH = 1
FUND_SHORT_RANKS = 2
# 동순위가 있는 지점과 그 등수. 값이 같은 종목이 여럿이면 원본이 같은
# 등수를 나란히 담는다(→ dashboard/sources/fund1.py 의 check_ranks).
# 등수는 첫 자리에 둔다. 마지막 자리를 겹치게 하면 그 지점의 마지막
# 등수가 앞당겨져, 앞 달에 없던 종목이 어느 줄인지 가릴 수 없게 된다.
FUND_TIED_BRANCH = 0
FUND_TIED_RANK = 1
# 순위 1..N에 붙는 순위변동. 마지막 순위는 앞 달에 없던 종목이라 비어 있다.
FUND_RANK_CHANGES = ("+2", "-1", "0")


def _fund_ranks(branch_index: int, last_rank: int) -> list[int]:
    """그 지점의 행마다 붙는 등수.

    동순위가 있는 지점은 한 등수를 두 번 쓰고 그다음 등수를 건너뛴다.
    행 수는 그대로다.
    """
    numbers = list(range(1, last_rank + 1))
    if branch_index != FUND_TIED_BRANCH:
        return numbers
    return [
        FUND_TIED_RANK if number == FUND_TIED_RANK + 1 else number
        for number in numbers
    ]


def _fund1_frame() -> pd.DataFrame:
    """상품 펀드 원본 표본. 지점·'전체'마다 순위 1..N의 종목이 있다.

    ETF와 같은 모양이되 시가총액이 없고, **지점마다 순위 수가 다르다.**
    두 번째 지점은 파는 종목이 적어 순위가 끝까지 차지 않는다. 첫 지점에는
    같은 등수가 나란히 오는 자리가 있다. 앞 달에 없던 종목은 지점마다
    마지막 순위에 하나씩 둔다.
    """
    rows = []
    month = MONTHS[-1]
    for branch_index, (code, name) in enumerate([*BRANCHES, TOTAL_BRANCH]):
        last_rank = (
            FUND_SHORT_RANKS
            if branch_index == FUND_SHORT_BRANCH
            else STOCK_RANKS
        )
        numbers = _fund_ranks(branch_index, last_rank)
        for position, rank in enumerate(numbers, start=1):
            index = branch_index + position
            amount = (600 - position * 400) * 100_000
            rows.append(
                {
                    "기준월": int(month),
                    "CSMT_ORZ_CD": code,
                    "CSMT_ORZ_NM": name,
                    "순위": rank,
                    "종목명": f"펀드 {index:02d}",
                    "거래고객수": 210 - position * 10 + branch_index * 5,
                    "거래대금": (2_800 - position * 200) * 1_000_000,
                    "순매수금액": str(amount),
                    "순위변동": (
                        ""
                        if position == len(numbers)
                        else FUND_RANK_CHANGES[position - 1]
                    ),
                }
            )
    return pd.DataFrame(rows)


# 연금 원본이 가로로 펼쳐 담고 있는 (연금 구분, 상품) 짝.
PENSION_BLOCKS = [
    (pension_type, product_type)
    for pension_type in PENSION_TYPES
    for product_type in PENSION_RANK_PRODUCT_TYPES
]
# 컬럼 이름에 공백이 섞여 들어오는 상품. 실제 원본이 이 다섯 컬럼만
# `IRP_ETF_ 종목명`처럼 밑줄 뒤에 공백을 붙여 담고 있다.
PENSION_SPACED_BLOCK = ("IRP", "ETF")
# 순위가 끝까지 차지 않는 상품과 그 마지막 순위. 그 뒤 순위는 종목명이 빈
# 칸이라 표준 프레임에 줄이 없다.
PENSION_SHORT_BLOCK = ("개인연금", "펀드")
PENSION_SHORT_RANKS = 2


def _pension_column(pension: str, product: str, field: str) -> str:
    space = " " if (pension, product) == PENSION_SPACED_BLOCK else ""
    return f"{pension}_{product}_{space}{field}"


def _pension1_frame() -> pd.DataFrame:
    """상품 연금통합 원본 표본. 한 행에 상품 여섯 개가 가로로 펼쳐져 있다.

    연금 구분 셋 × 상품 둘이며 상품마다 다섯 컬럼이다. 개인연금 펀드만
    순위가 끝까지 차지 않아 뒤쪽 종목명이 빈 칸이고, IRP ETF 다섯 컬럼은
    이름에 공백이 섞여 있다. 순위변동은 상품마다 마지막 순위에서 비어 있다.

    줄이 없는 자리는 빈 칸을 NaN으로 담는다. 실제 원본이 그 모양이며,
    빈 문자열만 넣어 두면 NaN을 걸러 내지 못하는 것을 알 수 없다.
    """
    rows = []
    month = MONTHS[-1]
    for branch_index, (code, name) in enumerate([*BRANCHES, TOTAL_BRANCH]):
        for rank in range(1, STOCK_RANKS + 1):
            row = {
                "기준월": int(month),
                "CSMT_ORZ_CD": code,
                "CSMT_ORZ_NM": name,
                "순위": rank,
            }
            for pension, product in PENSION_BLOCKS:
                # '전체'는 어느 상품이나 끝까지 찬다.
                short = (pension, product) == PENSION_SHORT_BLOCK and (
                    name != TOTAL_BRANCH[1]
                )
                end = PENSION_SHORT_RANKS if short else STOCK_RANKS
                blank = rank > end
                index = branch_index + rank
                amount = (600 - rank * 400) * 100_000
                values = {
                    "종목명": (
                        np.nan
                        if blank
                        else f"{pension} {product} {index:02d}"
                    ),
                    "거래고객수": np.nan if blank else 150 - rank * 10,
                    "거래대금": (
                        np.nan
                        if blank
                        else (1_800 - rank * 200) * 1_000_000
                    ),
                    "순매수금액": np.nan if blank else str(amount),
                    "순위변동": (
                        ""
                        if blank or rank == end
                        else ("+2", "-1", "0")[rank - 1]
                    ),
                }
                for field, value in values.items():
                    row[_pension_column(pension, product, field)] = value
            rows.append(row)
    return pd.DataFrame(rows)


# 수익률 표본에서 지점마다 붙는 1년·3년 수익률(%). 첫 지점은 1년이 손실이라
# 음수다. 값이 고정되어 결과를 재현할 수 있다.
BRANCH_RETURNS = ((-4.25, 11.8), (7.5, 23.45))
# '전체' 행의 수익률. 지점 수익률의 합도 평균도 아닌 따로 계산된 값이라
# 지점 값과 맞지 않아도 된다(→ dashboard/data.py 의 _TOTAL_CHECK_COLUMNS).
TOTAL_RETURN = (2.75, 18.6)


def _branch_return_frame() -> pd.DataFrame:
    """지점별 수익률 원본 표본. 지점·'전체'마다 마지막 달 한 행씩이다.

    분류축이 없어 순위표들보다 단순하다. 값은 이미 %로 계산된 숫자이며
    손실이 난 지점은 음수다.
    """
    month = MONTHS[-1]
    rows = [
        {
            "기준월": int(month),
            "CSMT_ORZ_CD": code,
            "CSMT_ORZ_NM": name,
            "수익률_1년": BRANCH_RETURNS[branch_index][0],
            "수익률_3년": BRANCH_RETURNS[branch_index][1],
        }
        for branch_index, (code, name) in enumerate(BRANCHES)
    ]
    rows.append(
        {
            "기준월": int(month),
            "CSMT_ORZ_CD": TOTAL_BRANCH[0],
            "CSMT_ORZ_NM": TOTAL_BRANCH[1],
            "수익률_1년": TOTAL_RETURN[0],
            "수익률_3년": TOTAL_RETURN[1],
        }
    )
    return pd.DataFrame(rows)


# 수익률 그룹별 비중 표본. 기간마다 지점 고객을 구간 열 개로 나눈 몫이다.
# 합이 지점 고객 수와 정확히 맞아야 한다 — 데이터 계층이 원본 안에서
# 앞뒤가 맞는지 대조한다(→ return_group.check_branch_totals).
GROUP_COUNTS = {
    "MM12_ERN_R": (2, 4, 6, 12, 20, 16, 14, 10, 8, 8),
    "MM36_ERN_R": (1, 2, 5, 10, 15, 18, 19, 14, 9, 7),
}
# 컬럼 이름에 공백이 다르게 들어오는 구간. 실제 원본이 `-20% ~ -10%`처럼
# 물결 좌우에 공백을 두는데, 없이 담겨 와도 같은 구간으로 읽어야 한다
# (→ return_group._group_names).
SQUEEZED_GROUP = RETURN_GROUPS[1]


def _written_group(index: int, name: str) -> str:
    """원본이 담는 구간 이름. 앞에 차례를 적는다.

    한 구간만 이름의 공백까지 떼어 담는다. 번호와 공백 어느 쪽이 달라도
    같은 구간으로 읽는지 한 표본으로 함께 확인한다.
    """
    if name == SQUEEZED_GROUP:
        name = "".join(name.split())
    return f"{index}){name}"


def _return_group_frame() -> pd.DataFrame:
    """수익률 그룹별 비중 원본 표본.

    지점·'전체'마다 기간 둘 × 구간 열 = 스무 행이다. 구간 인원수의 합이
    지점 합계가 되고 비중은 그 둘로 계산한 %다.

    구간 이름은 실제 원본과 같이 `0)-20%미만` 꼴로 담는다(→ _written_group).
    """
    rows = []
    month = MONTHS[-1]
    for branch_index, (code, name) in enumerate([*BRANCHES, TOTAL_BRANCH]):
        for period_code, weights in GROUP_COUNTS.items():
            counts = [
                weight * (branch_index + 1) for weight in weights
            ]
            total = sum(counts)
            for order, (group_name, count) in enumerate(
                zip(RETURN_GROUPS, counts)
            ):
                written = _written_group(order, group_name)
                rows.append(
                    {
                        "기준월": int(month),
                        "CSMT_ORZ_CD": code,
                        "CSMT_ORZ_NM": name,
                        "수익률_구분": period_code,
                        "수익률_그룹": written,
                        "고객수": count,
                        "고객수_지점합계": total,
                        "고객비중": round(count / total * 100.0, 2),
                    }
                )
    return pd.DataFrame(rows)


@pytest.fixture
def source_files(tmp_path, monkeypatch):
    """원본 파일들을 만들고 환경 변수를 걸어 주는 헬퍼를 반환한다.

    `with_asset=False`로 부르면 자산 파일을, `with_consulting=False`로
    부르면 상담 파일을 지정하지 않는다. 필수가 아닌 원본이 빠졌을 때의
    동작을 확인할 때 쓴다.
    """

    def _write(
        monthly: pd.DataFrame | None = None,
        customer2: pd.DataFrame | None = None,
        asset1: pd.DataFrame | None = None,
        asset2: pd.DataFrame | None = None,
        asset3: pd.DataFrame | None = None,
        asset4: pd.DataFrame | None = None,
        consulting1: pd.DataFrame | None = None,
        transaction1: pd.DataFrame | None = None,
        transaction2: pd.DataFrame | None = None,
        transaction3: pd.DataFrame | None = None,
        revenue1: pd.DataFrame | None = None,
        domestic_stock1: pd.DataFrame | None = None,
        domestic_stock2: pd.DataFrame | None = None,
        overseas_stock1: pd.DataFrame | None = None,
        overseas_stock2: pd.DataFrame | None = None,
        etf2: pd.DataFrame | None = None,
        fund1: pd.DataFrame | None = None,
        pension1: pd.DataFrame | None = None,
        branch_return: pd.DataFrame | None = None,
        return_group: pd.DataFrame | None = None,
        asset_return: pd.DataFrame | None = None,
        stock_share_return: pd.DataFrame | None = None,
        overseas_share_return: pd.DataFrame | None = None,
        etf_share_return: pd.DataFrame | None = None,
        pension_share_return: pd.DataFrame | None = None,
        stock_turnover_return: pd.DataFrame | None = None,
        age_return: pd.DataFrame | None = None,
        digital1: pd.DataFrame | None = None,
        digital2: pd.DataFrame | None = None,
        digital3: pd.DataFrame | None = None,
        digital4: pd.DataFrame | None = None,
        with_asset: bool = True,
        with_consulting: bool = True,
        with_transaction: bool = True,
        with_revenue: bool = True,
        with_product: bool = True,
        with_return: bool = True,
        with_digital: bool = True,
    ):
        monthly_path = tmp_path / "monthly.pkl"
        customer2_path = tmp_path / "customer2.pkl"
        (monthly if monthly is not None else _monthly_frame()).to_pickle(monthly_path)
        frame = customer2 if customer2 is not None else _customer2_frame()
        frame.to_pickle(customer2_path)
        monkeypatch.setenv("DASHBOARD_DATA_SOURCE", "local_file")
        monkeypatch.setenv("DASHBOARD_DATA_FILE", str(monthly_path))
        monkeypatch.setenv("DASHBOARD_CUSTOMER2_FILE", str(customer2_path))
        for key, given, default, include in (
            ("ASSET1", asset1, _asset1_frame, with_asset),
            ("ASSET2", asset2, _asset2_frame, with_asset),
            ("ASSET3", asset3, _asset3_frame, with_asset),
            ("ASSET4", asset4, _asset4_frame, with_asset),
            ("CONSULTING1", consulting1, _consulting_frame, with_consulting),
            (
                "TRANSACTION1",
                transaction1,
                _transaction1_frame,
                with_transaction,
            ),
            (
                "TRANSACTION2",
                transaction2,
                _transaction2_frame,
                with_transaction,
            ),
            (
                "TRANSACTION3",
                transaction3,
                _transaction3_frame,
                with_transaction,
            ),
            ("REVENUE1", revenue1, _revenue1_frame, with_revenue),
            (
                "DOMESTIC_STOCK1",
                domestic_stock1,
                _domestic_stock1_frame,
                with_product,
            ),
            (
                "DOMESTIC_STOCK2",
                domestic_stock2,
                _domestic_stock2_frame,
                with_product,
            ),
            (
                "OVERSEAS_STOCK1",
                overseas_stock1,
                _overseas_stock1_frame,
                with_product,
            ),
            (
                "OVERSEAS_STOCK2",
                overseas_stock2,
                _overseas_stock2_frame,
                with_product,
            ),
            ("ETF2", etf2, _etf2_frame, with_product),
            ("FUND1", fund1, _fund1_frame, with_product),
            ("PENSION1", pension1, _pension1_frame, with_product),
            (
                "BRANCH_RETURN",
                branch_return,
                _branch_return_frame,
                with_return,
            ),
            (
                "RETURN_GROUP",
                return_group,
                _return_group_frame,
                with_return,
            ),
            (
                "ASSET_RETURN",
                asset_return,
                _asset_return_frame,
                with_return,
            ),
            (
                "STOCK_SHARE_RETURN",
                stock_share_return,
                _stock_share_return_frame,
                with_return,
            ),
            (
                "OVERSEAS_SHARE_RETURN",
                overseas_share_return,
                _overseas_share_return_frame,
                with_return,
            ),
            (
                "ETF_SHARE_RETURN",
                etf_share_return,
                _etf_share_return_frame,
                with_return,
            ),
            (
                "PENSION_SHARE_RETURN",
                pension_share_return,
                _pension_share_return_frame,
                with_return,
            ),
            (
                "STOCK_TURNOVER_RETURN",
                stock_turnover_return,
                _stock_turnover_return_frame,
                with_return,
            ),
            (
                "AGE_RETURN",
                age_return,
                _age_return_frame,
                with_return,
            ),
            ("DIGITAL1", digital1, _digital1_frame, with_digital),
            ("DIGITAL2", digital2, _digital2_frame, with_digital),
            ("DIGITAL3", digital3, _digital3_frame, with_digital),
            ("DIGITAL4", digital4, _digital4_frame, with_digital),
        ):
            if not include:
                # conftest가 걸어 둔 표본 자산 파일을 걷어낸다.
                monkeypatch.delenv(f"DASHBOARD_{key}_FILE", raising=False)
                continue
            path = tmp_path / f"{key.lower()}.pkl"
            (given if given is not None else default()).to_pickle(path)
            monkeypatch.setenv(f"DASHBOARD_{key}_FILE", str(path))
        return load_dashboard_data

    return _write


def test_source_files_load_into_the_standard_frames(source_files):
    data = source_files()()
    assert data.branch_names == [name for _, name in BRANCHES]
    assert data.months == ["2025-11", "2025-12", "2026-01"]
    # '전체' 행은 지점 데이터에서 빠진다.
    assert TOTAL_BRANCH[1] not in set(data.monthly["branch_name"])
    assert list(data.age["age_group"].cat.categories) == list(ALL_AGE_GROUPS)
    assert list(data.investment["investment_type"].cat.categories) == list(INVESTMENT_TYPES)
    # 연령·투자성향·요약은 마지막 한 달치만 담고 있다.
    for frame in (data.age, data.investment, data.summary):
        assert sorted(frame["base_month"].unique()) == ["2026-01"]


def test_age_other_group_is_counted_but_not_charted(source_files):
    """'기타'는 고객 수 대조에는 들어가고 분포 차트에서는 빠진다.

    원본의 '합계'가 '기타'를 빼고 세므로, 이 구간을 읽지 않으면 연령 합계가
    고객 수보다 적어 검증에서 멈춘다.
    """
    other = 5
    branch_name = BRANCHES[0][1]
    end = _counts(0, len(MONTHS) - 1)
    data = source_files(customer2=_customer2_with_other(other))()

    rows = data.age[data.age["branch_name"] == branch_name]
    counts = rows.set_index("age_group")["customer_count"]
    assert counts[OTHER_AGE_COLUMN] == other
    # 6개 구간 + 기타를 더하면 고객 수와 정확히 맞는다.
    assert int(counts.sum()) == end

    distribution = metrics.age_distribution(
        data.age, branch_name, age_total=data.age_total
    )
    assert set(distribution["age_group"]) == set(AGE_GROUPS)
    for _, group in distribution.groupby("scope", observed=True):
        assert group["share"].sum() == pytest.approx(100.0)
    branch_part = distribution[distribution["scope"] == branch_name]
    assert int(branch_part["customer_count"].sum()) == end - other


def test_ratio_columns_are_scaled_to_percent(source_files):
    data = source_files()()
    row = data.summary.iloc[0]
    assert row["male_share"] == pytest.approx(51.25)
    assert row["recent_signup_share"] == pytest.approx(24.08)
    assert row["recommendation_share"] == pytest.approx(41.71)
    assert row["grade_s_share"] == pytest.approx(30.62)


def test_growth_rate_is_used_as_given(source_files):
    """고객수증가율은 이미 %이므로 그대로 쓴다. 화면 값이 원본과 정확히 같아야 한다."""
    data = source_files()()
    _, branch_rows = metrics.branch_table(data.monthly, data.summary)
    given = _customer2_frame().set_index("CSMT_ORZ_NM")["고객수증가율"]
    for row in branch_rows.itertuples():
        assert row.customer_growth_yoy == pytest.approx(given[row.branch_name])


def test_missing_measures_stay_empty_instead_of_zero(source_files):
    """원본에 없는 총자산·앱 값은 0이 아니라 빈 값으로 남는다.

    거래고객 비중은 거래1이 담고 있어 값이 채워진다. 그 원본까지 없을
    때 비는지는 아래 테스트가 확인한다.
    """
    data = source_files()()
    assert data.monthly["total_assets"].isna().all()
    kpis = shared.kpi_metrics(data.monthly)
    assert kpis["customer_count"]["value"] is not None
    assert kpis["app_share"]["value"] is None


def test_transaction_share_is_empty_without_the_transaction_source(
    source_files,
):
    """거래1이 없으면 거래고객 비중도 비어야 한다. 0%로 채우지 않는다."""
    data = source_files(with_transaction=False)()
    kpis = shared.kpi_metrics(data.monthly)
    assert kpis["transaction_share"]["value"] is None


def test_transaction_share_uses_the_total_product_count(source_files):
    """거래고객 비중 = 거래1의 '전체' 거래고객수 ÷ 공통고객 수."""
    data = source_files()()
    kpis = shared.kpi_metrics(data.monthly, monthly_total=data.monthly_total)
    total = data.monthly_total
    row = total[total["base_month"] == "2026-01"].iloc[0]
    expected = (
        row["transaction_customer_count"] / row["customer_count"] * 100.0
    )
    assert kpis["transaction_share"]["value"] == pytest.approx(expected)


def test_excluded_investment_type_is_dropped_but_still_checked(source_files):
    """'미제공'은 화면에서 빠지되 합계 대조에는 들어간다."""
    data = source_files()()
    assert set(data.investment["investment_type"]) == set(INVESTMENT_TYPES)
    key = ["base_month", "branch_id"]
    shown = data.investment.groupby(key, observed=True)["customer_count"].sum()
    customers = data.monthly.set_index(key)["customer_count"].reindex(shown.index)
    assert (shown < customers).all(), "제외한 분류만큼 적어야 한다"


def test_total_row_uses_the_source_values_as_given(source_files):
    """전체 행은 지점 값에서 되계산하지 않고 원본의 '전체' 행을 그대로 쓴다."""
    data = source_files()()
    total_row, _ = metrics.branch_table(
        data.monthly, data.summary, summary_total=data.summary_total
    )
    given = _customer2_frame().set_index("CSMT_ORZ_NM").loc[TOTAL_BRANCH[1]]
    assert total_row["customer_count"] == given["고객수_종료월"]
    assert total_row["customer_growth_yoy"] == pytest.approx(given["고객수증가율"])
    assert total_row["male_share"] == pytest.approx(given["남성여부"] * 100)
    assert total_row["average_age"] == pytest.approx(given["연령"])
    assert total_row["grade_s_share"] == pytest.approx(given["고객등급S이상"] * 100)


def test_filtering_branches_drops_the_source_total(source_files):
    """지점을 걸러내면 원본 전체 행은 더 이상 맞지 않으므로 쓰지 않는다."""
    load = source_files()
    filtered = load(filters={"branch_names": [BRANCHES[0][1]]})
    assert filtered.summary_total.empty
    total_row, branch_rows = metrics.branch_table(
        filtered.monthly, filtered.summary, summary_total=filtered.summary_total
    )
    assert len(branch_rows) == 1
    assert total_row["customer_count"] == branch_rows.iloc[0]["customer_count"]


def test_two_files_from_different_points_in_time_are_rejected(source_files):
    """고객 수가 크게 어긋나면 두 파일이 가리키는 시점이 다르다는 뜻이다."""
    customer2 = _customer2_frame({0: _big_gap(0)})
    with pytest.raises(ValueError, match="너무 다릅니다"):
        source_files(customer2=customer2)()




def _big_gap(branch_index: int) -> int:
    """허용 범위를 확실히 넘는 차이."""
    count = _counts(branch_index, len(MONTHS) - 1)
    return int(COUNT_TOLERANCE + count * 0.05) + 1


def test_investment_parts_that_do_not_add_up_are_rejected(source_files):
    customer2 = _customer2_frame()
    customer2.loc[0, f"{INVESTMENT_TYPES[0]}_희망"] = (
        int(customer2.loc[0, f"{INVESTMENT_TYPES[0]}_희망"]) + 3
    )
    with pytest.raises(ValueError, match="숫자가 서로 맞지 않는 지점"):
        source_files(customer2=customer2)()


def test_percent_given_where_a_ratio_is_expected_is_rejected(source_files):
    """0~1 비율 자리에 이미 %가 들어오면 두 번 곱해져 100을 넘는다. 그때 멈춘다."""
    customer2 = _customer2_frame()
    customer2["남성여부"] = customer2["남성여부"] * 100
    with pytest.raises(ValueError, match="0~100 범위를 벗어난"):
        source_files(customer2=customer2)()


def test_missing_source_column_names_itself(source_files):
    customer2 = _customer2_frame().drop(columns=["권유여부"])
    with pytest.raises(ValueError, match="권유여부"):
        source_files(customer2=customer2)()


# --- 지점 자산 원본 -----------------------------------------------------------
def test_asset_file_joins_the_monthly_frame(source_files):
    """자산 원본의 값이 기준월·지점 그대로 월별 프레임에 붙는다."""
    data = source_files()()
    given = _asset1_frame()
    given["base_month"] = [
        f"{str(month)[:4]}-{str(month)[4:]}" for month in given["기준월"]
    ]
    branches = given[given["CSMT_ORZ_CD"] != TOTAL_BRANCH[0]].set_index(
        ["base_month", "CSMT_ORZ_CD"]
    )
    joined = data.monthly.set_index(["base_month", "branch_id"])
    for key, row in branches.iterrows():
        assert joined.loc[key, "net_assets"] == pytest.approx(row["순자산_억원"])
        assert joined.loc[key, "average_assets"] == pytest.approx(
            row["고객평균자산_백만원"]
        )
    # '전체' 행도 원본 값을 그대로 들고 간다.
    total = given[given["CSMT_ORZ_CD"] == TOTAL_BRANCH[0]].set_index("base_month")
    totals = data.monthly_total.set_index("base_month")
    for month in totals.index:
        assert totals.loc[month, "net_assets"] == pytest.approx(
            total.loc[month, "순자산_억원"]
        )


def test_asset_file_is_optional_and_missing_values_stay_empty(source_files):
    """자산 파일이 없으면 자산 컬럼은 0이 아니라 빈 값으로 남는다."""
    data = source_files(with_asset=False)()
    assert data.monthly["net_assets"].isna().all()
    assert data.monthly["average_assets"].isna().all()


def test_asset_file_customer_count_must_match_the_monthly_file(source_files):
    """같은 지표가 두 원본에 겹쳐 있으면 크게 벌어져서는 안 된다."""
    asset = _asset1_frame()
    asset.loc[0, "공통고객수"] = int(asset.loc[0, "공통고객수"]) + _big_gap(0)
    with pytest.raises(ValueError, match="공통고객수가 너무 다릅니다"):
        source_files(asset1=asset)()


def test_asset_file_customer_count_may_differ_a_little(source_files):
    """추출 시점이 하루만 달라도 몇 명이 어긋난다. 그때는 알리고 넘어간다.

    화면의 고객 수는 월별 파일 값을 쓰고, 자산1의 순자산은 그대로 붙는다.
    """
    asset = _asset1_frame()
    asset.loc[0, "공통고객수"] = int(asset.loc[0, "공통고객수"]) - 1
    with pytest.warns(UserWarning, match="공통고객수가 조금 다릅니다"):
        data = source_files(asset1=asset)()
    first = f"{MONTHS[0][:4]}-{MONTHS[0][4:]}"
    row = data.monthly.set_index(["base_month", "branch_id"]).loc[
        (first, BRANCHES[0][0])
    ]
    assert row["customer_count"] == _counts(0, 0)
    assert row["net_assets"] == pytest.approx(_net_assets(0, 0))


def test_asset_file_with_a_different_branch_set_is_rejected(source_files):
    """한쪽 파일에만 있는 지점·월이 있으면 조용히 비우지 않고 멈춘다."""
    asset = _asset1_frame().drop(index=0).reset_index(drop=True)
    with pytest.raises(ValueError, match="없는 기준월·지점이"):
        source_files(asset1=asset)()


def test_asset_total_row_is_checked_against_the_branch_sum(source_files):
    """'전체' 행의 순자산이 지점 합계와 다르면 멈춘다."""
    asset = _asset1_frame()
    is_total = asset["CSMT_ORZ_CD"] == TOTAL_BRANCH[0]
    first = asset[is_total].index[0]
    asset.loc[first, "순자산_억원"] = int(asset.loc[first, "순자산_억원"]) + 100
    with pytest.raises(ValueError, match="'전체' 행과 지점 합계가 다릅니다"):
        source_files(asset1=asset)()


def test_asset_file_with_duplicate_rows_is_rejected(source_files):
    """한 지점이 한 달에 두 번 나오면 어느 값이 맞는지 알 수 없으므로 멈춘다."""
    asset = _asset1_frame()
    doubled = pd.concat([asset, asset.iloc[[0]]], ignore_index=True)
    with pytest.raises(ValueError, match="두 번 이상 있습니다"):
        source_files(asset1=doubled)()


# --- 지점 자산 프로필(자산2) ---------------------------------------------------
def test_asset2_amounts_are_converted_from_won(source_files):
    """원 단위로 들어온 연금 금액만 억원·백만원으로 맞춘다.

    순자산은 원본이 이미 억원이라 손대지 않는다. 여기에 1억을 또 나누면
    값이 0에 가까워져 산점도의 가로축 눈금이 전부 0이 된다(회귀 방지).
    """
    data = source_files()()
    row = data.summary.set_index("branch_name").loc[BRANCHES[0][1]]
    assert row["net_assets_start"] == pytest.approx(_net_assets(0, 0))
    assert row["net_assets_end"] == pytest.approx(
        _net_assets(0, len(MONTHS) - 1)
    )
    count_column, asset_column, average_column, rate, average = (
        ASSET_PRODUCTS[0]
    )
    joined = int((_counts(0, len(MONTHS) - 1) + 3) * rate)
    assert row["pension_customer_count"] == joined
    assert row["pension_assets"] == pytest.approx(
        joined * average / WON_PER_100M
    )
    assert row["pension_assets_average"] == pytest.approx(
        average / WON_PER_1M
    )


def test_asset2_shares_are_scaled_to_percent(source_files):
    """자산 구성 비중은 0~1로 들어오므로 100을 곱한다. 합은 100%다."""
    data = source_files()()
    row = data.summary.iloc[0]
    assert row["domestic_stock_share"] == pytest.approx(ASSET_SHARES[0] * 100)
    assert row["other_asset_share"] == pytest.approx(ASSET_SHARES[-1] * 100)
    total = sum(
        row[column]
        for column in (
            "domestic_stock_share",
            "foreign_stock_share",
            "domestic_etf_share",
            "bond_share",
            "fund_share",
            "other_asset_share",
        )
    )
    assert total == pytest.approx(100.0)


def test_asset2_growth_rate_is_used_as_given(source_files):
    """순자산증가율은 이미 %이므로 그대로 쓴다."""
    data = source_files()()
    given = _asset2_frame().set_index("CSMT_ORZ_NM")["순자산증가율"]
    rows = data.summary.set_index("branch_name")
    for name in rows.index:
        assert rows.loc[name, "net_assets_growth"] == pytest.approx(
            given[name]
        )


def test_asset2_values_are_not_checked_against_other_files(source_files):
    """자산2의 고객수·순자산은 다른 파일과 집계 기준이 달라 대조하지 않는다.

    값이 달라도 멈추지 않고 각 파일의 값을 그대로 들고 가야 한다.
    """
    asset2 = _asset2_frame()
    is_total = asset2["CSMT_ORZ_CD"] == TOTAL_BRANCH[0]
    # 지점 값을 옮기고 '전체' 행도 함께 맞춘다. 한 파일 안의 앞뒤는 맞아야
    # 하고, 여기서 보려는 것은 다른 파일과 달라도 되는지다.
    asset2.loc[~is_total, "고객수"] += 500
    asset2.loc[is_total, "고객수"] += 500 * len(BRANCHES)
    asset2["순자산_종료월"] = asset2["순자산_종료월"] * 2
    data = source_files(asset2=asset2)()
    row = data.summary.set_index("branch_name").loc[BRANCHES[0][1]]
    # 자산2의 고객수는 표준 customer_count를 덮지 않는다.
    assert row["asset_customer_count"] == _counts(0, len(MONTHS) - 1) + 503
    assert row["customer_count"] == _counts(0, len(MONTHS) - 1)
    assert row["net_assets_end"] == pytest.approx(
        _net_assets(0, len(MONTHS) - 1) * 2
    )


def test_asset2_total_row_is_checked_against_the_branch_sum(source_files):
    """'전체' 행의 더할 수 있는 값이 지점 합계와 다르면 멈춘다."""
    asset2 = _asset2_frame()
    is_total = asset2["CSMT_ORZ_CD"] == TOTAL_BRANCH[0]
    first = asset2[is_total].index[0]
    asset2.loc[first, "개인연금자산"] = (
        int(asset2.loc[first, "개인연금자산"]) + 3 * WON_PER_100M
    )
    with pytest.raises(ValueError, match="'전체' 행과 지점 합계가 다릅니다"):
        source_files(asset2=asset2)()


def test_asset2_total_row_ignores_values_that_cannot_be_summed(source_files):
    """비중·증가율·1인 평균은 더할 수 없으므로 대조하지 않는다.

    '전체' 행의 이 값들이 지점 합계와 달라도 멈추면 안 된다.
    """
    data = source_files()()
    total = data.summary_total.iloc[0]
    branches = data.summary
    for column in ("net_assets_growth", "bond_share", "irp_assets_average"):
        assert total[column] != pytest.approx(branches[column].sum()), column
        assert pd.notna(total[column]), column


def test_asset2_is_optional_and_missing_values_stay_empty(source_files):
    data = source_files(with_asset=False)()
    for column in ("net_assets_end", "pension_assets", "bond_share"):
        assert data.summary[column].isna().all(), column


def test_asset2_with_a_different_branch_set_is_rejected(source_files):
    asset2 = _asset2_frame().drop(index=0).reset_index(drop=True)
    with pytest.raises(ValueError, match="없는 지점이"):
        source_files(asset2=asset2)()


def test_asset2_with_duplicate_branches_is_rejected(source_files):
    asset2 = _asset2_frame()
    doubled = pd.concat([asset2, asset2.iloc[[0]]], ignore_index=True)
    with pytest.raises(ValueError, match="두 번 이상 있습니다"):
        source_files(asset2=doubled)()


def test_asset2_percent_given_where_a_ratio_is_expected_is_rejected(
    source_files,
):
    """0~1 자리에 이미 %가 들어오면 두 번 곱해져 100을 넘는다. 그때 멈춘다."""
    asset2 = _asset2_frame()
    asset2["국내주식비중"] = asset2["국내주식비중"] * 100
    with pytest.raises(ValueError, match="0~100 범위를 벗어난"):
        source_files(asset2=asset2)()


# --- 상품 분류별 증감율(자산3) -------------------------------------------------
def test_asset3_rows_are_labelled_by_the_asset_type_column(source_files):
    """'상품분류' 컬럼의 값이 그대로 분류 이름이 된다."""
    data = source_files()()
    change = data.asset_change
    assert list(change["asset_type"].cat.categories) == list(ALL_ASSET_TYPES)

    first_month = MONTHS[1][:4] + "-" + MONTHS[1][4:]
    picked = change[
        (change["base_month"] == first_month)
        & (change["branch_name"] == BRANCHES[0][1])
    ].set_index("asset_type")
    for type_index, asset_type in enumerate(ALL_ASSET_TYPES):
        assert picked.loc[asset_type, "change_rate"] == pytest.approx(
            _change_rate(0, type_index, 0)
        ), asset_type


def test_asset3_months_are_unfolded_into_rows(source_files):
    """가로로 펼쳐진 월 열이 한 줄에 한 시점인 형태로 바뀐다."""
    data = source_files()()
    change = data.asset_change
    # 전월 대비라 첫 달은 빠진다.
    assert sorted(change["base_month"].unique()) == ["2025-12", "2026-01"]
    assert len(change) == (
        len(BRANCHES) * len(ALL_ASSET_TYPES) * (len(MONTHS) - 1)
    )
    # '전체' 지점은 지점 데이터에서 빠져 따로 들고 간다.
    assert TOTAL_BRANCH[1] not in set(change["branch_name"])
    assert len(data.asset_change_total) == (
        len(ALL_ASSET_TYPES) * (len(MONTHS) - 1)
    )


def test_asset3_rows_may_come_in_any_order(source_files):
    """이름이 붙어 있으므로 행이 뒤섞여도 값이 밀리지 않는다."""
    ordered = source_files()()
    shuffled_frame = (
        _asset3_frame().sample(frac=1, random_state=7).reset_index(drop=True)
    )
    shuffled = source_files(asset3=shuffled_frame)()
    key = ["base_month", "branch_name", "asset_type"]
    left = ordered.asset_change.sort_values(key).reset_index(drop=True)
    right = shuffled.asset_change.sort_values(key).reset_index(drop=True)
    assert list(left["change_rate"]) == list(right["change_rate"])


def test_asset3_with_an_unknown_asset_type_is_rejected(source_files):
    """코드표에 없는 분류는 화면에서 조용히 사라지므로 멈춘다."""
    asset3 = _asset3_frame()
    asset3.loc[3, "상품분류"] = "가상자산"
    with pytest.raises(ValueError, match="쓸 수 없는 값"):
        source_files(asset3=asset3)()


def test_asset3_with_a_duplicate_asset_type_is_rejected(source_files):
    """같은 지점에 같은 분류가 둘이면 어느 값이 맞는지 알 수 없다."""
    asset3 = _asset3_frame()
    doubled = pd.concat([asset3, asset3.iloc[[0]]], ignore_index=True)
    with pytest.raises(ValueError, match="두 번 이상"):
        source_files(asset3=doubled)()


def test_asset3_may_omit_an_asset_type(source_files):
    """분류가 빠지면 그 칸만 비고 나머지는 그대로다.

    이름이 붙어 있으므로 빠진 행 때문에 값이 밀리지 않는다.
    """
    asset3 = _asset3_frame()
    dropped = asset3[asset3["상품분류"] != "금현물"].reset_index(drop=True)
    data = source_files(asset3=dropped)()
    assert "금현물" not in set(data.asset_change["asset_type"])
    assert not data.asset_change.empty


def test_asset3_with_a_month_outside_the_monthly_file_is_rejected(
    source_files,
):
    asset3 = _asset3_frame().rename(columns={int(MONTHS[1]): 209901})
    with pytest.raises(ValueError, match="없는 기준 월"):
        source_files(asset3=asset3)()


def test_asset3_is_optional_and_leaves_the_frame_empty(source_files):
    """자산3이 없으면 증감율 프레임은 비어 있고 나머지는 정상 동작한다."""
    data = source_files(with_asset=False)()
    assert data.asset_change.empty
    assert data.asset_change_total.empty
    assert not data.monthly.empty


def test_asset3_total_product_row_is_kept_as_given(source_files):
    """'전체' 분류는 14개의 합이 아니라 따로 계산된 값이라 그대로 둔다."""
    data = source_files()()
    change = data.asset_change
    picked = change[change["branch_name"] == BRANCHES[0][1]]
    by_type = picked.groupby("asset_type", observed=True)[
        "change_rate"
    ].sum()
    products = sum(by_type[name] for name in ALL_ASSET_TYPES[:-1])
    assert by_type[ALL_ASSET_TYPES[-1]] != pytest.approx(products)


# --- 월별 연금 자산(자산4) -----------------------------------------------------
def test_asset4_joins_the_monthly_frame(source_files):
    """자산4의 값이 기준월·지점 그대로 월별 프레임에 붙는다.

    금액은 원본이 이미 억원이라 환산하지 않는다.
    """
    data = source_files()()
    joined = data.monthly.set_index(["base_month", "branch_id"])
    for month_index, month in enumerate(MONTHS):
        key_month = f"{month[:4]}-{month[4:]}"
        for branch_index, (code, _name) in enumerate(BRANCHES):
            row = joined.loc[(key_month, code)]
            assert row["pension_customer_count"] == _pension_count(
                branch_index, month_index, 0
            )
            assert row["irp_assets"] == pytest.approx(
                _pension_assets(branch_index, month_index, 1)
            )
            assert row["dc_customer_count"] == _pension_count(
                branch_index, month_index, 2
            )


def test_asset4_total_row_is_kept_for_every_month(source_files):
    """'전체' 행은 월마다 따로 들고 간다. 추이 그래프의 막대가 그 값이다."""
    data = source_files()()
    totals = data.monthly_total.set_index("base_month")
    assert len(totals) == len(MONTHS)
    for month_index, month in enumerate(MONTHS):
        expected = sum(
            _pension_assets(branch_index, month_index, 0)
            for branch_index in range(len(BRANCHES))
        )
        key_month = f"{month[:4]}-{month[4:]}"
        assert totals.loc[key_month, "pension_assets"] == pytest.approx(
            expected
        )


def test_asset4_total_row_is_checked_against_the_branch_sum(source_files):
    """'전체' 행의 연금 자산이 지점 합계와 다르면 멈춘다."""
    asset4 = _asset4_frame()
    is_total = asset4["CSMT_ORZ_CD"] == TOTAL_BRANCH[0]
    first = asset4[is_total].index[0]
    asset4.loc[first, "IRP자산"] = int(asset4.loc[first, "IRP자산"]) + 9
    with pytest.raises(ValueError, match="'전체' 행과 지점 합계가 다릅니다"):
        source_files(asset4=asset4)()


def test_asset4_values_are_not_checked_against_asset2(source_files):
    """자산2와 같은 지표를 담고 있지만 집계 기준이 달라 대조하지 않는다.

    값이 달라도 멈추지 않고 각 파일의 값을 그대로 들고 가야 한다.
    """
    data = source_files()()
    last = f"{MONTHS[-1][:4]}-{MONTHS[-1][4:]}"
    monthly = data.monthly.set_index(["base_month", "branch_name"])
    summary = data.summary.set_index("branch_name")
    name = BRANCHES[0][1]
    assert monthly.loc[(last, name), "pension_assets"] != pytest.approx(
        summary.loc[name, "pension_assets"]
    )
    assert pd.notna(monthly.loc[(last, name), "pension_assets"])
    assert pd.notna(summary.loc[name, "pension_assets"])


def test_asset4_is_optional_and_missing_values_stay_empty(source_files):
    """자산4가 없으면 연금 컬럼은 0이 아니라 빈 값으로 남는다."""
    data = source_files(with_asset=False)()
    for column in ("pension_assets", "irp_customer_count", "dc_assets"):
        assert data.monthly[column].isna().all(), column


def test_asset4_with_a_different_branch_set_is_rejected(source_files):
    """한쪽 파일에만 있는 지점·월이 있으면 조용히 비우지 않고 멈춘다."""
    asset4 = _asset4_frame().drop(index=0).reset_index(drop=True)
    with pytest.raises(ValueError, match="없는 기준월·지점이"):
        source_files(asset4=asset4)()


def test_asset4_with_duplicate_rows_is_rejected(source_files):
    """한 지점이 한 달에 두 번 나오면 어느 값이 맞는지 알 수 없으므로 멈춘다."""
    asset4 = _asset4_frame()
    doubled = pd.concat([asset4, asset4.iloc[[0]]], ignore_index=True)
    with pytest.raises(ValueError, match="두 번 이상 있습니다"):
        source_files(asset4=doubled)()


def test_asset4_missing_source_column_names_itself(source_files):
    asset4 = _asset4_frame().drop(columns=["DC자산"])
    with pytest.raises(ValueError, match="DC자산"):
        source_files(asset4=asset4)()


def test_asset_average_is_not_summed_into_the_total(source_files):
    """평균 자산은 더할 수 없으므로 지점 합계와 대조하지 않는다.

    '전체' 행의 평균이 지점 합계와 다르다는 이유로 멈추면 안 된다.
    """
    data = source_files()()
    given = _asset1_frame()
    total = given[given["CSMT_ORZ_CD"] == TOTAL_BRANCH[0]]["고객평균자산_백만원"]
    branch_sum = given[given["CSMT_ORZ_CD"] != TOTAL_BRANCH[0]][
        "고객평균자산_백만원"
    ].sum()
    assert total.iloc[0] != pytest.approx(branch_sum)
    assert data.monthly_total["average_assets"].notna().all()


# --- 상담1 -------------------------------------------------------------------
def test_consulting_rows_reach_the_frame(source_files):
    """상담 원본이 표준 프레임으로 들어오고 '전체'는 따로 남는다."""
    data = source_files()()
    assert len(data.consulting) == (
        len(MONTHS)
        * len(BRANCHES)
        * len(CONSULTING_TYPES)
        * CONSULTING_TOPICS
    )
    assert set(data.consulting["consulting_type"]) == set(CONSULTING_TYPES)
    assert set(data.consulting_total["branch_name"]) == {TOTAL_BRANCH[1]}


def test_consulting_is_optional_and_leaves_the_frame_empty(source_files):
    data = source_files(with_consulting=False)()
    assert data.consulting.empty


def test_consulting_numbers_are_kept_in_order(source_files):
    """원본이 뒤섞여 들어와도 번호 순으로 세운다."""
    shuffled = _consulting_frame().sort_values("번호", ascending=False)
    data = source_files(consulting1=shuffled)()
    keys = ["base_month", "branch_id", "consulting_type"]
    for _key, group in data.consulting.groupby(keys, observed=True):
        assert group["topic_rank"].tolist() == list(
            range(1, CONSULTING_TOPICS + 1)
        )


def test_consulting_percent_sign_is_stripped(source_files):
    """`16%`처럼 기호가 붙어 와도 숫자로 읽는다."""
    data = source_files()()
    shares = data.consulting["topic_share"]
    assert shares.between(0, 100).all()
    assert shares.max() > 1


def test_consulting_plain_numbers_are_read_too(source_files):
    """기호 없이 숫자만 오는 파일도 그대로 읽는다."""
    plain = _consulting_frame()
    plain["비중"] = plain["비중"].str.rstrip("%").astype(float)
    data = source_files(consulting1=plain)()
    assert data.consulting["topic_share"].max() > 1


def test_consulting_ratio_given_where_a_percent_is_expected_is_rejected(
    source_files,
):
    """0~1 비율을 %로 잘못 읽으면 화면 숫자가 100배 어긋난다."""
    ratio = _consulting_frame()
    ratio["비중"] = ratio["비중"].str.rstrip("%").astype(float) / 100.0
    with pytest.raises(ValueError, match="SHARE_IN_RATIO"):
        source_files(consulting1=ratio)()


def test_consulting_share_that_cannot_be_read_names_itself(source_files):
    """읽을 수 없는 값을 0으로 덮지 않고 그 값을 알리며 멈춘다."""
    broken = _consulting_frame()
    broken.loc[0, "비중"] = "약 16 퍼센트"
    with pytest.raises(ValueError, match="비중"):
        source_files(consulting1=broken)()


def test_consulting_duplicate_numbers_are_rejected(source_files):
    """같은 번호가 두 번 나오면 어느 쪽이 맞는지 화면에서 알 수 없다."""
    consulting = _consulting_frame()
    doubled = pd.concat(
        [consulting, consulting.iloc[[0]]], ignore_index=True
    )
    with pytest.raises(ValueError, match="같은 번호가"):
        source_files(consulting1=doubled)()


def test_consulting_month_outside_the_monthly_file_is_rejected(source_files):
    """두 파일의 기간이 어긋나면 조용히 비워 두지 않고 멈춘다."""
    consulting = _consulting_frame()
    one_month = consulting[consulting["기준월"] == int(MONTHS[0])].copy()
    one_month["기준월"] = 202001
    consulting = one_month
    with pytest.raises(ValueError, match="기준 월"):
        source_files(consulting1=consulting)()


def test_consulting_missing_source_column_names_itself(source_files):
    consulting = _consulting_frame().drop(columns=["주요내용"])
    with pytest.raises(ValueError, match="주요내용"):
        source_files(consulting1=consulting)()


# --- 거래1·거래2·거래3 -------------------------------------------------------
def test_transaction_rows_are_unfolded_by_product(source_files):
    """상품이 가로로 펼쳐진 원본이 한 줄에 한 상품인 형태로 들어온다."""
    data = source_files()()
    frame = data.transaction

    assert list(frame["product_type"].cat.categories) == list(
        ALL_TRADE_PRODUCT_TYPES
    )
    # 지점 × 월 × 상품. '전체' 지점 행은 여기서 빠져 있다.
    assert len(frame) == (
        len(BRANCHES) * len(MONTHS) * len(ALL_TRADE_PRODUCT_TYPES)
    )

    first = frame[
        (frame["branch_name"] == BRANCHES[0][1])
        & (frame["base_month"] == "2025-11")
    ].set_index("product_type")
    for seed, product in enumerate(
        transaction1_source.PRODUCT_COLUMNS
    ):
        assert first.loc[product, "trade_amount"] == _trade_amount(0, 0, seed)
        assert first.loc[product, "trade_customer_count"] == _trade_count(
            0, 0, seed
        )


def test_transaction_total_product_is_kept_as_given(source_files):
    """'전체' 상품은 상품별 합이 아니라 원본 값을 그대로 쓴다.

    한 고객이 두 상품을 거래하면 거래고객수는 상품별 합보다 작다. 더해서
    만들면 화면 숫자가 원본과 달라진다.
    """
    data = source_files()()
    frame = data.transaction
    first = frame[
        (frame["branch_name"] == BRANCHES[0][1])
        & (frame["base_month"] == "2025-11")
    ].set_index("product_type")

    products = [
        product
        for product in ALL_TRADE_PRODUCT_TYPES
        if product != TRADE_PRODUCT_TOTAL
    ]
    kept = first.loc[TRADE_PRODUCT_TOTAL, "trade_customer_count"]
    assert kept == _trade_count(0, 0, 0)
    assert kept != sum(
        first.loc[product, "trade_customer_count"] for product in products
    )


def test_transaction_total_row_is_checked_against_the_branch_sum(
    source_files,
):
    """원본의 '전체' 지점 행이 지점 합계와 다르면 멈춘다."""
    frame = _transaction1_frame()
    is_total = frame["CSMT_ORZ_NM"] == TOTAL_BRANCH[1]
    frame.loc[is_total, "국내주식_거래고객수"] += 500
    with pytest.raises(ValueError, match="지점 합계"):
        source_files(transaction1=frame)()


def test_transaction_duplicate_month_and_branch_is_rejected(source_files):
    """같은 기준월·지점이 두 번 있으면 합계가 조용히 두 배가 된다."""
    frame = _transaction1_frame()
    doubled = pd.concat([frame, frame.iloc[[0]]], ignore_index=True)
    with pytest.raises(ValueError, match="두 번 이상"):
        source_files(transaction1=doubled)()


def test_transaction_missing_product_column_names_itself(source_files):
    frame = _transaction1_frame().drop(columns=["채권_거래금액"])
    with pytest.raises(ValueError, match="채권_거래금액"):
        source_files(transaction1=frame)()


def test_pension_transaction_keeps_the_type_axis(source_files):
    """거래2는 연금 구분 축이 하나 더 있다."""
    data = source_files()()
    frame = data.pension_transaction

    assert list(frame["pension_type"].cat.categories) == list(PENSION_TYPES)
    assert len(frame) == (
        len(BRANCHES)
        * len(MONTHS)
        * len(PENSION_TYPES)
        * len(transaction2_source.PRODUCT_COLUMNS)
    )


def test_pension_transaction_other_product_has_no_customer_count(
    source_files,
):
    """원본에 없는 거래고객수를 0으로 채우지 않고 비워 둔다.

    0은 '없음'이 아니라 '0으로 측정됨'을 뜻한다. 화면에는 `-`로 나타난다.
    """
    data = source_files()()
    frame = data.pension_transaction
    other = frame[frame["product_type"] == "기타"]

    assert len(other) > 0
    assert other["trade_customer_count"].isna().all()
    assert other["trade_amount"].notna().all()
    # 나머지 상품은 값이 다 있다.
    rest = frame[frame["product_type"] != "기타"]
    assert rest["trade_customer_count"].notna().all()


def test_pension_transaction_unknown_type_names_itself(source_files):
    """'구분'에 낯선 값이 있으면 조용히 사라지지 않고 그 값을 알린다."""
    frame = _transaction2_frame()
    frame.loc[0, "구분"] = "퇴직연금"
    with pytest.raises(ValueError, match="퇴직연금"):
        source_files(transaction2=frame)()


def test_cash_flow_rows_are_unfolded_by_channel(source_files):
    """거래3은 채널마다 한 줄이 된다."""
    data = source_files()()
    frame = data.cash_flow

    assert list(frame["channel"].cat.categories) == list(
        ALL_CASH_FLOW_CHANNELS
    )
    assert len(frame) == (
        len(BRANCHES) * len(MONTHS) * len(ALL_CASH_FLOW_CHANNELS)
    )

    first = frame[
        (frame["branch_name"] == BRANCHES[0][1])
        & (frame["base_month"] == "2025-11")
    ].set_index("channel")
    assert first.loc["증권", "deposit_amount"] == _trade_amount(0, 0, 2)
    assert first.loc["증권", "withdrawal_amount"] == _trade_amount(0, 0, 0)


def test_cash_flow_total_channel_keeps_only_the_net(source_files):
    """'전체' 채널에는 순입금만 있다. 입금·출금은 원본에 없어 비어 있다."""
    data = source_files()()
    total = data.cash_flow[
        data.cash_flow["channel"] == CASH_FLOW_CHANNEL_TOTAL
    ]

    assert len(total) > 0
    assert total["net_amount"].notna().all()
    assert total["deposit_amount"].isna().all()
    assert total["withdrawal_amount"].isna().all()


def test_cash_flow_keeps_negative_net_amounts(source_files):
    """순입금은 빠져나간 달에 음수가 된다. 인원수와 달리 막지 않는다.

    세 컬럼 모두 음수를 가질 수 있다. 어느 한 채널만 통과하고 다른 쪽이
    막히면 그 채널만 화면에서 사라진다.
    """
    frame = _transaction3_frame()
    given = {"증권": -12.5, "은행": -3.4, CASH_FLOW_CHANNEL_TOTAL: -15.9}
    for channel, value in given.items():
        _, _, net_column = transaction3_source.CHANNEL_COLUMNS[channel]
        frame.loc[0, net_column] = value
    data = source_files(transaction3=frame)()

    kept = data.cash_flow[
        (data.cash_flow["branch_name"] == BRANCHES[0][1])
        & (data.cash_flow["base_month"] == "2025-11")
    ].set_index("channel")
    for channel, value in given.items():
        assert kept.loc[channel, "net_amount"] == value


def test_transaction_month_outside_the_monthly_file_is_rejected(
    source_files,
):
    """두 파일의 기간이 어긋나면 조용히 비워 두지 않고 멈춘다."""
    frame = _transaction1_frame()
    one_month = frame[frame["기준월"] == int(MONTHS[0])].copy()
    one_month["기준월"] = 202001
    with pytest.raises(ValueError, match="기준 월"):
        source_files(transaction1=one_month)()


def test_transaction_files_are_optional_and_leave_the_frames_empty(
    source_files,
):
    """거래 파일이 없어도 화면은 열린다. 그 프레임만 비어 있다."""
    data = source_files(with_transaction=False)()

    assert data.transaction.empty
    assert data.pension_transaction.empty
    assert data.cash_flow.empty
    # 다른 프레임은 그대로다.
    assert data.branch_names == [name for _, name in BRANCHES]


def test_transaction_customers_join_the_monthly_frame(source_files):
    """거래1의 '전체' 상품 거래고객수가 상단 카드의 분자가 된다."""
    data = source_files()()
    monthly = data.monthly
    row = monthly[
        (monthly["branch_name"] == BRANCHES[0][1])
        & (monthly["base_month"] == "2025-11")
    ].iloc[0]
    assert row["transaction_customer_count"] == _trade_count(0, 0, 0)


def test_transaction_customers_are_not_summed_over_products(source_files):
    """상품별 합을 쓰면 한 고객이 여러 번 세어져 공통고객 수를 넘는다.

    원본이 따로 담고 있는 '전체' 상품 값을 그대로 써야 한다.
    """
    data = source_files()()
    summed = sum(
        _trade_count(0, 0, seed)
        for seed in range(1, len(transaction1_source.PRODUCT_COLUMNS))
    )
    monthly = data.monthly
    row = monthly[
        (monthly["branch_name"] == BRANCHES[0][1])
        & (monthly["base_month"] == "2025-11")
    ].iloc[0]
    assert row["transaction_customer_count"] != summed
    assert row["transaction_customer_count"] <= row["customer_count"]


def test_transaction_customers_reach_the_total_row(source_files):
    """'전체' 지점 행에도 붙어야 상단 카드가 전체 기준으로 계산된다."""
    data = source_files()()
    total = data.monthly_total
    assert not total.empty
    assert total["transaction_customer_count"].notna().all()


def test_transaction_customers_stay_empty_without_the_source(source_files):
    """거래1이 없으면 비운 채로 둔다. 0으로 채우지 않는다."""
    data = source_files(with_transaction=False)()
    assert data.monthly["transaction_customer_count"].isna().all()


def test_revenue_rows_are_unfolded_by_type(source_files):
    """수익 분류가 가로로 펼쳐진 원본이 한 줄에 한 분류인 형태로 들어온다."""
    data = source_files()()
    frame = data.revenue

    assert list(frame["revenue_type"].cat.categories) == list(
        ALL_REVENUE_TYPES
    )
    # 지점 × 월 × 분류. '전체' 지점 행은 여기서 빠져 있다.
    assert len(frame) == (
        len(BRANCHES) * len(MONTHS) * len(ALL_REVENUE_TYPES)
    )

    first = frame[
        (frame["branch_name"] == BRANCHES[0][1])
        & (frame["base_month"] == "2025-11")
    ].set_index("revenue_type")
    amounts = _revenue_amounts(0, 0)
    for revenue_type, columns in revenue1_source.TYPE_COLUMNS.items():
        assert first.loc[revenue_type, "revenue_amount"] == amounts[
            columns[0]
        ]


def test_revenue_amounts_stay_in_won(source_files):
    """수익은 원 단위 그대로 들어온다. 억원으로 바꾸지 않는다."""
    data = source_files()()
    frame = data.revenue
    row = frame[
        (frame["branch_name"] == BRANCHES[0][1])
        & (frame["base_month"] == "2025-11")
        & (frame["revenue_type"] == REVENUE_FINAL)
    ].iloc[0]
    amounts = _revenue_amounts(0, 0)
    assert row["revenue_amount"] == amounts["수익_공통_최종"]
    assert row["all_revenue_amount"] == amounts["수익_전체_최종"]


def test_revenue_all_customer_amount_is_only_on_the_group_rows(source_files):
    """전체고객 수익은 상품별로 나뉘어 있지 않아 묶음 행에만 있다.

    없는 칸을 0으로 채우지 않는다. 0은 '없음'이 아니라 '0으로 측정됨'이다.
    """
    data = source_files()()
    frame = data.revenue
    groups = frame[frame["revenue_type"].isin(REVENUE_GROUP_TYPES)]
    products = frame[~frame["revenue_type"].isin(REVENUE_GROUP_TYPES)]

    assert len(products) > 0
    assert groups["all_revenue_amount"].notna().all()
    assert products["all_revenue_amount"].isna().all()
    # 공통고객 수익은 모든 분류에 있다.
    assert frame["revenue_amount"].notna().all()


def test_revenue_share_is_empty_where_the_source_has_none(source_files):
    """원본에 비중 컬럼이 없는 '리테일'·'최종'은 비운 채로 둔다."""
    data = source_files()()
    frame = data.revenue
    empty = frame[frame["revenue_type"].isin([REVENUE_RETAIL, REVENUE_FINAL])]
    given = frame[~frame["revenue_type"].isin([REVENUE_RETAIL, REVENUE_FINAL])]

    assert empty["revenue_share"].isna().all()
    assert given["revenue_share"].notna().all()


def test_revenue_common_share_is_kept_on_the_final_row(source_files):
    """전체고객 대비 공통고객 비중은 분류축이 없어 '최종' 행에만 담긴다."""
    data = source_files()()
    frame = data.revenue
    final = frame[frame["revenue_type"] == REVENUE_FINAL]
    rest = frame[frame["revenue_type"] != REVENUE_FINAL]

    assert final["common_revenue_share"].notna().all()
    assert rest["common_revenue_share"].isna().all()
    amounts = _revenue_amounts(0, 0)
    expected = _revenue_shares(amounts)[revenue1_source.SOURCE_COMMON_SHARE]
    row = final[
        (final["branch_name"] == BRANCHES[0][1])
        & (final["base_month"] == "2025-11")
    ].iloc[0]
    assert row["common_revenue_share"] == expected


def test_revenue_share_is_used_as_given(source_files):
    """원본이 담고 있는 비중을 다시 계산하지 않고 그대로 쓴다."""
    frame = _revenue1_frame()
    # 금액과 앞뒤가 맞지 않는 값을 넣어도 그대로 통과해야 한다.
    frame["수익_공통_국내주식_비중"] = 12.3
    data = source_files(revenue1=frame)()
    shares = data.revenue[data.revenue["revenue_type"] == "국내주식"]
    assert (shares["revenue_share"] == 12.3).all()


def test_revenue_total_row_is_kept_apart(source_files):
    """원본의 '전체' 지점 행은 지점 데이터와 섞이지 않고 따로 남는다."""
    data = source_files()()
    assert TOTAL_BRANCH[1] not in set(data.revenue["branch_name"])
    total = data.revenue_total
    assert set(total["branch_name"]) == {TOTAL_BRANCH[1]}
    assert len(total) == len(MONTHS) * len(ALL_REVENUE_TYPES)


def test_revenue_is_optional_and_leaves_the_frame_empty(source_files):
    """수익1이 없어도 나머지 화면은 그대로 열린다."""
    data = source_files(with_revenue=False)()
    assert data.revenue.empty
    assert list(data.revenue.columns) == list(REVENUE_COLUMNS) + list(
        REVENUE_OPTIONAL_COLUMNS
    )


def test_revenue_duplicate_month_and_branch_is_rejected(source_files):
    """같은 기준월·지점이 두 번 있으면 합계가 조용히 두 배가 된다."""
    frame = _revenue1_frame()
    doubled = pd.concat([frame, frame.iloc[[0]]], ignore_index=True)
    with pytest.raises(ValueError, match="두 번 이상"):
        source_files(revenue1=doubled)()


def test_revenue_missing_source_column_names_itself(source_files):
    frame = _revenue1_frame().drop(columns=["수익_공통_채권"])
    with pytest.raises(ValueError, match="수익_공통_채권"):
        source_files(revenue1=frame)()


def test_revenue_month_outside_the_monthly_file_is_rejected(source_files):
    """월별 파일에 없는 달이 있으면 두 파일의 기간이 어긋난 것이다."""
    frame = _revenue1_frame()
    frame.loc[0, "기준월"] = 202602
    with pytest.raises(ValueError, match="2026-02"):
        source_files(revenue1=frame)()


def test_revenue_negative_amount_is_allowed(source_files):
    """수익은 손실이 나면 음수가 된다. 인원수와 달리 막지 않는다."""
    frame = _revenue1_frame()
    frame["수익_공통_기타"] = -1_500_000
    data = source_files(revenue1=frame)()
    other = data.revenue[data.revenue["revenue_type"] == "기타"]
    assert (other["revenue_amount"] == -1_500_000).all()


def test_revenue_final_must_equal_retail_plus_pension(source_files):
    """'리테일 + 퇴직 = 최종'이 어긋나면 멈춘다. 공통고객 쪽."""
    frame = _revenue1_frame()
    frame.loc[0, "수익_공통_최종"] += 1
    with pytest.raises(ValueError, match="수익_공통_최종"):
        source_files(revenue1=frame)()


def test_revenue_all_customer_final_is_checked_too(source_files):
    """전체고객 쪽에서도 같은 관계가 성립해야 한다."""
    frame = _revenue1_frame()
    frame.loc[0, "수익_전체_퇴직"] -= 10_000
    with pytest.raises(ValueError, match="수익_전체_최종"):
        source_files(revenue1=frame)()


def test_revenue_group_sum_is_not_recomputed(source_files):
    """관계가 맞으면 '최종'은 원본 값 그대로 화면까지 간다."""
    data = source_files()()
    frame = data.revenue
    row = frame[
        (frame["branch_name"] == BRANCHES[0][1])
        & (frame["base_month"] == "2025-11")
    ].set_index("revenue_type")
    assert (
        row.loc[REVENUE_FINAL, "revenue_amount"]
        == row.loc[REVENUE_RETAIL, "revenue_amount"]
        + row.loc[REVENUE_PENSION, "revenue_amount"]
    )


def test_revenue_etf_column_name_has_no_underscore(source_files):
    """국내ETF 금액 컬럼은 '수익_공통_국내ETF'다.

    비중 컬럼과 표기가 같다. 밑줄을 넣은 이름으로 읽으면 컬럼을 못 찾아
    파일 전체가 열리지 않는다.
    """
    amount, _all_amount, share = revenue1_source.TYPE_COLUMNS["국내ETF"]
    assert amount == "수익_공통_국내ETF"
    assert share == "수익_공통_국내ETF_비중"
    # 표본도 그 이름으로 담겨 있고 그대로 읽힌다.
    frame = _revenue1_frame()
    assert amount in frame.columns
    data = source_files(revenue1=frame)()
    rows = data.revenue[data.revenue["revenue_type"] == "국내ETF"]
    assert rows["revenue_amount"].notna().all()


# --- 상품 국내주식1 ----------------------------------------------------------
def test_domestic_stock_rank_rows_reach_the_frame(source_files):
    """원본의 순위 행이 표준 프레임까지 들어온다.

    행 수는 지점 × 순위다. '전체' 지점 행은 여기서 빠져 있다.
    """
    data = source_files()()
    frame = data.domestic_stock_rank
    assert len(frame) == len(BRANCHES) * STOCK_RANKS
    assert TOTAL_BRANCH[1] not in set(frame["branch_name"])
    # 원본이 마지막 한 달만 담고 있어도 그대로 들어온다.
    assert sorted(frame["base_month"].unique()) == ["2026-01"]
    row = frame[frame["branch_name"] == BRANCHES[0][1]].iloc[0]
    assert row["stock_rank"] == 1
    assert row["stock_name"] == "종목 01"


def test_domestic_stock_rank_rank_total_row_is_kept_apart(source_files):
    """'전체' 행은 지점 데이터와 섞이지 않고 따로 남는다.

    섞이면 어느 지점의 순위인지 알 수 없는 행이 표에 끼어든다.
    """
    data = source_files()()
    total = data.domestic_stock_rank_total
    assert set(total["branch_name"]) == {TOTAL_BRANCH[1]}
    assert len(total) == STOCK_RANKS


def test_domestic_stock_rank_is_optional_and_leaves_the_frame_empty(source_files):
    """원본이 없어도 나머지 화면은 열린다."""
    data = source_files(with_product=False)()
    assert data.domestic_stock_rank.empty
    assert data.domestic_stock_rank_total.empty


def test_domestic_stock_rank_units_are_kept_as_given(source_files):
    """시가총액은 억원, 거래대금·순매수금액은 원 그대로 넘어온다."""
    source = _domestic_stock1_frame()
    data = source_files(domestic_stock1=source)()
    given = source[source["CSMT_ORZ_NM"] == BRANCHES[0][1]].iloc[0]
    row = data.domestic_stock_rank[
        data.domestic_stock_rank["branch_name"] == BRANCHES[0][1]
    ].iloc[0]
    assert row["market_cap"] == given["시가총액"]
    assert row["trade_value"] == given["거래대금"]
    assert row["trade_customer_count"] == given["거래고객수"]


def test_domestic_stock_rank_keeps_negative_net_buy(source_files):
    """순매도인 종목의 순매수금액은 음수 그대로 남는다."""
    data = source_files()()
    assert (data.domestic_stock_rank["net_buy_amount"] < 0).any()


def test_domestic_stock_rank_rank_change_keeps_its_sign(source_files):
    """`+2`·`-1`·`0`을 부호가 있는 숫자로 읽는다."""
    data = source_files()()
    changes = data.domestic_stock_rank.set_index(
        ["branch_name", "stock_rank"]
    )["rank_change"]
    branch = BRANCHES[0][1]
    assert changes[(branch, 1)] == 2
    assert changes[(branch, 2)] == -1
    assert changes[(branch, 3)] == 0


def test_domestic_stock_rank_new_entry_rank_change_stays_empty(source_files):
    """앞 달에 없던 종목은 순위변동을 비운 채로 둔다.

    0으로 채우면 '순위가 그대로'라는 뜻이 되어 뜻이 달라진다.
    """
    frame = _domestic_stock1_frame()
    frame.loc[0, "순위변동"] = "신규"
    data = source_files(domestic_stock1=frame)()
    rows = data.domestic_stock_rank[
        data.domestic_stock_rank["branch_name"] == BRANCHES[0][1]
    ].set_index("stock_rank")
    assert pd.isna(rows.loc[1, "rank_change"])


def test_domestic_stock_rank_unknown_rank_change_stops(source_files):
    """모르는 표기를 조용히 버리지 않고 그 값을 알리며 멈춘다."""
    frame = _domestic_stock1_frame()
    frame.loc[0, "순위변동"] = "위로"
    with pytest.raises(ValueError, match="순위변동"):
        source_files(domestic_stock1=frame)()


def test_domestic_stock_rank_empty_sector_is_kept_empty(source_files):
    """업종이 비어 있는 종목은 빈 값 그대로 넘어온다."""
    data = source_files()()
    sectors = data.domestic_stock_rank["sector"]
    assert (sectors == "").any()
    assert sectors.notna().all()


def test_domestic_stock_rank_missing_stock_name_stops(source_files):
    """종목명이 비어 있으면 어느 컬럼인지 알리며 멈춘다."""
    frame = _domestic_stock1_frame()
    frame.loc[0, "종목명"] = ""
    with pytest.raises(ValueError, match="stock_name"):
        source_files(domestic_stock1=frame)()


def test_domestic_stock_rank_duplicate_rank_stops(source_files):
    """한 지점에 같은 순위가 두 번 있으면 멈춘다."""
    frame = _domestic_stock1_frame()
    frame.loc[1, "순위"] = frame.loc[0, "순위"]
    with pytest.raises(ValueError, match="순위"):
        source_files(domestic_stock1=frame)()


def test_domestic_stock_rank_duplicate_name_stops(source_files):
    """한 지점에 같은 종목이 두 번 있으면 멈춘다.

    트리맵에서 그 종목의 면적이 두 번 더해진다.
    """
    frame = _domestic_stock1_frame()
    frame.loc[1, "종목명"] = frame.loc[0, "종목명"]
    with pytest.raises(ValueError, match="종목"):
        source_files(domestic_stock1=frame)()


def test_domestic_stock_rank_negative_market_cap_stops(source_files):
    """시가총액이 음수면 읽는 방법이 틀렸다는 뜻이라 멈춘다."""
    frame = _domestic_stock1_frame()
    frame.loc[0, "시가총액"] = -1
    with pytest.raises(ValueError, match="시가총액"):
        source_files(domestic_stock1=frame)()


def test_domestic_stock_rank_month_outside_the_monthly_file_stops(source_files):
    """월별 파일에 없는 기준 월이 있으면 두 파일이 어긋났다는 뜻이다."""
    frame = _domestic_stock1_frame()
    frame["기준월"] = 202603
    with pytest.raises(ValueError, match="기준 월"):
        source_files(domestic_stock1=frame)()


def test_domestic_stock_rank_numbers_with_commas_are_read(source_files):
    """`-1,234`처럼 표기가 붙어 와도 숫자로 읽는다."""
    frame = _domestic_stock1_frame()
    frame["순매수금액"] = frame["순매수금액"].map(lambda value: f"{value:,}")
    data = source_files(domestic_stock1=frame)()
    assert data.domestic_stock_rank["net_buy_amount"].notna().all()
    assert (data.domestic_stock_rank["net_buy_amount"] < 0).any()


# --- 상품 국내주식2 ----------------------------------------------------------
def test_domestic_stock_cap_rows_reach_the_frame(source_files):
    """시가총액 상위 종목 행이 표준 프레임까지 들어온다.

    지점마다 거래한 종목만 있어 행 수가 지점 × 종목보다 적다.
    """
    data = source_files()()
    frame = data.domestic_stock_cap
    assert len(frame) == len(BRANCHES) * STOCK_CAP_COUNT - 1
    assert TOTAL_BRANCH[1] not in set(frame["branch_name"])
    assert sorted(frame["base_month"].unique()) == ["2026-01"]
    assert set(frame["stock_name"]) == {
        f"종목 {index + 1:02d}" for index in range(STOCK_CAP_COUNT)
    }


def test_domestic_stock_cap_allows_uneven_row_counts(source_files):
    """지점마다 행 수가 달라도 그대로 둔다.

    거래하지 않은 종목을 0으로 채우면 '거래 없음'이 '0으로 측정됨'이 된다.
    """
    data = source_files()()
    counts = data.domestic_stock_cap.groupby("branch_name").size()
    assert counts[BRANCHES[0][1]] == STOCK_CAP_COUNT - 1
    assert counts[BRANCHES[1][1]] == STOCK_CAP_COUNT
    # 빠진 종목이 결측 행으로 채워지지도 않는다.
    rows = data.domestic_stock_cap[
        data.domestic_stock_cap["branch_name"] == BRANCHES[0][1]
    ]
    assert f"종목 {SKIPPED_STOCK + 1:02d}" not in set(rows["stock_name"])


def test_domestic_stock_cap_total_row_is_kept_apart(source_files):
    """'전체' 행은 지점 데이터와 섞이지 않고 따로 남는다."""
    data = source_files()()
    total = data.domestic_stock_cap_total
    assert set(total["branch_name"]) == {TOTAL_BRANCH[1]}
    assert len(total) == STOCK_CAP_COUNT


def test_domestic_stock_cap_is_optional(source_files):
    """원본이 없어도 나머지 화면은 열린다."""
    data = source_files(with_product=False)()
    assert data.domestic_stock_cap.empty
    assert data.domestic_stock_cap_total.empty


def test_domestic_stock_cap_negative_amount_text_is_read(source_files):
    """`-70000` 처럼 부호가 붙은 글도 음수로 읽는다."""
    data = source_files()()
    amounts = data.domestic_stock_cap["net_buy_amount"]
    assert amounts.notna().all()
    assert (amounts < 0).any()
    assert (amounts > 0).any()


def test_domestic_stock_cap_units_are_kept_as_given(source_files):
    """시가총액은 억원, 거래대금은 원 그대로 넘어온다."""
    source = _domestic_stock2_frame()
    data = source_files(domestic_stock2=source)()
    given = source[source["CSMT_ORZ_NM"] == BRANCHES[1][1]].iloc[0]
    row = data.domestic_stock_cap[
        (data.domestic_stock_cap["branch_name"] == BRANCHES[1][1])
        & (data.domestic_stock_cap["stock_name"] == given["ITM_ABRV_NM"])
    ].iloc[0]
    assert row["market_cap"] == given["시가총액"]
    assert row["trade_value"] == given["거래대금"]
    assert row["trade_customer_count"] == given["거래고객수"]


def test_domestic_stock_cap_empty_sector_is_kept_empty(source_files):
    """업종이 비어 있는 종목은 빈 값 그대로 넘어온다."""
    data = source_files()()
    sectors = data.domestic_stock_cap["sector"]
    assert (sectors == "").any()
    assert sectors.notna().all()


def test_domestic_stock_cap_duplicate_stock_stops(source_files):
    """한 지점에 같은 종목이 두 번 있으면 멈춘다.

    트리맵에서 그 종목의 면적이 두 번 더해진다.
    """
    frame = _domestic_stock2_frame()
    frame.loc[1, "ITM_ABRV_NM"] = frame.loc[0, "ITM_ABRV_NM"]
    with pytest.raises(ValueError, match="같은 종목"):
        source_files(domestic_stock2=frame)()


def test_domestic_stock_cap_mixed_market_cap_stops(source_files):
    """같은 종목의 시가총액이 지점마다 다르면 멈춘다.

    트리맵의 면적이 지점을 바꿀 때마다 달라진다.
    """
    frame = _domestic_stock2_frame()
    last = len(frame) - 1
    frame.loc[last, "시가총액"] = frame.loc[last, "시가총액"] + 1
    with pytest.raises(ValueError, match="market_cap"):
        source_files(domestic_stock2=frame)()


def test_domestic_stock_cap_mixed_sector_stops(source_files):
    """같은 종목의 업종이 지점마다 다르면 멈춘다."""
    frame = _domestic_stock2_frame()
    frame.loc[0, "업종"] = "다른 업종"
    with pytest.raises(ValueError, match="sector"):
        source_files(domestic_stock2=frame)()


def test_domestic_stock_cap_blank_sector_is_not_a_conflict(source_files):
    """업종이 일부 행에만 비어 있어도 충돌로 보지 않는다.

    빈 값을 채워 넣지 않고, 값이 들어 있는 행끼리만 견준다.
    """
    frame = _domestic_stock2_frame()
    first = frame.index[frame["ITM_ABRV_NM"] == "종목 01"][0]
    frame.loc[first, "업종"] = ""
    data = source_files(domestic_stock2=frame)()
    assert not data.domestic_stock_cap.empty


def test_domestic_stock_cap_missing_branch_is_reported_not_fatal(
    source_files,
):
    """지점 하나가 통째로 빠져도 화면은 열리고 그 지점을 알린다.

    상위 종목을 하나도 거래하지 않은 지점이 있을 수 있다. 그렇다고 다른
    지점까지 못 보게 하지는 않는다.
    """
    frame = _domestic_stock2_frame()
    frame = frame[frame["CSMT_ORZ_NM"] != BRANCHES[0][1]]
    with pytest.warns(UserWarning, match="행이 하나도 없는 지점"):
        data = source_files(domestic_stock2=frame)()
    assert set(data.domestic_stock_cap["branch_name"]) == {BRANCHES[1][1]}


def test_domestic_stock_cap_unknown_branch_stops(source_files):
    """월별 파일에 없는 지점이 있으면 두 원본의 범위가 다르다는 뜻이다."""
    frame = _domestic_stock2_frame()
    frame.loc[0, "CSMT_ORZ_CD"] = "9999"
    frame.loc[0, "CSMT_ORZ_NM"] = "지점 99"
    with pytest.raises(ValueError, match="monthly에 없는 지점"):
        source_files(domestic_stock2=frame)()


def test_domestic_stock_cap_facts_table_has_one_row_per_stock(source_files):
    """종목표는 종목마다 한 행이고 시가총액 큰 순이다."""
    from dashboard.sources import domestic_stock2 as source

    data = source_files()()
    facts = source.stock_facts(data.domestic_stock_cap)
    assert len(facts) == STOCK_CAP_COUNT
    assert facts["market_cap"].is_monotonic_decreasing


# --- 상품 해외주식1 ----------------------------------------------------------
def test_overseas_stock_rank_rows_reach_the_frame(source_files):
    """원본의 순위 행이 표준 프레임까지 들어온다.

    행 수는 지점 × 순위다. '전체' 지점 행은 여기서 빠져 있다.
    """
    data = source_files()()
    frame = data.overseas_stock_rank
    assert len(frame) == len(BRANCHES) * STOCK_RANKS
    assert TOTAL_BRANCH[1] not in set(frame["branch_name"])
    # 원본이 마지막 한 달만 담고 있어도 그대로 들어온다.
    assert sorted(frame["base_month"].unique()) == ["2026-01"]
    row = frame[frame["branch_name"] == BRANCHES[0][1]].iloc[0]
    assert row["stock_rank"] == 1
    assert row["stock_name"] == "해외종목 01"


def test_overseas_stock_rank_total_row_is_kept_apart(source_files):
    """'전체' 행은 지점 데이터와 섞이지 않고 따로 남는다."""
    data = source_files()()
    total = data.overseas_stock_rank_total
    assert set(total["branch_name"]) == {TOTAL_BRANCH[1]}
    assert len(total) == STOCK_RANKS


def test_overseas_stock_rank_is_optional(source_files):
    """원본이 없어도 나머지 화면은 열린다."""
    data = source_files(with_product=False)()
    assert data.overseas_stock_rank.empty
    assert data.overseas_stock_rank_total.empty


def test_overseas_stock_rank_keeps_exchange_and_units(source_files):
    """거래소는 글 그대로, 거래대금·순매수금액은 원 단위 그대로 온다."""
    source = _overseas_stock1_frame()
    data = source_files(overseas_stock1=source)()
    given = source[source["CSMT_ORZ_NM"] == BRANCHES[0][1]].iloc[0]
    row = data.overseas_stock_rank[
        data.overseas_stock_rank["branch_name"] == BRANCHES[0][1]
    ].iloc[0]
    assert row["exchange"] == given["거래소"]
    assert row["trade_value"] == given["거래대금"]
    assert row["trade_customer_count"] == given["거래고객수"]
    assert row["net_buy_amount"] == float(given["순매수금액"])


def test_overseas_stock_rank_has_no_market_cap(source_files):
    """해외주식 원본에는 시가총액이 없다."""
    data = source_files()()
    assert "market_cap" not in data.overseas_stock_rank.columns


def test_overseas_stock_rank_keeps_negative_net_buy(source_files):
    """순매도인 종목의 순매수금액은 앞에 `-`가 붙은 글이라도 음수로 남는다."""
    data = source_files()()
    assert (data.overseas_stock_rank["net_buy_amount"] < 0).any()


def test_overseas_stock_rank_rank_change_keeps_its_sign(source_files):
    """`+2`·`-1`·`0`을 부호가 있는 숫자로 읽는다."""
    data = source_files()()
    changes = data.overseas_stock_rank.set_index(
        ["branch_name", "stock_rank"]
    )["rank_change"]
    assert changes[(BRANCHES[0][1], 1)] == 2
    assert changes[(BRANCHES[0][1], 2)] == -1
    assert changes[(BRANCHES[1][1], NEW_ENTRY_RANK)] == 0


def test_overseas_stock_rank_new_entry_rank_change_stays_empty(source_files):
    """앞 달에 없던 종목은 순위변동을 비운 채로 둔다.

    0으로 채우면 '순위가 그대로'라는 뜻이 되어 뜻이 달라진다. 화면이 그
    빈 칸을 'NEW'로 적는다.
    """
    data = source_files()()
    rows = data.overseas_stock_rank[
        data.overseas_stock_rank["branch_name"] == BRANCHES[0][1]
    ].set_index("stock_rank")
    assert pd.isna(rows.loc[NEW_ENTRY_RANK, "rank_change"])


def test_overseas_stock_rank_unknown_rank_change_stops(source_files):
    """읽을 수 없는 순위변동은 조용히 비우지 않고 멈춘다."""
    frame = _overseas_stock1_frame()
    frame.loc[0, "순위변동"] = "위로"
    with pytest.raises(ValueError, match="순위변동"):
        source_files(overseas_stock1=frame)()


def test_overseas_stock_rank_empty_sector_is_kept_empty(source_files):
    """비어 있는 업종은 채우지 않고 빈 값 그대로 넘긴다."""
    data = source_files()()
    sectors = data.overseas_stock_rank["sector"]
    assert (sectors == "").any()
    assert sectors.notna().all()


def test_overseas_stock_rank_missing_stock_name_stops(source_files):
    """종목명이 비어 있으면 어느 행인지 알 수 없으므로 멈춘다."""
    frame = _overseas_stock1_frame()
    frame.loc[0, "종목명"] = ""
    with pytest.raises(ValueError, match="stock_name"):
        source_files(overseas_stock1=frame)()


def test_overseas_stock_rank_duplicate_rank_stops(source_files):
    """한 지점의 한 달에 같은 순위가 두 번 있으면 멈춘다."""
    frame = _overseas_stock1_frame()
    frame.loc[1, "순위"] = frame.loc[0, "순위"]
    with pytest.raises(ValueError, match="같은 순위"):
        source_files(overseas_stock1=frame)()


def test_overseas_stock_rank_duplicate_name_stops(source_files):
    """한 지점의 한 달에 같은 종목이 두 번 있으면 멈춘다."""
    frame = _overseas_stock1_frame()
    frame.loc[1, "종목명"] = frame.loc[0, "종목명"]
    with pytest.raises(ValueError, match="같은 종목"):
        source_files(overseas_stock1=frame)()


def test_overseas_stock_rank_negative_customer_count_stops(source_files):
    """거래고객수가 음수면 원본을 읽는 방법이 틀렸다는 뜻이다."""
    frame = _overseas_stock1_frame()
    frame.loc[0, "거래고객수"] = -1
    with pytest.raises(ValueError, match="거래고객수"):
        source_files(overseas_stock1=frame)()


def test_overseas_stock_rank_month_outside_monthly_stops(source_files):
    """월별 파일에 없는 달이 있으면 두 파일의 기간이 어긋났다는 뜻이다."""
    frame = _overseas_stock1_frame()
    frame.loc[0, "기준월"] = 209912
    with pytest.raises(ValueError, match="없는 기준 월"):
        source_files(overseas_stock1=frame)()


def test_overseas_stock_rank_numbers_with_commas_are_read(source_files):
    """천 단위 쉼표가 붙은 금액도 읽는다."""
    frame = _overseas_stock1_frame()
    frame["순매수금액"] = frame["순매수금액"].map(lambda v: f"{int(v):,}")
    data = source_files(overseas_stock1=frame)()
    assert data.overseas_stock_rank["net_buy_amount"].notna().all()
    assert (data.overseas_stock_rank["net_buy_amount"] < 0).any()


# --- 상품 해외주식2 ----------------------------------------------------------
def test_overseas_stock_cap_rows_reach_the_frame(source_files):
    """시가총액 상위 종목 행이 표준 프레임까지 들어온다.

    지점마다 거래한 종목만 있어 행 수가 지점 × 종목보다 적다.
    """
    data = source_files()()
    frame = data.overseas_stock_cap
    assert frame["stock_name"].nunique() == OVERSEAS_CAP_COUNT
    assert len(frame) == len(BRANCHES) * OVERSEAS_CAP_COUNT - 1
    assert TOTAL_BRANCH[1] not in set(frame["branch_name"])
    assert sorted(frame["base_month"].unique()) == ["2026-01"]

    total = data.overseas_stock_cap_total
    assert set(total["branch_name"]) == {TOTAL_BRANCH[1]}
    assert len(total) == OVERSEAS_CAP_COUNT


def test_overseas_stock_cap_is_optional(source_files):
    """원본이 없어도 나머지 화면은 열린다."""
    data = source_files(with_product=False)()
    assert data.overseas_stock_cap.empty
    assert data.overseas_stock_cap_total.empty


def test_overseas_stock_cap_market_cap_is_dollars(source_files):
    """시가총액은 달러 그대로 오고 원화 컬럼과 이름이 다르다.

    환율을 곱해 원화로 바꾸면 그날 환율에 따라 화면 숫자가 달라진다.
    """
    source = _overseas_stock2_frame()
    data = source_files(overseas_stock2=source)()
    frame = data.overseas_stock_cap
    assert "market_cap" not in frame.columns
    given = source.iloc[0]
    row = frame[frame["stock_name"] == given["종목명"]].iloc[0]
    assert row["market_cap_usd"] == given["시가총액"]


def test_overseas_stock_cap_net_buy_is_won_and_signed(source_files):
    """순매수금액은 원화이며 앞에 `-`가 붙은 글이라도 음수로 남는다."""
    data = source_files()()
    amounts = data.overseas_stock_cap["net_buy_amount"]
    assert (amounts < 0).any()
    assert (amounts > 0).any()


def test_overseas_stock_cap_keeps_the_rank_as_given(source_files):
    """순위는 원본이 준 숫자 그대로 온다.

    무엇을 기준으로 매긴 순위인지 확인되지 않았으므로 종목의 성질로 다루지
    않는다. 지점마다 다른 순위가 와도 멈추지 않아야 한다.
    """
    frame = _overseas_stock2_frame()
    target = frame[frame["CSMT_ORZ_NM"] == BRANCHES[1][1]].index[0]
    frame.loc[target, "순위"] = 99
    data = source_files(overseas_stock2=frame)()
    rows = data.overseas_stock_cap
    row = rows[
        (rows["branch_name"] == BRANCHES[1][1])
        & (rows["stock_name"] == frame.loc[target, "종목명"])
    ].iloc[0]
    assert row["stock_rank"] == 99


def test_overseas_stock_cap_facts_leave_the_rank_out(source_files):
    """종목표에는 순위를 넣지 않는다.

    첫 행의 순위를 종목의 순위처럼 적으면 지점별 순위인 경우에 틀린 값이
    된다.
    """
    from dashboard.sources import overseas_stock2 as source

    data = source_files()()
    facts = source.stock_facts(data.overseas_stock_cap)
    assert "stock_rank" not in facts.columns


def test_overseas_stock_cap_duplicate_stock_stops(source_files):
    """한 지점에 같은 종목이 두 번 있으면 면적이 두 번 더해진다."""
    frame = _overseas_stock2_frame()
    frame.loc[1, "종목명"] = frame.loc[0, "종목명"]
    with pytest.raises(ValueError, match="같은 종목"):
        source_files(overseas_stock2=frame)()


def test_overseas_stock_cap_mixed_market_cap_stops(source_files):
    """같은 종목의 시가총액이 지점마다 다르면 멈춘다."""
    frame = _overseas_stock2_frame()
    target = frame[frame["CSMT_ORZ_NM"] == BRANCHES[1][1]].index[0]
    frame.loc[target, "시가총액"] = 1
    with pytest.raises(ValueError, match="market_cap_usd"):
        source_files(overseas_stock2=frame)()


def test_overseas_stock_cap_mixed_exchange_stops(source_files):
    """같은 종목의 거래소가 지점마다 다르면 파일이 잘못 붙은 것이다."""
    frame = _overseas_stock2_frame()
    target = frame[frame["CSMT_ORZ_NM"] == BRANCHES[1][1]].index[0]
    frame.loc[target, "거래소"] = "TSE"
    with pytest.raises(ValueError, match="exchange"):
        source_files(overseas_stock2=frame)()


def test_overseas_stock_cap_blank_sector_is_not_a_conflict(source_files):
    """비어 있는 업종은 값이 다른 것으로 보지 않는다.

    한 지점만 업종이 비어 있어도 그 종목은 업종 하나를 가진 것이다.
    """
    frame = _overseas_stock2_frame()
    target = frame[frame["CSMT_ORZ_NM"] == BRANCHES[1][1]].index[0]
    frame.loc[target, "업종"] = ""
    data = source_files(overseas_stock2=frame)()
    assert not data.overseas_stock_cap.empty


def test_overseas_stock_cap_missing_branch_is_reported_not_fatal(
    source_files,
):
    """한 종목도 거래하지 않은 지점은 행이 없어도 화면을 연다."""
    frame = _overseas_stock2_frame()
    frame = frame[frame["CSMT_ORZ_NM"] != BRANCHES[0][1]]
    with pytest.warns(UserWarning, match="행이 하나도 없는 지점"):
        data = source_files(overseas_stock2=frame)()
    assert set(data.overseas_stock_cap["branch_name"]) == {BRANCHES[1][1]}


def test_overseas_stock_cap_facts_table_has_one_row_per_stock(source_files):
    """종목표는 종목마다 한 행이고 시가총액 큰 순이다."""
    from dashboard.sources import overseas_stock2 as source

    data = source_files()()
    facts = source.stock_facts(data.overseas_stock_cap)
    assert len(facts) == OVERSEAS_CAP_COUNT
    assert facts["market_cap_usd"].is_monotonic_decreasing


# --- 상품 ETF2 ---------------------------------------------------------------
def test_etf_rows_reach_the_frame(source_files):
    """원본의 순위 행이 표준 프레임까지 들어온다.

    행 수는 지점 × 순위다. '전체' 지점 행은 여기서 빠져 있다.
    """
    data = source_files()()
    frame = data.etf_rank
    assert len(frame) == len(BRANCHES) * STOCK_RANKS
    assert TOTAL_BRANCH[1] not in set(frame["branch_name"])
    assert sorted(frame["base_month"].unique()) == ["2026-01"]
    row = frame[frame["branch_name"] == BRANCHES[0][1]].iloc[0]
    assert row["stock_rank"] == 1
    assert row["stock_name"] == "ETF 01"


def test_etf_total_row_is_kept_apart(source_files):
    """'전체' 행은 지점 데이터와 섞이지 않고 따로 남는다."""
    data = source_files()()
    total = data.etf_rank_total
    assert set(total["branch_name"]) == {TOTAL_BRANCH[1]}
    assert len(total) == STOCK_RANKS


def test_etf_is_optional(source_files):
    """원본이 없어도 나머지 화면은 열린다."""
    data = source_files(with_product=False)()
    assert data.etf_rank.empty
    assert data.etf_rank_total.empty


def test_etf_units_are_kept_as_given(source_files):
    """시가총액은 억원, 거래대금·순매수금액은 원 그대로 넘어온다."""
    source = _etf2_frame()
    data = source_files(etf2=source)()
    given = source[source["CSMT_ORZ_NM"] == BRANCHES[0][1]].iloc[0]
    row = data.etf_rank[
        data.etf_rank["branch_name"] == BRANCHES[0][1]
    ].iloc[0]
    assert row["market_cap"] == given["시가총액"]
    assert row["trade_value"] == given["거래대금"]
    assert row["trade_customer_count"] == given["거래고객수"]
    assert row["net_buy_amount"] == float(given["순매수금액"])


def test_etf_has_no_sector(source_files):
    """ETF 원본에는 업종이 없다. 종목을 묶을 축이 이 프레임에 없다."""
    data = source_files()()
    assert "sector" not in data.etf_rank.columns
    assert "exchange" not in data.etf_rank.columns


def test_etf_keeps_negative_net_buy(source_files):
    """순매도 종목의 순매수금액은 앞에 `-`가 붙은 글이라도 음수로 남는다."""
    data = source_files()()
    assert (data.etf_rank["net_buy_amount"] < 0).any()


def test_etf_rank_change_keeps_its_sign(source_files):
    """`+2`·`-1`·`0`을 부호가 있는 숫자로 읽는다."""
    data = source_files()()
    changes = data.etf_rank.set_index(["branch_name", "stock_rank"])[
        "rank_change"
    ]
    assert changes[(BRANCHES[0][1], 1)] == 2
    assert changes[(BRANCHES[0][1], 2)] == -1
    assert changes[(BRANCHES[1][1], NEW_ENTRY_RANK)] == 0


def test_etf_new_entry_rank_change_stays_empty(source_files):
    """앞 달에 없던 종목은 순위변동을 비운 채로 둔다.

    0으로 채우면 '순위가 그대로'라는 뜻이 되어 뜻이 달라진다. 화면이 그
    빈 칸을 'NEW'로 적는다.
    """
    data = source_files()()
    rows = data.etf_rank[
        data.etf_rank["branch_name"] == BRANCHES[0][1]
    ].set_index("stock_rank")
    assert pd.isna(rows.loc[NEW_ENTRY_RANK, "rank_change"])


def test_etf_unknown_rank_change_stops(source_files):
    """읽을 수 없는 순위변동은 조용히 비우지 않고 멈춘다."""
    frame = _etf2_frame()
    frame.loc[0, "순위변동"] = "위로"
    with pytest.raises(ValueError, match="순위변동"):
        source_files(etf2=frame)()


def test_etf_missing_stock_name_stops(source_files):
    """종목명이 비어 있으면 어느 행인지 알 수 없으므로 멈춘다."""
    frame = _etf2_frame()
    frame.loc[0, "종목명"] = ""
    with pytest.raises(ValueError, match="stock_name"):
        source_files(etf2=frame)()


def test_etf_duplicate_rank_stops(source_files):
    """한 지점의 한 달에 같은 순위가 두 번 있으면 멈춘다."""
    frame = _etf2_frame()
    frame.loc[1, "순위"] = frame.loc[0, "순위"]
    with pytest.raises(ValueError, match="같은 순위"):
        source_files(etf2=frame)()


def test_etf_duplicate_name_stops(source_files):
    """한 지점의 한 달에 같은 종목이 두 번 있으면 멈춘다."""
    frame = _etf2_frame()
    frame.loc[1, "종목명"] = frame.loc[0, "종목명"]
    with pytest.raises(ValueError, match="같은 종목"):
        source_files(etf2=frame)()


def test_etf_negative_market_cap_stops(source_files):
    """시가총액이 음수면 원본을 읽는 방법이 틀렸다는 뜻이다."""
    frame = _etf2_frame()
    frame.loc[0, "시가총액"] = -1
    with pytest.raises(ValueError, match="시가총액"):
        source_files(etf2=frame)()


def test_etf_month_outside_monthly_stops(source_files):
    """월별 파일에 없는 달이 있으면 두 파일의 기간이 어긋났다는 뜻이다."""
    frame = _etf2_frame()
    frame.loc[0, "기준월"] = 209912
    with pytest.raises(ValueError, match="없는 기준 월"):
        source_files(etf2=frame)()


def test_etf_numbers_with_commas_are_read(source_files):
    """천 단위 쉼표가 붙은 금액도 읽는다."""
    frame = _etf2_frame()
    frame["순매수금액"] = frame["순매수금액"].map(lambda v: f"{int(v):,}")
    data = source_files(etf2=frame)()
    assert data.etf_rank["net_buy_amount"].notna().all()
    assert (data.etf_rank["net_buy_amount"] < 0).any()


# --- 상품 펀드1 --------------------------------------------------------------
def test_fund_rows_reach_the_frame(source_files):
    """원본의 순위 행이 표준 프레임까지 들어온다.

    지점마다 순위 수가 달라 행 수는 지점 × 순위가 아니다. '전체' 지점 행은
    여기서 빠져 있다.
    """
    data = source_files()()
    frame = data.fund_rank
    assert len(frame) == STOCK_RANKS + FUND_SHORT_RANKS
    assert TOTAL_BRANCH[1] not in set(frame["branch_name"])
    assert sorted(frame["base_month"].unique()) == ["2026-01"]
    row = frame[frame["branch_name"] == BRANCHES[0][1]].iloc[0]
    assert row["stock_rank"] == 1
    assert row["stock_name"] == "펀드 01"


def test_fund_branch_may_stop_short_of_the_last_rank(source_files):
    """순위가 끝까지 차지 않는 지점도 그대로 들어온다.

    파는 종목이 적은 지점이다. 빈 순위를 채우거나 그 지점을 빼면 화면에
    없는 종목이 생기거나 지점 하나가 사라진다.
    """
    data = source_files()()
    counts = data.fund_rank.groupby("branch_name")["stock_rank"].max()
    short_branch = BRANCHES[FUND_SHORT_BRANCH][1]
    assert counts[short_branch] == FUND_SHORT_RANKS
    assert counts[BRANCHES[0][1]] == STOCK_RANKS
    # 지점은 하나도 빠지지 않는다.
    assert set(counts.index) == {name for _, name in BRANCHES}


def test_fund_total_row_is_kept_apart(source_files):
    """'전체' 행은 지점 데이터와 섞이지 않고 따로 남는다."""
    data = source_files()()
    total = data.fund_rank_total
    assert set(total["branch_name"]) == {TOTAL_BRANCH[1]}
    assert len(total) == STOCK_RANKS


def test_fund_is_optional(source_files):
    """원본이 없어도 나머지 화면은 열린다."""
    data = source_files(with_product=False)()
    assert data.fund_rank.empty
    assert data.fund_rank_total.empty


def test_fund_units_are_kept_as_given(source_files):
    """거래대금·순매수금액은 원 그대로 넘어온다."""
    source = _fund1_frame()
    data = source_files(fund1=source)()
    given = source[source["CSMT_ORZ_NM"] == BRANCHES[0][1]].iloc[0]
    row = data.fund_rank[
        data.fund_rank["branch_name"] == BRANCHES[0][1]
    ].iloc[0]
    assert row["trade_value"] == given["거래대금"]
    assert row["trade_customer_count"] == given["거래고객수"]
    assert row["net_buy_amount"] == float(given["순매수금액"])


def test_fund_has_no_market_cap(source_files):
    """펀드 원본에는 시가총액이 없다.

    칸 크기를 정할 값이 없으므로 이 프레임으로는 트리맵을 그릴 수 없다.
    있다고 보고 화면을 만들면 빈 그림이 나온다.
    """
    data = source_files()()
    for column in ("market_cap", "market_cap_usd", "sector", "exchange"):
        assert column not in data.fund_rank.columns


def test_fund_keeps_negative_net_buy(source_files):
    """순매도 종목의 순매수금액은 앞에 `-`가 붙은 글이라도 음수로 남는다."""
    data = source_files()()
    assert (data.fund_rank["net_buy_amount"] < 0).any()


def test_fund_rank_change_keeps_its_sign(source_files):
    """`+2`·`-1`을 부호가 있는 숫자로 읽는다.

    첫 지점은 첫 등수가 겹치므로 그 등수에 두 줄이 있다.
    """
    data = source_files()()
    changes = data.fund_rank.set_index(["branch_name", "stock_rank"])[
        "rank_change"
    ]
    assert sorted(changes.loc[(BRANCHES[0][1], FUND_TIED_RANK)]) == [
        -1.0,
        2.0,
    ]


def test_fund_new_entry_rank_change_stays_empty(source_files):
    """앞 달에 없던 종목은 순위변동을 비운 채로 둔다.

    그 자리는 지점마다 마지막 순위이며, 순위 수가 다른 지점에서도 마찬가지다.
    0으로 채우면 '순위가 그대로'라는 뜻이 되어 뜻이 달라진다. 화면이 그 빈
    칸을 'NEW'로 적는다.
    """
    data = source_files()()
    frame = data.fund_rank
    last = frame.groupby("branch_name")["stock_rank"].transform("max")
    assert frame.loc[frame["stock_rank"] == last, "rank_change"].isna().all()
    assert frame.loc[frame["stock_rank"] < last, "rank_change"].notna().all()


def test_fund_unknown_rank_change_stops(source_files):
    """읽을 수 없는 순위변동은 조용히 비우지 않고 멈춘다."""
    frame = _fund1_frame()
    frame.loc[0, "순위변동"] = "위로"
    with pytest.raises(ValueError, match="순위변동"):
        source_files(fund1=frame)()


def test_fund_missing_stock_name_stops(source_files):
    """종목명이 비어 있으면 어느 행인지 알 수 없으므로 멈춘다."""
    frame = _fund1_frame()
    frame.loc[0, "종목명"] = ""
    with pytest.raises(ValueError, match="stock_name"):
        source_files(fund1=frame)()


def test_fund_keeps_tied_ranks(source_files):
    """같은 등수가 나란히 와도 막지 않는다.

    값이 같은 종목이 여럿이면 원본이 같은 등수를 담는다. 주식·ETF
    순위표와 다른 점이다(→ dashboard/sources/fund1.py 의 check_ranks).
    """
    data = source_files()()
    frame = data.fund_rank
    tied = frame[
        frame.duplicated(subset=["branch_id", "stock_rank"], keep=False)
    ]
    assert set(tied["stock_rank"]) == {FUND_TIED_RANK}
    assert set(tied["branch_name"]) == {BRANCHES[FUND_TIED_BRANCH][1]}
    # 등수가 겹쳐도 행 수는 그대로다.
    rows = frame[frame["branch_name"] == BRANCHES[FUND_TIED_BRANCH][1]]
    assert len(rows) == STOCK_RANKS


def test_fund_duplicate_rank_and_name_stops(source_files):
    """같은 등수에 같은 종목이 두 번 있으면 멈춘다.

    등수가 겹치는 것은 정상이지만 같은 종목이 두 줄이면 금액이 두 번
    세어진다.
    """
    frame = _fund1_frame()
    frame.loc[1, "순위"] = frame.loc[0, "순위"]
    frame.loc[1, "종목명"] = frame.loc[0, "종목명"]
    with pytest.raises(ValueError, match="같은 종목"):
        source_files(fund1=frame)()


def test_fund_duplicate_name_stops(source_files):
    """한 지점의 한 달에 같은 종목이 두 번 있으면 멈춘다."""
    frame = _fund1_frame()
    frame.loc[1, "종목명"] = frame.loc[0, "종목명"]
    with pytest.raises(ValueError, match="같은 종목"):
        source_files(fund1=frame)()


def test_fund_negative_customer_count_stops(source_files):
    """거래고객수가 음수면 원본을 읽는 방법이 틀렸다는 뜻이다."""
    frame = _fund1_frame()
    frame.loc[0, "거래고객수"] = -1
    with pytest.raises(ValueError, match="거래고객수"):
        source_files(fund1=frame)()


def test_fund_month_outside_monthly_stops(source_files):
    """월별 파일에 없는 달이 있으면 두 파일의 기간이 어긋났다는 뜻이다."""
    frame = _fund1_frame()
    frame.loc[0, "기준월"] = 209912
    with pytest.raises(ValueError, match="없는 기준 월"):
        source_files(fund1=frame)()


def test_fund_missing_branch_stops(source_files):
    """지점이 통째로 빠지면 두 원본의 범위가 어긋났다는 뜻이라 멈춘다.

    순위가 끝까지 차지 않는 것과 지점이 아예 없는 것은 다르다. 앞은 그 지점이
    파는 종목이 적다는 뜻이고, 뒤는 두 파일이 다른 범위에서 뽑혔다는 뜻이다.
    """
    frame = _fund1_frame()
    frame = frame[frame["CSMT_ORZ_NM"] != BRANCHES[0][1]]
    with pytest.raises(ValueError, match="지점"):
        source_files(fund1=frame)()


def test_fund_numbers_with_commas_are_read(source_files):
    """천 단위 쉼표가 붙은 금액도 읽는다."""
    frame = _fund1_frame()
    frame["순매수금액"] = frame["순매수금액"].map(lambda v: f"{int(v):,}")
    data = source_files(fund1=frame)()
    assert data.fund_rank["net_buy_amount"].notna().all()
    assert (data.fund_rank["net_buy_amount"] < 0).any()


# --- 상품 연금통합1 ----------------------------------------------------------
def _pension_rows(data, pension: str, product: str) -> pd.DataFrame:
    frame = data.pension_rank
    return frame[
        (frame["pension_type"] == pension)
        & (frame["product_type"] == product)
    ]


def test_pension_wide_file_is_unfolded(source_files):
    """가로로 펼쳐진 상품 여섯 개가 한 줄에 하나씩인 형태가 된다.

    한 행이 상품 수만큼 줄이 되고, 종목명이 빈 칸이던 자리만 빠진다.
    """
    data = source_files()()
    frame = data.pension_rank
    full = len(BRANCHES) * STOCK_RANKS
    short = len(BRANCHES) * PENSION_SHORT_RANKS
    assert len(frame) == full * (len(PENSION_BLOCKS) - 1) + short
    assert sorted(frame["base_month"].unique()) == ["2026-01"]
    assert TOTAL_BRANCH[1] not in set(frame["branch_name"])


def test_pension_keeps_both_axes(source_files):
    """연금 구분과 상품이 각각 컬럼으로 남는다.

    둘을 한 이름으로 합치면 화면에서 다시 갈라야 한다.
    """
    data = source_files()()
    frame = data.pension_rank
    assert list(frame["pension_type"].cat.categories) == list(
        PENSION_TYPES
    )
    assert list(frame["product_type"].cat.categories) == list(
        PENSION_RANK_PRODUCT_TYPES
    )
    found = {
        (pension, product)
        for pension, product in zip(
            frame["pension_type"], frame["product_type"]
        )
    }
    assert found == set(PENSION_BLOCKS)


def test_pension_column_names_with_spaces_are_read(source_files):
    """컬럼 이름에 공백이 섞여 있어도 읽는다.

    실제 원본이 IRP ETF 다섯 컬럼만 `IRP_ETF_ 종목명`처럼 담고 있다.
    공백만 다른 이름을 못 찾는다고 멈추면 파일 전체가 열리지 않는다
    (→ pension1._tidy_columns).
    """
    source = _pension1_frame()
    spaced = [column for column in source.columns if " " in column]
    assert len(spaced) == len(pension1_source.BLOCK_COLUMNS)
    data = source_files()()
    rows = _pension_rows(data, *PENSION_SPACED_BLOCK)
    assert len(rows) == len(BRANCHES) * STOCK_RANKS
    assert rows["stock_name"].notna().all()


def test_pension_same_name_after_stripping_spaces_stops(source_files):
    """공백을 뗐더니 이름이 같아지는 컬럼이 있으면 멈춘다.

    어느 쪽 값을 써야 할지 알 수 없다.
    """
    frame = _pension1_frame()
    frame["IRP_ETF_종목명"] = frame[
        _pension_column("IRP", "ETF", "종목명")
    ]
    with pytest.raises(ValueError, match="공백만 다른"):
        source_files(pension1=frame)()


def test_pension_blank_stock_name_makes_no_row(source_files):
    """종목명이 빈 칸인 자리는 줄을 만들지 않는다.

    가로로 펼친 파일에서 빈 칸은 '그 상품은 이 순위까지 없다'는 뜻이다.
    값을 지어내 채우면 화면에 없는 종목이 생긴다.
    """
    data = source_files()()
    short = _pension_rows(data, *PENSION_SHORT_BLOCK)
    assert short["stock_rank"].max() == PENSION_SHORT_RANKS
    assert short["stock_name"].str.strip().ne("").all()
    # 다른 상품은 그 자리에 줄이 그대로 있다.
    other = _pension_rows(data, "DC", "ETF")
    assert other["stock_rank"].max() == STOCK_RANKS


def test_pension_blank_stock_name_may_be_missing(source_files):
    """빈 칸을 어떤 모양으로 담아 와도 그 줄을 만들지 않는다.

    원본은 빈 칸을 NaN으로 담기도 하고 빈 문자열로 담기도 한다. 한쪽만
    걸러 내면 다른 쪽에서 '종목명이 비어 있다'며 파일 전체가 열리지 않는다
    (→ pension1.build).
    """
    column = _pension_column(*PENSION_SHORT_BLOCK, "종목명")
    for blank in (np.nan, "", "  ", None):
        frame = _pension1_frame()
        frame[column] = frame[column].where(
            frame[column].notna(), blank
        )
        data = source_files(pension1=frame)()
        rows = _pension_rows(data, *PENSION_SHORT_BLOCK)
        assert len(rows) == len(BRANCHES) * PENSION_SHORT_RANKS
        assert rows["stock_name"].str.strip().ne("").all()


def test_pension_total_row_is_kept_apart(source_files):
    """'전체' 행은 지점 데이터와 섞이지 않고 따로 남는다."""
    data = source_files()()
    total = data.pension_rank_total
    assert set(total["branch_name"]) == {TOTAL_BRANCH[1]}
    # '전체'는 모든 상품이 끝까지 찬다.
    assert len(total) == STOCK_RANKS * len(PENSION_BLOCKS)


def test_pension_is_optional(source_files):
    """원본이 없어도 나머지 화면은 열린다."""
    data = source_files(with_product=False)()
    assert data.pension_rank.empty
    assert data.pension_rank_total.empty


def test_pension_units_are_kept_as_given(source_files):
    """거래대금·순매수금액은 원 그대로 넘어온다."""
    source = _pension1_frame()
    data = source_files(pension1=source)()
    given = source[
        (source["CSMT_ORZ_NM"] == BRANCHES[0][1]) & (source["순위"] == 1)
    ].iloc[0]
    rows = _pension_rows(data, "DC", "펀드")
    row = rows[rows["branch_name"] == BRANCHES[0][1]].iloc[0]
    assert row["trade_value"] == given["DC_펀드_거래대금"]
    assert row["trade_customer_count"] == given["DC_펀드_거래고객수"]
    assert row["net_buy_amount"] == float(given["DC_펀드_순매수금액"])


def test_pension_keeps_negative_net_buy(source_files):
    """순매도 종목의 순매수금액은 앞에 `-`가 붙은 글이라도 음수로 남는다."""
    data = source_files()()
    assert (data.pension_rank["net_buy_amount"] < 0).any()


def test_pension_rank_change_keeps_its_sign(source_files):
    """`+2`·`-1`을 부호가 있는 숫자로 읽는다."""
    data = source_files()()
    rows = _pension_rows(data, "DC", "ETF")
    changes = rows.set_index(["branch_name", "stock_rank"])["rank_change"]
    assert changes[(BRANCHES[0][1], 1)] == 2
    assert changes[(BRANCHES[0][1], 2)] == -1


def test_pension_new_entry_rank_change_stays_empty(source_files):
    """앞 달에 없던 종목은 순위변동을 비운 채로 둔다.

    그 자리는 상품마다 마지막 순위이며, 순위가 짧은 상품도 마찬가지다.
    화면이 그 빈 칸을 'NEW'로 적는다.
    """
    data = source_files()()
    frame = data.pension_rank
    keys = ["branch_name", "pension_type", "product_type"]
    last = frame.groupby(keys, observed=True)["stock_rank"].transform(
        "max"
    )
    assert frame.loc[frame["stock_rank"] == last, "rank_change"].isna().all()
    assert frame.loc[frame["stock_rank"] < last, "rank_change"].notna().all()


def test_pension_unknown_rank_change_stops(source_files):
    """읽을 수 없는 순위변동은 조용히 비우지 않고 멈춘다."""
    frame = _pension1_frame()
    frame.loc[0, "DC_ETF_순위변동"] = "위로"
    with pytest.raises(ValueError, match="순위변동"):
        source_files(pension1=frame)()


def test_pension_missing_product_column_stops(source_files):
    """상품 컬럼이 하나라도 없으면 그 이름을 알리며 멈춘다."""
    frame = _pension1_frame().drop(columns=["IRP_펀드_거래대금"])
    with pytest.raises(ValueError, match="IRP_펀드_거래대금"):
        source_files(pension1=frame)()


def test_pension_duplicate_rank_stops(source_files):
    """한 지점의 한 상품에 같은 순위가 두 번 있으면 멈춘다."""
    frame = _pension1_frame()
    frame.loc[1, "순위"] = frame.loc[0, "순위"]
    with pytest.raises(ValueError, match="같은 순위"):
        source_files(pension1=frame)()


def test_pension_duplicate_name_stops(source_files):
    """한 지점의 한 상품에 같은 종목이 두 번 있으면 멈춘다."""
    frame = _pension1_frame()
    frame.loc[1, "DC_ETF_종목명"] = frame.loc[0, "DC_ETF_종목명"]
    with pytest.raises(ValueError, match="같은 종목"):
        source_files(pension1=frame)()


def test_pension_negative_customer_count_stops(source_files):
    """거래고객수가 음수면 원본을 읽는 방법이 틀렸다는 뜻이다."""
    frame = _pension1_frame()
    frame.loc[0, "DC_펀드_거래고객수"] = -1
    with pytest.raises(ValueError, match="거래고객수"):
        source_files(pension1=frame)()


def test_pension_month_outside_monthly_stops(source_files):
    """월별 파일에 없는 달이 있으면 두 파일의 기간이 어긋났다는 뜻이다."""
    frame = _pension1_frame()
    frame.loc[0, "기준월"] = 209912
    with pytest.raises(ValueError, match="없는 기준 월"):
        source_files(pension1=frame)()


def test_pension_numbers_with_commas_are_read(source_files):
    """천 단위 쉼표가 붙은 금액도 읽는다."""
    frame = _pension1_frame()
    column = "DC_ETF_순매수금액"
    frame[column] = frame[column].map(lambda v: f"{int(v):,}")
    data = source_files(pension1=frame)()
    rows = _pension_rows(data, "DC", "ETF")
    assert rows["net_buy_amount"].notna().all()
    assert (rows["net_buy_amount"] < 0).any()


# --- 수익률 지점별 -----------------------------------------------------------
def test_branch_return_rows_reach_the_frame(source_files):
    """원본의 지점 행이 표준 프레임까지 들어온다.

    분류축이 없어 행 수가 곧 지점 수다. '전체' 지점 행은 여기서 빠져 있다.
    """
    data = source_files()()
    frame = data.branch_return
    assert len(frame) == len(BRANCHES)
    assert TOTAL_BRANCH[1] not in set(frame["branch_name"])
    assert sorted(frame["base_month"].unique()) == ["2026-01"]
    row = frame[frame["branch_name"] == BRANCHES[0][1]].iloc[0]
    assert row["return_1y"] == BRANCH_RETURNS[0][0]
    assert row["return_3y"] == BRANCH_RETURNS[0][1]


def test_branch_return_total_row_is_kept_apart(source_files):
    """'전체' 행은 지점 데이터와 섞이지 않고 따로 남는다.

    수익률은 더할 수 없으므로 지점 합계와 대조하지 않는다. 지점 값과 맞지
    않아도 그대로 들어온다.
    """
    data = source_files()()
    total = data.branch_return_total
    assert set(total["branch_name"]) == {TOTAL_BRANCH[1]}
    assert len(total) == 1
    assert total.iloc[0]["return_1y"] == TOTAL_RETURN[0]
    assert total.iloc[0]["return_3y"] == TOTAL_RETURN[1]


def test_branch_return_is_optional(source_files):
    """원본이 없어도 나머지 화면은 열린다."""
    data = source_files(with_return=False)()
    assert data.branch_return.empty
    assert data.branch_return_total.empty


def test_branch_return_percent_is_kept_as_given(source_files):
    """수익률은 원본의 % 값 그대로 넘어온다.

    0~1 비율로 보고 100을 곱하거나 반대로 100으로 나누면 화면 숫자가
    원본과 달라진다.
    """
    source = _branch_return_frame()
    data = source_files(branch_return=source)()
    given = source[source["CSMT_ORZ_NM"] == BRANCHES[1][1]].iloc[0]
    row = data.branch_return[
        data.branch_return["branch_name"] == BRANCHES[1][1]
    ].iloc[0]
    assert row["return_1y"] == given["수익률_1년"]
    assert row["return_3y"] == given["수익률_3년"]


def test_branch_return_keeps_negative_rates(source_files):
    """손실이 난 지점의 수익률은 음수로 남는다.

    인원수와 달리 음수를 막지 않는다. 0으로 올리면 손실이 사라진다.
    """
    data = source_files()()
    assert (data.branch_return["return_1y"] < 0).any()


def test_branch_return_allows_rates_over_one_hundred(source_files):
    """100%를 넘는 수익률도 그대로 들어온다.

    다른 프레임의 비중 컬럼과 달리 0~100 범위 검사를 하지 않는다.
    """
    frame = _branch_return_frame()
    frame.loc[0, "수익률_3년"] = 145.6
    data = source_files(branch_return=frame)()
    row = data.branch_return[
        data.branch_return["branch_name"] == BRANCHES[0][1]
    ].iloc[0]
    assert row["return_3y"] == 145.6


def test_branch_return_blank_rate_stays_empty(source_files):
    """수익률이 비어 있는 지점은 비운 채로 넘어온다.

    0으로 채우면 '수익이 없었다'는 뜻이 되어 뜻이 달라진다. 화면은 그 빈
    칸을 `-`로 적는다.
    """
    frame = _branch_return_frame()
    frame.loc[0, "수익률_3년"] = np.nan
    data = source_files(branch_return=frame)()
    rates = data.branch_return.set_index("branch_name")["return_3y"]
    assert pd.isna(rates[BRANCHES[0][1]])
    assert rates[BRANCHES[1][1]] == BRANCH_RETURNS[1][1]


def test_branch_return_empty_text_stays_empty(source_files):
    """빈 문자열과 `-`도 비어 있는 값으로 읽는다."""
    frame = _branch_return_frame()
    frame["수익률_1년"] = frame["수익률_1년"].astype(object)
    frame.loc[0, "수익률_1년"] = ""
    frame.loc[1, "수익률_1년"] = "-"
    data = source_files(branch_return=frame)()
    assert data.branch_return["return_1y"].isna().all()


def test_branch_return_unreadable_rate_stops(source_files):
    """읽을 수 없는 수익률은 조용히 비우지 않고 멈춘다."""
    frame = _branch_return_frame()
    frame["수익률_1년"] = frame["수익률_1년"].astype(object)
    frame.loc[0, "수익률_1년"] = "많이"
    with pytest.raises(ValueError, match="수익률_1년"):
        source_files(branch_return=frame)()


def test_branch_return_marks_are_stripped(source_files):
    """`%`·`+`·천 단위 쉼표가 붙어 와도 읽는다."""
    frame = _branch_return_frame()
    frame["수익률_1년"] = frame["수익률_1년"].astype(object)
    frame.loc[0, "수익률_1년"] = "-4.25%"
    frame.loc[1, "수익률_1년"] = "+7.5"
    frame["수익률_3년"] = frame["수익률_3년"].astype(object)
    frame.loc[1, "수익률_3년"] = "1,023.45"
    data = source_files(branch_return=frame)()
    rates = data.branch_return.set_index("branch_name")
    assert rates.loc[BRANCHES[0][1], "return_1y"] == -4.25
    assert rates.loc[BRANCHES[1][1], "return_1y"] == 7.5
    assert rates.loc[BRANCHES[1][1], "return_3y"] == 1023.45


def test_branch_return_duplicate_branch_stops(source_files):
    """한 지점이 한 달에 두 번 있으면 어느 값이 맞는지 알 수 없다."""
    frame = _branch_return_frame()
    frame = pd.concat([frame, frame.iloc[[0]]], ignore_index=True)
    with pytest.raises(ValueError, match="같은 기준월·지점"):
        source_files(branch_return=frame)()


def test_branch_return_month_outside_monthly_stops(source_files):
    """월별 파일에 없는 달이 있으면 두 파일의 기간이 어긋났다는 뜻이다."""
    frame = _branch_return_frame()
    frame.loc[0, "기준월"] = 209912
    with pytest.raises(ValueError, match="없는 기준 월"):
        source_files(branch_return=frame)()


def test_branch_return_missing_branch_stops(source_files):
    """지점이 통째로 빠지면 두 원본의 범위가 어긋났다는 뜻이라 멈춘다."""
    frame = _branch_return_frame()
    frame = frame[frame["CSMT_ORZ_NM"] != BRANCHES[0][1]]
    with pytest.raises(ValueError, match="지점"):
        source_files(branch_return=frame)()


def test_branch_return_missing_column_stops(source_files):
    """원본 컬럼 이름이 바뀌면 어느 컬럼이 없는지 알리며 멈춘다."""
    frame = _branch_return_frame().rename(
        columns={"수익률_3년": "수익률_36개월"}
    )
    with pytest.raises(ValueError, match="수익률_3년"):
        source_files(branch_return=frame)()


# --- 수익률 그룹별 비중 ------------------------------------------------------
def _group_rows(data, branch_name: str, period: str) -> pd.DataFrame:
    frame = data.return_group
    return frame[
        (frame["branch_name"] == branch_name)
        & (frame["return_period"] == period)
    ]


def test_return_group_rows_reach_the_frame(source_files):
    """원본의 구간 행이 표준 프레임까지 들어온다.

    행 수는 지점 × 기간 × 구간이다. '전체' 지점 행은 여기서 빠져 있다.
    """
    data = source_files()()
    frame = data.return_group
    assert len(frame) == len(BRANCHES) * 2 * len(RETURN_GROUPS)
    assert TOTAL_BRANCH[1] not in set(frame["branch_name"])
    assert sorted(frame["base_month"].unique()) == ["2026-01"]


def test_return_group_period_codes_get_their_names(source_files):
    """`MM12_ERN_R`·`MM36_ERN_R`에 화면 이름을 붙인다.

    코드를 그대로 화면까지 보내면 라디오와 축에 코드가 적힌다.
    """
    data = source_files()()
    periods = data.return_group["return_period"]
    assert list(periods.cat.categories) == list(RETURN_PERIODS)
    assert set(periods) == set(RETURN_PERIODS)
    counts = _group_rows(data, BRANCHES[0][1], RETURN_PERIODS[0])
    assert len(counts) == len(RETURN_GROUPS)


def test_return_group_keeps_the_declared_order(source_files):
    """구간은 낮은 쪽부터 높은 쪽 순이다.

    가나다순으로 다시 세우면 `+100%이상`이 `-20%미만` 앞으로 온다.
    """
    data = source_files()()
    groups = data.return_group["return_group"]
    assert list(groups.cat.categories) == list(RETURN_GROUPS)
    rows = _group_rows(data, BRANCHES[0][1], RETURN_PERIODS[0])
    assert list(rows["return_group"]) == list(RETURN_GROUPS)


def test_return_group_reads_names_with_different_spacing(source_files):
    """`-20%~-10%`처럼 공백이 없어도 같은 구간으로 읽는다.

    공백만 다른 이름을 모르는 값이라고 멈추면 파일 전체가 열리지 않는다.
    """
    source = _return_group_frame()
    assert SQUEEZED_GROUP not in set(source["수익률_그룹"])
    data = source_files(return_group=source)()
    assert SQUEEZED_GROUP in set(data.return_group["return_group"])


def test_return_group_strips_the_order_prefix(source_files):
    """`0)-20%미만`의 앞 번호를 떼고 읽는다.

    화면의 가로축에 늘어선 자리가 이미 차례를 말하므로 눈금에 번호까지
    적지 않는다.
    """
    source = _return_group_frame()
    written = set(source["수익률_그룹"])
    assert written.isdisjoint(RETURN_GROUPS)
    assert all(re.fullmatch(r"\d+\).+", name) for name in written)
    data = source_files(return_group=source)()
    assert set(data.return_group["return_group"]) == set(RETURN_GROUPS)


def test_return_group_prefix_may_start_at_one(source_files):
    """1부터 세어도 읽는다. 번호끼리의 앞뒤만 견준다."""
    frame = _return_group_frame()
    frame["수익률_그룹"] = [
        f"{RETURN_GROUPS.index(name) + 1}){name}"
        for name in frame["수익률_그룹"].map(
            lambda value: RETURN_GROUPS[int(value.split(")")[0])]
        )
    ]
    data = source_files(return_group=frame)()
    assert set(data.return_group["return_group"]) == set(RETURN_GROUPS)


def test_return_group_prefix_out_of_order_stops(source_files):
    """원본이 적어 둔 차례가 화면 차례와 다르면 멈춘다.

    구간을 다시 늘어놓았는데 화면은 옛 차례로 그리면, 막대 순서가 틀린 채로
    맞는 것처럼 보인다.
    """
    frame = _return_group_frame()
    last = len(RETURN_GROUPS) - 1
    frame["수익률_그룹"] = frame["수익률_그룹"].map(
        lambda value: f"{last - int(value.split(')')[0])})"
        f"{value.split(')', 1)[1]}"
    )
    with pytest.raises(ValueError, match="차례가 화면 차례와 다릅니다"):
        source_files(return_group=frame)()


def test_return_group_same_number_on_two_groups_stops(source_files):
    """한 번호가 두 구간에 붙어 있으면 차례를 읽을 수 없다."""
    frame = _return_group_frame()
    frame["수익률_그룹"] = frame["수익률_그룹"].map(
        lambda value: "0)" + value.split(")", 1)[1]
    )
    with pytest.raises(ValueError, match="같은 번호"):
        source_files(return_group=frame)()


def test_return_group_reads_names_without_a_prefix(source_files):
    """번호가 없어도 읽는다. 그때는 차례를 확인하지 않는다."""
    frame = _return_group_frame()
    frame["수익률_그룹"] = frame["수익률_그룹"].map(
        lambda value: value.split(")", 1)[1]
    )
    data = source_files(return_group=frame)()
    assert set(data.return_group["return_group"]) == set(RETURN_GROUPS)


def test_return_group_share_is_kept_as_given(source_files):
    """원본이 담은 비중을 그대로 넘긴다.

    인원수에서 다시 만들면 반올림 때문에 화면 숫자가 원본과 달라진다.
    """
    source = _return_group_frame()
    data = source_files(return_group=source)()
    given = source[
        (source["CSMT_ORZ_NM"] == BRANCHES[0][1])
        & (source["수익률_구분"] == "MM12_ERN_R")
    ].iloc[0]
    row = _group_rows(data, BRANCHES[0][1], RETURN_PERIODS[0]).iloc[0]
    assert row["customer_share"] == given["고객비중"]
    assert row["customer_count"] == given["고객수"]
    assert row["branch_customer_count"] == given["고객수_지점합계"]


def test_return_group_blank_share_stays_empty(source_files):
    """비중이 비어 있어도 인원수는 그대로 들어온다."""
    frame = _return_group_frame()
    frame["고객비중"] = frame["고객비중"].astype(object)
    frame.loc[0, "고객비중"] = np.nan
    data = source_files(return_group=frame)()
    shares = data.return_group["customer_share"]
    assert shares.isna().sum() == 1
    assert data.return_group["customer_count"].notna().all()


def test_return_group_counts_must_add_up(source_files):
    """구간 인원수의 합이 지점 합계와 다르면 멈춘다.

    한 파일 안에서 앞뒤가 맞는지 보는 대조라 허용치를 두지 않는다.
    맞지 않으면 막대 높이와 hover의 고객 수가 서로 다른 말을 하게 된다.
    """
    frame = _return_group_frame()
    frame.loc[0, "고객수"] = int(frame.loc[0, "고객수"]) + 5
    with pytest.raises(ValueError, match="지점 합계"):
        source_files(return_group=frame)()


def test_return_group_branch_total_must_be_the_same(source_files):
    """한 지점·기간의 지점 합계가 구간마다 다르면 멈춘다."""
    frame = _return_group_frame()
    frame.loc[0, "고객수_지점합계"] = 999_999
    with pytest.raises(ValueError, match="고객수_지점합계"):
        source_files(return_group=frame)()


def test_return_group_share_must_match_the_counts(source_files):
    """비중이 인원수에서 계산한 값과 크게 어긋나면 멈춘다.

    원본이 0~1 비율을 담아 왔을 때 그대로 화면에 올리는 것을 막는다.
    """
    frame = _return_group_frame()
    frame["고객비중"] = frame["고객비중"] / 100.0
    with pytest.raises(ValueError, match="고객비중"):
        source_files(return_group=frame)()


def test_return_group_rounding_in_the_share_is_allowed(source_files):
    """소수점 아래 반올림 차이는 넘어간다."""
    frame = _return_group_frame()
    frame["고객비중"] = frame["고객비중"].map(
        lambda value: round(float(value) + 0.004, 4)
    )
    data = source_files(return_group=frame)()
    assert data.return_group["customer_share"].notna().all()


def test_return_group_unknown_group_stops(source_files):
    """모르는 구간 이름은 조용히 결측으로 바꾸지 않고 멈춘다."""
    frame = _return_group_frame()
    frame.loc[0, "수익률_그룹"] = "+300% ~ +400%"
    with pytest.raises(ValueError, match="\\+300%"):
        source_files(return_group=frame)()


def test_return_group_unknown_period_stops(source_files):
    """모르는 기간 코드도 멈춘다. 코드가 바뀌면 PERIOD_CODES를 고친다."""
    frame = _return_group_frame()
    frame["수익률_구분"] = frame["수익률_구분"].replace(
        {"MM12_ERN_R": "MM60_ERN_R"}
    )
    with pytest.raises(ValueError, match="MM60_ERN_R"):
        source_files(return_group=frame)()


def test_return_group_duplicate_row_stops(source_files):
    """같은 지점·기간·구간이 두 번 있으면 막대 높이가 두 배가 된다."""
    frame = _return_group_frame()
    frame = pd.concat([frame, frame.iloc[[0]]], ignore_index=True)
    with pytest.raises(ValueError, match="두 번 이상"):
        source_files(return_group=frame)()


def test_return_group_negative_count_stops(source_files):
    """인원수가 음수면 원본을 읽는 방법이 틀렸다는 뜻이다."""
    frame = _return_group_frame()
    frame.loc[0, "고객수"] = -1
    with pytest.raises(ValueError, match="고객수"):
        source_files(return_group=frame)()


def test_return_group_month_outside_monthly_stops(source_files):
    """월별 파일에 없는 달이 있으면 두 파일의 기간이 어긋났다는 뜻이다.

    한 행만 옮기면 그 행이 다른 묶음으로 빠져 구간 합계가 먼저 어긋난다.
    기간이 통째로 다른 경우를 보려고 모든 행의 달을 옮긴다.
    """
    frame = _return_group_frame()
    frame["기준월"] = 209912
    with pytest.raises(ValueError, match="없는 기준 월"):
        source_files(return_group=frame)()


def test_return_group_is_optional(source_files):
    """원본이 없어도 나머지 화면은 열린다."""
    data = source_files(with_return=False)()
    assert data.return_group.empty
    assert data.return_group_total.empty


# --- 수익률 자산규모별 ------------------------------------------------------
def _asset_return_frame() -> pd.DataFrame:
    """자산규모별 수익률 원본 표본.

    지점·'전체'마다 자산 규모 구간 여섯 행이다. 구간 이름은 실제 원본과
    같이 `1)1백만 ~ 1천만` 꼴로 담고, 1부터 센다.
    """
    rows = []
    month = MONTHS[-1]
    for branch_index, (code, name) in enumerate([*BRANCHES, TOTAL_BRANCH]):
        for order, group_name in enumerate(ASSET_GROUPS):
            rows.append(
                {
                    "기준월": int(month),
                    "CSMT_ORZ_CD": code,
                    "CSMT_ORZ_NM": name,
                    "자산그룹": f"{order + 1}){group_name}",
                    # 첫 구간은 손실이라 음수다.
                    "수익률_1년": round(-6.5 + order * 3.0 + branch_index, 2),
                    "수익률_3년": round(4.0 + order * 4.5 + branch_index, 2),
                }
            )
    return pd.DataFrame(rows)


def test_asset_return_rows_reach_the_frame(source_files):
    """원본의 구간 행이 표준 프레임까지 들어온다.

    행 수는 지점 × 자산 규모 구간이다. '전체' 지점 행은 여기서 빠져 있다.
    """
    data = source_files()()
    frame = data.asset_return
    assert len(frame) == len(BRANCHES) * len(ASSET_GROUPS)
    assert TOTAL_BRANCH[1] not in set(frame["branch_name"])
    assert sorted(frame["base_month"].unique()) == ["2026-01"]

    total = data.asset_return_total
    assert set(total["branch_name"]) == {TOTAL_BRANCH[1]}
    assert len(total) == len(ASSET_GROUPS)


def test_asset_return_strips_the_order_prefix(source_files):
    """`1)1백만 ~ 1천만`의 앞 번호를 떼고 읽는다.

    수익률 그룹별 비중과 같은 규칙이라 데이터 계층의 함수를 함께 쓴다
    (→ data.to_ordered_label_column).
    """
    source = _asset_return_frame()
    assert set(source["자산그룹"]).isdisjoint(ASSET_GROUPS)
    data = source_files(asset_return=source)()
    groups = data.asset_return["asset_group"]
    assert set(groups) == set(ASSET_GROUPS)
    # 작은 구간부터 큰 구간 순이다.
    assert list(groups.cat.categories) == list(ASSET_GROUPS)
    rows = data.asset_return[
        data.asset_return["branch_name"] == BRANCHES[0][1]
    ]
    assert list(rows["asset_group"]) == list(ASSET_GROUPS)


def test_asset_return_prefix_out_of_order_stops(source_files):
    """원본이 적어 둔 차례가 화면 차례와 다르면 멈춘다."""
    frame = _asset_return_frame()
    last = len(ASSET_GROUPS)
    frame["자산그룹"] = frame["자산그룹"].map(
        lambda value: f"{last + 1 - int(value.split(')')[0])})"
        f"{value.split(')', 1)[1]}"
    )
    with pytest.raises(ValueError, match="차례가 화면 차례와 다릅니다"):
        source_files(asset_return=frame)()


def test_asset_return_percent_is_kept_as_given(source_files):
    """수익률은 원본의 % 값 그대로 넘어온다."""
    source = _asset_return_frame()
    data = source_files(asset_return=source)()
    given = source[
        (source["CSMT_ORZ_NM"] == BRANCHES[0][1])
        & (source["자산그룹"].str.endswith(ASSET_GROUPS[0]))
    ].iloc[0]
    row = data.asset_return[
        (data.asset_return["branch_name"] == BRANCHES[0][1])
        & (data.asset_return["asset_group"] == ASSET_GROUPS[0])
    ].iloc[0]
    assert row["return_1y"] == given["수익률_1년"]
    assert row["return_3y"] == given["수익률_3년"]


def test_asset_return_keeps_negative_rates(source_files):
    """손실이 난 구간의 수익률은 음수로 남는다."""
    data = source_files()()
    assert (data.asset_return["return_1y"] < 0).any()


def test_asset_return_blank_rate_stays_empty(source_files):
    """고객이 없는 구간은 수익률이 비어 있을 수 있다. 0으로 채우지 않는다."""
    frame = _asset_return_frame()
    frame["수익률_3년"] = frame["수익률_3년"].astype(object)
    frame.loc[0, "수익률_3년"] = np.nan
    data = source_files(asset_return=frame)()
    assert data.asset_return["return_3y"].isna().sum() == 1
    assert data.asset_return["return_1y"].notna().all()


def test_asset_return_unknown_group_stops(source_files):
    """모르는 자산그룹은 조용히 결측으로 바꾸지 않고 멈춘다."""
    frame = _asset_return_frame()
    frame.loc[0, "자산그룹"] = "7)10억이상"
    with pytest.raises(ValueError, match="10억이상"):
        source_files(asset_return=frame)()


def test_asset_return_duplicate_group_stops(source_files):
    """한 지점에 같은 구간이 두 번 있으면 어느 값이 맞는지 알 수 없다."""
    frame = _asset_return_frame()
    frame = pd.concat([frame, frame.iloc[[0]]], ignore_index=True)
    with pytest.raises(ValueError, match="두 번 이상"):
        source_files(asset_return=frame)()


def test_asset_return_missing_branch_stops(source_files):
    """지점이 통째로 빠지면 두 원본의 범위가 어긋났다는 뜻이라 멈춘다."""
    frame = _asset_return_frame()
    frame = frame[frame["CSMT_ORZ_NM"] != BRANCHES[0][1]]
    with pytest.raises(ValueError, match="지점"):
        source_files(asset_return=frame)()


def test_asset_return_is_optional(source_files):
    """원본이 없어도 나머지 화면은 열린다."""
    data = source_files(with_return=False)()
    assert data.asset_return.empty
    assert data.asset_return_total.empty


# --- 수익률 구간별 ----------------------------------------------------------
# `수익률_seg_...` 원본 여섯 개는 가르는 기준과 구간 목록만 다르고 모양이
# 같다. 조립도 한 곳에서 하므로(→ dashboard/sources/segment_return.py) 검사도
# 여섯 원본을 함께 돈다.
# (원본 키, 원본 컬럼명, 표준 컬럼명, 구간 목록, 번호를 붙이는지) 순이다.
#
# 연령대 원본만 구간 앞에 번호가 없다. 번호가 없으면 데이터 계층이 차례를
# 확인하지 않으므로 차례 검사에서는 빠진다(→ NUMBERED_SEGMENT_SOURCES).
SEGMENT_RETURN_SOURCES = [
    (
        "stock_share_return",
        "국내주식잔고비중",
        "stock_share_group",
        BALANCE_SHARE_GROUPS,
        True,
    ),
    (
        "overseas_share_return",
        "해외주식잔고비중",
        "overseas_share_group",
        BALANCE_SHARE_GROUPS,
        True,
    ),
    (
        "etf_share_return",
        "ETF잔고비중",
        "etf_share_group",
        BALANCE_SHARE_GROUPS,
        True,
    ),
    (
        "pension_share_return",
        "개인연금잔고비중",
        "pension_share_group",
        BALANCE_SHARE_GROUPS,
        True,
    ),
    (
        "stock_turnover_return",
        "국내주식회전율그룹",
        "stock_turnover_group",
        STOCK_TURNOVER_GROUPS,
        True,
    ),
    (
        "age_return",
        "연령대",
        "return_age_group",
        RETURN_AGE_GROUPS,
        False,
    ),
]
NUMBERED_SEGMENT_SOURCES = [
    source for source in SEGMENT_RETURN_SOURCES if source[4]
]


def _segment_return_frame(
    source_column: str, groups: tuple[str, ...], numbered: bool
) -> pd.DataFrame:
    """구간별 수익률 원본 표본.

    지점·'전체'마다 구간 수만큼 행이 있다. 번호를 붙이는 원본은 실제 원본과
    같이 `1)5%미만` 꼴로 담고 1부터 센다.
    """
    rows = []
    month = MONTHS[-1]
    for branch_index, (code, name) in enumerate([*BRANCHES, TOTAL_BRANCH]):
        for order, group_name in enumerate(groups):
            label = f"{order + 1}){group_name}" if numbered else group_name
            rows.append(
                {
                    "기준월": int(month),
                    "CSMT_ORZ_CD": code,
                    "CSMT_ORZ_NM": name,
                    source_column: label,
                    # 뒤쪽 구간은 손실이라 음수다.
                    "수익률_1년": round(
                        7.5 - order * 3.5 + branch_index, 2
                    ),
                    "수익률_3년": round(
                        22.0 - order * 4.5 + branch_index, 2
                    ),
                }
            )
    return pd.DataFrame(rows)


def _stock_share_return_frame() -> pd.DataFrame:
    return _segment_return_frame(
        "국내주식잔고비중", BALANCE_SHARE_GROUPS, True
    )


def _overseas_share_return_frame() -> pd.DataFrame:
    return _segment_return_frame(
        "해외주식잔고비중", BALANCE_SHARE_GROUPS, True
    )


def _etf_share_return_frame() -> pd.DataFrame:
    return _segment_return_frame(
        "ETF잔고비중", BALANCE_SHARE_GROUPS, True
    )


def _pension_share_return_frame() -> pd.DataFrame:
    return _segment_return_frame(
        "개인연금잔고비중", BALANCE_SHARE_GROUPS, True
    )


def _stock_turnover_return_frame() -> pd.DataFrame:
    return _segment_return_frame(
        "국내주식회전율그룹", STOCK_TURNOVER_GROUPS, True
    )


def _age_return_frame() -> pd.DataFrame:
    return _segment_return_frame("연령대", RETURN_AGE_GROUPS, False)


PARAMS = "key, source_column, group_column, groups, numbered"


@pytest.mark.parametrize(PARAMS, SEGMENT_RETURN_SOURCES)
def test_segment_return_rows_reach_the_frame(
    source_files, key, source_column, group_column, groups, numbered
):
    """원본의 구간 행이 표준 프레임까지 들어온다.

    행 수는 지점 × 구간이다. '전체' 지점 행은 여기서 빠져 있다.
    """
    data = source_files()()
    frame = getattr(data, key)
    assert len(frame) == len(BRANCHES) * len(groups)
    assert TOTAL_BRANCH[1] not in set(frame["branch_name"])
    assert sorted(frame["base_month"].unique()) == ["2026-01"]

    total = data.total_of(key)
    assert set(total["branch_name"]) == {TOTAL_BRANCH[1]}
    assert len(total) == len(groups)


@pytest.mark.parametrize(PARAMS, SEGMENT_RETURN_SOURCES)
def test_segment_return_keeps_the_group_order(
    source_files, key, source_column, group_column, groups, numbered
):
    """구간이 데이터 계층에 적힌 차례 그대로 늘어선다.

    번호를 붙여 오는 원본은 `1)5%미만`의 앞 번호를 떼고 읽는다
    (→ data.to_ordered_label_column).
    """
    source = _segment_return_frame(source_column, groups, numbered)
    if numbered:
        assert set(source[source_column]).isdisjoint(groups)
    data = source_files(**{key: source})()
    frame = getattr(data, key)
    assert set(frame[group_column]) == set(groups)
    assert list(frame[group_column].cat.categories) == list(groups)
    rows = frame[frame["branch_name"] == BRANCHES[0][1]]
    assert list(rows[group_column]) == list(groups)


@pytest.mark.parametrize(PARAMS, NUMBERED_SEGMENT_SOURCES)
def test_segment_return_prefix_out_of_order_stops(
    source_files, key, source_column, group_column, groups, numbered
):
    """원본이 적어 둔 차례가 화면 차례와 다르면 멈춘다."""
    frame = _segment_return_frame(source_column, groups, numbered)
    last = len(groups)
    frame[source_column] = frame[source_column].map(
        lambda value: f"{last + 1 - int(value.split(')')[0])})"
        f"{value.split(')', 1)[1]}"
    )
    with pytest.raises(ValueError, match="차례가 화면 차례와 다릅니다"):
        source_files(**{key: frame})()


@pytest.mark.parametrize(PARAMS, SEGMENT_RETURN_SOURCES)
def test_segment_return_percent_is_kept_as_given(
    source_files, key, source_column, group_column, groups, numbered
):
    """수익률은 원본의 % 값 그대로 넘어온다."""
    source = _segment_return_frame(source_column, groups, numbered)
    data = source_files(**{key: source})()
    given = source[
        (source["CSMT_ORZ_NM"] == BRANCHES[0][1])
        & (source[source_column].str.endswith(groups[0]))
    ].iloc[0]
    frame = getattr(data, key)
    row = frame[
        (frame["branch_name"] == BRANCHES[0][1])
        & (frame[group_column] == groups[0])
    ].iloc[0]
    assert row["return_1y"] == given["수익률_1년"]
    assert row["return_3y"] == given["수익률_3년"]


@pytest.mark.parametrize(PARAMS, SEGMENT_RETURN_SOURCES)
def test_segment_return_keeps_negative_rates(
    source_files, key, source_column, group_column, groups, numbered
):
    """손실이 난 구간의 수익률은 음수로 남는다."""
    data = source_files()()
    assert (getattr(data, key)["return_1y"] < 0).any()


@pytest.mark.parametrize(PARAMS, SEGMENT_RETURN_SOURCES)
def test_segment_return_blank_rate_stays_empty(
    source_files, key, source_column, group_column, groups, numbered
):
    """고객이 없는 구간은 수익률이 비어 있을 수 있다. 0으로 채우지 않는다."""
    frame = _segment_return_frame(source_column, groups, numbered)
    frame["수익률_3년"] = frame["수익률_3년"].astype(object)
    frame.loc[0, "수익률_3년"] = np.nan
    data = source_files(**{key: frame})()
    assert getattr(data, key)["return_3y"].isna().sum() == 1
    assert getattr(data, key)["return_1y"].notna().all()


@pytest.mark.parametrize(PARAMS, SEGMENT_RETURN_SOURCES)
def test_segment_return_unknown_group_stops(
    source_files, key, source_column, group_column, groups, numbered
):
    """모르는 구간은 조용히 결측으로 바꾸지 않고 멈춘다."""
    frame = _segment_return_frame(source_column, groups, numbered)
    frame.loc[0, source_column] = "없는구간"
    with pytest.raises(ValueError, match="없는구간"):
        source_files(**{key: frame})()


@pytest.mark.parametrize(PARAMS, SEGMENT_RETURN_SOURCES)
def test_segment_return_duplicate_group_stops(
    source_files, key, source_column, group_column, groups, numbered
):
    """한 지점에 같은 구간이 두 번 있으면 어느 값이 맞는지 알 수 없다."""
    frame = _segment_return_frame(source_column, groups, numbered)
    frame = pd.concat([frame, frame.iloc[[0]]], ignore_index=True)
    with pytest.raises(ValueError, match="두 번 이상"):
        source_files(**{key: frame})()


@pytest.mark.parametrize(PARAMS, SEGMENT_RETURN_SOURCES)
def test_segment_return_missing_branch_stops(
    source_files, key, source_column, group_column, groups, numbered
):
    """지점이 통째로 빠지면 두 원본의 범위가 어긋났다는 뜻이라 멈춘다."""
    frame = _segment_return_frame(source_column, groups, numbered)
    frame = frame[frame["CSMT_ORZ_NM"] != BRANCHES[0][1]]
    with pytest.raises(ValueError, match="지점"):
        source_files(**{key: frame})()


@pytest.mark.parametrize(PARAMS, SEGMENT_RETURN_SOURCES)
def test_segment_return_is_optional(
    source_files, key, source_column, group_column, groups, numbered
):
    """원본이 없어도 나머지 화면은 열린다."""
    data = source_files(with_return=False)()
    assert getattr(data, key).empty
    assert data.total_of(key).empty


def test_segment_return_source_column_is_named_in_the_error(source_files):
    """어느 원본의 어느 컬럼이 문제인지 오류 문구에 원본 이름으로 나온다.

    여섯 원본이 조립을 함께 쓰므로, 문구가 원본마다 달라지는지 한 번 본다
    (→ dashboard/sources/segment_return.py 의 _source_name).
    """
    frame = _etf_share_return_frame()
    last = len(BALANCE_SHARE_GROUPS)
    frame["ETF잔고비중"] = frame["ETF잔고비중"].map(
        lambda value: f"{last + 1 - int(value.split(')')[0])})"
        f"{value.split(')', 1)[1]}"
    )
    with pytest.raises(
        ValueError, match="ETF비중별 수익률 파일이 적어 둔 ETF잔고비중"
    ):
        source_files(etf_share_return=frame)()


# --- 디지털 채널 -------------------------------------------------------------
# 채널마다 대략 이만큼의 고객이 쓴다고 두고, 지점·달마다 조금씩 흔든다.
# 실제 비율은 원본이 정하며 앱 코드에는 적지 않는다(→ AGENTS.md §10.1).
DIGITAL_RATIOS = {"HTS": 0.18, "MTS": 0.52, "WEB": 0.26}
DIGITAL_TRADE_RATIO = 0.41
# 채널별 고객 특성 표본. (평균 연령, 평균 자산(원), 상품 비중 여섯).
DIGITAL_PROFILES = {
    "HTS": (57.4, 182_000_000, (46.0, 12.0, 7.0, 9.0, 5.0, 4.0)),
    "MTS": (38.2, 41_000_000, (28.0, 27.0, 16.0, 3.0, 6.0, 5.0)),
    "WEB": (46.5, 96_000_000, (35.0, 18.0, 11.0, 7.0, 8.0, 9.0)),
}
DIGITAL_MIX_NAMES = (
    "국내주식비중",
    "해외주식비중",
    "국내ETF비중",
    "채권비중",
    "펀드비중",
    "개인연금비중",
)


def _digital_ratio(channel: str, branch_index: int, month_index: int) -> float:
    """그 지점·달에 그 채널을 쓴 고객의 몫. 값이 고정되어 재현할 수 있다."""
    return (
        DIGITAL_RATIOS[channel]
        + branch_index * 0.03
        - month_index * 0.01
    )


def _digital_share(count: int, customers: int) -> float:
    """원본이 담는 이용 비중(%). 실제 원본과 같이 소수 둘째 자리까지다."""
    return round(count / customers * 100.0, 2)


def _digital1_row(
    month: str,
    code: str,
    name: str,
    customers: int,
    counts: dict[str, int],
    trade: int,
) -> dict:
    """디지털채널1 원본의 한 행. 지점 행과 '전체' 행이 같은 모양이다."""
    row = {
        "기준월": int(month),
        "CSMT_ORZ_CD": code,
        "CSMT_ORZ_NM": name,
        "고객수": customers,
        "거래고객수": trade,
        "거래고객비중": _digital_share(trade, customers),
    }
    for channel, count in counts.items():
        row[f"{channel}_이용고객수"] = count
        row[f"{channel}_이용비중"] = _digital_share(count, customers)
    return row


def _digital1_frame() -> pd.DataFrame:
    """디지털채널1 원본 표본. 채널 셋이 한 행에 가로로 붙어 있다.

    이용 비중은 고객 수에서 계산해 담는다. 원본 안에서 인원수와 비중이
    앞뒤로 맞는지 보는 대조를 그대로 지나가야 한다
    (→ dashboard/sources/digital1.py 의 check_shares).

    고객수는 월별 파일과 같은 값을 쓴다. 두 파일이 겹쳐 갖는 지표라
    데이터 계층이 대조한다(→ check_digital1_against_monthly).
    """
    rows = []
    for month_index, month in enumerate(MONTHS):
        totals = {channel: 0 for channel in DIGITAL_RATIOS}
        trade_total = 0
        customer_total = 0
        for branch_index, (code, name) in enumerate(BRANCHES):
            customers = _counts(branch_index, month_index)
            customer_total += customers
            counts = {
                channel: int(
                    round(
                        customers
                        * _digital_ratio(channel, branch_index, month_index)
                    )
                )
                for channel in DIGITAL_RATIOS
            }
            trade = int(round(customers * DIGITAL_TRADE_RATIO))
            trade_total += trade
            for channel, count in counts.items():
                totals[channel] += count
            rows.append(
                _digital1_row(month, code, name, customers, counts, trade)
            )
        rows.append(
            _digital1_row(
                month,
                TOTAL_BRANCH[0],
                TOTAL_BRANCH[1],
                customer_total,
                totals,
                trade_total,
            )
        )
    return pd.DataFrame(rows)


def _digital2_frame() -> pd.DataFrame:
    """디지털채널2 원본 표본. 채널 셋이 한 행에 가로로 펼쳐져 있다.

    HTS는 나이가 많고 자산이 크며, MTS는 젊고 자산이 작다. 지점마다 조금씩
    다르게 두어 펴는 과정에서 값이 뒤섞이면 드러나게 한다.
    """
    rows = []
    for month_index, month in enumerate(MONTHS):
        for branch_index, (code, name) in enumerate(
            [*BRANCHES, TOTAL_BRANCH]
        ):
            row = {
                "기준월": int(month),
                "CSMT_ORZ_CD": code,
                "CSMT_ORZ_NM": name,
            }
            for channel, (age, assets, mix) in DIGITAL_PROFILES.items():
                row[f"{channel}_연령"] = round(
                    age + branch_index * 0.7 - month_index * 0.1, 1
                )
                row[f"{channel}_자산평균"] = int(
                    assets * (1 + branch_index * 0.08 + month_index * 0.01)
                )
                for mix_index, mix_name in enumerate(DIGITAL_MIX_NAMES):
                    row[f"{channel}_{mix_name}"] = round(
                        mix[mix_index] + branch_index * 0.5, 2
                    )
            rows.append(row)
    return pd.DataFrame(rows)


def test_digital_channel_rows_reach_the_frame(source_files):
    """가로로 붙어 있던 채널 셋이 한 줄에 하나씩인 형태로 들어온다.

    행 수는 지점 × 월 × 채널이다. '전체' 행은 따로 떨어져 나간다.
    """
    data = source_files()()
    frame = data.digital_channel
    assert len(frame) == len(BRANCHES) * len(MONTHS) * len(DIGITAL_RATIOS)
    assert set(frame["channel"]) == set(DIGITAL_RATIOS)
    assert TOTAL_BRANCH[1] not in set(frame["branch_name"])

    total = data.digital_channel_total
    assert set(total["branch_name"]) == {TOTAL_BRANCH[1]}
    assert len(total) == len(MONTHS) * len(DIGITAL_RATIOS)


def test_digital_channel_keeps_the_source_share(source_files):
    """비중은 원본 값을 그대로 쓴다. 인원수에서 다시 만들지 않는다."""
    data = source_files()()
    frame = data.digital_channel
    first = frame[
        (frame["branch_id"] == BRANCHES[0][0])
        & (frame["base_month"] == "2025-11")
        & (frame["channel"] == "MTS")
    ].iloc[0]
    customers = _counts(0, 0)
    expected = int(round(customers * _digital_ratio("MTS", 0, 0)))
    assert first["user_count"] == expected
    assert first["user_share"] == _digital_share(expected, customers)


def test_digital_columns_reach_the_monthly_frame(source_files):
    """채널로 나뉘지 않는 값은 월별 프레임에 따로 붙는다.

    디지털채널1의 고객 수는 `digital_customer_count`로 들어가고, 월별 파일이
    주는 `customer_count`는 그대로 남는다. 거래고객 수도 거래1의
    `transaction_customer_count`와 섞이지 않는다(→ AGENTS.md §17).
    """
    data = source_files()()
    monthly = data.monthly
    row = monthly[
        (monthly["branch_id"] == BRANCHES[0][0])
        & (monthly["base_month"] == "2025-11")
    ].iloc[0]
    customers = _counts(0, 0)
    expected = int(round(customers * DIGITAL_TRADE_RATIO))
    assert row["digital_customer_count"] == customers
    assert row["customer_count"] == customers
    assert row["digital_trade_customer_count"] == expected
    assert row["digital_trade_customer_share"] == _digital_share(
        expected, customers
    )


def test_digital_customer_count_may_differ_from_monthly(source_files):
    """두 파일의 고객 수가 달라도 멈추지 않고 각자 값을 그대로 쓴다.

    어느 쪽이 맞는지 가릴 근거가 없어 견주지 않는다. 한쪽이 다른 쪽을
    덮지도 않는다(→ data.MONTHLY_DIGITAL_COLUMNS).
    """
    frame = _digital1_frame()
    frame["고객수"] = frame["고객수"] * 2
    data = source_files(digital1=frame)()
    monthly = data.monthly
    row = monthly[
        (monthly["branch_id"] == BRANCHES[0][0])
        & (monthly["base_month"] == "2025-11")
    ].iloc[0]
    assert row["customer_count"] == _counts(0, 0)
    assert row["digital_customer_count"] == _counts(0, 0) * 2


def test_digital_profile_rows_reach_the_frame(source_files):
    """채널별 고객 특성도 한 줄에 한 채널인 형태로 들어온다."""
    data = source_files()()
    frame = data.digital_profile
    assert len(frame) == len(BRANCHES) * len(MONTHS) * len(DIGITAL_PROFILES)
    row = frame[
        (frame["branch_id"] == BRANCHES[0][0])
        & (frame["base_month"] == "2025-11")
        & (frame["channel"] == "HTS")
    ].iloc[0]
    age, assets, mix = DIGITAL_PROFILES["HTS"]
    assert row["average_age"] == round(age, 1)
    assert row["average_assets_won"] == assets
    assert row["domestic_stock_share"] == mix[0]


def test_digital1_keeps_the_source_share_as_is(source_files):
    """비중은 원본 값을 그대로 옮긴다. 인원수와 견주지 않는다.

    원본이 비중을 이미 계산해 담고 있어 그대로 쓴다. 인원수에서 다시
    만들거나 맞는지 확인하지 않는다(→ AGENTS.md §9).
    """
    frame = _digital1_frame()
    # 인원수와 전혀 맞지 않는 비중을 넣어도 그대로 화면까지 간다.
    frame["MTS_이용비중"] = 1.25
    data = source_files(digital1=frame)()
    channel = data.digital_channel
    mts = channel[channel["channel"] == "MTS"]
    assert (mts["user_share"] == 1.25).all()


def test_digital1_duplicate_month_branch_stops(source_files):
    """같은 기준월·지점이 두 번 있으면 멈춘다."""
    frame = _digital1_frame()
    frame = pd.concat([frame, frame.iloc[[0]]], ignore_index=True)
    with pytest.raises(ValueError, match="두 번 이상"):
        source_files(digital1=frame)()


def test_digital2_share_out_of_range_stops(source_files):
    """비중이 0~100을 벗어나면 멈춘다."""
    frame = _digital2_frame()
    frame.loc[0, "HTS_국내주식비중"] = 140.0
    with pytest.raises(ValueError, match="domestic_stock_share"):
        source_files(digital2=frame)()


def test_digital2_age_out_of_range_stops(source_files):
    """평균 연령이 사람의 나이 범위를 벗어나면 멈춘다."""
    frame = _digital2_frame()
    frame.loc[0, "MTS_연령"] = 380.0
    with pytest.raises(ValueError, match="average_age"):
        source_files(digital2=frame)()


def test_digital_sources_are_optional(source_files):
    """원본이 없어도 나머지 화면은 열린다.

    두 프레임이 비고, 월별 프레임의 거래고객 값도 비운 채로 남는다.
    0으로 채우지 않는다(→ AGENTS.md §9).
    """
    data = source_files(with_digital=False)()
    assert data.digital_channel.empty
    assert data.digital_profile.empty
    assert data.digital_channel_total.empty
    assert data.monthly["digital_trade_customer_count"].isna().all()


# 이용일수 구간별 채널 이용 비중 표본. 채널마다 여섯 칸의 몫이 다르고,
# 합은 100%다. 실제 값은 원본이 정하며 앱 코드에는 적지 않는다.
DIGITAL_DAY_MIX = {
    "HTS": (58.0, 18.0, 9.0, 6.0, 4.5, 4.5),
    "MTS": (21.0, 24.0, 17.0, 14.0, 11.0, 13.0),
    "WEB": (44.0, 26.0, 13.0, 8.0, 5.0, 4.0),
}


def _digital3_frame() -> pd.DataFrame:
    """디지털채널3 원본 표본.

    지점·'전체'마다 이용일수 구간 여섯 행이고, 그 한 행에 채널 셋의 비중이
    가로로 붙어 있다. 구간 이름은 실제 원본과 같이 `1)0일(미사용)` 꼴로
    담고 1부터 센다. 원본이 마지막 한 달만 담고 있어 표본도 그렇게 만든다.
    """
    rows = []
    month = MONTHS[-1]
    for branch_index, (code, name) in enumerate([*BRANCHES, TOTAL_BRANCH]):
        for order, group in enumerate(DIGITAL_USAGE_DAY_GROUPS):
            row = {
                "기준월": int(month),
                "CSMT_ORZ_CD": code,
                "CSMT_ORZ_NM": name,
                "이용일수": f"{order + 1}){group}",
            }
            for channel, mix in DIGITAL_DAY_MIX.items():
                row[f"{channel}_이용비중"] = round(
                    mix[order] + branch_index * 0.1, 2
                )
            rows.append(row)
    return pd.DataFrame(rows)


def test_digital_usage_days_rows_reach_the_frame(source_files):
    """가로로 붙어 있던 채널 셋이 한 줄에 하나씩인 형태로 들어온다.

    행 수는 지점 × 구간 × 채널이다. 원본이 마지막 한 달만 담고 있어 기간이
    한 달뿐이며, '전체' 지점 행은 따로 떨어져 나간다.
    """
    data = source_files()()
    frame = data.digital_usage_days
    groups = len(DIGITAL_USAGE_DAY_GROUPS)
    channels = len(DIGITAL_DAY_MIX)
    assert len(frame) == len(BRANCHES) * groups * channels
    assert set(frame["channel"]) == set(DIGITAL_DAY_MIX)
    assert TOTAL_BRANCH[1] not in set(frame["branch_name"])
    assert sorted(frame["base_month"].unique()) == ["2026-01"]

    total = data.digital_usage_days_total
    assert set(total["branch_name"]) == {TOTAL_BRANCH[1]}
    assert len(total) == groups * channels


def test_digital_usage_days_strips_the_order_prefix(source_files):
    """`1)0일(미사용)`의 앞 번호를 떼고 읽는다.

    번호는 화면까지 보내지 않는다. 가로축에 늘어선 자리가 이미 차례를
    말하므로 눈금에 번호까지 적으면 글자만 길어진다.
    """
    data = source_files()()
    frame = data.digital_usage_days
    assert set(frame["usage_day_group"]) == set(DIGITAL_USAGE_DAY_GROUPS)
    assert list(frame["usage_day_group"].cat.categories) == list(
        DIGITAL_USAGE_DAY_GROUPS
    )


def test_digital_usage_days_keeps_each_channel_apart(source_files):
    """채널마다 제 몫이 그대로 온다. 펴는 과정에서 섞이지 않았다."""
    data = source_files()()
    frame = data.digital_usage_days
    first = frame[frame["branch_id"] == BRANCHES[0][0]]
    for channel, mix in DIGITAL_DAY_MIX.items():
        rows = first[first["channel"] == channel]
        rows = rows.sort_values("usage_day_group")
        assert list(rows["day_group_share"]) == list(mix)


def test_digital_usage_days_group_order_mismatch_stops(source_files):
    """원본이 적어 둔 차례가 화면 차례와 다르면 멈춘다.

    원본이 구간을 다시 늘어놓았는데 화면이 옛 차례로 그리면, 막대 순서가
    틀린 채로 맞는 것처럼 보인다(→ data.to_ordered_label_column).
    """
    frame = _digital3_frame()
    last = len(DIGITAL_USAGE_DAY_GROUPS)
    frame["이용일수"] = frame["이용일수"].map(
        lambda value: f"{last + 1 - int(value.split(')')[0])})"
        f"{value.split(')', 1)[1]}"
    )
    with pytest.raises(ValueError, match="이용일수"):
        source_files(digital3=frame)()


def test_digital_usage_days_unknown_group_stops(source_files):
    """구간 목록에 없는 값이 오면 그 값을 알리며 멈춘다."""
    frame = _digital3_frame()
    frame.loc[0, "이용일수"] = "1)30일 이상"
    with pytest.raises(ValueError, match="30일 이상"):
        source_files(digital3=frame)()


def test_digital_usage_days_duplicate_group_stops(source_files):
    """같은 기준월·지점·구간이 두 번 있으면 멈춘다.

    펴기 전에 확인해야 한다. 그대로 두면 채널 수만큼 부풀어 세 배가 된다.
    """
    frame = _digital3_frame()
    frame = pd.concat([frame, frame.iloc[[0]]], ignore_index=True)
    with pytest.raises(ValueError, match="두 번 이상"):
        source_files(digital3=frame)()


def test_digital_usage_days_keeps_the_source_share(source_files):
    """비중은 원본 값을 그대로 쓴다. 합이 100%인지 확인하지 않는다."""
    frame = _digital3_frame()
    frame["MTS_이용비중"] = 3.5
    data = source_files(digital3=frame)()
    rows = data.digital_usage_days
    mts = rows[rows["channel"] == "MTS"]
    assert (mts["day_group_share"] == 3.5).all()


def test_digital_usage_days_is_optional(source_files):
    """원본이 없어도 나머지 화면은 열린다."""
    data = source_files(with_digital=False)()
    assert data.digital_usage_days.empty
    assert data.digital_usage_days_total.empty


# 메뉴 순위 표본의 모양. 실제 원본은 순위 30까지지만 표본은 짧게 둔다.
# 몇 위까지인지는 실제 데이터에서 달라지므로 앱 코드에 적지 않는다.
DIGITAL_MENU_RANK_COUNT = 4

# 분류마다 1위의 조회 건수와 거래 전환 비율(%). 분류 차례대로 값을 갈라
# 두어야, 펴는 과정에서 분류끼리 섞였을 때 드러난다.
DIGITAL_MENU_TOP_VIEWS = (9000, 7000, 5000, 3000, 2000, 1000)
DIGITAL_MENU_TOP_RATES = (12.0, 46.0, 38.0, 33.0, 21.0, 17.0)


def _menu_name(category: str, rank: int) -> str:
    """표본이 쓰는 메뉴 이름. 실제 메뉴 이름을 흉내 내지 않는다."""
    return f"{category} 메뉴{rank}"


def _digital4_frame() -> pd.DataFrame:
    """디지털채널4 원본 표본.

    지점·'전체'마다 순위 행이 있고, 그 한 행에 메뉴 분류 여섯의 메뉴 이름과
    조회 건수, 거래 전환 비율이 가로로 붙어 있다. 원본이 마지막 한 달만
    담고 있어 표본도 그렇게 만든다.
    """
    rows = []
    month = MONTHS[-1]
    for branch_index, (code, name) in enumerate([*BRANCHES, TOTAL_BRANCH]):
        for rank in range(1, DIGITAL_MENU_RANK_COUNT + 1):
            row = {
                "기준월": int(month),
                "CSMT_ORZ_CD": code,
                "CSMT_ORZ_NM": name,
                "순위": rank,
            }
            for index, category in enumerate(DIGITAL_MENU_CATEGORIES):
                row[category] = _menu_name(category, rank)
                row[f"{category}_조회건수"] = (
                    DIGITAL_MENU_TOP_VIEWS[index]
                    - (rank - 1) * 100
                    + branch_index
                )
                row[f"{category}_r"] = round(
                    DIGITAL_MENU_TOP_RATES[index] - (rank - 1), 2
                )
            rows.append(row)
    return pd.DataFrame(rows)


def test_digital_menu_rank_rows_reach_the_frame(source_files):
    """가로로 붙어 있던 분류 여섯이 한 줄에 하나씩인 형태로 들어온다.

    행 수는 지점 × 순위 × 분류다. 원본이 마지막 한 달만 담고 있어 기간이
    한 달뿐이며, '전체' 지점 행은 따로 떨어져 나간다.
    """
    data = source_files()()
    frame = data.digital_menu_rank
    categories = len(DIGITAL_MENU_CATEGORIES)
    per_branch = DIGITAL_MENU_RANK_COUNT * categories
    assert len(frame) == len(BRANCHES) * per_branch
    assert set(frame["menu_category"]) == set(DIGITAL_MENU_CATEGORIES)
    assert TOTAL_BRANCH[1] not in set(frame["branch_name"])
    assert sorted(frame["base_month"].unique()) == ["2026-01"]

    total = data.digital_menu_rank_total
    assert set(total["branch_name"]) == {TOTAL_BRANCH[1]}
    assert len(total) == per_branch


def test_digital_menu_rank_keeps_each_category_apart(source_files):
    """분류마다 제 메뉴와 값이 그대로 온다. 펴는 과정에서 섞이지 않았다."""
    data = source_files()()
    frame = data.digital_menu_rank
    first = frame[frame["branch_id"] == BRANCHES[0][0]]
    for index, category in enumerate(DIGITAL_MENU_CATEGORIES):
        rows = first[first["menu_category"] == category]
        rows = rows.sort_values("menu_rank")
        assert list(rows["menu_name"]) == [
            _menu_name(category, rank)
            for rank in range(1, DIGITAL_MENU_RANK_COUNT + 1)
        ]
        assert rows.iloc[0]["view_count"] == DIGITAL_MENU_TOP_VIEWS[index]
        assert (
            rows.iloc[0]["trade_conversion_share"]
            == DIGITAL_MENU_TOP_RATES[index]
        )


def test_digital_menu_rank_keeps_the_declared_category_order(source_files):
    """분류 차례는 선언한 차례를 따른다. 가나다순으로 다시 세우지 않는다."""
    data = source_files()()
    frame = data.digital_menu_rank
    assert list(frame["menu_category"].cat.categories) == list(
        DIGITAL_MENU_CATEGORIES
    )


def test_digital_menu_rank_sorts_by_rank(source_files):
    """한 지점·한 분류 안에서 순위 차례로 줄을 세운다."""
    data = source_files()()
    frame = data.digital_menu_rank
    rows = frame[
        (frame["branch_id"] == BRANCHES[0][0])
        & (frame["menu_category"] == DIGITAL_MENU_CATEGORIES[0])
    ]
    assert list(rows["menu_rank"]) == list(
        range(1, DIGITAL_MENU_RANK_COUNT + 1)
    )


def test_digital_menu_rank_drops_blank_menu_names(source_files):
    """메뉴 이름이 빈 칸이면 그 줄을 만들지 않는다.

    가로로 펼친 파일에서 빈 칸은 '그 분류는 이 순위까지 없다'는 뜻이다.
    이름을 지어내 채우지 않는다(→ AGENTS.md §9).
    """
    frame = _digital4_frame()
    category = DIGITAL_MENU_CATEGORIES[-1]
    last = frame["순위"] == DIGITAL_MENU_RANK_COUNT
    frame.loc[last, category] = ""
    frame.loc[last, f"{category}_조회건수"] = None
    frame.loc[last, f"{category}_r"] = None
    data = source_files(digital4=frame)()
    rows = data.digital_menu_rank
    short = rows[rows["menu_category"] == category]
    assert len(short) == len(BRANCHES) * (DIGITAL_MENU_RANK_COUNT - 1)
    # 다른 분류는 그대로다.
    other = rows[rows["menu_category"] == DIGITAL_MENU_CATEGORIES[0]]
    assert len(other) == len(BRANCHES) * DIGITAL_MENU_RANK_COUNT


def test_digital_menu_rank_duplicate_rank_stops(source_files):
    """한 지점·한 분류 안에서 같은 순위가 두 번 있으면 멈춘다."""
    frame = _digital4_frame()
    frame = pd.concat([frame, frame.iloc[[0]]], ignore_index=True)
    with pytest.raises(ValueError, match="두 번 이상"):
        source_files(digital4=frame)()


def test_digital_menu_rank_duplicate_menu_stops(source_files):
    """한 지점·한 분류 안에서 같은 메뉴가 두 번 있으면 멈춘다.

    겹치면 그 메뉴의 조회 건수가 두 번 더해진다.
    """
    frame = _digital4_frame()
    category = DIGITAL_MENU_CATEGORIES[0]
    first = frame.index[frame["순위"] == 1][0]
    second = frame.index[frame["순위"] == 2][0]
    frame.loc[second, category] = frame.loc[first, category]
    with pytest.raises(ValueError, match="메뉴"):
        source_files(digital4=frame)()


def test_digital_menu_rank_negative_view_count_stops(source_files):
    """조회 건수에 음수가 있으면 멈춘다. 들어간 횟수는 음수일 수 없다."""
    frame = _digital4_frame()
    frame.loc[0, f"{DIGITAL_MENU_CATEGORIES[0]}_조회건수"] = -5
    with pytest.raises(ValueError, match="조회건수"):
        source_files(digital4=frame)()


def test_digital_menu_rank_missing_category_column_stops(source_files):
    """분류 컬럼이 빠져 있으면 그 이름을 알리며 멈춘다."""
    frame = _digital4_frame().drop(columns=[DIGITAL_MENU_CATEGORIES[1]])
    with pytest.raises(ValueError, match=DIGITAL_MENU_CATEGORIES[1]):
        source_files(digital4=frame)()


def test_digital_menu_rank_keeps_the_source_view_count(source_files):
    """조회 건수는 원본 값을 그대로 쓴다. 분류끼리 더하지 않는다.

    '공통고객'은 나머지 다섯을 합친 값이 아니라 다섯과 나란한 하나의
    분류다(→ data.DIGITAL_MENU_CATEGORIES).
    """
    frame = _digital4_frame()
    frame["공통고객_조회건수"] = 12345
    data = source_files(digital4=frame)()
    rows = data.digital_menu_rank
    common = rows[rows["menu_category"] == "공통고객"]
    assert (common["view_count"] == 12345).all()


def test_digital_menu_rank_keeps_the_source_conversion_share(source_files):
    """거래 전환 비율은 원본 값을 그대로 쓴다.

    원본이 이미 %로 계산해 담고 있어 100을 곱하거나 나누지 않고, 조회
    건수와 견주지도 않는다(→ AGENTS.md §9).
    """
    frame = _digital4_frame()
    # 조회 건수와 전혀 맞지 않는 비율을 넣어도 그대로 화면까지 간다.
    frame["국내주식_r"] = 7.25
    data = source_files(digital4=frame)()
    rows = data.digital_menu_rank
    stock = rows[rows["menu_category"] == "국내주식"]
    assert (stock["trade_conversion_share"] == 7.25).all()


def test_digital_menu_rank_conversion_share_out_of_range_stops(
    source_files,
):
    """거래 전환 비율이 0~100을 벗어나면 멈춘다.

    조회한 것 중의 몫이라 100%를 넘을 수 없다. 벗어난 값은 원본을 읽는
    방법이 틀렸다는 뜻이다.
    """
    frame = _digital4_frame()
    frame.loc[0, f"{DIGITAL_MENU_CATEGORIES[0]}_r"] = 180.0
    with pytest.raises(ValueError, match="거래 전환 비율"):
        source_files(digital4=frame)()


def test_digital_menu_rank_keeps_a_blank_conversion_share(source_files):
    """비율을 낼 수 없는 자리는 비운 채로 둔다. 0으로 채우지 않는다.

    0%는 '거래로 이어지지 않았다'는 측정값이라 '값이 없다'와 다르다
    (→ AGENTS.md §9).
    """
    frame = _digital4_frame()
    category = DIGITAL_MENU_CATEGORIES[0]
    frame.loc[0, f"{category}_r"] = None
    data = source_files(digital4=frame)()
    rows = data.digital_menu_rank
    blank = rows[
        (rows["menu_category"] == category) & (rows["menu_rank"] == 1)
    ]
    assert blank["trade_conversion_share"].isna().any()
    # 나머지 자리는 그대로 값이 있다.
    assert rows["trade_conversion_share"].notna().any()


def test_digital_menu_rank_missing_conversion_column_stops(source_files):
    """거래 전환 비율 컬럼이 빠져 있으면 그 이름을 알리며 멈춘다."""
    column = f"{DIGITAL_MENU_CATEGORIES[2]}_r"
    frame = _digital4_frame().drop(columns=[column])
    with pytest.raises(ValueError, match=column):
        source_files(digital4=frame)()


def test_digital_menu_rank_is_optional(source_files):
    """원본이 없어도 나머지 화면은 열린다."""
    data = source_files(with_digital=False)()
    assert data.digital_menu_rank.empty
    assert data.digital_menu_rank_total.empty
