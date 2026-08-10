import hashlib
import hmac
import json
from datetime import datetime
from typing import TYPE_CHECKING

import discord
import topgg
from aiohttp import web
from discord.ext import commands

from config import TOPGG_WEBHOOK_KEY

if TYPE_CHECKING:
    from bot import LunaBot


def _verify_topgg_signature(raw_body: str, signature: str, secret: str) -> bool:
    try:
        parts = dict(part.split("=", 1) for part in signature.split(","))
        timestamp = parts["t"]
        received_sig = parts["v1"]
    except (KeyError, ValueError):
        return False

    expected = hmac.new(
        secret.encode(), f"{timestamp}.{raw_body}".encode(), hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(expected, received_sig)


class TopGG(commands.Cog):
    """Handles server votes"""

    def __init__(self, bot):
        self.bot: "LunaBot" = bot

        async def bot_vote_handler(request):
            signature = request.headers.get("x-topgg-signature", "")
            raw_body = await request.text()

            if not _verify_topgg_signature(raw_body, signature, TOPGG_WEBHOOK_KEY):
                return web.Response(status=401, text="Authorization failed")

            data = json.loads(raw_body)

            if data["type"] == "vote.create" and data["data"]["project"][
                "platform_id"
            ] == str(self.bot.GUILD_ID):
                expire_dt = datetime.fromisoformat(data["data"]["expires_at"])
                user_id = int(data["data"]["user"]["platform_id"])
                guild = self.bot.get_guild(self.bot.GUILD_ID)
                member = guild.get_member(user_id)
                if member is not None:
                    role_id = self.bot.vars.get("voter-role-id")
                    await member.add_roles(discord.Object(role_id))
                    await self.bot.schedule_future_task(
                        "remove_role",
                        expire_dt,
                        user_id=user_id,
                        role_id=role_id,
                    )
                    layout = self.bot.get_layout("newvote")
                    await layout.send(
                        self.bot.get_var_channel("voter"),
                        repls={"mention": member.mention},
                        special=False,
                    )
                    # await self.bot.get_var_channel("action-log").send(
                    #     f"{member.name} ({member.id}) voted for the server on TopGG"
                    # )
                    self.bot.log(
                        f"{member.name} ({member.id}) voted for the server on TopGG",
                        "topgg",
                    )
                else:
                    self.bot.log(
                        f"{user_id} voted for the server on TopGG but they were not in the server",
                        "topgg",
                    )
            else:
                self.bot.log(f"unrecognized data payload received: {data}", "topgg")

            return web.Response(status=200, text="OK")

        bot.topgg_webhook = topgg.WebhookManager(bot)
        bot.topgg_webhook.webserver.router.add_post(
            path="/dsl", handler=bot_vote_handler
        )

        self.task = bot.topgg_webhook.run(port=8081)
        self.bot.log("topgg webserver is up", "topgg")

    async def cog_unload(self):
        await self.bot.topgg_webhook.close()
        self.task.cancel()
        self.bot.log("topgg webserver is down", "topgg")


async def setup(bot):
    await bot.add_cog(TopGG(bot))
