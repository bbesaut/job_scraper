# Job Scraper Discord Bot

Discord bot that scrapes swiss jobs websites every 15 minutes for new developer job postings and posts them to a Discord channel.

## Stack

- Python 3.11
- discord.py (bot framework)
- requests / httpx + lxml (scraping)
- Deployed on Fly.io

## How it works

- `main.py` starts the bot and loads every cog in `cogs/`.
- `cogs/scraper.py` runs a loop every 15 minutes: scrapes all three sites, filters postings for relevance (see below), and posts new ones as embeds to the target Discord channel. Already-seen job URLs are remembered (in `/data/sent_jobs.json` in prod) to avoid duplicate posts.
- `cogs/clear.py` adds a `!clear [n]` command to bulk-delete messages in a channel.
- `scrapers/jobs_ch.py`, `scrapers/jobup_ch.py` and `scrapers/jobscout24_ch.py` contain the actual scraping logic for each site.
- `scrapers/relevance.py` decides whether a scraped posting is actually relevant, based on `greenflags.txt` and `greyflags.txt` (see below).
- The bot switches between a **DEV** channel and a **PROD** channel based on the `ENVIRONNEMENT` env var (see `main.py`), so it only reacts to commands in the matching channel.

### Filtering: `greenflags.txt` and `greyflags.txt`

Each posting's title and full description are checked against two keyword/phrase lists (one entry per line, case-insensitive, whole-word match):

- **`greenflags.txt`** — the keywords that make a posting relevant (e.g. `java`, `developer`, `backend`). A posting is kept if a greenflag appears in the **title**, or if at least 2 distinct greenflags appear in the **body** (a single incidental mention isn't enough on its own — e.g. a nurse posting that happens to mention "Microsoft Software" as an employee perk shouldn't pass).
- **`greyflags.txt`** — phrases that should **not** count as evidence, even though they contain a greenflag (e.g. `fachliche Entwicklung`, `persönliche Entwicklung` — generic HR phrasing about career growth, not software development). These phrases are stripped out of the text *before* counting greenflag matches. A greyflag does **not** reject a posting outright — it just means that occurrence doesn't count as proof of relevance; the posting can still be kept if it matches elsewhere.

Edit either file to tune the filtering — no code changes needed.

## Prerequisites

- Python 3.11+
- A Discord bot token (Discord Developer Portal), with the bot invited to your server and the **Message Content** intent enabled

## Setup

1. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

2. Create a `.env` file at the project root (already gitignored):

   ```
   DISCORD_TOKEN=your-bot-token-here
   ENVIRONNEMENT=DEV
   ```

   - `ENVIRONNEMENT=DEV` restricts the bot to the dev channel (ID hardcoded as `SALON_DEV_ID` in `main.py`).
   - `ENVIRONNEMENT=PROD` restricts it to the prod channel.

3. Edit `greenflags.txt` and `greyflags.txt` if you want to change how job postings are filtered — see [Filtering](#filtering-greenflagstxt-and-greyflagstxt) above.

## Run locally

```bash
python main.py
```

The bot connects to Discord and starts the scraping loop (every 15 min) once ready. Console logs are also mirrored to a Discord logs channel via a custom logging handler.

## Deploy (Fly.io)

The project is already configured for Fly.io (`fly.toml`, `Dockerfile`):

```bash
fly deploy
```

- App name: `job-scraper-57eklg`, region `iad`, 1 shared CPU / 256MB.
- A persistent volume mounted at `/data` stores `sent_jobs.json` in production so job history survives restarts.
- Set secrets instead of using `.env` in production:

  ```bash
  fly secrets set DISCORD_TOKEN=your-bot-token-here ENVIRONNEMENT=PROD
  ```

## Notes

- ⚠️ The `DISCORD_TOKEN` currently sitting in your local `.env` is a real bot token — it's gitignored so it won't be committed, but treat it like a password (don't paste it anywhere, rotate it in the Discord Developer Portal if it's ever leaked).
- `test.py` is a scratch script for inspecting the raw jobup.ch API response shape, not part of the bot itself.
