import asyncio
import logging
import random
import time
from datetime import datetime
from itertools import cycle
from typing import TYPE_CHECKING, Dict, List, Set
from zoneinfo import ZoneInfo

import dateparser
import discord
from discord.ext import commands, tasks

from cogs.utils import Layout, next_day
from cogs.utils.errors import ActivityEventBreak
from cogs.utils.time_stuff import localnow

from .constants import *
from .effects import (
    CooldownReducer,
    Multiplier,
)
from .graphs import plot_data
from .player import Player
from .team import Team
from .trivia import parse_raw
from .views import DailyTasksView, RedeemView, TeamLBView

if TYPE_CHECKING:
    from bot import LunaBot


class TeamStatsFlags(commands.FlagConverter):
    # team: str = None
    stat: str
    start: str = None
    end: str = "now"


def is_break():
    return localnow().weekday() in (5, 6)


def is_on_break(ctx):
    if is_break():
        raise ActivityEventBreak()

    return True


class ActivityEvent(commands.Cog):
    def __init__(self, bot):
        self.bot: "LunaBot" = bot
        self.teams: Dict[str, Team] = {}
        self.players: Dict[int, Player] = {}
        # self.channel_ids: Dict[int] = {
        #     1158930467337293905,
        #     1158931468664446986,
        #     GENERAL_ID,
        # }
        self.bot.powerup_tasks = []

        if TEST:
            self.msgs_needed = 3
            self.powerups_cycle = cycle([0, 1, 2, 3, 4])
        else:
            self.msgs_needed = random.randint(5, 10)

        self.msg_counter = 0

        self.has_welcomed: Set[int] = set()

        self.powerups_1k = {
            "topup": f"Receive {REDEEM_TOPUP_LOW}-{REDEEM_TOPUP_HIGH} points",
            "steal": f"Steal {REDEEM_STEAL_LOW}-{REDEEM_STEAL_HIGH} points from the other team",
            "double": "Double all incoming points for 30 minutes",
            "triple": "Triple all incoming points for 20 minutes",
            "reduce_cd": "Reduce the cooldown for messages to 1 minute for 25 minutes",
        }
        self.powerup_names = [
            "trivia",
            "steal_trivia",
            "reduced_cd",
            "double",
            "triple",
        ]
        self.non_point_types = [
            "all_msg",
            "multi_powerup",
            "cd_powerup",
            "1k",
            "trivia_powerup",
            "steal_powerup",
            "topup_powerup",
        ]

        self.team_members = {
            "poinsettia": [
                496225545529327616,
                675058943596298340,
                653067767137697905,
                1360304699063931104,
                1136006166909026505,
            ],
            "mistletoe": [
                718475543061987329,
                713118404017651773,
                775100386196717589,
                1430154024505835592,
                835932200368209941,
            ],
        }
        self.team_channels = {
            "mistletoe": TEAM_MISTLETOE_CHANNEL_ID,
            "poinsettia": TEAM_POINSETTIA_CHANNEL_ID,
        }
        self.team_roles = {
            "mistletoe": 1442249692946890853,
            "poinsettia": 1442249666392752279,
        }
        self.team_emojis = {
            "mistletoe": "<:ML_Team_Mistletoe:1302156859909607496>",
            "poinsettia": "<:ML_Team_Poinsettia:1302156805639503892>",
        }
        self.nick_dict = {
            496225545529327616: "Luna",
            675058943596298340: "Molly",
            653067767137697905: "Sora",
            1360304699063931104: "Fae",
            1136006166909026505: "Alessia",
            718475543061987329: "Storch",
            713118404017651773: "Lux",
            775100386196717589: "Kaiz",
            1430154024505835592: "Mika",
            835932200368209941: "Nala",
            # 1056609396257472584: "Bipper",
        }

        self.powerup_emoji = "<a:ML_present_gift:1302182895020150804>"

        self.daily_message_task_cds = {}

        # self.fresh = True

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
                   
                   CREATE TABLE IF NOT EXISTS event_dailies (
                       id SERIAL PRIMARY KEY,
                       user_id BIGINT,
                       date_str TEXT,
                       task TEXT,
                       num INTEGER DEFAULT 1,
                       claimed BOOLEAN DEFAULT FALSE,
                       UNIQUE (user_id, date_str, task)
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

        # rows = await self.bot.db.fetch("SELECT * FROM event_stats")

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

                saved_powerups = [
                    row["option"] for row in await self.bot.db.fetch(query, team_name)
                ]
                self.teams[team_name] = Team(
                    self.bot,
                    team_name,
                    self.team_emojis[team_name],
                    self.bot.get_channel(self.team_channels[team_name]),
                    self.guild.get_role(self.team_roles[team_name]),
                    redeems,
                    saved_powerups,
                )

            for member_id in member_ids:
                member = self.guild.get_member(member_id)
                if member is None:
                    continue

                query = """SELECT
                               id,
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
                    if row["name"] == "multi_powerup":
                        powerups.append(
                            Multiplier(
                                row["value"],
                                row["start_time"],
                                row["end_time"],
                                id=row["id"],
                            )
                        )
                    elif row["name"] == "cd_powerup":
                        powerups.append(
                            CooldownReducer(
                                # row["id"],
                                row["value"],
                                row["start_time"],
                                row["end_time"],
                                id=row["id"],
                            )
                        )

                query = """SELECT
                               sum(gain)
                           FROM
                               event_log
                           WHERE
                               type != ALL($2)
                               AND user_id = $1 
                        """
                points = await self.bot.db.fetchval(
                    query, member.id, self.non_point_types
                )
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
                msgs = await self.bot.db.fetchval(query, "all_msg", member.id)
                if msgs is None:
                    msgs = 0

                team = self.teams[team_name]
                player = Player(
                    self.bot,
                    team,
                    member,
                    self.nick_dict[member.id],
                    points,
                    msgs,
                    powerups,
                )
                self.players[member.id] = player
                team.players.append(player)

        self.teams["mistletoe"].create_captain()
        self.teams["poinsettia"].create_captain()
        self.teams["mistletoe"].opp = self.teams["poinsettia"]
        self.teams["poinsettia"].opp = self.teams["mistletoe"]

        self.questions = parse_raw()

        if not TEST:
            random.shuffle(self.questions)

        self.questions_i = 0

        self.intercept_snowballs = False
        self.num_snowballs: Dict[str, Dict[int, int]] = {}
        self.snowball_messages: List[discord.Message] = []

        self.sync_player_data.start()
        self.award_pension.start()

    async def cog_unload(self):
        for t in self.bot.powerup_tasks:
            t.cancel()
        self.bot.log(f"Cancelled {len(self.bot.powerup_tasks)} powerup tasks", "ae")
        self.sync_player_data.cancel()
        self.award_pension.cancel()

    @tasks.loop(hours=24)
    async def award_pension(self):
        tmp = self.bot.vars.get("ae-break-ids")
        assert isinstance(tmp, str)
        ids = map(int, tmp.split(","))

        amount = self.bot.vars.get("ae-pension-amount")
        nicks = []
        for user_id in ids:
            player = self.players.get(user_id)
            if player is None:
                print(f"{user_id} not a player")
                continue
            await player.add_points(amount, "pension", multi=False)
            nicks.append(player.nick)

        channel = self.bot.get_var_channel("private")
        assert isinstance(channel, discord.TextChannel)
        await channel.send(f"Awarded pensions to {', '.join(nicks)}")

    @award_pension.before_loop
    async def before_award_pension(self):
        await discord.utils.sleep_until(next_day(ZoneInfo("America/Chicago")))

    @tasks.loop(hours=1)
    async def sync_player_data(self):
        """Fetch points and message counts from the database and update the players."""
        try:
            for player_id, player in self.players.items():
                # Fetch points
                points_query = """
                SELECT
                    COALESCE(SUM(gain), 0)
                FROM
                    event_log
                WHERE
                    user_id = $1
                    AND type != ALL($2)
                """
                points = await self.bot.db.fetchval(
                    points_query, player_id, self.non_point_types
                )
                if points is None:
                    points = 0

                # Fetch message count
                msgs_query = """
                SELECT
                    COALESCE(SUM(gain), 0)
                FROM
                    event_log
                WHERE
                    user_id = $1
                    AND type = $2
                """
                msgs = await self.bot.db.fetchval(msgs_query, player_id, "all_msg")
                if msgs is None:
                    msgs = 0

                # Update player object
                player.points = points
                player.msg_count = msgs

                logging.info(
                    f"Updated Player {player.nick} (ID: {player_id}): "
                    f"Points: {player.points}, Msg Count: {player.msg_count}"
                )

        except Exception as e:
            self.bot.log(f"Error during player data synchronization: {e}", "ae")

    @sync_player_data.before_loop
    async def before_sync_player_data(self):
        await asyncio.sleep(3600)

    async def cog_check(self, ctx):
        return ctx.author.id in self.players or ctx.author.id == 718475543061987329

    async def trivia(
        self, player: Player, channel: discord.TextChannel, steal: bool = False
    ):
        await player.log_powerup("trivia_powerup")

        question = self.questions[self.questions_i]

        if self.questions_i == len(self.questions) - 1:
            random.shuffle(self.questions)
            self.questions_i = 0
        else:
            self.questions_i += 1

        question.shuffle_choices()

        points = random.randint(1, 5)
        args = {
            "mention": player.member.mention,
            "team": player.team.name.capitalize(),
        } | question.get_main_layout_repls()

        if not steal:
            layout = self.bot.get_layout("ae/trivia/main")
        else:
            args["otherteam"] = player.team.opp.name
            layout = self.bot.get_layout("ae/stealtrivia/main")

        bot_msg = await layout.send(channel, repls=args, special=False)
        assert bot_msg is not None

        emojis = [
            "<a:ML_red_flower:1308674651450511381>",
            "<a:ML_green_flower:1308674666897997857>",
            "<a:ML_white_flower:1308674682135773206>",
            "<a:ML_gold_flower:1308674704072245318>",
        ]

        for emoji in emojis:
            await bot_msg.add_reaction(emoji)

        def check(r, u):
            return (
                r.message == bot_msg
                and u.id == player.member.id
                and str(r.emoji) in emojis
            )

        try:
            reaction, user = await self.bot.wait_for(
                "reaction_add", check=check, timeout=45
            )
        except asyncio.TimeoutError:
            layout = self.bot.get_layout("ae/trivia/timeout")
            await layout.send(bot_msg, reply=True)
            return

        if question.choices[emojis.index(str(reaction.emoji))] == question.answer:
            await player.increment_daily_task("trivia")

            repls = {"answer": question.answer, "user": player.nick, "points": -1}

            if not steal:
                points = await player.add_points(points, "trivia")

                repls["team"] = player.team.name.capitalize()
                layout = self.bot.get_layout("ae/trivia/correct")
            else:
                await player.team.opp.captain.remove_points(points, "steal_trivia")
                points = await player.add_points(points, "trivia")

                repls["team"] = player.team.opp.name.capitalize()
                layout = self.bot.get_layout("ae/stealtrivia/correct")

            repls["points"] = points
            await layout.send(channel, repls=repls, delete_after=10)
        else:
            layout = self.bot.get_layout("ae/trivia/incorrect")
            await layout.send(
                channel, repls={"answer": question.answer}, delete_after=10
            )

        await asyncio.sleep(10)
        await bot_msg.delete()

    def can_snowball_fight(self):
        """returns True if there are at least two active players on each team"""
        mistletoe = 0
        poinsettia = 0
        now = time.time()

        for player in self.players.values():
            if (
                player.team.name == "mistletoe"
                and (now - player.last_message_time) < 60
            ):
                mistletoe += 1
            elif (
                player.team.name == "poinsettia"
                and (now - player.last_message_time) < 60
            ):
                poinsettia += 1

        if TEST:
            return mistletoe >= 1 and mistletoe == poinsettia
        else:
            m = min(mistletoe, poinsettia)
            d = abs(mistletoe - poinsettia)
            return m > 0 and (d == 0 or (d == 1 and m >= 2))

    async def snowball_fight(self, channel: discord.TextChannel):
        # whichever team spams the most snowballs in 15 seconds wins

        # dodge_phrases = ["dodge", "💨"]

        self.num_snowballs["mistletoe"] = {}
        self.num_snowballs["poinsettia"] = {}

        num_mistletoe = self.num_snowballs["mistletoe"]
        num_poinsettia = self.num_snowballs["poinsettia"]

        self.snowball_messages = []
        self.intercept_snowballs = True

        layout = self.bot.get_layout("ae/snowballfight")
        await layout.send(channel)

        await asyncio.sleep(25)
        # tally handled in on_message

        self.intercept_snowballs = False

        await channel.delete_messages(self.snowball_messages)

        totals_dict = {
            "mistletoe": sum(num_mistletoe.values()),
            "poinsettia": sum(num_poinsettia.values()),
        }

        def weighted_points(total_points: int, team: str) -> Dict[int, int]:
            # return a dict of player ids to points based on how many snowballs they threw
            # the ratio of snowballs thrown equals the ratio of points they get
            return {
                k: round(v / totals_dict[team] * total_points)
                for k, v in self.num_snowballs[team].items()
            }

        if totals_dict["mistletoe"] == totals_dict["poinsettia"]:
            total_points = round(totals_dict["mistletoe"] / 5)

            for team_name in totals_dict.keys():
                for member_id, points in weighted_points(
                    total_points, team_name
                ).items():
                    await self.players[member_id].add_points(
                        points, "snowball_fight", multi=False
                    )

            repls = {
                "snowballs": sum(totals_dict.values()),
                "points1": total_points,
                "points2": total_points,
            }
            layout = self.bot.get_layout("ae/snowballfight/draw")
            await layout.send(channel, repls=repls)
        else:
            winning_team = max(totals_dict, key=totals_dict.get)
            losing_team = min(totals_dict, key=totals_dict.get)
            snowball_diff = abs(totals_dict["mistletoe"] - totals_dict["poinsettia"])

            bonus_points = round(snowball_diff / 2)
            winning_points = round(totals_dict[winning_team] / 4) + bonus_points
            losing_points = round(totals_dict[losing_team] / 4)

            for member_id, points in weighted_points(
                winning_points, winning_team
            ).items():
                await self.players[member_id].add_points(
                    points, "snowball_fight", multi=False
                )
            for member_id, points in weighted_points(
                losing_points, losing_team
            ).items():
                await self.players[member_id].add_points(
                    points, "snowball_fight", multi=False
                )

            if winning_team == "poinsettia":
                points1 = losing_points
                points2 = winning_points
            else:
                points1 = winning_points
                points2 = losing_points

            repls = {
                "snowballs": sum(totals_dict.values()),
                "points1": points1,
                "points2": points2,
                "winningteam": winning_team.capitalize(),
                "bonus": bonus_points,
            }
            layout = self.bot.get_layout("ae/snowballfight/results")
            await layout.send(channel, repls=repls)

    @commands.Cog.listener()
    async def on_member_join(self, member):
        self.has_welcomed = set()

    async def handle_snowball(self, msg: discord.Message):
        snowball_phrases = ["<:ML_blue_snowflake:1310499586841903154>"]

        if msg.content not in snowball_phrases:
            return

        num_mistletoe = self.num_snowballs["mistletoe"]
        num_poinsettia = self.num_snowballs["poinsettia"]

        self.snowball_messages.append(msg)

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

    @commands.Cog.listener()
    async def on_message(self, msg: discord.Message):
        if msg.guild is None or msg.guild.id != self.bot.GUILD_ID:
            return
        if msg.author.bot:
            return
        if msg.author.id not in self.players:
            return
        if msg.channel.id != GENERAL_ID:
            return

        if is_break() and not TEST:
            return

        if (
            msg.author not in self.daily_message_task_cds
            or self.daily_message_task_cds[msg.author] < time.time()
        ):
            self.daily_message_task_cds[msg.author] = time.time() + 5
            await self.players[msg.author.id].increment_daily_task("messages")

        if self.intercept_snowballs:
            await self.handle_snowball(msg)
            return

        player = self.players[msg.author.id]
        await player.on_msg()

        if player.msg_count % LOW_PERIOD == 0:
            self.bot.loop.create_task(player.on_500())

        if player.team.msg_count % HIGH_PERIOD == 0:
            self.bot.loop.create_task(player.team.on_1000())

        if msg.author.id not in self.has_welcomed:
            if msg.content.lower().startswith("welc"):
                self.has_welcomed.add(msg.author.id)
                self.bot.loop.create_task(player.on_welc(msg.channel))

        self.msg_counter += 1
        if self.msg_counter < self.msgs_needed:
            return

        self.msg_counter = 0
        self.msgs_needed = random.randint(10, 25)

        # comment out later
        # self.msgs_needed = 3

        # if random.random() < 0.5 and not TEST and not self.fresh:
        if random.random() < 0.5 and not TEST:
            return

        # self.fresh = False

        if TEST:
            snowball_threshold = 1
        else:
            snowball_threshold = 0.15

        if (
            not self.intercept_snowballs
            and self.can_snowball_fight()
            and random.random() < snowball_threshold
        ):
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

        spawn_msg = await layout.send(msg.channel, special=False)

        await spawn_msg.add_reaction(self.powerup_emoji)

        def check(r, u):
            return (
                u.id in self.players
                and r.message == spawn_msg
                and str(r.emoji) == self.powerup_emoji
            )

        try:
            reaction, user = await self.bot.wait_for(
                "reaction_add", check=check, timeout=60
            )
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
            await player.apply_new_powerup(
                CooldownReducer(
                    INDIV_REDUCED_CD, time.time(), time.time() + INDIV_REDUCED_CD_TIME
                ),
                log=True,
            )

            for other in player.team.players:
                if other != player:
                    await other.apply_new_powerup(
                        CooldownReducer(
                            TEAM_REDUCED_CD,
                            time.time(),
                            time.time() + TEAM_REDUCED_CD_TIME,
                        )
                    )

            layout = self.bot.get_layout("ae/reducedcd")
        elif powerup_name == "double":
            await player.apply_new_powerup(
                Multiplier(2, time.time(), time.time() + INDIV_DOUBLE_TIME), log=True
            )

            for other in player.team.players:
                if other != player:
                    await other.apply_new_powerup(
                        Multiplier(2, time.time(), time.time() + TEAM_DOUBLE_TIME)
                    )

            layout = self.bot.get_layout("ae/double")
        elif powerup_name == "triple":
            await player.apply_new_powerup(
                Multiplier(3, time.time(), time.time() + INDIV_TRIPLE_TIME), log=True
            )

            for other in player.team.players:
                if other != player:
                    await other.apply_new_powerup(
                        Multiplier(3, time.time(), time.time() + TEAM_TRIPLE_TIME)
                    )

            layout = self.bot.get_layout("ae/triple")

        if layout is not None:
            repls = {
                "mention": player.member.mention,
                "team": player.team.name.capitalize(),
            }
            await layout.send(msg.channel, repls=repls, special=False)

    @commands.command()
    @commands.check(is_on_break)
    async def redeem(self, ctx):
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

        layout = self.bot.get_layout("ae/redeem")
        view = RedeemView(ctx, team, choices, self.powerups_1k)
        view.message = await layout.send(
            ctx,
            repls={
                f"powerup{i + 1}": self.powerups_1k[choice]
                for i, choice in enumerate(choices)
            },
            view=view,
        )

    @commands.command()
    @commands.check(is_on_break)
    async def usepowerup(self, ctx):
        for team in self.teams.values():
            if ctx.author == team.captain.member:
                break
        else:
            return

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
            msg = await self.bot.wait_for("message", check=check, timeout=60)
        except asyncio.TimeoutError:
            await temp.delete()
            return

        if (
            not msg.content.isdigit()
            or int(msg.content) > len(powerups)
            or int(msg.content) < 1
        ):
            await ctx.send("That is not a valid number!", ephemeral=True)
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
        embed = discord.Embed(title="Points for each team", color=0xCAB7FF)
        for team in self.teams:
            embed.add_field(
                name=team.capitalize(), value=f"{self.teams[team].total_points:,}"
            )
        await ctx.send(embed=embed)

    @commands.command(aliases=["pts", "teamlb", "allpoints", "pointslb"])
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

    @commands.command(aliases=["effects"])
    @commands.check(is_on_break)
    async def powerups(self, ctx, *, member: discord.Member = None):
        if member is None:
            member = ctx.author

        if member.id not in self.players:
            await ctx.send("You aren't on a team!")
            return

        player = self.players[member.id]

        hearts = []
        powerup_names = []
        values = []
        timethingys = []

        pink_heart = self.bot.vars.get("heart-point-emoji")
        purple_heart = self.bot.vars.get("heart-point-purple-emoji")

        powerups = sorted(player.powerups, key=lambda p: p.end)
        exists = False
        for i, powerup in enumerate(powerups):
            exists = True
            if powerup.name == "Multiplier":
                value = f"x{powerup.n}"
            else:
                minutes, seconds = divmod(powerup.n, 60)
                value = f"{minutes}:{seconds:02}"

            values.append(value)
            hearts.append(pink_heart if i % 2 == 0 else purple_heart)
            powerup_names.append(powerup.name)
            timethingys.append(
                discord.utils.format_dt(datetime.fromtimestamp(powerup.end), "R")
            )

        real_multi = f"x{player.real_multi}"
        minutes, seconds = divmod(player.cd, 60)
        real_cd = f"{minutes}:{seconds:02}"

        layout = self.bot.get_layout("ae/powerups")
        await layout.send(
            ctx,
            repls={
                "data": zip(hearts, powerup_names, values, timethingys),
                "branch": self.bot.vars.get("branch-final-emoji"),
                "exists": exists,
                "realmulti": real_multi,
                "realcd": real_cd,
            },
            jinja=True,
        )

    @commands.command(aliases=["dailys"])
    @commands.check(is_on_break)
    async def dailies(self, ctx):
        if ctx.author.id not in self.players:
            return

        view = DailyTasksView(ctx, self.players[ctx.author.id])
        await view.send()

    @commands.command()
    async def teamstats(self, ctx, *, flags: TeamStatsFlags):
        VALID_STATS = {
            "msgs",
            "msg",
            "message",
            "messages",
            "points",
            "pts",
            "powerup",
            "powerups",
            "bonuses",
            "bonus",
            "trivia",
            "stolen",
            "stole",
            "steals",
            "welc",
            "welcs",
            "snowball",
            "snowballfight",
            "snowballs",
            "snowballfights",
            "snow",
            "daily",
            "dailies",
            "advent",
        }

        if flags.stat.lower() not in VALID_STATS:
            return await ctx.send("That is not a valid option!")

        # team = self._get_team(ctx, flags)
        # if team is None:
        #     return await ctx.send('That is not a valid team!')
        team = "both"

        tz = await ctx.fetch_timezone()

        start = (
            START_TIME
            if flags.start is None
            else dateparser.parse(
                flags.start,
                settings={"TIMEZONE": tz, "RETURN_AS_TIMEZONE_AWARE": True},
            )
        )

        end = dateparser.parse(
            flags.end, settings={"TIMEZONE": tz, "RETURN_AS_TIMEZONE_AWARE": True}
        )

        if flags.stat in {"msg", "messages", "message", "msgs"}:
            await self._process_stat(
                ctx,
                team,
                start,
                end,
                "messages sent",
                "all_msg",
                lambda x: x.msg_count,
                lambda t: t.msg_count,
            )
        elif flags.stat in {"points", "pts"}:
            await self._process_stat(
                ctx,
                team,
                start,
                end,
                "points earned",
                None,
                lambda x: x.points,
                lambda t: t.total_points,
                exclude_types=self.non_point_types,
            )
        elif flags.stat in {"powerup", "powerups"}:
            await self._process_powerup(ctx, team, start, end, "powerups obtained")
        elif flags.stat in {"bonus", "bonuses"}:
            await self._process_bonus(
                ctx,
                team,
                start,
                end,
                "bonus points earned",
                ["welc_bonus", "500_bonus", "topup_bonus", "steal_bonus"],
            )
        elif flags.stat == "trivia":
            await self._process_bonus(
                ctx, team, start, end, "trivia points earned", ["trivia"]
            )
        elif flags.stat in {"stolen", "stole", "steals"}:
            await self._process_bonus(
                ctx, team, start, end, "points stolen", ["stolen", "steal_trivia"]
            )
        elif flags.stat in {"snowball", "snowballfight"}:
            await self._process_bonus(
                ctx, team, start, end, "points from snowball fights", ["snowball_fight"]
            )
        elif flags.stat in {"welc", "welcs"}:
            await self._process_bonus(
                ctx, team, start, end, "points from welcoming", ["welc_bonus"]
            )
        elif flags.stat in {"daily", "dailies", "advent"}:
            await self._process_bonus(
                ctx, team, start, end, "points from dailies", ["dailies_bonus"]
            )

    def _data_from_rows(self, rows_list, start, end):
        ret = []
        for team, rows in rows_list:
            data = []
            cumulative_sum = 0  # Accumulate values even before the start time

            # Add all rows before the start time to the cumulative sum
            for row in rows:
                if row["time"] <= int(start.timestamp()):
                    cumulative_sum += row["gain"]
                else:
                    break

            # Ensure a data point at the start time
            data.append((int(start.timestamp()), cumulative_sum))

            # Add rows from the start time onward
            for row in rows:
                if row["time"] > int(start.timestamp()):
                    cumulative_sum += row["gain"]
                    data.append((row["time"], cumulative_sum))

            # Ensure a data point at the end time
            if not data or data[-1][0] < int(end.timestamp()):
                data.append((int(end.timestamp()), cumulative_sum))

            ret.append((team, data))
        return ret

    def _get_team(self, ctx, flags):
        if flags.team is None:
            return self.players[ctx.author.id].team
        elif flags.team.lower() == "both":
            return "both"
        elif flags.team not in self.teams:
            return None
        else:
            return self.teams[flags.team]

    async def _process_stat(
        self,
        ctx,
        team,
        start,
        end,
        title,
        stat_type,
        player_key,
        team_key,
        exclude_types=None,
    ):
        rows_list = []
        for t in self.teams.values() if team == "both" else [team]:
            rows = await self._fetch_rows(t.name, stat_type, start, end, exclude_types)
            rows_list.append((t, rows))

        data = self._data_from_rows(rows_list, start, end)
        file = await plot_data(ctx, data)
        embed = self.bot.get_embed("ae/teamstats")
        repls = self._get_stat_repls(title, start, end, player_key, team_key)
        embed = await Layout.fill_embed(embed, repls, special=False)
        embed.set_image(url="attachment://plot.png")
        await ctx.send(embed=embed, file=file)

    async def _process_bonus(self, ctx, team, start, end, title, types):
        rows_list, stats, player_stats = [], {}, {}
        for t in self.teams.values():
            rows, stats, player_stats = await self._process_rows(
                t, types, end, stats, player_stats
            )
            rows_list.append((t, rows))

        data = self._data_from_rows(rows_list, start, end)
        file = await plot_data(ctx, data)
        embed = self.bot.get_embed("ae/teamstats")
        repls = self._get_bonus_repls(title, team, stats, player_stats, start, end)
        embed = await Layout.fill_embed(embed, repls, special=False)
        embed.set_image(url="attachment://plot.png")
        await ctx.send(embed=embed, file=file)

    async def _fetch_rows(self, team, stat_type, start, end, exclude_types):
        if stat_type:
            query = """SELECT time, gain FROM event_log WHERE team = $1 AND type = $2 AND time < $3 ORDER BY time ASC"""
            return await self.bot.db.fetch(query, team, stat_type, int(end.timestamp()))
        else:
            query = """SELECT gain, time FROM event_log WHERE team = $1 AND type != ALL($2) AND time < $3 ORDER BY time ASC"""
            return await self.bot.db.fetch(
                query, team, exclude_types, int(end.timestamp())
            )

    async def _process_rows(self, team, types, end, stats, player_stats):
        if team.name not in stats:
            stats[team.name] = {}

        query = """SELECT user_id, gain, time FROM event_log WHERE team = $1 AND type = ANY($3) AND time < $2"""
        rows = await self.bot.db.fetch(query, team.name, int(end.timestamp()), types)

        total = 0
        for row in rows:
            if row["user_id"] not in player_stats:
                player_stats[row["user_id"]] = 0
            player_stats[row["user_id"]] += row["gain"]
            total += row["gain"]

        stats[team.name]["total"] = total
        return rows, stats, player_stats

    def _get_stat_repls(self, title, start, end, player_key, team_key):
        total = 0
        repls = {}

        # for i, t in enumerate(self.teams.values()):
        # ORDER IS IMPORTANT TO MATCH LAYOUT!
        for i, tname in enumerate(["mistletoe", "poinsettia"]):
            t = self.teams[tname]
            duration = end.timestamp() - start.timestamp()
            repls[f"mvp{i + 1}"] = max(t.players, key=player_key).nick
            repls[f"total{i + 1}"] = team_key(t)
            repls[f"houravg{i + 1}"] = "{:.2f}".format(team_key(t) / (duration / 3600))
            repls[f"dayavg{i + 1}"] = "{:.2f}".format(team_key(t) / (duration / 86400))
            repls[f"playeravg{i + 1}"] = "{:.2f}".format(team_key(t) / len(t.players))
            total += team_key(t)

        repls["stattitle"] = title.title()
        repls["stat"] = title
        repls["total"] = total

        return repls

    def _get_bonus_repls(self, title, team, stats, player_stats, start, end):
        total = 0
        repls = {}
        for i, t in enumerate(self.teams.values()):
            mvp = max(t.players, key=lambda x: player_stats.get(x.member.id, 0))
            # count = player_stats.get(mvp.member.id, 0)
            this_total = stats[t.name]["total"]
            repls[f"mvp{i + 1}"] = mvp.nick
            repls[f"total{i + 1}"] = this_total
            repls[f"playeravg{i + 1}"] = "{:.2f}".format(total / len(t.players))
            repls[f"houravg{i + 1}"] = "{:.2f}".format(
                total / (end.timestamp() - start.timestamp()) * 3600
            )
            repls[f"dayavg{i + 1}"] = "{:.2f}".format(
                total / (end.timestamp() - start.timestamp()) * 86400
            )

            total += this_total

        repls["title"] = title.title()
        repls["stat"] = title
        repls["total"] = total

        return repls

    @commands.command()
    @commands.is_owner()
    async def announce(self, ctx, *, message):
        for team in self.teams.values():
            this_message = f"{team.captain.member.mention}\n\n{message}\n\n-storch\n-# this message is sent to both team channels and will only ping the captain"
            await team.channel.send(this_message)
        await ctx.send("Done!")

    @commands.command()
    async def teamping(self, ctx):
        for team, ids in self.team_members.items():
            if ctx.author.id in ids:
                break
        else:
            return

        role_id = self.team_roles[team]
        role = ctx.guild.get_role(role_id)
        if role is None:
            return await ctx.send("Role not found.")

        await ctx.send(role.mention)


async def setup(bot):
    if LOAD:
        await bot.add_cog(ActivityEvent(bot))
