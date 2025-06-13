import discord 
import asyncio 
from config import TOKEN
from bot import LunaBot


discord.utils.setup_logging()

async def main():
    bot = LunaBot()
    async with bot:
        bot.loop.create_task(bot.start_task())
        await bot.start(TOKEN)

if __name__ == '__main__':
    asyncio.run(main())
