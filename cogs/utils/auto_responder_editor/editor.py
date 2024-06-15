import discord 
import json 
from discord.ext import commands 
from discord import ui, ButtonStyle, TextStyle 
from ..auto_responders import AutoResponderAction, AutoResponder 
from typing import Optional
from .modals import (
    TriggerModal,
    ChooseLayoutModal,
    CreateLayoutModal,
    DeleteAfterModal,
    RemoveActionModal,
    SleepModal,
    CooldownModal
)
from ..helpers import Cooldown, View
from ..layouts import Layout 


__all__ = (
    'AutoResponderEditor',
)

class AutoResponderEditor(View):
    def __init__(self, bot, owner, *, default_trigger: Optional[str] = None, ar: Optional[AutoResponder] = None, timeout: float = 600):
        self.bot = bot
        self.owner: discord.Member = owner 

        self.trigger = default_trigger
        self.detection = None 
        self.actions = [] 
        self.restrictions = {}
        self.cooldown: Optional[Cooldown] = None

        if ar is not None:
            self.trigger = ar.trigger
            self.detection = ar.detection
            self.actions = ar.actions
            self.restrictions = ar.restrictions
            self.cooldown = ar.cooldown

        self.message: discord.Message = None
        self.final_interaction: discord.Interaction = None
        self.type = 'AutoResponderEditor'
        super().__init__(timeout=timeout, bot=bot, owner=owner)
        self.update()

    @property 
    def embed(self):
        if len(self.actions) == 0:
            desc = '**No Actions**'
        else:
            strs = []
            for i, action in enumerate(self.actions):
                strs.append(f'{i+1}. {action.type}')

            desc = '\n\n'.join(strs) 
            desc = f'**Actions:**\n\n{desc}'

        embed = discord.Embed(
            title='Autoresponder Editor', 
            description=desc,
            color=self.bot.DEFAULT_EMBED_COLOR
        )
        # trigger
        if self.trigger:
            embed.add_field(name='Trigger', value=self.trigger, inline=False)
        # detection
        if self.detection:
            embed.add_field(name='Detection', value=self.detection, inline=False)

        # restrictions 
        if len(self.restrictions) > 0:
            strs = []
            for k, v in self.restrictions.items():
                if len(v) == 0:
                    continue
                if k.endswith('channels'):
                    v = ', '.join(f'<#{i}>' for i in v)
                elif  k.endswith('roles'):
                    v = ', '.join(f'<@&{i}>' for i in v)
                elif k.endswith('users'):
                    v = ', '.join(f'<@{i}>' for i in v)
                strs.append(f'{k}: {v}')
            desc = '\n'.join(strs)
            embed.add_field(name='Restrictions', value=desc, inline=False)

        if self.cooldown:
            if self.cooldown.type is commands.BucketType.default:
                typev = 'Default'
            elif self.cooldown.type is commands.BucketType.user:
                typev = 'User'
            elif self.cooldown.type is commands.BucketType.channel:
                typev = 'Channel'

            s = 's' if self.cooldown.rate > 1 else ''
            embed.add_field(name=f'Cooldown ({typev})', value=f'{self.cooldown.rate} use{s} per {self.cooldown.per}s', inline=False)

        return embed
    
    def jsonify_actions(self) -> str:
        actions_list = []
        for a in self.actions:
            action_dict = {}
            action_dict['type'] = a.type 
            action_dict['kwargs'] = a.kwargs
            actions_list.append(action_dict)

        return json.dumps(actions_list, indent=4)
    
    def jsonify_restrictions(self) -> str:
        return json.dumps(self.restrictions, indent=4)

    def jsonify_cooldown(self) -> str:
        if self.cooldown is None:
            return None
        else:
            return self.cooldown.jsonify()

    def update(self):
        ok = True
        if self.trigger:
            self.trigger_status.label = 'Trigger set' 
            self.trigger_status.emoji = '\N{WHITE HEAVY CHECK MARK}'
        else:
            ok = False
            self.trigger_status.label = 'Trigger not set' 
            self.trigger_status.emoji = '\N{WARNING SIGN}'

        if self.detection is not None:
            self.detection_status.label = 'Detection set' 
            self.detection_status.emoji = '\N{WHITE HEAVY CHECK MARK}'
        else:
            ok = False
            self.detection_status.label = 'Detection not set' 
            self.detection_status.emoji = '\N{WARNING SIGN}'

        if len(self.actions) > 0:
            self.action_status.label = 'Action set' 
            self.action_status.emoji = '\N{WHITE HEAVY CHECK MARK}'
        else:
            ok = False
            self.action_status.label = 'Action not set' 
            self.action_status.emoji = '\N{WARNING SIGN}'

        self.submit.disabled = not ok

    @ui.button(label='Set trigger', style=ButtonStyle.blurple, row=0)
    async def set_trigger(self, interaction, button):
        modal = TriggerModal(self, self.trigger)
        await interaction.response.send_modal(modal)

    @ui.button(label='Set restrictions', style=ButtonStyle.blurple, row=0)
    async def set_restrictions(self, interaction, button):
        view = RestrictionsView(self)
        await interaction.response.edit_message(view=view)
    
    @ui.button(label='Set cooldown', style=ButtonStyle.blurple, row=0)
    async def set_cooldown(self, interaction, button):
        modal = CooldownModal(self)
        await interaction.response.send_modal(modal)
    
    @ui.select(placeholder='Select detection method', options=[
        discord.SelectOption(label='starts with trigger', value='starts'),
        discord.SelectOption(label='contains trigger', value='contains'),
        discord.SelectOption(label='matches trigger', value='matches'),
        discord.SelectOption(label='trigger is a word', value='contains_word'),
        discord.SelectOption(label='trigger is a regular expression', value='regex')
    ], row=1)
    async def set_detection_method(self, interaction, select):
        self.detection = select.values[0] 
        self.update()
        await interaction.response.edit_message(embed=self.embed, view=self)

    @ui.button(label='Add action', style=ButtonStyle.green, row=2)
    async def add_action(self, interaction, button):
        view = AddActionView(self)
        await interaction.response.edit_message(view=view)
    
    @ui.button(label='Remove action', style=ButtonStyle.red, row=2)
    async def remove_action(self, interaction, button):
        modal = RemoveActionModal(self)
        await interaction.response.send_modal(modal)

    @ui.button(label='Submit', style=ButtonStyle.green, row=3, disabled=True)
    async def submit(self, interaction, button):
        self.final_interaction = interaction
        self.cancelled = False
        self.stop()
    
    @ui.button(label='Cancel', style=ButtonStyle.red, row=3)
    async def cancel(self, interaction, button):
        await self.cancel_smoothly(interaction)

    @ui.button(label='Trigger not set', emoji='\N{WARNING SIGN}', style=ButtonStyle.grey, row=4, disabled=True)
    async def trigger_status(self, interaction, button):
        pass

    @ui.button(label='Detection not set', emoji='\N{WARNING SIGN}', style=ButtonStyle.grey, row=4, disabled=True)
    async def detection_status(self, interaction, button):
        pass

    @ui.button(label='Action not set', emoji='\N{WARNING SIGN}', style=ButtonStyle.grey, row=4, disabled=True)
    async def action_status(self, interaction, button):
        pass

    async def on_timeout(self):
        if self.message:
            await self.message.delete()
        self.stop()


