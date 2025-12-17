from typing import TYPE_CHECKING

import discord
from discord.ext import commands

from cogs.tickets import create_ticket

if TYPE_CHECKING:
    from bot import LunaCtx


class ItemCategory:
    def __init__(self, name: str, display_name: str, description: str):
        self.name = name
        self.display_name = display_name
        self.description = description


class ItemReq:
    def __init__(self, type: str, description: str, name: str):
        self.type = type
        self.description = description
        self.name = name

        if self.type == "buy":
            self.sort_order = 0
        elif self.type == "sell":
            self.sort_order = 1
        else:
            self.sort_order = 2


class BaseItem:
    def __init__(
        self,
        number_id: int,
        name_id: str,
        display_name: str,
        price: int,
        sell_price: int,
        stock: int,
        usable: bool,
        activatable: bool,
        category: ItemCategory,
        description: str,
        reqs: list[ItemReq],
        # buy_reqs: List['BuyRequirement'],
        # sell_reqs: List['SellRequirement'],
        # trade_reqs: List['TradeRequirement'],
    ):
        self.number_id = number_id
        self.name_id = name_id
        self.display_name = display_name
        self.price = price
        self.sell_price = sell_price if sell_price else round(price * 0.8)
        self.stock = stock
        self.usable = usable
        self.activatable = activatable
        self.category = category
        self.description = description if description else "No description available."
        self.reqs = reqs
        # self.buy_reqs = buy_reqs
        # self.sell_reqs = sell_reqs
        # self.trade_reqs = trade_reqs
        self.tradable = True

        for i in range(len(self.reqs)):
            req = self.reqs[i]
            if req.type == "trade" and req.name == "no":
                self.tradable = False
                self.reqs.pop(i)
                break

    def as_list(self) -> list[str]:
        return [str(self.number_id), self.name_id, self.display_name]

    def is_sellable_at_all(self) -> bool:
        return self.sell_price != -1

    def is_tradable_at_all(self) -> bool:
        return self.tradable

    async def is_buyable(self, member: discord.Member) -> bool:
        return True

    async def is_sellable(self, member: discord.Member) -> bool:
        return self.is_sellable_at_all()

    async def is_tradable(
        self,
        other_item: "BaseItem",
        member: discord.Member,
        other_member: discord.Member,
    ) -> bool:
        return self.is_tradable_at_all()

    async def use(self, ctx: "LunaCtx", **kwargs):
        await self.update_item_use_time(ctx)

        # handled in command
        # query = "UPDATE user_items SET item_count = item_count - 1 WHERE user_id = $1 AND item_name_id = $2 RETURNING item_count"
        # count = await ctx.bot.db.execute(query, ctx.author.id, self.name_id)
        # if count == 0:
        #     query = "DELETE FROM user_items WHERE user_id = $1 AND item_name_id = $2"
        #     await ctx.bot.db.execute(query, ctx.author.id, self.name_id)

        lyname = kwargs.get("layout_name") or "itemused"
        lyrepls = kwargs.get("repls") or {}
        layout = ctx.bot.get_layout(lyname)
        await layout.send(ctx, repls=lyrepls)

    async def update_item_use_time(self, ctx: "LunaCtx"):
        query = """INSERT INTO
                       item_use_times (user_id, item_name_id)
                   VALUES
                       ($1, $2)
                   ON CONFLICT (user_id, item_name_id) DO
                   UPDATE
                   SET
                       time_used = CURRENT_TIMESTAMP
                """
        await ctx.bot.db.execute(query, ctx.author.id, self.name_id)

    async def activate(self, ctx: "LunaCtx", **kwargs):
        query = """UPDATE user_items
                   SET
                     state = $1
                   WHERE
                     user_id = $2
                     AND item_name_id = $3
                """
        await ctx.bot.db.execute(query, "active", ctx.author.id, self.name_id)

        await self.update_item_use_time(ctx)

        lyname = kwargs.get("layout_name") or "itemactivated"
        lyrepls = kwargs.get("repls") or {}
        layout = ctx.bot.get_layout(lyname)
        await layout.send(ctx, repls=lyrepls)

    async def deactivate(self, ctx: "LunaCtx", **kwargs):
        query = (
            "UPDATE user_items SET state = $1 WHERE user_id = $2 AND item_name_id = $3"
        )
        await ctx.bot.db.execute(query, "inactive", ctx.author.id, self.name_id)

        lyname = kwargs.get("layout_name") or "itemdeactivated"
        lyrepls = kwargs.get("repls") or {}
        layout = ctx.bot.get_layout(lyname)
        await layout.send(ctx, repls=lyrepls)


