"""데이터 계약과 정합성 검증.

표본 파일은 `tests/data/`에 있고 실제 원본과 같은 형식이다(→ fixture_data).
"""

from __future__ import annotations

import pandas as pd
import pytest

from dashboard import data as data_module
from dashboard import sources
from dashboard.data import (
    AGE_GROUPS,
    ALL_AGE_GROUPS,
    FRAME_NAMES,
    INVESTMENT_TYPES,
    TOTAL_LABEL,
    YOY_MONTHS,
    load_dashboard_data,
    reference_month,
    shift_month,
    validate_dashboard_data,
)
from fixture_data import (
    BRANCH_COUNT,
    CURRENT_MONTH,
    END_MONTH,
    MONTH_COUNT,
    PREVIOUS_MONTH,
    START_MONTH,
    YOY_BASE_MONTH,
    month_range,
)


@pytest.fixture(scope="module")
def dataset():
    return load_dashboard_data()


def _frames(data: data_module.DashboardData) -> dict[str, pd.DataFrame]:
    """pkl에 저장하는 형태(dict)로 바꾼다."""
    return {name: getattr(data, name) for name in FRAME_NAMES}


def _normalized(data: data_module.DashboardData, **replaced: pd.DataFrame):
    """일부 프레임만 바꿔 정규화한다. 값 검사 오류를 직접 확인할 때 쓴다."""
    return data_module._normalize(data_module.DashboardData(**{**_frames(data), **replaced}))


def test_fixture_covers_13_months():
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


def test_loading_twice_gives_the_same_data(dataset):
    again = load_dashboard_data()
    pd.testing.assert_frame_equal(dataset.monthly, again.monthly)


def test_age_and_investment_sums_stay_within_customer_count(dataset):
    """연령은 고객 수와 정확히 맞고, 투자성향은 넘지 않는다.

    투자성향은 화면에서 빼는 분류가 있어 합계가 고객 수보다 적을 수 있다.
    원본 안에서 분류 합계가 맞는지는 어댑터가 확인한다(→ test_source_adapter).
    """
    key = ["base_month", "branch_id"]
    base = dataset.monthly.set_index(key)["customer_count"]
    snapshot = base[base.index.get_level_values("base_month").isin(dataset.age["base_month"])]

    age_sum = dataset.age.groupby(key, observed=True)["customer_count"].sum()
    assert age_sum.reindex(snapshot.index).equals(snapshot)

    invest_sum = dataset.investment.groupby(key, observed=True)["customer_count"].sum()
    assert (invest_sum.reindex(snapshot.index) <= snapshot).all()


def test_share_columns_stay_within_range(dataset):
    """비율 컬럼은 0~100 안에 있어야 한다. 100을 곱하지 않았거나 두 번 곱하면 벗어난다."""
    for column in data_module.SUMMARY_SHARE_COLUMNS:
        values = dataset.summary[column]
        assert values.notna().all(), column
        assert values.between(0, 100).all(), column


def test_categories_are_complete_and_ordered(dataset):
    # '기타'(연령 미선택)까지 유효한 값으로 받는다. 화면 분포에서는 빠진다.
    assert list(dataset.age["age_group"].cat.categories) == list(
        ALL_AGE_GROUPS
    )
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


# --- 실제 데이터 대비: 검증이 더미 기준을 강요하지 않는가 -----------------------
def test_validation_allows_other_periods_and_branch_counts(dataset):
    """기간과 지점 수는 실제 데이터에서 얼마든지 달라진다.

    예전에는 `month_range()`와 `BRANCH_COUNT`를 그대로 요구해서, 지점이 한 곳
    늘거나 데이터 기간이 밀리기만 해도 앱이 아예 뜨지 않았다(회귀 방지).
    """
    # 연령·투자성향·요약은 마지막 월 스냅샷만 담고 있으므로 그 월을 포함해 자른다.
    trimmed = load_dashboard_data(
        filters={
            "branch_names": dataset.branch_names[:5],
            "base_months": dataset.months[-3:],
        }
    )
    validate_dashboard_data(trimmed)


