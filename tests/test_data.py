"""더미 데이터의 계약과 정합성 검증."""

from __future__ import annotations

import pandas as pd
import pytest

from dashboard import data as data_module
from dashboard.data import (
    AGE_GROUPS,
    BRANCH_COUNT,
    CURRENT_MONTH,
    END_MONTH,
    INVESTMENT_TYPES,
    MONTH_COUNT,
    PREVIOUS_MONTH,
    START_MONTH,
    YOY_BASE_MONTH,
    YOY_MONTHS,
    load_dashboard_data,
    month_range,
    reference_month,
    shift_month,
    validate_dashboard_data,
)


@pytest.fixture(scope="module")
def dataset():
    return load_dashboard_data()


def test_month_range_covers_13_months():
    months = month_range()
    assert len(months) == MONTH_COUNT
    assert months[0] == "2025-07"
    assert months[-1] == "2026-07"


# --- 기준 월 계산 -------------------------------------------------------------
def test_shift_month_crosses_year_boundary():
    assert shift_month("2026-07", -1) == "2026-06"
    assert shift_month("2026-01", -1) == "2025-12"
    assert shift_month("2026-01", -YOY_MONTHS) == "2025-01"
    assert shift_month("2025-12", 2) == "2026-02"


def test_reference_months_are_derived_not_hardcoded():
    """기준 월 3개는 서로 손으로 맞추지 않는다.

    예전에는 YOY_BASE_MONTH가 START_MONTH와 같았는데, 이는 MONTH_COUNT가
    13이라 우연히 12개월 전과 일치했을 뿐이다. 기간을 늘리면 YoY라고
    표시하면서 2년 증가율을 계산하게 된다.
    """
    assert END_MONTH == shift_month(START_MONTH, MONTH_COUNT - 1)
    assert PREVIOUS_MONTH == shift_month(CURRENT_MONTH, -1)
    assert YOY_BASE_MONTH == shift_month(CURRENT_MONTH, -YOY_MONTHS)


def test_reference_month_follows_the_data(dataset):
    """기준 월은 상수가 아니라 데이터의 최신 월을 따라간다."""
    assert reference_month(dataset) == dataset.months[-1]

    trimmed = load_dashboard_data(
        filters={"base_months": [m for m in dataset.months if m <= "2026-03"]}
    )
    assert reference_month(trimmed) == "2026-03"


def test_reference_month_can_be_fixed_by_env(dataset, monkeypatch):
    monkeypatch.setenv(data_module.BASE_MONTH_ENV, "2026-01")
    assert reference_month(dataset) == "2026-01"


def test_reference_month_rejects_month_without_data(dataset, monkeypatch):
    """지정한 월에 데이터가 없으면 조용히 빈 화면이 되지 않고 오류를 낸다."""
    monkeypatch.setenv(data_module.BASE_MONTH_ENV, "2019-01")
    with pytest.raises(ValueError):
        reference_month(dataset)


def test_branch_count_is_27(dataset):
    assert dataset.monthly["branch_id"].nunique() == BRANCH_COUNT
    assert len(dataset.branch_names) == BRANCH_COUNT


def test_seed_is_fixed(dataset):
    again = load_dashboard_data()
    pd.testing.assert_frame_equal(dataset.monthly, again.monthly)


def test_age_and_investment_sums_match_customer_count(dataset):
    key = ["base_month", "branch_id"]
    base = dataset.monthly.set_index(key)["customer_count"]
    age_sum = dataset.age.groupby(key, observed=True)["customer_count"].sum()
    invest_sum = dataset.investment.groupby(key, observed=True)["customer_count"].sum()
    assert age_sum.reindex(base.index).equals(base)
    assert invest_sum.reindex(base.index).equals(base)


def test_sub_counts_never_exceed_customer_count(dataset):
    monthly = dataset.monthly
    assert (monthly["transaction_customer_count"] <= monthly["customer_count"]).all()
    assert (monthly["app_user_count"] <= monthly["customer_count"]).all()
    summary = dataset.summary
    for column in (
        "male_customer_count",
        "recent_signup_customer_count",
        "recommendation_consent_customer_count",
        "grade_s_or_higher_customer_count",
    ):
        assert (summary[column] <= summary["customer_count"]).all()


def test_categories_are_complete_and_ordered(dataset):
    assert list(dataset.age["age_group"].cat.categories) == list(AGE_GROUPS)
    assert list(dataset.investment["investment_type"].cat.categories) == list(INVESTMENT_TYPES)


def test_trend_has_growing_and_shrinking_branches(dataset):
    monthly = dataset.monthly
    first = monthly[monthly["base_month"] == "2025-07"].set_index("branch_name")["customer_count"]
    last = monthly[monthly["base_month"] == CURRENT_MONTH].set_index("branch_name")["customer_count"]
    change = (last - first).dropna()
    assert (change > 0).any(), "성장하는 지점이 있어야 한다"
    assert (change < 0).any(), "감소하는 지점이 있어야 한다"


def test_branch_size_spread_is_wide(dataset):
    counts = dataset.monthly[dataset.monthly["base_month"] == CURRENT_MONTH]["customer_count"]
    assert counts.max() / counts.min() > 3, "지점 규모 차이가 충분히 나타나야 한다"


def test_monthly_change_is_gradual(dataset):
    """월별 고객 수가 급격하게 튀지 않는지 확인한다."""
    monthly = dataset.monthly.sort_values(["branch_id", "base_month"])
    change = monthly.groupby("branch_id", observed=True)["customer_count"].pct_change().dropna()
    assert change.abs().max() < 0.06


def test_validation_rejects_broken_data(dataset):
    broken_age = dataset.age.copy()
    broken_age.loc[0, "customer_count"] = int(broken_age.loc[0, "customer_count"]) + 10
    broken = data_module.DashboardData(
        monthly=dataset.monthly,
        age=broken_age,
        investment=dataset.investment,
        summary=dataset.summary,
    )
    with pytest.raises(ValueError):
        validate_dashboard_data(broken)


def test_unknown_data_source_is_rejected(monkeypatch):
    monkeypatch.setenv(data_module.DATA_SOURCE_ENV, "oracle")
    with pytest.raises(ValueError):
        load_dashboard_data()


def test_filters_narrow_the_result(dataset):
    filtered = load_dashboard_data(filters={"branch_names": ["지점 01"], "base_months": [CURRENT_MONTH]})
    assert filtered.monthly["branch_name"].unique().tolist() == ["지점 01"]
    assert filtered.monthly["base_month"].unique().tolist() == [CURRENT_MONTH]
