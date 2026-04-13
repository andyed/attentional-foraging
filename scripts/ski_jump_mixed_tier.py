"""Why does the mixed regression-rate tercile have the highest
boundary-click rate (3.15% vs ~0.7% for both extremes)?

Tests four hypotheses:
  H1: Boundary-clicking is a behavior of users who reach the bottom
      but DON'T regress (mixed = scrolls deep but doesn't go back).
  H2: Boundary clicks are concentrated in 1-2 outlier participants
      in the mixed tier, not a tier-wide effect.
  H3: Tercile boundaries are unstable; boundary-click rate is not
      monotone or robust to slight reshuffling of users.
  H4: The "mixed" effect is driven by abs-rank specifically, not
      organic-rank (already partly checked — both show the same
      mixed > extremes pattern, so H4 is mostly ruled out, but we'll
      double-check by splitting boundary clicks into ad vs organic).
"""

from __future__ import annotations

import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path("/Users/andyed/Documents/dev/attentional-foraging/notebooks-v2")))
from data_loader import (
    get_trial_ids,
    get_trial_meta,
    load_mouse_events,
    absolute_to_organic_rank,
    absolute_rank_band_tops,
)


def participant_regression_rate(trials_by_pid):
    out = {}
    for pid, tids in trials_by_pid.items():
        n_with_reg = 0
        n_total = 0
        for tid in tids:
            try:
                _, scrolls, _ = load_mouse_events(tid)
            except Exception:
                continue
            n_total += 1
            if not scrolls:
                continue
            ys = [y for _, y in scrolls]
            hwm = ys[0]
            for y in ys:
                if hwm - y > 30:
                    n_with_reg += 1
                    break
                if y > hwm:
                    hwm = y
        if n_total > 0:
            out[pid] = n_with_reg / n_total
    return out


def trial_has_regression(scrolls):
    if not scrolls:
        return False
    ys = [y for _, y in scrolls]
    hwm = ys[0]
    for y in ys:
        if hwm - y > 30:
            return True
        if y > hwm:
            hwm = y
    return False


def click_abs_rank(click_y, abs_tops, n_abs):
    pos = -1
    for i, top in enumerate(abs_tops):
        if click_y >= top:
            pos = i
        else:
            break
    return pos if 0 <= pos < n_abs else None


