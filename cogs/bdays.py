from discord.ext import commands, tasks
from discord import app_commands
from datetime import datetime, time, date, timedelta
from discord import ui 
import discord
from discord.interactions import Interaction 
import textwrap 
from zoneinfo import ZoneInfo
from .utils import LayoutContext
import json 
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from bot import LunaBot


def is_valid_month(monthstr):
    try:
        month = int(monthstr)
    except ValueError:
        return False 
    return 1 <= month <= 12 

def is_valid_day(month, daystr):
    try:
        day = int(daystr)
    except ValueError:
        return False
    
    if month == 2:
        limit = 29 
    elif month in (1, 3, 5, 7, 8, 10, 12):
        limit = 31 
    else:
        limit = 30 
    
    return 1 <= day <= limit 


start_time = time(hour=5, minute=0)

class Birthdays(commands.Cog, description="Set your birthday, see other birthdays"):

    def __init__(self, bot):
        self.bot: 'LunaBot' = bot 
    
    async def cog_load(self):
        self.send_bdays.start()

    async def cog_unload(self):
        self.send_bdays.cancel()

    @tasks.loop(time=start_time)
    async def send_bdays(self):
        now = datetime.now()

        query = 'SELECT user_id FROM bdays WHERE month = $1 AND day = $2'
        user_ids = await self.bot.db.fetch(query, now.month, now.day)
        if len(user_ids) == 0:
            return 

        mentions_list = []
        rm_timestamp = (now+timedelta(days=7)).timestamp()

        for user_id in user_ids: 
            guild = self.bot.get_guild(self.bot.GUILD_ID)
            member = guild.get_member(user_id)
            if member is None:
                continue 

            mentions_list.append(member.mention)
            role = guild.get_role(self.bot.vars.get('bday-role-id'))
            await member.add_roles(role)
            await self.bot.schedule_remove_role(member, role, rm_timestamp)

        if len(mentions_list) == 1:
            mentions_str = mentions_list[0]
        elif len(mentions_list) == 2:
            mentions_str = ' and '.join(mentions_list)
        else:
            mentions_str = ', '.join(mentions_list[:-1]) + ', and ' + mentions_list[-1]

        channel = self.bot.get_channel(self.bot.vars.get('bday-channel-id'))  
        layout = self.bot.get_layout('bday')
        ctx = LayoutContext(author=member)
        await layout.send(channel, ctx, repls={'mentions': mentions_str})

    @commands.hybrid_command(name='set-birthday')
    async def set_bday(self, ctx):
        """Sets your birthday to be announced in the designated channel."""
        if ctx.interaction is None:
            return await ctx.send('Sorry, this command is **slash only**!')
        inter = ctx.interaction
        class Modal(ui.Modal, title='Enter your birthday'):
            month = ui.TextInput(label='Month (1-12)', max_length=2)
            day = ui.TextInput(label='Day (1-31)', max_length=2)

            async def on_submit(self, minter):
                month = str(self.month)
                day = str(self.day )
                if not is_valid_month(month):
                    await minter.response.send_message('Please try again and enter a valid month (number between 1 and 12).', ephemeral=True)
                    return 
                month = int(month)
                if not is_valid_day(month, day):
                    await minter.response.send_message('Please try again and enter a valid day.', ephemeral=True)
                    return 
                day = int(day)
                
                query = 'INSERT INTO bdays (user_id, month, day) VALUES ($1, $2, $3) ON CONFLICT (user_id) DO UPDATE SET month = $2, DAY = $3'
                await minter.bot.db.execute(query, minter.author.id, month, day)
                
                await minter.response.send_message(f'Set your birthday to {month}/{day}!', ephemeral=True)
        
        modal = Modal()
        
        await inter.response.send_modal(modal)
    
    @commands.hybrid_command(name='upcoming-birthdays')
    async def upcoming_bdays(self, ctx):
        """Gets people's birthdays up to the next 10."""

        def magic(now, m, d):
            move = False 
            if m < now.month:
                move = True 
            elif m == now.month:
                if d < now.day:
                    move = True 
            if move:
                return date(now.year+1, m, d)
            else:
                return date(now.year, m, d)

            
        embed = discord.Embed(title='Upcoming Birthdays', color=0xcab7ff)
        row = await self.bot.db.fetchrow('SELECT user_id, month, day FROM bdays')
        now = datetime.now(tz=ZoneInfo("US/Central"))
        x = sorted(x, key=lambda row: magic(now, row['month'], row['day']))
        x = x[:10]
        for row in x:
            user = ctx.guild.get_member(row['user_id'])
            disp = user.display_name if user else f'User with ID {row["user_id"]}'
            
            if (row['month'], row['day']) == (now.month, now.day):
                opt = '(Happy Birthday!)'
            else:
                opt = ''
            embed.add_field(name=disp, value=f'{row["month"]}/{row["day"]} {opt}', inline=False)
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Birthdays(bot))
