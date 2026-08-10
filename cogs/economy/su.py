from typing import TYPE_CHECKING

from discord.ext import commands

if TYPE_CHECKING:
    from bot import LunaBot


class EconomySu(commands.Cog):
    """Owner-only economy debug commands (drop tables, bulk-insert shop items)."""

    def __init__(self, bot):
        self.bot: "LunaBot" = bot

    async def cog_check(self, ctx):
        return ctx.author.id in self.bot.owner_ids

    @commands.command()
    async def droptables(self, ctx, *tables):
        query = f"DROP TABLE {','.join(tables)}"
        result = await self.bot.db.execute(query)
        await ctx.send(result)

    @commands.command()
    async def insertitems(self, ctx):
        data = [
            (
                "<@&983832932743512166>",
                "cherrypop",
                "A vibrant pop of cherry red! Gives you a color role with the hex #ff4961",
                500000,
                -1,
                400000,
                [
                    (
                        "trade",
                        "Only able to be traded for other color roles that are NOT perk limited",
                    ),
                ],
                "color_roles",
                False,
                True,
            ),
            (
                "<@&987445973565472768>",
                "juicycitrus",
                "A bright orange, much like a citrus! Gives you a color role with the hex #ff7a55",
                500000,
                -1,
                400000,
                [
                    (
                        "trade",
                        "Only able to be traded for other color roles that are NOT perk limited",
                    ),
                ],
                "color_roles",
                False,
                True,
            ),
            (
                "<@&1217667555628552222>",
                "tangylemonade",
                "A nice refreshing glass of yellow lemonade! Gives you a color role with the hex #ffcb6a",
                500000,
                -1,
                400000,
                [
                    (
                        "trade",
                        "Only able to be traded for other color roles that are NOT perk limited",
                    ),
                ],
                "color_roles",
                False,
                True,
            ),
            (
                "<@&1217667588486594571>",
                "zestylimeade",
                "A nice refreshing glass of green limeade! Gives you a color role with the hex #6dff8d",
                500000,
                -1,
                400000,
                [
                    (
                        "trade",
                        "Only able to be traded for other color roles that are NOT perk limited",
                    ),
                ],
                "color_roles",
                False,
                True,
            ),
            (
                "<@&989736151726317589>",
                "blueberrydaydream",
                "A burst of dazzling blue, reminiscent of a blueberry! Gives you a color role with the hex #5794ff",
                500000,
                -1,
                400000,
                [
                    (
                        "trade",
                        "Only able to be traded for other color roles that are NOT perk limited",
                    ),
                ],
                "color_roles",
                False,
                True,
            ),
            (
                "<@&989747430507569212>",
                "fizzygrapesoda",
                "A fizzling glass of purple grape soda! Gives you a color role with the hex #9c69f",
                500000,
                -1,
                400000,
                [
                    (
                        "trade",
                        "Only able to be traded for other color roles that are NOT perk limited",
                    ),
                ],
                "color_roles",
                False,
                True,
            ),
            (
                "<@&989747431178661908>",
                "prettyinpink",
                "A beautiful dash of pink! Gives you a color role with the hex #9c69ff",
                500000,
                -1,
                400000,
                [
                    (
                        "trade",
                        "Only able to be traded for other color roles that are NOT perk limited",
                    ),
                ],
                "color_roles",
                False,
                True,
            ),
        ]
        i = 1
        for (
            displayname,
            nameid,
            desc,
            price,
            stock,
            sellprice,
            reqs,
            category,
            usable,
            actble,
        ) in data:
            query = """INSERT INTO
                           shop_items (
                               name_id,
                               number_id,
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
                nameid,
                i,
                displayname,
                price,
                sellprice,
                stock,
                usable,
                actble,
                category,
                desc,
            )

            for req_type, req_desc in reqs:
                query = """INSERT INTO
                               item_reqs (item_name_id, type, description)
                           VALUES
                               ($1, $2, $3)
                        """
                await self.bot.db.execute(query, nameid, req_type, req_desc)

            i += 1

        await ctx.send("done")
