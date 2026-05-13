import asyncio
import json
from datetime import timedelta
from io import StringIO
from typing import TYPE_CHECKING

import discord
from discord.ext import commands

from cogs.utils import InvalidURL, LayoutContext
from cogs.utils.checks import is_admin

if TYPE_CHECKING:
    from bot import LunaBot

import time
from typing import Optional

# Custom rust module
from fuzzy_rust import extract_bests


def is_art_manager():
    async def predicate(ctx: commands.Context):
        if ctx.author.id not in json.loads(ctx.bot.vars.get("art-manager-ids")):
            # layout = ctx.bot.get_layout("lunaonly")
            # await layout.send(ctx)
            return False
        return True

    return commands.check(predicate)


class Staff(commands.Cog):
    """The description for Staff goes here."""

    def __init__(self, bot):
        self.bot: "LunaBot" = bot
        self.role_lock = True

    async def cog_check(self, ctx):
        return (
            ctx.guild.get_role(self.bot.vars.get("staff-role-id")) in ctx.author.roles
        )

    @commands.command()
    async def userlookup(self, ctx, limit: Optional[int] = 5, *, query: str):
        t1 = time.perf_counter()
        search_terms = {}

        # Gather search terms and allow multiple users with the same name
        def slop():
            for m in ctx.guild.members:
                terms = [m.display_name, m.global_name, m.name]
                for term in terms:
                    if term:  # Ensure term is not None
                        if term in search_terms:
                            search_terms[term].append(m)
                        else:
                            search_terms[term] = [m]

        await asyncio.to_thread(slop)

        t2 = time.perf_counter()

        # Perform Rust-based fuzzy matching
        results = await asyncio.to_thread(
            extract_bests,
            query,
            list(search_terms.keys()),
            limit,
        )

        # slow python-based
        # results = await asyncio.to_thread(
        #     process.extract,
        #     query,
        #     search_terms.keys(),
        #     limit=limit,
        # )

        t3 = time.perf_counter()
        embed = discord.Embed(title="Best Matches", color=self.bot.DEFAULT_EMBED_COLOR)

        desc = []
        seen = set()
        for x in results:
            name = x[0]
            for member in search_terms[
                name
            ]:  # Append all members with the matching name
                if member in seen:
                    continue
                seen.add(member)
                desc.append(
                    f"{member.mention} (`{member.name}` a.k.a. {member.display_name})"
                )

        embed.description = "\n".join(desc)
        t4 = time.perf_counter()
        if ctx.author.id == self.bot.owner_id:
            await ctx.send(
                f"search_terms={len(search_terms)}, preprocess={(t2 - t1):.2f}, fuzzy={(t3 - t2):.2f}, postprocess={(t4 - t3):.2f}"
            )

        await ctx.send(embed=embed)

    @commands.command()
    async def rolelookup(self, ctx, limit: Optional[int] = 5, *, query: str):
        t1 = time.perf_counter()
        search_terms = {}

        # Gather search terms and allow multiple users with the same name
        for r in ctx.guild.roles:
            terms = [r.name]
            for term in terms:
                if term:  # Ensure term is not None
                    if term in search_terms:
                        search_terms[term].append(r)
                    else:
                        search_terms[term] = [r]

        t2 = time.perf_counter()

        # Perform Rust-based fuzzy matching
        results = await asyncio.to_thread(
            extract_bests,
            query,
            list(search_terms.keys()),
            limit,
            # process.extractBests,
            # query,
            # search_terms.keys(),
            # limit=limit,
        )

        # slow python-based
        # results = await asyncio.to_thread(
        #     process.extractBests,
        #     query,
        #     search_terms.keys(),
        #     limit=limit,
        # )

        t3 = time.perf_counter()
        embed = discord.Embed(title="Best Matches", color=self.bot.DEFAULT_EMBED_COLOR)

        desc = []
        seen = set()
        for name, _ in results:
            for role in search_terms[name]:  # Append all roles with the matching name
                if role in seen:
                    continue
                seen.add(role)
                desc.append(f"{role.mention} (`{role.name}`)")

        embed.description = "\n".join(desc)
        t4 = time.perf_counter()
        if ctx.author.id == self.bot.owner_id:
            await ctx.send(
                f"search_terms={len(search_terms)}, preprocess={(t2 - t1):.2f}, fuzzy={(t3 - t2):.2f}, postprocess={(t4 - t3):.2f}"
            )

        await ctx.send(embed=embed)

    @commands.command()
    async def mod(self, ctx, *, user: discord.Member):
        # hardcoded ids
        if ctx.author.id != 426110953021505549:
            return await ctx.send("you are not miku")

        role = ctx.guild.get_role(899119780701810718)
        self.role_lock = False
        await user.add_roles(role)
        await ctx.send("Done!")
        await asyncio.sleep(1)
        self.role_lock = True

    @commands.command()
    async def admin(self, ctx, *, user: discord.Member):
        # hardcoded ids
        if ctx.author.id not in (496225545529327616, 675058943596298340):
            return await ctx.send("you are not luna or molly")

        role = ctx.guild.get_role(899119768567689237)
        self.role_lock = False
        await user.add_roles(role)
        await ctx.send("Done!")
        await asyncio.sleep(1)
        self.role_lock = True

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        if self.bot.vars.get("role-protection") == 0:
            return

        before_role_ids = set(r.id for r in before.roles)
        for role in after.roles:
            if role.id not in before_role_ids:
                if (
                    role.permissions.administrator or role.permissions.manage_messages
                ) and self.role_lock:
                    await after.remove_roles(role)
                    await self.bot.get_var_channel("mod").send(
                        f"Removed `{role.name}` from {after.mention} ({after.id}) because it was not added using `!mod` or `!admin`."
                    )

    @commands.command()
    async def purge(self, ctx, arg1, *, arg2=None):
        if arg2 is None:
            # normal purge
            if not arg1.isdigit():
                return await ctx.send("Not a valid number!")

            if not is_admin(ctx):
                dt = await self.bot.get_cooldown_end(
                    "purge", 3600, rate=5, obj=ctx.author
                )
                if dt is not None:
                    return await ctx.send("purging on cooldown to prevent abuse")

            x = int(arg1)
            if x > 99:
                x = 99

            await ctx.channel.purge(limit=x + 1)
            embed = discord.Embed(
                description=f"{ctx.author.mention} purged {x} in {ctx.channel.mention}"
            )
            await self.bot.get_var_channel("private").send(embed=embed)
        else:
            # user purge
            mc = commands.MemberConverter()

            for argm, argx in ((arg1, arg2), (arg2, arg1)):
                try:
                    member = await mc.convert(ctx, argm)
                    break
                except commands.MemberNotFound:
                    member = None

            if member is None:
                return await ctx.send("Not a valid member!")
            if not argx.isdigit():
                return await ctx.send("Not a valid number!")

            if not is_admin(ctx):
                dt = await self.bot.get_cooldown_end(
                    "purge", 3600, rate=5, obj=ctx.author
                )
                if dt is not None:
                    return await ctx.send("purging on cooldown to prevent abuse")

            x = int(argx)
            if x > 99:
                x = 99

            plist = []
            now = discord.utils.utcnow()

            async for msg in ctx.channel.history(limit=500):
                if msg == ctx.message:
                    continue
                if len(plist) >= x:
                    break
                if (now - msg.created_at).total_seconds() > 86400 * 14:
                    break
                if msg.author == member:
                    plist.append(msg)

            plist.append(ctx.message)
            await ctx.channel.delete_messages(plist)
            embed = discord.Embed(
                description=f"{ctx.author.mention} purged {len(plist)} in {ctx.channel.mention}"
            )
            await self.bot.get_var_channel("private").send(embed=embed)

    @commands.command()
    async def savechat(self, ctx, message1: str, message2: str):
        try:
            m1 = await self.bot.fetch_message_from_url(message1)
            m2 = await self.bot.fetch_message_from_url(message2)
        except InvalidURL:
            return await ctx.send("one of those message links is invalid")

        if m1.channel != m2.channel:
            return await ctx.send("the messages must be from the same channel")

        lines = []
        msgs = []
        msg_data = []

        async for msg in m1.channel.history(
            limit=None,
            before=m2.created_at + timedelta(seconds=1),
            after=m1.created_at - timedelta(seconds=1),
            oldest_first=True,
        ):
            if msg.author.bot:
                continue

            lines.append(f"{msg.author} ({msg.author.id}): {msg.content}")
            msgs.append(msg)
            msg_data.append(
                {
                    "author": {
                        "id": msg.author.id,
                        "username": msg.author.name,
                        "display_name": msg.author.display_name,
                        "avatar_url": msg.author.display_avatar.with_format("png").url,
                    },
                    "content": msg.content,
                    "timestamp": msg.created_at.timestamp(),
                }
            )

        if len(msgs) == 0:
            return await ctx.send("No messages to save")

        txtbuf = StringIO()
        txtbuf.write("\n".join(lines))
        txtbuf.seek(0)

        jsonbuf = StringIO()
        jsonbuf.write(json.dumps(msg_data))
        jsonbuf.seek(0)

        mod_channel = self.bot.get_var_channel("mod")
        file_msg = await mod_channel.send(
            f"Saved chat files from around [here]({msgs[0].jump_url}):\n-# Please do not delete this message",
            files=[
                discord.File(fp=txtbuf, filename="saved-chat.txt"),
                discord.File(fp=jsonbuf, filename="saved-chat.json"),
            ],
        )
        await mod_channel.send(
            f"To view them in browser, click [here](https://hudsonshi.com/lunabot/saved-chat/?channelId={file_msg.channel.id}&messageId={file_msg.id})"
        )

        bot_msg = await ctx.send(
            "Files saved in mod channel. Type `purge` in the next minute to purge."
        )

        try:
            await self.bot.wait_for(
                "message",
                check=lambda m: (
                    m.channel == ctx.channel
                    and m.author == ctx.author
                    and m.content.lower() == "purge"
                ),
                timeout=60,
            )
        except asyncio.TimeoutError:
            await bot_msg.delete()
            return

        chunks = [msgs[i : i + 100] for i in range(0, len(msgs), 100)]
        for chunk in chunks:
            try:
                await m1.channel.delete_messages(chunk)
            except (discord.HTTPException, discord.Forbidden):
                pass

        await ctx.send("Finished purging!")

    @commands.command()
    @is_art_manager()
    async def vip(self, ctx, *, member: discord.Member):
        VIP_ROLE_ID = 1192676146911916092
        await member.add_roles(discord.Object(VIP_ROLE_ID))
        layout = self.bot.get_layout(".vip")
        await layout.send(ctx, LayoutContext(author=member))
        await ctx.message.delete()

    @commands.command()
    @is_art_manager()
    async def buyer(self, ctx, *, member: discord.Member):
        BUYER_ROLE_ID = 1197373980416430090
        await member.add_roles(discord.Object(BUYER_ROLE_ID))
        layout = self.bot.get_layout(".buyer")
        await layout.send(ctx, LayoutContext(author=member))
        await ctx.message.delete()

    @commands.command()
    @is_art_manager()
    async def seller(self, ctx, *, member: discord.Member):
        SELLER_ROLE_ID = 1197374014025371808
        await member.add_roles(discord.Object(SELLER_ROLE_ID))
        layout = self.bot.get_layout(".seller")
        await layout.send(ctx, LayoutContext(author=member))
        await ctx.message.delete()

    @commands.command()
    async def dni(
        self,
        ctx,
        role: Optional[discord.Role],
        name: str,
        hex1: str,
        hex2: str | None = None,
    ):
        v1 = None
        v2 = None
        try:
            v1 = int(hex1.lstrip("#"), base=16)
            if hex2 is not None:
                v2 = int(hex2.lstrip("#"), base=16)
        except ValueError:
            return await ctx.send("Invalid hex code.")

        if not 0 <= v1 <= 0xFFFFFF:
            return await ctx.send("Invalid hex code.")

        if v2 is not None and not 0 <= v2 <= 0xFFFFFF:
            return await ctx.send("Invalid hex code.")

        if role is None:
            role = ctx.guild.get_role(1434398478003605514)

        if role is None:
            return await ctx.send("no role")

        if v2 is None:
            await role.edit(name=name, colour=discord.Colour(v1))
        else:
            await role.edit(
                name=name,
                colour=discord.Colour(v1),
                secondary_colour=discord.Colour(v2),
            )

        embed = discord.Embed(
            description=f"dni {role.mention}",
            color=self.bot.DEFAULT_EMBED_COLOR,
        )
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(Staff(bot))
