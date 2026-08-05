"""데이터 계층.

대시보드가 데이터에 접근하는 유일한 경로다. 레이아웃·차트·그리드·콜백은
이 모듈이 반환한 데이터만 사용하고 파일이나 데이터베이스를 직접 읽지 않는다.

실제 데이터로 교체할 때 손댈 곳은 `SOURCE_COLUMN_MAP`(원본 컬럼명 매핑)뿐이다.
반환 구조(`DashboardData`)가 같으면 UI 코드는 수정하지 않는다.

정규화는 값을 조용히 고치지 않는다. 읽을 수 없는 값이나 모르는 분류값을 만나면
0이나 결측으로 덮지 않고 어느 컬럼의 어떤 값이 문제인지 알려주며 멈춘다.
틀린 숫자가 맞는 것처럼 화면에 뜨는 쪽이 더 위험하기 때문이다.

금액 단위: `total_assets`는 억원 단위 정수다.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, fields
from functools import lru_cache

import numpy as np
import pandas as pd

# --- 기준 월 계산 -------------------------------------------------------------
# 전년 동월 비교 간격(개월). 이 값 하나로 YoY 기준을 정한다.
YOY_MONTHS = 12


def shift_month(base_month: str, months: int) -> str:
    """`YYYY-MM`에서 `months`만큼 이동한 월을 반환한다. 음수면 과거로 간다."""
    return str(pd.Period(str(base_month)[:7], freq="M") + months)


# --- 분석 범위 ---------------------------------------------------------------
# 아래 값들은 서로 손으로 맞추지 않는다. 하나가 바뀌면 나머지가 따라온다.
START_MONTH = "2025-07"
MONTH_COUNT = 13
END_MONTH = shift_month(START_MONTH, MONTH_COUNT - 1)

# 기준 월의 기본값. 실제 데이터에서는 `reference_month()`로 데이터의 최신 월을 쓴다.
CURRENT_MONTH = END_MONTH
PREVIOUS_MONTH = shift_month(CURRENT_MONTH, -1)
YOY_BASE_MONTH = shift_month(CURRENT_MONTH, -YOY_MONTHS)

# 기준 월을 특정 월로 고정하고 싶을 때 쓰는 환경 변수(`YYYY-MM`).
# 지정하지 않으면 데이터의 최신 월을 기준 월로 삼는다.
BASE_MONTH_ENV = "DASHBOARD_BASE_MONTH"

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
NON_CONSENT_LABEL = "마케팅 불원"

# 원본이 연령 구간·투자성향을 숫자 코드로 담고 있으면 코드→이름을 여기에만 적는다.
# 예: {"1": "10대 이하", "2": "20대", ...}. 코드는 문자열로 적는다.
# 비어 있으면 원본이 위의 이름을 그대로 쓴다는 뜻이다.
AGE_GROUP_CODES: dict[str, str] = {}
INVESTMENT_TYPE_CODES: dict[str, str] = {}

# --- 데이터 소스 -------------------------------------------------------------
DATA_SOURCE_ENV = "DASHBOARD_DATA_SOURCE"
# local_file 소스에서 읽을 pkl 파일 경로.
DATA_FILE_ENV = "DASHBOARD_DATA_FILE"
DEFAULT_DATA_SOURCE = "sample"
# internal_source 는 실제 연결 방식이 확정된 뒤 구현한다.
SUPPORTED_DATA_SOURCES = ("sample", "local_file")

# 원본 컬럼명 → 내부 표준 컬럼명.
# 실제 파일의 컬럼 이름이 아래 표준 이름과 다르면 여기에만 적는다.
# 다른 파일은 고치지 않는다. 예: {"기준년월": "base_month", "지점코드": "branch_id"}
SOURCE_COLUMN_MAP: dict[str, str] = {}

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

# pkl 파일에 담아야 할 4개 데이터와 각각의 필수 컬럼.
FRAME_NAMES = ("monthly", "age", "investment", "summary")
FRAME_COLUMNS: dict[str, tuple[str, ...]] = {
    "monthly": MONTHLY_COLUMNS,
    "age": AGE_COLUMNS,
    "investment": INVESTMENT_COLUMNS,
    "summary": SUMMARY_COLUMNS,
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
    데이터 소스는 환경 변수 `DASHBOARD_DATA_SOURCE`로 고른다.

    - `sample`(기본) — 개발용 더미 데이터
    - `local_file` — `DASHBOARD_DATA_FILE`이 가리키는 pkl 파일
    """
    source = os.environ.get(DATA_SOURCE_ENV, DEFAULT_DATA_SOURCE).strip().lower()
    if source not in SUPPORTED_DATA_SOURCES:
        raise ValueError(
            f"지원하지 않는 데이터 소스입니다: {source!r}. "
            f"사용 가능한 값: {', '.join(SUPPORTED_DATA_SOURCES)}"
        )

    data = _load_sample() if source == "sample" else _load_local_file(_data_file_path())
    if filters:
        data = _apply_filters(data, filters)
    return data


