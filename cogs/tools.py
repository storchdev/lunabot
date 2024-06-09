from discord.ext import commands 
import csv 
import asyncio
import json 
from io import StringIO
from discord import ui 
from discord.utils import escape_markdown
from .utils import EmbedEditor
import discord 
from typing import Optional, Literal
import importlib 


class Tools(commands.Cog, description='storchs tools'):
    
    def __init__(self, bot):
        self.bot = bot 
    
    async def cog_check(self, ctx):
        return ctx.author.guild_permissions.administrator or ctx.author.id == self.bot.owner_id

    async def reload_cog(self, cog, info):
        try:
            await self.bot.reload_extension('cogs.' + cog)
            info.append(f'Reloaded cog `{cog}`')
        except commands.ExtensionNotLoaded:
            await self.bot.load_extension('cogs.' + cog)
            info.append(f'Loaded cog `{cog}`')
        except Exception as e:
            info.append(f'Error when reloading cog `{cog}`')

    async def reload_module(self, mname, info):
        try:
            module = __import__('cogs.' + mname)
            importlib.reload(module)
            info.append(f'Reloaded module `{mname}`')
        except Exception as e:
            info.append(f'Error when reloading module `{module}`')

    @commands.command()
    async def sql(self, ctx, *, query):
        if query.lower().startswith('select'):
            try:
                rows = await self.bot.db.fetch(query)
            except Exception as e:
                await ctx.send(f'Error: {e}')
                return
            if not rows:
                await ctx.send('No results.')
                return
            buf = StringIO()
            writer = csv.writer(buf)
            writer.writerow(rows[0].keys())
            for row in rows:
                row = dict(row)
                writer.writerow(row.values())
            buf.seek(0)
            await ctx.send(file=discord.File(buf, filename='query.csv'))
        else:
            try:
                await self.bot.db.execute(query)
            except Exception as e:
                await ctx.send(f'Error: {e}')
                return

            await ctx.send('Done!')

    @commands.command()
    async def buildembed(self, ctx):
        view = EmbedEditor(self.bot, ctx.author, timeout=None)
        await ctx.send('Please hit the **Submit** button when you\'re ready!', view=view)
        await view.wait()
        if view.ready:
            await ctx.send(embed=view.current_embed)
        
    @commands.command()
    async def r(self, ctx):
        with open('cogs/settings.json') as f:
            settings = json.load(f)
        modules = settings['active_modules']
        cogs = settings['active_cogs']
        info = []
        for mname in modules:
            await self.reload_module(mname, info)
        for cog in cogs:
            await self.reload_cog(cog, info)
    
        await ctx.send('\n'.join(info))

    @commands.command()
    async def rc(self, ctx, *cogs):
        info = []
        for cog in cogs:
            await self.reload_cog(cog, info)
        await ctx.send('\n'.join(info))
    
    @commands.command()
    async def rm(self, ctx, *modules):
        info = []
        for mname in modules:
            await self.reload_module(mname, info)
        await ctx.send('\n'.join(info))


    @commands.command()
    async def grabembed(self, ctx, url):
        tokens = url.split('/')
        channel_id = int(tokens[5])
        message_id = int(tokens[6])
        channel = self.bot.get_channel(channel_id)
        message = await channel.fetch_message(message_id)
        embed = message.embeds[0].to_dict()

        # if 'footer' in embed:
            # embed.pop('footer')
            
        data = json.dumps(embed, indent=4)
        await ctx.send(f'```json\n{data}```')

    @commands.command()
    async def grabbuttonemoji(self, ctx, url):
        tokens = url.split('/')
        channel_id = int(tokens[5])
        message_id = int(tokens[6])
        channel = self.bot.get_channel(channel_id)
        message = await channel.fetch_message(message_id)
        view = ui.View.from_message(message)
        await ctx.send(escape_markdown(str(view.children[0].emoji)))

    @commands.command()
    async def sync(ctx: commands.Context, guilds: commands.Greedy[discord.Object], spec: Optional[Literal["~", "*", "^"]] = None) -> None:
        if not guilds:
            if spec == "~":
                synced = await ctx.bot.tree.sync(guild=ctx.guild)
            elif spec == "*":
                ctx.bot.tree.copy_global_to(guild=ctx.guild)
                synced = await ctx.bot.tree.sync(guild=ctx.guild)
            elif spec == "^":
                ctx.bot.tree.clear_commands(guild=ctx.guild)
                await ctx.bot.tree.sync(guild=ctx.guild)
                synced = []
            else:
                synced = await ctx.bot.tree.sync()

            await ctx.send(
                f"Synced {len(synced)} commands {'globally' if spec is None else 'to the current guild.'}"
            )
            return

        ret = 0
        for guild in guilds:
            try:
                await ctx.bot.tree.sync(guild=guild)
            except discord.HTTPException:
                pass
            else:
                ret += 1

        await ctx.send(f"Synced the tree to {ret}/{len(guilds)}.")


async def setup(bot):
    await bot.add_cog(Tools(bot))