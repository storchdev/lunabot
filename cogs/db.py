from typing import TYPE_CHECKING

import asyncpg

from config import DB_LOGIN

if TYPE_CHECKING:
    from bot import LunaBot


class DB:
    def __init__(self, bot):
        self.bot: "LunaBot" = bot

    async def connect(self):
        self.bot.db = await asyncpg.create_pool(
            user="lunabot",
            database="lunabot",
            password=DB_LOGIN,
            host="localhost",
            port="5432",
        )
        with open("schema.sql") as f:
            await self.bot.db.execute(f.read())


async def setup(bot):
    db = DB(bot)
    await db.connect()