@lru_cache(maxsize=1)
def _load_sample() -> DashboardData:
    """개발용 더미 데이터를 생성한다. seed가 고정되어 결과가 재현된다."""
    data = _generate_sample(np.random.default_rng(_SAMPLE_SEED))
    data = _normalize(data)
    # 더미 데이터는 생성기가 만든 값이므로 기간·지점 수까지 정확히 확인한다.
    # 실제 데이터에는 이 두 가지를 요구하지 않는다(→ validate_dashboard_data).
    validate_dashboard_data(
        data, expected_months=tuple(month_range()), expected_branch_count=BRANCH_COUNT
    )
    return data


# --- 실제 데이터(pkl) 읽기 ----------------------------------------------------
def _data_file_path() -> str:
    path = os.environ.get(DATA_FILE_ENV, "").strip()
    if not path:
        raise ValueError(
            f"{DATA_SOURCE_ENV}=local_file 을 쓰려면 "
            f"{DATA_FILE_ENV} 환경 변수에 pkl 파일 경로를 지정해야 합니다."
        )
    if not os.path.isfile(path):
        raise ValueError(f"데이터 파일을 찾을 수 없습니다: {path}")
    return path


def _load_local_file(path: str) -> DashboardData:
    """pkl 파일을 읽는다. 파일이 갱신되면 자동으로 다시 읽는다.

    주의: pickle은 파일을 여는 것만으로 그 안의 코드가 실행될 수 있는 형식이다.
    사내에서 직접 만든 파일만 사용한다.
    """
    stat = os.stat(path)
    return _read_pickle(path, stat.st_mtime_ns, stat.st_size)


@lru_cache(maxsize=4)
def _read_pickle(path: str, mtime_ns: int, size: int) -> DashboardData:
    """캐시 키에 수정 시각과 크기를 넣어 파일이 바뀌면 다시 읽게 한다."""
    del mtime_ns, size  # 캐시 키로만 쓴다.
    data = _from_pickle_object(pd.read_pickle(path), path)
    data = _normalize(data)
    validate_dashboard_data(data)
    return data


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
            f"{', '.join(FRAME_NAMES)} 4개를 키로 갖는 dict로 저장하세요."
        )
    missing = [name for name in FRAME_NAMES if name not in raw]
    if missing:
        raise ValueError(
            f"{path} 에 다음 데이터가 없습니다: {', '.join(missing)}. "
            f"필요한 키: {', '.join(FRAME_NAMES)}"
        )

    frames: dict[str, pd.DataFrame] = {}
    for name in FRAME_NAMES:
        frame = raw[name]
        if not isinstance(frame, pd.DataFrame):
            raise ValueError(
                f"{path} 의 {name!r} 이 DataFrame이 아니라 {type(frame).__name__} 입니다."
            )
        frames[name] = frame.rename(columns=SOURCE_COLUMN_MAP) if SOURCE_COLUMN_MAP else frame
    return DashboardData(**frames)


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
_SORT_KEY = ["base_month", "branch_id"]
_MONTH_PATTERN = r"\d{4}-(0[1-9]|1[0-2])"

