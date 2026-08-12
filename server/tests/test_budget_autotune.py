"""TDD tests for AutoTuner (feature #8: Budget Auto-tuning)."""
import pytest


def make_rows(spents, cap=30000, hit_cap=0, success=1, project_key="abc"):
    from luna_mcp.budget.history import SessionRow
    return [
        SessionRow(ts=float(i), project_key=project_key, total_spent=s,
                   cap=cap, skipped=0, downgraded=0,
                   hit_cap=hit_cap, success=success)
        for i, s in enumerate(spents)
    ]


# ── compute_cap ───────────────────────────────────────────────────────────────

def test_cold_start_returns_work_preset():
    from luna_mcp.budget.autotune import PRESETS, compute_cap
    rows = make_rows([1000, 2000, 3000])  # < 5
    assert compute_cap(rows) == PRESETS["work"]


def test_cold_start_empty():
    from luna_mcp.budget.autotune import PRESETS, compute_cap
    assert compute_cap([]) == PRESETS["work"]


def test_p95_buffer_120_percent():
    from luna_mcp.budget.autotune import compute_cap
    # 20 sessions, all spent 10000 → p95=10000, cap should be ~12000
    rows = make_rows([10_000] * 20)
    cap = compute_cap(rows)
    assert cap == pytest.approx(12_000, rel=0.05)


def test_cap_grows_with_higher_spend():
    from luna_mcp.budget.autotune import compute_cap
    low_rows = make_rows([5_000] * 20)
    high_rows = make_rows([20_000] * 20)
    assert compute_cap(high_rows) > compute_cap(low_rows)


def test_failure_autobump_at_20pct_failed():
    """If >=20% of last 20 sessions hit cap and didn't succeed → bump by 1.3x."""
    from luna_mcp.budget.autotune import compute_cap
    from luna_mcp.budget.history import SessionRow
    # 20 sessions, 5 of them failed (hit_cap=1, success=0) → 25% >= 20%
    rows = []
    for i in range(15):
        rows.append(SessionRow(ts=float(i), project_key="k", total_spent=10_000,
                               cap=10_000, skipped=0, downgraded=0, hit_cap=0, success=1))
    for i in range(15, 20):
        rows.append(SessionRow(ts=float(i), project_key="k", total_spent=10_000,
                               cap=10_000, skipped=0, downgraded=0, hit_cap=1, success=0))
    cap_no_fail = compute_cap(make_rows([10_000] * 20))
    cap_fail = compute_cap(rows)
    assert cap_fail > cap_no_fail


def test_outlier_does_not_dominate():
    """One outlier in 30 doesn't make cap huge."""
    from luna_mcp.budget.autotune import compute_cap
    spents = [10_000] * 29 + [200_000]  # 1 outlier
    rows = make_rows(spents)
    cap = compute_cap(rows)
    # p95 of 30 items at index 28: should be 10000, not 200000
    assert cap < 50_000


def test_high_variance_uses_max_observed():
    """When IQR/p50 > 0.5, cap >= last observed session."""
    from luna_mcp.budget.autotune import compute_cap
    # IQR = 15000-5000=10000, p50=5000 → 10000/5000=2.0 > 0.5
    spents = [5_000] * 10 + [15_000] * 10
    rows = make_rows(spents)
    cap = compute_cap(rows)
    assert cap >= max(spents)


def test_hard_upper_clamp():
    from luna_mcp.budget.autotune import HARD_UPPER, compute_cap
    rows = make_rows([HARD_UPPER] * 20)
    cap = compute_cap(rows)
    assert cap <= HARD_UPPER


def test_cap_at_least_p95_times_1pt2():
    from luna_mcp.budget.autotune import compute_cap
    spents = list(range(1000, 21000, 1000))  # 20 values
    rows = make_rows(spents)
    cap = compute_cap(rows)
    s = sorted(spents)
    p95 = s[min(len(s) - 1, int(len(s) * 0.95))]
    assert cap >= int(p95 * 1.2) * 0.9  # allow slight variance from other logic


# ── allow_prob / sigmoid ──────────────────────────────────────────────────────

def test_sigmoid_high_psuccess_allows_more():
    from luna_mcp.budget.autotune import allow_prob
    # At 70% spent, high p_success should allow more than low p_success
    p_high = allow_prob(0.70, 0.9)
    p_low = allow_prob(0.70, 0.1)
    assert p_high > p_low


def test_sigmoid_low_pct_always_high_prob():
    from luna_mcp.budget.autotune import allow_prob
    assert allow_prob(0.0, 0.5) > 0.9
    assert allow_prob(0.1, 0.5) > 0.8


def test_sigmoid_high_pct_low_prob():
    from luna_mcp.budget.autotune import allow_prob
    # At 95% with low p_success → near 0
    p = allow_prob(0.95, 0.1)
    assert p < 0.1


def test_sigmoid_prob_between_0_and_1():
    from luna_mcp.budget.autotune import allow_prob
    for pct in [0.0, 0.25, 0.5, 0.75, 1.0]:
        for ps in [0.0, 0.5, 1.0]:
            p = allow_prob(pct, ps)
            assert 0.0 <= p <= 1.0


# ── estimate_p_success ────────────────────────────────────────────────────────

def test_estimate_p_success_default_optimistic_when_empty():
    from luna_mcp.budget.autotune import estimate_p_success
    assert estimate_p_success([]) == pytest.approx(0.85)


def test_estimate_p_success_all_success():
    from luna_mcp.budget.autotune import estimate_p_success
    rows = make_rows([1000] * 10, success=1)
    assert estimate_p_success(rows) == pytest.approx(1.0)


def test_estimate_p_success_half_failed():
    from luna_mcp.budget.autotune import estimate_p_success
    from luna_mcp.budget.history import SessionRow
    rows = (
        [SessionRow(ts=float(i), project_key="k", total_spent=1000, cap=30000,
                    skipped=0, downgraded=0, hit_cap=0, success=1) for i in range(10)]
        + [SessionRow(ts=float(i+10), project_key="k", total_spent=1000, cap=30000,
                      skipped=0, downgraded=0, hit_cap=1, success=0) for i in range(10)]
    )
    p = estimate_p_success(rows)
    assert p == pytest.approx(0.5)


def test_estimate_p_success_uses_last_20():
    """estimate_p_success uses only the newest 20 rows (DB returns DESC: newest first)."""
    from luna_mcp.budget.autotune import estimate_p_success
    from luna_mcp.budget.history import SessionRow
    # DB returns DESC: 10 newest success first, then 20 older failures
    newest_success = [SessionRow(ts=float(29 - i), project_key="k", total_spent=1000, cap=30000,
                                 skipped=0, downgraded=0, hit_cap=0, success=1) for i in range(10)]
    older_failed = [SessionRow(ts=float(19 - i), project_key="k", total_spent=1000, cap=30000,
                               skipped=0, downgraded=0, hit_cap=1, success=0) for i in range(20)]
    rows = newest_success + older_failed  # DESC order
    p = estimate_p_success(rows)
    # rows[:20] = 10 success + 10 failed → 0.5
    assert p == pytest.approx(0.5)
