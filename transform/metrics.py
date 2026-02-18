from __future__ import annotations

import math


def add_team_derived_metrics(rows: list[dict]) -> list[dict]:
    for row in rows:
        ab = max(row.get("ab", 0.0), 1.0)
        h = row.get("h", 0.0)
        doubles = row.get("2b", 0.0)
        triples = row.get("3b", 0.0)
        hr = row.get("hr", 0.0)
        bb = row.get("bb", 0.0)
        so = row.get("so", 0.0)
        g = max(row.get("g", 0.0), 1.0)

        singles = max(h - doubles - triples - hr, 0.0)
        obp = (h + bb) / max((ab + bb), 1.0)
        slg = (singles + 2 * doubles + 3 * triples + 4 * hr) / ab
        avg = h / ab

        row["avg"] = round(avg, 4)
        row["obp"] = round(obp, 4)
        row["slg"] = round(slg, 4)
        row["ops"] = round(obp + slg, 4)
        row["iso"] = round(slg - avg, 4)
        row["bb_k_ratio"] = round(bb / max(so, 1.0), 4)
        row["runs_per_game"] = round(row.get("r", 0.0) / g, 4)

        ip = max(row.get("ip", 0.0), 1.0)
        wh = row.get("wh", row.get("bb", 0.0) + row.get("ha", 0.0))
        k = row.get("k", 0.0)
        er = row.get("er", 0.0)
        opp_ba = row.get("opp_ba", 0.0)
        fe = row.get("fe", 0.0)

        row["whip"] = round(wh / ip, 4)
        row["k_bb_ratio"] = round(k / max(row.get("bb", 0.0), 1.0), 4)
        row["opponent_ba"] = round(opp_ba, 4)
        row["errors_per_game"] = round(fe / g, 4)
        row["fielding_pct"] = round(1.0 - (fe / max((h + fe), 1.0)), 4)
        row["era"] = round((9.0 * er) / ip, 4)

    _apply_z_scores(rows)
    return rows


def add_player_derived_metrics(rows: list[dict]) -> list[dict]:
    for row in rows:
        ab = max(row.get("ab", 0.0), 1.0)
        h = row.get("h", 0.0)
        doubles = row.get("2b", 0.0)
        triples = row.get("3b", 0.0)
        hr = row.get("hr", 0.0)
        bb = row.get("bb", 0.0)

        singles = max(h - doubles - triples - hr, 0.0)
        obp = (h + bb) / max((ab + bb), 1.0)
        slg = (singles + 2 * doubles + 3 * triples + 4 * hr) / ab

        row["avg"] = round(h / ab, 4)
        row["ops"] = round(obp + slg, 4)
        row["iso"] = round(slg - (h / ab), 4)
    return rows


def _apply_z_scores(rows: list[dict]) -> None:
    metrics = {
        "offense_z": ["ops", "runs_per_game", "iso"],
        "pitching_z": ["k_bb_ratio", "whip", "era"],
        "discipline_z": ["bb_k_ratio"],
        "defense_z": ["fielding_pct", "errors_per_game"],
    }

    per_metric_stats = {}
    for cols in metrics.values():
        for col in cols:
            values = [float(r.get(col, 0.0)) for r in rows]
            mean = sum(values) / max(len(values), 1)
            variance = sum((v - mean) ** 2 for v in values) / max(len(values), 1)
            stdev = math.sqrt(variance) if variance > 0 else 1.0
            per_metric_stats[col] = (mean, stdev)

    for row in rows:
        for group, cols in metrics.items():
            z_values = []
            for col in cols:
                mean, stdev = per_metric_stats[col]
                raw = float(row.get(col, 0.0))
                z = (raw - mean) / stdev
                if col in {"whip", "era", "errors_per_game"}:
                    z *= -1.0
                z_values.append(z)
            row[group] = round(sum(z_values) / max(len(z_values), 1), 4)

        row["era_norm"] = row["pitching_z"]
