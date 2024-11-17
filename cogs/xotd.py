from discord.ext import commands, tasks
import discord
import aiohttp 
import json 
from config import SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from .utils import staff_only
from .utils import SimplePages
from .utils import next_day
from typing import TYPE_CHECKING
# from asyncspotify import Client, ClientCredentialsFlow
from .utils import user_cd_except_staff
import re
from .utils import ConfirmView


if TYPE_CHECKING:
    from bot import LunaBot

# spotify_auth = ClientCredentialsFlow(
#     client_id=SPOTIFY_CLIENT_ID,
#     client_secret=SPOTIFY_CLIENT_SECRET
# )


# async def fetch_song(spotify_url):
#     async with Client(spotify_auth) as client:
#         # Extract track ID from URL
#         track_id = spotify_url.split('/')[-1].split('?')[0]
#         # Get track information asynchronously
#         track = await client.get_track(track_id)
#         track_name = track.name
#         artist_name = track.artists[0].name

#         return track_name, artist_name


def get_post_date(days):
    now = datetime.now(ZoneInfo('US/Central')).replace(hour=0, minute=0, second=0, microsecond=0)
    dt = now + timedelta(days=days)
    return discord.utils.format_dt(dt, 'R')


class XoTD(commands.Cog):
    """The description for Xotd goes here."""

    def __init__(self, bot):
        self.bot: 'LunaBot' = bot
    
    async def cog_load(self):
        query = 'INSERT INTO queues (name, items) VALUES ($1, $2) ON CONFLICT DO NOTHING'
        await self.bot.db.execute(query, 'qotd', '[]')
        await self.bot.db.execute(query, 'sotd', '[]')

        questions = await self.bot.db.fetchval('SELECT items FROM queues WHERE name = $1', 'qotd')
        self.questions = json.loads(questions)
        songs = await self.bot.db.fetchval('SELECT items FROM queues WHERE name = $1', 'sotd')
        self.songs = json.loads(songs)

        self.post_qotd.start()
        self.post_sotd.start()

    async def cog_unload(self):
        self.post_qotd.cancel()
        self.post_sotd.cancel()

    @tasks.loop(hours=24) 
    async def post_qotd(self):
        if len(self.questions) == 0:
            return
        
        question = self.questions.pop(0)
        await self.bot.db.execute('UPDATE queues SET items = $1 WHERE name = $2', json.dumps(self.questions), 'qotd')

        number = await self.bot.get_count('qotd')
        channel = self.bot.get_var_channel('qotd')
        layout = self.bot.get_layout('qotd')
        msg = await layout.send(channel, repls={'number': number, 'question': question['question']})
        await msg.create_thread(name='⁺﹒Your Answer﹗𖹭﹒⁺')

    @post_qotd.before_loop
    async def before_post_qotd(self):
        await discord.utils.sleep_until(next_day())

    @tasks.loop(hours=24) 
    async def post_sotd(self):
        if len(self.songs) == 0:
            return
        
        song = self.songs.pop(0)
        await self.bot.db.execute('UPDATE queues SET items = $1 WHERE name = $2', json.dumps(self.songs), 'sotd')

        number = await self.bot.get_count('sotd')
        channel = self.bot.get_var_channel('sotd')
        layout = self.bot.get_layout('sotd')
        msg = await layout.send(channel, repls={'number': number, 'songname': song['name'], 'artist': song['artist'], 'songurl': song['url']})
        await msg.create_thread(name='⁺﹒Song of the Day﹗𖹭﹒⁺')
       

    @post_sotd.before_loop
    async def before_post_sotd(self):
        await discord.utils.sleep_until(next_day())

    @commands.hybrid_command(name='add-qotd')
    @user_cd_except_staff(86400)
    async def add_qotd(self, ctx, *, question: str):
        """Adds a question to the queue to be posted as the QoTD."""
        # end_time = await self.bot.get_cooldown_end('qotd', 86400, obj=ctx.author)
        # if end_time:
        #     await ctx.send(f'You are on cooldown for adding questions. Try again {discord.utils.format_dt(end_time, "R")}.', ephemeral=True)
        #     return 

        self.questions.append({'question': question, 'author_id': ctx.author.id})
        await self.bot.db.execute('UPDATE queues SET items = $1 WHERE name = $2', json.dumps(self.questions), 'qotd')

        md = get_post_date(len(self.questions)) 
        await ctx.send(f'Your question was added to queue! It will be posted {md}. Note that questions are reviewed, and those that fail to follow the server rules will be removed.', ephemeral=True)
        channel = self.bot.get_var_channel('queue-log')
        await channel.send(f'A new question was added to the queue!\n\nQ: {question}\nUser: ||{ctx.author.mention}||')

    @commands.hybrid_command(name='add-sotd')
    @user_cd_except_staff(86400)
    async def add_sotd(self, ctx, *, data: str):
        """Adds a song to the queue to be posted as the SoTD."""

        data = data.strip(' \n').split('\n')
        if len(data) != 3:
            await ctx.send('The format is:\n\n`Song Name\nArtist\nSpotify URL`', ephemeral=True)
            return 
        
        spotify_url = data[2]
        if not re.match(r'https://open\.spotify\.com/track/[A-Za-z0-9]{22}(\?si=[A-Za-z0-9_-]+)?', spotify_url):
            await ctx.send('Invalid Spotify URL.', ephemeral=True)
            return 

        view = ConfirmView(ctx)
        await ctx.send(f'Confirm this information?\n\nSong: {data[0]}\nArtist: {data[1]}\nURL: {spotify_url}', view=view)
        await view.wait()

        if view.choice is None:
            return
        
        if view.choice is False:
            await view.final_interaction.response.edit_message(content='Cancelled.', view=None)
            return 

        name = data[0]
        artist = data[1]
        # name, artist = await fetch_song(spotify_url) 
        self.songs.append({'name': name, 'artist': artist, 'url': spotify_url, 'author_id': ctx.author.id})
        await self.bot.db.execute('UPDATE queues SET items = $1 WHERE name = $2', json.dumps(self.songs), 'sotd')

        md = get_post_date(len(self.songs))
        await view.final_interaction.response.edit_message(content=f'Your song was added to queue! It will be posted {md}. Note that songs are reviewed, and those that fail to follow the server rules will be removed.', view=None)
        channel = self.bot.get_var_channel('queue-log')
        await channel.send(f'A new song was added to the queue!\n\nSong: {spotify_url}\nUser: ||{ctx.author.mention}||')

    @commands.group(aliases=['sq'], invoke_without_command=True)
    @staff_only()    
    async def sotdqueue(self, ctx):
        await ctx.send_help(ctx.command)

    @sotdqueue.command(name='view')
    async def sq_view(self, ctx):
        if len(self.songs) == 0:
            await ctx.send('No songs in queue.')
            return
        lines = []
        dt = next_day()
        for song in self.songs:
            md = discord.utils.format_dt(dt, 'd')
            lines.append(f'[{song["name"]}]({song["url"]}) by {song["artist"]} - {md}')
            dt += timedelta(days=1)

        pages = SimplePages(lines, ctx=ctx)
        await pages.start()
    
    @sotdqueue.command(name='remove')
    async def sq_remove(self, ctx, index: int):
        if index < 1 or index > len(self.songs):
            await ctx.send('Invalid index.')
            return
        song = self.songs.pop(index-1)
        await self.bot.db.execute('UPDATE queues SET items = $1 WHERE name = $2', json.dumps(self.songs), 'sotd')
        await ctx.send(f'Song by {song["artist"]} was removed from the queue.')
        
    @commands.group(aliases=['qq'], invoke_without_command=True)
    @staff_only()
    async def qotdqueue(self, ctx):
        await ctx.send_help(ctx.command)

    @qotdqueue.command(name='view')
    async def qq_view(self, ctx):
        if len(self.questions) == 0:
            await ctx.send('No questions in queue.')
            return
        lines = []
        dt = next_day()
        for question in self.questions:
            md = discord.utils.format_dt(dt, 'd')
            lines.append(f'{question["question"]} - {md}')
            dt += timedelta(days=1)
        pages = SimplePages(lines, ctx=ctx)
        await pages.start()

    @qotdqueue.command(name='remove')
    async def qq_remove(self, ctx, index: int):
        if index < 1 or index > len(self.questions):
            await ctx.send('Invalid index.')
            return
        question = self.questions.pop(index-1)
        await self.bot.db.execute('UPDATE queues SET items = $1 WHERE name = $2', json.dumps(self.questions), 'qotd')
        await ctx.send(f'Question by <@{question["author_id"]}> was removed from the queue.')


async def setup(bot):
    await bot.add_cog(XoTD(bot))
