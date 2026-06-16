import discord
from discord.ext import commands
import os

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print("Bot en ligne")

@bot.command()
async def hihi(ctx):
    await ctx.send("hihi")

bot.run(DISCORD_TOKEN)