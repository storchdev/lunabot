import asyncio
import json
import math
import random
import time
from datetime import timedelta
from typing import TYPE_CHECKING, Optional

import discord
from discord import app_commands
from discord.ext import commands

from ..utils import LayoutContext, next_day
from ..utils.checks import is_booster, is_tag_rep, is_vanity_rep, staff_only
from ..perks import format_lunaras
from . import items  # for automatically finding Item classes
from .inv import InvMainPages, InvMainPageSource
from .items import ItemCategory, ItemReq
from .search import search_item
from .shop import ShopMainView
from .su import EconomySu

if TYPE_CHECKING:
    from bot import LunaBot

    from .items import BaseItem

GFX_CHOICES = [
    "static banner",
    "animated banner",
    "static icon",
    "animated icon",
    "divider",
    "header",
    "text emote",
    "edit",
]

BAKING_CHOICES = [
    "cupcake",
    "cookie",
    "pie",
    "pastry",
    "croissant",
    "muffin",
    "bagel",
    "donut",
    "cheesecake",
    "cinnamon roll",
    "coffee cake",
    "carrot cake",
    "chocolate cake",
    "vanilla cake",
    "red velvet cake",
    "birthday cake",
    "cake pop",
    "loaf of bread",
    "loaf of banana bread",
    "crepe",
    "baguette",
    "pudding",
]

DRAWING_CHOICES = [
    "tree",
    "leaf",
    "car",
    "bunny",
    "kitty",
    "puppy",
    "pig",
    "bird",
    "cow",
    "horse",
    "plant",
    "jungle",
    "chair",
    "apple",
    "pear",
    "orange",
    "banana",
    "lightbulb",
    "flower",
    "building",
    "cake",
]


class AddItemFlags(commands.FlagConverter):
    number_id: int
    name_id: str
    display_name: str
    description: str
    price: int
    sell_price: Optional[int] = None
    stock: int = -1
    usable: bool
    activatable: bool
    category: str
    buy_reqs: str = "[]"
    sell_reqs: str = "[]"
    trade_reqs: str = "[]"


