import asyncio
import logging
import sys

import discord

from bot import LunaBot
from config import TOKEN

discord.utils.setup_logging(handler=logging.FileHandler("lunabot.log"))
sys.stderr = open("errors.log", "a", buffering=1)


async def main():
    bot = LunaBot()
    async with bot:
        bot.loop.create_task(bot.start_task())
        await bot.start(TOKEN)


if __name__ == "__main__":
    asyncio.run(main())
