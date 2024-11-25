from itertools import cycle
from datetime import datetime
from textwrap import dedent
import time 
import random 
import asyncio 

import discord 
from discord.ext import commands, tasks 
import dateparser

from .graphs import plot_data
from .trivia import parse_raw
from .constants import * 
from .player import Player 
from .team import Team
from .effects import (
    Powerup,
    Multiplier,
    CooldownReducer,
) 
from .views import RedeemView, TeamLBView
from cogs.utils import LayoutContext, View

from typing import Dict, Set, TYPE_CHECKING

if TYPE_CHECKING:
    from bot import LunaBot


class TeamStatsFlags(commands.FlagConverter):
    team: str = None 
    stat: str
    start: str = None
    end: str = 'now'


class ActivityEvent(commands.Cog):

    def __init__(self, bot):
        self.bot: "LunaBot" = bot 
        self.teams: Dict[str, Team] = {}
        self.players: Dict[int, Player] = {}
        self.channel_ids: Dict[int] = {1158930467337293905, 1158931468664446986, GENERAL_ID}

        if TEST:
            self.msgs_needed = 3
            self.powerups_cycle = cycle([0, 1, 2, 3, 4])
        else:
            self.msgs_needed = random.randint(15, 35)

        self.msg_counter = 0  

        self.has_welcomed: Set[int] = set() 
        
        self.powerups_1k = {
            "topup": "Receive 15-20 points",
            "steal": "Steal 10-15 points from the other team",
            "double": "Double all incoming points for 30 minutes",
            "triple": "Triple all incoming points for 20 minutes",
            "reduce_cd": "Reduce the cooldown for messages to 1 minute for 25 minutes"
        }
        self.powerup_names = [
            "trivia",
            "steal_trivia",
            "reduced_cd",
            "double",
            "triple",
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

        self.team_members = {
            "mistletoe": [
                496225545529327616,
                # add more
            ],
            "poinsettia": [
                718475543061987329,
                # add more
            ] 
        }
        self.team_channels = {
            "mistletoe": TEAM_MISTLETOE_CHANNEL_ID,
            "poinsettia": TEAM_POINSETTIA_CHANNEL_ID,
        }
        self.team_roles = {
            "mistletoe": 1216572143492403320,
            "poinsettia": 1216572111615692991,
        }
        self.team_emojis = {
            "mistletoe": "<:ML_Team_Mistletoe:1302156859909607496>",
            "poinsettia": "<:ML_Team_Poinsettia:1302156805639503892>",
        }
        self.nick_dict = {
            496225545529327616: 'Luna',
            718475543061987329: 'Storch',
            # add more
        }

        self.powerup_emoji = '<a:ML_present_gift:1302182895020150804>'

        self.last_msg_times: Dict[int, float] = {}

    def generate_powerup(self) -> int:
        if TEST:
            return next(self.powerups_cycle)

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

    async def create_tables(self):
        query = """CREATE TABLE IF NOT EXISTS num_redeems (
                       team TEXT PRIMARY KEY,
                       number INTEGER,
                       total INTEGER
                   );
                   
                   CREATE TABLE IF NOT EXISTS saved_powerups (
                       id SERIAL PRIMARY KEY,
                       team TEXT,
                       option TEXT,
                       time INTEGER
                   );
                   
                   CREATE TABLE IF NOT EXISTS event_stats (
                       user_id bigint PRIMARY KEY,
                       team text,
                       messages integer,
                       points integer
                   );
                   
                   CREATE TABLE IF NOT EXISTS event_log (
                       id serial PRIMARY KEY,
                       user_id bigint,
                       team text,
                       type text,
                       gain integer,
                       time integer
                   );
                   
                   CREATE TABLE IF NOT EXISTS powerups (
                       id SERIAL PRIMARY KEY,
                       user_id bigint,
                       name text,
                       value integer,
                       start_time integer,
                       end_time integer
                   );
                """
        await self.bot.db.execute(query)

        for team, member_ids in self.team_members.items():
            query = """INSERT INTO
                           event_stats (user_id, team, points, messages)
                       VALUES
                           ($1, $2, 0, 0)
                       ON CONFLICT (user_id) DO nothing
                    """
            for member_id in member_ids:
                await self.bot.db.execute(query, member_id, team)
            
        rows = await self.bot.db.fetch("SELECT * FROM event_stats")

    async def cog_load(self):

        self.guild = self.bot.get_guild(self.bot.GUILD_ID)

        await self.create_tables()

        for team_name, member_ids in self.team_members.items():
            if team_name not in self.teams:
                query = """INSERT INTO
                                num_redeems (team, number, total)
                            VALUES
                                ($1, 0, 0)
                            ON CONFLICT (team) DO nothing
                        """
                await self.bot.db.execute(query, team_name)
                query = """SELECT number FROM num_redeems WHERE team = $1"""
                redeems = await self.bot.db.fetchval(query, team_name)
                query = """SELECT option FROM saved_powerups WHERE team = $1"""

                saved_powerups = [row['option'] for row in await self.bot.db.fetch(query, team_name)]
                self.teams[team_name] = Team(
                    self.bot,
                    team_name,
                    self.team_emojis[team_name],
                    self.bot.get_channel(self.team_channels[team_name]),
                    self.guild.get_role(self.team_roles[team_name]),
                    redeems,
                    saved_powerups
                )

            for member_id in member_ids: 
                member = self.guild.get_member(member_id)
                if member is None:
                    continue 
                
                query = """SELECT
                               name,
                               value,
                               start_time,
                               end_time
                           FROM
                               powerups
                           WHERE
                               user_id = $1 
                               AND end_time > $2 
                        """

                rows = await self.bot.db.fetch(query, member.id, time.time())
                powerups = []
                for row in rows:
                    if row['name'] == 'multi_powerup':
                        powerups.append(Multiplier(row['value'], row['start_time'], row['end_time']))
                    elif row['name'] == 'cd_powerup':
                        powerups.append(CooldownReducer(row['value'], row['start_time'], row['end_time']))

                placeholders = ','.join(f'${i+2}' for i in range(len(self.non_point_types)))
                query = f"""SELECT
                               sum(gain)
                           FROM
                               event_log
                           WHERE
                               type NOT IN ({placeholders})
                               AND user_id = $1 
                        """ 
                points = await self.bot.db.fetchval(query, member.id, *self.non_point_types)
                if points is None:
                    points = 0

                query = """SELECT
                               sum(gain)
                           FROM
                               event_log
                           WHERE
                               type = $1 
                               AND user_id = $2
                        """ 
                msgs = await self.bot.db.fetchval(query, 'all_msg', member.id)
                if msgs is None:
                    msgs = 0 

                team = self.teams[team_name]
                player = Player(self.bot, team, member, self.nick_dict[member.id], points, msgs, powerups)
                self.players[member.id] = player 
                team.players.append(player)
                team.msg_count += player.msg_count

        self.teams["mistletoe"].create_captain()
        self.teams["poinsettia"].create_captain()
        self.teams["mistletoe"].opp = self.teams["poinsettia"]
        self.teams["poinsettia"].opp = self.teams["mistletoe"]

        self.questions = parse_raw()

        if not TEST:
            random.shuffle(self.questions)

        self.questions_i = 0

    async def cog_check(self, ctx):
        return ctx.author.id in self.players or ctx.author.id == 718475543061987329

    async def trivia(self, player: Player, channel: discord.TextChannel, steal: bool = False):
        await player.log_powerup('trivia_powerup')

        question = self.questions[self.questions_i]

        if self.questions_i == len(self.questions) - 1:
            random.shuffle(self.questions)
            self.questions_i = 0
        else:
            self.questions_i += 1
        
        question.shuffle_choices()

        points = random.randint(1, 5) 
        args = {
            'mention': player.member.mention,
            'team': player.team.name.capitalize(),
        } | question.get_main_layout_repls()

        if not steal:
            layout = self.bot.get_layout('ae/trivia/main')
        else:
            args['otherteam'] = player.team.opp.name
            layout = self.bot.get_layout('ae/stealtrivia/main')

        bot_msg = await layout.send(channel, repls=args) 

        emojis = [
            "<a:ML_red_flower:1308674651450511381>",
            "<a:ML_green_flower:1308674666897997857>",
            "<a:ML_white_flower:1308674682135773206>",
            "<a:ML_gold_flower:1308674704072245318>",
        ]

        for emoji in emojis:
            await bot_msg.add_reaction(emoji)

        def check(r, u):
            return r.message == bot_msg and u.id == player.member.id and str(r.emoji) in emojis
        
        try:
            reaction, user = await self.bot.wait_for('reaction_add', check=check, timeout=45)
        except asyncio.TimeoutError:
            layout = self.bot.get_layout('ae/trivia/timeout')
            await layout.send(bot_msg, reply=True)
            return

        if question.choices[emojis.index(str(reaction.emoji))] == question.answer:
            if not steal:
                await player.add_points(points, 'trivia')
                layout = self.bot.get_layout("ae/trivia/correct")
                await layout.send(channel, repls={"points": points})
            else:
                await player.team.opp.captain.remove_points(points, 'steal_trivia')
                await player.add_points(points, 'trivia')
                layout = self.bot.get_layout("ae/tealtrivia/correct")
                await layout.send(channel, repls={"points": points})
        else:
            layout = self.bot.get_layout("ae/trivia/incorrect")
            await layout.send(channel, repls=question.get_incorrect_layout_repls())

        await asyncio.sleep(10)
        await bot_msg.delete()
    
    def can_snowball_fight(self):
        """returns True if there are at least two active players on each team"""
        mistletoe = 0
        poinsettia = 0
        now = time.time()

        for player in self.players.values():
            if player.team.name == "mistletoe" and \
                (player.last_message_time - now) < 60:
                mistletoe += 1
            elif player.team.name == "poinsettia" and \
                (player.last_message_time - now) < 60:
                poinsettia += 1

        return mistletoe >= 2 and poinsettia >= 2
    
    async def snowball_fight(self, channel: discord.TextChannel):
        # whichever team spams the most snowballs in 15 seconds wins
        layout = self.bot.get_layout("ae/snowballfight")
        msg = await layout.send(channel)

        allowed_phrases = ["throw" "bonk" "🏐" "🪩" "⛄" "☃️" "❄️" "🧊" ]

        def check(m):
            return m.channel == channel and m.content.lower() in allowed_phrases
        
        num_mistletoe: Dict[int, int] = {}
        num_poinsettia: Dict[int, int] = {}

        end = time.time() + 15
        while time.time() < end:
            try:
                msg = await self.bot.wait_for('message', check=check, timeout=end - time.time())
            except asyncio.TimeoutError:
                continue

            if msg.author.id in self.players:
                await msg.delete()
                if self.players[msg.author.id].team.name == "mistletoe":
                    if msg.author.id not in num_mistletoe:
                        num_mistletoe[msg.author.id] = 1
                    else:
                        num_mistletoe[msg.author.id] += 1
                else:

                    if msg.author.id not in num_poinsettia:
                        num_poinsettia[msg.author.id] = 1
                    else:
                        num_poinsettia[msg.author.id] += 1

        def weighted_points(total_points: int, team: str) -> Dict[int, int]:
            # return a dict of player ids to points based on how many snowballs they threw
            # the ratio of snowballs thrown equals the ratio of points they get
            if team == "mistletoe":
                total = sum(num_mistletoe.values())
                return {k: round(v / total * total_points) for k, v in num_mistletoe.items()}
            else:
                total = sum(num_poinsettia.values())
                return {k: round(v / total * total_points) for k, v in num_poinsettia.items()}

        if sum(num_mistletoe.values()) == sum(num_poinsettia.values()):
            total_points = round(sum(num_mistletoe.values()) / 10)

            for member_id, points in weighted_points(total_points, "mistletoe").items():
                await self.players[member_id].add_points(points, 'snowball_fight')
            
            for member_id, points in weighted_points(total_points, "poinsettia").items():
                await self.players[member_id].add_points(points, 'snowball_fight')
        


    @commands.Cog.listener()
    async def on_member_join(self, member):
        self.has_welcomed = set()

    @commands.Cog.listener()
    async def on_message(self, msg: discord.Message):
        # comment out later
        # return 

        if msg.guild is None or msg.guild.id != self.bot.GUILD_ID:
            return 
        if msg.author.bot:
            return 
        if msg.author.id not in self.players:
            return 
        # if msg.channel.id not in self.channel_ids:
        #     return
        if msg.channel.id != GENERAL_ID:
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
        if self.msg_counter < self.msgs_needed:
            return

        self.msg_counter = 0 
        self.msgs_needed = random.randint(15, 35)
        
        #comment out later 
        # self.msgs_needed = 3

        if random.random() < 0.5:
            return

        if self.can_snowball_fight() and random.random() < 0.15:
            await self.snowball_fight(msg.channel)
            return

        powerup_i = self.generate_powerup()
        powerup_name = self.powerup_names[powerup_i]

        if powerup_name == "trivia":
            layout = self.bot.get_layout("ae/powerup/trivia")
        elif powerup_name == "steal_trivia":
            layout = self.bot.get_layout("ae/powerup/stealtrivia")
        else:
            layout = self.bot.get_layout("ae/powerup/random")

        spawn_msg = await layout.send(msg.channel)

        await spawn_msg.add_reaction(self.powerup_emoji)

        def check(r, u):
            return u.id in self.players and r.message == spawn_msg and str(r.emoji) == self.powerup_emoji

        try:
            reaction, user = await self.bot.wait_for('reaction_add', check=check, timeout=60)
        except asyncio.TimeoutError:
            await spawn_msg.delete()
            return 
        
        player = self.players[user.id]
        layout = None 

        if powerup_name == "trivia":
            # await player.log_powerup('1k')
            await self.trivia(player, msg.channel)
        elif powerup_name == "steal_trivia":
            await self.trivia(player, msg.channel, steal=True)
        elif powerup_name == "reduced_cd":
            await player.apply_powerup(CooldownReducer(INDIV_REDUCED_CD, time.time(), time.time() + INDIV_REDUCED_CD_TIME), log=True)

            for other in player.team.players:
                if other != player:
                    await other.apply_powerup(CooldownReducer(TEAM_REDUCED_CD, time.time(), time.time() + TEAM_REDUCED_CD_TIME))

            layout = self.bot.get_layout("ae/reducedcd")
        elif powerup_i == "double":
            await player.apply_powerup(Multiplier(2, time.time(), time.time() + INDIV_DOUBLE_TIME), log=True)

            for other in player.team.players:
                if other != player:
                    await other.apply_powerup(Multiplier(2, time.time(), time.time() + TEAM_DOUBLE_TIME))

            layout = self.bot.get_layout("ae/double")
        elif powerup_i == "triple":
            await player.apply_powerup(Multiplier(3, time.time(), time.time() + INDIV_TRIPLE_TIME), log=True)

            for other in player.team.players:
                if other != player:
                    await other.apply_powerup(Multiplier(3, time.time(), time.time() + TEAM_TRIPLE_TIME))

            layout = self.bot.get_layout("ae/triple")

        if layout is not None:
            repls = {
                'mention': player.member.mention,
                'team': player.team.name.capitalize(),
            }                    
            await layout.send(msg.channel, repls=repls)

    @commands.command()
    async def redeem(self, ctx):
        # comment out later
        # team = self.players[ctx.author.id].team 
        
        for team in self.teams.values():
            if ctx.author == team.captain.member:
                break 
        else:
            return 
        
        if team.redeems == 0:
            layout = self.bot.get_layout("ae/redeem/nopowerups")
            return await layout.send(ctx)

        query = "SELECT total FROM num_redeems WHERE team = $1"
        seed = 420 + 69 * await self.bot.db.fetchval(query, team.name)

        seeded_random = random.Random()
        seeded_random.seed(seed)
        choices = seeded_random.sample(list(self.powerups_1k.keys()), 3)

        # embed = discord.Embed(color=0xcab7ff, title='Redeem a Powerup') 
        # for i, choice in enumerate(choices):
        #     embed.add_field(name=f'{i+1}', value=self.powerups_1k[choice], inline=False)

        layout = self.bot.get_layout("ae/redeem")
        view = RedeemView(ctx, team, choices, self.powerups_1k)
        view.message = await layout.send(ctx, repls={
            f"powerup{i+1}": self.powerups_1k[choice]
            for i, choice in enumerate(choices)
        }, view=view)
        # view.message = await ctx.send(embed=embed, view=view)
    
    @commands.command()
    async def usepowerup(self, ctx):
        for team in self.teams.values():
            if ctx.author == team.captain.member:
                break 
        else:
            return 

        # comment out later
        # team = self.players[ctx.author.id].team
        
        powerups = team.saved_powerups
        if len(powerups) == 0:
            layout = self.bot.get_layout("ae/usepowerup/nopowerups")
            await layout.send(ctx)
            return
        
        powerups = [self.powerups_1k[name] for name in team.saved_powerups]
        layout = self.bot.get_layout("ae/usepowerup")
        temp = await layout.send(ctx, repls={"powerups": powerups}, jinja=True)

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
        
        powerup = team.saved_powerups.pop(int(msg.content) - 1)
        query = """WITH
                       P AS (
                           SELECT id
                           FROM saved_powerups
                           WHERE
                               team = $1
                               AND option = $2
                           LIMIT 1
                       )
                   DELETE FROM saved_powerups
                   WHERE
                       id = (
                           SELECT id
                           FROM P
                       )
                """
        await self.bot.db.execute(query, team.name, powerup)

        points = await team.apply_team_powerup(powerup)
        points = points if points is not None else ""
        layout = self.bot.get_layout(f"ae/usepowerup/{powerup}")
        await layout.send(ctx, repls={"points": points})
    
    @commands.command()
    async def teampoints(self, ctx):
        embed = discord.Embed(title='Points for each team', color=0xcab7ff)
        for team in self.teams:
            embed.add_field(name=team.capitalize(), value=f'{self.teams[team].total_points:,}')
        await ctx.send(embed=embed)
    
    @commands.command(aliases=["teamlb", "allpoints", "pointslb"])
    async def points(self, ctx):
        ok = False
        for team in self.teams.values():
            for player in team.players:
                if player.member == ctx.author:
                    ok = True
                    break 
            if ok:
                break
        if not ok:
            await ctx.send("You aren't on a team!")
            return
        
        view = TeamLBView(ctx, team)
        await view.update()
            
         


        # embed = discord.Embed(title='Points for each player', color=0xcab7ff)
        # for team in self.teams:
        #     pointlst = []
        #     for player in self.teams[team].players:
        #         pointlst.append(f'**{player.nick}** - `{player.points:,}`')
        #     embed.add_field(name=f'Team {team.capitalize()}', value='\n'.join(pointlst))
        # await ctx.send(embed=embed)
    
    # @commands.command()
    # async def pointslb(self, ctx):
    #     embed = discord.Embed(title='Points leaderboard', color=0xcab7ff)
    #     pointlst = []
    #     players = sorted(self.players.values(), key=lambda x: x.points, reverse=True)
    #     i = 1
    #     for player in players:
    #         pointlst.append(f'#{i}: **{player.nick}** - `{player.points:,}`')
    #         i += 1
    #     embed.description = '\n'.join(pointlst)
    #     await ctx.send(embed=embed)

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
        VALID_STATS = {
            'msgs', 'msg', 'message', 'messages',
            'points', 'pts',
            'powerup', 'powerups',
            'bonuses', 'bonus',
            'trivia',
            'stolen', 'stole', 'steals',
            'welc', 'welcs'
        }

        if flags.stat.lower() not in VALID_STATS:
            return await ctx.send('That is not a valid option!')

        team = self._get_team(ctx, flags)
        if team is None:
            return await ctx.send('That is not a valid team!')

        start = START_TIME if flags.start is None else dateparser.parse(flags.start)
        end = dateparser.parse(flags.end)

        if flags.stat in {'msg', 'messages', 'message', 'msgs'}:
            await self._process_stat(ctx, team, start, end, 'Messages sent', 'all_msg', lambda x: x.msg_count, lambda t: t.msg_count)
        elif flags.stat in {'points', 'pts'}:
            await self._process_stat(ctx, team, start, end, 'Points earned', None, lambda x: x.points, lambda t: t.total_points, exclude_types=self.non_point_types)
        elif flags.stat in {'powerup', 'powerups'}:
            await self._process_powerup(ctx, team, start, end, 'Powerups obtained')
        elif flags.stat in {'bonus', 'bonuses'}:
            await self._process_bonus(ctx, team, start, end, 'Bonus points earned', ['welc_bonus', '500_bonus', 'topup_bonus', 'steal_bonus'])
        elif flags.stat == 'trivia':
            await self._process_bonus(ctx, team, start, end, 'Trivia points earned', ['trivia'])
        elif flags.stat in {'stolen', 'stole', 'steals'}:
            await self._process_bonus(ctx, team, start, end, 'Points stolen', ['stolen', 'steal_trivia'])
        else:
            await self._process_bonus(ctx, team, start, end, 'Points from welcoming', ['welc_bonus'])

    def _get_team(self, ctx, flags):
        if flags.team is None:
            return self.players[ctx.author.id].team
        elif flags.team.lower() == 'both':
            return 'both'
        elif flags.team not in self.teams:
            return None
        else:
            return self.teams[flags.team]

    async def _process_stat(self, ctx, team, start, end, title, stat_type, player_key, team_key, exclude_types=None):
        rows_list = []
        for t in (self.teams.values() if team == 'both' else [team]):
            rows = await self._fetch_rows(t.name, stat_type, start, end, exclude_types)
            rows_list.append((t, rows))

        data = self._data_from_rows(rows_list, start)
        file = await plot_data(self.bot, data)
        embed = self._create_stat_embed(title, team, data, start, end, player_key, team_key)
        await ctx.send(embed=embed, file=file)

    async def _process_bonus(self, ctx, team, start, end, title, types):
        rows_list, stats, player_stats = [], {}, {}
        for t in (self.teams.values() if team == 'both' else [team]):
            rows, stats, player_stats = await self._process_rows(t, types, end, stats, player_stats)
            rows_list.append((t, rows))

        data = self._data_from_rows(rows_list, start)
        file = await plot_data(self.bot, data)
        embed = self._create_bonus_embed(title, team, stats, player_stats, start, end)
        await ctx.send(embed=embed, file=file)

    async def _fetch_rows(self, team, stat_type, start, end, exclude_types):
        if stat_type:
            query = """SELECT time, gain FROM event_log WHERE team = $1 AND type = $2 AND time < $3 ORDER BY time ASC"""
            return await self.bot.db.fetch(query, team, stat_type, int(end.timestamp()))
        else:
            placeholders = ','.join(f'${i+3}' for i in range(len(exclude_types)))
            query = f"""SELECT gain, time FROM event_log WHERE team = $1 AND time < $2 AND type NOT IN ({placeholders})"""
            return await self.bot.db.fetch(query, team, int(end.timestamp()), *exclude_types)

    async def _process_rows(self, team, types, end, stats, player_stats):
        if team.name not in stats:
            stats[team.name] = {}

        query = f"""SELECT user_id, gain, time FROM event_log WHERE team = $1 AND type IN ({','.join(f"${i+3}" for i in range(len(types)))}) AND time < $2"""
        rows = await self.bot.db.fetch(query, team.name, int(end.timestamp()), *types)

        total = 0
        for row in rows:
            if row['user_id'] not in player_stats:
                player_stats[row['user_id']] = 0
            player_stats[row['user_id']] += row['gain']
            total += row['gain']

        stats[team.name]['total'] = total
        return rows, stats, player_stats

    def _data_from_rows(self, rows_list, start):
        ret = []
        for team, rows in rows_list:
            data = []
            count, i = 0, 0
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
                prev_sum = data[-1][1] if data else 0
                data.append((row['time'], prev_sum + row['gain']))
                i += 1

            ret.append((team, data))
        return ret

    def _create_stat_embed(self, title, team, data, start, end, player_key, team_key):
        embed = discord.Embed(title=title, color=0xcab7ff)
        for t in (self.teams.values() if team == 'both' else [team]):
            mvp = max(t.players, key=player_key)
            total = team_key(t)
            val = self._generate_stat_val(mvp, total, start, end, len(t.players))
            embed.add_field(name=t.name.capitalize(), value=val)
        return embed

    def _create_bonus_embed(self, title, team, stats, player_stats, start, end):
        embed = discord.Embed(title=title, color=0xcab7ff)
        for t in (self.teams.values() if team == 'both' else [team]):
            mvp = max(t.players, key=lambda x: player_stats.get(x.member.id, 0))
            count = player_stats.get(mvp.member.id, 0)
            total = stats[t.name]['total']
            val = self._generate_stat_val(mvp, total, start, end, len(t.players))
            embed.add_field(name=t.name.capitalize(), value=val)
        return embed

    def _generate_stat_val(self, mvp, total, start, end, player_count):
        duration = (end.timestamp() - start.timestamp())
        return dedent(f'''
        Total: **{total:,}**
        Average per player: **{total / player_count:.2f}**
        Team MVP: **{mvp.nick}** ({total:,})
        Average per hour: **{total / (duration / 3600):.2f}**
        Average per day: **{total / (duration / 86400):.2f}**
        ''')


async def setup(bot):
    if LOAD:
        await bot.add_cog(ActivityEvent(bot))

