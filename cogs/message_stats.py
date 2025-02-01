from discord.ext import commands 
import random 
from .utils.checks import staff_only
import discord 
import asyncio 
from matplotlib import pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime, timedelta, time
from typing import TYPE_CHECKING
from io import BytesIO
from pytz import timezone 
from dateparser import parse



if TYPE_CHECKING:
    from bot import LunaBot



class MsgStatsFlags(commands.FlagConverter):
    all_channels: bool = False
    start: str = "1 week ago"
    end: str = "now"    
    tick: str = "1d"
    ticks: int = None 
    


def plot_data_sync(data, title, ylabel):
    """
    Plot data synchronously.
    :param data: A dictionary with join, leave, and net data.
    :param stat: The statistic to plot ('joins', 'leaves', 'net').
    :param start: Start time for the plot.
    :param end: End time for the plot.
    :return: A BytesIO object containing the plot.
    """
    # Prepare the data for plotting
    x_values = []
    y_values = []

    for time, value in data:
        x_values.append(time)
        y_values.append(value)

    # Create the plot.
    fig = plt.figure(figsize=(8, 5))
    fig.set_facecolor('none')  # Set figure background color
    ax = fig.add_subplot(1, 1, 1)
    ax.set_facecolor('none')  # Set axes background color

    # Plot the data
    marker = None

    ax.plot(x_values, y_values, color="#cab7ff", marker=marker)  # Use colors for the line and markers

    # Set title and labels
    ax.set_title(title, color='cyan')
    ax.set_ylabel(ylabel, color='cyan')

    ax.set_xlabel("Time", color='cyan')

    # Customize the axes
    ax.spines['top'].set_color('white')
    ax.spines['right'].set_color('white')
    ax.spines['left'].set_color('white')
    ax.spines['bottom'].set_color('white')

    ax.tick_params(axis='both', colors='cyan')  # Set tick colors to cyan
    ax.xaxis_date()
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%a %-m/%-d\n%-I:%M %p', tz=timezone('US/Central')))
    
    # Remove axis labels (but keep ticks and numbers)
    ax.set_xlabel("")  # Remove x-axis label
    ax.set_ylabel("")  # Remove y-axis label

    # Set grid
    ax.yaxis.grid(True, color='white', linestyle='--', linewidth=0.5)  # Add a white grid
    ax.xaxis.grid(True, color='white', linestyle='--', linewidth=0.5)  # Add a white grid

    # Rotate the x axis labels.
    # fig.autofmt_xdate()

    # Save the plot to a BytesIO object.
    buf = BytesIO()
    fig.savefig(buf, format='png')
    buf.seek(0)

    return buf


def parse_time_interval(string):
    # parse xd xh xm xs
    units = {'d': 86400, 'h': 3600, 'm': 60, 's': 1}

    total_seconds = 0
    current_number = ''
    for char in string:
        if char.isdigit():
            current_number += char
        else:
            if current_number:
                total_seconds += int(current_number) * units[char]
                current_number = ''

    return total_seconds    


class MessageStats(commands.Cog):
    def __init__(self, bot):
        self.bot: 'LunaBot' = bot 
    
    @commands.Cog.listener()
    async def on_message(self, msg: discord.Message):
        if not msg.guild:
            return 

        if msg.author.bot or msg.guild.id != self.bot.GUILD_ID:
            return 
        
        
        query = """INSERT INTO
                       message_data (user_id, channel_id)
                   VALUES
                       ($1, $2)
                """
        await self.bot.db.execute(query, msg.author.id, msg.channel.id)


    async def generate_data(self, start: datetime, end: datetime, tick, general_only):
        data = []
        current_time = start

        running_sum = 0
        async def get_interval_count(t1, t2):
            if general_only:
                query = 'SELECT COUNT(*) FROM message_data WHERE time >= $1 AND time < $2 AND channel_id != $3' 
                return await self.bot.db.fetchval(query, t1, t2, self.bot.vars.get("general-channel-id"))
            else:
                query = 'SELECT COUNT(*) FROM message_data WHERE time >= $1 AND time < $2' 
                return await self.bot.db.fetchval(query, t1, t2)

        while current_time < end:
            next_time = current_time + tick
            data.append((current_time + tick / 2, await get_interval_count(current_time, next_time)))
            current_time = next_time
            running_sum += data[-1][1]

        return data, running_sum
    
    # async def get_total_joins(self, start, end, guild_id):
    #     query = 'SELECT COUNT(*) FROM joins WHERE time BETWEEN $1 AND $2 AND guild_id = $3'
    #     total_joins = await self.bot.db.fetchval(query, start, end, guild_id)
    #     return total_joins
    
    # async def get_total_leaves(self, start, end, guild_id):
    #     query = 'SELECT COUNT(*) FROM leaves WHERE time BETWEEN $1 AND $2 AND guild_id = $3'
    #     total_leaves = await self.bot.db.fetchval(query, start, end, guild_id)
    #     return total_leaves

    async def generate_base_embed(self, data, n_msgs):
        embed = discord.Embed(
            title='Stats',
            color=0xcab7ff
        )
        # n_msgs = data[-1][1] - data[0][1]
        start = data[0][0]
        end = data[-1][0]

        embed.add_field(name='Start', value=discord.utils.format_dt(start, 'R'), inline=True)
        embed.add_field(name='End', value=discord.utils.format_dt(end, 'R'), inline=True)
        embed.add_field(name='Messages', value=n_msgs, inline=False)

        netpersecond = n_msgs / (end - start).total_seconds()
        netperweek = netpersecond * 604800
        netperday = netpersecond * 86400
        netperhour = netpersecond * 3600
        value = f'{netperhour:.2f} per hour\n{netperday:.2f} per day\n{netperweek:.2f} per week'
        embed.add_field(name='Net Rates', value=value, inline=False)

        embed.set_image(url='attachment://plot.png')

        return embed

    @commands.command()
    async def msgstats(self, ctx, *, flags: MsgStatsFlags):
        start = parse(flags.start, settings={'TIMEZONE': 'US/Central', 'RETURN_AS_TIMEZONE_AWARE': True})
        end = parse(flags.end, settings={'TIMEZONE': 'US/Central', 'RETURN_AS_TIMEZONE_AWARE': True})

        if end <= start:
            await ctx.send("End time must be after start time.")
            return
        
        if end > discord.utils.utcnow():
            end = discord.utils.utcnow()

        if flags.ticks:
            delta = timedelta(seconds=(end - start).total_seconds() / flags.ticks)
        elif flags.tick:
            delta = timedelta(seconds=parse_time_interval(flags.tick))

        data, n_msgs = await self.generate_data(start, end, delta, not flags.all_channels)
        buf = await asyncio.to_thread(plot_data_sync, data, "messages sent", "# of new messages")
        file = discord.File(buf, filename='plot.png')
        embed = await self.generate_base_embed(data, n_msgs)

        await ctx.send(file=file, embed=embed)



async def setup(bot):
    await bot.add_cog(MessageStats(bot))
