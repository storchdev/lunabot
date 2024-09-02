from discord.ext import commands, tasks
from zoneinfo import ZoneInfo
import json 
from num2words import num2words
from .utils import generate_rank_card, SimplePages, Layout, LayoutContext
from io import BytesIO
import time
import random
import discord
import datetime
import math
from .utils import next_sunday


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
        self.xp_multipliers = {
            913086743035658292: 1.2,
            1060750259980079195: 1.15,
            981252193132884109: 1.1
        }
        self.xp_cache = {} 
        self.bot.xp_cache = self.xp_cache
        self.msg_counts = {}
        self.weekly_xp_task.start()

    # make a loop that runs every sunday at 1am 
    async def weekly_xp(self):
        # await self.dump_xp()
        query = '''SELECT xp.user_id, (xp.total_xp - xp_copy.total_xp) AS diff
                    FROM xp
                    INNER JOIN xp_copy ON xp.user_id = xp_copy.user_id
                    WHERE xp.user_id != $1 
                    ORDER BY diff DESC
                    LIMIT 3;
                '''
        rows = await self.bot.db.fetch(query, self.bot.vars.get('luna-id'))
    
        # TODO: make this a layout
        with open('cogs/static/embeds.json', encoding='utf8') as f:
            data = json.load(f)
        
        embed = discord.Embed.from_dict(data['weekly_lb'])

        for i in range(3):
            try:
                msgs = self.msg_counts[rows[i][0]]
            except KeyError:
                msgs = 'placeholder'
            embed.description = embed.description.replace(f'{{ping{i}}}', f'<@{rows[i][0]}>')
            embed.description = embed.description.replace(f'{{xp{i}}}', f'{rows[i][1]}')
            embed.description = embed.description.replace(f'{{msgs{i}}}', f'{msgs}')
        
        embed2 = discord.Embed.from_dict(data['weekly_reset'])
        this_sunday = discord.utils.utcnow()
        next_sunday = this_sunday + datetime.timedelta(days=7)
        embed2.description = embed2.description.replace('{this_sunday}', discord.utils.format_dt(this_sunday, 'd'))
        embed2.description = embed2.description.replace('{next_sunday}', discord.utils.format_dt(next_sunday, 'd'))

        channel = self.bot.get_channel(1137942143562940436)
        await channel.send(embed=embed)
        await channel.send(embed=embed2)
        
        await self.freeze_lb()

    @tasks.loop(hours=168)
    async def weekly_xp_task(self):
        await self.weekly_xp()
        # select top 3 users order by the difference between xp and xp_copy 
            
    @weekly_xp_task.before_loop
    async def before_weekly_xp(self):
        await discord.utils.sleep_until(next_sunday())

    async def cog_load(self):
        query = 'select user_id, total_xp from xp'
        rows = await self.bot.db.fetch(query)
        for row in rows:
            self.xp_cache[row['user_id']] = row['total_xp']
        rows = await self.bot.db.fetch('select user_id, count from msg_count')
        for row in rows:
            self.msg_counts[row['user_id']] = row['count']

    # async def dump_xp(self):
    #     for user_id, total_xp in self.xp_cache.items():
    #         query = '''INSERT INTO xp (user_id, "total_xp") 
    #                     VALUES ($1, $2)
    #                     ON CONFLICT (user_id)
    #                     DO UPDATE SET total_xp = $2
    #                 '''
    #         await self.bot.db.execute(query, user_id, total_xp) 
        
    # async def dump_msg_counts(self):
    #     for user_id, count in self.msg_counts.items():
    #         query = '''INSERT INTO msg_count (user_id, count) 
    #                     VALUES ($1, $2)
    #                     ON CONFLICT (user_id)
    #                     DO UPDATE SET count = $2
    #                 '''
    #         await self.bot.db.execute(query, user_id, count)

    async def cog_unload(self):
        self.weekly_xp_task.cancel()
        # await self.dump_xp()
        # await self.dump_msg_counts()
    
    async def freeze_lb(self):
        await self.bot.db.execute('DROP TABLE IF EXISTS xp_copy')
        # make a copy of the xp table
        await self.bot.db.execute('CREATE TABLE xp_copy AS SELECT * FROM xp')
        await self.bot.db.execute('DROP TABLE IF EXISTS msg_count')
        await self.bot.db.execute('CREATE TABLE msg_count (user_id BIGINT PRIMARY KEY, count INTEGER)')
        self.msg_counts = {}

    async def add_leveled_roles(self, message, old_level, new_level, authorroles):
        roles = {lvl: self.leveled_roles[lvl] for lvl in self.leveled_roles if lvl <= new_level}
        if roles:
            keys = list(roles.keys())
            lvl = max(keys)
            role = roles[lvl]
            keys.remove(lvl)
            if role not in authorroles:
                role = message.guild.get_role(role)
                await message.author.add_roles(role)
            for lvl in keys:
                role = roles[lvl]
                if role in authorroles:
                    role = message.guild.get_role(role)
                    await message.author.remove_roles(role)

        if old_level != new_level:
            # embed = discord.Embed(title='❀ㆍㆍLevel Up﹗⁺ ₍ <a:LC_lilac_heart_NF2U_DNS:1046191564055138365> ₎', color=0xcab7ff)
            # embed.description = f'> ♡﹒﹒**Psst!** Tysm for being active here with us, you are now level {new_level}. Keep sending messages to gain more levels, which can gain you some **epic perks**. Tired of receiving these level up messages?? Go [here](https://discord.com/channels/899108709450543115/1106225161562230925) to remove access to this channel; just react to that message again to regain access. <a:LC_star_burst:1147790893064142989> ✿❀'
            # embed.set_footer(text='⁺﹒Type ".myperks" to view our full list of available perks, including perks for our active members﹒⁺')
            # channel = self.bot.get_channel(1137942143562940436)
            # await channel.send(f'⁺﹒{message.author.mention}﹗𖹭﹒⁺', embed=embed)
            channel = self.bot.get_var_channel('levelup')
            layout = self.bot.get_layout('levelup')
            ctx = LayoutContext(author=message.author) 
            await layout.send(channel, ctx, repls={'level': new_level})

        self.xp_cooldowns[message.author.id] = time.time() + 15

    async def get_xp_info(self, user):
        query = """SELECT (
                       SELECT COUNT(*)
                       FROM xp second
                       WHERE second.total_xp >= first.total_xp
                   ) AS rank, total_xp 
                   FROM xp first
                   WHERE user_id = $1
                """
        res = await self.bot.db.fetchrow(query, user.id)
        return res

    @commands.Cog.listener()
    async def on_message(self, message):
        if not message.guild:
            return
        if message.guild.id != self.main_guild_id:
            return 

        if message.channel.id not in self.whitelisted_channels or message.author.bot:
            return 

        self.msg_counts[message.author.id] = self.msg_counts.get(message.author.id, 0) + 1
        count = self.msg_counts[message.author.id]

        query = '''INSERT INTO msg_count (user_id, count) 
                    VALUES ($1, $2)
                    ON CONFLICT (user_id)
                    DO UPDATE SET count = $2
                '''
        await self.bot.db.execute(query, message.author.id, count)

        if message.author.id not in self.xp_cooldowns or self.xp_cooldowns[message.author.id] < time.time():
            authorroles = [role.id for role in message.author.roles]
            increment = random.randint(20, 25)
            for role_id, multi in self.xp_multipliers.items():
                if role_id in authorroles:
                    increment *= multi 
            increment = round(increment)
            old = self.xp_cache.get(message.author.id)
            if old is None:
                self.xp_cache[message.author.id] = increment 
                new = increment
                old = 0
            else:
                self.xp_cache[message.author.id] += increment
                new = old + increment 

            query = '''INSERT INTO xp (user_id, "total_xp") 
                        VALUES ($1, $2)
                        ON CONFLICT (user_id)
                        DO UPDATE SET total_xp = $2
                    '''
            await self.bot.db.execute(query, message.author.id, new) 

            new_level, old_level = get_level(new), get_level(old)
            await self.add_leveled_roles(message, old_level, new_level, authorroles)

    @commands.hybrid_command(name='rank')
    async def _rank(self, ctx, *, member: discord.Member = None):
        """Checks your server level and XP and other stats"""

        m = member if member else ctx.author

        async with ctx.channel.typing():

            xp = self.xp_cache.get(m.id)
            if xp is None:
                self.xp_cache[ctx.author.id] = 0
                xp = 0

            xps_no_luna = [v for k, v in self.xp_cache.items() if k != self.bot.vars.get('luna-id')] 
            rank = len([v for v in xps_no_luna if v > xp]) + 1
            mx = xp
            current_level = get_level(mx)

            empty = get_xp(current_level)
            full = get_xp(current_level+1)
            pc = (mx - empty) / (full - empty)

            av_file = BytesIO()
            await m.display_avatar.with_format('png').save(av_file)

            file = await self.bot.loop.run_in_executor(None, generate_rank_card, current_level, av_file, pc)

            layout = self.bot.get_layout('rankcommand')
            embed = layout.embeds[0].copy()
            embed.set_image(url='attachment://rank.gif')
            embed = Layout.fill_embed(embed, {
                'ordinal': num2words(rank, to='ordinal_num'),
                'totalxp': xp,
                'neededxp': full - mx
            }, special=False)
            await ctx.send(embed=embed, file=discord.File(fp=file, filename='rank.gif'))