# 마케팅 동의 여부를 참·거짓으로 읽을 때 허용하는 표기.
# 원본이 "Y"/"N" 같은 문자열이면 bool로 그냥 바꿀 수 없다. 빈 문자열이 아닌
# 모든 문자열은 참이 되어 "N"까지 동의로 뒤집히기 때문이다.
_TRUE_TEXTS = frozenset({"true", "t", "y", "yes", "1", "동의", "o"})
_FALSE_TEXTS = frozenset({"false", "f", "n", "no", "0", "미동의", "비동의", "불원", "x"})


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
        "investment": _normalize_frame(_reshape_investment(data.investment), "investment"),
        "summary": _normalize_frame(data.summary, "summary"),
    }
    source_totals = {}
    for name in FRAME_NAMES:
        frames[name], source_totals[name] = _split_source_total(frames[name], name)

    frames["age"]["age_group"] = _to_category(
        frames["age"]["age_group"], AGE_GROUPS, "age", "age_group", AGE_GROUP_CODES
    )
    frames["investment"]["investment_type"] = _to_category(
        frames["investment"]["investment_type"],
        INVESTMENT_TYPES,
        "investment",
        "investment_type",
        INVESTMENT_TYPE_CODES,
    )
    frames["investment"]["marketing_consent"] = _to_bool_column(
        frames["investment"]["marketing_consent"], "investment", "marketing_consent"
    )

    normalized = DashboardData(**frames)
    _check_source_total(normalized, source_totals["monthly"])
    return normalized


def _reshape_investment(frame: pd.DataFrame) -> pd.DataFrame:
    """동의·불원이 각각 인원수 컬럼으로 있으면 표준 형태(한 줄에 한 구분)로 편다.

    이미 `marketing_consent` 컬럼이 있으면 그대로 둔다.
    """
    if "marketing_consent" in frame.columns:
        return frame
    wide = [column for column in INVESTMENT_WIDE_COLUMNS if column not in frame.columns]
    if wide:
        return frame  # 표준 형태도 아니고 넓은 형태도 아니면 아래 컬럼 검사에서 걸린다.

    keys = ["base_month", "branch_id", "branch_name", "investment_type"]
    parts = []
    for column, consent in (
        ("consent_customer_count", True),
        ("non_consent_customer_count", False),
    ):
        part = frame.loc[:, [*keys, column]].rename(columns={column: "customer_count"})
        part["marketing_consent"] = consent
        parts.append(part)
    return pd.concat(parts, ignore_index=True)