def test_validation_can_check_an_expected_range(dataset):
    """기간·지점 수를 지정하면 그것까지 확인한다. 표본 파일 점검에 쓴다."""
    with pytest.raises(ValueError):
        validate_dashboard_data(dataset, expected_branch_count=BRANCH_COUNT + 1)
    with pytest.raises(ValueError):
        validate_dashboard_data(dataset, expected_months=("2030-01",))


def test_snapshot_frames_may_cover_fewer_months(dataset):
    """연령·투자성향·요약은 특정 시점 스냅샷만 담을 수 있다.

    실제 원본은 월별 고객 수만 여러 달치이고 나머지는 최근 한 달치만 오기도 한다.
    """
    one_month = {
        name: frame[frame["base_month"] == CURRENT_MONTH]
        for name, frame in _frames(dataset).items()
        if name != "monthly"
    }
    validate_dashboard_data(
        data_module.DashboardData(monthly=dataset.monthly, **one_month)
    )


def test_frames_may_not_hold_months_missing_from_monthly(dataset):
    """monthly에 없는 월이 다른 데이터에 있으면 막는다. 기간의 기준은 monthly다."""
    stray_age = dataset.age.copy()
    stray_age["base_month"] = stray_age["base_month"].replace(CURRENT_MONTH, "2030-01")
    with pytest.raises(ValueError, match="monthly에 없는 기준 월"):
        validate_dashboard_data(
            data_module.DashboardData(**{**_frames(dataset), "age": stray_age})
        )


# --- 실제 데이터 대비: 값을 조용히 고치지 않는가 --------------------------------
@pytest.mark.parametrize(
    ("bad_value", "expected"),
    [
        (None, "숫자로 읽을 수 없는"),
        ("N/A", "숫자로 읽을 수 없는"),
        (-5, "음수"),
    ],
)
def test_unreadable_numbers_stop_instead_of_becoming_zero(dataset, bad_value, expected):
    """빈 칸을 0으로 덮으면 틀린 합계가 맞는 것처럼 화면에 뜬다(회귀 방지)."""
    broken = dataset.monthly.astype({"customer_count": object})
    broken.loc[0, "customer_count"] = bad_value
    with pytest.raises(ValueError, match=expected):
        _normalized(dataset, monthly=broken)


def test_bad_month_format_is_rejected(dataset):
    broken = dataset.monthly.copy()
    broken.loc[0, "base_month"] = "2027/01"
    with pytest.raises(ValueError, match="YYYY-MM"):
        _normalized(dataset, monthly=broken)


# --- 실제 데이터 대비: 모르는 분류값이 원인을 알려주는가 -------------------------
def test_unknown_category_names_the_offending_value(dataset):
    """모르는 값을 Categorical로 만들면 조용히 결측이 되고 원인이 숨는다."""
    broken = dataset.age.copy()
    broken["age_group"] = broken["age_group"].astype(str).replace({"20대": "20~29세"})
    with pytest.raises(ValueError, match="20~29세"):
        _normalized(dataset, age=broken)


def test_text_booleans_are_read_correctly(dataset):
    """원본이 'Y'/'N' 문자열이어도 뒤집히지 않는다.

    문자열을 bool로 그냥 바꾸면 빈 문자열이 아닌 모든 값이 참이 되어
    'N'까지 동의로 바뀐다.
    """
    source = dataset.investment.copy()
    expected = int(source["marketing_consent"].sum())
    source["marketing_consent"] = ["Y" if flag else "N" for flag in source["marketing_consent"]]
    normalized = _normalized(dataset, investment=source)
    assert int(normalized.investment["marketing_consent"].sum()) == expected


def test_unknown_boolean_text_is_rejected(dataset):
    source = dataset.investment.copy()
    source["marketing_consent"] = ["예" if flag else "아니오" for flag in source["marketing_consent"]]
    with pytest.raises(ValueError, match="참·거짓"):
        _normalized(dataset, investment=source)


