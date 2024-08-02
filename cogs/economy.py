from discord.ext import commands
import discord
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from bot import LunaBot
    

class Currency(commands.Cog):
    """The description for Currency goes here."""

    def __init__(self, bot):
        self.bot: 'LunaBot' = bot
        self.lunara = self.bot.vars.get('lunara')
    
    @commands.hybrid_command()
    async def shop(self, ctx):
        rows = await self.bot.db.fetch('SELECT * FROM shop_items')
        names = []
        descs = []
        for row in rows:
            names.append(row['common_name'])
            descs.append(row['description'])
        layout = self.bot.get_layout('shop')
        await layout.send(ctx, repls={
            'itemnames': names,
            'itemdescs': descs
        })

async def setup(bot):
    await bot.add_cog(Currency(bot))
