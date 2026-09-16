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
Totals and Longest rankings combine Garmin + Zepp. Fastest-split rankings, fastest average
and HR-zone totals currently remain Garmin-only, explicitly labeled in the UI.
Walk% is unavailable until sample cadence units are verified.
Do not equate Zepp Hybrid Charge with Garmin Body Battery.
Do not diagnose readiness/illness from sleep stages or RHR alone.
The original training plan is historical and needs a separate review.
Garmin-only build_stats.py must NOT overwrite merged stats; use sync_zepp.py.
build_dashboard.py is historically gitignored and imports zepp_view.enrich locally.
The routine creates a factual Coach card; session-specific interpretation can be edited
in coach_analysis.html after import and before build.
Validation: python -m unittest test_sync_zepp -v (local Zepp database required).

