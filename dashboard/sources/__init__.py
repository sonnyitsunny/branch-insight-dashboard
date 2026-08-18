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

from dashboard.data import (
    REVENUE_FINAL,
    TRADE_PRODUCT_TOTAL,
    DashboardData,
    check_count_gap,
    plain_text,
    to_numeric_column,
)
from dashboard.sources import (
    asset1,
    asset2,
    asset3,
    asset4,
    consulting1,
    monthly,
    profile,
    revenue1,
    transaction1,
    transaction2,
    transaction3,
)


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
    Source(key="asset1", module=asset1, required=False),
    Source(key="asset2", module=asset2, required=False),
    Source(key="asset3", module=asset3, required=False),
    Source(key="asset4", module=asset4, required=False),
    Source(key="consulting1", module=consulting1, required=False),
    Source(key="transaction1", module=transaction1, required=False),
    Source(key="transaction2", module=transaction2, required=False),
    Source(key="transaction3", module=transaction3, required=False),
    Source(key="revenue1", module=revenue1, required=False),
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


def _renamed(
    raw: dict[str, pd.DataFrame],
    paths: dict[str, str] | None,
    key: str,
) -> pd.DataFrame | None:
    """원본 하나를 표준 컬럼 이름으로 바꾼다. 없으면 None.

    필수 원본이 빠져 있으면 어느 파일인지 알리며 멈춘다.
    """
    source = find(key)
    frame = raw.get(key)
    if frame is None:
        if source.required:
            raise ValueError(f"{source.label} 원본이 없습니다.")
        return None
    path = (paths or {}).get(key) or f"{source.label} 파일"
    return rename(frame, source, path)


def assemble(
    raw: dict[str, pd.DataFrame],
    paths: dict[str, str] | None = None,
) -> DashboardData:
    """원본 파일들을 표준 4개 프레임으로 바꾼다.

    `raw`는 원본 키(`SOURCES`의 `key`)마다 읽어 온 DataFrame을 담는다.
    필수가 아닌 원본은 빼도 되며, 그 컬럼은 비어 있고 화면에 `-`로 나타난다.
    원본이 늘어도 이 함수의 인자는 늘지 않는다.
    `paths`는 오류 메시지에 쓸 파일 경로다.

    붙는 자리는 원본의 단위가 정한다. 기준월·지점 단위인 자산1·자산4는
    월별 프레임에, 지점마다 한 행인 자산2는 지점 요약 프레임에 붙는다. 지점
    프로필과 자산2에는 기준 월 컬럼이 없어 월별 파일의 마지막 월을 쓴다.
    """
    monthly_frame = monthly.build(_renamed(raw, paths, "monthly"))

    asset1_raw = _renamed(raw, paths, "asset1")
    if asset1_raw is not None:
        asset1_frame = asset1.build(asset1_raw)
        check_asset1_against_monthly(monthly_frame, asset1_frame)
        monthly_frame = merge_monthly_values(
            monthly_frame, asset1_frame, asset1.VALUE_COLUMNS
        )

    asset4_raw = _renamed(raw, paths, "asset4")
    if asset4_raw is not None:
        asset4_frame = asset4.build(asset4_raw)
        # 자산4에는 다른 원본과 겹치는 지표가 없어 값 대조는 하지 않는다.
        # 같은 기준월·지점을 담고 있는지만 확인한다.
        check_month_branch_keys(monthly_frame, asset4_frame, asset4.LABEL)
        monthly_frame = merge_monthly_values(
            monthly_frame, asset4_frame, asset4.VALUE_COLUMNS
        )

    months = monthly.months(monthly_frame)

    # 거래1은 월별 프레임에도 한 컬럼을 남긴다. 상단 카드의 '거래고객 비중'이
    # 그 값을 공통고객 수로 나눠 만든다(→ merge_transaction_customers).
    transaction_frame = _long_frame(raw, paths, "transaction1", months)
    if not transaction_frame.empty:
        monthly_frame = merge_transaction_customers(
            monthly_frame, transaction_frame
        )

    # 수익1도 월별 프레임에 한 컬럼을 남긴다. 상단 카드의 '공통고객 수익'이
    # 그 값을 쓴다(→ merge_revenue).
    revenue_frame = _long_frame(raw, paths, "revenue1", months)
    if not revenue_frame.empty:
        monthly_frame = merge_revenue(monthly_frame, revenue_frame)

    profile_frame = profile.build(
        _renamed(raw, paths, "profile"), months[-1]
    )
    check_profile_against_monthly(monthly_frame, profile_frame, months)

    asset2_raw = _renamed(raw, paths, "asset2")
    if asset2_raw is not None:
        profile_frame = merge_asset2(
            profile_frame, asset2.build(asset2_raw, months[-1])
        )

    asset3_raw = _renamed(raw, paths, "asset3")
    asset_change = (
        pd.DataFrame()
        if asset3_raw is None
        else check_asset3_months(asset3.build(asset3_raw), months)
    )

    consulting1_raw = _renamed(raw, paths, "consulting1")
    consulting = (
        pd.DataFrame()
        if consulting1_raw is None
        else check_consulting_months(
            consulting1.build(consulting1_raw), months
        )
    )

    return DashboardData(
        monthly=monthly_frame,
        age=profile.build_age(profile_frame),
        investment=profile.build_investment(profile_frame),
        summary=profile_frame,
        asset_change=asset_change,
        consulting=consulting,
        transaction=transaction_frame,
        pension_transaction=_long_frame(
            raw, paths, "transaction2", months
        ),
        cash_flow=_long_frame(raw, paths, "transaction3", months),
        revenue=revenue_frame,
    )


