import discord
from discord.ext import commands
import os
from dotenv import load_dotenv

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
ENVIRONNEMENT = os.getenv("ENVIRONNEMENT", "DEV") # sur DEV par defaut
SALON_DEV_ID = 1516481386998009876 # ID du salon de test pour le bot 

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"Bot en ligne (Mode: {ENVIRONNEMENT})")

@bot.command()
async def hihi(ctx):
    # Si le bot cloud voit la commande dans le salon dev -> il ignore
    if ENVIRONNEMENT == "PROD" and ctx.channel.id == SALON_DEV_ID:
        return 
    
    # Si le bot local voit la commande en dehors du salon dev -> il ignore
    if ENVIRONNEMENT == "DEV" and ctx.channel.id != SALON_DEV_ID:
        return 

    await ctx.send(f"hihi depuis {ENVIRONNEMENT}")

bot.run(DISCORD_TOKEN)