# Sync workflow

This project uses Zepp / T-Rex 3. Preserve the Garmin archive.

When the user requests sync:
1. Run `python sync_zepp.py` with UTF-8 output. Do not publish after a failed cloud sync.
2. This always analyzes all available workout and health series, saves
   `zepp_analysis.json`, and writes `latest_analysis.md`. Read the report and
   the relevant workout/health objects before composing the chat analysis.
3. Use full graph evidence: splits, fastest segment, HR peak timing, watch HR
   zones, cadence/step length/power/running dynamics, halves, sleep and daily
   health. Check coverage, source dates and missing fields. Not all extrema
   happen simultaneously. Do not infer pain, injury, diagnosis or clearance
   from a chart. Incorporate user-reported symptoms and shoes as user reports.
4. Build with `python build_dashboard.py`, run appropriate checks, then commit
   and push the explicitly selected generated files, per the user's standing
   auto-push request. `update_and_deploy.bat` runs the same complete workflow.
5. Reply in Thai with a run card, sleep/health summary, useful graph findings,
   missing/stale-data caveats and concrete training implications. Do not merely
   repeat averages when graph data is available. Keep running terms in English.

Generated files: activities.json, sleep.json, wellness.json, stats.json,
zepp_sync.json, zepp_analysis.json, latest_analysis.md, coach_analysis.html,
dashboard.html. Add changed source files explicitly when implementing fixes.
Do not stage all files indiscriminately. No HAR, tokens, database, device IDs,
raw coordinates, or raw payloads in the published analysis.

`--local-only` is for rebuilding already-synced data; it does not contact Zepp.
Do not claim it fetched new cloud data. Computation uses full local resolution;
published workout charts are 15-second mean/min/max bins and health charts are
30-minute sample bins. Keep nulls and gaps, validate units before adding metrics,
and never silently replace missing daily values with another day's measurements.

Checks after analysis changes:
`python -m unittest test_sync_zepp test_zepp_analysis -v`
`node --check zepp_analysis_view.js`
`node test_zepp_analysis_view.cjs`

Decoder unit reference: ZeppBridge v2.4.0, commit
ff5e2d9039f26788e0fe2c1d3d1cf4df452579a4, workout_detail.rs and storage/mod.rs.
