# Wingfoiling calibration deployment — 19 October 2026

Owner calibration implemented and deployed in [Actions run 39204043768](https://github.com/dancollier-git/south-devon-wind/actions/runs/39204043768).
Code commit: `2ea5f8a232ffd7edb39ea7c0991e5175e00d944c`; published data commit: `cd84a0b`.
All 29 tests passed in the runner. Both NCI retrieval and all five forecast sources succeeded.
All five Pages JSON endpoints returned HTTP 200 and matched the data commit exactly.
All 58 prior observation records survived unchanged; this run added record 59.
weather.py, record.py and accuracy.py hashes were unchanged. Archives are preserved.

Assessment snapshot: 2026-10-19T05:20:47.046672+00:00. These are forecasts available at that time, not later observations.

[Live assessments](https://dancollier-git.github.io/south-devon-wind/assessments.json) update hourly.

## Resulting seven-day windows

All times UK local: BST through Saturday 24 October, GMT on Sunday 25 October.
No confirmed GO: every current window has WAVE HEIGHT UNVERIFIED, TIDE UNKNOWN and LAUNCH UNVERIFIED.

| Date | South Milton session windows | Overall label | Sustained wind | Maximum gust |
|---|---|---|---|---|
| 2026-10-19 | None qualifying | NO GO | — | — |
| 2026-10-20 | None qualifying | NO GO | — | — |
| 2026-10-21 | 08:00–11:00; 11:00–14:00 | GO CANDIDATE | 25.7–28.6 kt; 21.4–24.3 kt | 47.4 kt; 40.2 kt |
| 2026-10-22 | None qualifying | NO GO | — | — |
| 2026-10-23 | 08:00–11:00; 11:00–14:00 | HEADS-UP | 32.5–32.9 kt; 31.3–32.3 kt | 53.5 kt; 52.7 kt |
| 2026-10-24 | 12:00–15:00; 15:00–18:00 | HEADS-UP | 13.2–13.6 kt; 14.0–14.4 kt | 22.9 kt; 23.7 kt |
| 2026-10-25 | 07:00–10:00; 10:00–11:00 | HEADS-UP | 18.7–19.4 kt; 18.6–18.6 kt | 32.3 kt; 32.4 kt |

Wednesday has strong wind candidates, with very gusty conditions requiring review. Friday is a very strong/gusty HEADS-UP only. Saturday is marginal WATCH wind at long range; Sunday has strong-candidate wind but remains HEADS-UP for timing.

Bigbury: no qualifying daylight WATCH/GO-candidate windows on any of the seven days under the owner’s NE–SE and >=15 kt rules. This is a forecast-specific result, not a permanent location rating.

## Accuracy and limitations

Prawle 0–24 h retrieval-lead band: 9 unique observations; signed bias -8.29 kt (forecast minus observation); MAE 8.29 kt; RMSE 8.35 kt; mean actual retrieval lead 1.08 h. Longer bands have no samples yet.
No bias correction is applied. The sample is small, the station is elevated, and neither beach is calibrated by these station errors.

Local tide predictions are not connected: ADMIRALTY onboarding/key and public-use rights must be arranged, with a verified local station. See [TIDE_ACCESS.md](TIDE_ACCESS.md). No low-tide times or reef exposure are invented.
No licensed breaking-wave feed or on-site launch checks are connected. Open-Meteo offshore swell remains separate and is never converted into Surfline breaking-wave ranges.
Wind thresholds are owner supplied; the configurable NW sector edge of 337.5°, review-only gust/strength flags, daylight approximation and +/-90 minute future tide-ranking heuristic are implementation assumptions documented in README.md.
Each window is 1–3 hours; adjacent windows can represent a longer continuous opportunity but remain separately assessed. Days 4–7 are HEADS-UP regardless of favourable wind strength. Forecasts, gusts and windows may change.
