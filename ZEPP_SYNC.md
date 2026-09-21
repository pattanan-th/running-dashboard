# Zepp migration — 2026-09-16

Current watch: Amazfit T-Rex 3; iPhone; ZeppBridge 2.4.0 signed in via HAR import.
The HAR and credentials are local only, outside this repository. Never commit them.

## Daily sync
1. Sync the watch in Zepp on iPhone.
2. Run update_and_deploy.bat (now calls sync_zepp.py, not Garmin).
3. If ZeppBridge reports busy or failed, deployment stops. Wait for desktop sync to finish and retry.
4. --local-only imports the existing local database; use only after checking the bridge status.
5. When the user asks for sync, include Coach and latest run cards in the chat as well as the website.

## Data
sync_zepp.py reads a read-only SQLite snapshot of ZeppBridge's normalized tables.
ZEPPBRIDGE_DATA_DIR and ZEPPBRIDGE_CLI optionally override paths.
Original Garmin stats are retained in garmin_stats_archive.json; never regenerate that from Zepp.
Garmin runs, sleep and wellness remain in their original JSON files.
Zepp runs have source=zepp and prefixed IDs. Reimports update them without duplicating.
Daily health metrics include units and dates. Sleep uses the local wake date in Asia/Bangkok
and chooses the longest session; extra sleep minutes are retained separately.
Raw cloud payloads, GPS coordinates, user IDs and tokens are not exported.
Cross-source run dates overlapping the Garmin archive fail closed for manual reconciliation.

## Current boundaries
Best Efforts by Time ranks the furthest recorded distance in rolling 5, 10, 20,
30 and 60 minute elapsed-time windows. One result per run; interpolated endpoints,
pauses included, gaps over 15 seconds excluded. Zepp-only because the archived
Garmin summary has no distance timeline. Rebuilt automatically on every import.
Totals, Longest and Best Efforts by Distance combine Garmin + Zepp.
Zepp efforts use currentDistance from local workout_detail: delta seconds and cumulative
centimetres (validated against every workout total). Rolling windows interpolate distance
crossings; one fastest result per run/distance. Elapsed time includes pauses within windows.
Gaps over 15 seconds split the timeline; trailing samples past workout end are omitted.
One-second duplicate timestamps keep the final reading. Missing/invalid series are skipped
with an activity-level reason. Results are approximate recorded-distance efforts, not
Zepp-certified PRs. No raw payload or route is exported. Original Garmin ranks remain.
Fastest average and HR-zone totals currently remain Garmin-only, explicitly labeled.
Walk% is unavailable until sample cadence units are verified.
Do not equate Zepp Hybrid Charge with Garmin Body Battery.
Do not diagnose readiness/illness from sleep stages or RHR alone.
The original training plan is historical and needs a separate review.
Garmin-only build_stats.py must NOT overwrite merged stats; use sync_zepp.py.
build_dashboard.py is historically gitignored and imports zepp_view.enrich locally.
The routine creates a factual Coach card; session-specific interpretation can be edited
in coach_analysis.html after import and before build.
Validation: python -m unittest test_sync_zepp -v (local Zepp database required).


Every sync: include date-aligned daily comparisons of sleep duration, RHR, Stress and HRV in the Coach card and chat. Readiness uses its reported date; never fill missing current-day values from yesterday. Sleep end is the latest recorded end, not a confirmed wake time; Zepp can revise an incomplete night on later syncs.
