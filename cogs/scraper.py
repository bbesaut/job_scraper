import discord
from discord.ext import commands, tasks
import os
import json 

from scrapers.jobs_ch import scrape_jobs_ch
from scrapers.jobup_ch import scrape_jobup_ch

DEV_CHANNEL_ID = 1516481386998009876  
PROD_CHANNEL_ID = 1516421352448594051  

class Scraper(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        
        self.env = os.getenv("ENVIRONNEMENT", "DEV")
        self.save_path = "/data/sent_jobs.json" if self.env == "PROD" else "sent_jobs.json"
        
        self.sent_jobs = self.load_memory()
        self.scraping_loop_task.start() 

    def load_memory(self):
        if os.path.exists(self.save_path):
            try:
                with open(self.save_path, "r", encoding="utf-8") as f:
                    return set(json.load(f))
            except Exception as e:
                print(f"Error loading memory: {e}")
        return set() 

    def save_memory(self):
        if self.env != "PROD":
            return 
        try:
            with open(self.save_path, "w", encoding="utf-8") as f:
                json.dump(list(self.sent_jobs), f)
        except Exception as e:
            print(f"Error saving memory: {e}")

    @tasks.loop(minutes=15) 
    async def scraping_loop_task(self):
        target_channel_id = PROD_CHANNEL_ID if self.env == "PROD" else DEV_CHANNEL_ID
        target_channel = self.bot.get_channel(target_channel_id)
        
        if target_channel is not None:
            jobs_ch_list = scrape_jobs_ch() 
            jobs_up_list = await scrape_jobup_ch()  # ✅ await

            all_jobs = jobs_ch_list + jobs_up_list
            new_jobs_count = 0
            
            for job in all_jobs:
                job_url = job['url']
                
                if job_url not in self.sent_jobs:
                    texte_alerte = f"@here  🚨  **NOUVELLE OFFRE ({job['source']})**"
                    
                    embed = discord.Embed(
                        title=job['title'],
                        url=job_url, 
                        color=discord.Color.green()
                    )
                    
                    embed.add_field(name="🏢  Entreprise", value=job['company'], inline=True)
                    embed.add_field(name="📍  Lieu", value=job['location'], inline=True)
                    
                    # ✅ jobup.ch a salary + workload, jobs.ch a workload + contract
                    if job['source'] == "jobup.ch":
                        embed.add_field(name="ℹ️  Taux", value=job.get('workload', 'Unknown'), inline=False)
                        embed.add_field(name="💰  Salaire", value=job.get('salary', 'Unknown'), inline=False)
                    else:
                        embed.add_field(name="ℹ️  Contrat", value=f"{job.get('workload', 'Unknown')} | {job.get('contract', 'Unknown')}", inline=False)
                    
                    embed.add_field(name="🔗  Lien", value=job_url, inline=False)
                                        
                    await target_channel.send(content=texte_alerte, embed=embed)
                    
                    self.sent_jobs.add(job_url)
                    new_jobs_count += 1 
            
            if new_jobs_count > 0:
                self.save_memory() 
                print(f"[{new_jobs_count}] NEW JOBS SENT & MEMORY SAVED\n")
            else:
                print(f"[0] No new jobs. Memory unchanged.\n")
                    
        else:
            print(f"ERROR: Channel {target_channel_id} not found.\n")

    @scraping_loop_task.before_loop
    async def before_start(self):
        await self.bot.wait_until_ready()

async def setup(bot):
    await bot.add_cog(Scraper(bot))