# --- 실제 데이터 대비: 원본이 숫자 컬럼일 때 ------------------------------------
def test_numeric_month_and_branch_id_are_read(dataset):
    """실제 데이터는 지점명 말고 전부 숫자다. 202507도 2026-01처럼 읽어야 한다."""
    frames = {}
    for name, frame in _frames(dataset).items():
        frame = frame.copy()
        frame["base_month"] = frame["base_month"].str.replace("-", "").astype(int)
        frame["branch_id"] = frame["branch_id"].str.lstrip("B").astype(int)
        frames[name] = frame

    normalized = data_module._normalize(data_module.DashboardData(**frames))
    assert normalized.months == dataset.months
    # 숫자 코드는 문자열로 맞춘다. '1.0' 같은 소수점 표기가 남으면 안 된다.
    assert not normalized.monthly["branch_id"].str.contains(".", regex=False).any()
    assert normalized.monthly["customer_count"].sum() == dataset.monthly["customer_count"].sum()


def test_unreadable_month_names_the_value(dataset):
    broken = dataset.monthly.astype({"base_month": object})
    broken.loc[0, "base_month"] = "2027/01"
    with pytest.raises(ValueError, match="YYYY-MM"):
        _normalized(dataset, monthly=broken)


# --- 실제 데이터 대비: 원본에 '전체' 합계 행이 있을 때 --------------------------
def _with_source_total(dataset) -> dict[str, pd.DataFrame]:
    """원본처럼 '전체' 합계 행을 덧붙인 4개 프레임."""
    frames = {}
    for name, frame in _frames(dataset).items():
        keys = [
            column
            for column in ("base_month", "age_group", "investment_type", "marketing_consent")
            if column in frame.columns
        ]
        total = frame.groupby(keys, observed=True, as_index=False).sum(numeric_only=True)
        if "average_age" in frame.columns:
            total["average_age"] = frame.groupby(keys, observed=True)["average_age"].mean().values
        total["branch_id"] = "ALL"
        total["branch_name"] = TOTAL_LABEL
        frames[name] = pd.concat([frame, total], ignore_index=True)
    return frames


def test_source_total_row_is_separated_from_branches(dataset):
    """원본의 '전체' 행을 지점으로 세면 모든 숫자가 두 배가 된다(회귀 방지)."""
    normalized = data_module._normalize(data_module.DashboardData(**_with_source_total(dataset)))
    validate_dashboard_data(normalized)

    assert TOTAL_LABEL not in normalized.branch_names
    assert len(normalized.branch_names) == BRANCH_COUNT
    assert normalized.monthly["customer_count"].sum() == dataset.monthly["customer_count"].sum()


def test_source_total_that_disagrees_with_branches_is_reported(dataset):
    frames = _with_source_total(dataset)
    monthly = frames["monthly"]
    monthly.loc[monthly["branch_name"] == TOTAL_LABEL, "customer_count"] += 999
    with pytest.raises(ValueError, match="지점 합계"):
        data_module._normalize(data_module.DashboardData(**frames))


# --- 실제 데이터 대비: 동의·불원이 각각 인원수 컬럼일 때 ------------------------
def test_investment_wide_form_is_reshaped(dataset):
    """원본은 동의 여부 플래그가 아니라 동의·불원 인원수를 각각 담고 있다."""
    long_form = dataset.investment
    wide = (
        long_form.pivot_table(
            index=["base_month", "branch_id", "branch_name", "investment_type"],
            columns="marketing_consent",
            values="customer_count",
            aggfunc="sum",
            observed=True,
        )
        .reset_index()
        .rename(columns={True: "consent_customer_count", False: "non_consent_customer_count"})
    )
    wide.columns.name = None

    normalized = _normalized(dataset, investment=wide)
    pd.testing.assert_frame_equal(
        normalized.investment.sort_values(list(normalized.investment.columns)).reset_index(
            drop=True
        ),
        long_form.sort_values(list(long_form.columns)).reset_index(drop=True),
    )


def test_category_codes_translate_numeric_values(dataset, monkeypatch):
    """원본이 연령 구간을 숫자 코드로 담고 있으면 코드표로 이름을 붙인다."""
    codes = {str(index + 1): group for index, group in enumerate(AGE_GROUPS)}
    monkeypatch.setattr(data_module, "AGE_GROUP_CODES", codes)

    numeric_age = dataset.age.copy()
    reverse = {group: int(code) for code, group in codes.items()}
    numeric_age["age_group"] = numeric_age["age_group"].map(reverse).astype(int)

    normalized = _normalized(dataset, age=numeric_age)
    assert list(normalized.age["age_group"].cat.categories) == list(
        ALL_AGE_GROUPS
    )
    assert normalized.age["age_group"].isna().sum() == 0


