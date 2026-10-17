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
