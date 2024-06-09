from discord.ext import commands 
from discord import app_commands
import discord 
from .utils import ChannelSelectView
import logging 


class PingOnJoin(commands.Cog):

    def __init__(self, bot):
        self.bot = bot 
        self.channels = {} 

    async def cog_check(self, ctx):
        return ctx.author.id == self.bot.owner_id or ctx.author.guild_permissions.administrator

    async def cog_load(self):
        rows = await self.bot.db.fetch('select * from pingonjoin')
        for row in rows:
            if row['guild_id'] not in self.channels:
                self.channels[row['guild_id']] = []
            self.channels[row['guild_id']].append(row['channel_id'])
    
    @commands.Cog.listener()
    async def on_member_join(self, member):
        # logging.info(f'{member} joined {member.guild}')
        if member.guild.id not in self.channels:
            return 
        # logging.info('Sending pings')
        for channel_id in self.channels[member.guild.id]:
            channel = self.bot.get_channel(channel_id)
            if channel is None:
                continue 
            msg = await channel.send(member.mention)
            # logging.info(f'sent ping in {channel}')
            await msg.delete()
    
    @commands.hybrid_command()
    @app_commands.default_permissions()
    async def editpoj(self, ctx):
        view = ChannelSelectView()
        await ctx.send('Select channels to ping on join. This will override any previous setting.', view=view)
        await view.wait()
        if view.cancelled:
            return

        await self.bot.db.execute('delete from pingonjoin where guild_id = $1', ctx.guild.id)
        for channel in view.channels:
            await self.bot.db.execute('insert into pingonjoin (guild_id, channel_id) values ($1, $2)', ctx.guild.id, channel.id)
        self.channels[ctx.guild.id] = [channel.id for channel in view.channels]
        await view.inter.response.send_message('Done!')


async def setup(bot):
    await bot.add_cog(PingOnJoin(bot))


