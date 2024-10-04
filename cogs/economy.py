from discord.ext import commands, menus
from discord import app_commands
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

def search_item(items: List['BaseItem'], query: str, threshold: int = 70) -> List['BaseItem']:
    results = []
    
    # Iterate over each item and compare the query to both the display_name and qualified_name
    for item in items:
        for name in item.as_list():
            similarity = fuzz.ratio(query.lower(), name.lower())
            if similarity > threshold:
                results.append((item, similarity))
                break

    # Sort results by similarity ratio in decreasing order
    results.sort(key=lambda x: x[1], reverse=True)

    # Return only the items, not the similarity scores
    return [item for item, _ in results]


class AddItemFlags(commands.FlagConverter):
    number_id: int
    name_id: str
    display_name: str
    description: str
    price: int
    stock: int = -1
    sellable: bool = True 
    tradable: bool = True

class BaseItem:
    def __init__(self, number_id: int, name_id: str, display_name: str, price: int, sell_price: Optional[int], stock: int, description: str, properties: Dict):
        self.number_id = number_id 
        self.name_id = name_id
        self.display_name = display_name
        self.price = price
        self.sell_price = sell_price if sell_price else round(price * 0.8)
        self.stock = stock
        self.description = description if description else 'No description available.'
        self.properties = properties

        self.sellable = properties.get('sellable', True)
        self.tradable = properties.get('tradable', True)
        self.perks_needed = properties.get('perks_needed', [])

    def as_list(self) -> List[str]:
        return [str(self.number_id), self.name_id, self.display_name]

    def use(self):
        raise NotImplementedError()


class WeLoveYouRoleItem(BaseItem):
    async def use(self, ctx, **kwargs):
        role = discord.Object(ctx.bot.vars.get('wly-role-id'))
        if role in ctx.author.roles:
            return False

        await ctx.author.add_roles(role)
        return True

class TestItem(BaseItem):
    async def use(self, ctx, member: discord.Member):
        await ctx.send(f'{member.mention} - test item used')
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
        emojis = []
        state = True 

        for entry in entries:
            itemnames.append(entry.display_name)
            itemdescs.append(entry.description)

            if state:
                emojis.append(self.ctx.bot.vars.get('heart-point-emoji'))
            else:
                emojis.append(self.ctx.bot.vars.get('heart-point-purple-emoji'))
            state = not state

        repls = {
            'itemnames': itemnames,
            'itemdescs': itemdescs,
            'emojis': emojis
        }
        embed = Layout.fill_embed(embed, repls, ctx=self.ctx)
        return embed

    


