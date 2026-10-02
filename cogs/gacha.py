import asyncio
import random
from collections import defaultdict
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands

from .economy.windows import format_months, is_open, window_end
from .utils.checks import admin_only, is_admin

if TYPE_CHECKING:
    from bot import LunaBot

    from .economy import Economy

RARE_SYMBOL = "☆"
COMMON_SYMBOL = "♡"
MAX_PULLS = 10

DEFAULT_BADGE_SET = "moons"

# seasonal banners -> the rank card to remind pullers about
BANNER_CARDS = {
    "snowflakes": "winter",
    "clovers": "spring",
    "suns": "summer",
    "leaves": "fall",
    "halloween": "halloween",
    "christmas": "christmas",
    "octoberroles": "halloween",
}


@dataclass
class GachaItem:
    name: str
    banner: str
    display_name: str
    rarity: str
    shop_item: str | None
    badge_slot: int | None

    @property
    def symbol(self) -> str:
        return RARE_SYMBOL if self.rarity == "rare" else COMMON_SYMBOL


@dataclass
class Banner:
    name: str
    display_name: str
    months: list[int] | None
    pull_cost: int
    rare_rate: float
    common_rate: float
    rare_pity: int
    common_pity: int
    consolation_min: int
    consolation_max: int
    common_refund: int
    rare_refund: int
    sort_order: int
    items: list[GachaItem] = field(default_factory=list)

    def is_open(self) -> bool:
        return is_open(self.months)

    @property
    def is_badge_set(self) -> bool:
        return any(it.badge_slot is not None for it in self.items)

    def tier(self, rarity: str) -> list[GachaItem]:
        return [it for it in self.items if it.rarity == rarity]

    def refund(self, item: GachaItem) -> int:
        return self.rare_refund if item.rarity == "rare" else self.common_refund


@dataclass
class PullResult:
    item: GachaItem | None  # None = miss
    new: bool = False
    lunara: int = 0  # consolation (miss) or duplicate refund


