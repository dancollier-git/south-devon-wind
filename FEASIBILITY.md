# Forecast feasibility — initial investigation 18 October 2026

**19 October calibration update:** Owner thresholds are now configured. The
assessment policy paragraphs below describe the initial implementation and are
superseded by [README.md](README.md#owner-calibration-19-october-2026). Missing
breaking-wave data now permits provisional wind candidates; 6–8 ft is caution,
6–10/8–12 ft remains NO GO. Daily summaries select daylight sessions.
See [TIDE_ACCESS.md](TIDE_ACCESS.md) for the local tide access investigation.

## Decision

Implement documented Open-Meteo weather and marine APIs for this personal,
non-commercial archive. Do not collect XCWeather or Surfline without a separate
written agreement covering automated access, storage and public redistribution.
No hidden endpoints, account cookies, scraping or access-control bypasses.

| Source | Access and permission | Data and limitations |
|---|---|---|
| XCWeather Bantham | No documented public forecast API or authentication contract found. [FAQ](https://www.xcweather.co.uk/Info/FAQ) explicitly asks users not to take its images or data for websites. Seek agreement via [contact](https://www.xcweather.co.uk/Info/Contact). Public visibility is not permission. | FAQ describes interpolated quarter-degree GFS, refreshed six-hourly. Wind, gusts and direction are displayed, but automated archive/redistribution permission is unestablished. Vaisala **Xweather** is a different service. |
| Surfline South Milton Sands / Bantham | [Terms](https://www.surfline.com/terms-of-use) prohibit automated extraction, unauthorised API access and significant content storage. No generally available licensed developer contract established in this investigation. A consumer subscription does not establish these rights. Ask Surfline about a licensed partnership, authentication, quotas and redistribution. | Desired beach breaking-wave minimum/maximum, swell height, period and direction require licensed access. No collector enabled. |
| Open-Meteo | Documented [weather](https://open-meteo.com/en/docs) and [marine](https://open-meteo.com/en/docs/marine-weather-api) JSON APIs. [Terms](https://open-meteo.com/en/terms): free API is non-commercial, no key; <10,000 calls/day, 5,000/hour, 600/minute. CC BY 4.0 data: credit Open-Meteo and providers, link licence, identify transformations. Commercial use requires a paid customer endpoint/key; not configured here. No uptime guarantee. | Hourly 10 m wind speed, gust, meteorological direction; combined significant wave height, swell height/period/direction. Seven-day output. Marine grid cells cannot resolve beach/reef bathymetry or breaking-wave ranges. Best-match blends may change; archive returned grid coordinates and raw payload. Not an exact reproduction of XCWeather or Surfline. |

Five forecast requests per scheduled run (three wind locations and two beach
marine locations), about 120/day, plus the separate existing NCI observation.
Bounded retries may increase that to 360/day. Shared GitHub runner IP limits can
still cause failures. APIs interpolate some native model timesteps to hourly.

## Timestamps, safety and accuracy

Standard forecast responses do not supply a trustworthy model issue timestamp.
Store `issue_time: null`, `issue_time_basis: unavailable`, and a separate UTC
`retrieved_at`; never call API execution duration (`generationtime_ms`) an issue
time. The archive preserves the exact forecast available at retrieval and its
valid times, not a single homogeneous model run. Forecast lead time in accuracy
reports is explicitly measured from retrieval. True model-run comparisons would
need a documented single-run source and model reference times.

Neither offshore significant wave height nor swell height is a breaking-wave
range. Never convert them into Surfline ranges. A future licensed breaking-wave
input with upper bound >=6 ft is conservatively NO GO (includes 6–10 and 8–12).
Missing breaking-wave data prevents GO. South Milton low-tide reef shelter must
be confirmed using local tide and reef knowledge: offshore models cannot certify
it. Swell indicates possible wave energy, not rideable or safe breaking waves.

No South Milton / Bigbury wind or tide thresholds were found in this repository.
Configuration remains unset pending the owner's values. HEADS-UP explains that
limitation; NO GO overrides it when a known limit is exceeded. Seven-day daily
summaries use the most restrictive hourly result; hourly windows remain visible.
GO means configured wind checks passed with confirmed small breaking waves;
South Milton additionally needs explicit low-tide shelter confirmation. It is
not a guarantee of on-water safety.

Prawle is an elevated observation site away from both beaches. Collect a Prawle
forecast at its own coordinates for validation, and distinguish station/model
bias from beach transfer error. Match fresh, warning-free subsequent readings
within 30 minutes; deduplicate observation timestamps; select the latest archived
forecast preceding a requested lead time (rather than counting every snapshot).
Report sample count, signed speed error, MAE and RMSE by lead band. Do not adjust
thresholds automatically from sparse or spatially mismatched data.

## Deployment and verification

Extend the existing serialized publication job, leaving weather.py and record.py
unchanged. Publish failures before failing health checks; one forecast failure
must not prevent NCI collection. Archive daily JSONL snapshots in git and publish
only compact latest/assessment/accuracy JSON on Pages. Preserve all observation
history. Readers must recalculate freshness at read time; scheduled Actions can
be delayed/skipped or disabled by GitHub inactivity policy. No SLA is implied.

Implementation and offline/live verification results are recorded in README.md.
