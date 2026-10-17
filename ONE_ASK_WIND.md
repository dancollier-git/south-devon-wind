# One-ask Prawle Point wind check

Investigated and demonstrated on 17 October 2026.

## Finding and recommendation

One-request operation is technically achievable in the ChatGPT/Codex session used for this investigation. The existing connected GitHub tools plus the session's functions.exec orchestration completed trigger → wait → poll → read before the assistant's final answer. No new infrastructure, account, subscription, token, or checker changes were needed.

This demonstrates this session's capabilities, not a global change to ChatGPT. A repository file cannot install instructions or tools in other chats. Keep the following procedure in the relevant chat/project instructions and use a mode exposing GitHub comment writes, GitHub API reads, and same-turn execution/waiting. The exact shorter phrase “Check the wind at Prawle Point” has not been separately tested in a new ordinary ChatGPT chat.

## Reusable chat/project instruction

When I ask to check the wind at Prawle Point:

1. Read docs/latest.json and docs/history.json from dancollier-git/south-devon-wind; record the baseline and existing issue_comment workflow run IDs.
2. Post exactly /wind to issue #1 through the connected GitHub comment tool. Record the returned comment ID, then GET that comment for its server-created timestamp and author. The author must be dancollier-git.
3. Keep this conversation turn active. Wait about 20 seconds using available execution orchestration. List workflow runs using GET https://api.github.com/repos/dancollier-git/south-devon-wind/actions/runs?event=issue_comment&per_page=10 via GitHub fetch.
4. Select the new wind.yml issue_comment run created after the comment, excluding baseline IDs. Poll that run every 10–15 seconds, with a bounded total wait such as 180 seconds. Do not post another command to poll. If no unique candidate exists, report ambiguity instead of assigning an unrelated run. GitHub's run listing does not include the originating comment ID.
5. Require completed/success and a successful publish job, including NCI retrieval, history commit and Pages deployment. Inspect that job's logs for its resulting observation commit.
6. Read docs/latest.json at that immutable commit, not just cached Pages or mutable main. Require retrieved_at later than the trigger. For a claim that the station observation itself is newer than the request, also require observation_time later than the comment timestamp. Reject missing timestamps, errors, stale data and warnings as fresh usable results.
7. Return sustained wind, recent gust, direction and source observation time in the same final response. Label the 10-minute average and latest dial reading separately. If the station has not updated, say so; a fresh fetch does not create a new sensor measurement. If the wait expires or a workflow fails, report that accurately in this turn, never return the baseline as a new observation.

These are instructions for the assistant, not an executable GitHub workflow or a guarantee that every ChatGPT mode will follow them.

## Live proof

The original investigation request was the only user message needed for this sequence:

