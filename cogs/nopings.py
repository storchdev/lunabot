from discord.ext import commands
import discord
import json

from cogs.utils import View


class ResendView(View):
    def __init__(self, bot, pinger, content):
        self.pinger = pinger
        self.content = content
        super().__init__(bot=bot, owner=pinger, timeout=300)

    # async def interaction_check(self, inter):
    #     if inter.user != self.pinger:
    #         await inter.response.defer()
    #         return False
    #     return True

    @discord.ui.button(label="Resend")
    async def resend(self, inter, button):
        await inter.response.send_message(self.content, ephemeral=True)


class NoPings(commands.Cog):
    """The description for Nopings goes here."""

    def __init__(self, bot):
        self.bot = bot
        self.no_ping_ids = set()

    async def cog_load(self):
        self.no_ping_ids = set(json.loads(self.bot.vars.get("no-ping-ids")))

    async def add_no_ping(self, uid: int):
        if uid in self.no_ping_ids:
            return

        self.no_ping_ids.add(uid)
        new_var = json.dumps(list(self.no_ping_ids))

        self.bot.vars["no-ping-ids"] = new_var
        query = "UPDATE vars SET value = $1 WHERE name = $2"
        await self.bot.db.execute(query, new_var, "no-ping-ids")

    async def remove_no_ping(self, uid: int):
        if uid not in self.no_ping_ids:
            return

        self.no_ping_ids.remove(uid)
        new_var = json.dumps(list(self.no_ping_ids))

        self.bot.vars["no-ping-ids"] = new_var
        query = "UPDATE vars SET value = $1 WHERE name = $2"
        await self.bot.db.execute(query, new_var, "no-ping-ids")

    @commands.Cog.listener()
    async def on_message(self, msg: discord.Message):
        if not msg.guild or msg.author.bot:
            return

        # if msg.author.guild_permissions.manage_messages:
        #     return

        for user in msg.mentions:
            if user == msg.author:
                continue
            if user.id in self.no_ping_ids:
                await msg.delete()
                layout = self.bot.get_layout("noping")
                v = ResendView(self.bot, msg.author, msg.content)
                await layout.send(msg.channel, view=v, delete_after=30)

    @commands.hybrid_command(name="noping", description="adds you to the no-ping list")
    async def noping(self, ctx):
        uid = ctx.author.id
        if uid not in self.no_ping_ids:
            await self.add_no_ping(uid)
            layout = self.bot.get_layout("nopingagreement")
            await layout.send(ctx, ephemeral=True)
        else:
            await self.remove_no_ping(uid)
            await ctx.send("Removed you from the no-ping list!", ephemeral=True)


async def setup(bot):
    await bot.add_cog(NoPings(bot))
