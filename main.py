import asyncio

import discord

from bot import LunaBot
from config import TOKEN

discord.utils.setup_logging()


async def main():
    bot = LunaBot()
    async with bot:
        bot.loop.create_task(bot.start_task())
        await bot.start(TOKEN)


if __name__ == "__main__":
    asyncio.run(main())
