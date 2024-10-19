from discord.ext import commands 
import random 
from .utils.checks import staff_only
import discord 
import asyncio 
from matplotlib import pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime, timedelta, time
from typing import TYPE_CHECKING
from io import BytesIO
from pytz import timezone 
from dateparser import parse



if TYPE_CHECKING:
    from bot import LunaBot



class MessageStats(commands.Cog):
    def __init__(self, bot):
        self.bot: 'LunaBot' = bot 
    
    @commands.Cog.listener()
    async def on_message(self, msg: discord.Message):
        if msg.author.bot or msg.guild.id != self.bot.GUILD_ID:
            return 
        
        
        query = 'INSERT INTO message_data (user_id, channel_id) VALUES ($1, $2)'
        await self.bot.db.execute(query, msg.author.id, msg.channel.id)



async def setup(bot):
    await bot.add_cog(MessageStats(bot))
