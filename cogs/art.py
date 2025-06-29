import discord
import json
from discord.ext import commands

from cogs.utils import Layout

# ART_HOF_CHANNEL_ID = 1191559069627060284
# ART_CHANNEL_IDS = [
#     1191555710291554395,
#     1191555765241131059,
#     1191558039636025485,
#     1191979119173447841,
# ]
# THRESHOLD = 3
# ART_HOF_EMOTE = "<a:ML_star_jump_spin:1147776861154316328>"


class Art(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.art_channel_ids = json.loads(self.bot.vars.get("art-channel-ids"))

        self.bot.log(f"art channel ids: {self.art_channel_ids}", "art")

    async def create_embed(self, message, stars):
        embed = self.bot.get_embed("hof")
        for a in message.attachments:
            if not a.is_spoiler():
                embed.set_image(url=a.url)
                break

        embed = await Layout.fill_embed(
            embed,
            {
                "mention": message.author.mention,
                "messagelink": message.jump_url,
                "text": message.content,
                "stars": stars,
            },
            special=False,
        )
        return embed

    @commands.Cog.listener()
    async def on_message(self, msg):
        if msg.author.bot:
            return
        if msg.channel.id in self.art_channel_ids:
            await msg.add_reaction(self.bot.vars.get("art-hof-emote"))
            await msg.add_reaction("<a:ML_sparkles:899826759313293432>")
            await msg.add_reaction("<a:ML_lilac_heart_NF2U_DNS:1046191564055138365>")
            await msg.create_thread(name="⁺﹒Compliments & Discussion﹗𖹭﹒⁺")

        elif msg.channel.id == self.bot.vars.get("fanart-channel-id"):
            emotes = [
                "<a:ML_lilac_heart_NF2U_DNS:1046191564055138365>",
                "<a:ML_sparkles:899826759313293432>",
                "<a:ML_kiss:923327145164546108>",
            ]
            for emote in emotes:
                await msg.add_reaction(emote)
            await msg.create_thread(name="⁺﹒Compliments & Discussion﹗𖹭﹒⁺")

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):
        if payload.user_id == self.bot.user.id:
            return

        self.bot.log("reaction triggered", "art")

        if payload.channel_id not in self.art_channel_ids:
            return

        self.bot.log("passed channel id check", "art")

        if str(payload.emoji) != self.bot.vars.get("art-hof-emote"):
            return

        self.bot.log("passed emote check", "art")

        message = await self.bot.get_channel(payload.channel_id).fetch_message(
            payload.message_id
        )
        if message.author.id == payload.user_id:
            return
        reaction = discord.utils.get(message.reactions, emoji=payload.emoji)

        query = """SELECT
                       *
                   FROM
                       art_hof
                   WHERE
                       original_id = $1
                """
        row = await self.bot.db.fetchrow(query, payload.message_id)
        stars = len(
            [
                u
                async for u in reaction.users()
                if u.id not in [self.bot.user.id, message.author.id]
            ]
        )

        self.bot.log("row found", "art")

        if row is not None:
            hof_channel = self.bot.get_channel(row["hof_channel_id"])
            hof_msg = await hof_channel.fetch_message(row["hof_id"])
            embed = await self.create_embed(message, stars)
            await hof_msg.edit(embed=embed)
            query = """UPDATE art_hof
                       SET
                           stars = $1
                       WHERE
                           original_id = $2
                    """
            await self.bot.db.execute(query, stars, payload.message_id)
            return

        threshold = self.bot.vars.get("art-hof-threshold")

        self.bot.log(f"stars={stars}, threshold={threshold}", "art")

        if stars < threshold:
            return

        embed = await self.create_embed(message, stars)
        hof_channel = self.bot.get_var_channel("art-hof")
        hof_msg = await hof_channel.send(embed=embed)
        query = """INSERT INTO
                       art_hof (
                           original_id,
                           hof_id,
                           hof_channel_id,
                           author_id,
                           stars
                       )
                   VALUES
                       ($1, $2, $3, $4, $5)
                """

        await self.bot.db.execute(
            query,
            payload.message_id,
            hof_msg.id,
            hof_channel.id,
            message.author.id,
            stars,
        )

        self.bot.log("inserted into db", "art")

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload):
        if payload.channel_id not in self.art_channel_ids:
            return

        if str(payload.emoji) != self.bot.vars.get("art-hof-emote"):
            return

        message = await self.bot.get_channel(payload.channel_id).fetch_message(
            payload.message_id
        )
        if message.author.id == payload.user_id:
            return
        reaction = discord.utils.get(message.reactions, emoji=payload.emoji)
        stars = len(
            [
                u
                async for u in reaction.users()
                if u.id not in [self.bot.user.id, message.author.id]
            ]
        )

        query = """SELECT
                       *
                   FROM
                       art_hof
                   WHERE
                       original_id = $1
                """
        row = await self.bot.db.fetchrow(query, payload.message_id)

        if row is not None:
            hof_channel = self.bot.get_channel(row["hof_channel_id"])
            hof_msg = await hof_channel.fetch_message(row["hof_id"])
            embed = await self.create_embed(message, stars)
            await hof_msg.edit(embed=embed)
            query = """UPDATE art_hof
                       SET
                           stars = $1
                       WHERE
                           original_id = $2
                    """
            await self.bot.db.execute(query, stars, payload.message_id)
            return


async def setup(bot):
    await bot.add_cog(Art(bot))
