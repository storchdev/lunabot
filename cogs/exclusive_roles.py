from collections import defaultdict
from typing import TYPE_CHECKING

from discord.ext import commands

if TYPE_CHECKING:
    from bot import LunaBot

from cogs.utils import RoleSelectView, SimplePages
import discord
from typing import List


class ExclusiveRoles(commands.Cog):
    """The description for ExclusiveRoles goes here."""

    def __init__(self, bot):
        self.bot: "LunaBot" = bot
        self.groups = defaultdict(lambda: defaultdict(set))
        self.group_lookup = defaultdict(dict)

        self.clean_progress = 0
        self.total_members = 0

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

    async def clean_member(
        self, member: discord.Member, roles: List[discord.Role]
    ) -> List[discord.Role]:
        to_remove = []

        for role in roles:
            role_id = role.id
            group_name = self.group_lookup[member.guild.id].get(role_id)

            if group_name:
                group_roles = self.groups[member.guild.id][group_name]

                # Check how many roles from the group the member has
                member_roles_in_group = [r for r in member.roles if r.id in group_roles]

                if len(member_roles_in_group) > 1:
                    # Violation occurred
                    to_remove.append(role)

        if to_remove:
            await member.remove_roles(*to_remove)
            self.bot.log(
                f"removed the following roles from {member}: {[r.name for r in to_remove]}",
                "exclusive_roles",
            )
            return to_remove
        else:
            return []

    @commands.Cog.listener()
    async def on_member_update(self, before, after):
        added_roles = set(after.roles) - set(before.roles)
        await self.clean_member(after, added_roles)

    @commands.hybrid_group(
        name="exclusive-roles",
        aliases=["exclusiveroles", "er"],
        invoke_without_command=True,
    )
    async def er(self, ctx: commands.Context):
        await ctx.send_help(ctx.command)

    @er.command(name="list", aliases=["all"])
    async def er_list(self, ctx):
        if ctx.guild.id not in self.groups:
            return await ctx.send("this server has no exclusive role groups")

        group_names = self.groups[ctx.guild.id].keys()
        group_names_fmt = [f"`{n}`" for n in group_names]

        v = SimplePages(group_names_fmt, ctx=ctx)
        await v.start()

    @er.command(name="view")
    async def er_view(self, ctx, *, name: str):
        name = name.lower()

        if name not in self.groups[ctx.guild.id]:
            return await ctx.send(
                "that exclusive role group does not exist in this server"
            )

        role_ids = self.groups[ctx.guild.id][name]
        role_fmt = []

        for rid in role_ids:
            r = ctx.guild.get_role(rid)
            if r is None:
                role_fmt.append(f"Unknown role (ID={rid})")
            else:
                role_fmt.append(r.mention)

        v = SimplePages(role_fmt, ctx=ctx)
        await v.start()

    @er.command(name="add", aliases=["create"])
    async def er_add(self, ctx, *, name: str):
        name = name.lower()

        if name in self.groups[ctx.guild.id]:
            return await ctx.send(
                "that exclusive role group already exists in this server"
            )

        v = RoleSelectView()
        bot_msg = await ctx.send(
            "Select the roles that are part of this group:", view=v
        )
        await v.wait()

        if v.final_interaction is None:
            await bot_msg.delete()
            return

        role_ids = [r.id for r in v.roles]

        for role_id in role_ids:
            self.groups[ctx.guild.id][name].add(role_id)
            self.group_lookup[ctx.guild.id][role_id] = name

        query = """INSERT INTO
                     exclusive_roles (guild_id, group_name, role_id)
                   VALUES
                     ($1, $2, $3)
                """

        values = [(ctx.guild.id, name, rid) for rid in role_ids]
        await self.bot.db.executemany(query, values)

        await v.final_interaction.response.edit_message(
            content=f"added exclusive role group `{name}`"
        )

    @er.command(name="remove", aliases=["delete"])
    async def er_remove(self, ctx, *, name: str):
        name = name.lower()

        if name not in self.groups[ctx.guild.id]:
            return await ctx.send(
                "that exclusive role group doesn't exist in this server"
            )

        role_ids = self.groups[ctx.guild.id].pop(name)

        for role_id in role_ids:
            self.group_lookup[ctx.guild.id].pop(role_id, None)

        query = """DELETE FROM exclusive_roles
                   WHERE
                     guild_id = $1
                     AND group_name = $2
                """
        await self.bot.db.execute(query, ctx.guild.id, name)

        await ctx.send(f"Removed exclusive role group `{name}`")

    @er.command(name="edit", aliases=["update"])
    async def er_edit(self, ctx, *, name: str):
        name = name.lower()

        if name not in self.groups[ctx.guild.id]:
            return await ctx.send(
                "that exclusive role group doesn't exist in this server"
            )

        v = RoleSelectView()
        bot_msg = await ctx.send(
            "Select the new roles that are part of this group (will override old setting):",
            view=v,
        )
        await v.wait()

        if v.final_interaction is None:
            await bot_msg.delete()
            return

        new_role_ids = [r.id for r in v.roles]
        old_role_ids = self.groups[ctx.guild.id][name]

        for role_id in old_role_ids:
            self.group_lookup[ctx.guild.id].pop(role_id, None)

        self.groups[ctx.guild.id][name] = set(new_role_ids)

        for role_id in new_role_ids:
            self.group_lookup[ctx.guild.id][role_id] = name

        delete_query = """DELETE FROM exclusive_roles
                          WHERE
                            guild_id = $1
                            AND group_name = $2
                       """
        await self.bot.db.execute(delete_query, ctx.guild.id, name)

        insert_query = """INSERT INTO
                            exclusive_roles (guild_id, group_name, role_id)
                          VALUES
                            ($1, $2, $3)
                       """
        values = [(ctx.guild.id, name, rid) for rid in new_role_ids]
        await self.bot.db.executemany(insert_query, values)

        await v.final_interaction.response.edit_message(
            content=f"updated exclusive role group `{name}`"
        )

    @er.command(name="cleanserver")
    async def er_scanserver(self, ctx):
        num_roles = 0
        num_members = 0
        self.total_members = len(ctx.guild.members)

        await ctx.send("Cleaning... do `!er csp` to see progress")

        for member in ctx.guild.members:
            num_cleaned = len(await self.clean_member(member, member.roles))
            if num_cleaned > 0:
                num_roles += num_cleaned
                num_members += 1
            self.clean_progress += 1

        self.clean_progress = 0
        await ctx.send(f"Removed {num_roles} roles from {num_members} members")

    @er.command(name="cleanserverprogress", aliases=["csp"])
    async def er_csp(self, ctx):
        if self.clean_progress == 0:
            return await ctx.send("no cleaning happening right now")

        total = self.total_members
        p = self.clean_progress / total * 100
        await ctx.send(f"{self.clean_progress}/{total} ({p:.0f}%)")


async def setup(bot):
    await bot.add_cog(ExclusiveRoles(bot))
