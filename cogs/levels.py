import time
import random
import datetime
import math
from io import BytesIO

from num2words import num2words

import discord
from discord import app_commands
from discord.ext import commands, tasks

from .utils import (
    generate_rank_card,
    next_sunday,
    SimplePages,
    Layout,
    LayoutContext,
)


def get_xp(lvl: int):
    return 50*lvl*lvl 

def get_level(xp: int):
    return int(math.sqrt(xp / 50))

class Levels(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.xp_cooldowns = {}
        self.main_guild_id = 899108709450543115
        self.leveled_roles = {
            1: 938858105473740840,
            5: 923096157645852693,
            10: 923096156324646922,
            15: 923096155460603984,
            20: 923096300696793128,
            25: 923096335039746048,
            30: 923096337841520721,
            40: 923096336436432996,
            50: 923096766805590026,
            75: 923096798078324756,
            100: 923096803958747187
        }
        self.whitelisted_channels = [
            899108709903532032,
            1202778473471680512,
            1191555710291554395,
            1191555765241131059,
            1191558551127199784,
            1191558039636025485,
            1191979119173447841,
            1191558432713625812,
            1193061987240910898,
        ]
        self.xp_multipliers = (
            (913086743035658292, 1.2),
            (1060750259980079195, 1.15),
            (981252193132884109, 1.1),
        )
        # self.xp_cache = {} 
        # self.bot.xp_cache = self.xp_cache
        # self.msg_counts = {}
        self.weekly_xp_task.start()
        self.cleanup_cooldowns.start()

    # make a loop that runs every sunday at 1am 
    async def weekly_xp(self, *, channel=None, reset=False):
        # await self.dump_xp()
        query = '''
                    SELECT xp.user_id, (xp.total_xp - xp_copy.total_xp) AS diff
                    FROM xp
                    INNER JOIN xp_copy ON xp.user_id = xp_copy.user_id
                    WHERE xp.user_id != $1 
                    ORDER BY diff DESC
                    LIMIT 3;
                '''
        rows = await self.bot.db.fetch(query, self.bot.vars.get('luna-id'))
    
        lb_layout = self.bot.get_layout('weeklylb')
        lb_repls = {}

        for i in range(3):
            row = rows[i]
            user_id = row['user_id']
            mention = f'<@{user_id}>'
            query = 'SELECT count FROM msg_count WHERE user_id = $1'
            msg_count = await self.bot.db.fetchval(query, row["user_id"])   
            xp = row['diff']

            lb_repls[f'mention{i+1}'] = mention
            lb_repls[f'xp{i+1}'] = xp
            lb_repls[f'messages{i+1}'] = msg_count
        
        this_sunday = discord.utils.utcnow()
        next_sunday = this_sunday + datetime.timedelta(days=7)

        reset_layout = self.bot.get_layout('weeklyreset')
        reset_repls = {
            'thissunday': discord.utils.format_dt(this_sunday, 'd'),
            'nextsunday': discord.utils.format_dt(next_sunday, 'd'),
        }

        if channel is None:
            channel = self.bot.get_var_channel('weekly-reset')

        await lb_layout.send(channel, repls=lb_repls)
        await reset_layout.send(channel, repls=reset_repls)

        if reset: 
            await self.reset_lb()

    @tasks.loop(hours=168)
    async def weekly_xp_task(self):
        await self.weekly_xp(reset=True)
        # select top 3 users order by the difference between xp and xp_copy 
            
    @weekly_xp_task.before_loop
    async def before_weekly_xp(self):
        await discord.utils.sleep_until(next_sunday())

    # async def cog_load(self):
    #     query = 'select user_id, total_xp from xp'
    #     rows = await self.bot.db.fetch(query)
        # for row in rows:
        #     self.xp_cache[row['user_id']] = row['total_xp']
        # rows = await self.bot.db.fetch('select user_id, count from msg_count')
        # for row in rows:
        #     self.msg_counts[row['user_id']] = row['count']

    @tasks.loop(minutes=10)  # Runs every 10 minutes; adjust as needed
    async def cleanup_cooldowns(self):
        """Task to clean up expired entries from xp_cooldowns."""
        current_time = time.time()
        # Remove entries where the cooldown time has passed
        self.xp_cooldowns = {user_id: cooldown for user_id, cooldown in self.xp_cooldowns.items() if cooldown > current_time}

    async def cog_unload(self):
        self.weekly_xp_task.cancel()
        self.cleanup_cooldowns.cancel()

    async def reset_lb(self):
        await self.bot.db.execute('DROP TABLE IF EXISTS xp_copy')
        # make a copy of the xp table
        await self.bot.db.execute('CREATE TABLE xp_copy AS SELECT * FROM xp')
        await self.bot.db.execute('DROP TABLE IF EXISTS msg_count')
        await self.bot.db.execute('CREATE TABLE msg_count (user_id BIGINT PRIMARY KEY, count INTEGER)')
        # self.msg_counts = {}

    async def add_leveled_roles(self, message, old_level, new_level):
        roles = {lvl: message.guild.get_role(self.leveled_roles[lvl]) for lvl in self.leveled_roles if lvl <= new_level}
        if roles:
            keys = list(roles.keys())
            lvl = max(keys)
            role = roles[lvl]
            keys.remove(lvl)

            if role not in message.author.roles:
                await message.author.add_roles(role)
            for lvl in keys:
                role = roles[lvl]
                if role in message.author.roles:
                    await message.author.remove_roles(role)

        if old_level != new_level:
            channel = self.bot.get_var_channel('levelup')
            layout = self.bot.get_layout('levelup')
            ctx = LayoutContext(author=message.author) 
            await layout.send(channel, ctx, repls={'level': new_level})

        self.xp_cooldowns[message.author.id] = time.time() + 15

    # async def get_xp_info(self, user):
    #     query = """SELECT (
    #                    SELECT COUNT(*)
    #                    FROM xp second
    #                    WHERE second.total_xp >= first.total_xp
    #                    AND second.user_id != $2
    #                ) AS rank, total_xp 
    #                FROM xp first
    #                WHERE user_id = $1
    #             """
    #     row = await self.bot.db.fetchrow(query, user.id, self.bot.vars.get('luna-id'))
    #     return row

    def get_increment(self, member):
        increment = random.randint(20, 25)

        # If it's a weekend, multiply by 1.2
        if datetime.datetime.today().weekday() in (5, 6):
            increment *= 1.2

        for role_id, multi in self.xp_multipliers:
            if member.guild.get_role(role_id) in member.roles:
                increment *= multi 

        return round(increment)

    @commands.Cog.listener()
    async def on_message(self, message):
        if not message.guild:
            return
        if message.guild.id != self.main_guild_id:
            return 

        if message.channel.id not in self.whitelisted_channels or message.author.bot:
            return 

        # self.msg_counts[message.author.id] = self.msg_counts.get(message.author.id, 0) + 1
        # count = self.msg_counts[message.author.id]

        query = '''INSERT INTO msg_count (user_id, count) 
                    VALUES ($1, $2)
                    ON CONFLICT (user_id)
                    DO UPDATE SET count = msg_count.count + $2
                '''
        await self.bot.db.execute(query, message.author.id, 1)

        if message.author.id not in self.xp_cooldowns or self.xp_cooldowns[message.author.id] < time.time():
            increment = self.get_increment(message.author)

            # old = self.xp_cache.get(message.author.id)
            # if old is None:
            #     self.xp_cache[message.author.id] = increment 
            #     new = increment
            #     old = 0
            # else:
            #     self.xp_cache[message.author.id] += increment
            #     new = old + increment 

            query = '''INSERT INTO xp (user_id, "total_xp") 
                        VALUES ($1, $2)
                        ON CONFLICT (user_id)
                        DO UPDATE SET total_xp = xp.total_xp + $2
                        RETURNING total_xp
                    '''
            new_xp = await self.bot.db.fetchval(query, message.author.id, increment) 
            old_xp = new_xp - increment

            new_level, old_level = get_level(new_xp), get_level(old_xp)
            await self.add_leveled_roles(message, old_level, new_level)

    @commands.hybrid_command(name='rank')
    @app_commands.describe(member='The member to check the rank of.')
    async def _rank(self, ctx, *, member: discord.Member = None):
        """Checks your server level and XP and other stats"""

        m = member if member else ctx.author

        async with ctx.channel.typing():

            # xp = self.xp_cache.get(m.id)
            # if xp is None:
            #     self.xp_cache[ctx.author.id] = 0
            #     xp = 0

            # xps_no_luna = [v for k, v in self.xp_cache.items() if k != self.bot.vars.get('luna-id')] 
            # rank = len([v for v in xps_no_luna if v > xp]) + 1

            query = "SELECT total_xp FROM xp WHERE user_id = $1"
            xp = await self.bot.db.fetchval(query, m.id)

            # Select all rows that have higher xp than the user
            query = "SELECT user_id FROM xp WHERE total_xp > $1 AND user_id != $2"
            rows = await self.bot.db.fetch(query, xp, self.bot.vars.get('luna-id'))

            rank = 1
            for row in rows:
                member = ctx.guild.get_member(row['user_id'])
                if member is not None:
                    rank += 1

            current_level = get_level(xp)

            empty = get_xp(current_level)
            full = get_xp(current_level+1)
            pc = (xp - empty) / (full - empty)

            av_file = BytesIO()
            await m.display_avatar.with_format('png').save(av_file)

            file = await self.bot.loop.run_in_executor(None, generate_rank_card, current_level, av_file, pc)

            layout = self.bot.get_layout('rankcommand')
            embed = layout.embeds[0].copy()
            embed.set_image(url='attachment://rank.gif')
            embed = await Layout.fill_embed(embed, {
                'ordinal': num2words(rank, to='ordinal_num'),
                'totalxp': xp,
                'neededxp': full - xp
            }, special=False)
            await ctx.send(embed=embed, file=discord.File(fp=file, filename='rank.gif'))

    @commands.command(aliases=['leaaderboard'])
    async def lb(self, ctx):
        """Shows the XP leaderboard."""

        # pairs_no_luna = [pair for pair in self.xp_cache.items() if pair[0] != self.bot.vars.get('luna-id')]
        # pairs = sorted(pairs_no_luna, key=lambda x: x[1], reverse=True)

        # Get pairs from db
        query = '''SELECT user_id, total_xp
                     FROM xp
                     WHERE user_id != $1
                     ORDER BY total_xp DESC
                 '''
        pairs = await self.bot.db.fetch(query, self.bot.vars.get('luna-id'))

        i = 0
        while i < len(pairs):
            pair = pairs[i]
            temp = ctx.guild.get_member(pair[0])
            if temp is None:
                pairs.pop(i)
            else:
                i += 1

        entries = []
        for user_id, total_xp in pairs:
            member = ctx.guild.get_member(user_id)
            lvl = get_level(total_xp)
            if member is not None:
                entries.append(f'{member.mention}\n**Level:** `{lvl}`\n**Total XP:** `{total_xp}`')

        embed = discord.Embed(title=f'XP Leaderboard', color=self.bot.DEFAULT_EMBED_COLOR)
        view = SimplePages(entries, ctx=ctx, embed=embed)
        await view.start() 

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def givexp(self, ctx, member: discord.Member, xp: int):
        # self.xp_cache[member.id] += xp
        query = """INSERT INTO
                       xp (user_id, "total_xp")
                   VALUES
                       ($1, $2)
                   ON CONFLICT (user_id) DO
                   UPDATE
                   SET
                       total_xp = xp.total_xp + $2
                """
        await self.bot.db.execute(query, member.id, xp)
        await ctx.send(f'Gave {xp} xp to {member.mention}.')

async def setup(bot):
    await bot.add_cog(Levels(bot))