def main():
    tids = sorted(get_trial_ids())
    by_pid = defaultdict(list)
    for tid in tids:
        by_pid[tid.split("-")[0]].append(tid)

    reg_rate = participant_regression_rate(by_pid)
    rates = sorted(reg_rate.values())
    n = len(rates)
    t1 = rates[n // 3]
    t2 = rates[2 * n // 3]
    pid_tier = {}
    for pid, r in reg_rate.items():
        if r <= t1:
            pid_tier[pid] = "satisficer"
        elif r <= t2:
            pid_tier[pid] = "mixed"
        else:
            pid_tier[pid] = "optimizer"

    # Walk all trials and bucket
    trials = []
    for tid in tids:
        pid = tid.split("-")[0]
        tier = pid_tier.get(pid)
        if tier is None:
            continue
        doc_h, _, _ = get_trial_meta(tid)
        if not doc_h:
            continue
        try:
            _, scrolls, clicks = load_mouse_events(tid)
        except Exception:
            continue
        if not clicks:
            continue
        mapping = absolute_to_organic_rank(tid, doc_height=doc_h)
        if not mapping:
            continue
        n_abs = max(mapping.keys()) + 1
        abs_tops = absolute_rank_band_tops(n_abs, doc_h)
        click_y = clicks[0][2]
        c_abs = click_abs_rank(click_y, abs_tops, n_abs)
        c_org = mapping.get(c_abs) if c_abs is not None else None

        trials.append({
            "tid": tid,
            "pid": pid,
            "tier": tier,
            "click_abs": c_abs,
            "click_org": c_org,
            "is_ad_slot": c_abs is not None and c_org is None,
            "had_regression": trial_has_regression(scrolls),
        })

    # Boundary-click trials (abs rank 9-10)
    boundary = [t for t in trials if t["click_abs"] in (9, 10)]
    print(f"=== Boundary clicks (abs rank 9-10): n = {len(boundary)} ===\n")

    # Per-tier breakdown
    for tier in ("satisficer", "mixed", "optimizer"):
        sub = [t for t in boundary if t["tier"] == tier]
        n_sub = len(sub)
        n_ad = sum(1 for t in sub if t["is_ad_slot"])
        n_organic = n_sub - n_ad
        with_reg = sum(1 for t in sub if t["had_regression"])
        # Per-participant breakdown
        by_user = Counter(t["pid"] for t in sub)
        print(f"{tier:>10s}  total={n_sub}  organic={n_organic}  ad_slot={n_ad}  with_regression={with_reg}/{n_sub} ({with_reg/n_sub*100:.0f}%)" if n_sub else f"{tier:>10s}  total=0")
        if n_sub:
            top_users = by_user.most_common()
            print(f"             top participants: " + ", ".join(f"{p}:{c}" for p, c in top_users))
            print()

    # H1 test: per-trial regression behavior split sat/mix/opt for boundary clicks
    # vs trial-population baseline
    print("=== H1 — does the mixed tier boundary cluster have NO trial regression? ===")
    print("If yes → 'reached the bottom but didn't bother going back' = the mixed signature.\n")

    print("Within-tier baseline regression rate (all trials, not just boundary):")
    for tier in ("satisficer", "mixed", "optimizer"):
        sub = [t for t in trials if t["tier"] == tier]
        n_sub = len(sub)
        n_with = sum(1 for t in sub if t["had_regression"])
        print(f"  {tier:>10s}  n={n_sub}  trial reg rate = {n_with/n_sub:.3f}")

    print("\nWithin boundary-click trials only:")
    for tier in ("satisficer", "mixed", "optimizer"):
        sub = [t for t in boundary if t["tier"] == tier]
        if not sub:
            continue
        n_sub = len(sub)
        n_with = sum(1 for t in sub if t["had_regression"])
        print(f"  {tier:>10s}  n={n_sub}  trial reg rate on boundary clicks = {n_with/n_sub:.3f}")

    # H2 test: how many distinct participants account for the mixed tier's 30 boundary clicks?
    print("\n=== H2 — concentration test ===")
    mixed_boundary = [t for t in boundary if t["tier"] == "mixed"]
    pids = Counter(t["pid"] for t in mixed_boundary)
    print(f"mixed tier: {len(mixed_boundary)} boundary clicks distributed across {len(pids)} participants")
    print(f"max per participant: {max(pids.values()) if pids else 0}")
    print(f"top 5 contributors: {pids.most_common(5)}")
    if pids:
        n_users_in_mixed = sum(1 for v in pid_tier.values() if v == "mixed")
        n_user_with_any_boundary = len(pids)
        print(f"of {n_users_in_mixed} mixed-tier participants, {n_user_with_any_boundary} have ≥1 boundary click")
        # Gini
        counts = sorted(pids.values(), reverse=True)
        cum = 0
        s = sum(counts)
        for k, c in enumerate(counts[:5], 1):
            cum += c
            print(f"  top {k} user(s): {cum}/{s} = {cum/s*100:.0f}% of mixed boundary clicks")

    # H4 — split boundary by ad vs organic per tier
    print("\n=== H4 — ad vs organic split of boundary clicks per tier ===")
    for tier in ("satisficer", "mixed", "optimizer"):
        sub = [t for t in boundary if t["tier"] == tier]
        if not sub:
            continue
        n_ad = sum(1 for t in sub if t["is_ad_slot"])
        n_organic = len(sub) - n_ad
        print(f"  {tier:>10s}  organic={n_organic}  ad_slot={n_ad}  ad_fraction={n_ad/len(sub):.0%}")

    # H3 — sensitivity: shift tercile boundaries by ±0.05 reg-rate
    print("\n=== H3 — boundary stability ===")
    for delta in [-0.05, -0.02, 0.0, 0.02, 0.05]:
        t1_d = t1 + delta
        t2_d = t2 + delta
        tier_d = {}
        for pid, r in reg_rate.items():
            if r <= t1_d:
                tier_d[pid] = "satisficer"
            elif r <= t2_d:
                tier_d[pid] = "mixed"
            else:
                tier_d[pid] = "optimizer"
        n_b_by_tier = {t: 0 for t in ("satisficer", "mixed", "optimizer")}
        n_t_by_tier = {t: 0 for t in ("satisficer", "mixed", "optimizer")}
        for tr in trials:
            tt = tier_d.get(tr["pid"])
            if tt is None:
                continue
            n_t_by_tier[tt] += 1
            if tr["click_abs"] in (9, 10):
                n_b_by_tier[tt] += 1
        ratios = {t: n_b_by_tier[t] / n_t_by_tier[t] if n_t_by_tier[t] else 0
                  for t in ("satisficer", "mixed", "optimizer")}
        n_in_tier = {t: sum(1 for v in tier_d.values() if v == t)
                     for t in ("satisficer", "mixed", "optimizer")}
        print(f"  delta={delta:+.2f}  boundaries=({t1_d:.3f},{t2_d:.3f})  "
              f"sat={ratios['satisficer']*100:.2f}%  mix={ratios['mixed']*100:.2f}%  opt={ratios['optimizer']*100:.2f}%  "
              f"users={n_in_tier}")


if __name__ == "__main__":
    main()
