from discord.ext import commands, tasks
import asyncio 
import re 
import discord

VC_IDS = {
    899108709450543115: 1041061422706204802,
    1068342105006673972: 1068342105006673977,
    1004878848262934538: 1004881486991851570,
    1041468894487003176: 1041472654537932911,
}

class Counters(commands.Cog):
    def __init__(self, bot):
        self.bot = bot 

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
    
async def setup(bot):
    await bot.add_cog(Counters(bot))