def merge_revenue(
    monthly_frame: pd.DataFrame, revenue_frame: pd.DataFrame
) -> pd.DataFrame:
    """수익1의 '최종' 분류 공통고객 수익을 월별 프레임에 붙인다.

    상단 카드의 '공통고객 수익'이 이 값을 그대로 쓴다(→ layout.KPI_CARDS).
    단위는 **원**이며 다른 금액 컬럼(억원)과 다르다
    (→ dashboard/sources/revenue1.py).

    분류별 수익을 더하지 않는다. '최종'은 상품 아홉 개와 '퇴직'을 합친 값을
    원본이 따로 담고 있고, 그 관계가 맞는지는 원본 모듈이 이미 대조했다
    (→ revenue1.GROUP_SUMS).

    수익1이 담지 않은 달은 비운 채로 둔다. 0으로 채우면 '수익 없음'이
    아니라 '수익이 0원으로 측정됨'이 된다(→ AGENTS.md §9).
    """
    final = revenue_frame[
        revenue_frame["revenue_type"] == REVENUE_FINAL
    ].rename(columns={"revenue_amount": "common_revenue"})
    if final.empty:
        return monthly_frame
    return merge_monthly_values(monthly_frame, final, ("common_revenue",))


def merge_transaction_customers(
    monthly_frame: pd.DataFrame, transaction_frame: pd.DataFrame
) -> pd.DataFrame:
    """거래1의 '전체' 상품 거래고객수를 월별 프레임에 붙인다.

    상단 카드의 '거래고객 비중'이 이 값을 공통고객 수로 나눠 만든다
    (→ dashboard/metrics.py의 monthly_totals). 분모인 공통고객 수는 월별
    파일의 값이며, 자산1의 공통고객수와 같은 값인지는 데이터 계층이 이미
    대조했다(→ check_asset1_against_monthly).

    상품별 거래고객수를 더하지 않는다. 한 고객이 국내주식과 해외주식을 모두
    거래하면 두 번 세어져 공통고객 수를 넘는다. 원본이 따로 담고 있는
    '전체' 상품 값을 그대로 쓴다.

    거래1이 담지 않은 달은 비운 채로 둔다. 0으로 채우면 '거래 없음'이
    아니라 '거래고객이 0명으로 측정됨'이 된다(→ AGENTS.md §9).
    """
    total_product = transaction_frame[
        transaction_frame["product_type"] == TRADE_PRODUCT_TOTAL
    ].rename(columns={"trade_customer_count": "transaction_customer_count"})
    if total_product.empty:
        return monthly_frame
    return merge_monthly_values(
        monthly_frame, total_product, ("transaction_customer_count",)
    )


def _long_frame(
    raw: dict[str, pd.DataFrame],
    paths: dict[str, str] | None,
    key: str,
    months: list[str],
) -> pd.DataFrame:
    """분류축이 있는 원본 하나를 표준 프레임으로 만든다.

    지정하지 않은 원본은 빈 프레임이 되고, 화면은 그 부분만 안내 상태로
    그린다. 원본이 있으면 월별 파일과 같은 기간인지 확인한다.
    """
    frame = _renamed(raw, paths, key)
    if frame is None:
        return pd.DataFrame()
    source = find(key)
    return check_months_within(
        source.module.build(frame), months, source.label
    )


