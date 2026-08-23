import json
import logging
from datetime import datetime, timedelta
from pkgutil import iter_modules
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

import aiohttp
import discord
from discord import Member, TextChannel, Thread
from discord.abc import GuildChannel, PrivateChannel
from discord.ext import commands
from discord.ext.duck.errors import ErrorManager
from parsedatetime import Calendar
from prettytable import TableStyle

from cogs.summer_event.constants import START_TIME
from cogs.db import init_db
from cogs.future_tasks import FutureTask
from cogs.utils import InvalidURL, Layout, TablePages, View
from cogs.utils.checks import guild_only
from config import DEFAULT_TIMEZONE, ERROR_WEBHOOK_URL, LOG_FILE

if TYPE_CHECKING:
    from cogs.tickets import Ticket

# fallback codeblock width for users who haven't calibrated a device yet
DEFAULT_DISPLAY_WIDTH = 60


class LunaBot(commands.Bot):
    def __init__(self, *args, **kwargs):
        super().__init__(
            "!",
            *args,
            intents=discord.Intents.all(),
            status=discord.Status.idle,
            **kwargs,
        )
        self.DEFAULT_EMBED_COLOR = 0xCAB7FF
        self.GUILD_ID = 899108709450543115
        self.STORCH_ID = 718475543061987329
        self.NAOMI_ID = 785037540155195424

        self.owner_id = None
        self.owner_ids = [self.STORCH_ID, self.NAOMI_ID]

        self.log_flags: list[str] = []
        self.views: set[View] = set()
        self.session = aiohttp.ClientSession()
        self.pdt = Calendar()

        self.embeds: dict[str, discord.Embed] = {}
        self.future_tasks: dict[int, FutureTask] = {}
        self.layouts: dict[str, Layout] = {}
        self.perk_rewards: dict[str, int] = {}
        self.tickets: dict[discord.Thread, Ticket] = {}
        self.tz_cache: dict[discord.User, str] = {}
        self.vars: dict[str, str | int] = {}
        self.width_cache: dict[int, int] = {}

        self.errors = ErrorManager(
            self,
            webhook_url=ERROR_WEBHOOK_URL,
            session=self.session,
            hijack_bot_on_error=True,
        )

    async def load_activity_event(self):
        from cogs.activity_event import (
            TEAM_MISTLETOE_CHANNEL_ID,
            TEAM_POINSETTIA_CHANNEL_ID,
        )

        ch = self.get_var_channel("private")

        assert isinstance(ch, discord.TextChannel)

        await ch.send("Sleeping until activity event starts")
        await discord.utils.sleep_until(START_TIME)
        await self.load_extension("cogs.activity_event")
        await ch.send("Loaded activity event")

        ch1 = self.get_channel(TEAM_POINSETTIA_CHANNEL_ID)
        ch2 = self.get_channel(TEAM_MISTLETOE_CHANNEL_ID)
        layout = self.get_layout("ae/live")

        await layout.send(ch1)
        await layout.send(ch2)

    async def load_summer_event(self):
        from cogs.summer_event import (
            TEAM_JELLYFISH_CHANNEL_ID,
            TEAM_STARFISH_CHANNEL_ID,
        )

        ch = self.get_var_channel("private")

        assert isinstance(ch, discord.TextChannel)

        await ch.send("Sleeping until summer event starts")
        await discord.utils.sleep_until(START_TIME)
        await self.load_extension("cogs.summer_event")
        await ch.send("Loaded summer activity event")

        ch1 = self.get_channel(TEAM_JELLYFISH_CHANNEL_ID)
        ch2 = self.get_channel(TEAM_STARFISH_CHANNEL_ID)
        layout = self.get_layout("se/live")

        await layout.send(ch1)
        await layout.send(ch2)

    async def start_task(self):
        await self.wait_until_ready()
        self.loop.create_task(self._start_task())

    async def _start_task(self):
        # await self.load_extension('cogs.db')
        # await self.load_extension('db_migration')
        # return
        self.log("--- START TASK CALLED ---")
        self.add_check(guild_only)

        # connect to db
        self.db = await init_db()

        await self.load_extension("jishaku")
        priority = ["cogs.vars", "cogs.tools", "cogs.embeds", "cogs.layouts"]
        not_cogs = ["cogs.utils", "cogs.db", "cogs.activity_event", "cogs.summer_event"]

        for cog in priority:
            await self.load_extension(cog)
            logging.info(f"Loaded cog {cog}")

        for cog in [m.name for m in iter_modules(["cogs"], prefix="cogs.")]:
            if cog in priority:
                continue
            if cog in not_cogs:
                continue
            await self.load_extension(cog)
            logging.info(f"Loaded cog {cog}")

        log_flags = self.vars.get("log-flags")
        assert isinstance(log_flags, str)
        if log_flags is not None:
            self.log_flags = json.loads(log_flags)

        # if discord.utils.utcnow() < START_TIME:
        #     self.loop.create_task(self.load_summer_event())
        # else:
        #     await self.load_extension("cogs.summer_event")

        logging.info("LunaBot is ready")

    async def close(self):
        for view in list(self.views):
            try:
                await view.on_timeout()
            except Exception as e:
                logging.info(f"Couldnt stop view: {e}")
        await self.session.close()
        await super().close()

    def get_embed(self, name: str) -> discord.Embed:
        if name not in self.embeds:
            return discord.Embed(
                title=f'Embed "{name}" not found', color=self.DEFAULT_EMBED_COLOR
            )

        return self.embeds[name].copy()

    def get_layout(self, name: str) -> Layout:
        if name not in self.layouts:
            return Layout(self, name, f'`Layout "{name}" not found`', [])
        return self.layouts[name]

    def get_layout_from_json(self, data: str | dict) -> Layout:
        if isinstance(data, str):
            d: dict = json.loads(data)
        else:
            d = data
        if d["name"] is not None:
            return self.get_layout(d["name"])

        return Layout(self, None, d["content"], d["embeds"])

    async def fetch_message_from_url(self, url: str) -> discord.Message:
        tokens = url.split("/")
        try:
            channel_id = int(tokens[-2])
            message_id = int(tokens[-1])
        except (IndexError, ValueError):
            raise InvalidURL()

        channel = self.get_channel(channel_id)
        if channel is None or not isinstance(channel, discord.TextChannel):
            raise InvalidURL()

        try:
            return await channel.fetch_message(message_id)
        except discord.NotFound:
            raise InvalidURL()

    async def schedule_future_task(self, action: str, time: datetime, **kwargs):
        query = """INSERT INTO
                       future_tasks (action, time, data)
                   VALUES
                       ($1, $2, $3)
                   RETURNING
                       id
                """
        task_id = await self.db.fetchval(
            query, action, time, json.dumps(kwargs, indent=4)
        )
        task = FutureTask(self, task_id, action, time, **kwargs)
        self.future_tasks[task_id] = task
        task.start()

    async def get_cooldown_end(
        self,
        action: str,
        duration: float,
        *,
        rate: int = 1,
        obj: Member | TextChannel | None = None,
        update: bool = True,
    ) -> datetime | None:
        if isinstance(obj, Member):
            bucket = "user"
        elif isinstance(obj, TextChannel):
            bucket = "channel"
        else:
            bucket = "global"

        if obj:
            obj_id = obj.id
        else:
            obj_id = None

        # query = 'UPDATE cooldowns SET count = count + 1 WHERE action = $1 AND object_id = $2 AND bucket = $3 AND end_time > NOW() RETURNING end_time'
        # row = await self.db.fetchrow(query, action, obj_id, bucket)
        # if row is not None:
        #     return row['end_time']

        query = "SELECT count, end_time FROM cooldowns WHERE action = $1 AND object_id = $2 AND bucket = $3"
        row = await self.db.fetchrow(query, action, obj_id, bucket)
        time_ok = True
        count_ok = True

        if row is not None:
            time_ok = row["end_time"] < discord.utils.utcnow()
            count_ok = row["count"] < rate

            if not time_ok and not count_ok:
                return row["end_time"]

            if not time_ok:
                query = "UPDATE cooldowns SET count = count + 1 WHERE action = $1 AND object_id = $2"
                await self.db.execute(query, action, obj_id)

        if update and time_ok:
            query = """INSERT INTO cooldowns (action, object_id, bucket, end_time, count) 
                       VALUES ($1, $2, $3, $4, 1) 
                       ON CONFLICT (action, object_id)
                       DO UPDATE SET end_time = $4, count = 1 
                    """
            end_time = discord.utils.utcnow() + timedelta(seconds=duration)
            await self.db.execute(query, action, obj_id, bucket, end_time)

        return None

    async def reset_cooldown(
        self,
        action: str,
        *,
        obj: Member | TextChannel | None = None,
    ) -> None:
        if isinstance(obj, Member):
            bucket = "user"
        elif isinstance(obj, TextChannel):
            bucket = "channel"
        else:
            bucket = "global"

        obj_id = obj.id if obj else None

        query = "DELETE FROM cooldowns WHERE action = $1 AND object_id = $2 AND bucket = $3"
        await self.db.execute(query, action, obj_id, bucket)

    def get_var_channel(
        self, name: str
    ) -> GuildChannel | Thread | PrivateChannel | TextChannel | None:
        name = name + "-channel-id"
        if name not in self.vars:
            return None

        return self.get_channel(int(self.vars[name]))

    async def get_count(self, name: str, *, update=True):
        if update:
            query = """INSERT INTO
                           counters (name, COUNT)
                       VALUES
                           ($1, 1)
                       ON CONFLICT (name) DO
                       UPDATE
                       SET
                           COUNT = counters.count + 1
                       RETURNING
                           COUNT
                    """
            return await self.db.fetchval(query, name)
        else:
            query = """INSERT INTO
                           counters (name, COUNT)
                       VALUES
                           ($1, 0)
                       ON CONFLICT (name) DO NOTHING
                       RETURNING
                           COUNT
                    """
            return await self.db.fetchval(query, name)

    async def send_table(
        self,
        ctx,
        rows: list,
        *,
        field_names: list[str],
        style: TableStyle = TableStyle.SINGLE_BORDER,
    ) -> None:
        """Sends `rows` as a paginated, codeblock-formatted PrettyTable sized
        to the invoking user's calibrated device width (see cogs/display.py).
        Each page packs as many rows as fit under Discord's 2000-char limit."""
        max_width = await ctx.fetch_display_width()
        pages = TablePages(
            rows,
            ctx=ctx,
            field_names=field_names,
            max_width=max_width,
            style=style,
        )
        await pages.start()

    async def dm_owner(self, message: str):
        assert self.owner_id is not None
        owner = self.get_user(self.owner_id)
        assert owner is not None
        await owner.send(message)

    def log(self, message: str, flag: str | None = None):
        if flag and flag not in self.log_flags:
            return

        with open(LOG_FILE, "a") as f:
            parts = []

            now = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")
            parts.append(f"[{now}]")

            if flag:
                parts.append(f"[{flag}]")

            parts.append(message)

            f.write(" ".join(parts) + "\n")

    async def on_message(self, message):
        ctx = await self.get_context(message, cls=LunaCtx)
        await self.invoke(ctx)