#             embed = discord.Embed(title='❀ㆍㆍYour Rank﹗⁺ ₍ <a:LCD_flower_spin:1147757953064128512> ₎', color=0xcab7ff)
#             embed.description = (f'''
# > ⁺ <a:Lumi_arrow_R:927733713163403344>﹒__Rank__ :: {num2words(rank, to='ordinal_num')}﹒⁺
# > ⁺ <a:Lumi_arrow_R:927733713163403344>﹒__XP__ :: {xp}﹒⁺
# > ⁺ <a:Lumi_arrow_R:927733713163403344>﹒__Needed XP__ :: {full - mx}﹒⁺
#             ''')
#             embed.set_footer(text='⁺﹒Type ".myperks" to view our full list of available perks, including perks for our active members﹒⁺')
#             total = t2 - t1 
#             await ctx.send(f'Render time: `{round(total, 3)}s`', embed=embed, file=discord.File(fp=file, filename='rank.gif'))


    @commands.command(aliases=['leaaderboard'])
    async def lb(self, ctx):
        """Shows the XP leaderboard."""

        pairs_no_luna = [pair for pair in self.xp_cache.items() if pair[0] != self.bot.vars.get('luna-id')]
        pairs = sorted(pairs_no_luna, key=lambda x: x[1], reverse=True)

        i = 0
        while i < len(pairs):
            pair = pairs[i]
            temp = ctx.guild.get_member(pair[0])
            if temp is None:
                pairs.pop(i)
            else:
                i += 1

        entries = []
        for row in pairs:
            member, xp = ctx.guild.get_member(row[0]), row[1]
            lvl = get_level(xp)
            if member is not None:
                entries.append(f'{member.mention}\n**Level:** `{lvl}`\n**Total XP:** `{xp}`')

        embed = discord.Embed(title=f'XP Leaderboard', color=self.bot.DEFAULT_EMBED_COLOR)
        view = SimplePages(entries, ctx=ctx, embed=embed)
        await view.start() 

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def givexp(self, ctx, member: discord.Member, xp: int):
        self.xp_cache[member.id] += xp
        query = '''INSERT INTO xp (user_id, "total_xp") 
                    VALUES ($1, $2)
                    ON CONFLICT (user_id)
                    DO UPDATE SET total_xp = $2
                '''
        await self.bot.db.execute(query, member.id, self.xp_cache[member.id])
        await ctx.send(f'Gave {xp} xp to {member.mention}.')

async def setup(bot):
    await bot.add_cog(Levels(bot))
