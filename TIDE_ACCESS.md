# Local tide prediction access — checked 19 October 2026

The authoritative route investigated is the [ADMIRALTY UK Tidal API](https://www.admiralty.co.uk/access-data/apis).
The [government API catalogue](https://www.api.gov.uk/ukho/uk-tidal-api-discovery/)
describes standard/secondary-station tidal-height predictions. ADMIRALTY's
[developer portal](https://developer.admiralty.co.uk/products) provides Discovery,
Foundation and Premium subscriptions. API onboarding/subscription and an access
key are required; the project's collector has no configured key or licensed
local-station contract. Before publishing data, confirm the chosen product's
public redistribution/storage terms and a station covering these beaches. Do not
transfer Plymouth predictions to South Milton without validated local corrections.

[EasyTide](https://www.admiralty.co.uk/access-data/tidal-data/easy-tide) provides
free seven-day predictions for people checking port tide times, and explicitly
points integrations to the APIs. Free viewing does not establish permission to
scrape and republish. No EasyTide scraping was implemented.

Environment Agency [tide-gauge API](https://www.api.gov.uk/ea/tide-gauge/) supplies
observations, not the required local seven-day predictions. Open-Meteo marine
sea-level predictions use a coarse offshore grid and cannot establish local reef
exposure or chart-datum water depth; they have not been substituted for a local
prediction service. No reliable, permitted and configured local prediction feed
was established in this session.

## Current output

`tide.state` is `unknown`, `nearest_low_local`, `minutes_from_low` and `near_low`
are null, and cautions include TIDE UNKNOWN. Wind candidates remain visible.
Morning is a preference when wind is suitable. No actual near-low-tide claim is
made. South Milton launch/reef checks remain unverified; Bigbury is not tide-gated.

## Future integration contract (not connected)

`assessments(..., tides=...)` accepts an internal location-keyed prediction bundle
from a future permitted adapter. It requires source attribution, retrieval time
(maximum age 24 hours), verified local station applicability, prediction coverage,
and alternating high/low UTC events. No network feed or owner-editable simulated
times are configured. It reports nearest low and rising/falling state within
coverage. Near low means +/-90 minutes for **ranking only**; +/-30 minutes labels
low tide. Those are planning heuristics, not water-depth or reef-safety thresholds.
Even reliable predictions cannot confirm current launch safety, surge or reef
exposure; those checks must come from current local knowledge.
