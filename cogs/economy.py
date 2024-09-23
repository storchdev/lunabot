from discord.ext import commands, menus
import math 
import asyncio 
import discord
from typing import List, Tuple, Dict, Optional, Union
from typing import TYPE_CHECKING
import random
from .utils import LayoutContext, Layout
from .utils.checks import staff_only
import time
from fuzzywuzzy import fuzz
from .utils import RoboPages
from bot import LunaBot
import json 


if TYPE_CHECKING:
    from bot import LunaBot


class BaseItem:
    def __init__(self, id: int, name_id: str, display_name: str, price: int, properties: Dict):
        self.id = id 
        self.name_id = name_id
        self.display_name = display_name
        self.price = price
        self.properties = properties

        self.description = properties.get('description', 'No description available.')
        self.sellable = properties.get('sellable', True)
        self.tradable = properties.get('tradable', True)
        self.perks_needed = properties.get('perks_needed', [])

    def as_list(self) -> List[str]:
        return [self.name_id, self.display_name]

    def use(self, **kwargs):
        raise NotImplementedError()


class WeLoveYouRoleItem(BaseItem):
    async def use(self, ctx, member: discord.Member):
        role = discord.Object(ctx.bot.vars.get('wly-role-id'))
        if role in member.roles:
            return False

        await member.add_roles(role)
        return True


class ShopPageSource(menus.ListPageSource):
    def __init__(self, ctx, items: List[BaseItem]):
        self.ctx = ctx
        super().__init__(items, per_page=5)

    async def format_page(self, menu, entries: List[BaseItem]):
        embed = self.ctx.bot.embeds.get('shop')
        if not embed:
            return "No shop embed found."

        itemnames = []
        itemdescs = []
        for entry in entries:
            itemnames.append(entry.display_name)
            itemdescs.append(entry.description)

        embed = Layout.fill_embed(embed, {'itemnames': itemnames, 'itemdescs': itemdescs}, ctx=self.ctx)
        return embed

    def fuzzy_find(self, query: str, threshold: int = 70) -> List[BaseItem]:
        results = []
        
        # Iterate over each item and compare the query to both the display_name and qualified_name
        for item in self.entries:
            for name in item.as_list():
                similarity = fuzz.ratio(query.lower(), name.lower())
                if similarity > threshold:
                    results.append((item, similarity))
                    break

        # Sort results by similarity ratio in decreasing order
        results.sort(key=lambda x: x[1], reverse=True)

        # Return only the items, not the similarity scores
        return [item for item, _ in results]


class QueryModal(discord.ui.Modal):
    def __init__(self, shop: 'ShopMenu'):
        super().__init__(title="Search Items")
        self.shop = shop
        self.query = discord.ui.TextInput(label="Enter your search query")

        self.add_item(self.query)

    async def on_submit(self, interaction: discord.Interaction):
        query = self.query.value
        results = self.shop.source.fuzzy_find(query)
        if results:
            await interaction.response.send_message(f"Found {len(results)} item(s) matching '{query}':", ephemeral=True)
            await self.shop.update_items(interaction, results)
        else:
            await interaction.response.send_message(f"No items found matching '{query}'.", ephemeral=True)


class ShopMenu(RoboPages):
    def __init__(self, source: ShopPageSource, ctx):
        super().__init__(source, ctx=ctx)
        self.add_item(self.search_button)

    async def update_items(self, interaction, items: List[BaseItem]):
        new_source = ShopPageSource(self.ctx, items)
        self.source = new_source
        self.current_page = 0
        await self.show_page(interaction, self.current_page)

    @discord.ui.button(label='Search', style=discord.ButtonStyle.green)
    async def search_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = QueryModal(self)
        await interaction.response.send_modal(modal)


