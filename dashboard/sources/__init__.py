"""원본 파일 등록표와 조립.

원본 파일을 하나 더 반입하려면 이 폴더에 모듈을 만들고 `SOURCES`에 한 줄
더한 뒤, `assemble`에서 만든 프레임을 `DashboardData`에 넣는다. 원본마다
다른 컬럼 이름과 형태는 그 모듈 안에서만 다룬다.

바깥에서 보는 창구는 `dashboard.data.load_dashboard_data()` 하나뿐이다.
UI 계층은 이 폴더를 직접 부르지 않는다(→ AGENTS.md §9).

여러 원본을 서로 맞춰 보는 대조는 원본 하나에 속하지 않으므로 여기 둔다.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from dashboard.data import DashboardData, plain_text, to_numeric_column
from dashboard.sources import monthly, profile


@dataclass(frozen=True)
class Source:
    """원본 파일 하나의 설정.

    파일 이름·환경 변수·컬럼표는 원본 모듈에서 그때그때 읽는다. 값을 여기로
    복사해 두면 모듈 쪽을 고쳐도 반영되지 않는다.
    `required`가 거짓이면 지정하지 않아도 넘어간다.
    """

    key: str
    module: object
    required: bool = True

    @property
    def label(self) -> str:
        return self.module.LABEL

    @property
    def file(self) -> str:
        return self.module.FILE

    @property
    def env(self) -> str:
        return self.module.FILE_ENV

    @property
    def columns(self) -> dict:
        return self.module.COLUMNS


SOURCES: tuple[Source, ...] = (
    Source(key="monthly", module=monthly),
    Source(key="profile", module=profile, required=False),
)

_BY_KEY = {source.key: source for source in SOURCES}


def find(key: str) -> Source:
    return _BY_KEY[key]


def rename(
    frame: pd.DataFrame, source: Source, path: str
) -> pd.DataFrame:
    """원본 컬럼명을 표준 이름으로 바꾼다. 없는 컬럼은 이름을 알리며 멈춘다."""
    missing = [
        column for column in source.columns if column not in frame.columns
    ]
    if missing:
        raise ValueError(
            f"{source.label} 파일({path})에 다음 컬럼이 없습니다:"
            f" {', '.join(missing)}. "
            f"원본 컬럼 이름이 다르면 dashboard/sources/{source.key}.py 의"
            " 컬럼표를 고쳐 주세요. "
            f"파일에 있는 컬럼: {', '.join(map(str, frame.columns))}"
        )
    return frame.rename(columns=source.columns)


def assemble(
    monthly_raw: pd.DataFrame,
    profile_raw: pd.DataFrame,
    monthly_path: str = "월별 고객 수 파일",
    profile_path: str = "지점 프로필 파일",
) -> DashboardData:
    """원본 두 파일을 표준 4개 프레임으로 바꾼다.

    지점 프로필에는 기준 월 컬럼이 없다. 월별 파일의 마지막 월을 기준 월로
    삼고, 두 파일의 고객 수가 실제로 같은지 대조해 시점이 어긋나면 멈춘다.
    """
    monthly_frame = monthly.build(
        rename(monthly_raw, find("monthly"), monthly_path)
    )
    months = monthly.months(monthly_frame)
    profile_frame = profile.build(
        rename(profile_raw, find("profile"), profile_path), months[-1]
    )

    check_profile_against_monthly(monthly_frame, profile_frame, months)

    return DashboardData(
        monthly=monthly_frame,
        age=profile.build_age(profile_frame),
        investment=profile.build_investment(profile_frame),
        summary=profile_frame,
    )


def check_profile_against_monthly(
    monthly_frame: pd.DataFrame,
    profile_frame: pd.DataFrame,
    months: list[str],
) -> None:
    """두 파일의 고객 수가 같은 시점을 가리키는지 대조한다.

    지점 프로필에는 기준 월이 없으므로, 시작·종료 시점 고객 수가 월별
    파일의 첫 월·마지막 월과 맞는지 확인한다. 어긋나면 두 파일의 추출
    시점이 다르다는 뜻이다.
    """
    checks = [(months[-1], "customer_count", "고객수_종료월")]
    if profile.START_COUNT_COLUMN in profile_frame.columns:
        checks.append(
            (
                months[0],
                profile.START_COUNT_COLUMN,
                profile.START_COUNT_COLUMN,
            )
        )

    profile_ids = plain_text(profile_frame["branch_id"])
    monthly_ids = plain_text(monthly_frame["branch_id"])
    for month, column, label in checks:
        same_month = monthly_frame["base_month"] == month
        expected = (
            monthly_frame[same_month]
            .assign(branch_id=monthly_ids[same_month])
            .set_index("branch_id")["customer_count"]
        )
        actual = to_numeric_column(
            profile_frame[column], profile.LABEL, column
        )
        actual.index = profile_ids
        missing = sorted(set(actual.index) - set(expected.index))
        if missing:
            raise ValueError(
                f"지점 프로필에 있는 지점이 월별 파일의 {month}에 없습니다: "
                f"{', '.join(missing[:5])}"
            )
        aligned = expected.reindex(actual.index)
        mismatch = actual.round().astype("int64") != aligned.astype("int64")
        if mismatch.any():
            branch_id = actual.index[mismatch][0]
            raise ValueError(
                f"두 파일의 고객 수가 다릅니다. {month} 지점 {branch_id} — "
                f"월별 파일 {int(aligned[mismatch].iloc[0]):,} vs 프로필"
                f" '{label}' "
                f"{int(actual[mismatch].iloc[0]):,}. "
                "두 파일이 같은 시점에서 뽑혔는지 확인해 주세요."
            )


__all__ = [
    "SOURCES",
    "Source",
    "assemble",
    "check_profile_against_monthly",
    "find",
    "monthly",
    "profile",
    "rename",
]
