"""骑马订针位规划（staple-plan）算法单元测试。"""
import pytest

from app.imposition import staple_plan


def _plan(forbidden_zones=(), **overrides):
    """默认 4 页 1 张、左装订、页高 100、2 针、无留边、无最小针距、无禁区。"""
    params = {
        "total_pages": 4,
        "max_sheets": 1,
        "binding": "left",
        "page_height_mm": 100.0,
        "staples_per_signature": 2,
        "top_margin_mm": 0.0,
        "bottom_margin_mm": 0.0,
        "min_spacing_mm": 0.0,
        "forbidden_zones": list(forbidden_zones),
    }
    params.update(overrides)
    return staple_plan(**params)


def _only(result):
    return result["signatures"][0]


def test_exact_ideal_positions_have_zero_deviation():
    # 页高 100、3 针：理想针位 25/50/75 恰为整数刻度
    sig = _only(_plan(staples_per_signature=3))
    assert sig["staple_positions_mm"] == [25, 50, 75]
    assert sig["max_deviation_mm"] == 0.0


def test_rounds_to_nearest_integer_ticks_minimizing_max_deviation():
    # 理想针位 100/3、200/3：最近整数刻度 33 与 67，最大偏差 1/3
    sig = _only(_plan())
    assert sig["staple_positions_mm"] == [33, 67]
    assert sig["max_deviation_mm"] == pytest.approx(1 / 3)


def test_tie_broken_by_lexicographically_smallest_sequence():
    # 页高 52.5、2 针：理想针位 17.5、35.0；17 与 18 偏差同为 0.5、
    # 偏差总和也相同，取字典序最小的 [17, 35]
    sig = _only(_plan(page_height_mm=52.5))
    assert sig["staple_positions_mm"] == [17, 35]
    assert sig["max_deviation_mm"] == pytest.approx(0.5)


def test_tie_broken_by_total_deviation_before_lexicographic():
    # 页高 52.8、2 针：理想针位 17.6、35.2；禁针 [35,35] 后第二针只能取 36
    # （偏差 0.8）。第一针 17（0.6）与 18（0.4）均在窗口内：字典序偏好 17，
    # 但偏差总和 1.2 < 1.4，先取总和最小的 [18, 36]
    sig = _only(_plan([(1, [(35.0, 35.0)])], page_height_mm=52.8))
    assert sig["staple_positions_mm"] == [18, 36]
    assert sig["max_deviation_mm"] == pytest.approx(0.8)


def test_min_spacing_forces_positions_to_spread():
    # 页高 50、4 针：理想针位 10/20/30/40；最小针距 15 时依次最小化
    # 最大偏差 -> 总和 -> 字典序，得 [2, 17, 32, 47]，最大偏差 8
    sig = _only(
        _plan(page_height_mm=50.0, staples_per_signature=4, min_spacing_mm=15.0)
    )
    assert sig["staple_positions_mm"] == [2, 17, 32, 47]
    assert sig["max_deviation_mm"] == pytest.approx(8.0)


def test_fractional_min_spacing_rounds_up_to_integer_gap():
    # 可行刻度只有 10、11（留边夹出）：最小针距 1 允许相邻，1.5 要求间距 ≥ 2
    sig = _only(
        _plan(top_margin_mm=10.0, bottom_margin_mm=89.0, min_spacing_mm=1.0)
    )
    assert sig["staple_positions_mm"] == [10, 11]
    assert sig["max_deviation_mm"] == pytest.approx(1 / 3)
    with pytest.raises(ValueError, match="无可行订针排列"):
        _plan(top_margin_mm=10.0, bottom_margin_mm=89.0, min_spacing_mm=1.5)


def test_margins_shift_feasible_range():
    # 上下留边各 10：理想针位 10+80/3、10+160/3 -> 37、63
    sig = _only(_plan(top_margin_mm=10.0, bottom_margin_mm=10.0))
    assert sig["staple_positions_mm"] == [37, 63]
    assert sig["max_deviation_mm"] == pytest.approx(1 / 3)
    assert all(10 <= p <= 90 for p in sig["staple_positions_mm"])


def test_forbidden_interval_avoids_blocked_ticks():
    # 禁针 [33,33]：第一针改取 34（偏差 2/3），第二针仍为 67
    sig = _only(_plan([(1, [(33.0, 33.0)])]))
    assert sig["staple_positions_mm"] == [34, 67]
    assert sig["max_deviation_mm"] == pytest.approx(2 / 3)


