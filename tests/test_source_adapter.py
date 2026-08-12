"""실제 원본 pkl을 표준 형태로 읽는 어댑터 검증.

원본 형태 — 월별 공통고객 수, 지점별 프로필 한 시점, 월별 지점 자산(자산1),
지점별 자산 프로필 한 시점(자산2), 상품 분류별 증감율(자산3), 월별 연금
자산(자산4). 자산 파일은 없어도 되며, 없으면 자산 컬럼이 비어 있어야 한다.
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
    COUNT_TOLERANCE,
    INVESTMENT_TYPES,
    EXCLUDED_INVESTMENT_TYPES,
    load_dashboard_data,
)
from dashboard.sources import profile as profile_source

MONTHS = ["202511", "202512", "202601"]
BRANCHES = [("0001", "지점 01"), ("0002", "지점 02")]
TOTAL_BRANCH = ("0000", "전체")
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


@pytest.fixture
def source_files(tmp_path, monkeypatch):
    """원본 파일들을 만들고 환경 변수를 걸어 주는 헬퍼를 반환한다.

    `with_asset=False`로 부르면 자산 파일을 지정하지 않는다. 필수가 아닌
    원본이 빠졌을 때의 동작을 확인할 때 쓴다.
    """

    def _write(
        monthly: pd.DataFrame | None = None,
        profile: pd.DataFrame | None = None,
        asset1: pd.DataFrame | None = None,
        asset2: pd.DataFrame | None = None,
        asset3: pd.DataFrame | None = None,
        asset4: pd.DataFrame | None = None,
        with_asset: bool = True,
    ):
        monthly_path = tmp_path / "monthly.pkl"
        profile_path = tmp_path / "profile.pkl"
        (monthly if monthly is not None else _monthly_frame()).to_pickle(monthly_path)
        (profile if profile is not None else _profile_frame()).to_pickle(profile_path)
        monkeypatch.setenv("DASHBOARD_DATA_SOURCE", "local_file")
        monkeypatch.setenv("DASHBOARD_DATA_FILE", str(monthly_path))
        monkeypatch.setenv("DASHBOARD_PROFILE_FILE", str(profile_path))
        for key, given, default in (
            ("ASSET1", asset1, _asset1_frame),
            ("ASSET2", asset2, _asset2_frame),
            ("ASSET3", asset3, _asset3_frame),
            ("ASSET4", asset4, _asset4_frame),
        ):
            if not with_asset:
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
    """원본에 없는 총자산·거래·앱 값은 0이 아니라 빈 값으로 남는다."""
    data = source_files()()
    assert data.monthly["total_assets"].isna().all()
    kpis = shared.kpi_metrics(data.monthly)
    assert kpis["customer_count"]["value"] is not None
    for key in ("transaction_share", "app_share"):
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
