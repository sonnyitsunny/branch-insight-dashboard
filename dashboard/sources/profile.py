"""원본 파일 — 지점별 프로필.

기준 월 컬럼이 없고 한 시점만 담고 있다. 연령 구간과 투자성향이 가로로
펼쳐진 형태라, 여기서 한 줄에 한 항목인 표준 형태로 편다.

원본 컬럼 이름이 바뀌면 이 파일의 표만 고친다. 다른 파일은 고치지 않는다
(→ AGENTS.md §9).
"""

from __future__ import annotations

import pandas as pd

from dashboard.data import (
    EXCLUDED_INVESTMENT_TYPES,
    INVESTMENT_TYPES,
    SHARE_TOLERANCE_PP,
    to_numeric_column,
)

FILE = "지점프로필.pkl"
FILE_ENV = "DASHBOARD_PROFILE_FILE"

LABEL = "지점 프로필"

# 원본 컬럼명 → 내부 표준 컬럼명.
COLUMNS: dict[str, str] = {
    "CSMT_ORZ_CD": "branch_id",
    "CSMT_ORZ_NM": "branch_name",
    "고객수_종료월": "customer_count",
    "연령": "average_age",
    "고객수증가율": "customer_growth_yoy",
    "남성여부": "male_share",
    "최근1년이내가입": "recent_signup_share",
    "권유여부": "recommendation_share",
    "고객등급S이상": "grade_s_share",
}

# 시작 시점 고객 수. 월별 파일의 첫 월과 맞는지 대조하는 데만 쓴다.
START_COUNT_COLUMN = "고객수_시작월"

# 0~1 비율로 들어오므로 100을 곱해 %로 맞춘다.
# 고객수증가율과 연령대 비중은 이미 %라서 여기에 넣지 않는다.
RATIO_COLUMNS = (
    "male_share",
    "recent_signup_share",
    "recommendation_share",
    "grade_s_share",
)

# 연령 구간: 원본 컬럼 → 표준 구간 이름
AGE_COLUMNS: dict[str, str] = {
    "10대이하": "10대 이하",
    "20대": "20대",
    "30대": "30대",
    "40대": "40대",
    "50대": "50대",
    "60대이상": "60대 이상",
}
AGE_TOTAL_COLUMN = "합계"
# 연령 미선택 컬럼. 있으면 읽고, 없으면 그냥 넘어간다.
# 이 값은 '합계'에 포함되지 않으므로 위 6개 구간과 따로 다룬다.
AGE_OTHER_COLUMNS: dict[str, str] = {"기타": "기타"}
# 연령 구간별 비중 컬럼의 접미사. 예: "20대" → "20대비중"
AGE_SHARE_SUFFIX = "비중"

# 투자성향: 분류마다 '_희망'(마케팅 동의)과 '_불원' 컬럼이 있다.
CONSENT_SUFFIX = "_희망"
NON_CONSENT_SUFFIX = "_불원"


def build(frame: pd.DataFrame, base_month: str) -> pd.DataFrame:
    """표준 이름으로 바뀐 원본에 기준 월을 붙이고 비율을 %로 맞춘다.

    원본에 기준 월 컬럼이 없으므로 월별 파일의 마지막 월을 받아 쓴다.
    """
    profile = frame.copy()
    profile["base_month"] = base_month
    for column in RATIO_COLUMNS:
        profile[column] = (
            to_numeric_column(profile[column], LABEL, column) * 100.0
        )
    return profile


def _keys(profile: pd.DataFrame) -> pd.DataFrame:
    return profile.loc[:, ["base_month", "branch_id", "branch_name"]].copy()


def build_age(profile: pd.DataFrame) -> pd.DataFrame:
    """연령 구간 컬럼을 한 줄에 한 구간인 표준 형태로 편다.

    '기타'(연령 미선택)는 원본의 '합계'에는 없지만 고객 수에는 있다.
    따로 읽어 한 줄로 넣어 두면 고객 수 대조가 맞고, 화면의 분포 차트는
    AGE_GROUPS만 그리므로 자동으로 빠진다.
    """
    missing = [
        column for column in AGE_COLUMNS if column not in profile.columns
    ]
    if missing:
        raise ValueError(
            f"{LABEL}에 연령 구간 컬럼이 없습니다: {', '.join(missing)}"
        )

    counts = {
        source: to_numeric_column(profile[source], LABEL, source)
        for source in AGE_COLUMNS
    }
    total = sum(counts.values())
    if AGE_TOTAL_COLUMN in profile.columns:
        given = to_numeric_column(
            profile[AGE_TOTAL_COLUMN], LABEL, AGE_TOTAL_COLUMN
        )
        check_equal_counts(
            total, given, profile, "연령 구간 6개의 합", AGE_TOTAL_COLUMN
        )

    parts = []
    for source, age_group in AGE_COLUMNS.items():
        part = _keys(profile)
        part["age_group"] = age_group
        part["customer_count"] = counts[source]
        share_column = f"{source}{AGE_SHARE_SUFFIX}"
        if share_column in profile.columns:
            share = to_numeric_column(
                profile[share_column], LABEL, share_column
            )
            check_share_matches_counts(
                share, counts[source], total, profile, share_column
            )
            part["share"] = share
        parts.append(part)

    # '기타'는 비중을 만들지 않는다. 원본의 비중은 '합계'를 분모로 쓰는데
    # 거기에 '기타'가 없어서, 함께 그리면 합이 100%를 넘는다.
    for source, age_group in AGE_OTHER_COLUMNS.items():
        if source not in profile.columns:
            continue
        part = _keys(profile)
        part["age_group"] = age_group
        part["customer_count"] = to_numeric_column(
            profile[source], LABEL, source
        )
        parts.append(part)
    return pd.concat(parts, ignore_index=True)


