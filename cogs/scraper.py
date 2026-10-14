import discord
from discord.ext import commands, tasks
import os
import json
import asyncio
import logging
import gc
from datetime import datetime
from zoneinfo import ZoneInfo
from scrapers.jobs_ch import scrape_jobs_ch
from scrapers.jobup_ch import scrape_jobup_ch
from scrapers.jobscout24_ch import scrape_jobscout24_ch
from scrapers.jobbasel_ch import scrape_jobbasel_ch
from scrapers.swissas_teamtailor import scrape_swissas_teamtailor
from scrapers.jetaviation import scrape_jetaviation
from scrapers.amacaerospace import scrape_amacaerospace

DEV_CHANNEL_ID = 1516481386998009876
DEV_LOGS_CHANNEL_ID = 1517559887754694838
PROD_CHANNEL_ID = 1516421352448594051
PROD_LOGS_CHANNEL_ID = 1517559558938034266

PARIS_TZ = ZoneInfo("Europe/Paris")

# Every `source` value the scrapers emit, so a source with nothing sent still shows up as 0.
SOURCES = (
    "jobs.ch", "jobup.ch", "jobscout24.ch", "jobbasel.ch",
    "swissas.teamtailor.com", "jobs.jetaviation.com", "amacaerospace.com",
)

class ParisFormatter(logging.Formatter):
    def formatTime(self, record, datefmt=None):
        dt = datetime.fromtimestamp(record.created, tz=PARIS_TZ)
        return dt.strftime(datefmt or "%Y-%m-%d %H:%M:%S")

class DiscordLogHandler(logging.Handler):
    def __init__(self, channel_getter):
        super().__init__()
        self.channel_getter = channel_getter
        self.loop = None

    def emit(self, record):
        msg = self.format(record)
        channel = self.channel_getter()
        if channel and self.loop and not self.loop.is_closed():
            asyncio.run_coroutine_threadsafe(channel.send(f"```\n{msg}\n```"), self.loop)

class Scraper(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.env = os.getenv("ENVIRONNEMENT", "DEV")
        self.dry_run = self.resolve_dry_run(self.env)
        self.save_path = "/data/sent_jobs.json" if self.env == "PROD" else "sent_jobs.json"
        self.sent_jobs = self.load_memory()

        self.logger = logging.getLogger("scraper")
        self.logger.setLevel(logging.DEBUG)
        self.discord_handler = DiscordLogHandler(self.get_logs_channel)
        self.discord_handler.setFormatter(ParisFormatter("%(asctime)s - %(message)s", "%H:%M:%S"))
        self.logger.addHandler(self.discord_handler)

        import builtins
        original_print = builtins.print
        def custom_print(*args, **kwargs):
            original_print(*args, **kwargs)
            self.logger.info(" ".join(str(a) for a in args))
        builtins.print = custom_print

        self.scraping_loop_task.start()

    @staticmethod
    def resolve_dry_run(env):
        """DRY_RUN=true/false wins; unset means on in DEV, off in PROD."""
        raw = os.getenv("DRY_RUN")
        if raw is None or not raw.strip():
            return env != "PROD"
        return raw.strip().lower() in ("1", "true", "yes", "on")

    def get_logs_channel(self):
        channel_id = PROD_LOGS_CHANNEL_ID if self.env == "PROD" else DEV_LOGS_CHANNEL_ID
        return self.bot.get_channel(channel_id)

    def load_memory(self):
        if os.path.exists(self.save_path):
            try:
                with open(self.save_path, "r", encoding="utf-8") as f:
                    return set(json.load(f))
            except Exception as e:
                print(f"Error loading memory: {e}")
        return set()

    def save_memory(self):
        # A dry run never sent anything, so persisting its jobs as "sent" would hide them forever.
        if self.env != "PROD" or self.dry_run: return
        try:
            with open(self.save_path, "w", encoding="utf-8") as f:
                json.dump(list(self.sent_jobs), f)
        except Exception as e:
            print(f"Error saving memory: {e}")

    @tasks.loop(hours=2)
    async def scraping_loop_task(self):
        self.discord_handler.loop = asyncio.get_event_loop()
        target_channel_id = PROD_CHANNEL_ID if self.env == "PROD" else DEV_CHANNEL_ID
        target_channel = self.bot.get_channel(target_channel_id)

        try:
            jobs_ch_results = await asyncio.to_thread(scrape_jobs_ch)
            jobup_ch_results = await scrape_jobup_ch()
            jobscout24_ch_results = await asyncio.to_thread(scrape_jobscout24_ch)
            jobbasel_ch_results = await asyncio.to_thread(scrape_jobbasel_ch)
            swissas_results = await asyncio.to_thread(scrape_swissas_teamtailor)
            jetaviation_results = await asyncio.to_thread(scrape_jetaviation)
            amacaerospace_results = await asyncio.to_thread(scrape_amacaerospace)

            all_jobs = (
                (jobs_ch_results or []) + (jobup_ch_results or []) + (jobscout24_ch_results or [])
                + (jobbasel_ch_results or []) + (swissas_results or []) + (jetaviation_results or [])
                + (amacaerospace_results or [])
            )

            new_jobs_count = 0
            sent_by_source = {source: 0 for source in SOURCES}
            for job in all_jobs:
                if job['url'] not in self.sent_jobs:
                    embed = discord.Embed(title=job['title'], color=discord.Color.green())
                    embed.add_field(name="🏢 Entreprise", value=job['company'], inline=True)
                    embed.add_field(name="📍 Lieu", value=job['location'], inline=True)
                    embed.add_field(name="ℹ️ Contrat", value=f"{job.get('workload', 'Unknown')} | {job.get('contract', 'Unknown')}", inline=False)
                    embed.add_field(name="🔗 Lien", value=job['url'], inline=True)


                    # Dry run: skip only the job notification. The per-source summary below still goes to logs.
                    if not self.dry_run:
                        await target_channel.send(content=f"@here 🚨 **NOUVELLE OFFRE ({job['source']})**", embed=embed)
                    self.sent_jobs.add(job['url'])
                    new_jobs_count += 1
                    sent_by_source[job['source']] = sent_by_source.get(job['source'], 0) + 1

            # One print (= one Discord log message) for all sources, same format as the FOUND lines.
            current_time = datetime.now(PARIS_TZ).strftime("%Y-%m-%d %H:%M:%S")
            print("\n".join(
                f"[{current_time}] - [{count}] SENT from {source}."
                for source, count in sent_by_source.items()
            ))

            print(f"[{new_jobs_count}] NEW SENT" if new_jobs_count > 0 else "No new jobs found.")
            if new_jobs_count > 0:
                self.save_memory()

            del jobs_ch_results
            del jobup_ch_results
            del jobscout24_ch_results
            del jobbasel_ch_results
            del swissas_results
            del jetaviation_results
            del amacaerospace_results
            del all_jobs
            gc.collect()

        except Exception as e:
            self.logger.error(f"Erreur critique : {e}")
            gc.collect()

    @scraping_loop_task.before_loop
    async def before_start(self):
        await self.bot.wait_until_ready()

async def setup(bot):
    await bot.add_cog(Scraper(bot))