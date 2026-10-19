# South Devon wind

Hourly NCI Prawle Point wind observations, recorded by GitHub Actions and published as JSON with GitHub Pages.

- [Latest JSON](https://dancollier-git.github.io/south-devon-wind/latest.json)
- [Observation and failure history](https://dancollier-git.github.io/south-devon-wind/history.json)
- [Workflow runs](https://github.com/dancollier-git/south-devon-wind/actions/workflows/wind.yml)
- [Original NCI weather page](https://www.nci-prawlepoint.org.uk/weather-gauges/)

## Implementation

`weather.py` reuses the Python standard-library checker developed in the Codex workspace at `/workspace/weather-investigation/weather.py`. It performs one unauthenticated GET to https://nci-prawlepoint.org.uk/scripts/wx-data.php, the JSON endpoint used by the original page's JavaScript. No API keys, cookies, browser automation or image recognition are needed. TLS verification stays enabled. No retries are made.

`record.py` runs that checker and writes `docs/latest.json`, appending every attempt (including failures) to `docs/history.json`. Git tracks the history; Pages serves the committed JSON. History grows over time and may eventually need archiving. The test fixture is a genuine saved observation from 16 October 2026, used only for offline tests; it is never published as a new reading. No fabricated initial observations are included.

| JSON field | Source/meaning |
|---|---|
| `wind_speed_knots` | `wspeed`, 10-minute average sustained wind |
| `latest_wind_speed_knots` | `wlatest`, wind-speed dial reading |
| `gust_knots` | `wgust`, recent gust, labelled 10 minutes on original page |
| `direction_degrees` | `bearing`, direction dial bearing |
| `average_direction_degrees` | `avgbearing` |
| `dominant_direction` | `domwinddir`, summary compass direction |
| `observation_time` | `obstime`, normalized to UTC; original offset retained in `observation_time_raw` |
| `retrieved_at` | Checker retrieval time |
| `age_seconds`, `stale`, `warnings` | Freshness and source quality at retrieval |
| `status` | `ok` or `warning` |
| `wind_alert` | True only for a fresh usable sustained reading >=20 knots |

The feed normally reports `windunit=kts`; supported alternate units are converted. Today's maximum gust (`wgustTM`) is not the recent gust. Freshness is calculated from the observation timestamp, not the HTTP response or `timeUTC`. Observations older than 600 seconds warn; missing timestamps have unknown freshness. Sensor faults and other warnings suppress wind alerts. A gust alone never triggers the sustained-wind alert.

A network/HTTP/parse failure is published as an error record instead of silently retaining an old reading as current. An unhealthy feed also fails the workflow after publishing its warning. When reading previously published JSON, recalculate age against the current time: `stale` describes the collection time and does not update itself. Check workflow status if the JSON has stopped changing.

## Schedule and permissions

The workflow runs at minute 17 of every UTC hour, on manual dispatch, and on relevant code pushes. GitHub schedules can be delayed or skipped and may be disabled after 60 days of inactivity in a public repository. This samples wind hourly; it cannot detect every threshold crossing between samples. `wind_alert` is machine-readable; this repository does not send push/SMS/email wind alerts. GitHub's own workflow failure notifications are separate.

Only the built-in `GITHUB_TOKEN` is used, with `contents: write` to record data, `pages: write` and `id-token: write` to deploy Pages. No personal token or NCI secret is stored. Pages must use the **GitHub Actions** build source; the `github-pages` environment must allow deployments from main.

Public accessibility does not establish an unrestricted data licence or quota. Use remains one direct feed request per workflow run; confirm acceptable use with NCI for broader redistribution. NCI's lookout is about 60 metres above sea level, so its winds can differ from conditions on the water. This project is not an official NCI service.

## Local use

Requires Python 3.12 (no third-party Python dependencies):

```sh
python weather.py                   # one live reading, no files written
python record.py                    # one live reading, update publication files
python -m unittest discover -s tests -v  # offline, no NCI requests
```

## Verified deployment

Verified on 17 October 2026 in [GitHub Actions run 39014537987](https://github.com/dancollier-git/south-devon-wind/actions/runs/39014537987). All seven offline tests passed, the runner fetched NCI directly, committed the observation, and deployed Pages successfully. Both public JSON endpoints returned HTTP 200 after deployment.

The genuine observation at 08:40:43 BST (07:40:43 UTC) reported sustained wind 10.4 knots, latest wind 10.4 knots, gust 14.8 knots and direction N / 355 degrees. It was 22.1 seconds old at collection, with no warnings and wind_alert=false. This is a historical validation example, not a claim about current conditions.

Initial setup encountered an integration permission denial for Pages administration. The owner enabled Settings → Pages → Source → GitHub Actions; the next workflow succeeded. No NCI access restrictions were encountered in the two runner fetches. This verifies functionality, not long-term uptime or weather measurement accuracy.

GitHub emitted non-blocking notices about older action Node.js targets (automatically run on Node 24) and an upcoming ubuntu-latest image migration. The validated run passed; maintain action versions and rerun checks as runner images change.

## On-demand checks

Manual triggering is already enabled by `workflow_dispatch` in the existing workflow. In GitHub, open **Actions → Record and publish wind → Run workflow**, select `main`, and run it. The same job, checker, history recording and Pages deployment are used for manual and hourly runs; manual dispatch does not change the schedule or thresholds.

From an already authenticated Codex environment with GitHub Actions write access:

```sh
gh workflow run wind.yml --repo dancollier-git/south-devon-wind --ref main
```

Wait for that specific new run to finish successfully, then read `latest.json` and confirm its observation timestamp is fresh. Do not assume an existing Pages response belongs to the requested run; compare its JSON to the record committed by that run. A manual observation may legitimately share a timestamp with the previous observation if the station has not yet updated. Avoid rapid repeated requests.

### ChatGPT integration

The GitHub connector tools exposed during the 17 October 2026 check do not include a workflow-dispatch operation. Available rerun operations are not a substitute for dispatching the current `main` workflow. The authenticated GitHub CLI in the Codex workspace can dispatch it without a new credential; that is distinct from connector-only access in an ordinary ChatGPT chat. An immediate conversational request requires an active chat/agent with this CLI capability; hourly execution remains entirely hosted by GitHub.

ChatGPT can now request a fresh observation by posting exactly `/wind` as a new comment on [issue #1](https://github.com/dancollier-git/south-devon-wind/issues/1), using its GitHub connector. The comment must be attributed to `dancollier-git`. Other senders, issues, pull requests, edited comments, uppercase commands, leading/trailing whitespace or additional text do not authorize a check. Keep issue #1 open as the permanent command interface.

The workflow's authorization job reads the event payload as JSON without executing comment text and has no token permissions. Unauthorized events skip the recording job and do not enter its concurrency queue. The existing recording/publishing job alone has `contents: write`, `pages: write` and `id-token: write`; no issue-write permission, external service or new credential is required. Authorized comment, manual, push and hourly runs share the `wind-publication` concurrency group and do not cancel a running job. Each recording job checks out current `main` after it acquires the slot, avoiding writes based on an older queued commit. GitHub concurrency can replace an older pending request when several requests arrive together; do not treat this as a guaranteed per-comment queue.

Manual dispatch was reverified in [run 39058328360](https://github.com/dancollier-git/south-devon-wind/actions/runs/39058328360): all tests, NCI retrieval, history commit and Pages deployment succeeded. Both public JSON files returned HTTP 200 and matched the committed data. The genuine observation was 19:29:04 BST on 17 October 2026, sustained 13.0 knots, gust 15.6 knots, bearing 355 degrees, dominant direction N. All 13 prior history records were preserved, with one new record appended. Checker, recorder and workflow file hashes were unchanged. The five preceding scheduled runs were successful and the workflow remained active.

### Issue-command validation

On 17 October 2026, ChatGPT posted the command through its existing GitHub connector, attributed to `dancollier-git`. [Exact `/wind` test run 39058927707](https://github.com/dancollier-git/south-devon-wind/actions/runs/39058927707) passed authorization, all 11 tests, NCI collection, history recording and Pages deployment. The real observation at 19:37:04 BST was sustained 13.0 knots, gust 16.5 knots, direction N / 360 degrees, 49.7 seconds old at retrieval. Both published JSON endpoints returned HTTP 200 and matched the committed files. All 14 prior history records remained intact; the code-push validation and command run appended two records. The checker and recorder hashes were unchanged.

A live [uppercase `/WIND` rejection run](https://github.com/dancollier-git/south-devon-wind/actions/runs/39058901825) completed authorization but skipped collection/publication. Offline tests exercised the exact authorization code against other users, issues, pull requests, edited events, whitespace, missing fields and incorrect commands; those were rejected. No other user's identity was impersonated for testing. The hourly cron remains `17 * * * *`, the workflow remains active, and issue #1 remains open.

## South Devon forecast archive

Read [FEASIBILITY.md](FEASIBILITY.md) for the access investigation and source
limitations. XCWeather and Surfline collection is disabled: their public sites
do not establish permission to automate and republish their forecasts.
Open-Meteo's documented non-commercial APIs provide the initial implementation.
If this project becomes commercial, arrange an appropriate paid API contract
before continued collection. Data is attributed in each publication and Pages.

The existing hourly job now collects five forecasts after recording NCI, even
when the observation failed. Each source retries transient failures at most
twice, with timeouts and schema/unit checks. A failed source publishes an error
with empty rows, never an old forecast labelled current. Successful sources
survive partial failures. Publication precedes the final failing health step.
The NCI checker/recorder and their JSON formats remain unchanged.

- `archive/forecasts/YYYY-MM-DD.jsonl`: append-only attempts in git, including raw
  responses, requested/returned coordinates, UTC retrieval and valid times,
  source, units and model selection. Issue time is explicitly null because the
  standard API doesn't provide it. Forecast snapshots are not model-run archives.
- `docs/forecast.json`: compact current attempt, with all valid hours and source
  errors. Bigbury wind coordinates represent the Bantham/Bigbury area; South
  Milton and Prawle have separate requested coordinates (approximate WGS84 in
  `forecast.LOCATIONS`). Coastal grid cells may differ materially from the beach.
- `docs/assessments.json`: hourly assessments and seven Europe/London calendar-day
  summaries, with the best viable daylight session windows and reasons.
- `docs/accuracy.json`: Prawle speed bias (forecast minus observed), MAE/RMSE and
  counts by 24-hour retrieval-lead band. It uses fresh usable observations only,
  deduplicates station timestamps and excludes hindsight. No backfilled forecasts
  or automatic threshold adjustments. Zero samples produce null scores.

Forecasts are unhealthy after three hours. Run `python forecast_health.py` to
recalculate freshness; clients must likewise compare `retrieved_at` and
`generated_at` with their current clock. Static JSON cannot update itself if
Actions stops. Provider model age is unknown, separately from retrieval age.
Archive growth is unbounded: at hourly cadence this can consume hundreds of MB
yearly. Monitor repository size and migrate old daily files to durable object
storage before git size becomes a problem; never silently delete history.

### Owner calibration (19 October 2026)

`config/wingfoil.json` contains the owner's actual wind calibration. Forecast
speeds are **not bias-corrected**. Prawle accuracy reporting remains separate.

| Location/direction | NO GO below | WATCH | GO candidate | Strong candidate |
|---|---:|---:|---:|---:|
| South Milton SW–W (225°–270°) | 13 kt | 13 to <16 | 16 to <18 | >=18 |
| South Milton NW (315°) | 16 kt | 16 to <19 | 19 to <21 | >=21 |
| Bigbury NE–SE (45°–135°) | 15 kt | 15 to <18 | >=18 | — |

For WNW, all South Milton speed boundaries increase linearly from W to NW
(+0 to +3 kt). The NW allowance extends to 337.5° (the conventional NW compass
sector edge), holding the +3 kt adjustment beyond 315°; this configurable sector
edge is an implementation assumption rather than a new owner wind threshold. S/SSW (180° to <225°) is WATCH if >=13 kt, otherwise insufficient
wind. Unsupported directions are NO GO under this owner's current calibration.
No wind or gust ceiling is imposed. Review flags at sustained >=35 kt, gust
>=45 kt or gust spread >=15 kt are explicit provisional **review heuristics**,
not owner limits, safety guarantees, or automatic downgrades. Hazardous launch
information or dangerous breaking waves can override otherwise excellent wind.

Breaking-wave preferences: 2–4 ft generally manageable; 4–6 ft potentially
excellent; upper bound >6 and <10 ft CAUTION/WATCH (including 6–8); upper bound
>=10 ft NO GO (including 6–10 and 8–12, conservatively covering other very large
ranges). These bands apply only to attributed breaking-wave data, never
Open-Meteo swell or combined significant wave height. Missing breaking waves
retain wind-based candidates with **WAVE HEIGHT UNVERIFIED**. Fully confirmed GO
requires genuine breaking-wave and local launch checks, and for South Milton
local reef confirmation. No live breaking-wave or launch-confirmation source is
connected, so live output remains provisional.

Each hour includes UK local date/time with numeric UTC offset and BST/GMT label,
location, sustained/gust/direction, separate wind suitability, offshore swell
height/period/direction, breaking range (null when unavailable), tide state,
launch suitability, wave-riding potential, overall recommendation, confidence,
reasons and cautions. `status` remains an alias of the overall recommendation.
Assessments use schema version 2; forecast/observation JSON endpoints are retained.

Days 1–3 publish actionable WATCH/GO-candidate sessions; days 4–7 label promising
sessions HEADS-UP while preserving underlying wind suitability. Each day lists
up to two non-overlapping 1–3 hour windows: first favour the strongest minimum
wind suitability, then duration, proximity to predicted low tide at South Milton,
and morning sessions. Remaining ties prefer the earlier start. Afternoon
unsuitability cannot hide a good morning. Only complete future hourly blocks
with the sun above the horizon at both ends are selected. Daylight uses the
[NOAA solar approximation](https://gml.noaa.gov/grad/solcalc/solareqns.PDF),
not a fixed clock-hour rule. The day of the October clock change has 25 local
hours; UTC iteration preserves both 01:00 occurrences. A day with no viable
remaining full daylight session says so, even if wind is suitable at night.

Tides remain **unknown**: see [TIDE_ACCESS.md](TIDE_ACCESS.md). Bigbury can work
at any tide, with launch checks. South Milton's low-tide reef shelter is a
positive, never inferred from strong wind or offshore waves. Internal support
for a future licensed local tide adapter reports nearest low and rising/falling
state; +/-90 minutes is only a ranking heuristic, not a reef exposure guarantee.
Fresh, attributed predictions require verified local station coverage. The
production collector has no such feed and does not publish invented tide times.

Local commands: `python forecast.py` collects and writes the archive/publication;
`python forecast_health.py` checks current files; the existing unittest discovery
runs all offline tests. Live source verification and deployment details follow.


### Initial verification on 18 October 2026

All 20 offline tests passed, covering existing NCI behaviour, command
permissions, forecast units/timestamps/schema, bounded retries, failed-attempt
publication, missing sources, assessment gates, freshness and accuracy matching.
A live local run fetched all five documented APIs successfully (168 valid hours
each); the first real snapshot is included in the archive. Both marine locations
returned the same coarse offshore cell: this is not beach-specific surf data.
The forecast health check passed. No live forecasts were fabricated.

The existing hourly workflow and Pages source are reused. A deployment is only
verified when a specific GitHub Actions run and its published JSON are checked;
local tests alone do not establish hosted execution.


### Calibration deployment verified — 19 October 2026

[CALIBRATION_REPORT.md](CALIBRATION_REPORT.md) records the successful deployment,
29 passing tests, published seven-day windows, endpoint checks and the current
small-sample accuracy metrics. All observation history was preserved.

## Daily report tide context and personal gear learning

[DAILY_REPORT.md](DAILY_REPORT.md) is the reusable procedure for reports requested
in chat: consult current ADMIRALTY tide information, cite the source and align it
with UK-local wind session windows. Official Met Office beach pages displaying
ADMIRALTY predictions provide an accessible fallback to EasyTide. Name the actual
reference station (currently Salcombe) and explain uncertainty at South Milton.
Tides are report context, not a new archived dataset. The hourly JSON still shows
TIDE UNKNOWN until an automatic feed is separately configured. This document does
not create scheduled report delivery or install instructions in other GPT chats.

The owner's actual wing and foil choices, performance comments and retrospective
better choices will inform personal recommendations over time. The procedure
keeps these separate from forecasts and Prawle measurements.


## Existing 05:00 ChatGPT forecast task

The owner confirms the active **Local Wind & Swell Check** ChatGPT task runs at
**05:00 Europe/London**, reading:

- https://dancollier-git.github.io/south-devon-wind/forecast.json
- https://dancollier-git.github.io/south-devon-wind/assessments.json

No additional scheduler is needed. The task is managed in ChatGPT; this
repository does not change its instructions or claim to inspect its delivery.
The hourly Actions cron stays `17 * * * *` UTC (local :17 under both BST/GMT).
05:00 London is 04:00 UTC during BST and 05:00 UTC during GMT. The prior hour's
scheduled run supplies the morning report, subject to GitHub scheduling delays.
On 19 October, recent scheduled starts were around :33–:53 rather than :17, so
neither exact start time nor guaranteed publication before 05:00 is promised.

Every successful collection regenerates both files from the same snapshot time,
archives forecasts, then commits and deploys `docs` to Pages. The serialized job
checks out current main; observation and forecast failures are published before
the final source-health failure. After deployment, `publication_check.py` fetches
both public files and compares their full JSON against this run, using unique
query parameters and bounded retries to allow CDN propagation. A mismatched,
unreachable or old publication fails the workflow; published source failures
are still checked separately. The check adds no weather/tide requests.

The report should recalculate age from `forecast.json.retrieved_at` and
`assessments.json.generated_at`. Older than three hours, future timestamps,
source errors or mismatched generation times must be called out rather than
presented as current. Retrieval freshness does not establish model-run age.
Tides remain live report context as described in DAILY_REPORT.md.

## Permanent owner session log — ChatGPT handover

**Repository:** `dancollier-git/south-devon-wind`  
**Canonical owner observations:** [`data/sessions.json`](data/sessions.json)

When the owner says “log my session”, “I went wingfoiling”, “I SUP surfed”, or provides a retrospective observation, ChatGPT should use its connected GitHub tools to read this README and the **latest** `data/sessions.json`, then append a structured entry and commit the updated file to the same repository. This is the persistent source of truth across conversations, **not** ChatGPT's memory or the forecast archive. Confirm the successful commit and link the record; never say it was saved before the GitHub write succeeds. If write access is unavailable, clearly say it was not saved and offer a copyable entry for later submission.

### Recording rules

- Accept informal, conversational or voice-dictated observations; do not require a form. Clarify only essential ambiguity such as which day or spot; leave other missing values `null` or absent, never invent details.
- Store an entry in the top-level `sessions` array, keeping `schema_version` and existing entries unchanged. Suggested fields: `id` (stable unique date/spot/session identifier), `date_local` (YYYY-MM-DD), `location`, `sport` (`wingfoil` or `sup_surf`), `start_local`, `end_local`, `gear` (board, wing, front foil, mast, paddle as applicable), `observations` (felt wind, gusts, direction, swell, breaking surf, tide, launch, quality, difficulty), `rating_1_to_5`, `notes`, `recorded_at` and `source`: `owner_reported`. Keep units explicit when known.
- Preserve the owner's original words in `notes` as closely as practical, with concise structured interpretation separately. Mark estimates and subjective judgements as such. Do not turn felt wind into measured wind or offshore swell into breaking surf.
- Avoid duplicates: check for an existing entry with the same date, spot, sport and time; amend that entry only if the owner is correcting or extending it. For any update, first fetch the current blob SHA and use GitHub's SHA-checked file update; on conflict, re-fetch and merge rather than overwriting someone else's entries.
- Where available, attach the **forecast issued before the session**, its retrieval timestamp and the applicable forecast hour, distinguishing it from later forecasts; never use a hindsight forecast as if it had been available beforehand. If a pre-session snapshot cannot be verified, leave forecast comparison unknown. Keep forecast/observations distinct.
- Do not modify the hourly forecast collector or its automated files when recording a session. The session log is manual owner-confirmed evidence, not a live weather feed.

### Using the history

Before personalised recommendations, read this log alongside current `docs/forecast.json`, `docs/assessments.json` and `config/wingfoil.json`. Compare the owner's reported enjoyment, gear choices and real launch conditions against the *contemporaneous* forecast where possible. Treat small samples cautiously and **do not** silently change wind thresholds or assert a proven calibration from one session. The owner can request corrections or deletion of a session entry.

**Quick prompt:** “South Milton this morning, 10–12, 4.5 m wing and 900 foil. Gusty but brilliant, launch flat. Log that.”
