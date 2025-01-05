from datetime import timedelta

from discord.ext import commands 
import discord 

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from bot import LunaBot


class Sus(commands.Cog):

    def __init__(self, bot):
        self.bot: "LunaBot" = bot
    
    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        role = after.guild.get_role(self.bot.vars.get("sus-role-id"))
        if role not in before.roles and role in after.roles:
            await self.bot.schedule_future_task(
                "kick_sus_member",
                discord.utils.utcnow() + timedelta(days=1),
                user_id=after.id
            )

            await self.bot.get_var_channel("action-log").send(f"Suspicious user scheduled for kicking: {after.mention}") 

async def setup(bot):
    await bot.add_cog(Sus(bot))
