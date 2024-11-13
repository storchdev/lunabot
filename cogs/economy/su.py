from discord.ext import commands 
from typing import Optional, TYPE_CHECKING
import json 

if TYPE_CHECKING:
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


class EconomySu(commands.Cog):
    def __init__(self, bot):
        self.bot: 'LunaBot' = bot 

    async def cog_check(self, ctx):
        return ctx.author.id in self.bot.owner_ids

    @commands.command()
    async def addcategory(self, ctx, name: str, display_name: str, description: str):
        query = 'INSERT INTO item_categories (name, display_name, description) VALUES ($1, $2, $3)'
        await self.bot.db.execute(query, name, display_name, description)
        self.categories[name] = description
        await ctx.send('Category added.')

    @commands.command()
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

    @commands.command()
    async def droptables(self, ctx, *tables):
        query = f'DROP TABLE {",".join(tables)}'
        result = await self.bot.db.execute(query)
        await ctx.send(result)
    
    @commands.command()
    async def insertitems(self, ctx):
        data = [
            (
               '<@&983832932743512166>' ,
                'cherrypop',
                'A vibrant pop of cherry red! Gives you a color role with the hex #ff4961',
                500000,
                -1,
                400000,
                [
                    ('trade', 'Only able to be traded for other color roles that are NOT perk limited'),
                ],
                'color_roles',
                False,
                True,
            ),
            (
               '<@&987445973565472768>',
                'juicycitrus',
                'A bright orange, much like a citrus! Gives you a color role with the hex #ff7a55',
                500000,
                -1,
                400000,
                [
                    ('trade', 'Only able to be traded for other color roles that are NOT perk limited'),
                ],
                'color_roles',
                False,
                True,
            ),
            (
               '<@&1217667555628552222>' ,
                'tangylemonade',
                'A nice refreshing glass of yellow lemonade! Gives you a color role with the hex #ffcb6a',
                500000,
                -1,
                400000,
                [
                    ('trade', 'Only able to be traded for other color roles that are NOT perk limited'),
                ],
                'color_roles',
                False,
                True,
            ),
            (
               '<@&1217667588486594571>' ,
                'zestylimeade',
                'A nice refreshing glass of green limeade! Gives you a color role with the hex #6dff8d',
                500000,
                -1,
                400000,
                [
                    ('trade', 'Only able to be traded for other color roles that are NOT perk limited'),
                ],
                'color_roles',
                False,
                True,
            ),
            (
               '<@&989736151726317589>' ,
                'blueberrydaydream',
                'A burst of dazzling blue, reminiscent of a blueberry! Gives you a color role with the hex #5794ff',
                500000,
                -1,
                400000,
                [
                    ('trade', 'Only able to be traded for other color roles that are NOT perk limited'),
                ],
                'color_roles',
                False,
                True,
            ),
            (
               '<@&989747430507569212>' ,
                'fizzygrapesoda',
                'A fizzling glass of purple grape soda! Gives you a color role with the hex #9c69f',
                500000,
                -1,
                400000,
                [
                    ('trade', 'Only able to be traded for other color roles that are NOT perk limited'),
                ],
                'color_roles',
                False,
                True,
            ),
            (
               '<@&989747431178661908>' ,
                'prettyinpink',
                'A beautiful dash of pink! Gives you a color role with the hex #9c69ff',
                500000,
                -1,
                400000,
                [
                    ('trade', 'Only able to be traded for other color roles that are NOT perk limited'),
                ],
                'color_roles',
                False,
                True,
            ),
        ]
        i = 1
        for displayname, nameid, desc, price, stock, sellprice, reqs, category, usable, actble in data:
            query = 'INSERT INTO shop_items (name_id, number_id, display_name, price, sell_price, stock, usable, activatable, category, description) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)'
            await self.bot.db.execute(query, nameid, i, displayname, price, sellprice, stock, usable, actble, category, desc)

            for req_type, req_desc in reqs:
                query = 'INSERT INTO item_reqs (item_name_id, type, description) VALUES ($1,$2,$3)'
                await self.bot.db.execute(query, nameid, req_type,req_desc)

            i += 1
        
        await ctx.send('done')