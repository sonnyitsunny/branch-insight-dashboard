"""집계·계산 검증. 전체 기준 값이 단순 평균이 아닌지 확인한다."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from dashboard import metrics
from dashboard.data import (
    AGE_GROUPS,
    BRANCH_COUNT,
    CONSENT_LABEL,
    CURRENT_MONTH,
    INVESTMENT_TYPES,
    MONTH_COUNT,
    PREVIOUS_MONTH,
    TOTAL_LABEL,
    YOY_BASE_MONTH,
    load_dashboard_data,
)


@pytest.fixture(scope="module")
def dataset():
    return load_dashboard_data()


# --- 기본 계산 ---------------------------------------------------------------
def test_safe_ratio_handles_zero_and_missing():
    assert metrics.safe_ratio(1, 0) is None
    assert metrics.safe_ratio(None, 10) is None
    assert metrics.safe_ratio(np.nan, 10) is None
    assert metrics.safe_ratio(5, 10) == 0.5


def test_yoy_and_delta():
    assert metrics.yoy_rate(111, 100) == pytest.approx(11.0)
    assert metrics.yoy_rate(100, 0) is None
    assert metrics.diff_abs(110, 100) == 10
    assert metrics.diff_pp(43.0, 43.8) == pytest.approx(-0.8)


def test_weighted_mean_uses_weights():
    assert metrics.weighted_mean([10, 20], [1, 3]) == pytest.approx(17.5)
    assert metrics.weighted_mean([10, 20], [0, 0]) is None
    assert metrics.weighted_mean([], []) is None


def test_empty_frames_do_not_raise():
    empty = pd.DataFrame()
    assert metrics.monthly_totals(empty).empty
    assert metrics.customer_trend(empty, "지점 01").empty
    assert metrics.growth_scatter(empty).empty
    assert metrics.age_distribution(empty, "지점 01").empty
    assert metrics.investment_breakdown(empty).empty
    total_row, branch_rows = metrics.branch_table(empty, empty)
    assert total_row == {}
    assert branch_rows.empty


# --- 전체 집계 ---------------------------------------------------------------
def test_monthly_totals_match_branch_sums(dataset):
    totals = metrics.monthly_totals(dataset.monthly)
    assert len(totals) == MONTH_COUNT
    current = totals[totals["base_month"] == CURRENT_MONTH].iloc[0]
    branch_current = dataset.monthly[dataset.monthly["base_month"] == CURRENT_MONTH]
    assert current["customer_count"] == branch_current["customer_count"].sum()
    assert current["total_assets"] == branch_current["total_assets"].sum()


def test_total_share_is_not_simple_average(dataset):
    """전체 비중은 지점 비율의 평균이 아니라 분자·분모 합산이어야 한다."""
    current = dataset.monthly[dataset.monthly["base_month"] == CURRENT_MONTH]
    pooled = 100.0 * current["transaction_customer_count"].sum() / current["customer_count"].sum()
    simple_average = (100.0 * current["transaction_customer_count"] / current["customer_count"]).mean()
    totals = metrics.monthly_totals(dataset.monthly)
    computed = totals[totals["base_month"] == CURRENT_MONTH].iloc[0]["transaction_share"]
    assert computed == pytest.approx(pooled)
    assert computed != pytest.approx(simple_average)


def test_kpi_metrics_compare_current_and_previous_month(dataset):
    kpis = metrics.kpi_metrics(dataset.monthly)
    totals = metrics.monthly_totals(dataset.monthly).set_index("base_month")
    expected_delta = (
        totals.loc[CURRENT_MONTH, "customer_count"] - totals.loc[PREVIOUS_MONTH, "customer_count"]
    )
    assert kpis["customer_count"]["value"] == totals.loc[CURRENT_MONTH, "customer_count"]
    assert kpis["customer_count"]["delta"] == expected_delta
    assert set(kpis) == {"customer_count", "total_assets", "transaction_share", "app_share"}


def test_kpi_metrics_handle_missing_month(dataset):
    kpis = metrics.kpi_metrics(dataset.monthly, current_month="2030-01", previous_month="2029-12")
    assert kpis["customer_count"]["value"] is None
    assert kpis["app_share"]["delta"] is None


# --- 차트 데이터 -------------------------------------------------------------
def test_customer_trend_shape_and_yoy(dataset):
    trend = metrics.customer_trend(dataset.monthly, "지점 01")
    assert len(trend) == MONTH_COUNT
    # 전년 동월 데이터가 없는 12개월은 값이 비어 있고 마지막 달만 계산된다.
    assert trend["branch_yoy"].iloc[:-1].isna().all(), "전년 동월이 없으면 YoY를 만들지 않는다"
    assert pd.notna(trend["branch_yoy"].iloc[-1])
    first = trend["branch_count"].iloc[0]
    last = trend["branch_count"].iloc[-1]
    assert trend["branch_yoy"].iloc[-1] == pytest.approx((last / first - 1) * 100)


def test_customer_trend_for_unknown_branch_keeps_totals(dataset):
    trend = metrics.customer_trend(dataset.monthly, "지점 99")
    assert len(trend) == MONTH_COUNT
    assert trend["branch_count"].isna().all()


def test_growth_scatter_has_27_points(dataset):
    scatter = metrics.growth_scatter(dataset.monthly)
    assert len(scatter) == BRANCH_COUNT
    assert scatter["yoy"].notna().all()
    row = scatter.iloc[0]
    assert row["yoy"] == pytest.approx((row["current_count"] / row["base_count"] - 1) * 100)


def test_growth_scatter_uses_july_2025_as_base(dataset):
    scatter = metrics.growth_scatter(dataset.monthly)
    base = dataset.monthly[dataset.monthly["base_month"] == YOY_BASE_MONTH].set_index("branch_name")
    merged = scatter.set_index("branch_name")
    expected = base["customer_count"].reindex(merged.index)
    assert merged["base_count"].astype(float).equals(expected.astype(float))


def test_median_line_matches_median(dataset):
    scatter = metrics.growth_scatter(dataset.monthly)
    assert metrics.median_customer_count(scatter) == pytest.approx(scatter["current_count"].median())


def test_age_distribution_shares_sum_to_100(dataset):
    distribution = metrics.age_distribution(dataset.age, "지점 03")
    assert set(distribution["scope"]) == {TOTAL_LABEL, "지점 03"}
    for scope, group in distribution.groupby("scope", observed=True):
        assert list(group["age_group"]) == list(AGE_GROUPS)
        assert group["share"].sum() == pytest.approx(100.0)


def test_age_total_is_pooled_not_averaged(dataset):
    distribution = metrics.age_distribution(dataset.age, "지점 03")
    total_rows = distribution[distribution["scope"] == TOTAL_LABEL].set_index("age_group")
    month_age = dataset.age[dataset.age["base_month"] == CURRENT_MONTH]
    pooled = month_age.groupby("age_group", observed=True)["customer_count"].sum()
    assert total_rows["customer_count"].equals(pooled.astype(int).reindex(total_rows.index))


def test_investment_breakdown_is_100_percent_per_type(dataset):
    breakdown = metrics.investment_breakdown(dataset.investment)
    assert list(breakdown["investment_type"].unique()) == list(INVESTMENT_TYPES)
    for investment_type, group in breakdown.groupby("investment_type", observed=True):
        assert group["share"].sum() == pytest.approx(100.0)
        assert group["customer_count"].sum() == group["type_total"].iloc[0]


def test_investment_total_equals_sum_of_branches(dataset):
    total = metrics.investment_breakdown(dataset.investment, TOTAL_LABEL)
    consent_total = total[total["consent_label"] == CONSENT_LABEL]["customer_count"].sum()
    month_data = dataset.investment[
        (dataset.investment["base_month"] == CURRENT_MONTH)
        & (dataset.investment["marketing_consent"])
    ]
    assert consent_total == month_data["customer_count"].sum()


def test_investment_for_single_branch(dataset):
    branch = metrics.investment_breakdown(dataset.investment, "지점 05")
    total_customers = branch["type_total"].drop_duplicates().sum()
    expected = dataset.monthly[
        (dataset.monthly["base_month"] == CURRENT_MONTH)
        & (dataset.monthly["branch_name"] == "지점 05")
    ]["customer_count"].iloc[0]
    assert total_customers == expected


# --- 테이블 -----------------------------------------------------------------
def test_branch_table_has_total_and_27_rows(dataset):
    total_row, branch_rows = metrics.branch_table(dataset.monthly, dataset.summary)
    assert len(branch_rows) == BRANCH_COUNT
    assert total_row["branch_name"] == TOTAL_LABEL
    assert total_row["customer_count"] == branch_rows["customer_count"].sum()


def test_total_row_growth_compares_totals(dataset):
    total_row, _ = metrics.branch_table(dataset.monthly, dataset.summary)
    totals = metrics.monthly_totals(dataset.monthly).set_index("base_month")["customer_count"]
    expected = (totals.loc[CURRENT_MONTH] / totals.loc[YOY_BASE_MONTH] - 1) * 100
    assert total_row["customer_growth_yoy"] == pytest.approx(expected)


def test_total_row_average_age_is_weighted(dataset):
    total_row, _ = metrics.branch_table(dataset.monthly, dataset.summary)
    current = dataset.summary[dataset.summary["base_month"] == CURRENT_MONTH]
    weighted = np.average(current["average_age"], weights=current["customer_count"])
    assert total_row["average_age"] == pytest.approx(weighted)
    assert total_row["average_age"] != pytest.approx(current["average_age"].mean())


def test_table_shares_are_within_range(dataset):
    _, branch_rows = metrics.branch_table(dataset.monthly, dataset.summary)
    for column in ("male_share", "recent_signup_share", "recommendation_share", "grade_s_share"):
        assert branch_rows[column].between(0, 100).all()
