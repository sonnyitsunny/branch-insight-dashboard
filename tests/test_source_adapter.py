"""실제 원본 pkl 두 개를 표준 형태로 읽는 어댑터 검증.

원본 형태 — 파일 1은 월별 공통고객 수, 파일 2는 지점별 프로필 한 시점.
여기서 만드는 표본은 실제 컬럼 이름만 흉내 내며 개인정보를 담지 않는다.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from dashboard import metrics
from dashboard.data import (
    AGE_GROUPS,
    ALL_AGE_GROUPS,
    INVESTMENT_TYPES,
    PROFILE_AGE_COLUMNS,
    EXCLUDED_INVESTMENT_TYPES,
    load_dashboard_data,
)

MONTHS = ["202511", "202512", "202601"]
BRANCHES = [("0001", "지점 01"), ("0002", "지점 02")]
TOTAL_BRANCH = ("0000", "전체")
# 원본 파일의 연령 구간 컬럼 이름. 표준 이름과 달라 매핑표를 거친다.
SOURCE_AGE = list(PROFILE_AGE_COLUMNS)
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


def _profile_frame() -> pd.DataFrame:
    rows = []
    total_start = total_end = 0
    for branch_index, (code, name) in enumerate(BRANCHES):
        start, end = _counts(branch_index, 0), _counts(branch_index, len(MONTHS) - 1)
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


@pytest.fixture
def source_files(tmp_path, monkeypatch):
    """두 원본 파일을 만들고 환경 변수를 걸어 주는 헬퍼를 반환한다."""

    def _write(monthly: pd.DataFrame | None = None, profile: pd.DataFrame | None = None):
        monthly_path = tmp_path / "monthly.pkl"
        profile_path = tmp_path / "profile.pkl"
        (monthly if monthly is not None else _monthly_frame()).to_pickle(monthly_path)
        (profile if profile is not None else _profile_frame()).to_pickle(profile_path)
        monkeypatch.setenv("DASHBOARD_DATA_SOURCE", "local_file")
        monkeypatch.setenv("DASHBOARD_DATA_FILE", str(monthly_path))
        monkeypatch.setenv("DASHBOARD_PROFILE_FILE", str(profile_path))
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
    """원본에 없는 총자산·거래·앱 값은 0이 아니라 빈 값으로 남는다."""
    data = source_files()()
    assert data.monthly["total_assets"].isna().all()
    kpis = metrics.kpi_metrics(data.monthly)
    assert kpis["customer_count"]["value"] is not None
    for key in ("total_assets", "transaction_share", "app_share"):
        assert kpis[key]["value"] is None, key


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
    profile = _profile_frame()
    profile.loc[0, "고객수_종료월"] = int(profile.loc[0, "고객수_종료월"]) + 5
    with pytest.raises(ValueError, match="두 파일의 고객 수가 다릅니다"):
        source_files(profile=profile)()


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