class Currency(commands.Cog):
    """The description for Currency goes here."""

    def __init__(self, bot):
        self.bot: 'LunaBot' = bot
        self.lunara = self.bot.vars.get('lunara')
        self.msg_count = 0
        self.drop_active = False
        self.low_drop = 1000 
        self.high_drop = 5000
        self.pick_limit = 1
        self.pickers = set()
        self.items = []
    
    async def cog_load(self):
        classes = {
            'weloveyourole': WeLoveYouRoleItem
        }

        query = 'SELECT * FROM shop_items'
        rows = await self.bot.db.fetch(query)
        for row in rows:
            cls = classes.get(row['name_id'], BaseItem)
            item = cls(row['id'], row['name_id'], row['display_name'], row['price'], json.loads(row['properties']))
            self.items.append(item)

    async def add_balance(self, user_id, amount):
        # update and return 
        query = 'INSERT INTO balances (user_id, balance) VALUES ($1, $2) ON CONFLICT (user_id) DO UPDATE SET balance = balances.balance + $2 RETURNING balance'
        return await self.bot.db.fetchval(query, user_id, amount)


    @commands.hybrid_command()
    async def shop(self, ctx):
        """View the shop"""
        itemnames = []
        itemdescs = []
        for item in self.items:
            itemnames.append(item.display_name)
            itemdescs.append(item.description)

        menu = ShopMenu(ShopPageSource(ctx, self.items), ctx)
        await menu.start()
    
    @commands.hybrid_group(aliases=['balance'])
    async def bal(self, ctx, member: discord.Member = None):
        """Check your balance"""
        if member is None:
            member = ctx.author
        # initialize balance if not exists    
        await self.add_balance(member.id, 0)
        layout = self.bot.get_layout('bal')
        query = 'SELECT balance FROM balances WHERE user_id = $1'
        bal = await self.bot.db.fetchval(query, member.id)
        await layout.send(ctx, LayoutContext(author=member), repls={'balance': bal})
    
    @bal.command(name='add')
    @staff_only()
    async def bal_add(self, ctx, member: discord.Member, amount: int):
        """Add balance to a user"""
        await self.add_balance(member.id, amount)
        await ctx.send(f'Added {amount}{self.lunara} to {member.mention}.')
    
    @bal.command(name='remove')
    @staff_only()
    async def bal_remove(self, ctx, member: discord.Member, amount: int):
        """Remove balance from a user"""
        await self.add_balance(member.id, -amount)
        await ctx.send(f'Removed {amount}{self.lunara} from {member.mention}.')

    
    @staticmethod
    def check_for_drop(message_count, max_messages=100, steepness=0.1, cap=0.1):
        """
        This function simulates a drop happening based on the message count. 
        As the message count increases, the probability of a drop happening increases.
        Returns True if the drop happens, otherwise False.
        """

        # Sigmoid function to scale probability between 0 and 1
        probability = 1 / (1 + math.exp(-steepness * (message_count - max_messages/2)))

        # Clamp probability to 0-1 range
        probability = min(probability, cap)

        # Randomly return True or False based on the probability
        return random.random() < probability
        
    @commands.Cog.listener()
    async def on_message(self, msg):
        if msg.author.bot:
            return
        
        if msg.channel.id != self.bot.vars.get('general-channel-id'):
            return 

        if not self.drop_active: 
            self.msg_count += 1

        if self.check_for_drop(self.msg_count):
            self.msg_count = 0 
            self.pickers.clear()
            layout = self.bot.get_layout('drop') 
            temp = await layout.send(msg.channel, LayoutContext(message=msg), repls={'low': self.low_drop, 'high': self.high_drop})
            self.drop_active = True
            await asyncio.sleep(30)
            self.drop_active = False
            await temp.delete()
                    
        if 'welc' in msg.content.lower():
            et = await self.bot.get_cooldown_end('welc', 60, obj=msg.author)
            if et:
                await (self.bot.get_layout('welccd')).send(msg.channel, LayoutContext(message=msg), delete_after=7)
                return

            gained = 100 
            bal = await self.add_balance(msg.author.id, gained)
            layout = self.bot.get_layout('welcreward')
            await layout.send(msg.channel, LayoutContext(message=msg), repls={'gained': gained, 'balance': bal}, delete_after=7) 

        et = await self.bot.get_cooldown_end('currency', 60, obj=msg.author)
        if et:
            return
        
        amount = random.randint(100, 300)
        await self.add_balance(msg.author.id, amount)

    @commands.command()
    async def pick(self, ctx):
        if not self.drop_active or ctx.channel.id != self.bot.vars.get('general-channel-id'):
            layout = self.bot.get_layout('drop/noactive')
            await layout.send(ctx, LayoutContext(message=ctx.message), delete_after=7)
            return 

        if ctx.author.id in self.pickers:
            layout = self.bot.get_layout('drop/limit')
            await layout.send(ctx, LayoutContext(message=ctx.message), delete_after=7)
            return

        self.pickers.add(ctx.author.id)

        amount = random.randint(self.low_drop, self.high_drop)
        await self.add_balance(ctx.author.id, amount)
        if 1000<=amount<=1999:
            layout = self.bot.get_layout('drop/1kto2k')
        elif 2000<=amount<3999:
            layout = self.bot.get_layout('drop/2kto4k')
        else:
            layout = self.bot.get_layout('drop/4kto5k')

        msg = await layout.send(ctx, LayoutContext(message=ctx.message), repls={'amount': amount})
        await asyncio.sleep(10)
        await msg.delete()
        await ctx.message.delete()
    

        


async def setup(bot):
    await bot.add_cog(Currency(bot))
