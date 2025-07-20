import json
import os
from typing import TYPE_CHECKING

import aiohttp_cors
import discord
from aiohttp import web
from discord.ext.duck import webserver

if TYPE_CHECKING:
    from bot import LunaBot


class Webserver(webserver.WebserverCog, port=8080):
    """The description for Webserver goes here."""

    def __init__(self, bot: "LunaBot"):
        self.bot = bot
        super().__init__()

        # Catch-all fallback to index.html
        # async def spa_handler(request):
        #     return web.FileResponse(os.path.join(DIST_DIR, "index.html"))

        # self.app.router.add_static("/", path=DIST_DIR, name="static", show_index=True)
        # self.app.router.add_get("/{tail:.*}", spa_handler)

        # Configure default CORS settings
        cors = aiohttp_cors.setup(self.app)
        cors = aiohttp_cors.setup(
            self.app,
            defaults={
                "*": aiohttp_cors.ResourceOptions(
                    allow_credentials=True, expose_headers="*", allow_headers="*"
                )
            },
        )

        # Apply CORS to all routes
        for route in list(self.app.router.routes()):
            cors.add(route)

    @webserver.route("GET", "/api/saved-chat/{channel_id}/{message_id}")
    async def get_saved_chat(self, request: web.Request):
        try:
            channel_id = int(request.match_info["channel_id"])
            message_id = int(request.match_info["message_id"])

            channel = self.bot.get_channel(channel_id)
            if channel is None:
                return web.json_response({"error": "channel not found"}, status=404)

            try:
                msg = await channel.fetch_message(message_id)
            except (discord.HTTPException, discord.Forbidden):
                return web.json_response({"error": "message not found"}, status=404)

            if (
                msg.author != self.bot.user
                or len(msg.attachments) != 2
                or msg.attachments[1].filename != "saved-chat.json"
            ):
                return web.json_response(
                    {"error": "message does not contain saved chat files"}, status=404
                )

            payload = json.loads(await msg.attachments[1].read())
            return web.json_response(payload)
        except Exception as e:
            self.bot.log(e, "webserver")


async def setup(bot):
    await bot.add_cog(Webserver(bot))