def test_forbidden_interval_is_closed_and_applies_to_integer_ticks():
    # [32.5, 33.5] 闭区间只覆盖整数刻度 33 -> 与禁 33 等效
    sig = _only(_plan([(1, [(32.5, 33.5)])]))
    assert sig["staple_positions_mm"] == [34, 67]
    # [33.1, 33.9] 不含任何整数刻度 -> 不影响
    sig = _only(_plan([(1, [(33.1, 33.9)])]))
    assert sig["staple_positions_mm"] == [33, 67]


def test_forbidden_zones_apply_per_signature():
    # 8 页、每帖 1 张 -> 2 帖；禁针只给第 2 帖
    result = _plan(
        [(2, [(33.0, 33.0)])],
        total_pages=8,
        max_sheets=1,
    )
    assert result["signature_count"] == 2
    first, second = result["signatures"]
    assert first["staple_positions_mm"] == [33, 67]
    assert second["staple_positions_mm"] == [34, 67]


def test_signature_and_sheet_counts_reused_from_impose():
    # 10 页、每帖 1 张 -> 3 帖（4+4+2 补 2 空白），各 1 张、补齐 4 页
    result = _plan(total_pages=10, max_sheets=1)
    assert result["signature_count"] == 3
    assert [s["sheet_count"] for s in result["signatures"]] == [1, 1, 1]
    assert [s["page_count_padded"] for s in result["signatures"]] == [4, 4, 4]
    assert [s["signature_index"] for s in result["signatures"]] == [1, 2, 3]
    # 回显请求参数
    assert result["page_height_mm"] == 100.0
    assert result["staples_per_signature"] == 2
    assert result["min_spacing_mm"] == 0.0


def test_positions_are_integer_ticks_within_page_height():
    result = _plan(page_height_mm=297.0, staples_per_signature=4,
                   top_margin_mm=12.5, bottom_margin_mm=9.5)
    for sig in result["signatures"]:
        positions = sig["staple_positions_mm"]
        assert all(isinstance(p, int) for p in positions)
        assert positions == sorted(positions)
        assert len(set(positions)) == len(positions)
        assert all(12.5 <= p <= 297.0 - 9.5 for p in positions)


def test_infeasible_signature_raises_with_signature_index():
    # 第 2 帖整页禁针 -> 无可行排列，错误指出帖号 2
    with pytest.raises(ValueError, match="第 2 帖"):
        _plan([(2, [(0.0, 100.0)])], total_pages=8, max_sheets=1)


def test_margins_leaving_no_room_raise():
    with pytest.raises(ValueError, match="第 1 帖"):
        _plan(top_margin_mm=60.0, bottom_margin_mm=60.0)


def test_min_spacing_too_large_raises():
    with pytest.raises(ValueError, match="无可行订针排列"):
        _plan(min_spacing_mm=1000.0)


def test_invalid_page_height_raises():
    for page_height_mm in (49.9, 1000.1, float("nan"), float("inf")):
        with pytest.raises(ValueError):
            _plan(page_height_mm=page_height_mm)


def test_invalid_staple_count_raises():
    for staples_per_signature in (1, 5, 2.0, True):
        with pytest.raises(ValueError):
            _plan(staples_per_signature=staples_per_signature)


def test_negative_margin_or_spacing_raises():
    with pytest.raises(ValueError):
        _plan(top_margin_mm=-1.0)
    with pytest.raises(ValueError):
        _plan(bottom_margin_mm=-0.5)
    with pytest.raises(ValueError):
        _plan(min_spacing_mm=-0.1)


def test_invalid_forbidden_signature_index_raises():
    with pytest.raises(ValueError):
        _plan([(0, [(10.0, 20.0)])])
    with pytest.raises(ValueError):
        _plan([(2, [(10.0, 20.0)])])  # 只有 1 帖


def test_duplicate_forbidden_signature_raises():
    with pytest.raises(ValueError):
        _plan([(1, [(10.0, 20.0)]), (1, [(30.0, 40.0)])])


def test_invalid_forbidden_interval_raises():
    with pytest.raises(ValueError):
        _plan([(1, [])])  # 空区间列表
    with pytest.raises(ValueError):
        _plan([(1, [(30.0, 20.0)])])  # 起点大于终点
    with pytest.raises(ValueError):
        _plan([(1, [(-1.0, 20.0)])])  # 越出页高下界
    with pytest.raises(ValueError):
        _plan([(1, [(20.0, 100.1)])])  # 越出页高上界
    with pytest.raises(ValueError):
        _plan([(1, [(float("nan"), 20.0)])])  # 非有限值