class AddActionView(View):
    def __init__(self, parent_view: AutoResponderEditor, *, timeout: float = 600):
        super().__init__(timeout=timeout, bot=parent_view.bot, parent_view=parent_view)

    @ui.select(placeholder='Select an action', options=[
        discord.SelectOption(label='Send message', value='send_message'),
        discord.SelectOption(label='Add Roles', value='add_roles'),
        discord.SelectOption(label='Remove Roles', value='remove_roles'),
        discord.SelectOption(label='Add Reactions', value='add_reactions'),
        discord.SelectOption(label='Delete Trigger', value='delete_trigger_message'),
        discord.SelectOption(label='Sleep', value='sleep'),
    ], row=0)
    async def set_action(self, interaction, select):
        action_type = select.values[0]
        if action_type == 'send_message':
            view = SendMessageEditor(self)
            await interaction.response.edit_message(view=view)
        elif action_type == 'add_roles':
            view = AddRolesView(self)
            await interaction.response.edit_message(view=view)
        elif action_type == 'remove_roles':
            view = RemoveRolesView(self)
            await interaction.response.edit_message(view=view)
        elif action_type == 'add_reactions':
            view = AddReactionView(self)
            await interaction.response.edit_message(content='Add reactions to this message, then press **Submit**', view=view)
        elif action_type == 'delete_trigger_message':
            for action in self.parent_view.actions: 
                if action.type == 'delete_trigger_message':
                    await interaction.response.send_message('You can only have one delete trigger message action!', ephemeral=True)
                    return
            self.parent_view.actions.append(AutoResponderAction(self.bot, 'delete_trigger_message'))
            self.parent_view.update() 
            await interaction.response.edit_message(view=self.parent_view, embed=self.parent_view.embed)
        elif action_type == 'sleep':
            modal = SleepModal(self)
            await interaction.response.send_modal(modal)
        else:
            raise ValueError('Invalid action')
    
    @ui.button(label='Cancel', style=ButtonStyle.red, row=1)
    async def cancel(self, interaction, button):
        await interaction.response.edit_message(view=self.parent_view)

        
