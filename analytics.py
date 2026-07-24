"""
Performance analytics — expectancy, profit factor, drawdown, streaks.

R-MODEL (zaroori padhna):
Ye bot orders execute nahi karta, isliye asli P&L kahin record nahi hota.
Metrics ek SAAF, likhe hue model par bante hain: har trade ek equal
one-third position maan kar TP1 / TP2 / TP3 par book hoti hai, bacha hua
hissa SL ya breakeven par band hota hai.

  SL laga, TP1 nahi aaya      -> -1.00 R
  TP1 aaya, phir BE           -> (TP1_R)/3
  TP1+TP2 aaye, phir BE       -> (TP1_R + TP2_R)/3
  TP3 (full target)           -> (TP1_R + TP2_R + TP3_R)/3

Ye ASLI paisa nahi hai -- ye ek consistent yardstick hai jisse alag-alag
settings compare ki ja sakein. Isse live P&L mat samajhna.
"""

import csv
import json
from datetime import datetime

TP1_R, TP2_R, TP3_R = 1.2, 2.0, 3.0


def realized_r(trade: dict) -> float | None:
    """Closed trade ka R. OPEN trade par None."""
    status = trade.get("status")
    if status == "OPEN":
        return None
    if status == "TP":
        return round((TP1_R + TP2_R + TP3_R) / 3, 4)
    if trade.get("hit_tp2"):
        return round((TP1_R + TP2_R) / 3, 4)
    if trade.get("hit_tp1"):
        return round(TP1_R / 3, 4)
    return -1.0


def compute_metrics(trades: list[dict]) -> dict:
    rs = [r for r in (realized_r(t) for t in trades) if r is not None]
    if not rs:
        return {"closed": 0}

    wins = [r for r in rs if r > 0]
    losses = [r for r in rs if r < 0]
    gross_win = sum(wins)
    gross_loss = abs(sum(losses))

    # Max drawdown equity curve par (R units mein)
    equity, peak, max_dd = 0.0, 0.0, 0.0
    for r in rs:
        equity += r
        peak = max(peak, equity)
        max_dd = max(max_dd, peak - equity)

    # Lagataar jeet / haar
    best_w = cur_w = best_l = cur_l = 0
    for r in rs:
        if r > 0:
            cur_w += 1; cur_l = 0
        else:
            cur_l += 1; cur_w = 0
        best_w = max(best_w, cur_w)
        best_l = max(best_l, cur_l)

    return {
        "closed":            len(rs),
        "wins":              len(wins),
        "losses":            len(losses),
        "win_rate":          round(len(wins) / len(rs) * 100, 2),
        "loss_rate":         round(len(losses) / len(rs) * 100, 2),
        "total_r":           round(sum(rs), 3),
        "expectancy_r":      round(sum(rs) / len(rs), 4),
        "avg_win_r":         round(gross_win / len(wins), 3) if wins else 0.0,
        "avg_loss_r":        round(-gross_loss / len(losses), 3) if losses else 0.0,
        "profit_factor":     round(gross_win / gross_loss, 3) if gross_loss else None,
        "max_drawdown_r":    round(max_dd, 3),
        "max_consec_wins":   best_w,
        "max_consec_losses": best_l,
    }


def by_group(trades: list[dict], key: str) -> dict:
    """key ke hisaab se metrics -- e.g. 'asset' ya 'signal'."""
    groups: dict[str, list] = {}
    for t in trades:
        groups.setdefault(str(t.get(key, "?")).upper(), []).append(t)
    return {k: compute_metrics(v) for k, v in sorted(groups.items())}


def export_json(trades: list[dict], path: str) -> str:
    payload = {
        "generated": datetime.utcnow().isoformat() + "Z",
        "overall":   compute_metrics(trades),
        "by_asset":  by_group(trades, "asset"),
        "by_side":   by_group(trades, "signal"),
        "trades":    [{**t, "realized_r": realized_r(t)} for t in trades],
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, default=str)
    return path


def export_csv(trades: list[dict], path: str) -> str:
    cols = ["id", "time", "asset", "signal", "entry", "sl",
            "tp1", "tp2", "tp3", "status", "hit_tp1", "hit_tp2",
            "hit_tp3", "realized_r"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for t in trades:
            w.writerow({**t, "realized_r": realized_r(t)})
    return path
