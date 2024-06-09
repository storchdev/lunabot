import re 
import json 
from typing import Optional, List, TYPE_CHECKING
import discord 
from discord.ext import commands

if TYPE_CHECKING:
    from bot import LunaBot


class LayoutContext:
    def __init__(self, *, author=None, channel=None, guild=None, message=None):
        self.author = author
        self.channel = channel
        self.guild = guild
        self.message = message


_REPLS = {
    'membercount': lambda ctx: ctx.guild.member_count,
    'mention': lambda ctx: ctx.author.mention,
    'username': lambda ctx: ctx.author.name,
    'name': lambda ctx: ctx.author.display_name,
    'nickname': lambda ctx: ctx.author.display_name,
    'server': lambda ctx: ctx.guild.name,
    'channel': lambda ctx: ctx.channel.mention,
    'channelname': lambda ctx: ctx.channel.name,
    'channelid': lambda ctx: ctx.channel.id,
    'serverid': lambda ctx: ctx.guild.id,
    'userid': lambda ctx: ctx.author.id,
    'boosts': lambda ctx: ctx.guild.premium_subscription_count,
}

class Layout:
    bot: 'LunaBot' = None

    def __init__(self, name: Optional[str] = None, content: Optional[str] = None, embed_names: Optional[List[str]] = None):
        self.name = name
        self.content = content
        self.embed_names = embed_names if embed_names else []

    def __bool__(self):
        return self.content or self.embed_names 

    @staticmethod
    def fill_text_one(text, key, value):
        return text.replace('{' + key + '}', str(value))
    
    @staticmethod 
    def fill_embed_one(embed, key, value):
        embed = embed.copy()
        for field in embed.fields:
            field.name = Layout.fill_text_one(field.name, key, value)
            field.value = Layout.fill_text_one(field.value, key, value)
        
        if embed.title: embed.title = Layout.fill_text_one(embed.title, key, value)
        if embed.footer: embed.footer.text = Layout.fill_text_one(embed.footer.text, key, value)
        if embed.author: embed.author.name = Layout.fill_text_one(embed.author.name, key, value)
        if embed.description: embed.description = Layout.fill_text_one(embed.description, key, value)
        
        return embed

    @staticmethod 
    def fill_text(ctx, text, **kwargs):
        toreplace = re.findall(r'{(.*?)}', text)
        for match in toreplace:
            if match in _REPLS:
                text = Layout.fill_text_one(text, match, _REPLS[match](ctx))
        
        for key, value in kwargs.items():
            text = Layout.fill_text_one(text, key, value)

        return text

    @staticmethod
    def fill_embed(ctx, _embed):
        embed = _embed.copy()
        for field in embed.fields:
            field.name = Layout.fill_text(ctx, field.name)
            field.value = Layout.fill_text(ctx, field.value)

        if embed.title: embed.title = Layout.fill_text(ctx, embed.title)
        if embed.footer: embed.footer.text = Layout.fill_text(ctx, embed.footer.text)
        if embed.author: embed.author.name = Layout.fill_text(ctx, embed.author.name)
        if embed.description: embed.description = Layout.fill_text(ctx, embed.description)

        return embed

    @property 
    def embeds(self):
        embeds = []
        for name in self.embed_names:
            embeds.append(self.bot.get_embed(name))
        return embeds
    
    def to_json(self):
        return json.dumps({
            'name': self.name,
            'content': self.content,
            'embeds': self.embed_names
        }, indent=4)
    
    async def send(self, msgble, ctx=None, **kwargs) -> Optional[discord.Message]:
        send_func = msgble.send

        if isinstance(msgble, discord.Message):
            if ctx is None:
                ctx = await self.bot.get_context(msgble)
            if 'reply' in kwargs and kwargs.pop('reply'):
                send_func = msgble.reply
            else:
                send_func = msgble.channel.send
        elif isinstance(msgble, commands.Context):
            if ctx is None:
                ctx = msgble
        elif isinstance(msgble, discord.Interaction):
            if ctx is None:
                ctx = await self.bot.get_context(msgble)
            if msgble.response.is_done():
                send_func = msgble.followup.send
            else:
                send_func = msgble.response.send_message
        
        if self.content:
            content = self.fill_text(ctx, self.content)
        else:
            content = None 
        
        embeds = []
        for embed in self.embeds:
            embeds.append(self.fill_embed(ctx, embed))
        
        return await send_func(content=content, embeds=embeds, **kwargs)
        
