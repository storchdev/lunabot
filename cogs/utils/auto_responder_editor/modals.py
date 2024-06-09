import discord 
from discord import ui 
from discord.ext import commands 
from ..auto_responders import AutoResponderAction
from cogs import utils
from ..errors import InvalidModalField
from typing import TYPE_CHECKING, Union
if TYPE_CHECKING:
    from .editor import AutoResponderEditor, SendMessageEditor


def to_boolean(argument: str) -> bool:
    lowered = argument.lower()
    if lowered in ('yes', 'y', 'true', 't', '1', 'on'):
        return True
    elif lowered in ('no', 'n', 'false', 'f', '0', 'off'):
        return False
    else:
        raise InvalidModalField(f'{argument} is not a valid true/false value!')

class BaseModal(discord.ui.Modal):
    def __init__(self, parent_view: Union['AutoResponderEditor', 'SendMessageEditor']):
        self.parent_view = parent_view
        self.update_defaults()
        super().__init__()

    def update_parent(self) -> None:
        raise NotImplementedError

    def update_defaults(self):
        return 

    async def on_error(self, interaction: discord.Interaction, error: Exception, /) -> None:
        if isinstance(error, InvalidModalField):
            self.parent_view.update_buttons()
            await interaction.response.edit_message(embed=self.parent_view.embed, view=self.parent_view)
            await interaction.followup.send(str(error), ephemeral=True)
            return
        await super().on_error(interaction, error)

    async def on_submit(self, interaction: discord.Interaction, /) -> None:
        self.update_parent()
        self.parent_view.update()

        kwargs = {}
        if self.parent_view.type == 'SendMessageEditor':
            kwargs = {
                'content': self.parent_view.layout.content,
                'embeds': self.parent_view.layout.embeds,
            }

        await interaction.response.edit_message(view=self.parent_view, **kwargs)


class TriggerModal(BaseModal, title='Enter trigger for autoresponder'):
    trigger = ui.TextInput(label='Trigger', max_length=256, required=True)

    def __init__(self, parent_view, trigger, **kwargs):
        super().__init__(**kwargs)
        self.trigger.default = trigger
        self.parent_view = parent_view
    
    def update_defaults(self):
        self.trigger.default = self.parent_view.trigger

    def update_parent(self) -> None:
        self.parent_view.trigger = self.trigger.value

class CreateLayoutModal(BaseModal, title='Enter Message Fields'):
    content = ui.TextInput(label='Text', required=False, style=discord.TextStyle.long)
    embed_names = ui.TextInput(label='Embed names (one per line)', required=False, style=discord.TextStyle.long)

    def __init__(self, parent_view: 'SendMessageEditor'):
        super().__init__()
        self.parent_view = parent_view

    def update_defaults(self):
        self.content.default = self.parent_view.layout.content
        self.embed_names.default = '\n'.join(self.parent_view.layout.embed_names)

    def update_parent(self):
        if self.content.value is None and self.embed_names.value is None:
            raise InvalidModalField('You must enter text or an embed name!')
        names = []
        if self.embed_names.value is not None:
            for name in self.embed_names.value.split('\n'):
                name = name.lower()
                if name not in self.parent_view.bot.embeds:
                    raise InvalidModalField(f'Embed {name} does not exist!')
                names.append(name)
        self.parent_view.layout.content = self.content.value
        self.parent_view.layout.embed_names = names

class ChooseLayoutModal(BaseModal, title='Enter Layout'):
    layout_name = ui.TextInput(label='Layout name', required=True)

    def __init__(self, parent_view: 'SendMessageEditor'):
        super().__init__(parent_view)
        self.parent_view = parent_view 

    async def update_parent(self):
        name = self.layout_name.value.lower()
        if name not in self.parent_view.bot.layouts:
            raise InvalidModalField(f'Layout {name} does not exist!')
        
        self.parent_view.layout = self.parent_view.bot.layouts[name]

class DeleteAfterModal(BaseModal, title='Enter Delete After'):
    delete_after = ui.TextInput(label='Delete after (in seconds, nothing = don\'t delete)', required=False)

    def __init__(self, parent_view: 'SendMessageEditor'):
        super().__init__(parent_view)
        self.parent_view = parent_view

    def update_defaults(self):
        self.delete_after.default = str(self.parent_view.delete_after)

    def update_parent(self):
        try:
            self.parent_view.delete_after = int(self.delete_after.value)
        except ValueError:
            raise InvalidModalField('Delete after must be a number!')
        
        
class RemoveActionModal(BaseModal, title='Remove Action'):
    index = ui.TextInput(label='Index of action to remove', required=True)

    def __init__(self, parent_view: 'AutoResponderEditor'):
        super().__init__(parent_view)
        self.parent_view = parent_view

    async def update_parent(self):
        try:
            index = int(self.index.value)
        except ValueError:
            raise InvalidModalField('Index must be a number!') 

        index -= 1 
        if not (0 <= index < len(self.parent_view.actions)):
            raise InvalidModalField(f'Index must be between 1 and {len(self.parent_view.actions)}!')

        self.parent_view.actions.pop(index)
    
class SleepModal(BaseModal, title='Enter Sleep Duration'):
    duration = ui.TextInput(label='Duration (in seconds)', required=True)

    def __init__(self, parent_view: 'AutoResponderEditor'):
        super().__init__(parent_view)
        self.parent_view = parent_view

    def update_parent(self):
        try:
            duration = float(self.duration.value)
        except ValueError:
            raise InvalidModalField('Duration must be a number!')

        self.parent_view.actions.append(AutoResponderAction('sleep', duration=duration))


class CooldownModal(BaseModal, title='Edit Cooldown'):
    bucket = ui.TextInput(label='Bucket (g=global, c=channel, u=user)', default='g', required=True)
    per = ui.TextInput(label='Duration of cooldown', required=True)
    rate = ui.TextInput(label='Number of uses per duration', default='1', required=True)

    def __init__(self, parent_view: 'AutoResponderEditor'):
        super().__init__(parent_view)
        self.parent_view = parent_view

    def update_defaults(self):
        if self.parent_view.cooldown is None:
            return

        if self.parent_view.cooldown.bucket == commands.BucketType.default.value:
            self.bucket.default = 'g'
        elif self.parent_view.cooldown.bucket == commands.BucketType.channel.value:
            self.bucket.default = 'c'
        elif self.parent_view.cooldown.bucket == commands.BucketType.user.value:
            self.bucket.default = 'u'
        
        self.per.default = str(self.parent_view.cooldown.per)
        self.rate.default = str(self.parent_view.cooldown.rate)

    def update_parent(self): 
        
        try:
            per = int(self.per.value)
        except ValueError:
            raise InvalidModalField('Duration must be a number!')
        
        try:
            rate = int(self.rate.value)
        except ValueError:
            raise InvalidModalField('Rate must be a number!')

        v = self.bucket.value.lower()  
        if v == 'g':
            bucket = 'global'
        elif v == 'c':
            bucket = 'channel'
        elif v == 'u':
            bucket = 'user'
        else:
            raise InvalidModalField('Bucket must be g, c, or u!')

        self.parent_view.cooldown = utils.Cooldown(rate, per, bucket)
