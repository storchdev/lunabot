import asyncio
from io import StringIO
from typing import TYPE_CHECKING

import discord
from discord.ext import commands

from cogs.utils import InvalidURL

if TYPE_CHECKING:
    from bot import LunaBot

import time
from typing import Optional

# from fuzzywuzzy import process
# Custom rust module
from fuzzy_rust import extract_bests


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
        async for msg in m1.channel.history(
            limit=None, before=m2.created_at, after=m1.created_at, oldest_first=True
        ):
            if msg.author.bot:
                continue
            lines.append(f"{msg.author} ({msg.author.id}): {msg.content}")
            msgs.append(msg)

        buf = StringIO()
        buf.write("\n".join(lines) + "\n")
        buf.seek(0)

        bot_msg = await ctx.send(
            "Here's the file. Purge?",
            file=discord.File(fp=buf, filename="savedchat.txt"),
        )
        try:
            await self.bot.wait_for(
                "message",
                check=lambda m: m.channel == ctx.channel
                and m.author == ctx.author
                and m.content.lower() in ["y", "yes"],
                timeout=60,
            )
        except asyncio.TimeoutError:
            await bot_msg.edit(content="")
            return

        chunks = [msgs[i : i + 100] for i in range(0, len(msgs), 100)]
        purged = 0
        for chunk in chunks:
            try:
                purged += len(await m1.channel.delete_messages(chunk))
            except discord.Forbidden:
                pass

        await ctx.send(f"Purged {purged} messages from {m1.channel.mention}")


async def setup(bot):
    await bot.add_cog(Staff(bot))
