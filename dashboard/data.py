"""데이터 계층.

대시보드가 데이터에 접근하는 유일한 경로다. 레이아웃·차트·그리드·콜백은
이 모듈이 반환한 데이터만 사용하고 파일이나 데이터베이스를 직접 읽지 않는다.

실제 데이터로 교체할 때 손댈 곳은 `_load_sample()` 자리에 들어갈 새 로더와
`_normalize()`의 컬럼 매핑뿐이다. 반환 구조(`DashboardData`)가 같으면
UI 코드는 수정하지 않는다.

금액 단위: `total_assets`는 억원 단위 정수다.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, fields
from functools import lru_cache

import numpy as np
import pandas as pd

# --- 분석 범위 ---------------------------------------------------------------
START_MONTH = "2025-07"
END_MONTH = "2026-07"
MONTH_COUNT = 13
CURRENT_MONTH = END_MONTH
PREVIOUS_MONTH = "2026-06"
YOY_BASE_MONTH = START_MONTH

BRANCH_COUNT = 27
TOTAL_LABEL = "전체"

# 최근 가입 고객 기준(개월). 실제 업무 기준이 정해지면 이 값만 바꾼다.
RECENT_SIGNUP_MONTHS = 12

AGE_GROUPS = ("10대 이하", "20대", "30대", "40대", "50대", "60대 이상")
# 평균 연령 계산에 쓰는 구간 대표값. 연령 분포와 평균 연령을 일치시키기 위해 쓴다.
AGE_MIDPOINTS = {
    "10대 이하": 15.0,
    "20대": 25.0,
    "30대": 35.0,
    "40대": 45.0,
    "50대": 55.0,
    "60대 이상": 67.0,
}

INVESTMENT_TYPES = ("성장형", "성장추구형", "위험중립형", "안정추구형", "안정형")
CONSENT_LABEL = "마케팅 동의"
NON_CONSENT_LABEL = "마케팅 비동의"

# --- 데이터 소스 -------------------------------------------------------------
DATA_SOURCE_ENV = "DASHBOARD_DATA_SOURCE"
DEFAULT_DATA_SOURCE = "sample"
# local_file, internal_source 는 실제 연결 방식이 확정된 뒤 구현한다.
SUPPORTED_DATA_SOURCES = ("sample",)

_SAMPLE_SEED = 20260731

MONTHLY_COLUMNS = (
    "base_month",
    "branch_id",
    "branch_name",
    "customer_count",
    "total_assets",
    "transaction_customer_count",
    "app_user_count",
)
AGE_COLUMNS = ("base_month", "branch_id", "branch_name", "age_group", "customer_count")
INVESTMENT_COLUMNS = (
    "base_month",
    "branch_id",
    "branch_name",
    "investment_type",
    "marketing_consent",
    "customer_count",
)
SUMMARY_COLUMNS = (
    "base_month",
    "branch_id",
    "branch_name",
    "customer_count",
    "male_customer_count",
    "average_age",
    "recent_signup_customer_count",
    "recommendation_consent_customer_count",
    "grade_s_or_higher_customer_count",
)


@dataclass(frozen=True)
class DashboardData:
    """UI 계층에 전달하는 표준 데이터 묶음.

    반환된 DataFrame은 캐시된 객체다. 사용하는 쪽에서 직접 수정하지 않는다.
    """

    monthly: pd.DataFrame
    age: pd.DataFrame
    investment: pd.DataFrame
    summary: pd.DataFrame

    @property
    def branch_names(self) -> list[str]:
        return sorted(self.monthly["branch_name"].unique().tolist())

    @property
    def months(self) -> list[str]:
        return sorted(self.monthly["base_month"].unique().tolist())


def month_range() -> list[str]:
    """분석 대상 월 목록을 `YYYY-MM` 문자열로 반환한다."""
    periods = pd.period_range(start=START_MONTH, periods=MONTH_COUNT, freq="M")
    return [str(period) for period in periods]


def load_dashboard_data(filters: dict | None = None) -> DashboardData:
    """대시보드 데이터를 반환한다.

    filters 예: {"branch_names": [...], "base_months": [...]}
    데이터 소스는 환경 변수 `DASHBOARD_DATA_SOURCE`로 고른다.
    """
    source = os.environ.get(DATA_SOURCE_ENV, DEFAULT_DATA_SOURCE).strip().lower()
    if source not in SUPPORTED_DATA_SOURCES:
        raise ValueError(
            f"지원하지 않는 데이터 소스입니다: {source!r}. "
            f"사용 가능한 값: {', '.join(SUPPORTED_DATA_SOURCES)}"
        )

    data = _load_sample()
    if filters:
        data = _apply_filters(data, filters)
    return data


@lru_cache(maxsize=1)
def _load_sample() -> DashboardData:
    """개발용 더미 데이터를 생성한다. seed가 고정되어 결과가 재현된다."""
    data = _generate_sample(np.random.default_rng(_SAMPLE_SEED))
    data = _normalize(data)
    validate_dashboard_data(data)
    return data


# --- 더미 데이터 생성 --------------------------------------------------------
def _generate_sample(rng: np.random.Generator) -> DashboardData:
    months = month_range()
    branch_ids = [f"B{index:02d}" for index in range(1, BRANCH_COUNT + 1)]
    branch_names = [f"지점 {index:02d}" for index in range(1, BRANCH_COUNT + 1)]

    # 지점 규모: 로그정규분포로 큰 지점과 작은 지점의 차이를 만든다.
    base_counts = np.clip(rng.lognormal(mean=np.log(2400), sigma=0.55, size=BRANCH_COUNT), 700, 9000)
    # 월 성장률: 평균은 소폭 성장이지만 일부 지점은 감소한다.
    monthly_drift = rng.normal(loc=0.0035, scale=0.0085, size=BRANCH_COUNT)
    asset_per_customer = np.clip(rng.normal(loc=2.8, scale=0.8, size=BRANCH_COUNT), 1.2, 5.5)
    transaction_ratio = np.clip(rng.normal(loc=0.43, scale=0.05, size=BRANCH_COUNT), 0.25, 0.60)
    app_ratio = np.clip(rng.normal(loc=0.72, scale=0.06, size=BRANCH_COUNT), 0.50, 0.90)
    male_ratio = np.clip(rng.normal(loc=0.50, scale=0.03, size=BRANCH_COUNT), 0.40, 0.60)
    recent_ratio = np.clip(rng.normal(loc=0.22, scale=0.06, size=BRANCH_COUNT), 0.05, 0.45)
    recommend_ratio = np.clip(rng.normal(loc=0.40, scale=0.07, size=BRANCH_COUNT), 0.20, 0.65)
    grade_s_ratio = np.clip(rng.normal(loc=0.25, scale=0.06, size=BRANCH_COUNT), 0.08, 0.50)

    # 시장 전체 자산 흐름(모든 지점 공통)
    market_factor = np.exp(np.cumsum(rng.normal(loc=0.002, scale=0.004, size=MONTH_COUNT)))

    age_weights = _perturb_weights(rng, (0.03, 0.14, 0.20, 0.22, 0.22, 0.19), scale=0.18)
    invest_weights = _perturb_weights(rng, (0.16, 0.24, 0.26, 0.20, 0.14), scale=0.16)
    # 성장하는 지점은 공격적 성향 비중이 조금 더 높게 기운다.
    growth_tilt = np.clip((monthly_drift - monthly_drift.mean()) / (monthly_drift.std() or 1.0), -2, 2)
    tilt = np.array([0.10, 0.05, 0.0, -0.05, -0.10])
    invest_weights = np.clip(invest_weights * (1.0 + growth_tilt[:, None] * tilt[None, :]), 0.01, None)
    invest_weights = invest_weights / invest_weights.sum(axis=1, keepdims=True)

    consent_base = np.array([0.72, 0.68, 0.60, 0.52, 0.45])
    consent_rate = np.clip(
        consent_base[None, :] * np.exp(rng.normal(0.0, 0.08, size=(BRANCH_COUNT, len(INVESTMENT_TYPES)))),
        0.20,
        0.90,
    )

    # 월별 고객 수: 완만한 추세 + 작은 잡음으로 급격한 변동을 피한다.
    noise = rng.normal(loc=0.0, scale=0.002, size=(BRANCH_COUNT, MONTH_COUNT))
    steps = monthly_drift[:, None] + noise
    steps[:, 0] = 0.0
    counts = np.rint(base_counts[:, None] * np.exp(np.cumsum(steps, axis=1))).astype(int)
    counts = np.maximum(counts, 100)

    monthly_rows: list[dict] = []
    age_rows: list[dict] = []
    invest_rows: list[dict] = []
    summary_rows: list[dict] = []

    for branch_index in range(BRANCH_COUNT):
        branch_id = branch_ids[branch_index]
        branch_name = branch_names[branch_index]
        for month_index, month in enumerate(months):
            customer_count = int(counts[branch_index, month_index])

            wobble = 1.0 + rng.normal(0.0, 0.012)
            transaction_count = _bounded_count(customer_count, transaction_ratio[branch_index] * wobble)
            app_count = _bounded_count(customer_count, app_ratio[branch_index] * wobble)
            total_assets = int(
                round(customer_count * asset_per_customer[branch_index] * market_factor[month_index])
            )

            monthly_rows.append(
                {
                    "base_month": month,
                    "branch_id": branch_id,
                    "branch_name": branch_name,
                    "customer_count": customer_count,
                    "total_assets": total_assets,
                    "transaction_customer_count": transaction_count,
                    "app_user_count": app_count,
                }
            )

            age_counts = _split_counts(customer_count, age_weights[branch_index])
            for age_group, count in zip(AGE_GROUPS, age_counts):
                age_rows.append(
                    {
                        "base_month": month,
                        "branch_id": branch_id,
                        "branch_name": branch_name,
                        "age_group": age_group,
                        "customer_count": int(count),
                    }
                )

            invest_counts = _split_counts(customer_count, invest_weights[branch_index])
            for type_index, (investment_type, count) in enumerate(zip(INVESTMENT_TYPES, invest_counts)):
                count = int(count)
                consent_count = _bounded_count(count, consent_rate[branch_index, type_index])
                invest_rows.append(
                    {
                        "base_month": month,
                        "branch_id": branch_id,
                        "branch_name": branch_name,
                        "investment_type": investment_type,
                        "marketing_consent": True,
                        "customer_count": consent_count,
                    }
                )
                invest_rows.append(
                    {
                        "base_month": month,
                        "branch_id": branch_id,
                        "branch_name": branch_name,
                        "investment_type": investment_type,
                        "marketing_consent": False,
                        "customer_count": count - consent_count,
                    }
                )

            # 평균 연령은 연령 분포에서 계산해 두 데이터가 어긋나지 않게 한다.
            midpoints = np.array([AGE_MIDPOINTS[group] for group in AGE_GROUPS])
            average_age = float(np.dot(age_counts, midpoints) / customer_count)
            summary_rows.append(
                {
                    "base_month": month,
                    "branch_id": branch_id,
                    "branch_name": branch_name,
                    "customer_count": customer_count,
                    "male_customer_count": _bounded_count(customer_count, male_ratio[branch_index]),
                    "average_age": round(average_age, 2),
                    "recent_signup_customer_count": _bounded_count(
                        customer_count, recent_ratio[branch_index]
                    ),
                    "recommendation_consent_customer_count": _bounded_count(
                        customer_count, recommend_ratio[branch_index]
                    ),
                    "grade_s_or_higher_customer_count": _bounded_count(
                        customer_count, grade_s_ratio[branch_index]
                    ),
                }
            )

    return DashboardData(
        monthly=pd.DataFrame(monthly_rows, columns=list(MONTHLY_COLUMNS)),
        age=pd.DataFrame(age_rows, columns=list(AGE_COLUMNS)),
        investment=pd.DataFrame(invest_rows, columns=list(INVESTMENT_COLUMNS)),
        summary=pd.DataFrame(summary_rows, columns=list(SUMMARY_COLUMNS)),
    )


def _perturb_weights(rng: np.random.Generator, base: tuple[float, ...], scale: float) -> np.ndarray:
    """지점마다 조금씩 다른 구성비를 만든다. 각 행의 합은 1이다."""
    weights = np.array(base, dtype=float)[None, :] * np.exp(
        rng.normal(0.0, scale, size=(BRANCH_COUNT, len(base)))
    )
    return weights / weights.sum(axis=1, keepdims=True)


def _split_counts(total: int, weights: np.ndarray) -> np.ndarray:
    """합계가 정확히 total이 되도록 정수로 나눈다(최대 잔여 방식)."""
    if total <= 0:
        return np.zeros(len(weights), dtype=int)
    share = np.asarray(weights, dtype=float)
    share = share / share.sum()
    raw = share * total
    counts = np.floor(raw).astype(int)
    remainder = total - int(counts.sum())
    if remainder > 0:
        order = np.argsort(-(raw - counts))
        counts[order[:remainder]] += 1
    return counts


def _bounded_count(total: int, ratio: float) -> int:
    """0 이상 total 이하의 정수 고객 수로 변환한다."""
    return int(min(max(round(total * float(ratio)), 0), total))


# --- 정규화와 검증 -----------------------------------------------------------
def _normalize(data: DashboardData) -> DashboardData:
    """컬럼 순서, 타입, 정렬을 표준 형태로 맞춘다.

    실제 데이터를 붙일 때 원본 컬럼명 매핑도 이 단계에서 처리한다.
    """
    monthly = _normalize_frame(data.monthly, MONTHLY_COLUMNS, ["base_month", "branch_id"])
    age = _normalize_frame(data.age, AGE_COLUMNS, ["base_month", "branch_id"])
    age["age_group"] = pd.Categorical(age["age_group"], categories=AGE_GROUPS, ordered=True)
    investment = _normalize_frame(data.investment, INVESTMENT_COLUMNS, ["base_month", "branch_id"])
    investment["investment_type"] = pd.Categorical(
        investment["investment_type"], categories=INVESTMENT_TYPES, ordered=True
    )
    investment["marketing_consent"] = investment["marketing_consent"].astype(bool)
    summary = _normalize_frame(data.summary, SUMMARY_COLUMNS, ["base_month", "branch_id"])
    return DashboardData(monthly=monthly, age=age, investment=investment, summary=summary)


def _normalize_frame(
    frame: pd.DataFrame, columns: tuple[str, ...], sort_by: list[str]
) -> pd.DataFrame:
    missing = [column for column in columns if column not in frame.columns]
    if missing:
        raise ValueError(f"필수 컬럼이 없습니다: {', '.join(missing)}")
    normalized = frame.loc[:, list(columns)].copy()
    normalized["base_month"] = normalized["base_month"].astype(str).str.slice(0, 7)
    count_columns = [column for column in columns if column.endswith("count")]
    for column in count_columns:
        normalized[column] = (
            pd.to_numeric(normalized[column], errors="coerce").fillna(0).clip(lower=0).astype(int)
        )
    if "total_assets" in normalized.columns:
        normalized["total_assets"] = (
            pd.to_numeric(normalized["total_assets"], errors="coerce").fillna(0).clip(lower=0).astype(int)
        )
    if "average_age" in normalized.columns:
        normalized["average_age"] = pd.to_numeric(normalized["average_age"], errors="coerce")
    return normalized.sort_values(sort_by).reset_index(drop=True)


def validate_dashboard_data(data: DashboardData) -> None:
    """더미 데이터와 실제 데이터가 같은 기준을 통과하도록 검증한다."""
    for field in fields(DashboardData):
        frame = getattr(data, field.name)
        if not isinstance(frame, pd.DataFrame):
            raise ValueError(f"{field.name}이 DataFrame이 아닙니다.")
        if frame.empty:
            raise ValueError(f"{field.name} 데이터가 비어 있습니다.")
        if frame.isna().to_numpy().any():
            raise ValueError(f"{field.name}에 누락값이 있습니다.")

    expected_months = set(month_range())
    for name, frame in (
        ("monthly", data.monthly),
        ("age", data.age),
        ("investment", data.investment),
        ("summary", data.summary),
    ):
        months = set(frame["base_month"].unique())
        if months != expected_months:
            raise ValueError(f"{name}의 기준 월이 분석 범위와 다릅니다.")
        branch_count = frame["branch_id"].nunique()
        if branch_count != BRANCH_COUNT:
            raise ValueError(f"{name}의 지점 수가 {BRANCH_COUNT}개가 아닙니다: {branch_count}")

    monthly = data.monthly
    for column in ("transaction_customer_count", "app_user_count"):
        if (monthly[column] > monthly["customer_count"]).any():
            raise ValueError(f"{column}이 고객 수보다 큽니다.")

    key = ["base_month", "branch_id"]
    base = monthly.set_index(key)["customer_count"]

    age_sum = data.age.groupby(key, observed=True)["customer_count"].sum()
    if not age_sum.reindex(base.index).eq(base).all():
        raise ValueError("연령 구간별 고객 수 합계가 고객 수와 다릅니다.")

    invest_sum = data.investment.groupby(key, observed=True)["customer_count"].sum()
    if not invest_sum.reindex(base.index).eq(base).all():
        raise ValueError("투자성향별 고객 수 합계가 고객 수와 다릅니다.")

    summary = data.summary.set_index(key)
    if not summary["customer_count"].reindex(base.index).eq(base).all():
        raise ValueError("요약 데이터의 고객 수가 월별 데이터와 다릅니다.")
    for column in (
        "male_customer_count",
        "recent_signup_customer_count",
        "recommendation_consent_customer_count",
        "grade_s_or_higher_customer_count",
    ):
        if (summary[column] > summary["customer_count"]).any():
            raise ValueError(f"{column}이 고객 수보다 큽니다.")
    if not summary["average_age"].between(0, 120).all():
        raise ValueError("평균 연령이 유효 범위를 벗어났습니다.")


def _apply_filters(data: DashboardData, filters: dict) -> DashboardData:
    branch_names = filters.get("branch_names")
    base_months = filters.get("base_months")

    def _filter(frame: pd.DataFrame) -> pd.DataFrame:
        result = frame
        if branch_names:
            result = result[result["branch_name"].isin(branch_names)]
        if base_months:
            result = result[result["base_month"].isin(base_months)]
        return result.reset_index(drop=True)

    return DashboardData(
        monthly=_filter(data.monthly),
        age=_filter(data.age),
        investment=_filter(data.investment),
        summary=_filter(data.summary),
    )
