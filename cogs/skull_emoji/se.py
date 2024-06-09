from typing import Optional
from textwrap import dedent
from discord.ext import commands, tasks 
import discord 
import time 
import json 
import random 
from discord import ui 
import asyncio 
from lunascript import Layout, LunaScript
from se_charts import plot_data
from trivia import questions
from typing import Literal
from itertools import cycle
import dateparser
from datetime import datetime
from zoneinfo import ZoneInfo


# START_TIME = datetime(2023, 10, 15, 13).astimezone(ZoneInfo('US/Central'))
# OPTION3_TIME = 30 
# OPTION4_TIME = 30 
# OPTION5_TIME = 30 
# OPTION5_CD = 10 
# LOW_PERIOD = 5 
# HIGH_PERIOD = 10 
# INDIV_REDUCED_CD = 1 
# TEAM_REDUCED_CD = 1 
# BASE_CD = 3 
# INDIV_DOUBLE_TIME = 30 
# TEAM_DOUBLE_TIME = 30 
# INDIV_TRIPLE_TIME = 15 
# TEAM_TRIPLE_TIME = 15 
# INDIV_REDUCED_CD_TIME = 30 
# TEAM_REDUCED_CD_TIME = 30
# WELC_CD = 30 

START_TIME = datetime.fromtimestamp(1697461200) 
OPTION3_TIME = 30 * 60
OPTION4_TIME = 20 * 60
OPTION5_TIME = 25 * 60
OPTION5_CD = 60 
LOW_PERIOD = 500 
HIGH_PERIOD = 1000
INDIV_REDUCED_CD = 60
TEAM_REDUCED_CD = 120
BASE_CD = 180
INDIV_DOUBLE_TIME = 15 * 60
TEAM_DOUBLE_TIME = 5 * 60
INDIV_TRIPLE_TIME = 15 * 60
TEAM_TRIPLE_TIME = 5 * 60
INDIV_REDUCED_CD_TIME = 30 * 60
TEAM_REDUCED_CD_TIME = 30 * 60
WELC_CD = 5 * 60



class TeamStatsFlags(commands.FlagConverter):
    team: str = None 
    stat: str
    start: str = None
    end: str = 'now'


class RedeemView(ui.View):

    def __init__(self, ctx, choices, powerups):
        super().__init__(timeout=180)
        self.inter = None 
        self.custom_id = None 

        async def callback(inter):
            if inter.user != ctx.author:
                return await inter.response.defer()
            
            self.custom_id = inter.data['custom_id']
            self.inter = inter 
            self.stop()

        for i, choice in enumerate(choices):
            i += 1
            btn = ui.Button(label=str(i), custom_id=str(powerups.index(choice)), style=discord.ButtonStyle.blurple, row=i)
            btn.callback = callback
            self.add_item(btn)
        


class Powerup:
    def __init__(self, start, end):
        self.start = start
        self.end = end


class Multiplier(Powerup):
    def __init__(self, n, start, end):
        super().__init__(start, end)
        self.n = n 
        self.name = 'Multiplier'
        self.log_name = 'multi_powerup'
    

class CooldownReducer(Powerup):
    def __init__(self, cd, start, end):
        super().__init__(start, end)
        self.n = cd 
        self.name = 'Cooldown Reducer'
        self.log_name = 'cd_powerup'


class Team:
    def __init__(self, name, players, channel, redeems, saved_powerups):
        self.name = name 
        self.players = players 
        self.channel = channel

        for player in self.players:
            player.team = self

        self.captain = None 
        self.msg_count = 0
        self.redeems = redeems 
        self.saved_powerups = saved_powerups
        self.opp = None 
    
    def create_captain(self):
        self.captain = self.players[0]

    async def on_1000(self):
        self.redeems += 1
        query = 'update redeems set number = number + 1 where team = ?'
        await self.captain.bot.db.execute(query, self.name)
        args = {
            'messages': self.msg_count,
            'captainping': self.captain.member.mention,
        }

        # comment out later 
        # args.pop('captainping')

        layout = Layout.from_name(self.captain.bot, '1k_private')
        ls = LunaScript.from_layout(self.channel, layout, args=args)
        await ls.send()
    
    async def option1(self):
        points = random.randint(15, 20)
        await self.captain.add_points(points, 'topup_bonus')
        await self.captain.log_powerup('topup_powerup')
        return points
    
    async def option2(self):
        points = random.randint(10, 15)
        await self.opp.captain.remove_points(points, 'stolen')
        await self.captain.add_points(points, 'steal_bonus')
        await self.captain.log_powerup('steal_powerup')
        return points
    
    async def option3(self):
        for player in self.players:
            if player == self.captain:
                log = True 
            else: 
                log = False

            await player.apply_powerup(Multiplier(2, time.time(), time.time() + OPTION3_TIME), log=log)
        
    async def option4(self):
        for player in self.players:
            if player == self.captain:
                log = True 
            else: 
                log = False

            await player.apply_powerup(Multiplier(3, time.time(), time.time() + OPTION4_TIME), log=log)
    
    async def option5(self):
        for player in self.players:
            if player == self.captain:
                log = True 
            else: 
                log = False

            await player.apply_powerup(CooldownReducer(OPTION5_CD, time.time(), time.time() + OPTION5_TIME), log=log)


    @property 
    def total_points(self):
        return sum([player.points for player in self.players])