# Class names MUST match the item_name_id in the database! (not case sensitive)


class ShoutoutItem(BaseItem):
    KIND = None

    async def use(self, ctx, **kwargs):
        end = await ctx.bot.get_cooldown_end("useshoutout", 30 * 86400, obj=ctx.author)
        if end is not None and ctx.author.id != ctx.bot.owner_id:
            raise commands.CommandOnCooldown(
                commands.Cooldown(1, 30 * 86400),
                (end - discord.utils.utcnow()).total_seconds(),
                commands.BucketType.user,
            )

        async with ctx.typing():
            ticket = await create_ticket(
                ctx.bot,
                ctx.author,
                f"Shoutout (`@{self.KIND}`)",
                opening_layout_name="shoutoutticket",
            )

        await super().use(
            ctx,
            layout_name="itemactivated/shoutout",
            repls={"link": ticket.thread.jump_url},
        )


class EveryoneShoutout(ShoutoutItem):
    KIND = "everyone"


class HereShoutout(ShoutoutItem):
    KIND = "here"


class ColorRoleItem(BaseItem):
    async def activate(self, ctx, **kwargs):
        name = kwargs.get("name")
        role = ctx.guild.get_role(ctx.bot.vars.get(f"{name}-role-id"))
        if role in ctx.author.roles:
            await ctx.send("role already activated layout")
            return

        await super().activate(ctx, **kwargs)
        await ctx.author.add_roles(role)

    async def deactivate(self, ctx, **kwargs):
        name = kwargs.get("name")
        role = ctx.guild.get_role(ctx.bot.vars.get(f"{name}-role-id"))
        if role not in ctx.author.roles:
            await ctx.send("role already deactivated layout")
            return

        await super().deactivate(ctx, **kwargs)
        await ctx.author.remove_roles(role)


class CherryPop(ColorRoleItem):
    async def activate(self, ctx, **kwargs):
        return await super().activate(ctx, name="cherrypop")

    async def deactivate(self, ctx, **kwargs):
        return await super().deactivate(ctx, name="cherrypop")


class JuicyCitrus(ColorRoleItem):
    async def activate(self, ctx, **kwargs):
        return await super().activate(ctx, name="juicycitrus")

    async def deactivate(self, ctx, **kwargs):
        return await super().deactivate(ctx, name="juicycitrus")


class TangyLemonade(ColorRoleItem):
    async def activate(self, ctx, **kwargs):
        return await super().activate(ctx, name="tangylemonade")

    async def deactivate(self, ctx, **kwargs):
        return await super().deactivate(ctx, name="tangylemonade")


class ZestyLimeade(ColorRoleItem):
    async def activate(self, ctx, **kwargs):
        return await super().activate(ctx, name="zestylimeade")

    async def deactivate(self, ctx, **kwargs):
        return await super().deactivate(ctx, name="zestylimeade")


class BlueberryDaydream(ColorRoleItem):
    async def activate(self, ctx, **kwargs):
        return await super().activate(ctx, name="blueberrydaydream")

    async def deactivate(self, ctx, **kwargs):
        return await super().deactivate(ctx, name="blueberrydaydream")


class FizzyGrapeSoda(ColorRoleItem):
    async def activate(self, ctx, **kwargs):
        return await super().activate(ctx, name="fizzygrapesoda")

    async def deactivate(self, ctx, **kwargs):
        return await super().deactivate(ctx, name="fizzygrapesoda")


class PrettyInPink(ColorRoleItem):
    async def activate(self, ctx, **kwargs):
        return await super().activate(ctx, name="prettyinpink")

    async def deactivate(self, ctx, **kwargs):
        return await super().deactivate(ctx, name="prettyinpink")
