import asyncio 
import math 
import random

import discord
from discord import app_commands
from discord.ext import commands 

from ..utils import LayoutContext
from ..utils.checks import staff_only

from . import items  # for automatically finding Item classes

from .items import ItemCategory, ItemReq
from .inv import InvMainPageSource, InvMainPages
from .search import search_item 
from .shop import ShopMainView
from .su import EconomySu

from typing import Optional
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .items import BaseItem
    from bot import LunaBot



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
        schema = '''
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
        '''
        await self.bot.db.execute(schema)

    async def cog_load(self):
        # sys.stderr = open('error.log', 'w')

        await self.create_tables()
        query = 'SELECT * FROM item_categories'
        rows = await self.bot.db.fetch(query)
        self.categories = {
            row["name"]: ItemCategory(
                row["name"],
                row["display_name"],
                row["description"]
            ) 
            for row in rows
        }

        query = 'SELECT * FROM shop_items ORDER BY number_id ASC'
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
            
            reqs = []
            query = 'SELECT * FROM item_reqs WHERE item_name_id = $1'
            req_rows = await self.bot.db.fetch(query, row["name_id"])
            for req_row in req_rows:
                reqs.append(ItemReq(req_row["type"], req_row["description"], req_row["name"]))
            
            reqs.sort(key=lambda r: r.sort_order )

            item = item_cls(
                row['number_id'], 
                row['name_id'], 
                row['display_name'], 
                row['price'], 
                row['sell_price'], 
                row['stock'], 
                row['usable'],
                row['activatable'],
                self.categories[row['category']],
                row['description'], 
                reqs,
            )
            
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

    async def add_item(self, user_id: str, item: 'BaseItem', amount: int = 1, *, update_stock=True):
        if item.activatable:
            state = "inactive"
        else:
            state = None

        query = '''
                    INSERT INTO user_items 
                        (user_id, item_name_id, state, item_count) 
                    VALUES ($1, $2, $3, $4) 
                    ON CONFLICT (user_id, item_name_id) DO UPDATE 
                    SET item_count = user_items.item_count + EXCLUDED.item_count
                '''
        await self.bot.db.execute(query, user_id, item.name_id, state, amount)

        if update_stock:
            query = "UPDATE shop_items SET stock = stock - 1 WHERE name_id = $1 AND stock != -1"
            await self.bot.db.execute(query, item.name_id)
    
    async def remove_item(self, user_id: str, item: 'BaseItem', amount: int = 1, *, update_stock=True):
        query = "UPDATE user_items SET item_count = item_count - $3 WHERE user_id = $1 AND item_name_id = $2 RETURNING item_count"
        count = await self.bot.db.fetchval(query, user_id, item.name_id, amount)
        if count <= 0:
            query = "DELETE FROM user_items WHERE user_id = $1 AND item_name_id = $2"
            await self.bot.db.execute(query, user_id, item.name_id)
        
        if update_stock:
            query = "UPDATE shop_items SET stock = stock + 1 WHERE name_id = $1 AND stock != -1"
            await self.bot.db.execute(query, item.name_id)

    
    async def get_balance(self, user_id):
        query = 'SELECT balance FROM balances WHERE user_id = $1'
        bal = await self.bot.db.fetchval(query, user_id)
        if bal is None:
            bal = 0

        return bal
    
    async def update_item_use_time(self, user_id, item_name_id):
        query = """INSERT INTO
                       item_use_times (user_id, item_name_id)
                   VALUES
                       ($1, $2)
                   ON CONFLICT (user_id, item_name_id) DO
                   UPDATE
                   SET
                       time_used = CURRENT_TIMESTAMP
                """
        await self.bot.db.execute(query, user_id, item_name_id)

    # User commands / slash commands 

    @commands.hybrid_command(name='inv', aliases=['inventory'])
    async def inv(self, ctx):
        """Browse your inventory."""

        query = "SELECT * FROM user_items WHERE user_id = $1 ORDER BY time_acquired DESC"
        rows = await self.bot.db.fetch(query, ctx.author.id)

        entries = []

        for row in rows:
            entries.append({
                "item_name_id": row["item_name_id"],
                "count": row["item_count"],
                "state": row["state"],
                "time_acquired": row["time_acquired"],
                "time_used": row["time_used"],
                "item": self.get_item_from_str(row["item_name_id"]),
            })

        source = InvMainPageSource(self.bot, entries)
        view = InvMainPages(source, ctx=ctx)
        await view.start()

    @commands.hybrid_command(name='shop')
    async def shop(self, ctx):
        """Browse the server shop."""
        view = ShopMainView(self.items, ctx=ctx)
        await ctx.send(embed=view.embed, view=view)
    
    @commands.hybrid_command(aliases=['purchase'])
    @app_commands.describe(item='The item you want to buy')
    async def buy(self, ctx, *, item: str):
        """Buy an item from the shop"""
        item = item.lower()
        shop_item = await self.get_item_or_send_suggestions(ctx, item)
        if not shop_item:
            return

        if not await shop_item.is_buyable(ctx.author):
            await ctx.send('you dont have buy requirements')
            return 

        if shop_item.activatable:
            query = 'SELECT item_count FROM user_items WHERE user_id = $1 AND item_name_id = $2'
            count = await self.bot.db.fetchval(query, ctx.author.id, shop_item.name_id)
            if count and count >= 1:
                layout = self.bot.get_layout('you can only have one of this item')
                await layout.send(ctx)
                return

        bal = await self.get_balance(ctx.author.id)

        if bal < shop_item.price or shop_item.stock == 0:
            layout = self.bot.get_layout('buy/failure')
            await layout.send(ctx)
            return 
        
        await self.add_item(ctx.author.id, shop_item)
        await self.add_balance(ctx.author.id, -shop_item.price)
        
        if shop_item.stock != -1:
            shop_item.stock -= 1
        
        layout = self.bot.get_layout('buy/success')
        await layout.send(ctx, LayoutContext(message=ctx.message), repls={'item': shop_item.display_name})

    async def get_item_or_send_suggestions(self, ctx, item: str)-> Optional['BaseItem']:
        shop_item = self.get_item_from_str(item)
        if shop_item is None:
            items = search_item(self.items, item)

            if items:
                display_names = [it.display_name for it in items]
                name_ids = [it.name_id for it in items]
                layout = self.bot.get_layout('itemsuggestions')
                await layout.send(ctx, repls={
                    "items": zip(display_names, name_ids),
                }, jinja=True)
            else:
                layout = self.bot.get_layout('itemnosuggestions')
                await layout.send(ctx)

            return None 

        return shop_item

    @commands.hybrid_command(name='sell')
    @app_commands.describe(item='The item you want to sell')
    async def sell(self, ctx, *, item: str):
        """Sell an item from your inventory"""
        shop_item = await self.get_item_or_send_suggestions(ctx, item)
        if not shop_item:
            return

        if not await shop_item.is_sellable(ctx.author):
            layout = self.bot.get_layout('sell/failure')

        query = 'SELECT * FROM user_items WHERE user_id = $1 AND item_name_id = $2'
        temp = await self.bot.db.fetchval(query, ctx.author.id, shop_item.name_id)
        if temp is None:
            layout = self.bot.get_layout('usernoitem')
            await layout.send(ctx)
            return
        
        query = 'SELECT state FROM user_items WHERE user_id = $1 AND item_name_id = $2'
        state = await self.bot.db.fetchval(query, ctx.author.id, shop_item.name_id)
        if state == 'active':
            layout = self.bot.get_layout('sell/active')
            await layout.send(ctx)
            return

        await self.remove_item(ctx.author.id, shop_item)
        await self.add_balance(ctx.author.id, shop_item.sell_price)
        layout = self.bot.get_layout('sell/success')
        await layout.send(ctx)
    
    @commands.hybrid_command(name='use', aliases=['consume'])
    @app_commands.describe(item='The item you want to use')
    async def use(self, ctx, *, item: str):
        """Use an item in your inventory"""
        shop_item = await self.get_item_or_send_suggestions(ctx, item)
        if not shop_item:
            return

        if not shop_item.usable:
            await ctx.send('item not usable')
            return 

        query = 'SELECT id FROM user_items WHERE user_id = $1 AND item_name_id = $2'
        temp_id = await self.bot.db.fetchval(query, ctx.author.id, shop_item.name_id)
        if temp_id is None:
            layout = self.bot.get_layout('usernoitem')
            await layout.send(ctx)
            return
        
        await self.remove_item(ctx.author.id, shop_item)
        status = await shop_item.use(ctx)
        if status:
            await self.update_item_use_time(ctx.author.id, shop_item.name_id)
            layout = self.bot.get_layout('itemused')
            await layout.send(ctx)
    
    @commands.hybrid_command(aliases=['act'])
    @app_commands.describe(item='The item you want to activate')
    async def activate(self, ctx, *, item: str):
        """Deactivates an item (e.g. color role)"""
        shop_item = await self.get_item_or_send_suggestions(ctx, item)
        if not shop_item:
            return 

        if not shop_item.activatable:
            await ctx.send('item not activatable')
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
        """Deactivates an item (e.g. color role)"""
        shop_item = await self.get_item_or_send_suggestions(ctx, item)
        if not shop_item:
            return 

        if not shop_item.activatable:
            await ctx.send('item not activatable')
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
    
    @commands.hybrid_command()
    @app_commands.describe(item='The item you want to view')
    async def iteminfo(self, ctx, *, item):
        item_str = item.lower()
        item = await self.get_item_or_send_suggestions(ctx, item_str)
        if item is None:
            return

        embed = self.bot.get_embed('iteminfo')

        plines = []

        arrow_r = self.bot.vars.get('arrow-r-emoji')
        pink_heart = self.bot.vars.get('heart-point-pink-emoji')
        lunara = self.bot.vars.get('lunara')
        branch_middle = self.bot.vars.get('branch-middle-emoji')
        branch_final = self.bot.vars.get('branch-final-emoji')

        arrow = pink_heart 

        plines.append(f'> ⁺ {arrow}﹒{item.display_name}﹒⁺')
        plines.append(f'> {branch_middle} __ID: **#{item.number_id}**__ (`{item.name_id}`)')

        if await item.is_sellable(ctx.author):
            sell_price = f'__{item.sell_price}__ {lunara}'
        else:
            sell_price = '__N/A__'

        plines.append(f'> {branch_middle} Sell price = {sell_price}')

        if item.stock == -1:
            stock = '∞'
        else:
            stock = str(item.stock)

        plines.append(f'> {branch_middle} Stock = __**{stock}**__')

        if item.is_sellable_at_all():
            sellable = "Yes"
        else:
            sellable = "No"

        if item.is_tradable_at_all():
            tradable = "Yes"
        else:
            tradable = "No"

        plines.append(f'> {branch_middle} Able to be sold :: {sellable}')
        plines.append(f'> {branch_middle} Able to be traded :: {tradable}')

        if item.reqs:
            plines.append(f'> {branch_middle} __Requirements:__')
            for i, req in enumerate(item.reqs):
                if i == len(item.reqs) - 1:
                    branch_emoji = branch_final
                else:
                    branch_emoji = branch_middle
                plines.append(f'> {branch_emoji} {arrow_r} {req.description}')
         
        # plines.append(f'> {branch_final} *{item.description}*')
        plines.append('             ‧  ╴‧  ╴‧  ╴‧')
        plines.append(f'> ⁺﹒*{item.description}*﹒⁺')
        plines.append('             ‧  ╴‧  ╴‧  ╴‧')

        embed.description = '\n'.join(plines)
        await ctx.send(embed=embed)

    # Staff 

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
    
    # Drops

    @staticmethod
    def check_for_drop(message_count, max_messages=150, steepness=0.1, cap=0.05):
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
        try:
            await ctx.message.delete()
        except discord.NotFound:
            print(f'Failed to delete {ctx.message.jump_url}')


async def setup(bot):
    await bot.add_cog(Economy(bot))
    await bot.add_cog(EconomySu(bot))