class SendMessageEditor(View):
    def __init__(self, parent_view: AddActionView, *, timeout: float = 600):
        self.parent_view = parent_view
        self.is_dm = False 
        self.channel = None 
        self.user = None 
        self.reply = False 
        self.ping_on_reply = True 
        self.delete_after = None 
        self.layout = Layout(self.bot)

        super().__init__(timeout=timeout, parent_view=parent_view)
        self.type = 'SendMessageEditor'
        self.clear_items()
        self.add_items()

    def add_user_select(self):
        select = ui.UserSelect(row=1, placeholder='Select user (nothing = same)', min_values=0)

        async def callback(interaction):
            if not self.interaction_check(interaction):
                return 

            if len(select.values) == 0:
                self.user = None 
            else:
                self.user = select.values[0]
            self.update()
            await interaction.response.edit_message(view=self, content=self.layout.content, embeds=self.layout.embeds)
        
        select.callback = callback 
        self.add_item(select)

    def add_channel_select(self):
        select = ui.ChannelSelect(row=1, placeholder='Select channel (nothing = same)', min_values=0)

        async def callback(interaction):
            if not self.interaction_check(interaction):
                return 

            if len(select.values) == 0:
                self.channel = None 
            else:
                self.channel = select.values[0]
            self.update()
            await interaction.response.edit_message(view=self, content=self.layout.content, embeds=self.layout.embeds)

        select.callback = callback 
        self.add_item(select) 

    def add_items(self):
        self.add_item(self.enter_layout)
        self.add_item(self.no_layout)
        self.add_item(self.dm_btn)
        if self.is_dm:
            self.add_user_select()
        else:
            self.add_channel_select()
        self.add_item(self.delete_after_btn)

        self.add_item(self.reply_btn)
        if self.reply:
            self.add_item(self.ping_on_reply_btn)

        self.add_item(self.layout_status)

        self.add_item(self.submit_btn)

    def update(self):
        ok = True 

        if self.is_dm:
            self.dm_btn.label = 'DM: Yes'
        else:
            self.dm_btn.label = 'DM: No'
        
        if self.ping_on_reply:
            self.ping_on_reply_btn.label = 'Ping on reply: Yes'
        else:
            self.ping_on_reply_btn.label = 'Ping on reply: No'

        if self.reply:
            self.reply_btn.label = 'Reply: Yes'
        else:
            self.reply_btn.label = 'Reply: No'

        if self.delete_after is None:
            self.delete_after_btn.label = 'Delete After: No'
        else:
            self.delete_after_btn.label = f'Delete After: {self.delete_after}s'

        if self.layout: 
            self.layout_status.label = 'Layout set' 
            self.layout_status.emoji = '\N{WHITE HEAVY CHECK MARK}'
        else:
            self.layout_status.label = 'Layout not set' 
            self.layout_status.emoji = '\N{WARNING SIGN}'
            ok = False

        self.submit_btn.disabled = not ok 
        self.clear_items()
        self.add_items()

    @ui.button(label='Enter layout', style=ButtonStyle.blurple, row=0)
    async def enter_layout(self, interaction, button):
        modal = ChooseLayoutModal(self)
        await interaction.response.send_modal(modal)
    
    @ui.button(label='No layout', style=ButtonStyle.gray, row=0)
    async def no_layout(self, interaction, button):
        modal = CreateLayoutModal(self)
        await interaction.response.send_modal(modal)

    @ui.button(label='DM: No', style=ButtonStyle.blurple, row=2)
    async def dm_btn(self, interaction, button):
        self.is_dm = not self.is_dm
        self.update()
        await interaction.response.edit_message(view=self, content=self.layout.content, embeds=self.layout.embeds)


    @ui.button(label='Delete After: No', style=ButtonStyle.blurple, row=3)
    async def delete_after_btn(self, interaction, button):
        modal = DeleteAfterModal(self)
        await interaction.response.send_modal(modal)

    @ui.button(label='Reply: No', style=ButtonStyle.blurple, row=3)
    async def reply_btn(self, interaction, button):
        self.reply = not self.reply
        self.update()
        await interaction.response.edit_message(view=self, content=self.layout.content, embeds=self.layout.embeds)

    @ui.button(label='Ping on reply: No', style=ButtonStyle.blurple, row=3)
    async def ping_on_reply_btn(self, interaction, button):
        self.ping_on_reply = not self.ping_on_reply
        self.update()
        await interaction.response.edit_message(view=self, content=self.layout.content, embeds=self.layout.embeds)
    

    @ui.button(label='Layout not set', emoji='\N{WARNING SIGN}', style=ButtonStyle.gray, disabled=True, row=4)
    async def layout_status(self, interaction, button):
        pass 

    @ui.button(label='Submit', style=ButtonStyle.green, disabled=True, row=4)
    async def submit_btn(self, interaction, button):
        action = AutoResponderAction(
            self.bot,
            'send_message',
            layout=self.layout.to_dict(),
            is_dm=self.is_dm,
            channel=self.channel,
            user=self.user,
            reply=self.reply,
            ping_on_reply=self.ping_on_reply,
            delete_after=self.delete_after
        )
        self.original_view.actions.append(action)
        self.original_view.update()
        await interaction.response.edit_message(view=self.original_view, embed=self.original_view.embed)

    @ui.button(label='Cancel', style=ButtonStyle.red, row=4)
    async def cancel_btn(self, interaction, button):
        await interaction.response.edit_message(view=self.parent_view)

    # async def on_timeout(self):
    #     if self.message:
    #         await self.message.delete()
    #     self.stop()