class LunaCtx(commands.Context):
    # def __init__(self, *args, **kwargs):
    #     super().__init__(*args, **kwargs)

    async def fetch_timezone(self) -> str:
        if self.author in self.bot.tz_cache:
            return self.bot.tz_cache[self.author]

        query = "SELECT timezone FROM timezones WHERE user_id = $1"
        tz = await self.bot.db.fetchval(query, self.author.id)
        if tz is None:
            tz = DEFAULT_TIMEZONE

        self.bot.tz_cache[self.author] = tz
        return tz

    async def parse_dt(self, dt_str: str) -> datetime | None:
        tz = ZoneInfo(await self.fetch_timezone())
        dt, status = self.bot.pdt.parseDT(
            dt_str, sourceTime=datetime.now(tz), tzinfo=tz
        )
        if status == 0:
            return None

        return dt

    async def fetch_display_width(self) -> int:
        """Max codeblock line width (in characters) that fits on the author's
        calibrated device without horizontal scrolling."""
        if self.author.id in self.bot.width_cache:
            return self.bot.width_cache[self.author.id]

        query = "SELECT char_width FROM user_devices WHERE user_id = $1 AND is_active = TRUE"
        width = await self.bot.db.fetchval(query, self.author.id)
        if width is None:
            width = DEFAULT_DISPLAY_WIDTH

        self.bot.width_cache[self.author.id] = width
        return width


class AdminCog(commands.Cog):
    async def cog_check(self, ctx):
        assert ctx.bot.owner_ids is not None
        if isinstance(ctx.author, discord.User):
            return False

        return (
            ctx.author.guild_permissions.administrator
            or ctx.author.id in ctx.bot.owner_ids
        )
