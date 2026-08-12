"""자산 탭 검증.

패널 여섯 개가 각각 어느 원본을 쓰는지, 선택 컨트롤이 실제로 그림을
바꾸는지, 단위와 색이 규칙대로인지 확인한다.
"""

from __future__ import annotations

import plotly.graph_objects as go
import pytest

from dashboard import callbacks
from dashboard import tabs as tab_registry
from dashboard.data import (
    ASSET_SHARE_COLUMNS,
    ALL_ASSET_TYPES,
    TOTAL_LABEL,
    load_dashboard_data,
)
from dashboard.tabs.asset import (
    COMPARE_LABELS,
    MIX_SLOTS,
    TAB,
    TABLE_COLUMNS,
)
from dashboard.tabs.registry import KIND_RADIO, VARIANTS_SLOT

CHARTS = {chart.key: chart for chart in TAB.charts}


@pytest.fixture(scope="module")
def dataset():
    return load_dashboard_data()


def draw(key: str, data, **selection):
    chart = CHARTS[key]
    chosen = chart.defaults(data)
    chosen.update(selection)
    return chart.build(data, chosen)


# --- 탭 등록 ----------------------------------------------------------------
def test_asset_tab_is_registered_with_six_panels():
    assert tab_registry.find("asset") is TAB
    assert [chart.key for chart in TAB.charts] == [
        "trend",
        "growth",
        "mix",
        "mixscatter",
        "heatmap",
        "pension",
    ]


def test_every_panel_returns_a_figure(dataset):
    for chart in TAB.charts:
        figure = chart.build(dataset, chart.defaults(dataset))
        assert isinstance(figure, go.Figure), chart.key
        assert figure.data, chart.key


# --- 1. 자산 추이 ------------------------------------------------------------
def test_trend_draws_total_as_bars_and_branch_as_a_line(dataset):
    figure = draw("trend", dataset)
    kinds = [trace.type for trace in figure.data]
    assert kinds == ["bar", "scatter"]
    assert figure.data[0].name == TOTAL_LABEL
    assert figure.data[1].name == dataset.branch_names[0]


def test_trend_radio_switches_between_total_and_average(dataset):
    net = draw("trend", dataset, measure="순자산")
    average = draw("trend", dataset, measure="고객 평균 자산")
    assert list(net.data[0].y) != list(average.data[0].y)
    assert "억원" in net.layout.yaxis.title.text
    assert "백만원" in average.layout.yaxis.title.text


def test_trend_uses_every_month_in_the_monthly_file(dataset):
    figure = draw("trend", dataset)
    assert len(figure.data[0].y) == len(dataset.months)


# --- 2. 자산 규모 및 증가율 --------------------------------------------------
def test_growth_scatter_uses_the_growth_rate_as_given(dataset):
    figure = draw("growth", dataset)
    given = dataset.summary.set_index("branch_name")["net_assets_growth"]
    for name, value in zip(figure.data[0].text, figure.data[0].y):
        assert value == pytest.approx(given[name])
    assert "%" in figure.layout.yaxis.title.text


def test_growth_scatter_has_no_select(dataset):
    assert CHARTS["growth"].selects == ()


# --- 3. 자산 구성 ------------------------------------------------------------
def test_mix_stacks_every_share_column_to_a_hundred(dataset):
    figure = draw("mix", dataset)
    assert len(figure.data) == len(ASSET_SHARE_COLUMNS)
    for index in range(1 + MIX_SLOTS):
        stacked = sum(trace.y[index] for trace in figure.data)
        assert stacked == pytest.approx(100.0, abs=0.5)


def test_mix_puts_the_total_first_then_the_chosen_branches(dataset):
    names = dataset.branch_names
    figure = draw(
        "mix", dataset, branch1=names[2], branch2=names[5], branch3=names[7]
    )
    assert list(figure.data[0].x) == [
        TOTAL_LABEL,
        names[2],
        names[5],
        names[7],
    ]


def test_mix_prints_the_share_inside_each_bar(dataset):
    """비중을 hover 없이 바로 읽을 수 있어야 한다."""
    from dashboard.tabs.asset.figures import MIX_LABEL_MIN_SHARE

    figure = draw("mix", dataset)
    assert figure.layout.uniformtext.mode == "hide"
    for trace in figure.data:
        assert trace.textposition == "inside"
        # 글자색은 Plotly가 막대 색에 맞춰 고르므로 지정하지 않는다.
        assert trace.insidetextfont.color is None
        for value, text in zip(trace.y, trace.text):
            if value is None or value < MIX_LABEL_MIN_SHARE:
                # 얇은 칸은 글자가 넘치므로 비운다.
                assert text == ""
            else:
                assert text == f"{value:.1f}%"


def test_mix_keeps_a_bar_per_slot_even_if_a_branch_repeats(dataset):
    """같은 지점을 두 칸에 골라도 칸이 사라지지 않는다.

    구분 이름으로 묶으면 막대가 하나로 합쳐져, 고른 칸이 조용히 없어진다.
    정적 HTML은 자리마다 숫자를 갈아 끼우므로 그쪽과도 어긋난다.
    """
    name = dataset.branch_names[5]
    other = dataset.branch_names[9]
    figure = draw("mix", dataset, branch1=name, branch2=name, branch3=other)
    assert list(figure.data[0].x) == [TOTAL_LABEL, name, name, other]
    values = list(figure.data[0].y)
    assert values[1] == values[2]