class AddRolesView(View):
    def __init__(self, parent_view: AddActionView, *, timeout: float = 600):
        super().__init__(timeout=timeout, parent_view=parent_view)

    @ui.select(cls=ui.RoleSelect, placeholder='Select roles', max_values=25, row=0)
    async def select_roles(self, interaction, select):
        action = AutoResponderAction(self.bot, 'add_roles', roles=[r.id for r in select.values])
        self.original_view.actions.append(action)
        await interaction.response.edit_message(view=self.original_view, embed=self.original_view.embed)

    @ui.button(label='Cancel', style=ButtonStyle.red, row=1)
    async def cancel(self, interaction, button):
        await interaction.response.edit_message(view=self.parent_view)

class RemoveRolesView(View):
    def __init__(self, parent_view: AddActionView, *, timeout: float = 600):
        super().__init__(timeout=timeout, parent_view=parent_view)

    @ui.select(cls=ui.RoleSelect, placeholder='Select roles', max_values=25, row=0)
    async def select_roles(self, interaction, select):
        action = AutoResponderAction(self.bot, 'remove_roles', roles=[r.id for r in select.values])
        self.original_view.actions.append(action)
        await interaction.response.edit_message(view=self.original_view, embed=self.original_view.embed)

    @ui.button(label='Cancel', style=ButtonStyle.red, row=1)
    async def cancel(self, interaction, button):
        await interaction.response.edit_message(view=self.parent_view)