def check_months_within(
    frame: pd.DataFrame, months: list[str], label: str
) -> pd.DataFrame:
    """원본의 월이 월별 파일 안에 들어 있는지 확인한다.

    원본마다 담고 있는 기간이 다를 수 있으므로 월별 파일보다 적은 것은
    정상이다. 월별 파일에 없는 달이 있으면 두 파일의 기간이 어긋났다는
    뜻이라 멈춘다.
    """
    extra = sorted(set(frame["base_month"].unique()) - set(months))
    if extra:
        raise ValueError(
            f"{label} 파일에 {monthly.LABEL} 파일에 없는 기준 월이"
            f" 있습니다: {', '.join(extra)}. "
            f"{monthly.LABEL}: {months[0]} ~ {months[-1]}"
        )
    return frame


def check_consulting_months(
    consulting: pd.DataFrame, months: list[str]
) -> pd.DataFrame:
    """상담 파일의 월이 월별 파일 안에 들어 있는지 확인한다.

    상담은 특정 달만 담고 있을 수 있으므로 월별 파일보다 적은 것은 정상이다.
    월별 파일에 없는 달이 있으면 두 파일의 기간이 어긋났다는 뜻이라 멈춘다.
    """
    return check_months_within(consulting, months, consulting1.LABEL)


def check_asset3_months(
    asset_change: pd.DataFrame, months: list[str]
) -> pd.DataFrame:
    """자산3의 월이 월별 파일 안에 들어 있는지 확인한다.

    전월 대비 증감율이라 첫 달은 비교할 앞 달이 없어 빠진다. 그래서 월별
    파일보다 적은 것은 정상이고, 월별 파일에 없는 달이 있으면 두 파일의
    기간이 어긋났다는 뜻이므로 멈춘다.
    """
    return check_months_within(asset_change, months, asset3.LABEL)


def _month_branch_index(frame: pd.DataFrame) -> pd.MultiIndex:
    """기준월·지점으로 만든 대조 키.

    지점 코드가 한쪽은 숫자, 한쪽은 문자열로 저장돼 있어도 맞물리도록
    문자열로 맞춘다.
    """
    return pd.MultiIndex.from_arrays(
        [frame["base_month"], plain_text(frame["branch_id"])],
        names=["base_month", "branch_id"],
    )


def check_month_branch_keys(
    monthly_frame: pd.DataFrame, asset_frame: pd.DataFrame, label: str
) -> None:
    """월별 원본 하나가 월별 파일과 같은 기준월·지점을 담고 있는지 본다.

    한쪽에만 있는 조합을 조용히 비워 두면 화면에서는 그냥 값이 없는 것으로
    보인다. 어느 파일에 무엇이 빠졌는지 알리며 멈춘다.
    """
    asset_key = _month_branch_index(asset_frame)
    duplicated = asset_key.duplicated()
    if duplicated.any():
        month, branch_id = asset_key[duplicated][0]
        raise ValueError(
            f"{label} 파일에 같은 기준월·지점이 두 번 이상 있습니다: "
            f"{month} 지점 {branch_id}. 한 지점은 한 달에 한 행이어야 합니다."
        )

    monthly_key = _month_branch_index(monthly_frame)
    for missing, source_label, other_label in (
        (monthly_key.difference(asset_key), label, monthly.LABEL),
        (asset_key.difference(monthly_key), monthly.LABEL, label),
    ):
        if len(missing):
            shown = ", ".join(
                f"{month} 지점 {branch_id}" for month, branch_id in missing[:5]
            )
            raise ValueError(
                f"{source_label} 파일에 없는 기준월·지점이"
                f" {len(missing)}건 있습니다: {shown}. "
                f"{other_label} 파일과 같은 범위인지 확인해 주세요."
            )


def check_asset1_against_monthly(
    monthly_frame: pd.DataFrame, asset_frame: pd.DataFrame
) -> None:
    """자산1 파일과 월별 파일이 같은 지점·월을 담고 있는지 대조한다.

    두 파일에 공통고객수가 겹쳐 있다. 두 파일이 하루라도 다른 날 뽑히면 그
    사이에 빠져나간 고객만큼 수가 어긋나므로, 작은 차이는 알리고 넘어간다.
    크게 벌어지면 집계 기준이 다르다는 뜻이라 멈춘다(→ data.COUNT_TOLERANCE).

    화면의 고객 수는 월별 파일 값을 쓴다. 자산1의 공통고객수는 여기 대조
    말고는 쓰지 않는다(→ asset1.VALUE_COLUMNS).
    """
    check_month_branch_keys(monthly_frame, asset_frame, asset1.LABEL)

    expected = pd.Series(
        to_numeric_column(
            monthly_frame["customer_count"], monthly.LABEL, "공통고객수"
        ).to_numpy(),
        index=_month_branch_index(monthly_frame),
    )
    actual = pd.Series(
        to_numeric_column(
            asset_frame["customer_count"], asset1.LABEL, "공통고객수"
        ).to_numpy(),
        index=_month_branch_index(asset_frame),
    ).reindex(expected.index)
    check_count_gap(
        actual, expected, "공통고객수", asset1.LABEL, monthly.LABEL
    )


