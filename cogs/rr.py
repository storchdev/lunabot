from discord import app_commands 
import asyncio
from discord.ext import commands, tasks 
import discord 
import time 
import datetime 
from discord import ui
from discord import ButtonStyle
import json 
import textwrap 
from discord import TextStyle 



# TODO: fix this whole thing later its messy asf

class TextModal(ui.Modal, title='Customize the reaction role message'):
    text = ui.TextInput(label='Enter message text here', style=TextStyle.long)

    def __init__(self, embed):
        self.embed = embed 
        super().__init__()

    async def on_submit(self, inter):
        self.embed.set_field_at(0, name='Message Text', value=str(self.text))
        await inter.response.edit_message(embed=self.embed)


class RRView1(ui.View):
    def __init__(self, ctx, embed, options):
        self.ctx = ctx
        self.ready = False 
        self.embed = embed

        self.message = None 
        self.embedname = None 

        self.modal = None 
        self.other_message_id = None

        super().__init__(timeout=None)

    @ui.button(label='Add message text', style=ButtonStyle.green)
    async def addmsg(self, inter, button):
        def check(m):
            return m.channel == inter.channel and m.author == inter.user

        await inter.response.send_message('Enter the message text:')
        try:
            msg = await self.ctx.bot.wait_for('message', check=check, timeout=180)
        except asyncio.TimeoutError:
            await inter.followup.send('You took too long to respond, please try again.') 
            return
        self.message = msg.content
        self.embed.set_field_at(0, name='Message Text', value=self.message)
        await self.sent.edit(embed=self.embed)
    
    @ui.button(label='Add an embed')
    async def embedbtn(self, inter, btn):
        await inter.response.send_message('Enter the name of an embed:')
        def check(m):
            return m.channel == inter.channel and m.author == inter.user
        try:
            msg = await self.ctx.bot.wait_for('message', check=check, timeout=180)
        except asyncio.TimeoutError:
            await inter.followup.send('You took too long to respond, please try again.') 
            return
        
        query = 'SELECT embed FROM embeds WHERE name = $1'
        val = await self.ctx.bot.db.fetchval(query, msg.content.lower())
        if val is None:
            await inter.response.send_message('No embed with that name found.')
            return

        self.embedname = msg.content.lower()
        self.embed.set_field_at(1, name='Embed', value=self.embedname)
        await self.sent.edit(embed=self.embed)

    @ui.button(label='Use an existing message', style=discord.ButtonStyle.blurple)
    async def useexisting(self, inter, btn):
        await inter.response.send_message('Enter the message ID:')

        def check(m):
            return m.channel == inter.channel and m.author == inter.user 

        try:
            msg = await inter.client.wait_for('message', check=check, timeout=180)
        except asyncio.TimeoutError:
            await inter.followup.send('You took too long to respond, please try again.') 
            return 
        
        self.other_message_id = msg.content 
        self.ready = True 
        self.stop() 

    @ui.button(label='Submit', style=ButtonStyle.green)
    async def submit(self, inter, button):
        if not (self.message or self.embed):
            await inter.response.send_message('Please enter either a message or an embed.', ephemeral=True)
            return 

        for item in self.children:
            item.disabled = True
        await inter.response.edit_message(view=self)
        
        self.ready = True 
        self.stop()

    @ui.button(label='Quit', style=ButtonStyle.red)
    async def quitbtn(self, inter, button):
        for item in self.children:
            item.disabled = True
        await inter.response.edit_message(view=self)
        self.stop()



class Joever(ValueError):
    ... 

async def parsemap(ctx, text):
    econv = commands.EmojiConverter()
    rconv = commands.RoleConverter()
    stuff = {}
    for line in text.splitlines():
        x = line.split()
        if len(x) != 2:
            raise Joever()
        try:
            emoji = await econv.convert(ctx, x[0])
            role = await rconv.convert(ctx, x[1])
        except (commands.CommandError, commands.BadArgument):
            raise Joever()
        stuff[str(emoji)] = role.id 

    if len(stuff) == 0:
        raise Joever()
    
    return stuff


