from discord.ext import commands
from .utils import LayoutContext
import discord
import re 

class VanityDetection(commands.Cog):
    """The description for VanityDetection goes here."""

    def __init__(self, bot):
        self.bot = bot
        invite = self.bot.vars.get('vanity-invite')
        self.pattern = re.compile(rf"(?<!\w)(\/{invite}|\.gg\/{invite}|discord\.gg\/{invite})(?!\w)")

    def has_vanity(self, member):
        for activity in member.activities:
            if activity.type == discord.ActivityType.custom:
                return self.pattern.search(activity.name)
        return False

    @commands.Cog.listener()
    async def on_presence_update(self, before, after):
        if after.guild.id != self.bot.GUILD_ID:
            return 
        
        if before.status != after.status:
            return

        if not self.has_vanity(before) and self.has_vanity(after):
            role = discord.Object(self.bot.vars.get('vanity-role-id'))
            
            if role in after.roles:
                return 

            await after.add_roles(role)

            channel = self.bot.get_channel(self.bot.vars.get('vanity-channel-id'))
            layout = self.bot.get_layout('newrep')
            ctx = LayoutContext(author=after)
            await layout.send(channel, ctx=ctx)
        elif self.has_vanity(before) and not self.has_vanity(after):
            role = discord.Object(self.bot.vars.get('vanity-role-id'))
            if role not in after.roles:
                return
            await after.remove_roles(role)


async def setup(bot):
    await bot.add_cog(VanityDetection(bot))
