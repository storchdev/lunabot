from discord.ext import commands, menus
from discord import app_commands
import math 
import asyncio 
import discord
from typing import List, Tuple, Dict, Optional, Union
from typing import TYPE_CHECKING
import random
from ..utils import LayoutContext, Layout
from ..utils.checks import staff_only
from ..utils import RoboPages
from bot import LunaBot
import json 
from . import items
from .helpers import search_item


if TYPE_CHECKING:
    from .items import BaseItem
    from bot import LunaBot




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
    buy_reqs: str = '[]'
    sell_reqs: str = '[]'
    trade_reqs: str = '[]'


class BaseRequirement:
    def __init__(self, item: 'BaseItem', req_type: str, description: str, args: dict):
        self.item = item
        self.req_type = req_type
        self.description = description
        self.args = args
    
    def __str__(self):
        return self.description

    async def is_met(self):
        raise NotImplementedError()

class BuyRequirement(BaseRequirement):
    async def is_met(self, member: discord.Member):
        if self.req_type == 'has_role':
            role_id = self.args.get('role_id')
            role = member.guild.get_role(role_id)
            if role is None:
                return False
            return role in member.roles
        # add more  
        return False 

class SellRequirement(BaseRequirement):
    async def is_met(self, member: discord.Member):
        return True

class TradeRequirement(BaseRequirement):
    async def is_met(self, other_item: 'BaseItem', member: discord.Member, other_member: discord.Member):
        return True


class ShopPageSource(menus.ListPageSource):
    def __init__(self, ctx, items: List['BaseItem']):
        self.ctx = ctx
        super().__init__(items, per_page=5)

    async def format_page(self, menu, entries: List['BaseItem']):
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

    async def update_items(self, interaction, items: List['BaseItem']):
        new_source = ShopPageSource(self.ctx, items)
        self.source = new_source
        self.current_page = 0
        await self.show_page(interaction, self.current_page)

    @discord.ui.button(label='Search', style=discord.ButtonStyle.green)
    async def search_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = QueryModal(self)
        await interaction.response.send_modal(modal)


