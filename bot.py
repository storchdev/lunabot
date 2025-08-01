import json
import logging
from datetime import datetime, timedelta
from pkgutil import iter_modules
from typing import TYPE_CHECKING, Dict, Optional, Set, Union

import aiohttp
import discord
from discord.ext import commands
from discord.ext.duck.errors import ErrorManager

from cogs.future_tasks import FutureTask
from cogs.utils import InvalidURL, Layout, View
from cogs.utils.checks import guild_only
from config import ERROR_WEBHOOK_URL, LOG_FILE

if TYPE_CHECKING:
    from asyncpg import Pool

    from cogs.tickets import Ticket


class LunaBot(commands.Bot):
    def __init__(self, *args, **kwargs):
        super().__init__(
            "!",
            *args,
            intents=discord.Intents.all(),
            status=discord.Status.idle,
            **kwargs,
        )
        self.STORCH_ID = 718475543061987329
        self.GUILD_ID = 899108709450543115
        self.owner_id = self.STORCH_ID
        self.owner_ids = [self.STORCH_ID]
        self.DEFAULT_EMBED_COLOR = 0xCAB7FF
        self.views: Set[View] = set()
        self.session = aiohttp.ClientSession()
        self.embeds: Dict[str, discord.Embed] = {}
        self.layouts: Dict[str, Layout] = {}
        self.future_tasks: Dict[int, FutureTask] = {}
        self.db: Optional[Pool] = None
        self.tickets: Dict[discord.Thread, Ticket] = {}
        self.log_flags = []
        self.errors = ErrorManager(
            self,
            webhook_url=ERROR_WEBHOOK_URL,
            session=self.session,
            hijack_bot_on_error=True,
        )

    async def start_task(self):
        await self.wait_until_ready()
        self.loop.create_task(self._start_task())

    async def _start_task(self):
        # await self.load_extension('cogs.db')
        # await self.load_extension('db_migration')
        # return
        self.log("--- START TASK CALLED ---")

        self.add_check(guild_only)
        await self.load_extension("jishaku")
        priority = ["cogs.db", "cogs.vars", "cogs.tools"]
        not_cogs = ["cogs.utils"]

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
        if log_flags is not None:
            self.log_flags = json.loads(log_flags)

        logging.info("LunaBot is ready")

    async def close(self):
        for view in self.views:
            try:
                await view.on_timeout()
            except Exception as e:
                print(f"Couldnt stop view: {e}")
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

    def get_layout_from_json(self, data: Union[str, dict]) -> Layout:
        if isinstance(data, str):
            data = json.loads(data)
        if data["name"] is not None:
            return self.get_layout(data["name"])

        return Layout(self, None, data["content"], data["embeds"])

    async def fetch_message_from_url(self, url: str) -> discord.Message:
        tokens = url.split("/")
        try:
            channel_id = int(tokens[-2])
            message_id = int(tokens[-1])
        except (IndexError, ValueError):
            raise InvalidURL()

        channel = self.get_channel(channel_id)
        if channel is None:
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
        obj: Optional[Union[discord.Member, discord.TextChannel]] = None,
        update=True,
    ) -> Optional[datetime]:
        if isinstance(obj, discord.Member):
            bucket = "user"
        elif isinstance(obj, discord.TextChannel):
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

    def get_var_channel(self, name: str) -> discord.TextChannel:
        name = name + "-channel-id"
        if name not in self.vars:
            return None
        return self.get_channel(self.vars[name])

    async def get_count(self, name, *, update=True):
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

    async def dm_owner(self, message: str):
        owner = self.get_user(self.owner_id)
        await owner.send(message)

    def log(self, message: str, flag: Optional[str] = None):
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
