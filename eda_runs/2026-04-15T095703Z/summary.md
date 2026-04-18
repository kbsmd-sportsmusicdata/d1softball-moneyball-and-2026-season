# EDA Analyst Summary

- Run ID: `2026-04-15T095703Z`
- Generated At: `2026-04-15T09:57:03.968190+00:00`
- Teams Rows: `25`
- Players Rows: `1271`

## Findings

1. **Texas A&M leads the all-around team profile** (analytical) - Texas A&M ranks first by composite score, signaling balanced strength across offense, pitching, discipline, and defense.
2. **Elite Talent lens is currently data-limited** (elite_talent) - This angle is included via fallback contract coverage until richer fields are available.
3. **Stanford profiles as a coaching-efficiency standout** (coaching) - Stanford combines strong discipline and defensive execution, a common marker of repeatable coaching impact.
4. **Top-5 race is primed for fan-facing weekly drama** (fan_first) - The top of the board is tight enough to produce meaningful weekly movement and marquee matchups.
5. **Oklahoma State shows one of the most balanced profiles** (analytical) - Oklahoma State has near-matching offense and pitching z-scores, which usually translates to stable game-to-game performance.
6. **UCF owns the strongest run-prevention signal** (coaching) - UCF ranks near the top in both ERA and WHIP, suggesting dependable prevention quality.

## Storyboard Arc

**Who is built to sustain performance and who can swing a series?**
- Step 1: `hook` -> Top-5 race is primed for fan-facing weekly drama: The top of the board is tight enough to produce meaningful weekly movement and marquee matchups.
- Step 2: `evidence` -> Texas A&M leads the all-around team profile: Texas A&M ranks first by composite score, signaling balanced strength across offense, pitching, discipline, and defense.
- Step 3: `contrast` -> Oklahoma State shows one of the most balanced profiles: Oklahoma State has near-matching offense and pitching z-scores, which usually translates to stable game-to-game performance.
- Step 4: `implication` -> Elite Talent lens is currently data-limited: This angle is included via fallback contract coverage until richer fields are available.
- Step 5: `action` -> Stanford profiles as a coaching-efficiency standout: Stanford combines strong discipline and defensive execution, a common marker of repeatable coaching impact.
- Step 6: `support` -> UCF owns the strongest run-prevention signal: UCF ranks near the top in both ERA and WHIP, suggesting dependable prevention quality.

## Deeper Analysis Queue

- [high] Which teams overperform expected results once schedule strength is introduced? (Schedule-adjusted residual modeling)
- [high] Which player profiles are most predictive of postseason run production? (Feature importance with holdout seasons)
- [medium] Where does pitching usage create hidden fatigue or efficiency edges? (Usage clustering + rolling trend decomposition)
- [medium] Which fan-facing storylines have the highest week-to-week volatility? (Volatility index + change-point detection)