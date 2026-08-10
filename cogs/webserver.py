import ast
import asyncio
import hmac
import inspect
import io
import json
import sys
import traceback
from typing import TYPE_CHECKING

import aiohttp_cors
import discord
from aiohttp import web
from cogs.utils.helpers import reload_module
from config import JSK_KEY
from discord.ext.duck import webserver

if TYPE_CHECKING:
    from bot import LunaBot

EXEC_CORO_CODE = """
async def _repl_coroutine(_bot):
    import asyncio
    import aiohttp
    import discord
    from discord.ext import commands
    bot = _bot
    try:
        pass
    finally:
        pass
"""


def _wrap_code(code: str) -> ast.Module:
    user_code = ast.parse(code, mode='exec')
    mod = ast.parse(EXEC_CORO_CODE, mode='exec')

    definition = mod.body[-1]
    assert isinstance(definition, ast.AsyncFunctionDef)

    try_block = definition.body[-1]
    assert isinstance(try_block, ast.Try)

    try_block.body.extend(user_code.body)
    ast.fix_missing_locations(mod)

    last_expr = try_block.body[-1]
    if isinstance(last_expr, ast.Expr) and not isinstance(last_expr.value, ast.Yield):
        yield_stmt = ast.Yield(last_expr.value)
        ast.copy_location(yield_stmt, last_expr)
        yield_expr = ast.Expr(yield_stmt)
        ast.copy_location(yield_expr, last_expr)
        try_block.body[-1] = yield_expr

    return mod


class Webserver(webserver.WebserverCog, port=8080):
    """aiohttp web server exposing remote code execution and shell endpoints."""

    def __init__(self, bot: "LunaBot"):
        self.bot: "LunaBot" = bot
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

    @webserver.route("post", "/api/exec")
    async def exec_code(self, request: web.Request):
        token = request.headers.get("Authorization", "")
        if not hmac.compare_digest(token, JSK_KEY):
            return web.json_response({"error": "unauthorized"}, status=401)

        try:
            body = await request.json()
            code = body.get("code", "")
        except Exception:
            return web.json_response({"error": "invalid json body"}, status=400)

        if not code.strip():
            return web.json_response({"error": "no code provided"}, status=400)

        stdout_capture = io.StringIO()
        results = []

        old_stdout = sys.stdout
        sys.stdout = stdout_capture
        try:
            mod = _wrap_code(code)
            compiled = compile(mod, '<exec>', 'exec')

            scope: dict = {}
            exec(compiled, scope)

            func = scope['_repl_coroutine']

            if inspect.isasyncgenfunction(func):
                async for result in func(self.bot):
                    if result is not None:
                        results.append(repr(result))
            else:
                result = await func(self.bot)
                if result is not None:
                    results.append(repr(result))
        except Exception:
            return web.json_response({
                "error": traceback.format_exc(),
                "stdout": stdout_capture.getvalue(),
            }, status=200)
        finally:
            sys.stdout = old_stdout

        return web.json_response({
            "results": results,
            "stdout": stdout_capture.getvalue(),
        })

    @webserver.route("post", "/api/reload")
    async def reload_modules(self, request: web.Request):
        token = request.headers.get("Authorization", "")
        if not hmac.compare_digest(token, JSK_KEY):
            return web.json_response({"error": "unauthorized"}, status=401)

        try:
            body = await request.json()
            modules = body.get("modules", [])
            cogs = body.get("cogs", [])
        except Exception:
            return web.json_response({"error": "invalid json body"}, status=400)

        info = []
        for mname in modules:
            info.extend(reload_module(mname))

        for cog in cogs:
            ext = "cogs." + cog
            try:
                await self.bot.reload_extension(ext)
                info.append(f"Reloaded extension `{ext}`")
            except Exception as e:
                info.append(f"Error reloading extension `{ext}`: {e}")

        return web.json_response({"info": info})

    @webserver.route("post", "/api/sh")
    async def exec_shell(self, request: web.Request):
        token = request.headers.get("Authorization", "")
        if not hmac.compare_digest(token, JSK_KEY):
            return web.json_response({"error": "unauthorized"}, status=401)

        try:
            body = await request.json()
            command = body.get("command", "")
        except Exception:
            return web.json_response({"error": "invalid json body"}, status=400)

        if not command.strip():
            return web.json_response({"error": "no command provided"}, status=400)

        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)
        except asyncio.TimeoutError:
            proc.kill()
            return web.json_response({
                "error": "command timed out after 30 seconds",
            }, status=200)

        return web.json_response({
            "return_code": proc.returncode,
            "stdout": stdout.decode(errors="replace"),
            "stderr": stderr.decode(errors="replace"),
        })

    @webserver.route("get", "/api/saved-chat/{channel_id}/{message_id}")
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
