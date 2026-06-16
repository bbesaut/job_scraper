import discord
from discord.ext import commands

class Clear(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def clear(self, ctx, nombre: int = 1000):
        messages_effaces = await ctx.channel.purge(limit=nombre)

async def setup(bot):
    await bot.add_cog(Clear(bot))