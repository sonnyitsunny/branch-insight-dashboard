"""집계·계산 검증. 전체 기준 값이 단순 평균이 아닌지 확인한다."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from dashboard import metrics as shared
from dashboard.tabs.customer import metrics
from dashboard.data import (
    AGE_GROUPS,
    CONSENT_LABEL,
    INVESTMENT_TYPES,
    TOTAL_LABEL,
    load_dashboard_data,
)
from fixture_data import (
    BRANCH_COUNT,
    CURRENT_MONTH,
    MONTH_COUNT,
    PREVIOUS_MONTH,
    YOY_BASE_MONTH,
)


@pytest.fixture(scope="module")
def dataset():
    return load_dashboard_data()


# --- 기본 계산 ---------------------------------------------------------------
def test_safe_ratio_handles_zero_and_missing():
    assert shared.safe_ratio(1, 0) is None
    assert shared.safe_ratio(None, 10) is None
    assert shared.safe_ratio(np.nan, 10) is None
    assert shared.safe_ratio(5, 10) == 0.5


def test_yoy_and_delta():
    assert shared.yoy_rate(111, 100) == pytest.approx(11.0)
    assert shared.yoy_rate(100, 0) is None
    assert shared.diff_abs(110, 100) == 10
    assert shared.diff_pp(43.0, 43.8) == pytest.approx(-0.8)


def test_weighted_mean_uses_weights():
    assert shared.weighted_mean([10, 20], [1, 3]) == pytest.approx(17.5)
    assert shared.weighted_mean([10, 20], [0, 0]) is None
    assert shared.weighted_mean([], []) is None


def test_empty_frames_do_not_raise():
    empty = pd.DataFrame()
    assert shared.monthly_totals(empty).empty
    assert metrics.customer_trend(empty, "지점 01").empty
    assert metrics.growth_scatter(empty).empty
    assert metrics.age_distribution(empty, "지점 01").empty
    assert metrics.investment_breakdown(empty).empty
    total_row, branch_rows = metrics.branch_table(empty, empty)
    assert total_row == {}
    assert branch_rows.empty


def _monthly_with_all_measures() -> pd.DataFrame:
    """총자산·거래·앱 값까지 들어 있는 월별 데이터.

    표본 파일에는 이 세 가지가 없다. 원본에 없기 때문이다. 합산과 비중 계산
    규칙은 그 데이터가 생긴 뒤에도 그대로여야 하므로 여기서 직접 만들어 확인한다.
    """
    branches = [
        # (고객 수, 총자산, 거래고객 수, 앱 이용자 수)
        (1000, 2800, 700, 900),
        (100, 260, 20, 30),
    ]
    rows = [
        {
            "base_month": month,
            "branch_id": f"{index:04d}",
            "branch_name": f"지점 {index:02d}",
            "customer_count": count,
            "total_assets": assets,
            "transaction_customer_count": trades,
            "app_user_count": app_users,
        }
        for month in (PREVIOUS_MONTH, CURRENT_MONTH)
        for index, (count, assets, trades, app_users) in enumerate(branches)
    ]
    return pd.DataFrame(rows)


# --- 전체 집계 ---------------------------------------------------------------
def test_monthly_totals_match_branch_sums(dataset):
    totals = shared.monthly_totals(dataset.monthly)
    assert len(totals) == MONTH_COUNT
    current = totals[totals["base_month"] == CURRENT_MONTH].iloc[0]
    branch_current = dataset.monthly[dataset.monthly["base_month"] == CURRENT_MONTH]
    assert current["customer_count"] == branch_current["customer_count"].sum()


def test_measures_missing_from_the_source_stay_empty(dataset):
    """원본에 없는 값은 0으로 합산되지 않고 빈 값으로 남는다.

    0으로 채우면 "데이터 없음"이 "0원"이라는 숫자로 화면에 뜬다(회귀 방지).

    거래고객수는 거래1이 담고 있어 여기서 빠진다. 그 값이 어떻게 붙는지는
    tests/test_source_adapter.py 가 확인한다.
    """
    totals = shared.monthly_totals(dataset.monthly)
    for column in ("total_assets", "app_user_count"):
        assert totals[column].isna().all(), column
    assert totals["app_share"].isna().all()


def test_total_share_is_not_simple_average():
    """전체 비중은 지점 비율의 평균이 아니라 분자·분모 합산이어야 한다."""
    monthly = _monthly_with_all_measures()
    current = monthly[monthly["base_month"] == CURRENT_MONTH]
    pooled = 100.0 * current["transaction_customer_count"].sum() / current["customer_count"].sum()
    simple_average = (
        100.0 * current["transaction_customer_count"] / current["customer_count"]
    ).mean()
    totals = shared.monthly_totals(monthly)
    computed = totals[totals["base_month"] == CURRENT_MONTH].iloc[0]["transaction_share"]
    assert computed == pytest.approx(pooled)
    assert computed != pytest.approx(simple_average)


def test_totals_sum_measures_across_branches():
    monthly = _monthly_with_all_measures()
    totals = shared.monthly_totals(monthly)
    current = totals[totals["base_month"] == CURRENT_MONTH].iloc[0]
    assert current["customer_count"] == 1100
    assert current["total_assets"] == 3060


def test_kpi_metrics_compare_current_and_previous_month(dataset):
    kpis = shared.kpi_metrics(dataset.monthly)
    totals = shared.monthly_totals(dataset.monthly).set_index("base_month")
    expected_delta = (
        totals.loc[CURRENT_MONTH, "customer_count"] - totals.loc[PREVIOUS_MONTH, "customer_count"]
    )
    assert kpis["customer_count"]["value"] == totals.loc[CURRENT_MONTH, "customer_count"]
    assert kpis["customer_count"]["delta"] == expected_delta
    assert set(kpis) == {"customer_count", "net_assets", "transaction_share", "app_share"}


def test_kpi_metrics_handle_missing_month(dataset):
    kpis = shared.kpi_metrics(dataset.monthly, current_month="2030-01", previous_month="2029-12")
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


def test_customer_trend_yoy_uses_month_labels_not_row_offset():
    """중간에 빠진 월이 있어도 12개월 전과 비교한다.

    행 번호로 12칸을 세면 결측 월이 있을 때 엉뚱한 달과 비교하면서도
    오류 없이 그럴듯한 숫자를 내놓는다(회귀 방지).
    """
    months = [f"2025-{m:02d}" for m in range(6, 13)] + [f"2026-{m:02d}" for m in range(1, 8)]
    counts = {month: 1000 + index * 100 for index, month in enumerate(months)}
    rows = [
        {
            "base_month": month,
            "branch_name": "지점 01",
            "customer_count": counts[month],
            "total_assets": 0,
            "transaction_customer_count": 0,
            "app_user_count": 0,
        }
        for month in months
    ]
    with_gap = pd.DataFrame([row for row in rows if row["base_month"] != "2025-10"])

    trend = metrics.customer_trend(with_gap, "지점 01")
    last = trend.iloc[-1]
    assert last["base_month"] == "2026-07"
    # 2025-07(1100) 대비여야 한다. 행 번호로 세면 2025-06(1000) 대비 130%가 나온다.
    assert last["branch_yoy"] == pytest.approx((counts["2026-07"] / counts["2025-07"] - 1) * 100)


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


def test_metrics_follow_a_shorter_data_range(dataset):
    """데이터 기간이 달라지면 기준 월도 따라간다. 상수를 고치지 않아도 된다."""
    months = [month for month in dataset.months if month <= "2026-03"]
    trimmed = load_dashboard_data(filters={"base_months": months})

    kpis = shared.kpi_metrics(trimmed.monthly)
    expected = trimmed.monthly[trimmed.monthly["base_month"] == "2026-03"]["customer_count"].sum()
    assert kpis["customer_count"]["value"] == pytest.approx(float(expected))

    # 2026-03의 12개월 전(2025-03)은 데이터에 없다.
    # 이럴 때 아무 달이나 끌어다 쓰지 않고 값을 비워야 한다.
    scatter = metrics.growth_scatter(trimmed.monthly)
    assert len(scatter) == BRANCH_COUNT
    assert scatter["current_count"].notna().all()
    assert scatter["yoy"].isna().all(), "전년 동월이 없으면 YoY를 만들지 않는다"


def test_growth_is_computed_from_monthly_when_the_source_omits_it():
    """원본이 증가율을 주지 않으면 monthly의 두 시점에서 계산한다.

    전년 동월 데이터까지 없으면 아무 달이나 끌어다 쓰지 않고 값을 비운다.
    """
    monthly = _monthly_with_all_measures()
    summary = pd.DataFrame(
        [
            {
                "base_month": CURRENT_MONTH,
                "branch_id": "0000",
                "branch_name": "지점 00",
                "customer_count": 1000,
                "average_age": 44.0,
                "male_share": 50.0,
                "recent_signup_share": 20.0,
                "recommendation_share": 40.0,
                "grade_s_share": 25.0,
            }
        ]
    )
    _, rows = metrics.branch_table(monthly, summary)
    assert rows["customer_growth_yoy"].isna().all(), "12개월 전이 없으면 비운다"

    _, rows = metrics.branch_table(monthly, summary, base_month=PREVIOUS_MONTH)
    assert rows.iloc[0]["customer_growth_yoy"] == pytest.approx(0.0)


def test_median_line_splits_branches_in_half(dataset):
    """세로 기준선은 '많음/적음'을 가르는 분할선이라 중앙값을 쓴다.

    평균을 쓰면 큰 지점 몇 곳에 끌려가 지점 대부분이 '적음' 쪽에 몰리고
    사분면 문구가 사실과 달라진다(회귀 방지).
    """
    scatter = metrics.growth_scatter(dataset.monthly)
    counts = scatter["current_count"]
    line = metrics.median_customer_count(scatter)
    assert line == pytest.approx(counts.median())
    assert abs(int((counts < line).sum()) - int((counts >= line).sum())) <= 1
    assert metrics.median_customer_count(pd.DataFrame()) is None


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
    """분류별 합계가 그 지점의 실제 인원과 맞는지 확인한다.

    화면에서 빼는 분류가 있으므로 고객 수보다 적을 수 있다. 합계는 그 지점의
    투자성향 데이터에 실제로 들어 있는 인원과 같아야 한다.
    """
    branch = metrics.investment_breakdown(dataset.investment, "지점 05")
    total_customers = branch["type_total"].drop_duplicates().sum()
    rows = dataset.investment[
        (dataset.investment["base_month"] == CURRENT_MONTH)
        & (dataset.investment["branch_name"] == "지점 05")
    ]
    assert total_customers == rows["customer_count"].sum()

    customers = dataset.monthly[
        (dataset.monthly["base_month"] == CURRENT_MONTH)
        & (dataset.monthly["branch_name"] == "지점 05")
    ]["customer_count"].iloc[0]
    assert total_customers <= customers


# --- 테이블 -----------------------------------------------------------------
def test_branch_table_has_total_and_27_rows(dataset):
    total_row, branch_rows = metrics.branch_table(dataset.monthly, dataset.summary)
    assert len(branch_rows) == BRANCH_COUNT
    assert total_row["branch_name"] == TOTAL_LABEL
    assert total_row["customer_count"] == branch_rows["customer_count"].sum()


def test_total_row_growth_compares_totals(dataset):
    total_row, _ = metrics.branch_table(dataset.monthly, dataset.summary)
    totals = shared.monthly_totals(dataset.monthly).set_index("base_month")["customer_count"]
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