def merge_monthly_values(
    monthly_frame: pd.DataFrame,
    asset_frame: pd.DataFrame,
    columns: tuple[str, ...],
) -> pd.DataFrame:
    """월별 원본의 값 컬럼을 월별 프레임에 붙인다.

    기준월·지점이 두 파일에서 같다는 것은 `check_month_branch_keys`가 이미
    확인했다. 여기서는 행 순서를 바꾸지 않고 컬럼만 더한다.
    """
    values = asset_frame.set_index(_month_branch_index(asset_frame))
    target = _month_branch_index(monthly_frame)
    merged = monthly_frame.copy()
    for column in columns:
        merged[column] = values[column].reindex(target).to_numpy()
    return merged


def merge_asset2(
    summary_frame: pd.DataFrame, asset_frame: pd.DataFrame
) -> pd.DataFrame:
    """자산2 원본의 값 컬럼을 지점 요약 프레임에 붙인다.

    두 원본 모두 지점마다 한 행인 한 시점 스냅샷이라 지점 코드로 맞춘다.
    지점 구성이 다르면 조용히 비워 두지 않고 멈춘다.

    값은 서로 대조하지 않는다. 고객 수와 순자산이 다른 원본에도 있지만
    집계 기준이 달라 값이 다를 수 있다.
    """
    values = asset_frame.set_index(plain_text(asset_frame["branch_id"]))
    duplicated = values.index.duplicated()
    if duplicated.any():
        raise ValueError(
            f"{asset2.LABEL} 파일에 같은 지점이 두 번 이상 있습니다: "
            f"{values.index[duplicated][0]}. "
            "한 지점은 한 행이어야 합니다."
        )

    target = plain_text(summary_frame["branch_id"])
    for missing, source_label, other_label in (
        (sorted(set(target) - set(values.index)), asset2.LABEL, profile.LABEL),
        (sorted(set(values.index) - set(target)), profile.LABEL, asset2.LABEL),
    ):
        if missing:
            raise ValueError(
                f"{source_label} 파일에 없는 지점이 {len(missing)}곳"
                f" 있습니다: {', '.join(missing[:5])}. "
                f"{other_label} 파일과 같은 지점 구성인지 확인해 주세요."
            )

    merged = summary_frame.copy()
    for column in asset2.VALUE_COLUMNS:
        merged[column] = values[column].reindex(target).to_numpy()
    return merged


def check_profile_against_monthly(
    monthly_frame: pd.DataFrame,
    profile_frame: pd.DataFrame,
    months: list[str],
) -> None:
    """두 파일의 고객 수가 같은 시점을 가리키는지 대조한다.

    지점 프로필에는 기준 월이 없으므로, 시작·종료 시점 고객 수가 월별
    파일의 첫 월·마지막 월과 맞는지 확인한다. 크게 어긋나면 두 파일이
    가리키는 시점 자체가 다르다는 뜻이다.

    작은 차이는 알리고 넘어간다. 두 파일이 다른 날 뽑히면 그 사이에
    빠져나간 고객만큼 수가 줄어든다(→ data.COUNT_TOLERANCE).
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
        check_count_gap(
            actual,
            expected,
            f"{month} 고객 수",
            f"{profile.LABEL} '{label}'",
            monthly.LABEL,
        )


__all__ = [
    "SOURCES",
    "Source",
    "asset1",
    "asset2",
    "asset3",
    "asset4",
    "assemble",
    "check_asset1_against_monthly",
    "check_asset3_months",
    "check_consulting_months",
    "consulting1",
    "check_month_branch_keys",
    "check_months_within",
    "check_profile_against_monthly",
    "find",
    "merge_asset2",
    "merge_monthly_values",
    "merge_revenue",
    "merge_transaction_customers",
    "monthly",
    "profile",
    "rename",
    "revenue1",
    "transaction1",
    "transaction2",
    "transaction3",
]
