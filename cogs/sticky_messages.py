from discord.ext import commands 
import discord 
from bot import LunaBot
from .utils import Layout, LayoutChooserOrEditor, SimplePages
import asyncio 
from time import time as rn


#TODO: turn sm into a group 


class StickyMessage:
    def __init__(self, bot, channel, layout, last_message_id):
        self.bot: LunaBot = bot 
        self.channel: discord.TextChannel = channel 
        self.layout: Layout = layout
        self.last_message_id: int = last_message_id
        self.task: asyncio.Task = None

    @classmethod 
    def from_db_row(cls, bot: LunaBot, row):
        channel = bot.get_channel(row['channel_id'])
        layout = bot.get_layout_from_json(row['layout'])
        last_message_id = row['last_message_id']
        return cls(bot, channel, layout, last_message_id)


class StickyMessages(commands.Cog):

    def __init__(self, bot):
        self.bot: LunaBot = bot 
        self.sticky_messages = {}

    async def cog_check(self, ctx):
        return ctx.author.guild_permissions.administrator or ctx.author.id == self.bot.owner_id

    async def cog_load(self):
        query = 'select * from sticky_messages'
        rows = await self.bot.db.fetch(query)
        for row in rows:
            self.sticky_messages[row['channel_id']] = StickyMessage.from_db_row(self.bot, row)
    
    @commands.Cog.listener()
    async def on_message(self, msg):
        if msg.author.bot:
            return 

        if msg.channel.id not in self.sticky_messages:
            return 

        sm = discord.utils.get(self.sticky_messages.values(), lambda sm: sm.channel == msg.channel)
        new_message = await sm.layout.send(msg.channel)
        old_message_id = sm.last_message_id
        sm.last_message_id = new_message.id

        query = 'update sticky_messages set last_msg_id = $1 where channel_id = $2'
        await self.bot.db.execute(query, new_message.id, msg.channel.id)

        if old_message_id is None:
            return 
        try:
            old_message = await msg.channel.fetch_message(old_message_id)
            await old_message.delete()
        except discord.NotFound:
            pass
    
    @commands.command()
    async def addsm(self, ctx, *, channel: discord.TextChannel):
        # ask for the text and then embed name 

        if channel.id in self.sticky_messages:
            await ctx.send('That channel already has a sticky message.')
            return

        view = LayoutChooserOrEditor(self.bot, ctx.author)
        await ctx.send(view=view, ephemeral=True)
        await view.wait()
        if view.cancelled:
            return
        
        query = 'insert into sticky_messages (channel_id, layout) values ($1, $2)'
        await self.bot.db.execute(query, channel.id, view.layout.to_json())
        sm = StickyMessage(self.bot, channel, view.layout, None)
        self.sticky_messages[channel.id] = sm

        await ctx.send('Successfully added the sticky message.')
    
    @commands.command()
    async def removesm(self, ctx, *, channel: discord.TextChannel):
        if channel.id not in self.sticky_messages:
            await ctx.send('That channel does not have a sticky message.')
            return

        query = 'delete from sticky_messages where channel_id = $1'
        await self.bot.db.execute(query, channel.id)
        del self.sticky_messages[channel.id]
        await ctx.send('Successfully removed the sticky message.')

    @commands.command()
    async def listsm(self, ctx):
        entries = []
        for sm in self.sticky_messages.values():
            entries.append(f'{sm.channel.mention}')
        embed = discord.Embed(title='Sticky Messages', color=self.bot.DEFAULT_EMBED_COLOR)
        pages = SimplePages(entries, ctx=ctx, embed=embed)
        await pages.start()


async def setup(bot):
    await bot.add_cog(StickyMessages(bot))
