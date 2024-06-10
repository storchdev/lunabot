from discord.ext import commands
from discord import app_commands
import discord 
import json 
import re 
from .utils.auto_responder_editor import AutoResponderEditor
from typing import Literal, Optional, List, TYPE_CHECKING
import asyncio 
from .utils import Layout, Cooldown, SimplePages, AutoResponder, AutoResponderAction

if TYPE_CHECKING:
    from bot import LunaBot
    

class AutoResponderCog(commands.Cog, name='Autoresponders', description="Autoresponder stuff (admin only)"):
    def __init__(self, bot):
        self.bot: 'LunaBot' = bot 
        self.auto_responders = []
        self.name_lookup = {}
    
    async def cog_load(self):
        query = 'SELECT * FROM auto_responders'
        rows = await self.bot.db.fetch(query)
        for row in rows:
            auto_responder = AutoResponder.from_db_row(row)
            self.auto_responders.append(auto_responder)
            self.name_lookup[auto_responder.name] = auto_responder

    async def cog_check(self, ctx):
        return ctx.author.guild_permissions.administrator or ctx.author.id in self.bot.owner_ids 

    async def ar_check(self, msg: discord.Message) -> Optional[AutoResponder]:
        for ar in self.auto_responders:
            if ar.wl_users and msg.author.id not in ar.wl_users:
                continue 
            if ar.bl_users and msg.author.id in ar.bl_users:
                continue 

            roleids = [r.id for r in msg.author.roles]
            if ar.wl_roles and all(role not in roleids for role in ar.wl_roles):
                continue 
            if ar.bl_roles and any(role in roleids for role in ar.bl_roles):
                continue 
            if ar.wl_channels and msg.channel.id not in ar.wl_channels:
                continue 
            if ar.bl_channels and msg.channel.id in ar.bl_channels:
                continue 
                
            if ar.cooldown:
                bucket = ar.cooldown.get_bucket(msg)
                retry_after = bucket.get_retry_after()
                if retry_after:
                    continue

            content = msg.content.lower()

            if ar.detection == 'starts':
                if not content.startswith(ar.trigger):
                    continue
            elif ar.detection == 'contains':
                if ar.trigger not in content:
                    continue 
            elif ar.detection == 'matches':
                if ar.trigger != content:
                    continue 
            elif ar.detection == 'contains_word':
                if ar.trigger not in content.split():
                    continue 
            elif ar.detection == 'regex':
                match = re.search(ar.trigger, msg.content, re.IGNORECASE)
                if not match: 
                    continue 
            
            return ar 
        
        return None

    @commands.Cog.listener()
    async def on_message(self, msg):
        if msg.author.bot: 
            return 
        
        if not msg.guild:
            return 

        ar = await self.ar_check(msg)
        if ar:
            for action in ar.actions:
                await action.execute(msg)


    @commands.hybrid_group(name='autoresponder', aliases=['ar'], invoke_without_command=True)
    @app_commands.default_permissions()
    async def autoresponder(self, ctx):
        embed = discord.Embed(title='Autoresponder commands', color=self.bot.DEFAULT_EMBED_COLOR)
        for cmd in ctx.command.commands:
            embed.add_field(name=cmd.name, value=cmd.help, inline=False)
        await ctx.send(embed=embed)

    @autoresponder.command(name='add', aliases=['create'])
    @app_commands.default_permissions()
    async def add_autoresponder(self, ctx, *, name):
        """Adds an auto-responder."""
        name = name.lower()
        if name in self.name_lookup:
            return await ctx.send('Autoresponder with that name already exists.', ephemeral=True)

        editor = AutoResponderEditor(self.bot, ctx.author, default_trigger=name)
        editor.message = await ctx.send(embed=editor.embed, view=editor)
        await editor.wait()

        if editor.cancelled:
            return 

        query = '''INSERT INTO auto_responders (
                       name,
                       trigger, 
                       detection, 
                       actions,
                       restrictions, 
                       cooldown,
                       author_id
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7) 
                    ON CONFLICT (name) 
                    DO NOTHING
                '''
        await self.bot.db.execute(query, 
            name,
            editor.trigger, 
            editor.detection, 
            editor.jsonify_actions(),
            editor.jsonify_restrictions(),
            editor.jsonify_cooldown(),
            ctx.author.id
        )
        ar = AutoResponder(
            name, 
            editor.trigger, 
            editor.detection, 
            editor.actions, 
            editor.restrictions, 
            editor.cooldown
        )

        self.auto_responders.append(ar)
        self.name_lookup[name] = ar

        await editor.final_interaction.response.edit_message(
            content='Successfully made autoresponder!', 
            view=None, embeds=[]
        )
    
    @autoresponder.command(name='remove', aliases=['delete'])
    @app_commands.default_permissions()
    async def remove_autoresponder(self, ctx, *, name):
        """Removes an auto-responder."""
        name = name.lower()
        if name not in self.name_lookup:
            return await ctx.send('Autoresponder with that name does not exist.', ephemeral=True)
        
        query = 'DELETE FROM auto_responders WHERE name = $1'
        await self.bot.db.execute(query, name)
        removed = self.name_lookup.pop(name)
        self.auto_responders.remove(removed)

        await ctx.send('Successfully removed autoresponder!', ephemeral=True)

    @autoresponder.command(name='edit')
    @app_commands.default_permissions()
    async def edit_autoresponder(self, ctx, *, name):
        """Edits an auto-responder."""
        name = name.lower()
        if name not in self.name_lookup:
            return await ctx.send('Autoresponder with that name does not exist.', ephemeral=True)

        editor = AutoResponderEditor(self.bot, ctx.author, ar=self.name_lookup[name])
        editor.message = await ctx.send(embed=editor.embed, view=editor)
        await editor.wait()

        if editor.cancelled:
            return 

        query = '''UPDATE auto_responders
                     SET trigger = $2,
                            detection = $3,
                            actions = $4,
                            restrictions = $5,
                            cooldown = $6   
                    WHERE name = $1
                '''
        await self.bot.db.execute(query,
            name,
            editor.trigger, 
            editor.detection, 
            editor.jsonify_actions(),
            editor.jsonify_restrictions(),
            editor.jsonify_cooldown()
        )
        ar = AutoResponder(
            name, 
            editor.trigger, 
            editor.detection, 
            editor.actions, 
            editor.restrictions, 
            editor.cooldown
        )

        old_ar = self.name_lookup.pop(name)
        self.auto_responders.remove(old_ar)
        self.name_lookup[name] = ar
        self.auto_responders.append(ar)

        await editor.final_interaction.response.edit_message(
            content='Successfully edited autoresponder!', 
            view=None, embeds=[]
        )

    @autoresponder.command(name='list')
    @app_commands.default_permissions()
    async def _list(self, ctx):
        """Lists all auto-responders."""
        entries = list(self.name_lookup.keys())
        if len(entries) == 0:
            await ctx.send('No autoresponders found.', ephemeral=True)
            return 
        
        entries.sort()
        view = SimplePages(entries, ctx=ctx)
        await view.start()


async def setup(bot):
    await bot.add_cog(AutoResponderCog(bot))