class Economy(commands.Cog):
    """black hole of everything economy-related"""

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
        self.categories = {}

    def is_verified(self, member: discord.Member):
        return member.guild.get_role(self.bot.vars.get('verified-role-id')) in member.roles

    async def cog_check(self, ctx):
        return self.is_verified(ctx.author)

    async def create_tables(self):
        DROP_TABLES = False
        if DROP_TABLES:
            query = 'DROP TABLE IF EXISTS user_items, shop_items, item_categories, item_reqs'
            await self.bot.db.execute(query)

        schema = '''
            CREATE TABLE IF NOT EXISTS user_items (
            id SERIAL PRIMARY KEY,
            user_id BIGINT,
            item_name_id TEXT,
            state TEXT,
            time_acquired TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS item_use_times (
            id SERIAL PRIMARY KEY,
            user_id BIGINT,
            item_name_id TEXT,
            time_used TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, item_name_id)
            );

            CREATE TABLE IF NOT EXISTS shop_items (
            name_id TEXT PRIMARY KEY,
            number_id INTEGER UNIQUE,
            display_name TEXT,
            price INTEGER,
            sell_price INTEGER,
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
            type TEXT,  --buy, sell, trade
            description TEXT,
            name TEXT,
            kwargs JSONB,
            UNIQUE(item_name_id, type, name)
            );
        '''
        await self.bot.db.execute(schema)

    async def cog_load(self):
        # sys.stderr = open('error.log', 'w')

        await self.create_tables()
        query = 'SELECT * FROM item_categories'
        rows = await self.bot.db.fetch(query)
        self.categories = {row['name']: {'display_name': row['display_name'], 'description': row['description']} for row in rows}

        query = 'SELECT * FROM shop_items'
        rows = await self.bot.db.fetch(query)

        classes = [item_cls for item_cls in items.__dict__.values() if isinstance(item_cls, type)]

        for row in rows:
            if row['category'] not in self.categories:
                raise Exception(f'item {row["name_id"]} has invalid category')

            for item_cls in classes:
                if item_cls.__name__.lower() == row['name_id']:
                    break
            else:
                item_cls = items.BaseItem

            item = item_cls(
                row['number_id'], 
                row['name_id'], 
                row['display_name'], 
                row['price'], 
                row['sell_price'], 
                row['stock'], 
                row['usable'],
                row['activatable'],
                row['category'],
                row['description'], 
                [],
                [],
                []
            )

            query = 'SELECT * FROM item_reqs WHERE item_name_id = $1'
            rows = await self.bot.db.fetch(query, item.name_id)
            for row in rows:
                if row['type'] == 'buy':
                    lst = item.buy_reqs
                    cls = BuyRequirement
                elif row['type'] == 'sell':
                    lst = item.sell_reqs
                    cls = SellRequirement
                elif row['type'] == 'trade':
                    lst = item.trade_reqs
                    cls = TradeRequirement
                else:
                    raise Exception(f'invalid req type {row["type"]}')

                lst.append(cls(
                    item, 
                    row['name'], 
                    row['description'], 
                    json.loads(row['kwargs'])
                ))

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

    async def add_item(self, user_id: str, item_name_id: str, state: str = None, amount: int = 1):
        query = 'INSERT INTO user_items (user_id, item_name_id, state) VALUES ($1, $2, $3)'
        for _ in range(amount):
            await self.bot.db.execute(query, user_id, item_name_id, state)
    
    async def remove_item(self, user_id: str, item_name_id: str, state: str = None, amount: int = 1):
        if state is None:
            query = 'DELETE FROM user_items WHERE user_id = $1 AND item_name_id = $2 LIMIT $3'
            await self.bot.db.execute(query, user_id, item_name_id, amount)
        else:
            query = 'DELETE FROM user_items WHERE user_id = $1 AND item_name_id = $2 AND state = $4 LIMIT $3'
            await self.bot.db.execute(query, user_id, item_name_id, amount, state)

    
    async def get_balance(self, user_id):
        query = 'SELECT balance FROM balances WHERE user_id = $1'
        bal = await self.bot.db.fetchval(query, user_id)
        if bal is None:
            bal = 0

        return bal
    
    async def update_item_use_time(self, user_id, item_name_id):
        query = 'INSERT INTO item_use_times (user_id, item_name_id) VALUES ($1, $2) ON CONFLICT (user_id, item_name_id) DO UPDATE SET time_used = CURRENT_TIMESTAMP'
        await self.bot.db.execute(query, user_id, item_name_id)
    
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
            
            items = search_item(self.items, item)

            if items:
                display_names = [it.display_name for it in items]
                name_ids = [it.name_id for it in items]
                layout = self.bot.get_layout('itemsuggestions')
                await layout.send(ctx, repls={
                    'displaynames': display_names, 
                    'nameids': name_ids
                })
            else:
                layout = self.bot.get_layout('itemnosuggestions')
                await layout.send(ctx)
            return

        if not await shop_item.is_buyable(ctx.author):
            await ctx.send('buy requirements layout')
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

    async def get_item_or_send_suggestions(self, ctx, item: str):
        shop_item = self.get_item_from_str(item)
        if shop_item is None:
            items = search_item(self.items, item)

            if items:
                display_names = [it.display_name for it in items]
                name_ids = [it.name_id for it in items]
                layout = self.bot.get_layout('itemsuggestions')
                await layout.send(ctx, repls={
                    'displaynames': display_names, 
                    'nameids': name_ids
                })
            else:
                layout = self.bot.get_layout('itemnosuggestions')
                await layout.send(ctx)

            return False
        return shop_item

    @commands.hybrid_command(aliases=['consume'])
    @app_commands.describe(item='The item you want to use')
    async def use(self, ctx, *, item: str):
        """Use an item in your inventory"""
        shop_item = await self.get_item_or_send_suggestions(ctx, item)

        if not shop_item.usable:
            await ctx.send('item not usable layout')
            return 

        query = 'SELECT id FROM user_items WHERE user_id = $1 AND item_name_id = $2'
        temp_id = await self.bot.db.fetchval(query, ctx.author.id, shop_item.name_id)
        if temp_id is None:
            layout = self.bot.get_layout('usernoitem')
            await layout.send(ctx)
            return
        
        await self.remove_item(ctx.author.id, shop_item.name_id)
        status = await shop_item.use(ctx)
        if status:
            await self.update_item_use_time(ctx.author.id, shop_item.name_id)
            layout = self.bot.get_layout('itemused')
            await layout.send(ctx)
    
    @commands.hybrid_command(aliases=['act'])
    @app_commands.describe(item='The item you want to activate')
    async def activate(self, ctx, *, item: str):
        shop_item = await self.get_item_or_send_suggestions(ctx, item)
        if not shop_item:
            return 

        if not shop_item.activatable:
            await ctx.send('item not activatable layout')
            return

        query = 'SELECT id FROM user_items WHERE user_id = $1 AND item_name_id = $2'
        temp_id = await self.bot.db.fetchval(query, ctx.author.id, shop_item.name_id)
        if temp_id is None:
            layout = self.bot.get_layout('usernoitem')
            await layout.send(ctx)
            return
        
        status = await shop_item.activate(ctx)
        if status:
            await self.update_item_use_time(ctx.author.id, shop_item.name_id)
            layout = self.bot.get_layout('itemactivated')
            await layout.send(ctx)
    
    @commands.hybrid_command(aliases=['deact'])
    @app_commands.describe(item='The item you want to deactivate')
    async def deactivate(self, ctx, *, item: str):
        shop_item = await self.get_item_or_send_suggestions(ctx, item)
        if not shop_item:
            return 

        if not shop_item.activatable:
            await ctx.send('item not activatable layout')
            return

        query = 'SELECT id FROM user_items WHERE user_id = $1 AND item_name_id = $2'
        temp_id = await self.bot.db.fetchval(query, ctx.author.id, shop_item.name_id)
        if temp_id is None:
            layout = self.bot.get_layout('usernoitem')
            await layout.send(ctx)
            return
        
        status = await shop_item.deactivate(ctx)
        if status:
            await self.update_item_use_time(ctx.author.id, shop_item.name_id)
            layout = self.bot.get_layout('itemdeactivated')
            await layout.send(ctx)

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
        if 1000 <= amount <= 1999:
            layout = self.bot.get_layout('drop/1kto2k')
        elif 2000 <=amount < 3999:
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
            items = search_item(self.items, item)

            if items:
                display_names = [it.display_name for it in items]
                name_ids = [it.name_id for it in items]
                layout = self.bot.get_layout('itemsuggestions')
                await layout.send(ctx, repls={
                    'displaynames': display_names, 
                    'nameids': name_ids
                })
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
            'sellprice': shop_item.sell_price if shop_item.sell_price != -1 else 'N/A',
            'stock': '∞' if shop_item.stock == -1 else shop_item.stock,
            'issellable': shop_item.is_sellable_text(),
            'istradable': shop_item.is_tradable_text(),
            'reqs': [],
            'desc': shop_item.description
        }

        if len(shop_item.buy_reqs) == 0:
            repls['maybenone'] = 'None!'
        else:
            repls['maybenone'] = ''
            shop_item['reqs'] = [str(req) for req in shop_item.buy_reqs]

        await layout.send(ctx, LayoutContext(message=ctx.message), repls=repls)

    @commands.command()
    @commands.is_owner()
    async def addcategory(self, ctx, name: str, display_name: str, description: str):
        query = 'INSERT INTO item_categories (name, display_name, description) VALUES ($1, $2, $3)'
        await self.bot.db.execute(query, name, display_name, description)
        self.categories[name] = description
        await ctx.send('Category added.')

    @commands.command()
    @commands.is_owner()
    async def additem(self, ctx, *, flags: AddItemFlags):
        if flags.category not in self.categories:
            await ctx.send('Invalid category provided.')
            return
        
        try:
            buy_reqs = json.loads(flags.buy_reqs)
            sell_reqs = json.loads(flags.sell_reqs)
            trade_reqs = json.loads(flags.trade_reqs)
        except json.JSONDecodeError:
            await ctx.send('Invalid JSON provided.')
            return

        query = 'INSERT INTO shop_items (number_id, name_id, display_name, price, sell_price, stock, usable, activatable, category, description) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)'
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
            flags.description
        )

        query = 'INSERT INTO item_reqs (item_name_id, type, name, description, kwargs) VALUES ($1, $2, $3, $4, $5)'
        for req in buy_reqs:
            await self.bot.db.execute(query, flags.name_id, 'buy', req['name'], req['description'], json.dumps(req['kwargs']))
        for req in sell_reqs:
            await self.bot.db.execute(query, flags.name_id, 'sell', req['name'], req['description'], json.dumps(req['kwargs']))
        for req in trade_reqs:
            await self.bot.db.execute(query, flags.name_id, 'trade', req['name'], req['description'], json.dumps(req['kwargs']))

        await ctx.send('Item added. Please reload the cog to see changes.')

    @additem.error
    async def additem_error(self, ctx, error):
        raise error


async def setup(bot):
    await bot.add_cog(Economy(bot))