def test_mix_avoids_the_combination_explosion(dataset):
    """지점 칸이 셋이라 조합이 지점 수의 세제곱이다.

    정적 HTML이 Figure를 조합마다 담으면 열 수 없는 크기가 된다.
    숫자만 담고 그 자리를 갈아 끼우는 방식이어야 한다.
    """
    chart = CHARTS["mix"]
    assert chart.variants == VARIANTS_SLOT
    assert chart.combinations(dataset) == []
    slots = chart.slot_values(dataset)
    assert set(slots) == {f"branch{index + 1}" for index in range(MIX_SLOTS)}
    for values in slots.values():
        assert len(values) == len(dataset.branch_names)
        for column in values.values():
            # 값과 막대 안 문구를 함께 담는다. 값만 담으면 정적 HTML에서
            # 막대 높이와 적힌 숫자가 서로 다른 지점을 가리키게 된다.
            assert len(column["y"]) == len(ASSET_SHARE_COLUMNS)
            assert len(column["text"]) == len(ASSET_SHARE_COLUMNS)


# --- 4. 자산 구성 비교 -------------------------------------------------------
def test_mix_scatter_axes_follow_the_two_selects(dataset):
    figure = draw("mixscatter", dataset, x="채권", y="펀드")
    assert "채권" in figure.layout.xaxis.title.text
    assert "펀드" in figure.layout.yaxis.title.text
    assert len(figure.data[0].x) == len(dataset.branch_names)


def test_mix_scatter_is_linear_when_both_axes_are_the_same(dataset):
    figure = draw("mixscatter", dataset, x="국내주식", y="국내주식")
    assert list(figure.data[0].x) == list(figure.data[0].y)


def test_mix_scatter_excludes_the_other_category(dataset):
    assert "기타" not in COMPARE_LABELS
    options = CHARTS["mixscatter"].selects[0].options(dataset)
    assert options == list(COMPARE_LABELS)


# --- 5. 자산 구성별 증감 -----------------------------------------------------
def test_heatmap_rows_follow_the_source_row_order(dataset):
    figure = draw("heatmap", dataset)
    assert list(figure.data[0].y) == list(ALL_ASSET_TYPES)


def test_heatmap_columns_are_the_change_months(dataset):
    figure = draw("heatmap", dataset)
    months = sorted(dataset.asset_change["base_month"].unique())
    assert len(figure.data[0].x) == len(months)


def test_heatmap_is_red_up_and_blue_down_around_zero(dataset):
    """색만으로 읽지 않도록 숫자도 함께 적는다."""
    figure = draw("heatmap", dataset)
    heatmap = figure.data[0]
    assert heatmap.zmid == 0
    assert heatmap.zmin == -heatmap.zmax
    # 낮은 쪽이 푸르고 높은 쪽이 붉다.
    assert heatmap.colorscale[0][1] == "#0086B8"
    assert heatmap.colorscale[-1][1] == "#CB6015"
    assert heatmap.texttemplate


def test_heatmap_can_show_the_total_branch(dataset):
    figure = draw("heatmap", dataset, scope=TOTAL_LABEL)
    assert figure.data
    branch = draw("heatmap", dataset, scope=dataset.branch_names[0])
    assert branch.data[0].z.tolist() != figure.data[0].z.tolist()


# --- 6. 연금 자산 ------------------------------------------------------------
def test_pension_draws_a_monthly_trend_from_the_monthly_file(dataset):
    """자산4가 기준월·지점 단위라 추이를 그린다.

    자산 추이 패널과 같은 골격이어야 한다 — 전체는 막대, 고른 지점은 선.
    """
    figure = draw("pension", dataset)
    kinds = [trace.type for trace in figure.data]
    assert kinds == ["bar", "scatter"]
    assert figure.data[0].name == TOTAL_LABEL
    assert figure.data[1].name == dataset.branch_names[0]
    assert len(figure.data[0].y) == len(dataset.months)
    assert len(figure.data[1].y) == len(dataset.months)


def test_pension_radio_switches_the_product(dataset):
    pension = draw("pension", dataset, product="개인연금")
    irp = draw("pension", dataset, product="IRP")
    assert list(pension.data[0].y) != list(irp.data[0].y)
    assert "개인연금" in pension.layout.yaxis.title.text
    assert "IRP" in irp.layout.yaxis.title.text
    assert "억원" in pension.layout.yaxis.title.text


def test_pension_line_follows_the_chosen_branch(dataset):
    name = dataset.branch_names[3]
    figure = draw("pension", dataset, branch=name)
    assert figure.data[1].name == name
    assert name in figure.layout.yaxis2.title.text
    other = draw("pension", dataset, branch=dataset.branch_names[4])
    assert list(figure.data[1].y) != list(other.data[1].y)
    # 전체 막대는 지점을 바꿔도 그대로다.
    assert list(figure.data[0].y) == list(other.data[0].y)


