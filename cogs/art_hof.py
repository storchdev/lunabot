from discord.ext import commands 
import discord 
from .utils import Layout


ART_HOF_CHANNEL_ID = 1191559069627060284
ART_CHANNEL_IDS = [
    1191555710291554395,
    1191555765241131059,
    1191558039636025485,
    1191979119173447841
]
THRESHOLD = 3
ART_HOF_EMOTE = '<a:LC_star_jump_spin:1147776861154316328>'


class ArtHof(commands.Cog):

    def __init__(self, bot):
        self.bot = bot 

    def create_embed(self, message, stars):
        embed = self.bot.get_embed('hof')
        for a in message.attachments:    
            if not a.is_spoiler():
                embed.set_image(url=a.url)
                break

        embed = Layout.fill_embed_one(embed, 'mention', message.author.mention)
        embed = Layout.fill_embed_one(embed, 'messagelink', message.jump_url)
        embed = Layout.fill_embed_one(embed, 'text', message.content)
        embed = Layout.fill_embed_one(embed, 'stars', stars)
        return embed 

    @commands.Cog.listener()
    async def on_message(self, msg):
        if msg.channel.id not in ART_CHANNEL_IDS:
            return
        if msg.author.bot:
            return
        await msg.add_reaction(ART_HOF_EMOTE)
        await msg.add_reaction("<a:ML_sparkles:899826759313293432>")
        await msg.add_reaction("<a:LC_lilac_heart_NF2U_DNS:1046191564055138365>")
        await msg.create_thread(name="⁺﹒Compliments & Discussion﹗𖹭﹒⁺")

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):
        if payload.channel_id not in ART_CHANNEL_IDS:
            return
        
        if str(payload.emoji) != ART_HOF_EMOTE:
            return

        message = await self.bot.get_channel(payload.channel_id).fetch_message(payload.message_id)
        if message.author.id == payload.user_id:
            return
        reaction = discord.utils.get(message.reactions, emoji=payload.emoji)

        query = 'SELECT * FROM art_hof WHERE original_id = $1' 
        row = await self.bot.db.fetchrow(query, payload.message_id)
        stars = len([u async for u in reaction.users() if u.id not in [self.bot.user.id, message.author.id]])

        if row is not None:
            hof_channel = self.bot.get_channel(row['hof_channel_id'])
            hof_msg = await hof_channel.fetch_message(row['hof_id'])
            embed = self.create_embed(message, stars)
            await hof_msg.edit(embed=embed)
            query = 'UPDATE art_hof SET stars = $1 WHERE original_id = $2'
            await self.bot.db.execute(query, stars, payload.message_id)
            return 
        
        if stars < THRESHOLD:
            return
        
        embed = self.create_embed(message, stars)
        hof_channel = self.bot.get_channel(ART_HOF_CHANNEL_ID)
        hof_msg = await hof_channel.send(embed=embed)
        query = '''INSERT INTO art_hof
                       (original_id, hof_id, hof_channel_id, author_id, stars) 
                   VALUES
                       ($1, $2, $3, $4, $5)
                '''
        await self.bot.db.execute(query, 
            payload.message_id, 
            hof_msg.id, 
            hof_channel.id, 
            message.author.id, 
            stars
        )

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload):
        if payload.channel_id not in ART_CHANNEL_IDS:
            return
        
        if str(payload.emoji) != ART_HOF_EMOTE:
            return 

        message = await self.bot.get_channel(payload.channel_id).fetch_message(payload.message_id)
        if message.author.id == payload.user_id:
            return
        reaction = discord.utils.get(message.reactions, emoji=payload.emoji)
        stars = len([u async for u in reaction.users() if u.id not in [self.bot.user.id, message.author.id]])

        query = 'SELECT * FROM art_hof WHERE original_id = $1' 
        row = await self.bot.db.fetchrow(query, payload.message_id)

        if row is not None:
            hof_channel = self.bot.get_channel(row['hof_channel_id'])
            hof_msg = await hof_channel.fetch_message(row['hof_id'])
            embed = self.create_embed(message, stars)
            await hof_msg.edit(embed=embed)
            query = 'UPDATE art_hof SET stars = $1 WHERE original_id = $2'
            await self.bot.db.execute(query, stars, payload.message_id)
            return 


async def setup(bot):
    await bot.add_cog(ArtHof(bot))
