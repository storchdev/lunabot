import json 
import discord 
from discord.ext import commands 
from discord import ui 
import time 
import asyncio 
from datetime import timedelta, datetime
from .utils import View
from io import StringIO

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from bot import LunaBot


class Ticket:
    def __init__(self, opener, timestamp):
        self.opener = opener
        self.timestamp = timestamp 
        self.id = None
        self.channel = None
    

class CloseReason(ui.Modal, title='Close'):
    def __init__(self, parent_view):
        super().__init__()
        self.parent_view = parent_view 

    reason = ui.TextInput(
        label='Reason', 
        placeholder='Reason for closing the ticket, e.g. "Resolved"',
        max_length=1024
    )

    async def on_submit(self, inter):
        await inter.response.send_message('Saving transcript...')
        await self.parent_view.close(inter, str(self.reason))

    
class CloseView(View):
    def __init__(self, bot, ticket_id, channel, opener_id, timestamp):
        super().__init__(bot=bot, timeout=None)
        self.ticket_id = ticket_id
        self.channel = channel 
        self.opener_id = opener_id 
        self.timestamp = timestamp
        self.close_without_reason.custom_id = f'ticket-noreason-{ticket_id}'
        self.close_with_reason.custom_id = f'ticket-reason-{ticket_id}'
    
    async def save_transcript(self):
        msg_objs = []
        async for msg in self.channel.history(oldest_first=True, limit=None):
            if msg.author.bot:
                continue 
            file_channel = self.bot.get_channel(self.bot.vars.get('transcript-file-channel-id'))

            if msg.attachments:
                new_msg = await file_channel.send(files=[await a.to_file() for a in msg.attachments])
                attachments = [a.url for a in new_msg.attachments]
            else:
                attachments = []

            msg_objs.append({
                'author_id': msg.author.id,
                'username': msg.author.name,
                'content': msg.content,
                'attachments': attachments
            })
        query = 'INSERT INTO ticket_transcripts (ticket_id, opener_id, messages) VALUES ($1, $2, $3)'
        await self.bot.db.execute(query, self.ticket_id, self.opener_id, json.dumps(msg_objs, indent=4))

    async def interaction_check(self, inter):
        if inter.user.id == self.bot.owner_id:
            return True 

        if inter.user.id == self.opener_id:
            await inter.response.send_message('Sorry, only staff can close tickets.', ephemeral=True) 
            return False
        return True

    async def close(self, inter, reason):
        await self.save_transcript()
        await self.channel.delete()
        query = 'DELETE FROM active_tickets WHERE ticket_id = $1'
        await inter.client.db.execute(query, self.ticket_id) 

        embed = discord.Embed(
            title='Ticket Closed',
            color=self.bot.DEFAULT_EMBED_COLOR,
            timestamp=discord.utils.utcnow()
        )
        embed.add_field(name='Ticket ID', value=str(self.ticket_id))
        embed.add_field(name='Opened By', value=f'<@!{self.opener_id}>')
        embed.add_field(name='Closed By', value=inter.user.mention)
        embed.add_field(name='Open Time', value=discord.utils.format_dt(self.timestamp))
        embed.add_field(name='Reason', value=reason, inline=False)
        archive = self.bot.get_channel(self.bot.vars.get('archive-channel-id'))
        await archive.send(embed=embed)
        
    @ui.button(label='Close', style=discord.ButtonStyle.red, emoji='\U0001f512')
    async def close_without_reason(self, inter, button):
        await inter.response.send_message('Saving transcript...')
        await self.close(inter, "No reason given")
    
    @ui.button(label='Close With Reason', style=discord.ButtonStyle.red, emoji='\U0001f512', row=1)
    async def close_with_reason(self, inter, button):
        modal = CloseReason(self)
        await inter.response.send_modal(modal)



class TicketView(ui.View):

    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot: 'LunaBot' = bot 
    
    @ui.button(label='joe', custom_id='helpdesk')
    async def open_ticket(self, interaction, button):
        menu = TicketTypeMenu(self.bot, interaction.user)
        await interaction.response.send_message('**Please select an option from the menu**', view=menu, ephemeral=True)
        