def test_pension_uses_the_source_values_as_given(dataset):
    """막대는 원본 '전체' 행, 선은 그 지점 행을 그대로 쓴다."""
    name = dataset.branch_names[2]
    figure = draw("pension", dataset, branch=name, product="IRP")
    totals = dataset.monthly_total.set_index("base_month")["irp_assets"]
    branch = dataset.monthly[dataset.monthly["branch_name"] == name]
    branch = branch.set_index("base_month")["irp_assets"]
    for index, month in enumerate(dataset.months):
        assert figure.data[0].y[index] == pytest.approx(totals[month])
        assert figure.data[1].y[index] == pytest.approx(branch[month])


def test_pension_hover_carries_the_customer_count(dataset):
    """자산이 는 것이 가입자 증가 때문인지 바로 견줄 수 있어야 한다."""
    figure = draw("pension", dataset)
    assert "가입 고객 수" in figure.data[0].hovertemplate
    assert figure.data[0].customdata.shape[1] == 3


# --- 선택 컨트롤 -------------------------------------------------------------
def test_radio_is_used_where_there_are_only_a_few_values(dataset):
    kinds = {
        (chart.key, select.key): select.kind
        for chart in TAB.charts
        for select in chart.selects
    }
    assert kinds[("trend", "measure")] == KIND_RADIO
    assert kinds[("pension", "product")] == KIND_RADIO
    assert kinds[("trend", "branch")] != KIND_RADIO


def test_every_select_has_its_default_inside_its_options(dataset):
    for chart in TAB.charts:
        chosen = chart.defaults(dataset)
        for select in chart.selects:
            assert chosen[select.key] in select.options(dataset), (
                chart.key,
                select.key,
            )


def test_callbacks_cover_every_select(dataset):
    import app as app_module

    registered = set(app_module.app.callback_map.keys())
    for chart in TAB.charts:
        if not chart.selects:
            continue
        assert f"{chart.chart_id('asset')}.figure" in registered


# --- 지점별 표 --------------------------------------------------------------
def test_table_has_the_declared_columns_in_order(dataset):
    headers = [column.header for column in TABLE_COLUMNS]
    assert headers[:5] == [
        "지점명",
        "고객 수",
        "자산 합계",
        "자산 평균",
        "자산 증가율(YoY)",
    ]
    assert len(TABLE_COLUMNS) == 20
    assert headers[-3:] == ["DC 고객 수", "DC 자산", "DC 1인 평균"]


def test_table_pins_the_branch_name(dataset):
    from dashboard import grid

    assert grid.pinned_field(TABLE_COLUMNS) == "branch_name"
    assert TABLE_COLUMNS[0].width, "고정 컬럼은 폭을 직접 정한다"


def test_table_has_a_row_per_branch_and_a_total(dataset):
    total, rows = TAB.table.build(dataset)
    assert len(rows) == len(dataset.branch_names)
    assert list(rows["branch_name"]) == sorted(dataset.branch_names)
    assert total["branch_name"] == TOTAL_LABEL


def test_table_totals_come_from_the_source_total_row(dataset):
    """전체 행은 원본 값을 그대로 쓴다. 비중·평균은 더할 수 없다."""
    total, rows = TAB.table.build(dataset)
    given = dataset.summary_total.iloc[0]
    assert total["net_assets_growth"] == pytest.approx(
        given["net_assets_growth"]
    )
    assert total["bond_share"] == pytest.approx(given["bond_share"])
    # 지점 비중의 단순 합이 아니다.
    assert total["bond_share"] != pytest.approx(rows["bond_share"].sum())


def test_table_asset_columns_match_the_kpi_card(dataset):
    """표의 자산 합계는 상단 카드·추이 그래프와 같은 값이어야 한다."""
    from dashboard import metrics as shared

    total, _rows = TAB.table.build(dataset)
    kpis = shared.kpi_metrics(
        dataset.monthly, monthly_total=dataset.monthly_total
    )
    assert total["net_assets"] == pytest.approx(kpis["net_assets"]["value"])
    assert total["customer_count"] == pytest.approx(
        kpis["customer_count"]["value"]
    )


def test_table_values_are_numbers_so_sorting_is_correct(dataset):
    """셀에 서식 없는 원본 값을 넣어야 정렬이 문자열 순서가 되지 않는다."""
    _total, rows = TAB.table.build(dataset)
    for column in TABLE_COLUMNS:
        if column.field == "branch_name":
            continue
        values = rows[column.field].dropna()
        assert values.empty or values.map(
            lambda value: isinstance(value, (int, float))
        ).all(), column.field


def test_table_growth_column_is_the_only_coloured_one(dataset):
    from dashboard import grid

    assert grid.growth_fields(TABLE_COLUMNS) == ("net_assets_growth",)


def test_initial_view_builds_every_panel(dataset):
    view = callbacks.build_tab_view(TAB, dataset)
    assert set(view["charts"]) == set(CHARTS)
    for key, card in view["charts"].items():
        assert card["figure"].data, key
        assert set(card["values"]) == {
            select.key for select in CHARTS[key].selects
        }
