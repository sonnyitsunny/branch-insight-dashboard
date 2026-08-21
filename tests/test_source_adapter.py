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

import numpy as np
import pandas as pd
import pytest

from dashboard import metrics as shared
from dashboard.tabs.customer import metrics
from dashboard.data import (
    AGE_GROUPS,
    ALL_AGE_GROUPS,
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
from dashboard.sources import profile as profile_source
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
SOURCE_AGE = list(profile_source.AGE_COLUMNS)
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


def _profile_row(code: str, name: str, start: int, end: int) -> dict:
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


def _profile_frame(offsets: dict[int, int] | None = None) -> pd.DataFrame:
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
        rows.append(_profile_row(code, name, start, end))
    rows.append(_profile_row(*TOTAL_BRANCH, total_start, total_end))
    return pd.DataFrame(rows)


def _row_with_other(
    code: str,
    name: str,
    start: int,
    end: int,
    other: int,
    age_counts: list[int],
) -> dict:
    """`_profile_row`와 같되 연령 구간 인원을 직접 받는다.

    실제 원본처럼 '합계'에는 '기타'가 빠지고 '고객수_종료월'에는 들어간다.
    """
    row = _profile_row(code, name, start, end)
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


def _profile_with_other(other: int) -> pd.DataFrame:
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


@pytest.fixture
def source_files(tmp_path, monkeypatch):
    """원본 파일들을 만들고 환경 변수를 걸어 주는 헬퍼를 반환한다.

    `with_asset=False`로 부르면 자산 파일을, `with_consulting=False`로
    부르면 상담 파일을 지정하지 않는다. 필수가 아닌 원본이 빠졌을 때의
    동작을 확인할 때 쓴다.
    """

    def _write(
        monthly: pd.DataFrame | None = None,
        profile: pd.DataFrame | None = None,
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
        with_asset: bool = True,
        with_consulting: bool = True,
        with_transaction: bool = True,
        with_revenue: bool = True,
        with_product: bool = True,
    ):
        monthly_path = tmp_path / "monthly.pkl"
        profile_path = tmp_path / "profile.pkl"
        (monthly if monthly is not None else _monthly_frame()).to_pickle(monthly_path)
        (profile if profile is not None else _profile_frame()).to_pickle(profile_path)
        monkeypatch.setenv("DASHBOARD_DATA_SOURCE", "local_file")
        monkeypatch.setenv("DASHBOARD_DATA_FILE", str(monthly_path))
        monkeypatch.setenv("DASHBOARD_PROFILE_FILE", str(profile_path))
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
    data = source_files(profile=_profile_with_other(other))()

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
    given = _profile_frame().set_index("CSMT_ORZ_NM")["고객수증가율"]
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
    given = _profile_frame().set_index("CSMT_ORZ_NM").loc[TOTAL_BRANCH[1]]
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
    profile = _profile_frame({0: _big_gap(0)})
    with pytest.raises(ValueError, match="너무 다릅니다"):
        source_files(profile=profile)()




def _big_gap(branch_index: int) -> int:
    """허용 범위를 확실히 넘는 차이."""
    count = _counts(branch_index, len(MONTHS) - 1)
    return int(COUNT_TOLERANCE + count * 0.05) + 1


def test_investment_parts_that_do_not_add_up_are_rejected(source_files):
    profile = _profile_frame()
    profile.loc[0, f"{INVESTMENT_TYPES[0]}_희망"] = (
        int(profile.loc[0, f"{INVESTMENT_TYPES[0]}_희망"]) + 3
    )
    with pytest.raises(ValueError, match="숫자가 서로 맞지 않는 지점"):
        source_files(profile=profile)()


def test_percent_given_where_a_ratio_is_expected_is_rejected(source_files):
    """0~1 비율 자리에 이미 %가 들어오면 두 번 곱해져 100을 넘는다. 그때 멈춘다."""
    profile = _profile_frame()
    profile["남성여부"] = profile["남성여부"] * 100
    with pytest.raises(ValueError, match="0~100 범위를 벗어난"):
        source_files(profile=profile)()


def test_missing_source_column_names_itself(source_files):
    profile = _profile_frame().drop(columns=["권유여부"])
    with pytest.raises(ValueError, match="권유여부"):
        source_files(profile=profile)()


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
