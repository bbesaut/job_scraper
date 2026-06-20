import discord
from discord.ext import commands, tasks
import os
import json
import asyncio
import logging
import gc
from scrapers.jobs_ch import scrape_jobs_ch
from scrapers.jobup_ch import scrape_jobup_ch

DEV_CHANNEL_ID = 1516481386998009876
DEV_LOGS_CHANNEL_ID = 1517559887754694838
PROD_CHANNEL_ID = 1516421352448594051
PROD_LOGS_CHANNEL_ID = 1517559558938034266

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
        self.save_path = "/data/sent_jobs.json" if self.env == "PROD" else "sent_jobs.json"
        self.sent_jobs = self.load_memory()

        self.logger = logging.getLogger("scraper")
        self.logger.setLevel(logging.DEBUG)
        self.discord_handler = DiscordLogHandler(self.get_logs_channel)
        self.discord_handler.setFormatter(logging.Formatter("%(asctime)s - %(message)s", "%H:%M:%S"))
        self.logger.addHandler(self.discord_handler)

        import builtins
        original_print = builtins.print
        def custom_print(*args, **kwargs):
            original_print(*args, **kwargs)
            self.logger.info(" ".join(str(a) for a in args))
        builtins.print = custom_print

        self.scraping_loop_task.start()

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
        if self.env != "PROD": return
        try:
            with open(self.save_path, "w", encoding="utf-8") as f:
                json.dump(list(self.sent_jobs), f)
        except Exception as e:
            print(f"Error saving memory: {e}")

    @tasks.loop(minutes=15)
    async def scraping_loop_task(self):
        self.discord_handler.loop = asyncio.get_event_loop()
        target_channel_id = PROD_CHANNEL_ID if self.env == "PROD" else DEV_CHANNEL_ID
        target_channel = self.bot.get_channel(target_channel_id)

        try:
            jobs_ch_results = await asyncio.to_thread(scrape_jobs_ch)
            jobup_ch_results = await scrape_jobup_ch()

            all_jobs = (jobs_ch_results or []) + (jobup_ch_results or [])

            new_jobs_count = 0
            for job in all_jobs:
                if job['url'] not in self.sent_jobs:
                    embed = discord.Embed(title=job['title'], color=discord.Color.green())
                    embed.add_field(name="🏢 Entreprise", value=job['company'], inline=True)
                    embed.add_field(name="📍 Lieu", value=job['location'], inline=True)
                    embed.add_field(name="ℹ️ Contrat", value=f"{job.get('workload', 'Unknown')} | {job.get('contract', 'Unknown')}", inline=False)
                    embed.add_field(name="🔗 Lien", value=job['url'], inline=True)


                    await target_channel.send(content=f"@here 🚨 **NOUVELLE OFFRE ({job['source']})**", embed=embed)
                    self.sent_jobs.add(job['url'])
                    new_jobs_count += 1

            print(f"[{new_jobs_count}] NEW SENT" if new_jobs_count > 0 else "No new jobs found.")
            if new_jobs_count > 0:
                self.save_memory()

            del jobs_ch_results
            del jobup_ch_results
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