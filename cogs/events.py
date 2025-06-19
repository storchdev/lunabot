import json
from typing import TYPE_CHECKING

from discord.ext import commands

from .utils import LayoutContext

if TYPE_CHECKING:
    from bot import LunaBot


class Events(
    commands.Cog, description="Manage join, leave, boost, and birthday messages"
):
    def __init__(self, bot):
        self.bot: "LunaBot" = bot

        with open("guild_data.json") as f:
            self.guild_data = json.load(f)

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
            await message.delete()

    @commands.Cog.listener()
    async def on_member_join(self, member):
        # this handles all server welcs
        if str(member.guild.id) in self.guild_data:
            channel = self.bot.get_channel(
                self.guild_data[str(member.guild.id)]["welc-channel-id"]
            )
            
            role_id = self.guild_data[str(member.guild.id)].get("new-welc-role-id")
            if role_id is None:
                role_text = ""
            else:
                role_text = member.guild.get_role(role_id).mention

            layout = self.bot.get_layout("welc")
            ctx = LayoutContext(author=member)
            # channel = self.bot.get_var_channel('guild-welc')
            bot_msg = await layout.send(channel, ctx, repls={"newwelcrole": role_text})
        
            if member.guild.id == self.bot.vars.get("main-server-id"):
                query = """INSERT INTO
                            welc_messages (user_id, channel_id, message_id)
                        VALUES
                            ($1, $2, $3)
                        """
                await self.bot.db.execute(query, member.id, bot_msg.channel.id, bot_msg.id)

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

    @commands.Cog.listener()
    async def on_member_update(self, before, after):
        booster_role = before.guild.get_role(self.bot.vars.get("booster-role-id"))

        if booster_role not in before.roles and booster_role in after.roles:
            member = after
            layout = self.bot.get_layout("boost")
            channel_id = self.bot.vars.get("boost-channel-id")
            channel = self.bot.get_channel(channel_id)
            ctx = LayoutContext(author=member)
            await layout.send(channel, ctx)


async def setup(bot):
    await bot.add_cog(Events(bot))
