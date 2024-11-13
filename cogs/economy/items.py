import discord 
from discord.ext import commands 

from typing import List
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from . import (
        BuyRequirement,
        SellRequirement,
        TradeRequirement,
    )

__all__ = (
    'BaseItem',
    'CherryPop',
    'JuicyCitrus',
)


class ItemCategory:
    def __init__(self, name, display_name, description):
        self.name = name 
        self.display_name = display_name
        self.description = description


class ItemReq:
    def __init__(self, type, description, name):
        self.type = type 
        self.description = description
        self.name = name 

        if self.type == 'buy':
            self.sort_order = 0
        elif self.type == 'sell':
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
            reqs: List[ItemReq],
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
        self.description = description if description else 'No description available.'
        self.reqs = reqs
        # self.buy_reqs = buy_reqs
        # self.sell_reqs = sell_reqs
        # self.trade_reqs = trade_reqs
        self.tradable = True

        for i in range(len(self.reqs)):
            req = self.reqs[i]
            if req.type == 'trade' and req.name == 'no':
                self.tradable = False
                self.reqs.pop(i)
                break 
        
    def as_list(self) -> List[str]:
        return [str(self.number_id), self.name_id, self.display_name]

    def is_sellable_at_all(self):
        return self.sell_price != -1
        
    def is_tradable_at_all(self):
        return self.tradable
    
    async def is_buyable(self, member: discord.Member):
        return True
    
    async def is_sellable(self, member: discord.Member):
        return self.is_sellable_at_all()
    
    async def is_tradable(self, other_item: 'BaseItem', member: discord.Member, other_member: discord.Member):
        return self.is_tradable_at_all()

    async def use(self, ctx, **kwargs):
        await ctx.send(f'{ctx.author.mention} - item used')
        return True 
    
    async def activate(self, ctx, **kwargs):
        query = 'UPDATE user_items SET state = $1 WHERE user_id = $2 AND item_name_id = $3'
        await ctx.bot.db.execute(query, 'active', ctx.author.id, self.name_id)
        return True 
    
    async def deactivate(self, ctx, **kwargs):
        query = 'UPDATE user_items SET state = $1 WHERE user_id = $2 AND item_name_id = $3'
        await ctx.bot.db.execute(query, 'inactive', ctx.author.id, self.name_id)
        return True 

class ColorRoleItem(BaseItem):
    async def activate(self, ctx, **kwargs):
        await super().activate(ctx, **kwargs)

        name = kwargs.get('name')
        role = ctx.guild.get_role(ctx.bot.vars.get(f'{name}-role-id'))
        if role in ctx.author.roles:
            await ctx.send('role already activated layout')
            return False 
        await ctx.author.add_roles(role)
        return True

    async def deactivate(self, ctx, **kwargs):
        await super().deactivate(ctx, **kwargs)

        name = kwargs.get('name')
        role = ctx.guild.get_role(ctx.bot.vars.get(f'{name}-role-id'))
        if role not in ctx.author.roles:
            await ctx.send('role already deactivated layout')
            return False
        await ctx.author.remove_roles(role)
        return True


class CherryPop(ColorRoleItem):

    async def activate(self, ctx, **kwargs):
        return await super().activate(ctx, name='cherrypop')
    
    async def deactivate(self, ctx, **kwargs):
        return await super().deactivate(ctx, name='cherrypop')

class JuicyCitrus(ColorRoleItem):

    async def activate(self, ctx, **kwargs):
        return await super().activate(ctx, name='juicycitrus')
    
    async def deactivate(self, ctx, **kwargs):
        return await super().deactivate(ctx, name='juicycitrus')

class TangyLemonade(ColorRoleItem):

    async def activate(self, ctx, **kwargs):
        return await super().activate(ctx, name='tangylemonade')
    
    async def deactivate(self, ctx, **kwargs):
        return await super().deactivate(ctx, name='tangylemonade')

class ZestyLimeade(ColorRoleItem):

    async def activate(self, ctx, **kwargs):
        return await super().activate(ctx, name='zestylimeade')
    
    async def deactivate(self, ctx, **kwargs):
        return await super().deactivate(ctx, name='zestylimeade')

class BlueberryDaydream(ColorRoleItem):

    async def activate(self, ctx, **kwargs):
        return await super().activate(ctx, name='blueberrydaydream')
    
    async def deactivate(self, ctx, **kwargs):
        return await super().deactivate(ctx, name='blueberrydaydream')

class FizzyGrapeSoda(ColorRoleItem):

    async def activate(self, ctx, **kwargs):
        return await super().activate(ctx, name='fizzygrapesoda')
    
    async def deactivate(self, ctx, **kwargs):
        return await super().deactivate(ctx, name='fizzygrapesoda')

class PrettyInPink(ColorRoleItem):

    async def activate(self, ctx, **kwargs):
        return await super().activate(ctx, name='prettyinpink')
    
    async def deactivate(self, ctx, **kwargs):
        return await super().deactivate(ctx, name='prettyinpink')