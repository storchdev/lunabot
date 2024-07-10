from discord.ext import commands 
import json 
import discord
from .utils import LayoutContext
import time 
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from bot import LunaBot



class Events(commands.Cog, description='Manage join, leave, boost, and birthday messages'):

    def __init__(self, bot):
        self.bot: 'LunaBot' = bot 

    async def cog_check(self, ctx):
        return ctx.author.guild_permissions.administrator or ctx.author.id == self.bot.owner_id
    
    @commands.Cog.listener()
    async def on_message(self, message):
        if message.channel.id == self.bot.vars.get('free-offers-channel-id'):
            await message.add_reaction('<a:LCM_mail:1151561338317983966>')
        if message.channel.id == self.bot.vars.get('void-channel-id'):
            await message.delete()

    @commands.Cog.listener()
    async def on_member_join(self, member):
        layout = self.bot.get_layout('welc')
        ctx = LayoutContext(author=member)
        channel = self.bot.get_channel(self.bot.vars.get('welc-channel-id'))
        await layout.send(channel, ctx)
    
    @commands.command()
    async def boosttest(self, ctx):
        booster_role = ctx.guild.get_role(self.bot.vars.get('booster-role-id'))
        if booster_role not in ctx.author.roles:
            await ctx.author.add_roles(booster_role)
        else:
            await ctx.author.remove_roles(booster_role)
        await ctx.send(':white_check_mark:')

    @commands.Cog.listener()
    async def on_member_update(self, before, after):
        booster_role = before.guild.get_role(self.bot.vars.get('booster-role-id'))

        if booster_role not in before.roles and booster_role in after.roles:
            member = after
            layout = self.bot.get_layout('boost')
            channel_id = self.bot.vars.get('boost-channel-id')
            channel = self.bot.get_channel(channel_id)
            ctx = LayoutContext(author=member)
            await layout.send(channel, ctx)

                
async def setup(bot):
    await bot.add_cog(Events(bot))