class Gacha(commands.Cog):
    """Limited-time gacha banners for roles and rank card badges."""

    def __init__(self, bot):
        self.bot: "LunaBot" = bot
        self.banners: dict[str, Banner] = {}
        self.items: dict[str, GachaItem] = {}
        self.locks: defaultdict[int, asyncio.Lock] = defaultdict(asyncio.Lock)

    @property
    def economy(self) -> "Economy":
        return self.bot.get_cog("Economy")

    async def cog_check(self, ctx):
        # `gacha-live` var gates the launch; admins can always test
        if not self.bot.vars.get("gacha-live") and not is_admin(ctx):
            return False
        return self.economy.is_verified(ctx.author)

    async def cog_load(self):
        rows = await self.bot.db.fetch("SELECT * FROM gacha_banners")
        self.banners = {row["name"]: Banner(**dict(row)) for row in rows}

        rows = await self.bot.db.fetch("SELECT * FROM gacha_items ORDER BY name")
        for row in rows:
            item = GachaItem(**dict(row))
            self.items[item.name] = item
            self.banners[item.banner].items.append(item)

        for banner in self.banners.values():
            # rares last, badges in slot order
            banner.items.sort(key=lambda it: (it.rarity == "rare", it.badge_slot or 0))

    def sorted_banners(self, *, open_only: bool = False) -> list[Banner]:
        banners = sorted(self.banners.values(), key=lambda b: b.sort_order)
        if open_only:
            banners = [b for b in banners if b.is_open()]
        return banners

    def find_banner(self, query: str) -> Banner | None:
        query = query.lower().strip()
        for banner in self.banners.values():
            if query in (banner.name, banner.display_name.lower()):
                return banner
        return None

    async def owned_items(self, user_id: int, banner: Banner | None = None) -> set[str]:
        query = "SELECT item FROM user_gacha_items WHERE user_id = $1"
        rows = await self.bot.db.fetch(query, user_id)
        names = {row["item"] for row in rows}
        if banner is not None:
            names &= {it.name for it in banner.items}
        return names

    async def get_pity(self, user_id: int, banner: Banner) -> tuple[int, int]:
        query = "SELECT since_rare, since_hit FROM gacha_pity WHERE user_id = $1 AND banner = $2"
        row = await self.bot.db.fetchrow(query, user_id, banner.name)
        if row is None:
            return 0, 0
        return row["since_rare"], row["since_hit"]

    def roll(
        self,
        banner: Banner,
        owned: set[str],
        since_rare: int,
        since_hit: int,
    ) -> tuple[PullResult, int, int]:
        """Roll one pull. Returns the result and the updated pity counters."""
        since_rare += 1
        since_hit += 1
        force_rare = since_rare >= banner.rare_pity
        force_hit = since_hit >= banner.common_pity

        r = random.random()
        if force_rare or r < banner.rare_rate:
            rarity, forced = "rare", force_rare
        elif force_hit or r < banner.rare_rate + banner.common_rate:
            rarity, forced = "common", force_hit
        else:
            amount = random.randint(banner.consolation_min, banner.consolation_max)
            return PullResult(None, lunara=amount), since_rare, since_hit

        pool = banner.tier(rarity)
        if forced:
            # a pity pull shouldn't waste itself on a duplicate if it can help it
            pool = [it for it in pool if it.name not in owned] or pool
        item = random.choice(pool)

        if rarity == "rare":
            since_rare = 0
        since_hit = 0

        if item.name in owned:
            return PullResult(item, lunara=banner.refund(item)), since_rare, since_hit
        return PullResult(item, new=True), since_rare, since_hit

    async def pull(
        self, member: discord.Member, banner: Banner, amount: int
    ) -> tuple[list[PullResult], int, int]:
        """Pull up to `amount` times. Stops early once the banner is complete.

        Returns (results, net lunara change, pulls until rare pity).
        """
        owned = await self.owned_items(member.id, banner)
        since_rare, since_hit = await self.get_pity(member.id, banner)

        results = []
        for _ in range(amount):
            if len(owned) == len(banner.items):
                break
            result, since_rare, since_hit = self.roll(
                banner, owned, since_rare, since_hit
            )
            if result.new:
                owned.add(result.item.name)
            results.append(result)

        net = sum(r.lunara for r in results) - banner.pull_cost * len(results)

        async with self.bot.db.acquire() as con, con.transaction():
            query = """INSERT INTO
                           gacha_pity (user_id, banner, since_rare, since_hit, total_pulls)
                       VALUES
                           ($1, $2, $3, $4, $5)
                       ON CONFLICT (user_id, banner) DO
                       UPDATE
                       SET
                           since_rare = EXCLUDED.since_rare,
                           since_hit = EXCLUDED.since_hit,
                           total_pulls = gacha_pity.total_pulls + EXCLUDED.total_pulls
                    """
            await con.execute(
                query, member.id, banner.name, since_rare, since_hit, len(results)
            )

            for result in results:
                if result.item is None:
                    continue
                await self._record_item(con, member.id, result.item, new=result.new)

            query = """INSERT INTO
                           balances (user_id, balance)
                       VALUES
                           ($1, $2)
                       ON CONFLICT (user_id) DO
                       UPDATE
                       SET
                           balance = balances.balance + $2
                    """
            await con.execute(query, member.id, net)

        return results, net, banner.rare_pity - since_rare

    async def _record_item(self, con, user_id: int, item: GachaItem, *, new: bool):
        query = """INSERT INTO
                       user_gacha_items (user_id, item)
                   VALUES
                       ($1, $2)
                   ON CONFLICT (user_id, item) DO
                   UPDATE
                   SET
                       times_pulled = user_gacha_items.times_pulled + 1
                """
        await con.execute(query, user_id, item.name)

        if new and item.shop_item is not None:
            query = """INSERT INTO
                           user_items (user_id, item_name_id, state, item_count)
                       VALUES
                           ($1, $2, 'inactive', 1)
                       ON CONFLICT (user_id, item_name_id) DO NOTHING
                    """
            await con.execute(query, user_id, item.shop_item)

    async def get_rank_card(self, member: discord.Member) -> tuple[str, list[tuple[str, int]]]:
        """Returns (template name, [(badge_set, slot), ...]) for a member's rank card."""
        query = """SELECT
                       ui.item_name_id
                   FROM
                       user_items ui
                       JOIN shop_items si ON si.name_id = ui.item_name_id
                   WHERE
                       ui.user_id = $1
                       AND ui.state = 'active'
                       AND si.category = 'rank_cards'
                """
        name_id = await self.bot.db.fetchval(query, member.id)
        template = name_id.removesuffix("card") if name_id else "standard"

        query = "SELECT badge_set FROM rank_card_prefs WHERE user_id = $1"
        badge_set = await self.bot.db.fetchval(query, member.id) or DEFAULT_BADGE_SET

        if badge_set not in self.banners:
            return template, []

        owned = await self.owned_items(member.id, self.banners[badge_set])
        badges = [
            (badge_set, self.items[name].badge_slot)
            for name in owned
            if self.items[name].badge_slot is not None
        ]
        return template, badges

    async def card_reminder(self, member: discord.Member, banner: Banner) -> dict | None:
        """The seasonal rank card tied to `banner`, if the member doesn't own it yet."""
        card = BANNER_CARDS.get(banner.name)
        if card is None:
            return None

        item = self.economy.get_item_from_str(f"{card}card")
        if item is None or not item.in_shop():
            return None

        query = "SELECT 1 FROM user_items WHERE user_id = $1 AND item_name_id = $2"
        if await self.bot.db.fetchval(query, member.id, item.name_id):
            return None

        return {
            "name": item.display_name,
            "nameid": item.name_id,
            "price": f"{item.price:,}",
        }

    def banner_repls(self, banner: Banner) -> dict:
        end = window_end(banner.months)
        return {
            "name": banner.name,
            "displayname": banner.display_name,
            "window": format_months(banner.months),
            "closes": discord.utils.format_dt(end, "R") if end else None,
            "cost": f"{banner.pull_cost:,}",
            "rarerate": f"{banner.rare_rate:.0%}",
            "commonrate": f"{banner.common_rate:.0%}",
            "rarepity": banner.rare_pity,
            "commonpity": banner.common_pity,
        }

    async def banner_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        return [
            app_commands.Choice(name=b.display_name, value=b.name)
            for b in self.sorted_banners(open_only=True)
            if current.lower() in b.display_name.lower()
        ][:25]

    async def send_bad_banner(self, ctx):
        layout = self.bot.get_layout("gacha/badbanner")
        banners = [self.banner_repls(b) for b in self.sorted_banners(open_only=True)]
        await layout.send(ctx, repls={"banners": banners}, jinja=True)

    @commands.hybrid_command(name="banners", aliases=["gacha"])
    async def banners_cmd(self, ctx):
        """See which gacha banners are open right now."""
        owned = await self.owned_items(ctx.author.id)
        banners = []
        for banner in self.sorted_banners(open_only=True):
            since_rare, _ = await self.get_pity(ctx.author.id, banner)
            repls = self.banner_repls(banner)
            repls["owned"] = len(owned & {it.name for it in banner.items})
            repls["total"] = len(banner.items)
            repls["rarein"] = banner.rare_pity - since_rare
            banners.append(repls)

        layout = self.bot.get_layout("gacha/banners")
        await layout.send(ctx, repls={"banners": banners}, jinja=True)

    @commands.hybrid_command(name="pull", aliases=["roll", "wish"])
    @app_commands.describe(banner="The banner to pull on", amount="How many pulls (1-10)")
    @app_commands.autocomplete(banner=banner_autocomplete)
    async def pull_cmd(
        self,
        ctx,
        banner: str,
        amount: commands.Range[int, 1, MAX_PULLS] = 1,
    ):
        """Pull on a gacha banner."""
        found = self.find_banner(banner)
        if found is None:
            await self.send_bad_banner(ctx)
            return
        banner = found

        if not banner.is_open():
            layout = self.bot.get_layout("gacha/closed")
            await layout.send(ctx, repls=self.banner_repls(banner), jinja=True)
            return

        async with self.locks[ctx.author.id]:
            owned = await self.owned_items(ctx.author.id, banner)
            if len(owned) == len(banner.items):
                layout = self.bot.get_layout("gacha/complete")
                await layout.send(ctx, repls=self.banner_repls(banner), jinja=True)
                return

            balance = await self.economy.get_balance(ctx.author.id)
            if balance < banner.pull_cost * amount:
                layout = self.bot.get_layout("gacha/broke")
                repls = self.banner_repls(banner)
                repls["balance"] = f"{balance:,}"
                repls["amount"] = amount
                repls["needed"] = f"{banner.pull_cost * amount:,}"
                await layout.send(ctx, repls=repls, jinja=True)
                return

            results, net, rare_in = await self.pull(ctx.author, banner, amount)
            balance = await self.economy.get_balance(ctx.author.id)

        repls = self.banner_repls(banner)
        repls.update(
            {
                "results": [
                    {
                        "item": r.item.display_name if r.item else None,
                        "symbol": r.item.symbol if r.item else None,
                        "rarity": r.item.rarity if r.item else None,
                        "new": r.new,
                        "lunara": f"{r.lunara:,}",
                    }
                    for r in results
                ],
                "pulls": len(results),
                "spent": f"{banner.pull_cost * len(results):,}",
                "net": f"{net:+,}",
                "balance": f"{balance:,}",
                "rarein": rare_in,
                "complete": len(await self.owned_items(ctx.author.id, banner))
                == len(banner.items),
                "hasrole": any(r.new and r.item.shop_item for r in results),
                "cardreminder": await self.card_reminder(ctx.author, banner),
            }
        )
        layout = self.bot.get_layout("gacha/pull")
        await layout.send(ctx, repls=repls, jinja=True)

    @commands.hybrid_command(name="collection", aliases=["badges"])
    @app_commands.describe(member="Whose collection to view")
    async def collection(self, ctx, member: discord.Member | None = None):
        """View your gacha collection."""
        member = member or ctx.author
        owned = await self.owned_items(member.id)

        banners = []
        for banner in self.sorted_banners():
            # closed banners only show if the member has something from them
            if not banner.is_open() and not owned & {it.name for it in banner.items}:
                continue
            repls = self.banner_repls(banner)
            repls["open"] = banner.is_open()
            repls["prizes"] = [
                {"name": it.display_name, "symbol": it.symbol, "owned": it.name in owned}
                for it in banner.items
            ]
            repls["owned"] = sum(it.name in owned for it in banner.items)
            repls["total"] = len(banner.items)
            banners.append(repls)

        layout = self.bot.get_layout("gacha/collection")
        await layout.send(
            ctx,
            repls={"member": member.display_name, "banners": banners},
            jinja=True,
        )

    @commands.hybrid_command(name="badgeset")
    @app_commands.describe(badge_set="The badge set to show on your rank card")
    async def badgeset(self, ctx, *, badge_set: str | None = None):
        """Choose which badge set shows on your rank card."""
        choices = [b for b in self.sorted_banners() if b.is_badge_set]
        banner = self.find_banner(badge_set) if badge_set else None

        if banner is None or banner not in choices:
            query = "SELECT badge_set FROM rank_card_prefs WHERE user_id = $1"
            current = await self.bot.db.fetchval(query, ctx.author.id)
            current = self.banners.get(current or DEFAULT_BADGE_SET)
            layout = self.bot.get_layout("gacha/badgeset/list")
            await layout.send(
                ctx,
                repls={
                    "current": current.display_name if current else DEFAULT_BADGE_SET,
                    "sets": [self.banner_repls(b) for b in choices],
                },
                jinja=True,
            )
            return

        query = """INSERT INTO
                       rank_card_prefs (user_id, badge_set)
                   VALUES
                       ($1, $2)
                   ON CONFLICT (user_id) DO
                   UPDATE
                   SET
                       badge_set = EXCLUDED.badge_set
                """
        await self.bot.db.execute(query, ctx.author.id, banner.name)
        layout = self.bot.get_layout("gacha/badgeset/set")
        await layout.send(ctx, repls=self.banner_repls(banner), jinja=True)

    @commands.command(name="gachagive")
    @admin_only()
    async def gachagive(self, ctx, member: discord.Member, *, item: str):
        """Give a gacha item to a member (doesn't touch pity or balance)."""
        gacha_item = self.items.get(item.lower())
        if gacha_item is None:
            await ctx.send(f"No gacha item `{item}`.")
            return

        new = gacha_item.name not in await self.owned_items(member.id)
        async with self.bot.db.acquire() as con, con.transaction():
            await self._record_item(con, member.id, gacha_item, new=new)
        await ctx.send(
            f"Gave {gacha_item.display_name} to {member.mention}"
            + ("" if new else " (duplicate, no refund given)"),
            allowed_mentions=discord.AllowedMentions.none(),
        )


async def setup(bot):
    await bot.add_cog(Gacha(bot))
