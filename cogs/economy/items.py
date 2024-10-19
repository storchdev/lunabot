import discord 
from discord.ext import commands 

from typing import List
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from . import BuyRequirement, SellRequirement, TradeRequirement


__all__ = (
    'BaseItem',
    'CherryPop',
)

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
            category: str, 
            description: str,
            buy_reqs: List['BuyRequirement'],
            sell_reqs: List['SellRequirement'],
            trade_reqs: List['TradeRequirement'],
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
        self.buy_reqs = buy_reqs
        self.sell_reqs = sell_reqs
        self.trade_reqs = trade_reqs
        
    def as_list(self) -> List[str]:
        return [str(self.number_id), self.name_id, self.display_name]

    def is_sellable_text(self):
        if len(self.sell_reqs) == 0: 
            if self.sell_price != -1:
                return 'Yes'
            else:
                return 'No'
        
        return '; '.join([str(req) for req in self.sell_reqs])
    
    def is_tradable_text(self):
        if len(self.trade_reqs) == 0:
            return 'Yes'
        
        return '; '.join([str(req) for req in self.trade_reqs])

    async def is_buyable(self, member: discord.Member):
        for req in self.buy_reqs:
            if not await req.is_met(member):
                return False
        return True
    
    async def is_sellable(self, member: discord.Member):
        if self.sell_price == -1:
            return False

        for req in self.sell_reqs:
            if not await req.is_met(member):
                return False
        return True
    
    async def is_tradable(self, other_item: 'BaseItem', member: discord.Member, other_member: discord.Member):
        for req in self.trade_reqs:
            if not await req.is_met(other_item, member, other_member):
                return False
        return True

    async def use(self, ctx, **kwargs):
        await ctx.send(f'{ctx.author.mention} - base item used')
        return True 
    
    async def activate(self, ctx, **kwargs):
        await ctx.send(f'{ctx.author.mention} - base item activated')
        return True 
    
    async def deactivate(self, ctx, **kwargs):
        await ctx.send(f'{ctx.author.mention} - base item deactivated')
        return True 

class ColorRoleItem(BaseItem):
    async def activate(self, ctx, **kwargs):
        name = kwargs.get('name')
        role = ctx.guild.get_role(ctx.bot.vars.get(f'{name}-role-id'))
        if role in ctx.author.roles:
            await ctx.send('role already activated layout')
            return False 
        await ctx.author.add_roles(role)
        return True

    async def deactivate(self, ctx, **kwargs):
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