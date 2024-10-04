from discord.ext import commands, tasks
from .utils import LayoutContext
import discord


class Vanity(commands.Cog):
    """The description for VanityDetection goes here."""

    def __init__(self, bot):
        self.bot = bot
        self.invite = self.bot.vars.get('vanity-invite')

    def has_vanity(self, member):
        for activity in member.activities:
            if activity.type == discord.ActivityType.custom:
                return f'/{self.invite}' in activity.name.lower()
        return False
    
    def get_vanity(self, member):
        for activity in member.activities:
            if activity.type == discord.ActivityType.custom:
                if f'/{self.invite}' in activity.name.lower():
                    return activity.name
        return None

    @commands.Cog.listener()
    async def on_presence_update(self, before, after):
        if after.guild.id != self.bot.GUILD_ID:
            return 
        
        if after.status is discord.Status.offline:
            return

        # if before.status != after.status:
        #     return

        if not self.has_vanity(before) and self.has_vanity(after):

            role = after.guild.get_role(self.bot.vars.get('vanity-role-id'))
            
            if role in after.roles:
                return 

            await after.add_roles(role)

            with open('vanitylog.txt', '+a') as f:
                f.write(f'{after} gained vanity: before={self.get_vanity(before)}, after={self.get_vanity(after)}\n')

            channel = self.bot.get_channel(self.bot.vars.get('vanity-channel-id'))
            layout = self.bot.get_layout('newrep')
            ctx = LayoutContext(author=after)
            await layout.send(channel, ctx=ctx)
        elif self.has_vanity(before) and not self.has_vanity(after):
            role = after.guild.get_role(self.bot.vars.get('vanity-role-id'))
            if role not in after.roles:
                return
            await after.remove_roles(role)

            with open('vanitylog.txt', '+a') as f:
                f.write(f'{after} lost vanity: before={self.get_vanity(before)}, after={self.get_vanity(after)}\n')

    async def cog_load(self):
        await self.update_roles()
    
    # async def cog_unload(self):
    #     self.update_roles.cancel() 
    
    # @tasks.loop(hours=1)
    async def update_roles(self):
        guild = self.bot.get_guild(self.bot.GUILD_ID)

        embed1 = discord.Embed(title='added roles to')
        embed2 = discord.Embed(title='removed roles from')
        embed3 = discord.Embed(title='this message sends once every time this cog is loaded')

        added = []
        removed = []

        for member in guild.members:
            if member.bot:
                continue

            if member.status is discord.Status.offline:
                continue

            if self.has_vanity(member):
                role = member.guild.get_role(self.bot.vars.get('vanity-role-id'))
                if role not in member.roles:
                    await member.add_roles(role)
                    added.append(member.mention)

            else:
                role = member.guild.get_role(self.bot.vars.get('vanity-role-id'))
                if role in member.roles:
                    await member.remove_roles(role)
                    removed.append(member.mention)
        
        channel = self.bot.get_var_channel('private')
        embed1.description = '\n'.join(added)
        embed2.description = '\n'.join(removed)
        await channel.send(embeds=[embed1, embed2, embed3])



async def setup(bot):
    await bot.add_cog(Vanity(bot))
