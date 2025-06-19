import zoneinfo
from datetime import datetime
from zoneinfo import ZoneInfo

import discord
from discord import app_commands
from discord.ext import commands
from fuzzywuzzy import process
from lxml import etree


class TimezoneCog(commands.Cog):
    DEFAULT_POPULAR_TIMEZONE_IDS = (
        "usnyc",
        "uslax",
        "uschi",
        "usden",
        "inccu",
        "trist",
        "rumow",
        "gblon",
        "frpar",
        "esmad",
        "deber",
        "grath",
        "uaiev",
        "itrom",
        "nlams",
        "plwaw",
        "cator",
        "aubne",
        "ausyd",
        "brsao",
        "jptyo",
        "cnsha",
    )

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.valid_timezones = set(zoneinfo.available_timezones())
        self._timezone_aliases = {
            "Eastern Time": "America/New_York",
            "Central Time": "America/Chicago",
            "Mountain Time": "America/Denver",
            "Pacific Time": "America/Los_Angeles",
            "EST": "America/New_York",
            "CST": "America/Chicago",
            "MST": "America/Denver",
            "PST": "America/Los_Angeles",
            "EDT": "America/New_York",
            "CDT": "America/Chicago",
            "MDT": "America/Denver",
            "PDT": "America/Los_Angeles",
        }
        self._task = bot.loop.create_task(self.load_bcp47_timezones())

    async def load_bcp47_timezones(self):
        async with self.bot.session.get(
            "https://raw.githubusercontent.com/unicode-org/cldr/main/common/bcp47/timezone.xml"
        ) as resp:
            if resp.status != 200:
                return

            parser = etree.XMLParser(ns_clean=True, recover=True, encoding="utf-8")
            tree = etree.fromstring(await resp.read(), parser=parser)

            entries = {
                node.attrib["name"]: {
                    "description": node.attrib["description"],
                    "aliases": node.get("alias", "Etc/Unknown").split(" "),
                    "preferred": node.get("preferred"),
                }
                for node in tree.iter("type")
                if not node.attrib["name"].startswith(("utcw", "utce", "unk"))
                and not node.attrib["description"].startswith("POSIX")
            }

            for entry in entries.values():
                if entry["preferred"]:
                    preferred_entry = entries.get(entry["preferred"])
                    if preferred_entry:
                        self._timezone_aliases[entry["description"]] = preferred_entry[
                            "aliases"
                        ][0]
                else:
                    self._timezone_aliases[entry["description"]] = entry["aliases"][0]

    @commands.hybrid_command(
        name="set-timezone", aliases=["settimezone", "settz", "set-tz"]
    )
    @app_commands.describe(timezone="the timezone name or abbreviation")
    async def set_timezone(self, ctx, *, timezone: str):
        """Sets the timezone for the user."""
        user_input = timezone
        all_timezones = list(self._timezone_aliases.keys()) + list(self.valid_timezones)
        match, score = process.extractOne(user_input, all_timezones)

        if score < 80:
            suggestions = process.extract(user_input, all_timezones, limit=5)
            suggestion_text = "\n".join(f"- `{s[0]}`" for s in suggestions)
            await ctx.send(
                f"Could not find an exact match for `{user_input}`. Did you mean one of these?\n{suggestion_text}"
            )
            return

        selected_timezone = self._timezone_aliases.get(match, match)

        try:
            ZoneInfo(selected_timezone)
        except Exception:
            await ctx.send(f"Error: `{selected_timezone}` is not a valid timezone.")
            return

        query = """INSERT INTO
                       timezones (user_id, timezone)
                   VALUES
                       ($1, $2)
                   ON CONFLICT (user_id) DO
                   UPDATE
                   SET
                       timezone = $2
                """
        await self.bot.db.execute(query, ctx.author.id, selected_timezone)

        await ctx.send(
            f"Timezone successfully set to `{match}` (**{selected_timezone}**)!"
        )

    @commands.hybrid_command(
        name="get-timezone", aliases=["gettimezone", "gettz", "get-tz"]
    )
    @app_commands.describe(member="the member to get the timezone of")
    async def get_timezone(self, ctx, *, member: discord.Member = None):
        """Retrieves the user's timezone."""
        if member is None:
            member = ctx.author
            other = False
        else:
            other = True

        query = """SELECT timezone
                   FROM timezones
                   WHERE user_id = $1
                """
        tz = await self.bot.db.fetchval(query, member.id)
        if tz is None:
            if other:
                await ctx.send(f"{member.display_name} has not set their timezone.")
            else:
                await ctx.send("Use `/set-timezone` to set your timezone first!")
            return

        current_time = datetime.now(ZoneInfo(tz)).strftime("%c")
        if other:
            await ctx.send(
                f"{member.display_name}'s timezone is set to `{tz}`.\nIt is {current_time}."
            )
        else:
            await ctx.send(f"Your timezone is set to `{tz}`.\nIt is {current_time}.")


async def setup(bot):
    await bot.add_cog(TimezoneCog(bot))
