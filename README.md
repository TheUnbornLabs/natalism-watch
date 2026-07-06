# 👶 Natalism Watch — daily dashboard

A local dashboard that collects content about **antinatalism**, **childfree**, and
**pro-natalism / anti-antinatalism** from across the web every day, grouped by topic.

Everything runs on your PC. No accounts, no server, no cost for the default sources.

---

## What it does

1. `collect.py` pulls fresh items from the internet for each topic:
   - **Reddit** — relevant subreddits (free)
   - **News** — Google News search RSS (free)
   - **Academic / Philosophy** — focused Google News queries (free)
   - **X / Twitter** — optional, needs a free developer Bearer token
   - **YouTube** — optional, needs a free API key
2. It saves everything to a local database (`data.db`), removing duplicates.
3. It regenerates **`dashboard.html`** — a single file you open in any browser.
   Filter by topic, source, recency, and full-text search.

---

## Two ways to use it

**A) With a Refresh button (recommended).**
Double-click **`serve.bat`** (or run `python serve.py`). It opens the dashboard at
`http://localhost:8765` and gives you a **↻ Refresh** button in the top-right that pulls
the latest items from the web on demand and updates the page in place. Leave the little
server window open while you use it; close it (or press Ctrl+C) to stop.

**B) As a plain file (no button).**
Double-click **`run.bat`** (collects data, then opens the dashboard), or run
`python collect.py` and open `dashboard.html`. This works with zero setup, but the
Refresh button can only fetch new data when the page is served by `serve.bat` — opened
as a bare file it will tell you to start the server.

> Why: browser security forbids a local HTML file from running code or hitting the
> network on its own, so live refresh needs the tiny local server behind it.

---

## Make it update automatically every day

Right-click **`setup_schedule.ps1`** → **Run with PowerShell**.
This registers a Windows Scheduled Task that runs the collector once a day (default 8:00 AM).

Pick a different time:

```
powershell -ExecutionPolicy Bypass -File setup_schedule.ps1 -Time "07:30"
```

- If the PC is off/asleep at that time, it runs as soon as the PC is next available.
- Test it immediately: `Start-ScheduledTask -TaskName NatalismDashboardDaily`
- Remove it: `Unregister-ScheduledTask -TaskName NatalismDashboardDaily -Confirm:$false`

The dashboard always shows the latest data the last collection gathered — just open
`dashboard.html` any time.

---

## Turning on X/Twitter and YouTube

These need free API keys (the other sources don't). Edit **`config.json`**:

```json
"sources_enabled": { ... "twitter": true, "youtube": true },
"api_keys": {
  "twitter_bearer_token": "PASTE_HERE",
  "youtube_api_key": "PASTE_HERE"
}
```

- **YouTube key:** console.cloud.google.com → enable "YouTube Data API v3" → create an API key.
- **X/Twitter Bearer token:** developer.x.com → create a project/app → copy the Bearer token.
  (Note: X's free tier is limited; if it errors, the run continues without it.)

---

## Languages

The collector pulls content **in multiple languages**, each with localized search terms
and that country's news edition, so you see what's happening worldwide — not just in English.

Enabled by default: **English, Spanish, German, French, Portuguese, Japanese**.
Italian and Hindi are included but switched off.

- Filter the dashboard by language with the **"All languages"** dropdown. Non-English items
  also show a small language tag (e.g. `JA`).
- Turn a language on/off in `config.json` under `"languages"` — set `"enabled": true/false`.
- Add a brand-new language:
  1. Add an entry under `"languages"` with its Google News locale string
     (`hl=<lang>&gl=<country>&ceid=<country>:<lang>`).
  2. Add a matching block of translated search terms under each topic's `"queries"`.

  Languages without translated queries for a topic are simply skipped for that topic.
- Reddit is English-dominated, so its items are tagged with `reddit_language` (default `en`).

> Note: more languages = more requests = longer collection time. Six languages takes a
> few minutes per full run.

## Customizing topics & sources

Open **`config.json`**. For each topic you can edit:
- `subreddits` — list of subreddit names
- `news_query` / `academic_query` / `social_query` / `youtube_query` — search terms
- `color` / `label` — how it appears on the dashboard

You can also add a whole new topic by copying one of the three blocks.

---

## Files

| File | Purpose |
|------|---------|
| `collect.py` | The collector / engine |
| `dashboard_template.py` | The dashboard's HTML/CSS/JS (edited rarely) |
| `config.json` | Topics, sources, API keys, settings |
| `data.db` | Local SQLite store (auto-created, keeps history) |
| `dashboard.html` | The dashboard you open (auto-generated) |
| `serve.py` / `serve.bat` | Local server that powers the ↻ Refresh button |
| `run.bat` | Manual: collect + open dashboard (no server) |
| `update.bat` | Collect only (used by the daily task) |
| `setup_schedule.ps1` | Registers the daily Windows task |

---

## Notes

- Reddit rate-limits unauthenticated requests hard; the main subreddit per topic
  usually gets through, smaller secondary ones may be skipped on a given run.
  They'll fill in over subsequent days since history accumulates.
- All sources fail gracefully and independently — one being down never stops the rest.
