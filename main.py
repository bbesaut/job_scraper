import discord
from discord.ext import commands
import os
from dotenv import load_dotenv

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
ENVIRONNEMENT = os.getenv("ENVIRONNEMENT", "DEV") # default = DEV
TEST_CHANNEL_ID = int(os.getenv("TEST_CHANNEL_ID", 0)) # test channel id on discord

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

@bot.check
async def filtre_environnement(ctx):
    if ENVIRONNEMENT == "PROD" and ctx.channel.id == TEST_CHANNEL_ID:
        return False 
    
    if ENVIRONNEMENT == "DEV" and ctx.channel.id != TEST_CHANNEL_ID:
        return False 

    return True
    
@bot.event
async def setup_hook(): # Load every cog in the cogs folder
    for filename in os.listdir('./cogs'):
        if filename.endswith('.py'):
            await bot.load_extension(f'cogs.{filename[:-3]}')
            print(f"COG LOADED : {filename}")

@bot.event
async def on_ready():
    print(f"BOT ONLINE (Mode: {ENVIRONNEMENT})")

bot.run(DISCORD_TOKEN)