class TicketTypeMenu(View):
    def __init__(self, bot, owner):
        super().__init__(bot=bot, owner=owner)

        for option in ['VIP Artist', 'Trusted Seller', 'Partnership Request', 'PM Request', 'Booster Perks', 'User Report', 'General Inquiry', 'Other']:
            self.ticket_type.add_option(label=option)
    
    async def interaction_check(self, inter):
        end_time = await self.bot.get_cd('ticket', inter.user, 60)
        if end_time:
            layout = self.bot.get_layout('ticketcd')
            await layout.send(inter, None, ephemeral=True, repls={'timethingy': discord.utils.format_dt(end_time, 'R')})
            return False 
        
        return True

    @ui.select(placeholder='What is this ticket for?')
    async def ticket_type(self, interaction, select):
        await interaction.response.edit_message(content='Please wait a moment...', view=None)
        ticket = await self.create_ticket()
        embed = discord.Embed(
            title='Ticket',
            color=self.bot.DEFAULT_EMBED_COLOR,
            description=f'Opened a new ticket: {ticket.channel.mention}'
        )
        msg = await interaction.original_response()
        await msg.edit(content=None, embed=embed)

    async def create_ticket(self):
        ticket = Ticket(self.owner, discord.utils.utcnow())
        channel = await self.create_channel(ticket)
        query = 'INSERT INTO active_tickets (ticket_id, channel_id, opener_id, timestamp) VALUES ($1, $2, $3, $4)'
        await self.bot.db.execute(query, ticket.id, ticket.channel.id, ticket.opener.id, ticket.timestamp.timestamp())
        view = CloseView(self.bot, ticket.id, ticket.channel, ticket.opener.id, ticket.timestamp)
        
        choice = self.ticket_type.values[0]
        luna_id = self.bot.vars.get('luna-id')
        pm_id = self.bot.vars.get('pm-role-id')
        staff_id = self.bot.vars.get('staff-role-id')

        if choice == 'VIP Artist':
            pings = f'<@{luna_id}>'
        elif choice == 'Trusted Seller':
            pings = f'<@{luna_id}>'
        elif choice == 'Partnership Request':
            pings = f'<@&{pm_id}>'  
        elif choice == 'PM Request':
            pings = f'<@{luna_id}>'  
        elif choice == 'Booster Perks':
            pings = f'<@{luna_id}>'
        elif choice == 'User Report':
            pings = f'<@&{staff_id}>'
        elif choice == 'General Inquiry':
            pings = f'<@&{staff_id}>'
        else:
            pings = f'<@&{staff_id}>'

        temp = await channel.send(f'{self.owner.mention}')
        archive = self.bot.get_channel(self.bot.vars.get('archive-channel-id'))
        await channel.send(view=view, embed=self.bot.get_embed('ticketinfo'))
        await archive.send(f'{pings}: get ready to rizz up {self.owner.mention} in {channel.mention} on skibidi')
        await asyncio.sleep(1)
        await temp.delete()
        return ticket 

    async def create_channel(self, ticket: Ticket):
        query = 'UPDATE ticket_counter SET num = num + 1 RETURNING num'
        ticket_id = await self.bot.db.fetchval(query)

        ticket.id = ticket_id
        archive = self.bot.get_channel(self.bot.vars.get('archive-channel-id'))
        staffrole = self.owner.guild.get_role(self.bot.vars.get('staff-role-id'))

        overwrites = {
            self.owner.guild.default_role: discord.PermissionOverwrite(view_channel=False),
            self.owner: discord.PermissionOverwrite(view_channel=True),
            staffrole: discord.PermissionOverwrite(view_channel=True)
        }

        ticket.channel = await archive.category.create_text_channel(name=f'ticket-{ticket_id}', overwrites=overwrites)
        return ticket.channel

class TicketCog(commands.Cog, name='Tickets', description='a few sketchy admin-only sketchy commands'):

    def __init__(self, bot):
        self.bot: 'LunaBot' = bot 

    async def cog_load(self):
        self.bot.add_view(TicketView(self.bot))
    
        query = 'SELECT * FROM active_tickets'
        rows = await self.bot.db.fetch(query)
        for row in rows:
            close = CloseView(self.bot, row['ticket_id'], self.bot.get_channel(row['channel_id']), row['opener_id'], datetime.fromtimestamp(row['timestamp']))
            self.bot.add_view(close)
    
    
    async def get_txt_file(self, ticket_id):
        query = 'SELECT messages FROM ticket_transcripts WHERE ticket_id = $1'
        row = await self.bot.db.fetchrow(query, ticket_id)
        if not row:
            return None
        msgs = json.loads(row['messages'])
        output = StringIO()
        for msg in msgs:
            output.write(f'{msg["username"]} ({msg["author_id"]}): {msg["content"]}\n')
            for a in msg['attachments']:
                output.write(f'  {a}\n')
            output.write('\n')
        
        output.seek(0)
        return discord.File(output, filename=f'transcript-{ticket_id}.txt')


    async def cog_check(self, ctx):
        return ctx.author.id == self.bot.owner_id or ctx.author.guild_permissions.administrator

    @commands.command()
    async def transcript(self, ctx, ticket_id: int):
        file = await self.get_txt_file(ticket_id)
        if file is None:
            await ctx.send('No transcript found for that ticket')
            return 
        await ctx.send(file=file)

    @commands.command()
    async def sendembed(self, ctx, channel: discord.TextChannel):
        for view in self.bot.persistent_views:
            if view.channel_id == channel.id:
                embed = view.embed1
                await channel.send(embed=embed, view=view)
                await ctx.send('ok')
                return 
        await ctx.send('i dont have a ticket prepared for that channel yet, pls contact storch')
        
    @commands.command()
    async def giverole(self, ctx, member: discord.Member, role: discord.Role):
        for view in self.bot.persistent_views:
            if view.required_role_id == role.id:
                try:
                    await member.add_roles(role)
                except discord.Forbidden:
                    await ctx.send('I couldnt give that member the role, make sure im not being permission hiearchyd')
                    return 
                
                query = 'INSERT INTO cooldowns (custom_id, user_id, end_time, reason) VALUES (?, ?, ?, ?)'
                await self.bot.db.execute(query, view.custom_id, member.id, int(time.time() + view.cooldown), 'initial wait')
                
                channel = self.bot.get_channel(view.channel_id)
                md = discord.utils.format_dt(discord.utils.utcnow() + timedelta(seconds=view.cooldown), 'd')
                await ctx.send(f'I gave {member.mention} the role; they can apply in {channel.mention} on {md}')
                return 

        await ctx.send('that role isnt required for any tickets')

async def setup(bot):
    await bot.add_cog(TicketCog(bot))