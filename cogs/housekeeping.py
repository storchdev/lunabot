import asyncio 
import re
from datetime import timedelta

from discord.ext import commands, tasks
import discord

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from bot import LunaBot


VC_IDS = {
    899108709450543115: 1041061422706204802,
    1068342105006673972: 1068342105006673977,
    1004878848262934538: 1004881486991851570,
    1041468894487003176: 1041472654537932911,
}


class Housekeeping(commands.Cog):
    """The description for Housekeeping goes here."""

    def __init__(self, bot):
        self.bot: "LunaBot" = bot

    async def cog_load(self):
        self.edit.start()

    async def cog_unload(self):
        self.edit.cancel()

    @tasks.loop(minutes=15)
    async def edit(self):
        for guild_id, channel_id in VC_IDS.items():
            guild = self.bot.get_guild(guild_id)
            if guild is None:
                continue
            channel = self.bot.get_channel(channel_id)
            count = int(re.search(r'(\d+)', channel.name).group(1))
            if count != len(guild.members):
                count = len(guild.members)
                try:
                    await channel.edit(name=re.sub(r'\d+', str(count), channel.name))
                except discord.Forbidden:
                    print(f'failed to edit member count in {guild.name}')
                await asyncio.sleep(3)

    @commands.Cog.listener()
    async def on_member_join(self, member):
        name = member.display_name
        if len(name) > 28:
            name = name[:28]
        await asyncio.sleep(1)
        await member.edit(nick=f'✿❀﹕{name}﹕')
    
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
    
    @commands.Cog.listener()
    async def on_member_leave(self, member):
        channel = self.bot.get_var_channel("promo")
        if channel is None:
            return 

        to_delete = [] 
        async for msg in channel.history(limit=100):
            if (discord.utils.utcnow() - msg.created_at).total_seconds() > 86400 * 14:
                break
            if msg.author == member:
                to_delete.append(msg)
        
        await channel.delete_messages(to_delete)
        await self.bot.get_var_channel("action-log").send(f"Deleted {len(to_delete)} promo messages by {member.name} ({member.id})")

    

async def setup(bot):
    await bot.add_cog(Housekeeping(bot))
