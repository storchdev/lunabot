from discord.ext import commands, tasks
import discord
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from .utils import next_sunday
from typing import TYPE_CHECKING
from num2words import num2words

if TYPE_CHECKING:
    from bot import LunaBot

class WeeklyCheckup(commands.Cog):
    """The description for WeeklyCheckup goes here."""

    def __init__(self, bot):
        self.bot: 'LunaBot' = bot
        self.weekly_checkup.start()

    @tasks.loop(hours=168)
    async def weekly_checkup(self):
        now = discord.utils.utcnow()
        last_sunday = now - timedelta(days=7)
        last_saturday = now - timedelta(days=1)
        last_sunday = last_sunday.strftime('%m/%d/%y')
        last_saturday = last_saturday.strftime('%m/%d/%y')

        count = await self.bot.get_count('weeklycheckup') 
        ordinal = num2words(count, to='ordinal_num')
        layout = self.bot.get_layout('weeklycheckup')
        channel = self.bot.get_var_channel('checkup')

        msg = await layout.send(channel, repls={'lastsunday': last_sunday, 'lastsaturday': last_saturday, 'ordinal': ordinal})
        emotes = [ 
            "<a:ML_flower_spin_1:1174180133624631366>",
            "<a:ML_flower_spin_2:1174180175521534013>",
            "<a:ML_flower_spin_3:1174180212863418539>",
            "<a:ML_flower_spin_4:1174180244945637396>",
            "<a:ML_flower_spin_5:1174180273638883328>",
        ]
        for emote in emotes:
            await msg.add_reaction(emote)

        await msg.create_thread(name='⁺﹒Discuss Your Week﹗𖹭﹒⁺')

    @weekly_checkup.before_loop 
    async def before_weekly_checkup(self):
        await discord.utils.sleep_until(next_sunday())
    
    # @commands.command()
    # async def test_weekly_checkup(self, ctx):
    #     await self.weekly_checkup()
    #     await ctx.send('Weekly checkup sent')


async def setup(bot):
    await bot.add_cog(WeeklyCheckup(bot))
