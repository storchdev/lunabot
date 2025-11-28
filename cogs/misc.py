import json
import random
from typing import TYPE_CHECKING

import discord
from discord.ext import commands

if TYPE_CHECKING:
    from bot import LunaBot


class Misc(commands.Cog):
    def __init__(self, bot):
        self.bot: "LunaBot" = bot

        # TODO: use db
        with open("cogs/webhooks.json") as f:
            self.webhooks = json.load(f)
        with open("cogs/static/8ball.json") as f:
            self._8ball_answers = json.load(f)

    # async def cog_load(self):
    #     self.urmom.start()

    # async def cog_unload(self):
    #     self.urmom.stop()

    @commands.hybrid_command()
    async def topic(self, ctx):
        """Get a random topic to talk about"""
        with open("cogs/static/topics.json") as f:
            topics: list[str] = json.load(f)

        if len(topics) == 0:
            return await ctx.send("Uh oh, no more topics to be found!")

        topic = random.choice(topics)

        layout = self.bot.get_layout("topic")
        await layout.send(ctx, repls={"question": topic})

        if self.bot.vars.get("remove-topic-after-use") == 1:
            topics.remove(topic)
            with open("cogs/static/topics.json", "w") as f:
                json.dump(topics, f, indent=4)

            priv = self.bot.get_var_channel("private")
            assert isinstance(priv, discord.TextChannel)

            if len(topics) < 10:
                await priv.send(
                    f"<@{self.bot.owner_id}> - {len(topics)} topics remaining"
                )

    @commands.hybrid_command()
    async def polyjuice(self, ctx, member: discord.Member, *, sentence: str):
        """Send a message as another user"""
        if ctx.interaction is None:
            await ctx.message.delete()
        else:
            await ctx.interaction.response.send_message("Sending...", ephemeral=True)
        if str(ctx.channel.id) not in self.webhooks:
            webhook = await ctx.channel.create_webhook(name="polyjuice")
            self.webhooks[str(ctx.channel.id)] = webhook.url
            with open("webhooks.json", "w") as f:
                json.dump(self.webhooks, f)
        else:
            webhook = discord.Webhook.from_url(
                self.webhooks[str(ctx.channel.id)], session=self.bot.session
            )

        await webhook.send(
            sentence,
            username=member.display_name,
            avatar_url=member.display_avatar.url,
            allowed_mentions=discord.AllowedMentions.none(),
        )

    @commands.hybrid_command(name="8ball")
    async def _8ball(self, ctx, *, question: str):
        """Ask the magic 8ball a question"""
        answer = random.choice(self._8ball_answers)
        answer = f"*{answer}*"
        layout = self.bot.get_layout("8ball")
        await layout.send(ctx, repls={"question": question, "answer": answer})

    @commands.hybrid_command(name="qna")
    async def qna(self, ctx, *, question: str):
        """Ask a question to the QnA channel"""
        channel = self.bot.get_var_channel("qna")
        layout = self.bot.get_layout("qna")
        msg = await layout.send(channel, repls={"question": question})
        await msg.create_thread(name="⁺﹒Luna's Answer﹗𖹭﹒⁺")
        await ctx.send(
            f"Your question has been sent to the QnA channel! {msg.jump_url}"
        )

    @commands.command()
    async def ratio(self, ctx):
        total = len(ctx.guild.members)
        online = len(
            [m for m in ctx.guild.members if m.status is not discord.Status.offline]
        )
        pc = str(round(online / total * 100))
        await ctx.send(f"{pc}% ({online}/{total})")

    # @tasks.loop(seconds=10)
    # async def urmom(self):
    #     print(0 / 0)

    @commands.command()
    async def serverbanner(self, ctx, *, member: discord.Member = None):
        if member is None:
            member = ctx.author

        banner = member.guild_banner or (await self.bot.fetch_user(member.id)).banner
        if banner is None:
            return await ctx.send("no banner :(")

        embed = discord.Embed(
            color=self.bot.DEFAULT_EMBED_COLOR, description="six seven"
        ).set_image(url=banner.url)
        await ctx.send(embed=embed)

    @commands.command()
    @commands.is_owner()
    async def cv2test(self, ctx):
        class Components(discord.ui.LayoutView):
            container1 = discord.ui.Container(
                discord.ui.Section(
                    discord.ui.TextDisplay(content="# welcome!"),
                    # discord.ui.TextDisplay(
                    #     content="Always lick a cactus before you become famous."
                    # ),
                    accessory=discord.ui.Thumbnail(
                        media="https://media.discordapp.net/attachments/1122048063771512872/1150947556512251934/IMG_4612.jpg?ex=6913d171&is=69127ff1&hm=296f170740e4ef7f3787f6521c515ec4856ace391c14e2fe2c87adeaf85b608f&",
                    ),
                ),
                discord.ui.Separator(
                    visible=True, spacing=discord.SeparatorSpacing.large
                ),
                discord.ui.TextDisplay(
                    content="True wisdom comes from hug a stranger during lazy times."
                ),
                discord.ui.Separator(
                    visible=True, spacing=discord.SeparatorSpacing.large
                ),
                discord.ui.TextDisplay(content="-# fanart made by someone"),
                accent_colour=discord.Colour(16711422),
            )

        view = Components()
        await ctx.send(view=view)


async def setup(bot):
    await bot.add_cog(Misc(bot))
