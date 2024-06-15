from typing import Optional 
import discord 
from discord.ext import commands
import discord 
import json 
from typing import Literal, Optional, List
import asyncio 
from .helpers import Cooldown
from .layouts import LayoutContext


class AutoResponderAction:
    def __init__(self, bot, action_type, **kwargs):
        self.bot = bot
        self.type = action_type
        self.kwargs = kwargs

    async def send_message(self, msg: discord.Message): 
        if self.kwargs['is_dm']:
            value = self.kwargs.get('user')
            if value is None:
                user = msg.author
            else:
                user = self.bot.get_user(value)
            if user is None:
                return await msg.channel.send(f'User `{value}` not found.')

            msgble = user
        else:
            value = self.kwargs.get('channel')
            if value is None:
                channel = msg.channel
            else:
                channel = msg.guild.get_channel(value)

            if channel is None:
                return await msg.channel.send(f'Channel `{value}` not found.')
            
            msgble = channel

        layout = self.bot.get_layout_from_json(self.kwargs['layout'])
        await layout.send(msgble, **self.kwargs)

    async def add_roles(self, msg: discord.Message):
        role_ids = self.kwargs['roles']
        status = []
        for role_id in role_ids:
            role = msg.guild.get_role(role_id)
            if role is None:
                status.append(f'Role `{role_id}` not found.')
                continue
            await msg.author.add_roles(role)

        if status:
            await msg.channel.send('\n'.join(status))

    async def remove_roles(self, msg: discord.Message):
        role_ids = self.kwargs['roles']
        status = []
        for role_id in role_ids:
            role = msg.guild.get_role(role_id)
            if role is None:
                status.append(f'Role `{role_id}` not found.')
                continue
            await msg.author.remove_roles(role)

        if status:
            await msg.channel.send('\n'.join(status))
        
    async def add_reactions(self, msg: discord.Message):
        emojis = self.kwargs['emojis']
        status = []

        for emoji in emojis:
            try:
                await msg.add_reaction(emoji)
            except discord.HTTPException:
                status.append(f'Unknown emoji: {emoji}')
        
        if status:
            await msg.channel.send('\n'.join(status))

    async def execute(self, msg: discord.Message):
        if self.type == 'send_message':
            await self.send_message(msg)
        elif self.type == 'delete_trigger_message':
            await msg.delete()
        elif self.type == 'add_roles':
            await self.add_roles(msg)
        elif self.type == 'remove_roles':
            await self.remove_roles(msg)
        elif self.type == 'add_reactions':
            await self.add_reactions(msg)
        elif self.type == 'sleep':
            await asyncio.sleep(self.kwargs['duration'])


class AutoResponder:
    def __init__(self, name, trigger: str, detection: str, actions: List[AutoResponderAction], restrictions: dict, cooldown: Optional[Cooldown] = None):
        self.name = name
        self.trigger = trigger 
        self.detection = detection 
        self.actions = actions

        self.restrictions = restrictions 
        self.wl_users = restrictions.get('whitelisted_users', [])
        self.bl_users = restrictions.get('blacklisted_users', [])
        self.wl_roles = restrictions.get('whitelisted_roles', [])
        self.bl_roles = restrictions.get('blacklisted_roles', [])
        self.wl_channels = restrictions.get('whitelisted_channels', [])
        self.bl_channels = restrictions.get('blacklisted_channels', [])

        #TODO: use db for cooldown once an api is available
        if cooldown:
            self.cooldown = commands.CooldownMapping.from_cooldown(
                cooldown.rate, cooldown.per, cooldown.type
            )
        else:
            self.cooldown = None

    @classmethod 
    def from_db_row(cls, bot, row):
        actions = []
        for action in json.loads(row['actions']):
            actions.append(AutoResponderAction(bot, action['type'], **action['kwargs'])) 

        if row['cooldown']:
            cooldown_dict = json.loads(row['cooldown'])
            cooldown = Cooldown(
                cooldown_dict['rate'], 
                cooldown_dict['per'], 
                cooldown_dict['bucket_type']
            )
        else:
            cooldown = None

        return cls(
            row['name'],
            row['trigger'],
            row['detection'],
            actions,
            json.loads(row['restrictions']),
            cooldown
        )

    def __eq__(self, other):
        return self.name == other.name