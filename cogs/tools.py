import asyncio
import csv
import importlib
import json
from io import BytesIO, StringIO
from pkgutil import iter_modules
from typing import TYPE_CHECKING, List, Literal, Optional, Union

import aiohttp
import dateparser
import discord
from discord import ui
from discord.ext import commands
from discord.utils import escape_markdown
from rapidfuzz import fuzz

from .utils import ConfirmView, EmbedEditor, View

if TYPE_CHECKING:
    from bot import LunaBot


class JumpModal(ui.Modal):
    index = discord.ui.TextInput(label="Index")

    def __init__(self, view):
        super().__init__(title="Jump to index")
        self.view = view

    async def on_submit(self, interaction):
        try:
            index = int(self.index.value)
        except ValueError:
            return await interaction.response.send_message(
                "Invalid index", ephemeral=True
            )
        if index < 0 or index >= len(self.view.roles):
            return await interaction.response.send_message(
                f"Index out of range; Please enter a number between 0 and {len(self.view.roles) - 1}",
                ephemeral=True,
            )

        self.view.index = index
        self.view.role = self.view.roles[index]
        await self.view.update_message(interaction)


class CleanRoleView(View):
    def __init__(self, ctx, roles: List[discord.Role]):
        super().__init__(bot=ctx.bot, owner=ctx.author)
        self.ctx = ctx
        self.roles = sorted(
            filter(lambda r: r.is_assignable(), roles), key=lambda r: r.position
        )
        self.index = 0
        self.role = self.roles[self.index]

    def get_embed(self):
        embed = discord.Embed(
            title=self.role.name,
        )
        embed.add_field(name="Index", value=self.index)
        embed.add_field(name="Members", value=len(self.role.members), inline=False)
        embed.add_field(
            name="Created at", value=discord.utils.format_dt(self.role.created_at, "R")
        )
        return embed

    async def update_message(self, interaction=None):
        embed = self.get_embed()
        if interaction:
            await interaction.response.edit_message(embed=embed)
        else:
            await self.message.edit(embed=embed)

    @discord.ui.button(label="Previous")
    async def previous(self, interaction, button):
        if self.index == 0:
            return await interaction.response.defer()
        self.index -= 1
        self.role = self.roles[self.index]
        await self.update_message(interaction)

    @discord.ui.button(label="Next")
    async def next(self, interaction, button):
        if self.index == len(self.roles) - 1:
            return await interaction.response.defer()
        self.index += 1
        self.role = self.roles[self.index]
        await self.update_message(interaction)

    @discord.ui.button(label="Jump")
    async def jump(self, interaction, button):
        await interaction.response.send_modal(JumpModal(self))

    @discord.ui.button(label="View members", row=1)
    async def view_members(self, interaction, button):
        members = ""
        for member in self.role.members:
            if len(members + member.mention + "\n") > 2000:
                break
            members += member.mention + "\n"

        await interaction.response.send_message(members, ephemeral=True)

    @discord.ui.button(label="Accidental delete prevention", row=2, disabled=True)
    async def _(self, interaction, button):
        pass

    @discord.ui.button(label="Accidental delete prevention", row=3, disabled=True)
    async def __(self, interaction, button):
        pass

    @discord.ui.button(label="Delete", row=4, style=discord.ButtonStyle.danger)
    async def delete(self, interaction, button):
        if len(self.role.members) > 10:
            confirmview = ConfirmView(self.ctx)
            await interaction.response.send_message(
                "Are you sure you want to delete this role?", view=confirmview
            )
            await confirmview.wait()
            if confirmview.choice is True:
                self.roles.remove(self.role)
                self.role = self.roles[self.index]
                await confirmview.final_interaction.response.defer()
                await self.role.delete()
                await self.update_message()
            else:
                await confirmview.final_interaction.response.edit_message(
                    content="Cancelled", view=None
                )
        else:
            await interaction.response.defer()
            await self.role.delete()
            self.roles.remove(self.role)
            self.role = self.roles[self.index]
            await self.update_message()


class DTStyleButton(discord.ui.Button):
    def __init__(self, label):
        super().__init__(label=label)

    async def callback(self, interaction: discord.Interaction):
        md = self.view.mds[int(self.label) - 1]
        await interaction.response.edit_message(content=md, view=None)
        self.view.stop()


class DTStyleChooser(View):
    def __init__(self, ctx, mds):
        super().__init__(bot=ctx.bot, owner=ctx.author)
        self.mds = mds

        for i in range(len(mds)):
            self.add_item(DTStyleButton(str(i + 1)))


