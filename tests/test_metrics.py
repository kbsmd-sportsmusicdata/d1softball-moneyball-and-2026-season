from transform.composite import apply_composite_score
from transform.metrics import add_team_derived_metrics


def test_team_metrics_and_composite_rank_determinism():
    rows = [
        {
            "team_id": "a",
            "team_name": "A",
            "ab": 100,
            "h": 40,
            "2b": 8,
            "3b": 2,
            "hr": 5,
            "bb": 20,
            "so": 25,
            "r": 30,
            "g": 10,
            "ip": 60,
            "wh": 50,
            "k": 70,
            "er": 10,
            "opp_ba": 0.2,
            "fe": 5,
            "ha": 30,
        },
        {
            "team_id": "b",
            "team_name": "B",
            "ab": 100,
            "h": 35,
            "2b": 5,
            "3b": 1,
            "hr": 4,
            "bb": 10,
            "so": 40,
            "r": 20,
            "g": 10,
            "ip": 60,
            "wh": 65,
            "k": 55,
            "er": 20,
            "opp_ba": 0.25,
            "fe": 10,
            "ha": 40,
        },
    ]

    derived = add_team_derived_metrics(rows)
    ranked = apply_composite_score(derived)

    assert ranked[0]["team_id"] == "a"
    assert ranked[0]["composite_rank"] == 1
    assert ranked[1]["composite_rank"] == 2
    assert ranked[0]["ops"] > ranked[1]["ops"]