class AddReactionView(View):
    def __init__(self, parent_view: AddActionView, *, timeout: float = 600):
        super().__init__(timeout=timeout, parent_view=parent_view)

    @ui.button(label='Submit', style=ButtonStyle.green)
    async def submit(self, interaction, button):
        # refetch to update emojis
        channel = self.original_view.message.channel
        message = await channel.fetch_message(self.original_view.message.id)

        emojis = [str(r.emoji) for r in message.reactions]
        if len(emojis) == 0:
            await interaction.response.send_message('No reactions found on the message!', ephemeral=True)
            return

        action = AutoResponderAction(self.bot, 'add_reactions', emojis=emojis)
        self.original_view.actions.append(action)
        await interaction.response.edit_message(content=None, view=self.original_view, embed=self.original_view.embed)


class RestrictionsView(View):
    def __init__(self, parent_view: AutoResponderEditor, *, timeout: float = 600):
        self.setting = None
        self.restrictions = {}
        super().__init__(timeout=timeout, parent_view=parent_view)
        self.clear_items()
        self.add_items()

    def add_items(self):
        self.add_item(self.select_restriction)

        if self.setting:
            if self.setting.endswith('channels'):
                self.add_item(ChannelSelect(self))
            elif self.setting.endswith('roles'):
                self.add_item(RoleSelect(self))
            elif self.setting.endswith('users'):
                self.add_item(UserSelect(self))

        self.add_item(self.cancel)

    @ui.select(options=[
        discord.SelectOption(label='Blacklist channels', value='blacklisted_channels'),
        discord.SelectOption(label='Whitelist channels', value='whitelisted_channels'),
        discord.SelectOption(label='Blacklist roles', value='blacklisted_roles'),
        discord.SelectOption(label='Whitelist roles', value='whitelisted_roles'),
        discord.SelectOption(label='Blacklist users', value='blacklisted_users'),
        discord.SelectOption(label='Whitelist users', value='whitelisted_users'),
    ], placeholder='Select a restriction')
    async def select_restriction(self, interaction, select):
        self.setting = select.values[0]
        self.clear_items()
        self.add_items()
        await interaction.response.edit_message(view=self)

    @ui.button(label='Cancel', style=ButtonStyle.red)
    async def cancel(self, interaction, button):
        await interaction.response.edit_message(view=self.parent_view)



class UserSelect(ui.UserSelect):
    def __init__(self, parent_view: RestrictionsView):
        self.parent_view = parent_view
        super().__init__(max_values=25)

    async def callback(self, interaction: discord.Interaction):
        self.original_view.restrictions[self.parent_view.setting] = [obj.id for obj in self.values]
        self.original_view.update()
        await interaction.response.edit_message(view=self.original_view, embed=self.original_view.embed)
    

class ChannelSelect(ui.ChannelSelect):
    def __init__(self, parent_view: RestrictionsView):
        self.parent_view = parent_view
        super().__init__(max_values=25)

    async def callback(self, interaction: discord.Interaction):
        self.original_view.restrictions[self.parent_view.setting] = [obj.id for obj in self.values]
        self.original_view.update()
        await interaction.response.edit_message(view=self.original_view, embed=self.original_view.embed)

class RoleSelect(ui.RoleSelect):
    def __init__(self, parent_view: RestrictionsView):
        self.parent_view = parent_view
        super().__init__(max_values=25)

    async def callback(self, interaction: discord.Interaction):
        self.original_view.restrictions[self.parent_view.setting] = [obj.id for obj in self.values]
        self.original_view.update()
        await interaction.response.edit_message(view=self.original_view, embed=self.original_view.embed)