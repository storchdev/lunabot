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


class StatsFlags(commands.FlagConverter):
    stat: str = "net"
    start: str = "1 week ago"
    end: str = "now"    
    tick: str = None
    ticks: int = 21
    


def plot_data_sync(data, stat, start, end, tick):
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

    for time, value in data[stat]:
        x_values.append(time)
        y_values.append(value)

    # Create the plot.
    fig = plt.figure(figsize=(8, 5))
    fig.set_facecolor('#36393f')  # Set figure background color
    ax = fig.add_subplot(1, 1, 1)
    ax.set_facecolor('#36393f')  # Set axes background color

    colors = {
        'joins': '#59ff91',
        'leaves': '#f55858',
        'net': 'yellow'
    }

    # Plot the data
    ax.plot(x_values, y_values, color=colors[stat], marker='o')  # Use colors for the line and markers

    # Set title and labels
    ax.set_title(f"{stat.capitalize()} Rate Over Time", color='cyan')
    ax.set_xlabel("Time", color='cyan')
    ax.set_ylabel("Rate", color='cyan')

    # Customize the axes
    ax.spines['top'].set_color('white')
    ax.spines['right'].set_color('white')
    ax.spines['left'].set_color('white')
    ax.spines['bottom'].set_color('white')

    ax.tick_params(axis='both', colors='cyan')  # Set tick colors to cyan
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%m/%d\n%H:%M', tz=timezone('US/Central')))
    
    # Remove axis labels (but keep ticks and numbers)
    ax.set_xlabel("")  # Remove x-axis label
    ax.set_ylabel("")  # Remove y-axis label

    # Set grid
    ax.yaxis.grid(True, color='white', linestyle='--', linewidth=0.5)  # Add a white grid
    ax.xaxis.grid(True, color='white', linestyle='--', linewidth=0.5)  # Add a white grid

    # Rotate the x axis labels.
    fig.autofmt_xdate()

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