- Baseline: 20 history entries; previous published observation was 18:44:05 UTC.
- Trigger: [comment 6238921133](https://github.com/dancollier-git/south-devon-wind/issues/1#issuecomment-6238921133), exact /wind, author dancollier-git, created 18:50:04 UTC.
- New [run 39059838774](https://github.com/dancollier-git/south-devon-wind/actions/runs/39059838774), created 18:50:07 UTC. It was the sole new issue_comment run found against the baseline. This is temporal correlation, not a comment-ID field in the Actions API.
- Orchestration actually waited 20 seconds, listed runs (in_progress), waited another 10 seconds, and read the specific run (completed/success).
- Run updated/completed at 18:50:32 UTC: 28 seconds after trigger. Both authorize and publish succeeded; 11 offline tests passed.
- NCI observation: 18:50:05 UTC / 19:50:05 BST, one second after the trigger; retrieval: 18:50:21.451827 UTC.
- Sustained 10-minute wind 13.9 knots; latest dial 14.8 knots; gust 16.5 knots; bearing 5 degrees; dominant direction N. No warnings, status ok.
- [Observation commit 817a44f5209f38d800414c226498cc00b8d9a2ef](https://github.com/dancollier-git/south-devon-wind/commit/817a44f5209f38d800414c226498cc00b8d9a2ef) appeared in this run's publish logs and changed only latest/history JSON.
- Immutable-commit JSON matched the connector result. Public Pages latest.json returned HTTP 200 and the same reading after deployment.
- History grew from 20 to 21, with all prior records identical and in order.
- No second user message was required. The final response to this original request includes the observation.

No production code was necessary: the proof of concept was session orchestration of existing tools. This document is the only added repository implementation guidance. Hourly cron (17 * * * *), JSON structures, existing observations, thresholds, Python retrieval methodology and Pages publication remain unchanged. The live test appended one genuine observation through the existing workflow.

## Connector capabilities and limits

The exposed github_add_comment_to_issue tool accepts issue #1 despite its pr_number parameter name. github_fetch supports GET on Actions run collections and individual runs; github_fetch_workflow_run_jobs and github_fetch_workflow_job_logs provide completion and commit evidence. github_fetch_file supports immutable commit refs.

Do not use github_fetch_commit_workflow_runs here: its documented wrapper filters to pull-request-triggered runs. No workflow-dispatch tool was exposed; the existing issue command solves that gap.

The GitHub connector does not itself sleep or make a comment call synchronous with Actions completion. functions.exec supplies waiting and sequential connector calls. Individual GitHub requests returned promptly; the waits occurred in orchestration, not inside a hanging connector call. No undocumented connector timeout or universal ChatGPT total-turn limit was established. A blanket “ChatGPT cannot wait 30–45 seconds” would contradict the live test.

In another ChatGPT surface, the minimum missing capability is an active same-turn orchestrator that can delay, repeatedly call authorized GitHub reads and continue until completion. A generic HTTP URL alone does not supply that capability. Ending the final answer ends this opportunity; a webhook or later automation notification is not the original response.

GitHub concurrency can replace pending requests, runner queues can delay work, and another command can make temporal run matching ambiguous. This PoC was isolated and does not establish reliable concurrent per-comment attribution. Solving that generally would need a request ID in a separate run result/artifact or other correlation mechanism, outside this minimal unchanged-workflow proof. Do not infer success from workflow success alone: the station can return an unchanged/old reading.

## Alternatives assessed (not deployed)

| Option | How ChatGPT would invoke it | Accounts/cost | Security, maintenance and latency |
| --- | --- | --- | --- |
| Existing GitHub + active orchestration (recommended) | Connected comment write, then delayed GitHub fetch calls in the same turn | Existing access only; no additional infrastructure charge for this proof | Existing owner-only command authorization; no new secrets. About 30–60 seconds expected including polling, based on prior 30–45 second runs; this run completed in 28 seconds. Queue delays unbounded. Lowest maintenance. |
| Cloudflare Worker | Register a Worker-backed MCP tool as a custom ChatGPT connection, or configure a custom GPT Action with its OpenAPI schema and auth. A bare Worker URL is insufficient. | New Cloudflare account and eligible ChatGPT custom-tool access. Workers Free currently offers 100,000 requests/day with a 10 ms CPU budget; tiny low-volume orchestration may fit but must be profiled. Paid Workers starts at $5/month if needed. | Store a repository-scoped GitHub credential as a Worker secret, authenticate callers, rate-limit and allowlist the repository. It can orchestrate the existing workflow without changing Python. Similar Actions latency plus network overhead; adds OAuth/key management and service maintenance. |
| Pipedream | Expose an appropriate MCP tool and connect its MCP server to ChatGPT, or attach an authenticated HTTP workflow as a custom GPT Action. An HTTP trigger alone is insufficient. | New Pipedream account and ChatGPT connection/configuration. Current Connect pricing advertises free development, paid production; do not assume an old free-workflow allowance applies. Verify the selected product/account before adopting. | Managed GitHub auth can reduce token handling; restrict tools, endpoint access and logs. Must explicitly return the completed observation rather than an immediate webhook acknowledgement. Similar workflow latency plus orchestration overhead. Not tested or recommended over the working GitHub approach. |
| Custom MCP server | Connect a remote HTTPS MCP endpoint through ChatGPT's custom server/plugin flow; expose check_prawle_wind returning the completed result, or bounded start/status tools that ChatGPT continues calling in the same turn | Hosting/account and supported ChatGPT plan/workspace permissions. Software can be free; hosting varies and no general free allowance is assumed. | OAuth or supported protected connection, least-privilege GitHub access, limits and timeouts. Could wrap existing GitHub execution to preserve methodology and publication. Similar 30–60 second expectation, not measured. Most code/auth maintenance unless hosted on an existing service. |
| Direct NCI read using existing execution | An available network-execution tool runs the unchanged weather.py and returns its output | No new service account; tool/network capability required | Simpler for a read alone, but does not prove the existing GitHub recording/publication path. Not substituted for the requested end-to-end test. |

A single long custom GPT Action that waits for GitHub is fragile: OpenAI documents a 45-second round-trip timeout. Use bounded calls/start-status polling within one turn if pursuing Actions; that still requires the assistant to continue. The 45-second Action rule is not evidence of the same timeout for the built-in GitHub connector or MCP.

Custom MCP connection eligibility depends on the actual account, surface and workspace policy. Current OpenAI guidance distinguishes full MCP write access for Business/Enterprise/Edu and Pro read/fetch permissions. This session demonstrably exposes GitHub writes; it cannot establish what an unrelated ordinary chat exposes. Triggering a GitHub run must not be mislabelled as a read-only MCP action to bypass those controls.

## Sources

- [Existing workflow](https://github.com/dancollier-git/south-devon-wind/blob/main/.github/workflows/wind.yml)
- [GitHub Actions workflow run API](https://docs.github.com/en/rest/actions/workflow-runs#list-workflow-runs-for-a-repository)
- [OpenAI custom MCP connection and account guidance](https://help.openai.com/en/articles/12584461-connecting-custom-mcp-servers-in-chatgpt)
- [GPT Actions production limits](https://developers.openai.com/api/docs/actions/production)
- [Cloudflare Workers pricing](https://developers.cloudflare.com/workers/platform/pricing/)
- [Cloudflare Workers limits](https://developers.cloudflare.com/workers/platform/limits/)
- [Pipedream current Connect pricing](https://pipedream.com/pricing)

No alternative service was deployed, no subscription purchased, and no universal ChatGPT behaviour change is claimed.