def check_share_matches_counts(
    share: pd.Series,
    count: pd.Series,
    total: pd.Series,
    profile: pd.DataFrame,
    column: str,
) -> None:
    """원본이 담은 비중이 인원수에서 계산한 비중과 맞는지 확인한다.

    반올림 차이는 넘어가고, 집계 기준이 달라 크게 벌어질 때만 멈춘다.
    막대 높이는 이 비중으로, hover의 고객 수는 인원수로 그리므로 둘이 크게
    어긋나면 화면 안에서 숫자가 서로 맞지 않게 된다.
    """
    computed = (count / total * 100.0).where(total > 0)
    gap = (share - computed).abs()
    over = gap > SHARE_TOLERANCE_PP
    if not over.any():
        return
    index = over.idxmax()
    raise ValueError(
        f"원본의 '{column}'이 인원수에서 계산한 비중과 다른 지점이 "
        f"{int(over.sum())}곳 있습니다. "
        f"예: {profile.loc[index, 'branch_name']} — "
        f"원본 {share[index]:.4f}% vs 인원수 기준 {computed[index]:.4f}% "
        f"(차이 {gap[index]:.4f}%p, 허용 {SHARE_TOLERANCE_PP}%p). "
        "두 값의 집계 기준이 같은지 확인해 주세요."
    )


def build_investment(profile: pd.DataFrame) -> pd.DataFrame:
    """투자성향 × 마케팅 동의 여부를 한 줄에 하나인 표준 형태로 편다.

    화면에서 빼는 분류도 합계 대조에는 넣는다. 그래야 고객이 새는지 알 수
    있다.
    """
    all_types = (*INVESTMENT_TYPES, *EXCLUDED_INVESTMENT_TYPES)
    suffixes = ((CONSENT_SUFFIX, True), (NON_CONSENT_SUFFIX, False))
    needed = [
        f"{name}{suffix}" for name in all_types for suffix, _ in suffixes
    ]
    missing = [column for column in needed if column not in profile.columns]
    if missing:
        raise ValueError(
            f"{LABEL}에 투자성향 컬럼이 없습니다: {', '.join(missing)}"
        )

    values = {
        column: to_numeric_column(profile[column], LABEL, column)
        for column in needed
    }

    # 분류별 희망 + 불원이 접미사 없는 분류 합계와 맞는지 확인한다.
    for name in all_types:
        if name not in profile.columns:
            continue
        pair = (
            values[f"{name}{CONSENT_SUFFIX}"]
            + values[f"{name}{NON_CONSENT_SUFFIX}"]
        )
        given = to_numeric_column(profile[name], LABEL, name)
        check_equal_counts(pair, given, profile, f"{name} 희망+불원", name)

    # 제외 분류까지 더한 값이 고객 수와 맞아야 한다.
    total = sum(values.values())
    check_equal_counts(
        total,
        to_numeric_column(profile["customer_count"], LABEL, "customer_count"),
        profile,
        "투자성향 전체 합계",
        "고객수_종료월",
    )

    parts = []
    for name in INVESTMENT_TYPES:
        for suffix, consent in suffixes:
            part = _keys(profile)
            part["investment_type"] = name
            part["marketing_consent"] = consent
            part["customer_count"] = values[f"{name}{suffix}"]
            parts.append(part)
    return pd.concat(parts, ignore_index=True)


def check_equal_counts(
    computed: pd.Series,
    given: pd.Series,
    profile: pd.DataFrame,
    label: str,
    column: str,
) -> None:
    """계산한 합계와 원본이 적어 둔 값이 다르면 어느 지점인지 알리며 멈춘다."""
    mismatch = computed != given
    if not mismatch.any():
        return
    index = mismatch.idxmax()
    branch = profile.loc[index, "branch_name"]
    raise ValueError(
        f"원본 안에서 숫자가 서로 맞지 않는 지점이 {int(mismatch.sum())}곳"
        " 있습니다. "
        f"[{label}] vs 원본 컬럼 '{column}'. "
        f"예: {branch} — {computed[index]:,} vs {given[index]:,}. "
        "원본을 확인한 뒤 다시 만들어 주세요."
    )
