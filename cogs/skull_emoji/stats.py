from textwrap import dedent
from typing import TYPE_CHECKING

import discord
from discord.ext import commands
import dateparser

from .graphs import plot_data
from .constants import *

if TYPE_CHECKING:
    from bot import LunaBot


class TeamStatsFlags(commands.FlagConverter):
    team: str = None
    stat: str
    start: str = None
    end: str = "now"


class ActivityEventStats(commands.Cog):
    def __init__(self, bot):
        self.bot: "LunaBot" = bot

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
        }

        if flags.stat.lower() not in VALID_STATS:
            return await ctx.send("That is not a valid option!")

        team = self._get_team(ctx, flags)
        if team is None:
            return await ctx.send("That is not a valid team!")

        start = START_TIME if flags.start is None else dateparser.parse(flags.start)
        end = dateparser.parse(flags.end)

        if flags.stat in {"msg", "messages", "message", "msgs"}:
            await self._process_stat(
                ctx,
                team,
                start,
                end,
                "Messages sent",
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
                "Points earned",
                None,
                lambda x: x.points,
                lambda t: t.total_points,
                exclude_types=self.non_point_types,
            )
        elif flags.stat in {"powerup", "powerups"}:
            await self._process_powerup(ctx, team, start, end, "Powerups obtained")
        elif flags.stat in {"bonus", "bonuses"}:
            await self._process_bonus(
                ctx,
                team,
                start,
                end,
                "Bonus points earned",
                ["welc_bonus", "500_bonus", "topup_bonus", "steal_bonus"],
            )
        elif flags.stat == "trivia":
            await self._process_bonus(
                ctx, team, start, end, "Trivia points earned", ["trivia"]
            )
        elif flags.stat in {"stolen", "stole", "steals"}:
            await self._process_bonus(
                ctx, team, start, end, "Points stolen", ["stolen", "steal_trivia"]
            )
        else:
            await self._process_bonus(
                ctx, team, start, end, "Points from welcoming", ["welc_bonus"]
            )

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

        data = self._data_from_rows(rows_list, start)
        file = await plot_data(self.bot, data)
        embed = self._create_stat_embed(
            title, team, data, start, end, player_key, team_key
        )
        await ctx.send(embed=embed, file=file)

    async def _process_bonus(self, ctx, team, start, end, title, types):
        rows_list, stats, player_stats = [], {}, {}
        for t in self.teams.values() if team == "both" else [team]:
            rows, stats, player_stats = await self._process_rows(
                t, types, end, stats, player_stats
            )
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
            placeholders = ",".join(f"${i + 3}" for i in range(len(exclude_types)))
            query = f"""SELECT gain, time FROM event_log WHERE team = $1 AND time < $2 AND type NOT IN ({placeholders})"""
            return await self.bot.db.fetch(
                query, team, int(end.timestamp()), *exclude_types
            )

    async def _process_rows(self, team, types, end, stats, player_stats):
        if team.name not in stats:
            stats[team.name] = {}

        query = f"""SELECT user_id, gain, time FROM event_log WHERE team = $1 AND type IN ({",".join(f"${i + 3}" for i in range(len(types)))}) AND time < $2"""
        rows = await self.bot.db.fetch(query, team.name, int(end.timestamp()), *types)

        total = 0
        for row in rows:
            if row["user_id"] not in player_stats:
                player_stats[row["user_id"]] = 0
            player_stats[row["user_id"]] += row["gain"]
            total += row["gain"]

        stats[team.name]["total"] = total
        return rows, stats, player_stats

    def _data_from_rows(self, rows_list, start):
        ret = []
        for team, rows in rows_list:
            data = []
            count, i = 0, 0
            while i < len(rows):
                row = rows[i]
                if row["time"] > int(start.timestamp()):
                    break
                count += row["gain"]
                i += 1

            if i != 0:
                data.append((row["time"], count))

            while i < len(rows):
                row = rows[i]
                prev_sum = data[-1][1] if data else 0
                data.append((row["time"], prev_sum + row["gain"]))
                i += 1

            ret.append((team, data))
        return ret

    def _create_stat_embed(self, title, team, data, start, end, player_key, team_key):
        embed = discord.Embed(title=title, color=0xCAB7FF)
        for t in self.teams.values() if team == "both" else [team]:
            mvp = max(t.players, key=player_key)
            total = team_key(t)
            val = self._generate_stat_val(mvp, total, start, end, len(t.players))
            embed.add_field(name=t.name.capitalize(), value=val)
        return embed

    def _create_bonus_embed(self, title, team, stats, player_stats, start, end):
        embed = discord.Embed(title=title, color=0xCAB7FF)
        for t in self.teams.values() if team == "both" else [team]:
            mvp = max(t.players, key=lambda x: player_stats.get(x.member.id, 0))
            count = player_stats.get(mvp.member.id, 0)
            total = stats[t.name]["total"]
            val = self._generate_stat_val(mvp, total, start, end, len(t.players))
            embed.add_field(name=t.name.capitalize(), value=val)
        return embed

    def _generate_stat_val(self, mvp, total, start, end, player_count):
        duration = end.timestamp() - start.timestamp()
        return dedent(f"""
        Total: **{total:,}**
        Average per player: **{total / player_count:.2f}**
        Team MVP: **{mvp.nick}** ({total:,})
        Average per hour: **{total / (duration / 3600):.2f}**
        Average per day: **{total / (duration / 86400):.2f}**
        """)