class Player:

    def __init__(self, bot, team, member, nick, points, msg_count, powerups):
        self.bot = bot 
        self.member = member 
        self.nick = nick 
        self.points = points 
        self.team = team 
        self.cds = [BASE_CD]
        self.multi = 1 
        self.powerups = powerups
        self.next_msg = 0
        self.next_welc = 0
        self.msg_count = msg_count

        self.apply_powerups()
    
    @property
    def cd(self):
        return min(self.cds)

    async def task(self, powerup):
        if isinstance(powerup, Multiplier):
            self.multi *= powerup.n
            await asyncio.sleep(powerup.end - time.time())
            self.multi //= powerup.n 
            self.powerups.remove(powerup)
        elif isinstance(powerup, CooldownReducer):
            self.cds.append(powerup.n)
            await asyncio.sleep(powerup.end - time.time())
            self.cds.remove(powerup.n)
            self.powerups.remove(powerup)

    async def log_powerup(self, name):
        query = 'insert into se_log (team, user_id, type, gain, time) values (?, ?, ?, ?, ?)'
        await self.bot.db.execute(query, self.team.name, self.member.id, name, 1, int(time.time()))

    async def apply_powerup(self, powerup, *, log=False):
        query = 'insert into powerups (user_id, name, value, start_time, end_time) values (?, ?, ?, ?, ?)'
        await self.bot.db.execute(query, self.member.id, powerup.name, powerup.n, powerup.start, powerup.end)
        self.bot.loop.create_task(self.task(powerup))
        if log:
            await self.log_powerup(powerup.log_name)

    def apply_powerups(self):
        for powerup in self.powerups:
            self.bot.loop.create_task(self.task(powerup))
            
    async def on_msg(self):
        await self.log_msg()
        if time.time() < self.next_msg:
            return 
        self.next_msg = time.time() + self.cd 
        await self.add_points(1, 'msg')
    
    async def on_welc(self, channel):
        if time.time() < self.next_welc:
            return
        self.next_welc = time.time() + WELC_CD 
        bonus = random.randint(1, 3)
        await self.add_points(bonus, 'welc_bonus')
        layout = Layout.from_name(self.bot, 'welc_bonus')
        args = {
            'points': bonus,
            'eventnick': self.nick,
            'teamname': self.team.name.capitalize(),
        }
        ls = LunaScript.from_layout(channel, layout, args=args)
        msg = await ls.send()
        await asyncio.sleep(10)
        await msg.delete()

    async def log_msg(self):
        self.msg_count += 1
        self.team.msg_count += 1
        # query = 'update se_stats set msgs = msgs + 1 where user_id = ?'
        # await self.bot.db.execute(query, self.member.id)
        query = 'insert into se_log (team, user_id, type, gain, time) values (?, ?, ?, ?, ?)'
        await self.bot.db.execute(query, self.team.name, self.member.id, 'all_msg', 1, int(time.time()))

    async def add_points(self, points, reason, multi=True):
        if multi:
            gain = points * self.multi
        else:
            gain = points

        self.points += gain

        query = 'insert into se_log (team, user_id, type, gain, time) values (?, ?, ?, ?, ?)'
        await self.bot.db.execute(query, self.team.name, self.member.id, reason, gain, int(time.time()))
        # query = 'update se_stats set points = points + ? where user_id = ?'
        # await self.bot.db.execute(query, gain, self.member.id)
    
    async def remove_points(self, points, reason):
        self.points -= points 
        query = 'insert into se_log (team, user_id, type, gain, time) values (?, ?, ?, ?, ?)'
        await self.bot.db.execute(query, self.team.name, self.member.id, reason, -points, int(time.time()))
        # query = 'update se_stats set points = points - ? where team = ?'
        # await self.bot.db.execute(query, points, self.member.id)
    
    async def on_500(self):
        await self.add_points(25, '500_bonus', multi=False)
        args = {
            'messages': self.msg_count,
        }
        layout = Layout.from_name(self.bot, '500_bonus')
        ls = LunaScript.from_layout(self.team.channel, layout, args=args, member=self.member)
        await ls.send()

    

