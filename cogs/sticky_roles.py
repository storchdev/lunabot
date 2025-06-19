from typing import TYPE_CHECKING

from discord.ext import commands

if TYPE_CHECKING:
    from bot import LunaBot


class StickyRoles(commands.Cog):
    """The description for StickyRoles goes here."""

    def __init__(self, bot):
        self.bot: "LunaBot" = bot

    @commands.Cog.listener()
    async def on_member_join(self, member):
        query = "SELECT role_id FROM sticky_roles WHERE user_id = $1 AND until > NOW()"
        rows = await self.bot.db.fetch(query, member.id)
        for row in rows:
            role = member.guild.get_role(row["role_id"])
            await member.add_roles(role)


async def setup(bot):
    await bot.add_cog(StickyRoles(bot))