class RRView2(ui.View):

    async def interaction_check(self, interaction):
        if interaction.user.id == self.ctx.author.id:
            return True 
        else:
            await interaction.response.defer()
            return False 
    
    def __init__(self, ctx, length):

        super().__init__(timeout=None)

        self.ez.add_option(label='No limit', value='-1')
        
        for i in range(1, length):
            self.ez.add_option(label=str(i), value=str(i))

        self.ctx = ctx 
        self.limit = None
        self.ready = False 


    @ui.select()
    async def ez(self, inter, select):
        self.limit = select.values[0]
        self.ready = True 
        await inter.response.defer()

    @ui.button(label='Submit', style=ButtonStyle.green)
    async def submit(self, inter, button):
        if self.limit is None:
            return await inter.response.send_message('Please choose a limit first.', ephemeral=True)
        
        for item in self.children:
            item.disabled = True
        await inter.response.edit_message(view=self)
        self.ready = True
        self.stop()


class TimeModal(ui.Modal, title='Set minimum time since joining'):
    def __init__(self, embed):
        self.embed = embed 
        self.seconds = 0

    days = ui.TextInput(label='Days', default='0')
    hours = ui.TextInput(label='Hours', default='0')
    minutes = ui.TextInput(label='Minutes', default='0')

    async def on_submit(self, inter):
        try:
            days = int(str(self.days))
            hours = int(str(self.hours))
            minutes = int(str(self.minutes))
        except ValueError:
            return await inter.response.send_message('Please enter a valid time.', ephemeral=True)

        secs = days * 86400 + hours * 3600 + minutes * 60
        if secs <= 0:
            secs = 0
        self.secs = secs 
        if self.secs == 0:
            val = 'None'
        else:
            val = f'{self.secs} seconds\n\n**:warning: Needs deny message**'
        
        self.embed.set_field_at(1, name='Required Time', value=val)
        await inter.response.edit_message(embed=self.embed)

class RoleDenyModal(ui.Modal, title='When user doesn\'t have a role'):
    text = ui.TextInput(label='Enter message here', style=TextStyle.long)

    def __init__(self, embed):
        self.embed = embed
        self.denymsg = None

    async def on_submit(self, inter):
        gg = self.embed.fields[0].split('\n\n')[0]
        self.embed.set_field_at(0, name='Required Role', value=f'{gg}\n\n**:white_check_mark: Has deny message**')
        self.denymsg = str(self.text)
        await inter.response.edit_message(embed=self.embed)

class TimeDenyModal(ui.Modal, title='When user hasn\'t stayed long enough'):
    text = ui.TextInput(label='Enter message here', style=TextStyle.long, default="Use {time} for the remaining time thingy (DO NOT TYPE 'in' BEFORE IT)")


    def __init__(self, embed):
        self.embed = embed
        self.denymsg = None

    async def on_submit(self, inter):
        gg = self.embed.fields[1].split('\n\n')[0]
        self.embed.set_field_at(1, name='Required Time', value=f'{gg}\n\n**:white_check_mark: Has deny message**')
        self.denymsg = str(self.text)
        await inter.response.edit_message(embed=self.embed)

class RRView3(ui.View):
    def __init__(self, ctx, embed):
        super().__init__(timeout=None)
        self.ctx = ctx 
        self.embed = embed 
        self.role = None 
        self.modal = None 
        self.seconds = 0 
        self.role_denymsg = None 
        self.time_denymsg = None

    async def interaction_check(self, interaction):
        return interaction.user.id == self.ctx.author.id

    @ui.select(cls=ui.RoleSelect)
    async def roleselect(self, inter, select):
        self.role = select.values[0]
        self.role_denymsg = None
        self.embed.set_field_at(0, name='Required Role', value=f'{self.role.mention}\n\n**Requires deny message**')
        await inter.response.edit_message(embed=self.embed)
    
    @ui.button(label='Set time requirement', style=ButtonStyle.blurple)
    async def timebtn(self, inter, button):
        self.modal = TimeModal(self.embed)
        self.time_denymsg = None 
        await inter.response.send_modal(self.modal)
        await self.modal.wait()
        self.seconds = self.modal.seconds 
    
    @ui.button(label='Submit', style=ButtonStyle.green, row=2)
    async def submit(self, inter, button):
        if self.role is not None and self.role_denymsg is None:
            rdmodal = RoleDenyModal(self.embed)
            await inter.response.send_modal(rdmodal)
            await rdmodal.wait()
            self.role_denymsg = rdmodal.denymsg 
        elif self.seconds != 0 and self.time_denymsg is None:
            tdmodal = TimeDenyModal(self.embed)
            await inter.response.send_modal(tdmodal)
            await tdmodal.wait()
            self.time_denymsg = tdmodal.denymsg

        for item in self.children:
            item.disabled = True
        await inter.response.edit_message(view=self)
        
        self.ready = True 
        self.stop()