class QueryModal(discord.ui.Modal):
    def __init__(self, shop: 'ShopMenu'):
        super().__init__(title="Search Items")
        self.shop = shop
        self.query = discord.ui.TextInput(label="Enter your search query")

        self.add_item(self.query)

    async def on_submit(self, interaction: discord.Interaction):
        query = self.query.value
        results = search_item(self.shop.source.entries, query)

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
        self.item_classes = {
            'weloveyourole': WeLoveYouRoleItem,
            'test': TestItem
        }

    def is_verified(self, member: discord.Member):
        return member.guild.get_role(self.bot.vars.get('verified-role-id')) in member.roles

    async def cog_check(self, ctx):
        return self.is_verified(ctx.author)

    async def cog_load(self):
        query = 'SELECT * FROM shop_items'
        rows = await self.bot.db.fetch(query)
        for row in rows:
            cls = self.item_classes.get(row['name_id'])
            if cls is None:
                cls = TestItem
                # raise Exception(f'item {row["name_id"]} has no class')
            item = cls(row['number_id'], row['name_id'], row['display_name'], row['price'], row['sell_price'], row['stock'], row['description'], json.loads(row['properties']))
            self.items.append(item)

    def get_item_from_str(self, item_str: str) -> 'BaseItem':
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
        query = 'UPDATE shop_items SET stock = stock + $1 WHERE name_id = $2'
        await self.bot.db.execute(query, change, item_name_id)

    async def add_balance(self, user_id, amount):
        # update and return 
        query = 'INSERT INTO balances (user_id, balance) VALUES ($1, $2) ON CONFLICT (user_id) DO UPDATE SET balance = balances.balance + $2 RETURNING balance'
        return await self.bot.db.fetchval(query, user_id, amount)

    async def add_item(self, user_id: str, item_name_id: str, amount: int = 1):
        query = 'INSERT INTO user_items (user_id, item_name_id, amount) VALUES ($1, $2, $3) ON CONFLICT (user_id, item_name_id) DO UPDATE SET amount = user_items.amount + $3'
        await self.bot.db.execute(query, user_id, item_name_id, amount)
    
    async def remove_item(self, user_id: str, item_name_id: str, amount: int = 1):
        query = 'UPDATE user_items SET amount = user_items.amount - $3 WHERE user_id = $1 AND item_name_id = $2'
        await self.bot.db.execute(query, user_id, item_name_id, amount)
    
    async def get_balance(self, user_id):
        query = 'SELECT balance FROM balances WHERE user_id = $1'
        bal = await self.bot.db.fetchval(query, user_id)
        if bal is None:
            bal = 0

        return bal
    
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
    
    
    @commands.hybrid_command(aliases=['purchase'])
    @app_commands.describe(item='The item you want to buy')
    async def buy(self, ctx, *, item: str):
        """Buy an item from the shop"""
        item = item.lower()
        shop_item = self.get_item_from_str(item)
        if shop_item is None:

            suggestions = [it.display_name for it in search_item(self.items, item)]

            if suggestions:
                layout = self.bot.get_layout('itemsuggestions')
                await layout.send(ctx, repls={'suggestions': suggestions})
            else:
                layout = self.bot.get_layout('itemnosuggestions')
                await layout.send(ctx)
            return


        bal = await self.get_balance(ctx.author.id)

        if bal < shop_item.price or shop_item.stock == 0:
            layout = self.bot.get_layout('buy/failure')
            await layout.send(ctx)
            return 

        await self.add_balance(ctx.author.id, -shop_item.price)
        await self.add_item(ctx.author.id, shop_item.name_id)
        layout = self.bot.get_layout('buy/success')
        await layout.send(ctx, LayoutContext(message=ctx.message), repls={'item': shop_item.display_name})
    
    @commands.hybrid_command(aliases=['consume'])
    @app_commands.describe(item='The item you want to use')
    async def use(self, ctx, *, item: str):
        """Use an item in your inventory"""
        item = item.lower()
        shop_item = self.get_item_from_str(item)
        if shop_item is None:
            suggestions = [it.display_name for it in search_item(self.items, item)]

            if suggestions:
                layout = self.bot.get_layout('itemsuggestions')
                await layout.send(ctx, repls={'suggestions': suggestions})
            else:
                layout = self.bot.get_layout('itemnosuggestions')
                await layout.send(ctx)
            return
        
        query = 'SELECT amount FROM user_items WHERE user_id = $1 AND item_name_id = $2'
        amount = await self.bot.db.fetchval(query, ctx.author.id, shop_item.name_id)
        if amount is None or amount == 0:
            layout = self.bot.get_layout('usernoitem')
            await layout.send(ctx)
            return
        
        await self.remove_item(ctx.author.id, shop_item.name_id)
        await shop_item.use(ctx, ctx.author)
    
    @commands.hybrid_command(aliases=['balance'])
    @app_commands.describe(member='The member you want to check the balance of')
    async def bal(self, ctx, member: discord.Member = None):
        """Check your balance"""
        if member is None:
            member = ctx.author
        bal = await self.get_balance(member.id)
        layout = self.bot.get_layout('bal')
        await layout.send(ctx, LayoutContext(author=member), repls={'balance': bal})
    
    @commands.command(name='addbal')
    @staff_only()
    async def bal_add(self, ctx, member: discord.Member, amount: int):
        """Add balance to a user"""
        await self.add_balance(member.id, amount)
        await ctx.send(f'Added {amount}{self.lunara} to {member.mention}.')
    
    @commands.command(name='removebal')
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
        
        if not self.is_verified(msg.author):
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
    
    @commands.hybrid_command()
    @app_commands.describe(item='The item you want to view')
    async def iteminfo(self, ctx, *, item):
        item = item.lower()
        shop_item = self.get_item_from_str(item)
        if shop_item is None:
            suggestions = [it.display_name for it in search_item(self.items, item)]

            if suggestions:
                layout = self.bot.get_layout('itemsuggestions')
                await layout.send(ctx, repls={'suggestions': suggestions})
            else:
                layout = self.bot.get_layout('itemnosuggestions')
                await layout.send(ctx)
            return

        layout = self.bot.get_layout('iteminfo')


        repls = {
            'item': shop_item.display_name,
            'numberid': shop_item.number_id,
            'nameid': shop_item.name_id,
            'price': shop_item.price,
            'sellprice': shop_item.sell_price,
            'stock': '∞' if shop_item.stock == -1 else shop_item.stock,
            'istradable': 'Yes' if shop_item.tradable else 'No',
            'reqs': [],
            'desc': shop_item.description
        }
        #todo: deal with perks later
        reqs = []
        if len(reqs) == 0:
            repls['maybenone'] = 'None!'
        else:
            repls['maybenone'] = ''

        await layout.send(ctx, LayoutContext(message=ctx.message), repls=repls)

    @commands.command()
    @commands.is_owner()
    async def additem(self, ctx, *, flags: AddItemFlags):
        properties = {
            'sellable': flags.sellable,
            'tradable': flags.tradable
        }
        query = 'INSERT INTO shop_items (number_id, name_id, display_name, price, stock, properties, description) VALUES ($1, $2, $3, $4, $5, $6, $7)'
        await self.bot.db.execute(query, flags.number_id, flags.name_id, flags.display_name, flags.price, flags.stock, json.dumps(properties), flags.description)
        await ctx.send('Item added.')

    @additem.error
    async def additem_error(self, ctx, error):
        raise error


async def setup(bot):
    await bot.add_cog(Currency(bot))