def _split_source_total(frame: pd.DataFrame, name: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """원본의 '전체' 합계 행을 지점 행과 분리한다."""
    is_total = frame["branch_name"] == TOTAL_LABEL
    if not is_total.any():
        return frame, frame.iloc[0:0]
    branches = frame[~is_total].reset_index(drop=True)
    if branches.empty:
        raise ValueError(f"{name} 데이터에 '{TOTAL_LABEL}' 행만 있고 지점 행이 없습니다.")
    return branches, frame[is_total].reset_index(drop=True)


def _check_source_total(data: DashboardData, source_total: pd.DataFrame) -> None:
    """원본의 '전체' 합계가 지점 합계와 맞는지 확인한다.

    맞으면 화면은 지점 합계로 계산한다. 다르면 어느 쪽이 맞는지 사람이
    판단해야 하므로 차이를 알리고 멈춘다.
    """
    if source_total.empty:
        return
    computed = data.monthly.groupby("base_month", observed=True)[
        ["customer_count", "total_assets"]
    ].sum()
    given = source_total.set_index("base_month")[["customer_count", "total_assets"]]
    for month in given.index:
        if month not in computed.index:
            continue
        for column in ("customer_count", "total_assets"):
            expected, actual = int(computed.loc[month, column]), int(given.loc[month, column])
            if expected != actual:
                raise ValueError(
                    f"원본의 '{TOTAL_LABEL}' 행과 지점 합계가 다릅니다. "
                    f"{month} {column} — 지점 합계 {expected:,} vs 전체 행 {actual:,}. "
                    "어느 쪽이 맞는지 확인한 뒤 원본을 맞춰 주세요."
                )


def _normalize_frame(frame: pd.DataFrame, name: str) -> pd.DataFrame:
    columns = FRAME_COLUMNS[name]
    missing = [column for column in columns if column not in frame.columns]
    if missing:
        raise ValueError(
            f"{name} 데이터에 필수 컬럼이 없습니다: {', '.join(missing)}. "
            f"필요한 컬럼: {', '.join(columns)}"
        )
    normalized = frame.loc[:, list(columns)].copy()
    normalized["base_month"] = _to_month_column(normalized["base_month"], name)
    normalized["branch_id"] = _to_text_column(normalized["branch_id"], name, "branch_id")
    normalized["branch_name"] = _to_text_column(normalized["branch_name"], name, "branch_name")
    for column in columns:
        if column.endswith("count") or column == "total_assets":
            normalized[column] = _to_int_column(normalized[column], name, column)
        elif column == "average_age":
            normalized[column] = _to_float_column(normalized[column], name, column)
    return normalized.sort_values(_SORT_KEY).reset_index(drop=True)


def _samples(values: pd.Series, mask: pd.Series, limit: int = 3) -> str:
    """오류 메시지에 넣을 실제 값 예시. 원인을 바로 찾을 수 있게 한다."""
    return ", ".join(repr(value) for value in values[mask].head(limit).tolist())


def _plain_text(series: pd.Series) -> pd.Series:
    """숫자로 들어온 값도 사람이 쓰는 표기로 바꾼다.

    원본이 숫자면 pandas가 `202601.0`, `1.0` 같은 소수점 표기를 만든다.
    그대로 두면 월 형식 검사와 지점 코드 대조가 어긋난다.
    """
    return series.astype(str).str.strip().str.replace(r"\.0+$", "", regex=True)


def _to_month_column(series: pd.Series, name: str) -> pd.Series:
    """기준 월을 `YYYY-MM` 문자열로 맞춘다.

    원본이 숫자 `202601`이든 문자열 `2026-01`이든 날짜 `2026-01-31`이든 읽는다.
    """
    text = _plain_text(series)
    compact = text.str.fullmatch(r"\d{6}")
    text = text.mask(compact, text.str.slice(0, 4) + "-" + text.str.slice(4, 6))
    text = text.str.slice(0, 7)
    invalid = ~text.str.fullmatch(_MONTH_PATTERN)
    if invalid.any():
        raise ValueError(
            f"{name}.base_month 를 YYYY-MM으로 읽을 수 없는 값이 {int(invalid.sum())}건 "
            f"있습니다. 예: {_samples(series, invalid)}. "
            "허용되는 형태: 202601, '2026-01', '2026-01-31'"
        )
    return text


def _to_text_column(series: pd.Series, name: str, column: str) -> pd.Series:
    """지점 코드·지점명처럼 이름표로 쓰는 값. 숫자 코드도 문자열로 맞춘다."""
    text = _plain_text(series)
    blank = text.isin(("", "nan", "None", "NaT"))
    if blank.any():
        raise ValueError(
            f"{name}.{column} 이 비어 있는 행이 {int(blank.sum())}건 있습니다."
        )
    return text


def _to_numeric_column(series: pd.Series, name: str, column: str) -> pd.Series:
    """숫자로 바꾼다. 빈 칸이나 읽을 수 없는 값을 0으로 덮지 않고 멈춘다."""
    numbers = pd.to_numeric(series, errors="coerce")
    unreadable = numbers.isna()
    if unreadable.any():
        raise ValueError(
            f"{name}.{column} 에 숫자로 읽을 수 없는 값이 {int(unreadable.sum())}건 있습니다. "
            f"예: {_samples(series, unreadable)}. "
            "0으로 처리해야 한다면 원본 데이터에서 직접 0을 채워 주세요."
        )
    return numbers


def _to_int_column(series: pd.Series, name: str, column: str) -> pd.Series:
    numbers = _to_numeric_column(series, name, column)
    negative = numbers < 0
    if negative.any():
        raise ValueError(
            f"{name}.{column} 에 음수가 {int(negative.sum())}건 있습니다. "
            f"예: {_samples(series, negative)}"
        )
    return numbers.round().astype(int)


def _to_float_column(series: pd.Series, name: str, column: str) -> pd.Series:
    return _to_numeric_column(series, name, column).astype(float)


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
    values = _plain_text(series)
    if codes:
        values = values.map(lambda value: codes.get(value, value))
    unknown = sorted(set(values) - set(categories))
    if unknown:
        hint = (
            ""
            if codes
            else f" 원본이 숫자 코드라면 data.py의 코드표에 코드→이름을 적어 주세요."
        )
        raise ValueError(
            f"{name}.{column} 에 정의되지 않은 값이 있습니다: {', '.join(unknown)}. "
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
            f"{name}.{column} 을 참·거짓으로 읽을 수 없는 값이 {int(unknown.sum())}건 "
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
    """더미 데이터와 실제 데이터가 같은 기준을 통과하도록 검증한다.

    기본 검사는 데이터가 스스로 앞뒤가 맞는지만 본다. 기간이 몇 개월인지,
    지점이 몇 개인지는 실제 데이터에서 얼마든지 달라질 수 있으므로 묻지 않는다.
    `expected_months`·`expected_branch_count`를 주면 그 값까지 확인하는데,
    이는 생성기가 만든 더미 데이터를 점검할 때만 쓴다.
    """
    for field in fields(DashboardData):
        frame = getattr(data, field.name)
        if not isinstance(frame, pd.DataFrame):
            raise ValueError(f"{field.name}이 DataFrame이 아닙니다.")
        if frame.empty:
            raise ValueError(f"{field.name} 데이터가 비어 있습니다.")
        if frame.isna().to_numpy().any():
            raise ValueError(f"{field.name}에 누락값이 있습니다.")

    frames = tuple((name, getattr(data, name)) for name in FRAME_NAMES)
    months = sorted(data.monthly["base_month"].unique())
    branch_ids = set(data.monthly["branch_id"].unique())

    # 4개 데이터가 서로 같은 기간·같은 지점을 담고 있어야 한다.
    for name, frame in frames:
        if sorted(frame["base_month"].unique()) != months:
            raise ValueError(
                f"{name}의 기준 월이 monthly와 다릅니다. "
                f"monthly: {months[0]} ~ {months[-1]} ({len(months)}개월)"
            )
        if set(frame["branch_id"].unique()) != branch_ids:
            raise ValueError(
                f"{name}의 지점이 monthly와 다릅니다. monthly 지점 수: {len(branch_ids)}"
            )
    if not _is_one_to_one(data.monthly, "branch_id", "branch_name"):
        raise ValueError("branch_id와 branch_name이 1:1로 대응하지 않습니다.")

    if expected_months is not None and tuple(months) != tuple(expected_months):
        raise ValueError(f"기준 월이 예상 범위와 다릅니다: {months[0]} ~ {months[-1]}")
    if expected_branch_count is not None and len(branch_ids) != expected_branch_count:
        raise ValueError(
            f"지점 수가 {expected_branch_count}개가 아닙니다: {len(branch_ids)}"
        )

    monthly = data.monthly
    for column in ("transaction_customer_count", "app_user_count"):
        _check_not_greater(monthly, column, "customer_count", "monthly")

    key = ["base_month", "branch_id"]
    base = monthly.set_index(key)["customer_count"]

    age_sum = data.age.groupby(key, observed=True)["customer_count"].sum()
    _check_matches_customer_count(age_sum, base, "연령 구간별 고객 수 합계")

    invest_sum = data.investment.groupby(key, observed=True)["customer_count"].sum()
    _check_matches_customer_count(invest_sum, base, "투자성향별 고객 수 합계")

    summary = data.summary.set_index(key)
    _check_matches_customer_count(summary["customer_count"], base, "요약 데이터의 고객 수")
    for column in (
        "male_customer_count",
        "recent_signup_customer_count",
        "recommendation_consent_customer_count",
        "grade_s_or_higher_customer_count",
    ):
        _check_not_greater(summary, column, "customer_count", "summary")
    outside = ~summary["average_age"].between(0, 120)
    if outside.any():
        raise ValueError(
            f"summary.average_age가 0~120 범위를 벗어난 행이 {int(outside.sum())}건 있습니다. "
            f"예: {_samples(summary['average_age'], outside)}"
        )


def _is_one_to_one(frame: pd.DataFrame, left: str, right: str) -> bool:
    pairs = frame.loc[:, [left, right]].drop_duplicates()
    return bool(pairs[left].is_unique and pairs[right].is_unique)


def _check_not_greater(frame: pd.DataFrame, column: str, limit: str, name: str) -> None:
    over = frame[column] > frame[limit]
    if over.any():
        row = frame[over].iloc[0]
        raise ValueError(
            f"{name}.{column}이 {limit}보다 큰 행이 {int(over.sum())}건 있습니다. "
            f"예: {row[column]} > {row[limit]}"
        )


def _check_matches_customer_count(actual: pd.Series, base: pd.Series, label: str) -> None:
    """합계가 고객 수와 다르면 어느 월·지점이 얼마나 어긋났는지 알려준다."""
    aligned = actual.reindex(base.index)
    mismatch = ~aligned.eq(base)
    if not mismatch.any():
        return
    month, branch_id = base.index[mismatch][0]
    raise ValueError(
        f"{label}가 고객 수와 다른 행이 {int(mismatch.sum())}건 있습니다. "
        f"예: {month} {branch_id} — 합계 {aligned[mismatch].iloc[0]} vs 고객 수 {base[mismatch].iloc[0]}"
    )


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