class RR(commands.Cog, name='Reaction Roles'):
    def __init__(self, bot):
        self.bot = bot

    async def cog_load(self):
        # make the rr_selections table
        query = '''
                    CREATE TABLE IF NOT EXISTS rr_selections (
                        user_id BIGINT NOT NULL,
                        channel_id BIGINT NOT NULL,
                        message_id BIGINT NOT NULL,
                        role_id BIGINT NOT NULL,
                        PRIMARY KEY (user_id, channel_id, message_id, role_id)
                    )
                '''
        await self.bot.db.execute(query)

    
    async def cog_check(self, ctx):
        return ctx.author.guild_permissions.administrator or ctx.author.id == self.bot.STORCH_ID
    
    @commands.hybrid_command()
    @app_commands.default_permissions()
    async def addrr(self, ctx, *, channel: discord.TextChannel):
        embed = discord.Embed(
            title='Make the message for reactions to go under',
            color=0xcab7ff
        ).add_field(name='Message Text', value='None').add_field(name='Embed', value='None')
        query = 'SELECT name FROM embeds WHERE creator_id = $1'
        rows = await self.bot.db.fetch(query, ctx.author.id)
        options = [row['name'] for row in rows]

        view1 = RRView1(ctx, embed, options)
        view1.sent = await ctx.send(embed=embed, view=view1)
        await view1.wait()

        if not view1.ready:
            await view1.sent.delete()
            return 
        await view1.sent.edit(view=None)

        if view1.other_message_id is not None:
            try:
                fetchedmsg = await channel.fetch_message(int(view1.other_message_id))
            except (discord.NotFound, ValueError):
                return await ctx.send('Message not found.')
        
        await ctx.send(textwrap.dedent("""
        Enter each emoji and role pair for each reaction, on a different line. For example:

        :nerd: @Role1
        :clown: @Role2
        :skull: @Role3

        Please leave a space between the emoji and the role!
        """))

        def check(m):
            return m.author == ctx.author and m.channel == ctx.channel 
        
        joever = False 
        while not joever:
            msg = await self.bot.wait_for('message', check=check)
            if msg.content.lower() == 'cancel':
                return
            try:
                stuff = await parsemap(ctx, msg.content)
                joever = True
            except Joever:
                await ctx.send('Something went wrong while parsing that! Please try again.')
        
        view2 = RRView2(ctx, len(stuff))
        await ctx.send('Choose a limit to the number of roles someone can get from this group:', view=view2)
        await view2.wait()

        if not view2.ready:
            return 
        
        embed = discord.Embed(
            title='Optional Settings',
            color=0xcab7ff
        ).add_field(name='Role Requirement', value='None').add_field(name='Time Requirement', value='None')
        view3 = RRView3(ctx, embed)
        await ctx.send(embed=embed, view=view3)
        await view3.wait()

        if view1.other_message_id is None:
            embedout = None 
            if view1.embedname:
                query = 'SELECT embed FROM embeds WHERE name = $1'
                val = await self.bot.db.fetchval(query, view1.embedname)
                embedout = discord.Embed.from_dict(json.loads(val))

            rrmsg = await channel.send(view1.message, embed=embedout)
        else:
            rrmsg = fetchedmsg 
        
        for emoji in stuff:
            await rrmsg.add_reaction(emoji)
        msgid = rrmsg.id

        query = """INSERT INTO
                       rrs (
                           channel_id,
                           message_id,
                           map,
                           max_sel,
                           req_role_id,
                           no_role_msg,
                           req_time,
                           no_time_msg
                       )
                   VALUES
                       ($1, $2, $3, $4, $5, $6, $7, $8)
                """
        await self.bot.db.execute(query, channel.id, msgid, json.dumps(stuff), int(view2.limit), view3.role.id if view3.role else None, view3.role_denymsg, view3.seconds, view3.time_denymsg)
        await ctx.send('Successfully added reaction role :white_check_mark:')

    @commands.hybrid_command()
    @app_commands.default_permissions()
    async def removerr(self, ctx, channel: discord.TextChannel, message_id: int):
        try:
            message = await channel.fetch_message(message_id)
        except discord.NotFound:
            return await ctx.send('Message not found.')

        await message.delete()
        query = 'DELETE FROM rrs WHERE channel_id = $1 AND message_id = $2'
        await self.bot.db.execute(query, channel.id, message_id)
        await ctx.send('Successfully removed reaction role :white_check_mark:')

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):
        query = 'SELECT map, max_sel, req_role_id, no_role_msg, req_time, no_time_msg FROM rrs WHERE channel_id = $1 AND message_id = $2'
        row = await self.bot.db.fetchrow(query, payload.channel_id, payload.message_id)
        if row is None:
            return 

        if row['req_role_id'] is not None:
            if row['req_role_id'] not in [role.id for role in payload.member.roles]:
                if row['no_role_msg'] is not None:
                    await payload.member.send(row['no_role_msg'])
                return await payload.member.remove_reaction(payload.emoji, payload.member.guild.get_channel(payload.channel_id).get_partial_message(payload.message_id))

        if row['req_time'] is not None:
            if payload.member.joined_at is None:
                return await payload.member.remove_reaction(payload.emoji, payload.member.guild.get_channel(payload.channel_id).get_partial_message(payload.message_id))
            if (discord.utils.utcnow() - payload.member.joined_at).total_seconds() < row['req_time']:
                if row['no_time_msg'] is not None:
                    await payload.member.send(row['no_time_msg'].replace('{time}', discord.utils.format_dt(payload.member.joined_at + datetime.timedelta(seconds=row['req_time']), 'R')))
                return await payload.member.remove_reaction(payload.emoji, payload.member.guild.get_channel(payload.channel_id).get_partial_message(payload.message_id))

        if row['max_sel'] != -1:
            query = 'SELECT COUNT(*) FROM rr_selections WHERE user_id = $1 AND channel_id = $2 AND message_id = $3'
            count = await self.bot.db.fetchval(query, payload.user_id, payload.channel_id, payload.message_id)
            if count >= row['max_sel']:
                return await payload.member.remove_reaction(payload.emoji, payload.member.guild.get_channel(payload.channel_id).get_partial_message(payload.message_id))

        query = 'SELECT role_id FROM rr_selections WHERE user_id = $1 AND channel_id = $2 AND message_id = $3'
        rows = await self.bot.db.fetch(query, payload.user_id, payload.channel_id, payload.message_id)
        if str(payload.emoji) in [str(row['role_id']) for row in rows]:
            return await payload.member.remove_reaction(payload.emoji, payload.member.guild.get_channel(payload.channel_id).get_partial_message(payload.message_id))

        map = json.loads(row['map'])
        if str(payload.emoji) not in map:
            return await payload.member.remove_reaction(payload.emoji, payload.member.guild.get_channel(payload.channel_id).get_partial_message(payload.message_id))
        
        role = payload.member.guild.get_role(map[str(payload.emoji)])
        await payload.member.add_roles(role)
        query = """INSERT INTO
                       rr_selections (user_id, channel_id, message_id, role_id)
                   VALUES
                       ($1, $2, $3, $4)
                   ON CONFLICT DO NOTHING
                """
        await self.bot.db.execute(query, payload.user_id, payload.channel_id, payload.message_id, role.id)

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload):
        query = 'SELECT map FROM rrs WHERE channel_id = $1 AND message_id = $2'
        row = await self.bot.db.fetchrow(query, payload.channel_id, payload.message_id)
        if row is None:
            return 

        map = json.loads(row['map'])
        if str(payload.emoji) not in map:
            return 

        guild = self.bot.get_guild(payload.guild_id)
        member = guild.get_member(payload.user_id)

        role = member.guild.get_role(map[str(payload.emoji)])
        await member.remove_roles(role)
        query = 'DELETE FROM rr_selections WHERE user_id = $1 AND channel_id = $2 AND message_id = $3 AND role_id = $4'
        await self.bot.db.execute(query, payload.user_id, payload.channel_id, payload.message_id, role.id)


async def setup(bot):
    await bot.add_cog(RR(bot))
