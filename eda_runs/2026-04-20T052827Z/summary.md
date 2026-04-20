# EDA Analyst Summary

- Run ID: `2026-04-20T052827Z`
- Generated At: `2026-04-20T05:28:27.647635+00:00`
- Teams Rows: `79`
- Players Rows: `125`

## Findings

1. **Analytical lens is currently data-limited** (analytical) - This angle is included via fallback coverage until richer fields are available.
2. **Elite Talent lens is currently data-limited** (elite_talent) - This angle is included via fallback coverage until richer fields are available.
3. **Coaching lens is currently data-limited** (coaching) - This angle is included via fallback coverage until richer fields are available.
4. **Fan First lens is currently data-limited** (fan_first) - This angle is included via fallback coverage until richer fields are available.
5. **Dataset quality checkpoint 1** (analytical) - Additional quality/context signal retained to satisfy the minimum finding count.

## Storyboard Arc

**What stands out in the latest dataset?**
- Step 1: `hook` -> Fan First lens is currently data-limited: This angle is included via fallback coverage until richer fields are available.
- Step 2: `evidence` -> Analytical lens is currently data-limited: This angle is included via fallback coverage until richer fields are available.
- Step 3: `contrast` -> Dataset quality checkpoint 1: Additional quality/context signal retained to satisfy the minimum finding count.
- Step 4: `implication` -> Elite Talent lens is currently data-limited: This angle is included via fallback coverage until richer fields are available.
- Step 5: `action` -> Coaching lens is currently data-limited: This angle is included via fallback coverage until richer fields are available.

## Deeper Analysis Queue

- [high] Which teams overperform expected results once schedule strength is introduced? (Schedule-adjusted residual modeling)
- [high] Which player profiles are most predictive of postseason run production? (Feature importance with holdout seasons)
- [medium] Where does usage create hidden fatigue or efficiency edges? (Usage clustering + rolling trend decomposition)
- [medium] Which fan-facing storylines have the highest week-to-week volatility? (Volatility index + change-point detection)