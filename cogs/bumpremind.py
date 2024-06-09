from discord.ext import commands 
import time 
import json
import discord  
import datetime
import logging 


class BumpRemind(commands.Cog):

    def __init__(self, bot):
        self.bot = bot 
        with open('cogs/static/embeds.json') as f:
            self.embed = discord.Embed.from_dict(json.load(f)['bump_remind'])
        self.channel_id = 899112780840468561
        self.disboard_id = 302050872383242240
 
    async def cog_load(self):
        query = 'SELECT nextbump FROM bumpremind'
        val = await self.bot.db.fetchval(query)
        if val is None:
            return
        if val > time.time():
            end_time = datetime.datetime.fromtimestamp(val)
            self.bot.loop.create_task(self.task(end_time))
        else:
            await self.send()

    async def send(self):
        channel = self.bot.get_channel(self.channel_id)
        await channel.send(
            '⁺﹒<@&1137968018270457957>﹗𖹭﹒⁺',
            embed=self.embed
        )
        query = 'DELETE FROM bumpremind'
        await self.bot.db.execute(query)

    async def task(self, end_time):
        await discord.utils.sleep_until(end_time)
        await self.send()

    @commands.Cog.listener()
    async def on_message(self, msg):
        if msg.author.id == self.disboard_id:
            if msg.embeds:
                embed = msg.embeds[0]
                if 'Bump done!' in embed.description:
                    end_time = discord.utils.utcnow() + datetime.timedelta(hours=2)
                    self.bot.loop.create_task(self.task(end_time))
                    query = 'INSERT INTO bumpremind (nextbump) VALUES ($1)'
                    await self.bot.db.execute(query, int(end_time.timestamp()))
                    logging.info(f'Next bump remind at {end_time}')


async def setup(bot):
    await bot.add_cog(BumpRemind(bot))
