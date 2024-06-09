from discord.ext import commands, tasks 
import json 
from discord import app_commands
import discord 
from time import time as rn 
import datetime 
from .utils import TimeConverter, Layout, LayoutChooserOrEditor
import asyncio 
from bot import LunaBot



class AutoMessage:
    def __init__(self, bot, name, channel, layout, interval, lastsent):
        self.bot: LunaBot = bot 
        self.channel: discord.TextChannel = channel 
        self.layout: Layout = layout
        self.interval: int = interval 
        self.lastsent: int = lastsent 
        self.name: str = name 
        self.task: asyncio.Task = None

    @classmethod 
    def from_db_row(cls, bot: LunaBot, row):
        name = row['name']
        channel = bot.get_channel(row['channel_id'])
        layout = bot.get_layout_from_json(row['layout'])
        interval = row['interval']
        lastsent = row['lastsent']
        return cls(bot, name, channel, layout, interval, lastsent)

    def start(self):
        self.task = self.bot.loop.create_task(self.run())

    async def run(self):
        sincelast = rn() - self.lastsent
        if sincelast < self.interval:
            await asyncio.sleep(self.interval - sincelast)
        while True:
            await self.layout.send(self.channel)
            query = 'UPDATE auto_messages SET lastsent = $1 WHERE name = $2'
            await self.bot.db.execute(query, rn(), self.name) 
            await asyncio.sleep(self.interval)

    async def cancel(self):
        self.task.cancel()
        query = 'DELETE FROM auto_messages WHERE name = $1'
        await self.bot.db.execute(query, self.name)


class Automessages(commands.Cog):

    def __init__(self, bot):
        self.bot = bot 
        self.auto_messages = {}

    async def cog_load(self):
        query = 'SELECT * FROM auto_messages'
        rows = await self.bot.db.fetch(query)
        for row in rows:
            self.auto_messages[row['name']] = AutoMessage.from_db_row(self.bot, row)

    async def cog_unload(self):
        for am in self.auto_messages.values():
            am.task.cancel()

    async def cog_check(self, ctx):
        return ctx.author.guild_permissions.administrator or ctx.author.id == self.bot.owner_id

    @commands.hybrid_group(aliases=['am'], invoke_without_command=True) 
    @app_commands.default_permissions()
    async def automessage(self, ctx):
        """Automessages management."""
        await ctx.send_help(ctx.command)

    @automessage.command(name='add', aliases=['create'])
    @app_commands.default_permissions()
    @app_commands.describe(name='a name for the automessage', channel='the channel to send the messages in', time='the interval')
    async def automessage_add(self, ctx, name: str, channel: discord.TextChannel, time: TimeConverter):
        if time is None:
            return 

        name = name.lower()
        query = 'SELECT id FROM auto_messages WHERE name = $1'
        val = await self.bot.db.fetchval(query, name)
        if val is not None:
            return await ctx.send('There is already an automessage under that name.', ephemeral=True) 
        
        view = LayoutChooserOrEditor(self.bot, ctx.author)
        await ctx.send(view=view, ephemeral=True)
        await view.wait()
        if view.cancelled:
            return 
        
        query = 'INSERT INTO auto_messages (name, channel_id, interval, layout, lastsent) VALUES ($1, $2, $3, $4, $5)'
        await self.bot.db.execute(query, name, channel.id, time, view.layout.to_json(), rn())
        await view.final_interaction.response.edit_message(
            content=f'Added your automessage `{name}`!',
            view=None
        )

    @automessage.command(name='remove', aliases=['delete'])
    @app_commands.default_permissions()
    @app_commands.describe(name='the name for the automessage') 
    async def automessage_remove(self, ctx, *, name: str):
        name = name.lower() 
        query = 'SELECT id FROM auto_messages WHERE name = $1'
        val = await self.bot.db.fetchval(query, name)
        if val is None:
            return await ctx.send('No automessage under that name.', ephemeral=True)

        if name in self.auto_messages:
            am = self.auto_messages.pop(name)
            am.task.cancel()

        query = 'DELETE FROM auto_messages WHERE name = $1'
        await self.bot.db.execute(query, name)
        await ctx.send('Deleted your automessage!', ephemeral=True)
    
    @automessage.command(name='list', aliases=['show'])
    @app_commands.default_permissions()
    async def automessage_list(self, ctx):
        query = 'SELECT name, channel_id FROM auto_messages'
        rows = await self.bot.db.fetch(query)
        if not rows:
            return await ctx.send('No automessages found.')
        embed = discord.Embed(color=0xcab7ff, title='Automessages')
        fields = []
        for row in rows:
            channel = self.bot.get_channel(row['channel_id'])
            name = row['name']
            fields.append(f'`{name}` in {channel.mention}')
        embed.description = '\n'.join(fields)
        await ctx.send(embed=embed)


        
async def setup(bot):
    await bot.add_cog(Automessages(bot))
