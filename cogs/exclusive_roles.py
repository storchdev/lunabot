from discord.ext import commands
from collections import defaultdict


class ExclusiveRoles(commands.Cog):
    """The description for ExclusiveRoles goes here."""

    def __init__(self, bot):
        self.bot = bot
        self.groups = defaultdict(lambda: defaultdict(set))
        self.group_lookup = defaultdict(dict)

    async def cog_load(self):
        query = "SELECT * FROM exclusive_roles"
        for row in await self.bot.db.fetch(query):
            guild_id = row["guild_id"]
            role_id = row["role_id"]
            group_name = row["group_name"]

            self.groups[guild_id][group_name].add(role_id)
            self.group_lookup[guild_id][role_id] = group_name

    async def cog_check(self, ctx):
        return ctx.author.guild_permissions.administrator

    @commands.Cog.listener()
    async def on_member_update(self, before, after):
        guild_id = after.guild.id

        added_roles = set(after.roles) - set(before.roles)

        to_remove = []

        for role in added_roles:
            role_id = role.id
            group_name = self.group_lookup[guild_id].get(role_id)

            if group_name:
                group_roles = self.groups[guild_id][group_name]

                # Check how many roles from the group the member has
                member_roles_in_group = [r for r in after.roles if r.id in group_roles]

                if len(member_roles_in_group) > 1:
                    # Violation occurred
                    to_remove.append(role)

        if to_remove:
            await after.remove_roles(*to_remove)
            self.bot.log(
                f"removed the following roles from {after}: {[r.name for r in to_remove]}",
                "exclusive_roles",
            )


async def setup(bot):
    await bot.add_cog(ExclusiveRoles(bot))