class Stats(commands.Cog):
    def __init__(self, bot):
        self.bot: 'LunaBot' = bot

    @commands.Cog.listener()
    async def on_member_join(self, member):
        """
        Event listener for when a member joins the server.
        Inserts the join event into the joins table.
        """
        # Increment member count if needed, based on your logic
        member_count = member.guild.member_count

        # Insert data into the joins table
        await self.bot.db.execute(
            'INSERT INTO joins (user_id, guild_id, member_count, time) VALUES ($1, $2, $3, $4)',
            member.id, member.guild.id, member_count, discord.utils.utcnow()
        )
    
    @commands.Cog.listener()
    async def on_member_remove(self, member):
        """
        Event listener for when a member leaves the server.
        Inserts the leave event into the leaves table.
        """
        # Increment member count if needed, based on your logic
        member_count = member.guild.member_count

        # Insert data into the leaves table
        await self.bot.db.execute(
            'INSERT INTO leaves (user_id, guild_id, member_count, time) VALUES ($1, $2, $3, $4)',
            member.id, member.guild.id, member_count, discord.utils.utcnow()
        )

    async def generate_data_points(self, start, end, tick):
        """
        Generate data points for the plot by querying the database.
        :param start: Start time for the data range.
        :param end: End time for the data range.
        :param tick: Time delta for each point.
        :return: A dictionary containing join and leave data points.
        """
        data = {'joins': [], 'leaves': [], 'net': []}

        current_time = start

        while current_time < end:
            next_time = current_time + tick
            join_count = await self.bot.db.fetchval(
                'SELECT COUNT(*) FROM joins WHERE time >= $1 AND time < $2', 
                current_time, next_time
            )
            leave_count = await self.bot.db.fetchval(
                'SELECT COUNT(*) FROM leaves WHERE time >= $1 AND time < $2', 
                current_time, next_time
            )
            
            data['joins'].append((current_time + tick / 2, join_count))
            data['leaves'].append((current_time + tick / 2, leave_count))
            data['net'].append((current_time + tick / 2, join_count - leave_count))

            current_time = next_time

        return data

    @commands.command()
    async def stats(self, ctx, *, flags: StatsFlags):
        stat = flags.stat
        start = parse(flags.start)
        end = parse(flags.end)

        if end <= start:
            await ctx.send("End time must be after start time.")
            return
        
        if end > datetime.now():
            end = datetime.now()
        
        tick = flags.tick
        ticks = flags.ticks

        if tick is None:
            tick = (end - start).total_seconds() / ticks
        else:
            tick = parse_time_interval(tick)

        #  GENERATE DATA POINTS FOR THE PLOT BY QUERYING THE DATABASE
        tick = timedelta(seconds=tick)
        data = await self.generate_data_points(start, end, tick)
        buf = await asyncio.to_thread(plot_data_sync, data, stat, start, end, tick)
        await ctx.send(file=discord.File(buf, filename='plot.png'))


    # @commands.command()
    # async def absstats(self, ctx, *, flags: StatsFlags):
    @commands.command(name="fakedata")
    @staff_only()
    async def insert_fake_data(self, ctx):
        """
        Inserts fake join and leave data into the database.
        Joins occur every 60-6000 seconds.
        Leaves occur every 60-3000 seconds.
        Data spans from one week ago until now.
        """
        guild = ctx.guild
        guild_id = guild.id
        start_time = discord.utils.utcnow() - timedelta(weeks=1)
        end_time = discord.utils.utcnow()

        # Parameters for joins and leaves
        join_min_delta = 60      # seconds
        join_max_delta = 6000    # seconds
        leave_min_delta = 60     # seconds
        leave_max_delta = 3000   # seconds

        # Initialize member count
        initial_member_count = guild.member_count if guild.member_count > 0 else 100
        member_count = initial_member_count

        # Generate join events
        join_events = []
        current_time_join = start_time
        while current_time_join < end_time:
            delta_seconds = random.randint(join_min_delta, join_max_delta)
            current_time_join += timedelta(seconds=delta_seconds)
            if current_time_join > end_time:
                break
            user_id = random.randint(100000000000000000, 999999999999999999)  # Fake user ID
            join_events.append({
                'time': current_time_join,
                'user_id': user_id
            })

        # Generate leave events
        leave_events = []
        current_time_leave = start_time
        while current_time_leave < end_time:
            delta_seconds = random.randint(leave_min_delta, leave_max_delta)
            current_time_leave += timedelta(seconds=delta_seconds)
            if current_time_leave > end_time:
                break
            user_id = random.randint(100000000000000000, 999999999999999999)  # Fake user ID
            leave_events.append({
                'time': current_time_leave,
                'user_id': user_id
            })

        # Merge and sort events
        all_events = []
        for event in join_events:
            all_events.append({
                'type': 'join',
                'time': event['time'],
                'user_id': event['user_id']
            })
        for event in leave_events:
            all_events.append({
                'type': 'leave',
                'time': event['time'],
                'user_id': event['user_id']
            })
        # Sort events by time
        all_events.sort(key=lambda x: x['time'])

        # Prepare lists for database insertion
        joins_to_insert = []
        leaves_to_insert = []

        # Simulate member count over time
        for event in all_events:
            event_time = event['time']
            user_id = event['user_id']
            if event['type'] == 'join':
                member_count += 1
                joins_to_insert.append(
                    (user_id, guild_id, member_count, event_time)
                )
            elif event['type'] == 'leave':
                member_count = max(member_count - 1, 0)
                leaves_to_insert.append(
                    (user_id, guild_id, member_count, event_time)
                )

        # Insert data into the database
        try:
            async with self.bot.db.acquire() as connection:
                async with connection.transaction():
                    if joins_to_insert:
                        await connection.executemany(
                            'INSERT INTO joins (user_id, guild_id, member_count, time) VALUES ($1, $2, $3, $4)',
                            joins_to_insert
                        )
                    if leaves_to_insert:
                        await connection.executemany(
                            'INSERT INTO leaves (user_id, guild_id, member_count, time) VALUES ($1, $2, $3, $4)',
                            leaves_to_insert
                        )
        except Exception as e:
            await ctx.send(f"An error occurred while inserting fake data: {e}")
            return

        # Provide feedback to the user
        num_joins = len(joins_to_insert)
        num_leaves = len(leaves_to_insert)
        await ctx.send(f"Successfully inserted {num_joins} fake join events and {num_leaves} fake leave events.")


async def setup(bot):
    await bot.add_cog(Stats(bot))
