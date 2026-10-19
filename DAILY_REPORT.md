# South Devon daily wingfoiling report

Owner preference agreed 19 October 2026: tide information is consulted live for
reports requested in chat, separately from the forecast archive. The archive is
for comparing forecasts/observations with actual sessions and learning personal
wing/foil choices. It does not need a copy of third-party tide predictions.

The owner confirms an existing active ChatGPT task, **Local Wind & Swell Check**,
runs at **05:00 Europe/London** and now reads the public forecast.json and
assessments.json endpoints. That task owns report delivery; do not create a
separate Codex scheduler. This repository supplies hourly data and the reusable
report procedure, not an automatic tide API connection. A reporting assistant
needs web access to consult live tides.

## Read the current forecast

Read `docs/forecast.json`, `docs/assessments.json`, `docs/latest.json` and
`docs/accuracy.json` (or their live Pages endpoints). Recalculate freshness using
the current clock, rather than trusting the saved stale flag. Use the owner's
calibration in `config/wingfoil.json`. Keep forecast wind separate from actual
Prawle observations; no automatic bias correction. Preserve strong-wind
candidates and show review cautions. Days 1–3 are actionable provisional windows;
days 4–7 remain HEADS-UP for timing.

## Consult tides when preparing each report

Preferred source: [ADMIRALTY EasyTide](https://easytide.admiralty.co.uk/).
Select and verify the station and dates in the visible website. Use normal web
reading, not hidden endpoints, scraping software or access-control workarounds.

If EasyTide's interactive predictions cannot be read, consult the visible tide
section on these official Met Office pages carrying ADMIRALTY tidal data:

- [Hope Cove beach](https://weather.metoffice.gov.uk/forecast/gbvmb4te7): regional
  tide reference for the South Milton discussion, **not** a South Milton gauge.
  The page identifies Salcombe as its tide station, 3.9 miles from Hope Cove.
- [Bantham beach](https://weather.metoffice.gov.uk/forecast/gbvnp8zub): identifies
  Salcombe as its tide station, 6.0 miles from Bantham.
- [Bigbury-on-Sea](https://weather.metoffice.gov.uk/forecast/gbvnp3nvw): identifies
  Salcombe as its tide station, 6.4 miles from Bigbury.

These source/station labels were verified on 19 October 2026; recheck them when
reading a report. Met Office pages explicitly warn that the beach times may vary
from the reference station. Do not treat the three pages as independent local
tide models or invent an offset from Salcombe to South Milton.

Verify the actual date heading, the source's update date and its timezone before
using each event. Search-result snippets alone are insufficient. EasyTide offers
fixed GMT/GMT+1 display options which do not automatically change at the end of
BST. Normalize according to the explicit source setting and present times with
Europe/London (BST/GMT) for **each event date**, including the October change.
If a source's date, time basis or prediction cannot be verified, report tide
unknown and link the source instead of guessing.

Read only what is needed to explain the sessions, cite the page in the report,
and retain required source attribution: Contains ADMIRALTY® tidal data:
© Crown copyright and database right. Do not commit prediction tables, copy tide
curves, add tide events to hourly JSON/archives or create a scheduled tide scraper.
A future automated/public tide feed remains a separate API integration requiring
the relevant access and rights; this report procedure does not claim those exist.

## Include this tide section in the report

For each relevant session/day, include:

- Low/high water times relevant to the session, in UK local time, with predicted
  height if useful and actually supplied (metres above chart datum; not reef depth).
- Source link, named reference station, date checked, and any local proxy caveat.
- Whether the session is before, near or after the predicted low; show the actual
  time difference rather than inferring a precise beach water level.
- South Milton: prioritise suitable morning wind near predicted low where
  possible. Explain potential low-tide reef shelter and flatter launch water,
  while requiring local reef/depth/launch checks. The engine's +/-90 minute
  near-low convention is a planning aid, not a safe exposure guarantee.
- Bigbury: no tide veto; retain the owner's any-tide rule and launch checks.

Use the published wind windows as a starting point. If newly consulted tides
make another 1–3 hour daylight slot more attractive, check that slot's hourly wind
and swell and explain the revised suggestion. Label it as the report's live-tide
interpretation, not an update to the archived machine assessment. Public
`assessments.json` will still say TIDE UNKNOWN until a separate feed is connected.

Keep WAVE HEIGHT UNVERIFIED if no genuine breaking-wave forecast is available.
A tide prediction does not supply breaking-wave height or confirm launch safety.
Do not promote a candidate to confirmed GO on tide timing alone.

## Gear learning and session feedback

The owner will provide actual wing and foil choices, comments on how they felt,
and whether another choice would have been better. Match feedback by location,
local session date/time and timezone to forecast and Prawle observations. Keep
chosen equipment, observed performance and retrospective preferred equipment
separate. Ask for missing session identifiers as needed. Do not invent an
inventory, experience records or confident gear sizes before evidence exists.

## Short report format

Lead with the best location/session and provisional recommendation. Follow with
wind/gust/direction, live tide timing/source and reef implication, swell versus
breaking-wave uncertainty, launch cautions and a provisional gear suggestion only
where personal evidence supports one. Summarise other promising days and state
freshness or missing inputs. Include source links next to the tide claims.
