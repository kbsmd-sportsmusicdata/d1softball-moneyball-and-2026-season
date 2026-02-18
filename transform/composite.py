from __future__ import annotations


def apply_composite_score(rows: list[dict]) -> list[dict]:
    for row in rows:
        row["composite_score"] = round(
            0.35 * row.get("offense_z", 0.0)
            + 0.40 * row.get("pitching_z", 0.0)
            + 0.15 * row.get("discipline_z", 0.0)
            + 0.10 * row.get("defense_z", 0.0),
            4,
        )

    rows.sort(key=lambda x: x["composite_score"], reverse=True)
    for index, row in enumerate(rows, start=1):
        row["composite_rank"] = index
    return rows
