import json
import random
from datetime import datetime
from typing import TYPE_CHECKING
import discord

from discord.ext import commands

from .utils import LayoutContext
from .vars import set_var

if TYPE_CHECKING:
    from bot import LunaBot


WELC_PROMPTS = [
    "What is your favorite art period and why??",
    "Who is your favorite artist and why??",
    "Share your favorite artwork of your own",
    "Share with us your latest WIP",
    "What is your favorite type of artistic media to work with and why??",
    "What is one piece of art advice that you heavily agree with??",
    "What is one piece of art advice that you heavily disagree with??",
    "What type of art do you normally make??",
    "Do you have any favorite games??",
    "Do you have any favorite books??",
    "Do you have any favorite movies??",
    "Do you have any favorite songs??",
    "Do you have any favorite animes??",
    "What was your inspiration or reason for your profile picture??",
    "Why did you decide to join??",
]


class Events(
    commands.Cog, description="Manage join, leave, boost, and birthday messages"
):
    """Join/leave handlers, auto-reactions."""

    def __init__(self, bot):
        self.bot: "LunaBot" = bot

        with open("guild_data.json") as f:
            self.guild_data = json.load(f)

        self.cmd_log = []

    async def cog_check(self, ctx):
        return (
            ctx.author.guild_permissions.administrator
            or ctx.author.id == self.bot.owner_id
        )

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.channel.id == self.bot.vars.get("free-offers-channel-id"):
            await message.add_reaction("<a:LCM_mail:1151561338317983966>")
        if message.channel.id == self.bot.vars.get("void-channel-id"):
            try:
                await message.delete()
            except discord.NotFound:
                print(f"Void channel message not found: {message.jump_url}")

    # @commands.Cog.listener()
    # async def on_member_join(self, member):

    # this handles all server welcs

    # if member.guild.id == self.bot.GUILD_ID:
    #     layout = self.bot.get_layout('welc')
    #     ctx = LayoutContext(author=member)
    #     channel = self.bot.get_var_channel('welc')
    #     await layout.send(channel, ctx)

    @commands.command()
    async def boosttest(self, ctx):
        booster_role = ctx.guild.get_role(self.bot.vars.get("booster-role-id"))
        if booster_role not in ctx.author.roles:
            await ctx.author.add_roles(booster_role)
        else:
            await ctx.author.remove_roles(booster_role)
        await ctx.send(":white_check_mark:")

    @commands.command()
    async def togglewelc(self, ctx):
        """Turn welcome messages on or off entirely."""
        on = 0 if self.bot.vars.get("do-welcs") == 1 else 1
        await set_var(self.bot, "do-welcs", str(on))
        await ctx.send(f"Welcome messages are now **{'on' if on else 'off'}**.")

    @commands.command()
    async def switchwelc(self, ctx):
        """Switch between the new (prompt) and old (role ping) welcome layouts."""
        new = 0 if self.bot.vars.get("new-welc") == 1 else 1
        await set_var(self.bot, "new-welc", str(new))
        style = "new (`welc2`, with prompt)" if new else "old (`welc`, with role ping)"
        await ctx.send(f"Welcome messages now use the {style} layout.")

    @commands.Cog.listener()
    async def on_member_update(self, before, after):
        if len(before.roles) == len(after.roles):
            return

        booster_role = before.guild.get_role(self.bot.vars.get("booster-role-id"))
        if (
            booster_role
            and booster_role not in before.roles
            and booster_role in after.roles
        ):
            member = after
            layout = self.bot.get_layout("boost")
            channel_id = self.bot.vars.get("boost-channel-id")
            channel = self.bot.get_channel(channel_id)
            ctx = LayoutContext(author=member)
            await layout.send(channel, ctx)
            return

        shopper_role = before.guild.get_role(self.bot.vars.get("shopper-role-id"))
        if (
            shopper_role
            and shopper_role not in before.roles
            and shopper_role in after.roles
        ):
            member = after
            if (
                self.bot.vars.get("do-welcs") == 1
                and str(member.guild.id) in self.guild_data
            ):
                channel = self.bot.get_channel(
                    self.guild_data[str(member.guild.id)]["welc-channel-id"]
                )

                ctx = LayoutContext(author=member)
                # channel = self.bot.get_var_channel('guild-welc')
                if self.bot.vars.get("new-welc") == 1:
                    layout = self.bot.get_layout("welc2")
                    repls = {"prompt": random.choice(WELC_PROMPTS)}
                else:
                    role_id = self.guild_data[str(member.guild.id)].get(
                        "new-welc-role-id"
                    )
                    if role_id is None:
                        role_text = ""
                    else:
                        role_text = member.guild.get_role(role_id).mention
                    layout = self.bot.get_layout("welc")
                    repls = {"newwelcrole": role_text}

                bot_msg = await layout.send(channel, ctx, repls=repls)

                if member.guild.id == self.bot.vars.get("main-server-id"):
                    query = """INSERT INTO
                                welc_messages (user_id, channel_id, message_id)
                            VALUES
                                ($1, $2, $3)
                            ON CONFLICT (user_id) DO UPDATE
                            SET
                                channel_id = $2,
                                message_id = $3
                            """
                    await self.bot.db.execute(
                        query, member.id, bot_msg.channel.id, bot_msg.id
                    )

    @commands.Cog.listener()
    async def on_command_completion(self, ctx):
        self.cmd_log.append(
            f"[{datetime.now().isoformat()}] {ctx.author.name} ({ctx.author.id}) used [{ctx.command.qualified_name.upper()}]({ctx.message.jump_url})"
        )

        if len(self.cmd_log) >= 10:
            with open("commands.log", "a") as f:
                f.write("\n".join(self.cmd_log) + "\n")
            self.cmd_log = []

    async def cog_unload(self):
        if len(self.cmd_log) > 0:
            with open("commands.log", "a") as f:
                f.write("\n".join(self.cmd_log) + "\n")


async def setup(bot):
    await bot.add_cog(Events(bot))
