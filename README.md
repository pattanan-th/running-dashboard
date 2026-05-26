# Korat 21 HM Training Dashboard

Personal half marathon training dashboard.

**Live**: (set after deploy)
**Race**: 21 June 2026 • Korat 21 Half Marathon

## Files

- `dashboard.html` — built dashboard (deploy this)
- `*.json` — data sources
- `*.md` — race week checklist, pacing strategy, etc.
- `build_dashboard.py` — rebuild script (local only)

## Update workflow

1. Update JSON files (via Claude Code scraping or manual)
2. `python build_dashboard.py`
3. `git add . && git commit -m "update" && git push`
4. Cloudflare auto-deploys in ~30 seconds