class Economy(commands.Cog):
    """black hole of everything economy-related"""

    def __init__(self, bot):
        self.bot: "LunaBot" = bot
        self.lunara = self.bot.vars.get("lunara")
        self.msg_count = 0
        # self.drop_active = False
        self.low_drop = 1000
        self.high_drop = 5000
        self.pick_limit = 1
        self.candy_picker_amounts: dict[discord.Member, int] = {}
        self.picker_amounts: dict[discord.Member, int] = {}
        self.drop_message: discord.Message | None = None
        self.candy_drop_msg_count = 0
        self.candy_drop_message: discord.Message | None = None
        self.items = []
        self.categories = {}
        self.skibidi = False
        self.last_edit = time.time()

    def is_verified(self, member: discord.Member):
        return (
            member.guild.get_role(self.bot.vars.get("verified-role-id")) in member.roles
        )

    async def cog_check(self, ctx):
        return self.is_verified(ctx.author)

    async def create_tables(self):
        schema = """
            CREATE TABLE IF NOT EXISTS user_items (
                id SERIAL PRIMARY KEY,
                user_id BIGINT,
                item_name_id TEXT,
                state TEXT,
                item_count INTEGER,
                time_acquired TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                time_used TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, item_name_id)
            );

            CREATE TABLE IF NOT EXISTS shop_items (
                name_id TEXT PRIMARY KEY,
                number_id INTEGER UNIQUE,
                display_name TEXT,
                price INTEGER,
                sell_price INTEGER DEFAULT NULL,
                stock INTEGER DEFAULT -1,
                usable BOOLEAN,
                activatable BOOLEAN,
                category TEXT,
                description TEXT
            );

            CREATE TABLE IF NOT EXISTS item_categories (
                name TEXT PRIMARY KEY,
                display_name TEXT,
                description TEXT
            );

            CREATE TABLE IF NOT EXISTS item_reqs( 
                item_name_id TEXT,
                type TEXT,  
                description TEXT,
                name TEXT,
                UNIQUE(item_name_id, type, name)
            );
        """
        await self.bot.db.execute(schema)

    async def cog_load(self):
        # sys.stderr = open('error.log', 'w')

        await self.create_tables()
        query = "SELECT * FROM item_categories"
        rows = await self.bot.db.fetch(query)
        self.categories = {
            row["name"]: ItemCategory(
                row["name"], row["display_name"], row["description"]
            )
            for row in rows
        }

        query = "SELECT * FROM shop_items ORDER BY number_id ASC"
        rows = await self.bot.db.fetch(query)

        classes = [
            item_cls
            for item_cls in items.__dict__.values()
            if isinstance(item_cls, type)
        ]

        fellback = []
        for row in rows:
            if row["category"] not in self.categories:
                raise Exception(f"item {row['name_id']} has invalid category")

            for item_cls in classes:
                if item_cls.__name__.lower() == row["name_id"]:
                    break
            else:
                fellback.append(row["name_id"])
                item_cls = items.BaseItem

            reqs = []
            query = "SELECT * FROM item_reqs WHERE item_name_id = $1"
            req_rows = await self.bot.db.fetch(query, row["name_id"])
            for req_row in req_rows:
                reqs.append(
                    ItemReq(req_row["type"], req_row["description"], req_row["name"])
                )

            reqs.sort(key=lambda r: r.sort_order)

            item = item_cls(
                row["number_id"],
                row["name_id"],
                row["display_name"],
                row["price"],
                row["sell_price"],
                row["stock"],
                row["usable"],
                row["activatable"],
                self.categories[row["category"]],
                row["description"],
                reqs,
            )

            self.items.append(item)

        if fellback:
            priv = self.bot.get_var_channel("private")
            await priv.send(
                f"Warning! items `{','.join(fellback)}` are not attached to a subclass"
            )

    def get_item_from_str(self, item_str: str) -> "BaseItem":
        for item in self.items:
            if item_str in item.as_list():
                return item
        return None

    async def get_stock(self, item_name_id: str):
        item = self.get_item_from_str(item_name_id)
        if item:
            return item.stock
        return None

    async def update_stock(self, item_name_id: str, change: int):
        item = self.get_item_from_str(item_name_id)
        item.stock += change
        query = "UPDATE shop_items SET stock = stock + $1 WHERE name_id = $2"
        await self.bot.db.execute(query, change, item_name_id)

    async def add_balance(self, user_id, amount):
        # update and return
        query = """INSERT INTO
                       balances (user_id, balance)
                   VALUES
                       ($1, $2)
                   ON CONFLICT (user_id) DO
                   UPDATE
                   SET
                       balance = balances.balance + $2
                   RETURNING
                       balance
                """
        return await self.bot.db.fetchval(query, user_id, amount)

    async def add_item(
        self, user_id: str, item: "BaseItem", amount: int = 1, *, update_stock=True
    ):
        if item.activatable:
            state = "inactive"
        else:
            state = None

        query = """
                    INSERT INTO user_items 
                        (user_id, item_name_id, state, item_count) 
                    VALUES ($1, $2, $3, $4) 
                    ON CONFLICT (user_id, item_name_id) DO UPDATE 
                    SET item_count = user_items.item_count + EXCLUDED.item_count
                """
        await self.bot.db.execute(query, user_id, item.name_id, state, amount)

        if update_stock:
            query = "UPDATE shop_items SET stock = stock - 1 WHERE name_id = $1 AND stock != -1"
            await self.bot.db.execute(query, item.name_id)

    async def remove_item(
        self, user_id: str, item: "BaseItem", amount: int = 1, *, update_stock=True
    ):
        query = "UPDATE user_items SET item_count = item_count - $3 WHERE user_id = $1 AND item_name_id = $2 RETURNING item_count"
        count = await self.bot.db.fetchval(query, user_id, item.name_id, amount)
        if count <= 0:
            query = "DELETE FROM user_items WHERE user_id = $1 AND item_name_id = $2"
            await self.bot.db.execute(query, user_id, item.name_id)

        if update_stock:
            query = "UPDATE shop_items SET stock = stock + 1 WHERE name_id = $1 AND stock != -1"
            await self.bot.db.execute(query, item.name_id)

    async def get_balance(self, user_id):
        query = "SELECT balance FROM balances WHERE user_id = $1"
        bal = await self.bot.db.fetchval(query, user_id)
        if bal is None:
            bal = 0

        return bal

    # Meta commands

    @commands.hybrid_command(name="inv", aliases=["inventory"])
    async def inv(self, ctx):
        """Browse your inventory."""

        query = (
            "SELECT * FROM user_items WHERE user_id = $1 ORDER BY time_acquired DESC"
        )
        rows = await self.bot.db.fetch(query, ctx.author.id)

        entries = []

        for row in rows:
            entries.append(
                {
                    "item_name_id": row["item_name_id"],
                    "count": row["item_count"],
                    "state": row["state"],
                    "time_acquired": row["time_acquired"],
                    "time_used": row["time_used"],
                    "item": self.get_item_from_str(row["item_name_id"]),
                }
            )

        source = InvMainPageSource(self.bot, entries)
        view = InvMainPages(source, ctx=ctx)
        await view.start()

    @commands.hybrid_command(name="shop")
    async def shop(self, ctx):
        """Browse the server shop."""
        view = ShopMainView(self.items, ctx=ctx)
        await ctx.send(embed=view.embed, view=view)

    @commands.hybrid_command(aliases=["purchase"])
    @app_commands.describe(item="The item you want to buy")
    async def buy(self, ctx, *, item: str):
        """Buy an item from the shop"""
        item = item.lower()
        shop_item = await self.get_item_or_send_suggestions(ctx, item)
        if not shop_item:
            return

        if not await shop_item.is_buyable(ctx.author, self.bot):
            await ctx.send("you dont have buy requirements")
            return

        if shop_item.activatable:
            query = "SELECT item_count FROM user_items WHERE user_id = $1 AND item_name_id = $2"
            count = await self.bot.db.fetchval(query, ctx.author.id, shop_item.name_id)
            if count and count >= 1:
                layout = self.bot.get_layout("you can only have one of this item")
                await layout.send(ctx)
                return

        bal = await self.get_balance(ctx.author.id)

        if bal < shop_item.price or shop_item.stock == 0:
            layout = self.bot.get_layout("buy/failure")
            await layout.send(ctx)
            return

        await self.add_item(ctx.author.id, shop_item)
        await self.add_balance(ctx.author.id, -shop_item.price)

        if shop_item.stock != -1:
            shop_item.stock -= 1

        layout = self.bot.get_layout("buy/success")
        await layout.send(
            ctx,
            LayoutContext(message=ctx.message),
            repls={"item": shop_item.display_name},
        )

    async def get_item_or_send_suggestions(
        self, ctx, item: str
    ) -> Optional["BaseItem"]:
        shop_item = self.get_item_from_str(item)
        if shop_item is None:
            items = search_item(self.items, item)

            if items:
                display_names = [it.display_name for it in items]
                name_ids = [it.name_id for it in items]
                layout = self.bot.get_layout("itemsuggestions")
                await layout.send(
                    ctx,
                    repls={
                        "items": zip(display_names, name_ids),
                    },
                    jinja=True,
                )
            else:
                layout = self.bot.get_layout("itemnosuggestions")
                await layout.send(ctx)

            return None

        return shop_item

    @commands.hybrid_command(name="sell")
    @app_commands.describe(item="The item you want to sell")
    async def sell(self, ctx, *, item: str):
        """Sell an item from your inventory"""
        shop_item = await self.get_item_or_send_suggestions(ctx, item)
        if not shop_item:
            return

        if not await shop_item.is_sellable(ctx.author):
            layout = self.bot.get_layout("sell/failure")

        query = "SELECT * FROM user_items WHERE user_id = $1 AND item_name_id = $2"
        temp = await self.bot.db.fetchval(query, ctx.author.id, shop_item.name_id)
        if temp is None:
            layout = self.bot.get_layout("usernoitem")
            await layout.send(ctx)
            return

        query = "SELECT state FROM user_items WHERE user_id = $1 AND item_name_id = $2"
        state = await self.bot.db.fetchval(query, ctx.author.id, shop_item.name_id)
        if state == "active":
            layout = self.bot.get_layout("sell/active")
            await layout.send(ctx)
            return

        await self.remove_item(ctx.author.id, shop_item)
        await self.add_balance(ctx.author.id, shop_item.sell_price)
        layout = self.bot.get_layout("sell/success")
        await layout.send(ctx)

    @commands.hybrid_command(name="use", aliases=["consume"])
    @app_commands.describe(item="The item you want to use")
    async def use(self, ctx, *, item: str):
        """Use an item in your inventory"""
        shop_item = await self.get_item_or_send_suggestions(ctx, item)
        if not shop_item:
            return

        if not shop_item.usable:
            await ctx.send("item not usable")
            return

        query = "SELECT id FROM user_items WHERE user_id = $1 AND item_name_id = $2"
        temp_id = await self.bot.db.fetchval(query, ctx.author.id, shop_item.name_id)
        if temp_id is None:
            layout = self.bot.get_layout("usernoitem")
            await layout.send(ctx)
            return

        await shop_item.use(ctx)
        await self.remove_item(ctx.author.id, shop_item)

    @commands.hybrid_command(aliases=["act"])
    @app_commands.describe(item="The item you want to activate")
    async def activate(self, ctx, *, item: str):
        """Deactivates an item (e.g. color role)"""
        shop_item = await self.get_item_or_send_suggestions(ctx, item)
        if not shop_item:
            return

        if not shop_item.activatable:
            await ctx.send("item not activatable")
            return

        query = "SELECT id FROM user_items WHERE user_id = $1 AND item_name_id = $2"
        temp_id = await self.bot.db.fetchval(query, ctx.author.id, shop_item.name_id)
        if temp_id is None:
            layout = self.bot.get_layout("usernoitem")
            await layout.send(ctx)
            return

        await shop_item.activate(ctx)

    @commands.hybrid_command(aliases=["deact"])
    @app_commands.describe(item="The item you want to deactivate")
    async def deactivate(self, ctx, *, item: str):
        """Deactivates an item (e.g. color role)"""
        shop_item = await self.get_item_or_send_suggestions(ctx, item)
        if not shop_item:
            return

        if not shop_item.activatable:
            await ctx.send("item not deactivatable")
            return

        query = "SELECT id FROM user_items WHERE user_id = $1 AND item_name_id = $2"
        temp_id = await self.bot.db.fetchval(query, ctx.author.id, shop_item.name_id)
        if temp_id is None:
            layout = self.bot.get_layout("usernoitem")
            await layout.send(ctx)
            return

        await shop_item.deactivate(ctx)

    @commands.hybrid_command(aliases=["balance"])
    @app_commands.describe(member="The member you want to check the balance of")
    async def bal(self, ctx, member: discord.Member | None = None):
        """Check your balance"""
        if member is None:
            member = ctx.author
        bal = await self.get_balance(member.id)
        layout = self.bot.get_layout("bal")
        await layout.send(ctx, LayoutContext(author=member), repls={"balance": bal})

    @commands.hybrid_command()
    @app_commands.describe(item="The item you want to view")
    async def iteminfo(self, ctx, *, item):
        item_str = item.lower()
        item = await self.get_item_or_send_suggestions(ctx, item_str)
        if item is None:
            return

        embed = self.bot.get_embed("iteminfo")

        plines = []

        arrow_r = self.bot.vars.get("arrow-r-emoji")
        pink_heart = self.bot.vars.get("heart-point-pink-emoji")
        lunara = self.bot.vars.get("lunara")
        branch_middle = self.bot.vars.get("branch-middle-emoji")
        branch_final = self.bot.vars.get("branch-final-emoji")

        arrow = pink_heart

        plines.append(f"> ⁺ {arrow}﹒{item.display_name}﹒⁺")
        plines.append(
            f"> {branch_middle} __ID: **#{item.number_id}**__ (`{item.name_id}`)"
        )

        if await item.is_sellable(ctx.author):
            sell_price = f"__{item.sell_price}__ {lunara}"
        else:
            sell_price = "__N/A__"

        plines.append(f"> {branch_middle} Sell price = {sell_price}")

        if item.stock == -1:
            stock = "∞"
        else:
            stock = str(item.stock)

        plines.append(f"> {branch_middle} Stock = __**{stock}**__")

        if item.is_sellable_at_all():
            sellable = "Yes"
        else:
            sellable = "No"

        if item.is_tradable_at_all():
            tradable = "Yes"
        else:
            tradable = "No"

        plines.append(f"> {branch_middle} Able to be sold :: {sellable}")
        plines.append(f"> {branch_middle} Able to be traded :: {tradable}")

        if item.reqs:
            plines.append(f"> {branch_middle} __Requirements:__")
            for i, req in enumerate(item.reqs):
                if i == len(item.reqs) - 1:
                    branch_emoji = branch_final
                else:
                    branch_emoji = branch_middle
                plines.append(f"> {branch_emoji} {arrow_r} {req.description}")

        # plines.append(f'> {branch_final} *{item.description}*')
        plines.append("             ‧  ╴‧  ╴‧  ╴‧")
        plines.append(f"> ⁺﹒*{item.description}*﹒⁺")
        plines.append("             ‧  ╴‧  ╴‧  ╴‧")

        embed.description = "\n".join(plines)
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="econ", aliases=["earn", "econhelp"])
    async def econ(self, ctx):
        """View all the ways to earn Lunara."""
        commands_list = sorted(
            c.name for c in self.get_commands() if c.extras.get("econ")
        )
        layout = self.bot.get_layout("econ/commands")
        await layout.send(ctx, repls={"commands": commands_list}, jinja=True)

    # Main commands

    @commands.hybrid_command(extras={"econ": True})
    async def flowerpick(self, ctx):
        """Pick flowers for a chance at some Lunara."""
        end_time = await self.bot.get_cooldown_end("flowerpick", 21600, obj=ctx.author)
        if end_time:
            layout = self.bot.get_layout("econ/flowers/cd")
            await layout.send(
                ctx, repls={"timethingy": discord.utils.format_dt(end_time, "R")}
            )
            return

        if random.random() < 0.5:
            amount = random.randint(3000, 5000)
            await self.add_balance(ctx.author.id, amount)
            layout = self.bot.get_layout("econ/flowers/good")
            await layout.send(ctx, repls={"3k-to-5k": amount})
        else:
            amount = random.randint(1000, 2000)
            await self.add_balance(ctx.author.id, -amount)
            layout = self.bot.get_layout("econ/flowers/bad")
            await layout.send(ctx, repls={"1k-to-2k": amount})

    @commands.hybrid_command(extras={"econ": True})
    async def stargaze(self, ctx):
        """Stargaze for a chance to wish upon a shooting star."""
        duration = 7 * 86400 if is_booster(ctx.author, self.bot) else 30 * 86400

        end_time = await self.bot.get_cooldown_end("stargaze", duration, obj=ctx.author)
        if end_time:
            layout = self.bot.get_layout("econ/stargaze/cd")
            await layout.send(
                ctx, repls={"timethingy": discord.utils.format_dt(end_time, "R")}
            )
            return

        amount = random.randint(60000, 90000)
        await self.add_balance(ctx.author.id, amount)
        layout = self.bot.get_layout("econ/stargaze")
        await layout.send(ctx, repls={"60k-to-90k": amount})

    @commands.hybrid_command(name="music", aliases=["vibe"], extras={"econ": True})
    async def music(self, ctx):
        """Vibe to the server's Spotify playlists for a chance at some Lunara."""
        end_time = await self.bot.get_cooldown_end("music", 3600, obj=ctx.author)
        if end_time:
            layout = self.bot.get_layout("econ/vibe/cd")
            await layout.send(
                ctx, repls={"timethingy": discord.utils.format_dt(end_time, "R")}
            )
            return

        if random.random() < 0.25:
            amount = random.randint(6000, 9000)
            await self.add_balance(ctx.author.id, amount)
            layout = self.bot.get_layout("econ/vibe/great")
            await layout.send(ctx, repls={"6k-to-9k": amount})
        else:
            amount = random.randint(3000, 5000)
            await self.add_balance(ctx.author.id, amount)
            layout = self.bot.get_layout("econ/vibe/good")
            await layout.send(ctx, repls={"3k-to-5k": amount})

    @commands.hybrid_command(extras={"econ": True})
    async def spin(self, ctx):
        """Spin a randomizer wheel for a chance at some Lunara. Boosters get 2 spins per day."""
        rate = 2 if is_booster(ctx.author, self.bot) else 1
        end_time = await self.bot.get_cooldown_end(
            "spin", 86400, rate=rate, obj=ctx.author
        )
        if end_time:
            layout = self.bot.get_layout("econ/spin/cd")
            await layout.send(
                ctx, repls={"timethingy": discord.utils.format_dt(end_time, "R")}
            )
            return

        query = "SELECT end_time FROM cooldowns WHERE action = $1 AND object_id = $2 AND bucket = 'user'"
        next_reset = await self.bot.db.fetchval(query, "spin", ctx.author.id)
        timethingy = discord.utils.format_dt(next_reset, "R")

        if random.random() < 0.75:
            amount = random.randint(1000, 5000)
            await self.add_balance(ctx.author.id, amount)
            layout = self.bot.get_layout("econ/spin/good")
            await layout.send(ctx, repls={"1k-to-5k": amount, "timethingy": timethingy})
        else:
            layout = self.bot.get_layout("econ/spin/bad")
            await layout.send(ctx, repls={"timethingy": timethingy})

    @commands.hybrid_command(extras={"econ": True})
    async def hug(self, ctx):
        """Give Luna a hug for a chance at some Lunara."""
        end_time = await self.bot.get_cooldown_end("hug", 1800, obj=ctx.author)
        if end_time:
            layout = self.bot.get_layout("econ/hug/cd")
            await layout.send(
                ctx, repls={"timethingy": discord.utils.format_dt(end_time, "R")}
            )
            return

        amount = random.randint(1500, 4000)
        await self.add_balance(ctx.author.id, amount)
        layout = self.bot.get_layout("econ/hug")
        await layout.send(ctx, repls={"1.5k-to-4k": amount})

    @commands.hybrid_command(extras={"econ": True})
    async def daily(self, ctx):
        """Claim your daily Lunara. Resets at midnight CST."""
        now = discord.utils.utcnow()
        duration = (next_day() - now).total_seconds()
        end_time = await self.bot.get_cooldown_end("daily", duration, obj=ctx.author)
        if end_time:
            layout = self.bot.get_layout("econ/daily/cd")
            await layout.send(
                ctx, repls={"timethingy": discord.utils.format_dt(end_time, "R")}
            )
            return

        await self.add_balance(ctx.author.id, 15000)

        bonus_lines = []
        if is_vanity_rep(ctx.author, self.bot):
            amount = self.bot.perk_rewards.get("vanity")
            if amount:
                await self.add_balance(ctx.author.id, amount)
                bonus_lines.append(
                    f"+ **{format_lunaras(amount)}** Lunaras for your vanity perk"
                )
        if is_tag_rep(ctx.author, self.bot):
            amount = self.bot.perk_rewards.get("tagrep")
            if amount:
                await self.add_balance(ctx.author.id, amount)
                bonus_lines.append(
                    f"+ **{format_lunaras(amount)}** Lunaras for your tag rep perk"
                )

        layout = self.bot.get_layout("econ/daily")
        timethingy = discord.utils.format_dt(now + timedelta(seconds=duration), "R")
        await layout.send(ctx, repls={"timethingy": timethingy})

        if bonus_lines:
            await ctx.send("\n".join(bonus_lines))

    @commands.hybrid_command(extras={"econ": True})
    async def event(self, ctx):
        """Join an event for a chance at a big Lunara prize."""
        duration = 14 * 86400
        now = discord.utils.utcnow()
        end_time = await self.bot.get_cooldown_end("event", duration, obj=ctx.author)
        if end_time:
            layout = self.bot.get_layout("econ/event/cd")
            await layout.send(
                ctx, repls={"timethingy": discord.utils.format_dt(end_time, "R")}
            )
            return

        timethingy = discord.utils.format_dt(now + timedelta(seconds=duration), "R")

        if random.random() < 0.25:
            amount = random.randint(30000, 40000)
            await self.add_balance(ctx.author.id, amount)
            layout = self.bot.get_layout("econ/event/great")
            await layout.send(
                ctx, repls={"30k-to-40k": amount, "timethingy": timethingy}
            )
        else:
            await self.add_balance(ctx.author.id, 10000)
            layout = self.bot.get_layout("econ/event/good")
            await layout.send(ctx, repls={"timethingy": timethingy})

    @commands.hybrid_command(extras={"econ": True})
    async def gfx(self, ctx):
        """Design some GFX for a chance at some Lunara."""
        end_time = await self.bot.get_cooldown_end("gfx", 2400, obj=ctx.author)
        if end_time:
            layout = self.bot.get_layout("econ/gfx/cd")
            await layout.send(
                ctx, repls={"timethingy": discord.utils.format_dt(end_time, "R")}
            )
            return

        amount = random.randint(2000, 3000)
        await self.add_balance(ctx.author.id, amount)
        layout = self.bot.get_layout("econ/gfx")
        await layout.send(
            ctx, repls={"2k-to-3k": amount, "gfxchoices": random.choice(GFX_CHOICES)}
        )

    @commands.hybrid_command(extras={"econ": True})
    async def bake(self, ctx):
        """Bake something delicious for some Lunara."""
        end_time = await self.bot.get_cooldown_end("bake", 1800, obj=ctx.author)
        if end_time:
            layout = self.bot.get_layout("econ/bake/cd")
            await layout.send(
                ctx, repls={"timethingy": discord.utils.format_dt(end_time, "R")}
            )
            return

        await self.add_balance(ctx.author.id, 1000)
        layout = self.bot.get_layout("econ/bake")
        await layout.send(ctx, repls={"bakingchoices": random.choice(BAKING_CHOICES)})

    @commands.hybrid_command(extras={"econ": True})
    async def draw(self, ctx):
        """Draw something creative for some Lunara."""
        end_time = await self.bot.get_cooldown_end("draw", 1800, obj=ctx.author)
        if end_time:
            layout = self.bot.get_layout("econ/draw/cd")
            await layout.send(
                ctx, repls={"timethingy": discord.utils.format_dt(end_time, "R")}
            )
            return

        await self.add_balance(ctx.author.id, 2000)
        layout = self.bot.get_layout("econ/draw")
        await layout.send(ctx, repls={"drawingchoices": random.choice(DRAWING_CHOICES)})

    @commands.hybrid_command(extras={"econ": True})
    async def paint(self, ctx):
        """Paint a scenery for a chance at some Lunara."""
        end_time = await self.bot.get_cooldown_end("paint", 1800, obj=ctx.author)
        if end_time:
            layout = self.bot.get_layout("econ/paint/cd")
            await layout.send(
                ctx, repls={"timethingy": discord.utils.format_dt(end_time, "R")}
            )
            return

        if random.random() < 0.75:
            amount = random.randint(1000, 2000)
            await self.add_balance(ctx.author.id, amount)
            layout = self.bot.get_layout("econ/paint/good")
            await layout.send(ctx, repls={"1k-to-2k": amount})
        else:
            layout = self.bot.get_layout("econ/paint/bad")
            await layout.send(ctx)

    @commands.hybrid_command()
    async def buypaint(self, ctx):
        """Buy some paint supplies."""
        end_time = await self.bot.get_cooldown_end("buypaint", 300, obj=ctx.author)
        if end_time:
            layout = self.bot.get_layout("econ/buypaint/cd")
            await layout.send(
                ctx, repls={"timethingy": discord.utils.format_dt(end_time, "R")}
            )
            return

        amount = random.randint(3000, 4000)
        await self.add_balance(ctx.author.id, -amount)
        await self.bot.reset_cooldown("paint", obj=ctx.author)
        layout = self.bot.get_layout("econ/buypaint")
        await layout.send(ctx, repls={"3k-to-4k": amount})

    # Staff

    @commands.command(name="addbal", aliases=["givebal", "baladd", "balgive"])
    @staff_only()
    async def bal_add(self, ctx, member: discord.Member, amount: int):
        """Add balance to a user"""
        await self.add_balance(member.id, amount)
        await ctx.send(f"Added {amount}{self.lunara} to {member.mention}.")

    @commands.command(name="removebal", aliases=["balremove"])
    @staff_only()
    async def bal_remove(self, ctx, member: discord.Member, amount: int):
        """Remove balance from a user"""
        await self.add_balance(member.id, -amount)
        await ctx.send(f"Removed {amount}{self.lunara} from {member.mention}.")

    # Drops

    @staticmethod
    def check_for_drop(message_count, max_messages=500, steepness=0.1, cap=0.05):
        """
        This function simulates a drop happening based on the message count.
        As the message count increases, the probability of a drop happening increases.
        Returns True if the drop happens, otherwise False.
        """
        # Sigmoid function to scale probability between 0 and 1
        probability = 1 / (
            1 + math.exp(-steepness * (message_count - max_messages / 2))
        )

        # Clamp probability to 0-1 range
        probability = min(probability, cap)

        # Randomly return True or False based on the probability
        return random.random() < probability

    async def handle_candydrop(self, msg: discord.Message):
        if self.candy_drop_message is None:

            async def task():
                self.candy_drop_msg_count += 1

                if (
                    self.check_for_drop(self.candy_drop_msg_count, 400, 0.025, 0.05)
                    or self.skibidi
                ):
                    # if True:
                    self.candy_msg_count = 0
                    self.candy_picker_amounts = {}

                    layout = self.bot.get_layout("hwn/candydrop")
                    self.candy_drop_message = await layout.send(
                        msg.channel, repls={"edited": False, "data": []}, jinja=True
                    )

                    await self.candy_drop_message.add_reaction(
                        self.bot.vars.get("candy-emoji")
                    )
                    await asyncio.sleep(30)
                    await self.candy_drop_message.delete()
                    self.candy_drop_message = None
                    self.skibidi = False

            self.bot.loop.create_task(task())

    @commands.Cog.listener()
    async def on_message(self, msg):
        if msg.author.bot:
            return

        if msg.channel.id != self.bot.vars.get("general-channel-id"):
            return

        if not self.is_verified(msg.author):
            return

        # await self.handle_candydrop(msg)  # halloween

        if not self.drop_message:

            async def task():
                self.msg_count += 1

                if self.check_for_drop(self.msg_count):
                    # if True:
                    self.msg_count = 0
                    self.picker_amounts = {}

                    layout = self.bot.get_layout("drop")
                    self.drop_message = await layout.send(
                        msg.channel, repls={"edited": False, "data": []}, jinja=True
                    )

                    await self.drop_message.add_reaction(self.bot.vars.get("lunara"))
                    await asyncio.sleep(30)
                    await self.drop_message.delete()
                    self.drop_message = None

            self.bot.loop.create_task(task())

        if "welc" in msg.content.lower():
            et = await self.bot.get_cooldown_end("welc", 60, obj=msg.author)
            if et:
                # await (self.bot.get_layout('welccd')).send(msg.channel, LayoutContext(message=msg), delete_after=7)
                return

            gained = 100
            await self.add_balance(msg.author.id, gained)

            # bal = await self.add_balance(msg.author.id, gained)
            # layout = self.bot.get_layout('welcreward')
            # await layout.send(msg.channel, LayoutContext(message=msg), repls={'gained': gained, 'balance': bal}, delete_after=7)

        et = await self.bot.get_cooldown_end("currency", 60, obj=msg.author)
        if et:
            return

        amount = random.randint(100, 300)
        await self.add_balance(msg.author.id, amount)

    # @commands.command()
    # async def pick(self, ctx):
    #     if not self.drop_active or ctx.channel.id != self.bot.vars.get('general-channel-id'):
    #         layout = self.bot.get_layout('drop/noactive')
    #         await layout.send(ctx, LayoutContext(message=ctx.message), delete_after=7)
    #         return

    #     if ctx.author.id in self.pickers:
    #         layout = self.bot.get_layout('drop/limit')
    #         await layout.send(ctx, LayoutContext(message=ctx.message), delete_after=7)
    #         return

    #     self.pickers.add(ctx.author.id)

    #     amount = random.randint(self.low_drop, self.high_drop)
    #     await self.add_balance(ctx.author.id, amount)
    #     if 1000 <= amount <= 1999:
    #         layout = self.bot.get_layout('drop/1kto2k')
    #     elif 2000 <=amount < 3999:
    #         layout = self.bot.get_layout('drop/2kto4k')
    #     else:
    #         layout = self.bot.get_layout('drop/4kto5k')

    #     msg = await layout.send(ctx, LayoutContext(message=ctx.message), repls={'amount': amount})
    #     await asyncio.sleep(10)
    #     await msg.delete()
    #     try:
    #         await ctx.message.delete()
    #     except discord.NotFound:
    #         print(f'Failed to delete {ctx.message.jump_url}')

    async def handle_candy_reaction(self, payload: discord.RawReactionActionEvent):
        if self.candy_drop_message is None:
            return
        if payload.message_id != self.candy_drop_message.id:
            return
        if payload.member in self.candy_picker_amounts:
            return

        amount = random.randint(self.low_drop, self.high_drop)
        self.candy_picker_amounts[payload.member] = amount

        query = """INSERT INTO
                     candybals (user_id, balance)
                   values
                     ($1, $2)
                   on conflict (user_id) do update
                   set
                     balance = candybals.balance + $2
                """
        await self.bot.db.execute(query, payload.user_id, amount)
        # await self.add_balance(payload.user_id, amount)

        layout = self.bot.get_layout("hwn/candydrop")

        # def amount_to_comment(amount: int):
        #     if 1000 <= amount <= 1999:
        #         return "...a low amount, but still better than nothing"
        #     elif 2000 <= amount <= 3999:
        #         return "...not a bad pick at all"
        #     else:
        #         return "...a truly impressive amount"

        amounts = list(self.candy_picker_amounts.values())

        await asyncio.sleep(self.last_edit + 1 - time.time())
        self.last_edit = time.time()  # buffer to prevent desync
        await layout.edit(
            self.candy_drop_message,
            repls={
                "data": zip(
                    [m.mention for m in self.candy_picker_amounts.keys()],
                    amounts,
                    # [amount_to_comment(a) for a in amounts],
                ),
                "edited": True,
            },
            jinja=True,
        )

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        if payload.user_id == self.bot.user.id:
            return

        # if str(payload.emoji) == self.bot.vars.get("candy-emoji"):
        #     await self.handle_candy_reaction(payload)

        if self.drop_message is None:
            return
        if payload.message_id != self.drop_message.id:
            return
        if str(payload.emoji) != self.bot.vars.get("lunara"):
            return

        if payload.member in self.picker_amounts:
            return

        amount = random.randint(self.low_drop, self.high_drop)
        self.picker_amounts[payload.member] = amount
        await self.add_balance(payload.user_id, amount)

        layout = self.bot.get_layout("drop")

        def amount_to_comment(amount: int):
            if 1000 <= amount <= 1999:
                return "...a low amount, but still better than nothing"
            elif 2000 <= amount <= 3999:
                return "...not a bad pick at all"
            else:
                return "...a truly impressive amount"

        amounts = list(self.picker_amounts.values())

        await layout.edit(
            self.drop_message,
            repls={
                "data": zip(
                    [m.mention for m in self.picker_amounts.keys()],
                    amounts,
                    [amount_to_comment(a) for a in amounts],
                ),
                "edited": True,
            },
            jinja=True,
        )

    @commands.command()
    async def candylb(self, ctx):
        return

        rows = await self.bot.db.fetch(
            "SELECT * FROM candybals ORDER BY balance DESC LIMIT 3"
        )
        mybal = await self.bot.db.fetchval(
            "SELECT balance FROM candybals WHERE user_id = $1", ctx.author.id
        )

        if mybal is None:
            mybal = 0

        myplace = (
            await self.bot.db.fetchval(
                "SELECT COUNT(*) FROM candybals WHERE balance > $1", mybal
            )
            + 1
        )

        repls = {"place": myplace, "balance": mybal}

        for i, row in enumerate(rows):
            repls[f"mention{i + 1}"] = f"<@{row['user_id']}>"

        for mentionn in [1, 2, 3]:
            if f"mention{mentionn}" not in repls:
                repls[f"mention{mentionn}"] = "N/A"

        layout = self.bot.get_layout("hwn/candylb")
        await layout.send(ctx, repls=repls)

    @commands.command()
    @commands.is_owner()
    async def addcategory(self, ctx, name: str, display_name: str, description: str):
        query = """INSERT INTO
                       item_categories (name, display_name, description)
                   VALUES
                       ($1, $2, $3)
                """
        await self.bot.db.execute(query, name, display_name, description)
        self.categories[name] = description
        await ctx.send("Category added.")

    @commands.command()
    @commands.is_owner()
    async def additem(self, ctx, *, flags: AddItemFlags):
        if flags.category not in self.categories:
            await ctx.send("Invalid category provided.")
            return

        try:
            buy_reqs = json.loads(flags.buy_reqs)
            sell_reqs = json.loads(flags.sell_reqs)
            trade_reqs = json.loads(flags.trade_reqs)
        except json.JSONDecodeError:
            await ctx.send("Invalid JSON provided.")
            return

        query = """INSERT INTO
                       shop_items (
                           number_id,
                           name_id,
                           display_name,
                           price,
                           sell_price,
                           stock,
                           usable,
                           activatable,
                           category,
                           description
                       )
                   VALUES
                       ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                """
        await self.bot.db.execute(
            query,
            flags.number_id,
            flags.name_id,
            flags.display_name,
            flags.price,
            flags.sell_price,
            flags.stock,
            flags.usable,
            flags.activatable,
            flags.category,
            flags.description,
        )

        query = "INSERT INTO item_reqs (item_name_id, type, name, description, kwargs) VALUES ($1, $2, $3, $4, $5)"
        for req in buy_reqs:
            await self.bot.db.execute(
                query,
                flags.name_id,
                "buy",
                req["name"],
                req["description"],
                json.dumps(req["kwargs"]),
            )
        for req in sell_reqs:
            await self.bot.db.execute(
                query,
                flags.name_id,
                "sell",
                req["name"],
                req["description"],
                json.dumps(req["kwargs"]),
            )
        for req in trade_reqs:
            await self.bot.db.execute(
                query,
                flags.name_id,
                "trade",
                req["name"],
                req["description"],
                json.dumps(req["kwargs"]),
            )

        await ctx.send("Item added. Please reload the cog to see changes.")


async def setup(bot):
    await bot.add_cog(Economy(bot))
    # await bot.add_cog(EconomySu(bot))