class StickerFlags(commands.FlagConverter):
    name: str
    description: str
    emoji: str
    url: str


class Tools(commands.Cog, description="storchs tools"):
    def __init__(self, bot):
        self.bot: "LunaBot" = bot

    async def cog_check(self, ctx):
        return (
            ctx.author.guild_permissions.administrator
            or ctx.author.id == self.bot.owner_id
        )

    async def reload_cog(self, cog, info):
        try:
            await self.bot.reload_extension("cogs." + cog)
            info.append(f"Reloaded cog `{cog}`")
        except commands.ExtensionNotLoaded:
            await self.bot.load_extension("cogs." + cog)
            info.append(f"Loaded cog `{cog}`")
        except Exception:
            info.append(f"Error when reloading cog `{cog}`")

    async def reload_module(self, mname, info):
        try:
            module = __import__("cogs." + mname)
            importlib.reload(module)
            info.append(f"Reloaded module `{mname}`")
        except Exception:
            info.append(f"Error when reloading module `{module}`")

    @commands.command()
    async def sql(self, ctx, *, query):
        if query.lower().startswith("select"):
            try:
                rows = await self.bot.db.fetch(query)
            except Exception as e:
                await ctx.send(f"Error: {e}")
                return
            if not rows:
                await ctx.send("No results.")
                return
            buf = StringIO()
            writer = csv.writer(buf)
            writer.writerow(rows[0].keys())
            for row in rows:
                row = dict(row)
                writer.writerow(row.values())
            buf.seek(0)
            await ctx.send(file=discord.File(buf, filename="query.csv"))
        else:
            try:
                await self.bot.db.execute(query)
            except Exception as e:
                await ctx.send(f"Error: {e}")
                return

            await ctx.send("Done!")

    @commands.command()
    async def buildembed(self, ctx):
        view = EmbedEditor(self.bot, ctx.author, timeout=None)
        view.message = await ctx.send(
            "Please hit the **Submit** button when you're ready!", view=view
        )
        await view.wait()
        if view.cancelled:
            return
        await ctx.send(embed=view.current_embed)
        await view.message.delete()

    # @commands.command()
    # async def r(self, ctx):
    #     with open('cogs/settings.json') as f:
    #         settings = json.load(f)
    #     modules = settings['active_modules']
    #     cogs = settings['active_cogs']
    #     info = []
    #     for mname in modules:
    #         await self.reload_module(mname, info)
    #     for cog in cogs:
    #         await self.reload_cog(cog, info)

    #     await ctx.send('\n'.join(info))

    @commands.command()
    async def r(self, ctx: commands.Context, *cogs):
        """really lazy reload with fuzzy find + jsk"""
        cog_names = []
        for lazycog in cogs:
            max_ratio = 0
            best_cog = None
            for cog in [m.name for m in iter_modules(["cogs"])]:
                ratio = fuzz.ratio(cog, lazycog)
                if ratio > max_ratio:
                    max_ratio = ratio
                    best_cog = cog
            cog_names.append("cogs." + best_cog)

        await ctx.invoke(self.bot.get_command("jsk reload"), cog_names)

    # @commands.command()
    # async def rm(self, ctx, *modules):
    #     info = []
    #     for mname in modules:
    #         await self.reload_module(mname, info)
    #     await ctx.send('\n'.join(info))

    @commands.command()
    async def grabembed(self, ctx, url):
        tokens = url.split("/")
        channel_id = int(tokens[5])
        message_id = int(tokens[6])
        channel = self.bot.get_channel(channel_id)
        message = await channel.fetch_message(message_id)
        embed = message.embeds[0].to_dict()

        # if 'footer' in embed:
        # embed.pop('footer')

        data = json.dumps(embed, indent=4)
        await ctx.send(f"```json\n{data}```")

    @commands.command()
    async def grabbuttonemoji(self, ctx, url):
        tokens = url.split("/")
        channel_id = int(tokens[5])
        message_id = int(tokens[6])
        channel = self.bot.get_channel(channel_id)
        message = await channel.fetch_message(message_id)
        view = ui.View.from_message(message)
        await ctx.send(escape_markdown(str(view.children[0].emoji)))

    @commands.command(aliases=["delmessage", "delmsg", "delmessages"])
    async def delmsgs(self, ctx, urls):
        for url in urls.split():
            tokens = url.split("/")
            channel_id = int(tokens[-2])
            message_id = int(tokens[-1])
            channel = self.bot.get_channel(channel_id)
            message = await channel.fetch_message(message_id)
            await message.delete()
        await ctx.message.delete()

    @commands.command()
    async def setroleicon(self, ctx, role: discord.Role, url: str):
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                if resp.status != 200:
                    return await ctx.send("Failed to fetch image.")
                data = await resp.read()

        await role.edit(display_icon=data)
        await ctx.send("Role icon set.")

    @commands.command()
    async def addsticker(self, ctx, *, flags: StickerFlags):
        async with aiohttp.ClientSession() as session:
            async with session.get(flags.url) as resp:
                if resp.status != 200:
                    return await ctx.send("Failed to fetch image.")
                data = await resp.read()

        buf = BytesIO(data)
        buf.seek(0)
        file = discord.File(buf, filename="sticker.png")

        sticker = await ctx.guild.create_sticker(
            name=flags.name, description=flags.description, emoji=flags.emoji, file=file
        )

        await ctx.send(f"Sticker `{sticker.name}` created.")

    @commands.command()
    async def grabtimestamp(self, ctx, obj: Union[discord.Message]):
        await ctx.send(obj.created_at.timestamp())

    @commands.command()
    async def sync(
        self,
        ctx: commands.Context,
        guilds: commands.Greedy[discord.Object],
        spec: Optional[Literal["~", "*", "^"]] = None,
    ) -> None:
        if not guilds:
            if spec == "~":
                synced = await ctx.bot.tree.sync(guild=ctx.guild)
            elif spec == "*":
                ctx.bot.tree.copy_global_to(guild=ctx.guild)
                synced = await ctx.bot.tree.sync(guild=ctx.guild)
            elif spec == "^":
                ctx.bot.tree.clear_commands(guild=ctx.guild)
                await ctx.bot.tree.sync(guild=ctx.guild)
                synced = []
            else:
                synced = await ctx.bot.tree.sync()

            await ctx.send(
                f"Synced {len(synced)} commands {'globally' if spec is None else 'to the current guild.'}"
            )
            return

        ret = 0
        for guild in guilds:
            try:
                await ctx.bot.tree.sync(guild=guild)
            except discord.HTTPException:
                pass
            else:
                ret += 1

        await ctx.send(f"Synced the tree to {ret}/{len(guilds)}.")

    @commands.command()
    async def timethingy(self, ctx, *, date_str=None):
        if date_str is None:
            dt = discord.utils.utcnow()
        else:
            dt = await asyncio.to_thread(
                dateparser.parse,
                date_str,
                settings={
                    "TIMEZONE": await ctx.fetch_timezone(),
                    "RETURN_AS_TIMEZONE_AWARE": True,
                },
            )
            if dt is None:
                await ctx.send("Invalid date string.")
                return
        styles = "tTdDfFR"
        mds = [discord.utils.format_dt(dt, s) for s in styles]
        content = "\n".join(f"**{i}** - {md}" for i, md in enumerate(mds, 1))
        view = DTStyleChooser(ctx, mds)
        view.message = await ctx.send(content, view=view)

    @commands.command()
    async def cleanroles(self, ctx):
        roles = ctx.guild.roles
        view = CleanRoleView(ctx, roles)
        view.message = await ctx.send(embed=view.get_embed(), view=view)

    @commands.command()
    async def addlf(self, ctx, *, flag: str):
        if flag in self.bot.log_flags:
            return await ctx.send("flag already enabled")

        self.bot.log_flags.append(flag)
        jsonstr = json.dumps(self.bot.log_flags)
        self.bot.vars["log-flags"] = jsonstr
        query = "UPDATE vars SET value = $1 WHERE name = $2"
        await self.bot.db.execute(query, jsonstr, "log-flags")

        await ctx.send(f"Done! Current flags: `{jsonstr}`")

    @commands.command()
    async def removelf(self, ctx, *, flag: str):
        if flag not in self.bot.log_flags:
            return await ctx.send("flag not already enabled")

        self.bot.log_flags.remove(flag)
        jsonstr = json.dumps(self.bot.log_flags)
        self.bot.vars["log-flags"] = jsonstr
        query = "UPDATE vars SET value = $1 WHERE name = $2"
        await self.bot.db.execute(query, jsonstr, "log-flags")

        await ctx.send(f"Done! Current flags: `{jsonstr}`")


async def setup(bot):
    await bot.add_cog(Tools(bot))