def test_unknown_category_hints_at_the_code_table(dataset):
    broken = dataset.age.copy()
    broken["age_group"] = broken["age_group"].map({group: index for index, group in enumerate(AGE_GROUPS)})
    with pytest.raises(ValueError, match="코드표"):
        _normalized(dataset, age=broken)


# --- 실제 데이터 대비: pkl 읽기 ------------------------------------------------
def test_pickle_source_round_trip(dataset, tmp_path, monkeypatch):
    path = tmp_path / "dashboard.pkl"
    pd.to_pickle(_frames(dataset), path)
    monkeypatch.setenv(data_module.DATA_SOURCE_ENV, "local_file")
    monkeypatch.setenv(sources.monthly.FILE_ENV, str(path))
    # 표준 4개 프레임을 담은 dict 하나로 읽는 경로를 확인한다.
    monkeypatch.setenv(sources.profile.FILE_ENV, "")

    loaded = load_dashboard_data()
    pd.testing.assert_frame_equal(loaded.monthly, dataset.monthly)
    assert loaded.months == dataset.months
    assert loaded.branch_names == dataset.branch_names


def test_pickle_reload_when_the_file_changes(dataset, tmp_path, monkeypatch):
    """파일을 새로 내보내면 앱을 다시 켜지 않아도 새 내용을 읽는다."""
    path = tmp_path / "dashboard.pkl"
    pd.to_pickle(_frames(dataset), path)
    monkeypatch.setenv(data_module.DATA_SOURCE_ENV, "local_file")
    monkeypatch.setenv(sources.monthly.FILE_ENV, str(path))
    # 표준 4개 프레임을 담은 dict 하나로 읽는 경로를 확인한다.
    monkeypatch.setenv(sources.profile.FILE_ENV, "")
    assert load_dashboard_data().months == dataset.months

    trimmed = load_dashboard_data(filters={"base_months": dataset.months[-4:]})
    pd.to_pickle(_frames(trimmed), path)
    assert load_dashboard_data().months == dataset.months[-4:]


@pytest.mark.parametrize(
    ("content", "expected"),
    [
        ("dict가 아님", "dict가 아니라"),
        ({"monthly": pd.DataFrame()}, "다음 데이터가 없습니다"),
    ],
)
def test_pickle_with_wrong_shape_explains_what_is_needed(
    tmp_path, monkeypatch, content, expected
):
    path = tmp_path / "wrong.pkl"
    pd.to_pickle(content, path)
    monkeypatch.setenv(data_module.DATA_SOURCE_ENV, "local_file")
    monkeypatch.setenv(sources.monthly.FILE_ENV, str(path))
    # 표준 4개 프레임을 담은 dict 하나로 읽는 경로를 확인한다.
    monkeypatch.setenv(sources.profile.FILE_ENV, "")
    with pytest.raises(ValueError, match=expected):
        load_dashboard_data()


def test_pickle_path_must_be_given_and_exist(monkeypatch, tmp_path):
    monkeypatch.setenv(data_module.DATA_SOURCE_ENV, "local_file")
    monkeypatch.setenv(sources.monthly.FILE_ENV, "")
    with pytest.raises(ValueError, match=sources.monthly.FILE_ENV):
        load_dashboard_data()

    monkeypatch.setenv(sources.monthly.FILE_ENV, str(tmp_path / "없는파일.pkl"))
    with pytest.raises(ValueError, match="찾을 수 없습니다"):
        load_dashboard_data()


def test_unknown_data_source_is_rejected(monkeypatch):
    monkeypatch.setenv(data_module.DATA_SOURCE_ENV, "oracle")
    with pytest.raises(ValueError):
        load_dashboard_data()


def test_filters_narrow_the_result(dataset):
    filtered = load_dashboard_data(filters={"branch_names": ["지점 01"], "base_months": [CURRENT_MONTH]})
    assert filtered.monthly["branch_name"].unique().tolist() == ["지점 01"]
    assert filtered.monthly["base_month"].unique().tolist() == [CURRENT_MONTH]
