import discord
from discord.ext import commands, tasks
import os

SALON_DEV_ID = 1516481386998009876  
SALON_PROD_ID = 1516421352448594051  

class Scraper(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.scraping_loop_task.start() 

    def cog_unload(self):
        self.scraping_loop_task.cancel()

    @tasks.loop(minutes=10) 
    async def scraping_loop_task(self):
        ENVIRONNEMENT = os.getenv("ENVIRONNEMENT", "DEV")

        if ENVIRONNEMENT == "PROD":
            target_channel = SALON_PROD_ID
        else:
            target_channel = SALON_DEV_ID

        salon = self.bot.get_channel(target_channel)
        
        if salon is not None:
            await salon.send(f"Test")
        else:
            print(f"ERROR : {target_channel} Channel not found.")

    @scraping_loop_task.before_loop
    async def before_start(self):
        await self.bot.wait_until_ready()

async def setup(bot):
    await bot.add_cog(Scraper(bot))