class ServerEvent(commands.Cog):

    def __init__(self, bot):
        self.bot = bot 
        self.teams = {}
        self.players = {}
        self.guild_id = 899108709450543115
        self.general_id = 899108709903532032
        self.channel_ids = {1158930467337293905, 1158931468664446986, self.general_id}
        self.msgs_needed = random.randint(15, 35)
        self.db = None

        # comment out later
        # self.msgs_needed = 3
        # self.test = cycle([0, 1, 2, 3, 4])

        self.msg_counter = 0  

        self.has_welcomed = set() 
        
        self.powerups_1k = [
            'Receive 15-20 points',
            'Steal 10-15 points from the other team',
            'Double all incoming points for 30 minutes',
            'Triple all incoming points for 20 minutes',
            'Reduce the cooldown for messages to 1 minute for 25 minutes'
        ]
        self.powerups_chat = [
            'Trivia :: 1 - 5 points',
            'Steal-trivia :: steal 1 - 5 points',
            'Reduced Cooldown',
            'Double Point Multiplier',
            'Triple Point Multiplier'
        ]
        self.non_point_types = [
            'all_msg',
            'multi_powerup',
            'cd_powerup',
            '1k',
            'trivia_powerup',
            'steal_powerup',
            'topup_powerup'
        ]
    
    def generate_powerup(self):
        # comment out later 
        # return next(self.test)

        n = random.uniform(0, 1)
        if n < 0.5:
            return 0
        elif n < 0.75:
            return 1
        elif n < 0.85:
            return 2
        elif n < 0.95:
            return 3
        else:
            return 4

    async def cog_load(self):
        # from db import DB
        
        # db = DB(self.bot, 'se.sqlite')
        # await db.connect()
        # self.db = db 

        playerdict = {
            'bunny': [
                496225545529327616,
                675058943596298340,
                713118404017651773,
                915088419535863828,
                1098065917159690270,
                918620857901928458,
                816483116067192863,
                950526903926816769,
                697940393198616577
            ],
            'kitty': [
                687661271989878860,
                656526348856197139,
                1022880540677914714,
                376171072422281236,
                1059048815245668403,
                1132364499513524234,
                785037540155195424,
                718475543061987329,
                858960041628532737
            ] 
        }
        channels = {
            'bunny': 1158930467337293905,
            'kitty': 1158931468664446986
        }
        nicks = {
            496225545529327616: 'Luna',
            687661271989878860: 'Nemi',
            675058943596298340: 'Molly',
            713118404017651773: 'Lux',
            915088419535863828: 'Yura',
            1098065917159690270: 'Kayine',
            656526348856197139: 'Josh',
            1022880540677914714: 'Cedar',
            376171072422281236: 'Sharky',
            1059048815245668403: 'Kohi',
            918620857901928458: 'Roii',
            816483116067192863: 'Seabass',
            950526903926816769: 'Lay',
            1132364499513524234: 'Ada',
            785037540155195424: 'Fwogiie',
            718475543061987329: 'Storch',
            697940393198616577: 'Bunny',
            858960041628532737: 'Clozy'
        }

        # for team, members in playerdict.items():
        #     query = 'insert into se_stats (user_id, team, points, msgs) values (?, ?, 0, 0) on conflict (user_id) do nothing'
        #     for member in members:
        #         await self.bot.db.execute(query, member, team)
            
        # rows = await self.bot.db.fetch('select * from se_stats')
        self.guild = self.bot.get_guild(self.guild_id)

        for team_name, member_ids in playerdict.items():
            for member_id in member_ids: 
                member = self.guild.get_member(member_id)
                if member is None:
                    continue 
            
                if team_name not in self.teams:
                    query = 'insert into redeems (team, number) values (?, 0) on conflict (team) do nothing'
                    await self.bot.db.execute(query, team_name)
                    query = 'select number from redeems where team = ?'
                    redeems = await self.bot.db.fetchval(query, team_name)
                    query = 'select option from saved_powerups where team = ?'
                    saved_powerups = [row['option'] for row in await self.bot.db.fetch(query, team_name)]
                    self.teams[team_name] = Team(team_name, [], self.bot.get_channel(channels[team_name]), redeems, saved_powerups)
                
                query = 'select name, value, start_time, end_time from powerups where user_id = ? and end_time > ?'
                rows = await self.bot.db.fetch(query, member.id, time.time())
                powerups = []
                for row in rows:
                    if row['name'] == 'Multiplier':
                        powerups.append(Multiplier(row['value'], row['start_time'], row['end_time']))
                    elif row['name'] == 'Cooldown Reducer':
                        powerups.append(CooldownReducer(row['value'], row['start_time'], row['end_time']))

                placeholders = ','.join('?' for _ in self.non_point_types)
                query = f'select sum(gain) from se_log where type not in ({placeholders}) and user_id = ?' 
                points = await self.bot.db.fetchval(query, *self.non_point_types, member.id)
                if points is None:
                    points = 0
                query = 'select sum(gain) from se_log where type = ? and user_id = ?' 
                msgs = await self.bot.db.fetchval(query, 'all_msg', member.id)
                if msgs is None:
                    msgs = 0 

                team = self.teams[team_name]
                player = Player(self.bot, team, member, nicks[member.id], points, msgs, powerups)
                self.players[member.id] = player 
                team.players.append(player)
                team.msg_count += player.msg_count

        team1 = self.teams['bunny']
        team2 = self.teams['kitty']
        team1.create_captain()
        team2.create_captain()
        team1.opp = team2
        team2.opp = team1

        self.questions = questions 
        random.shuffle(self.questions)
        self.questions_i = 0


    async def cog_check(self, ctx):
        return ctx.author.id in self.players or ctx.author.id == 718475543061987329

    async def trivia(self, player, channel, steal=False):
        await player.log_powerup('trivia_powerup')

        q_tuple = self.questions[self.questions_i]
        q = q_tuple[0]
        a = q_tuple[1]
        if q == 'Who is Nemi??':
            choices = [
                "He is Luna's bf",
                "He is the other owner of this server",
                "He is an amazing person",
                a
            ]
        else:
            choices = q_tuple[2]()
            choices.append(a)
            random.shuffle(choices)
        
        if self.questions_i == len(self.questions) - 1:
            random.shuffle(self.questions)
            self.questions_i = 0
        else:
            self.questions_i += 1

        points = random.randint(1, 5) 
        args = {
            'question': q,
            'ans1': f'*{choices[0]}*',
            'ans2': f'*{choices[1]}*',
            'ans3': f'*{choices[2]}*',
            'ans4': f'*{choices[3]}*',
            'points': points,
            'eventnick': player.nick,
            'teamname': player.team.name.capitalize(),
        }
        if not steal:
            layout = Layout.from_name(self.bot, 'trivia')
        else:
            args['otherteamname'] = player.team.opp.name
            layout = Layout.from_name(self.bot, 'steal_trivia')

        ls = LunaScript.from_layout(channel, layout, args=args, member=player.member)
        msg = await ls.send()
        
        emojis = {
            '<:LC_alpha_A_NF2U:1113244739337207909>': 0,
            '<:LC_alpha_B_NF2U:1113244768235958402>': 1,
            '<:LC_alpha_C_NF2U:1113244841275568129>': 2,
            '<:LC_alpha_D_NF2U:1113244889224859660>': 3
        }

        for emoji in emojis:
            await msg.add_reaction(emoji)

        def check(r, u):
            return r.message == msg and u.id == player.member.id and str(r.emoji) in emojis
        
        try:
            reaction, user = await self.bot.wait_for('reaction_add', check=check, timeout=45)
        except asyncio.TimeoutError:
            layout = Layout.from_name(self.bot, 'trivia_timeout') 
            ls = LunaScript.from_layout(channel, layout)
            await ls.reply(msg)
            return

        if emojis[str(reaction.emoji)] == choices.index(a):
            if not steal:
                await player.add_points(points, 'trivia')
                await channel.send(f'You got the answer right! {player.nick} earned **{points}** points.')
            else:
                await player.team.opp.captain.remove_points(points, 'steal_trivia')
                await player.add_points(points, 'trivia')
                await channel.send(f'You got the answer right! {player.nick} stole **{points}** points from the other team.')
        else:
            await channel.send(f'{player.nick} got the answer wrong! The correct answer was **{a}**.', delete_after=10)

        await asyncio.sleep(10)
        await msg.delete()

    @commands.Cog.listener()
    async def on_member_join(self, member):
        self.has_welcomed = set()

    @commands.Cog.listener()
    async def on_message(self, msg):
        # comment out later
        # return 

        if msg.guild is None or msg.guild.id != self.guild_id:
            return 
        if msg.author.bot:
            return 
        if msg.author.id not in self.players:
            return 
        if msg.channel.id not in self.channel_ids:
            return
        if msg.channel.id != self.general_id:
            return 

        player = self.players[msg.author.id]
        await player.on_msg()

        if player.msg_count % LOW_PERIOD == 0:
            await player.on_500()
        
        if player.team.msg_count % HIGH_PERIOD == 0:
            await player.team.on_1000()

        if msg.author.id not in self.has_welcomed:
            if msg.content.lower().startswith('welc'):
                self.has_welcomed.add(msg.author.id)
                await player.on_welc(msg.channel)

        self.msg_counter += 1
        if self.msg_counter >= self.msgs_needed:
            self.msg_counter = 0 
            self.msgs_needed = random.randint(15, 35)
            
            #comment out later 
            # self.msgs_needed = 3

            if random.choice([True, False]):
                layout = Layout.from_name(self.bot, 'powerup_spawn')
                powerup_i = self.generate_powerup()
                powerup_name = self.powerups_chat[powerup_i]
                ls = LunaScript.from_layout(msg.channel, layout, args={'powerupname': powerup_name})
                spawn = await ls.send()
                await spawn.add_reaction('<a:LC_lilac_heart_NF2U_DNS:1046191564055138365>')

                def check(r, u):
                    return u.id in self.players and r.message == spawn and str(r.emoji) == '<a:LC_lilac_heart_NF2U_DNS:1046191564055138365>'

                try:
                    reaction, user = await self.bot.wait_for('reaction_add', check=check, timeout=60)
                except asyncio.TimeoutError:
                    await spawn.delete()
                    return 
                
                player = self.players[user.id]
                layout = None 

                if powerup_i == 0:
                    await player.log_powerup('1k')
                    await self.trivia(player, msg.channel)
                elif powerup_i == 1:
                    await self.trivia(player, msg.channel, steal=True)
                elif powerup_i == 2:
                    await player.apply_powerup(CooldownReducer(INDIV_REDUCED_CD, time.time(), time.time() + INDIV_REDUCED_CD_TIME), log=True)

                    for other in player.team.players:
                        if other != player:
                            await other.apply_powerup(CooldownReducer(TEAM_REDUCED_CD, time.time(), time.time() + TEAM_REDUCED_CD_TIME))

                    layout = Layout.from_name(self.bot, 'reduced_cd')
                elif powerup_i == 3:
                    await player.apply_powerup(Multiplier(2, time.time(), time.time() + INDIV_DOUBLE_TIME), log=True)

                    for other in player.team.players:
                        if other != player:
                            await other.apply_powerup(Multiplier(2, time.time(), time.time() + TEAM_DOUBLE_TIME))

                    layout = Layout.from_name(self.bot, 'double')
                else:
                    await player.apply_powerup(Multiplier(3, time.time(), time.time() + INDIV_TRIPLE_TIME), log=True)

                    for other in player.team.players:
                        if other != player:
                            await other.apply_powerup(Multiplier(3, time.time(), time.time() + TEAM_TRIPLE_TIME))

                    layout = Layout.from_name(self.bot, 'triple')

                if layout is not None:
                    args = {
                        'eventnick': player.nick,
                        'teamname': player.team.name.capitalize(),
                    }                    
                    ls = LunaScript.from_layout(msg.channel, layout, args=args, member=player.member)
                    await ls.send()

    @commands.command()
    async def redeem(self, ctx):
        # comment out later
        # team = self.players[ctx.author.id].team 
        
        for team in self.teams.values():
            if ctx.author == team.captain:
                break 
        else:
            return 
        
        if team.redeems == 0:
            return await ctx.send('You have no more powerups to redeem!')

        choices = random.sample(self.powerups_1k, 3)

        embed = discord.Embed(color=0xcab7ff, title='Redeem a Powerup') 
        for i, choice in enumerate(choices):
            embed.add_field(name=f'{i+1}', value=choice, inline=False)
         
        view = RedeemView(ctx, choices, self.powerups_1k)
        msg = await ctx.send(embed=embed, view=view)
        await view.wait()

        if view.inter is None:
            await msg.delete()
            return

        query = 'update redeems set number = number - 1 where team = ?'
        await self.bot.db.execute(query, team.name)
        team.redeems -= 1
        query = 'insert into saved_powerups (team, option, time) values (?, ?, ?)'
        await self.bot.db.execute(query, team.name, int(view.custom_id), int(time.time()))
        team.saved_powerups.append(int(view.custom_id))

        choice = self.powerups_1k[int(view.custom_id)]
        await view.inter.response.edit_message(content=f'**You have redeemed:**\n`{choice}`\n\nUse `!usepowerup` to use it anytime!', embed=None, view=None)
    
    @commands.command()
    async def usepowerup(self, ctx):
        for team in self.teams.values():
            if ctx.author == team.captain:
                break 
        else:
            return 

        # comment out later
        # team = self.players[ctx.author.id].team
        
        powerups = team.saved_powerups
        if len(powerups) == 0:
            return await ctx.send('You have no saved powerups!')
        
        embed = discord.Embed(color=0xcab7ff, title='Use a Powerup')
        for i, powerup_i in enumerate(powerups):
            embed.add_field(name=f'{i+1}', value=self.powerups_1k[powerup_i], inline=False)
        embed.set_footer(text='Type the number to use the powerup')

        temp = await ctx.send(embed=embed)

        def check(m):
            return m.author == ctx.author and m.channel == ctx.channel
        
        try:
            msg = await self.bot.wait_for('message', check=check, timeout=60)
        except asyncio.TimeoutError:
            await temp.delete()
            return
        
        if not msg.content.isdigit() or int(msg.content) > len(powerups) or int(msg.content) < 1:
            await ctx.send('That is not a valid number!', ephemeral=True)
            return
        
        powerup = powerups[int(msg.content) - 1]
        team.saved_powerups.remove(powerup)
        query = 'delete from saved_powerups where team = ? and option = ? limit 1'
        await self.bot.db.execute(query, team.name, powerup)

        if powerup == 0:
            n = await team.option1()
            await ctx.send(f'Your captain used a powerup that claimed **{n}** points for your team!')
        elif powerup == 1:
            n = await team.option2()
            await ctx.send(f'Your captain used a powerup that stole **{n}** points from the other team!')
        elif powerup == 2:
            await team.option3()
            await ctx.send('Your captain used a powerup that **doubled** all incoming points for __30 minutes__!')
        elif powerup == 3:
            await team.option4()
            await ctx.send('Your captain used a powerup that **tripled** all incoming points for __20 minutes__!')
        else:
            await team.option5()
            await ctx.send('Your captain used a powerup that **reduced the cooldown** for messages to __1 minute__ for __25 minutes__!')
    
    @commands.command()
    async def teampoints(self, ctx):
        embed = discord.Embed(title='Points for each team', color=0xcab7ff)
        for team in self.teams:
            embed.add_field(name=team.capitalize(), value=f'{self.teams[team].total_points:,}')
        await ctx.send(embed=embed)
    
    @commands.command()
    async def points(self, ctx):
        embed = discord.Embed(title='Points for each player', color=0xcab7ff)
        for team in self.teams:
            pointlst = []
            for player in self.teams[team].players:
                pointlst.append(f'**{player.nick}** - `{player.points:,}`')
            embed.add_field(name=f'Team {team.capitalize()}', value='\n'.join(pointlst))
        await ctx.send(embed=embed)
    
    @commands.command()
    async def pointslb(self, ctx):
        embed = discord.Embed(title='Points leaderboard', color=0xcab7ff)
        pointlst = []
        players = sorted(self.players.values(), key=lambda x: x.points, reverse=True)
        i = 1
        for player in players:
            pointlst.append(f'#{i}: **{player.nick}** - `{player.points:,}`')
            i += 1
        embed.description = '\n'.join(pointlst)
        await ctx.send(embed=embed)

    @commands.command(alises=['effects'])
    async def powerups(self, ctx, *, member: discord.Member = None):
        if member is None:
            member = ctx.author

        embed = discord.Embed(title='Active Powerups', color=0xcab7ff)
        for team in self.teams:
            poweruplst = []
            for player in self.teams[team].players:
                lst2 = [] 
                if len(player.powerups) == 0:
                    continue 
                for powerup in player.powerups:
                    end = discord.utils.format_dt(datetime.datetime.fromtimestamp(powerup.end), 'R')
                    if powerup.name == 'Multiplier':
                        lst2.append(f'{powerup.n}x multiplier, ends {end}')
                    else:
                        mins = round((powerup.end - time.time()) / 60)
                        lst2.append(f'{mins} min message CD, ends {end}')
                lst2 = '\n'.join(lst2)
                poweruplst.append(f'**{player.nick}**\n{lst2}')
            if len(poweruplst) == 0:
                continue 
            embed.add_field(name=f'Team {team.capitalize()}', value='\n\n'.join(poweruplst))
        await ctx.send(embed=embed)
    
    @commands.command()
    async def teamstats(self, ctx, *, flags: TeamStatsFlags):
        if flags.stat.lower() not in {
            'msgs', 'msg', 'message', 'messages', 
            'points', 'pts', 
            'powerup', 'powerups', 
            'bonuses', 'bonus', 
            'trivia', 
            'stolen', 'stole', 'steals', 
            'welc', 'welcs'
        }:
            return await ctx.send('That is not a valid option!')
        if flags.team is None:
            team = self.players[ctx.author.id].team
        elif flags.team.lower() == 'both':
            team = 'both'
        elif flags.team not in self.teams:
            return await ctx.send('That is not a valid team!')
        else:
            team = self.teams[flags.team]
        
        if flags.start is None:
            start = START_TIME
        else:
            start = dateparser.parse(flags.start)

        end = dateparser.parse(flags.end)

        def data_from_rows(rows_list):
            ret = []
            for team, rows in rows_list:
                data = []
                # find the initial msg count 
                count = 0 
                i = 0
                while i < len(rows):
                    row = rows[i]
                    if row['time'] > int(start.timestamp()):
                        break 
                    count += row['gain']
                    i += 1

                if i != 0:
                    data.append((row['time'], count))

                while i < len(rows):
                    row = rows[i]
                    if len(data) == 0:
                        prev_sum = 0 
                    else:
                        prev_sum = data[-1][1]

                    data.append((row['time'], prev_sum + row['gain']))
                    i += 1

                ret.append((team, data))

            return ret
        
        if team == 'both':
            teams = self.teams.values()
        else:
            teams = [team] 
        
        def key(x):
            if x.member.id not in player_stats:
                return 0
            return player_stats[x.member.id]

        if flags.stat in {'msg', 'messages', 'message', 'msgs'}:
            rows_list = []
            for team in teams:
                query = 'select time, gain from se_log where team = ? and type = ? and time < ? order by time asc'
                rows = await self.bot.db.fetch(query, team.name, 'all_msg', int(end.timestamp()))
                rows_list.append((team, rows))
            data = data_from_rows(rows_list)
            file = await plot_data(self.bot, data)

            embed = discord.Embed(title='Messages sent', color=0xcab7ff)
            for i, team in enumerate(teams):
                mvp = max(team.players, key=lambda x: x.msg_count)
                earliest = start.timestamp()
                latest = end.timestamp()

                val = dedent(f'''
                Total: **{team.msg_count:,}**
                Average per player: **{team.msg_count / len(team.players):.2f}**
                Team MVP: **{mvp.nick}** ({mvp.msg_count:,})
                Average per hour: **{team.msg_count / ((latest - earliest) / 3600):.2f}**
                Average per day: **{team.msg_count / ((latest - earliest) / 86400):.2f}**
                ''')
                embed.add_field(name=team.name.capitalize(), value=val)
                
            await ctx.send(embed=embed, file=file)

        elif flags.stat in {'points', 'pts'}:
            rows_list = []
            for team in teams:
                placeholders = ','.join('?' for _ in self.non_point_types)
                query = f'select gain, time from se_log where team = ? and type not in ({placeholders}) and time < ?'
                rows = await self.bot.db.fetch(query, team.name, *self.non_point_types, int(end.timestamp()))
                rows_list.append((team, rows))
            data = data_from_rows(rows_list)
            file = await plot_data(self.bot, data)
            embed = discord.Embed(title='Points earned', color=0xcab7ff)
            for i, team in enumerate(teams):
                mvp = max(team.players, key=lambda x: x.points)
                earliest = start.timestamp()
                latest = end.timestamp()

                points = team.total_points
                val = dedent(f'''
                Total: **{points:,}**
                Average per player: **{points / len(team.players):.2f}**
                Team MVP: **{mvp.nick}** ({mvp.points:,})
                Average per hour: **{points / ((latest - earliest) / 3600):.2f}**
                Average per day: **{points / ((latest - earliest) / 86400):.2f}**
                ''')
                embed.add_field(name=team.name.capitalize(), value=val)
            await ctx.send(embed=embed, file=file)
        
        elif flags.stat in {'powerup', 'powerups'}:
            rows_list = []
            types = [
                'topup_powerup',
                'steal_powerup',
                'trivia_powerup',
                'multi_powerup',
                'cd_powerup',
            ]
            placeholders = ','.join(['?']*len(types))
            stats = {}

            for team in teams:
                if team.name not in stats:
                    stats[team.name] = {}

                query = f'select user_id, count(user_id) as freq from se_log where team = ? and type IN ({placeholders}) and time < ? group by user_id order by freq desc limit 1'
                row = await self.bot.db.fetchrow(query, team.name, *types, int(end.timestamp()))
                stats['mvp'] = (self.players[row['user_id']], row['freq'])

                query = f'select user_id, gain, time from se_log where team = ? and type in ({placeholders}) and time < ?'
                rows = await self.bot.db.fetch(query, team.name, *types, int(end.timestamp()))
                stats[team.name]['powerups'] = len(rows)    
                rows_list.append((team, rows))

            data = data_from_rows(rows_list)
            file = await plot_data(self.bot, data)
            embed = discord.Embed(title='Powerups obtained', color=0xcab7ff)
            for i, team in enumerate(teams):
                mvp, count = stats[team.name]['mvp']
                powerups = stats[team.name]['powerups']
                earliest = start.timestamp()
                latest = end.timestamp()

                val = dedent(f'''
                Total: **{powerups:,}**
                Average per player: **{powerups / len(team.players):.2f}**
                Team MVP: **{mvp.nick}** ({count:,})
                Average per hour: **{powerups / ((latest - earliest) / 3600):.2f}**
                Average per day: **{powerups / ((latest - earliest) / 86400):.2f}**
                ''')
                embed.add_field(name=team.name.capitalize(), value=val)
            await ctx.send(embed=embed, file=file)
        
        elif flags.stat in {'bonus', 'bonuses'}:
            rows_list = []
            types = [
                'welc_bonus',
                '500_bonus',
                'topup_bonus',
                'steal_bonus'
            ]
            placeholders = ','.join(['?']*len(types))

            stats = {}
            player_stats = {}
    
            for team in teams:
                total = 0
                if team.name not in stats:
                    stats[team.name] = {}

                query = f'select user_id, gain, time from se_log where team = ? and type in ({placeholders}) and time < ?'
                rows = await self.bot.db.fetch(query, team.name, *types, int(end.timestamp()))

                for row in rows:
                    if row['user_id'] not in player_stats:
                        player_stats[row['user_id']] = 0
                    player_stats[row['user_id']] += row['gain']
                    total += row['gain']

                stats[team.name]['total'] = total    
                rows_list.append((team, rows))

            data = data_from_rows(rows_list)
            file = await plot_data(self.bot, data)
            embed = discord.Embed(title='Bonus points earned', color=0xcab7ff)
            for team in teams:
                mvp = max(team.players, key=key)
                count = player_stats.get(mvp.member.id, 0)
                total = stats[team.name]['total']
                earliest = start.timestamp()
                latest = end.timestamp()

                val = dedent(f'''
                Total: **{total:,}**
                Average per player: **{total / len(team.players):.2f}**
                Team MVP: **{mvp.nick}** ({count:,})
                Average per hour: **{total / ((latest - earliest) / 3600):.2f}**
                Average per day: **{total / ((latest - earliest) / 86400):.2f}**
                ''')
                embed.add_field(name=team.name.capitalize(), value=val)
            await ctx.send(embed=embed, file=file)
        
        elif flags.stat == 'trivia':
            rows_list = []
            stats = {}
            player_stats = {}
    
            for team in teams:
                total = 0
                if team.name not in stats:
                    stats[team.name] = {}

                query = 'select user_id, gain, time from se_log where team = ? and type = ? and time < ?'
                rows = await self.bot.db.fetch(query, team.name, 'trivia', int(end.timestamp()))

                for row in rows:
                    if row['user_id'] not in player_stats:
                        player_stats[row['user_id']] = 0
                    player_stats[row['user_id']] += row['gain']
                    total += row['gain']

                stats[team.name]['total'] = total    
                rows_list.append((team, rows))

            data = data_from_rows(rows_list)
            print(data)
            file = await plot_data(self.bot, data)
            embed = discord.Embed(title='Trivia points earned', color=0xcab7ff)
            for team in teams:
                mvp = max(team.players, key=key)
                count = player_stats.get(mvp.member.id, 0)
                total = stats[team.name]['total']
                earliest = start.timestamp()
                latest = end.timestamp()

                val = dedent(f'''
                Total: **{total:,}**
                Average per player: **{total / len(team.players):.2f}**
                Team MVP: **{mvp.nick}** ({count:,})
                Average per hour: **{total / ((latest - earliest) / 3600):.2f}**
                Average per day: **{total / ((latest - earliest) / 86400):.2f}**
                ''')
                embed.add_field(name=team.name.capitalize(), value=val)
            await ctx.send(embed=embed, file=file)
            
        elif flags.stat in {'stolen', 'stole', 'steals'}:
            rows_list = []
            stats = {}
            player_stats = {}
    
            for team in teams:
                total = 0
                if team.name not in stats:
                    stats[team.name] = {}

                query = 'select user_id, gain, time from se_log where team = ? and type in (?, ?) and time < ?'
                rows = await self.bot.db.fetch(query, team.name, 'stolen', 'steal_trivia', int(end.timestamp()))

                for row in rows:
                    if row['user_id'] not in player_stats:
                        player_stats[row['user_id']] = 0
                    player_stats[row['user_id']] -= row['gain']
                    total -= row['gain']

                stats[team.name]['total'] = total    
                rows_list.append((team, rows))

            data = data_from_rows(rows_list)
            file = await plot_data(self.bot, data)
            embed = discord.Embed(title='Points stolen', color=0xcab7ff)
            for team in teams:
                mvp = max(team.players, key=key)
                count = player_stats.get(mvp.member.id, 0)
                total = stats[team.name]['total']
                earliest = start.timestamp()
                latest = end.timestamp()

                val = dedent(f'''
                Total: **{total:,}**
                Average per player: **{total / len(team.players):.2f}**
                Team MVP: **{mvp.nick}** ({count:,})
                Average per hour: **{total / ((latest - earliest) / 3600):.2f}**
                Average per day: **{total / ((latest - earliest) / 86400):.2f}**
                ''')
                embed.add_field(name=team.name.capitalize(), value=val)
            await ctx.send(embed=embed, file=file)
        
        else:
            rows_list = []
            stats = {}
            player_stats = {}
    
            for team in teams:
                total = 0
                if team.name not in stats:
                    stats[team.name] = {}

                query = 'select user_id, gain, time from se_log where team = ? and type = ? and time < ?'
                rows = await self.bot.db.fetch(query, team.name, 'welc_bonus', int(end.timestamp()))

                for row in rows:
                    if row['user_id'] not in player_stats:
                        player_stats[row['user_id']] = 0
                    player_stats[row['user_id']] += row['gain']
                    total += row['gain']

                stats[team.name]['total'] = total    
                rows_list.append((team, rows))

            data = data_from_rows(rows_list)
            file = await plot_data(self.bot, data)
            embed = discord.Embed(title='Points from welcoming', color=0xcab7ff)
            for team in teams:
                mvp = max(team.players, key=key)
                count = player_stats.get(mvp.member.id, 0)
                total = stats[team.name]['total']
                earliest = start.timestamp()
                latest = end.timestamp()

                val = dedent(f'''
                Total: **{total:,}**
                Average per player: **{total / len(team.players):.2f}**
                Team MVP: **{mvp.nick}** ({count:,})
                Average per hour: **{total / ((latest - earliest) / 3600):.2f}**
                Average per day: **{total / ((latest - earliest) / 86400):.2f}**
                ''')
                embed.add_field(name=team.name.capitalize(), value=val)
            await ctx.send(embed=embed, file=file)
        
async def setup(bot):
    await bot.add_cog(ServerEvent(bot))

