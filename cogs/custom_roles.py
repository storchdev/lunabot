import json
from typing import TYPE_CHECKING

import discord
from discord.ext import commands

from cogs.vars import set_var

from .utils.checks import admin_only

if TYPE_CHECKING:
    from bot import LunaBot


def parse_hex_colours(hex1: str, hex2: str | None) -> tuple[int, int | None] | None:
    try:
        v1 = int(hex1.lstrip("#"), base=16)
        v2 = int(hex2.lstrip("#"), base=16) if hex2 is not None else None
    except ValueError:
        return None

    if not 0 <= v1 <= 0xFFFFFF:
        return None
    if v2 is not None and not 0 <= v2 <= 0xFFFFFF:
        return None

    return v1, v2


class CustomRoles(commands.Cog):
    """Custom color role creation and editing."""

    def __init__(self, bot):
        self.bot: "LunaBot" = bot

    @commands.command(
        name="edit-custom-role", aliases=["editcustomrole", "ecr", "editcr", "dni"]
    )
    async def edit_custom_role(
        self,
        ctx,
        name: str,
        hex1: str,
        hex2: str | None = None,
    ):
        """Edits the custom role linked to you."""
        parsed = parse_hex_colours(hex1, hex2)
        if parsed is None:
            return await ctx.send("Invalid hex code.")
        v1, v2 = parsed

        custom_roles = json.loads(self.bot.vars.get("custom-roles"))
        if str(ctx.author.id) not in custom_roles:
            return await ctx.send("no custom role linked to you")

        role = ctx.guild.get_role(custom_roles[str(ctx.author.id)])
        if role is None:
            return await ctx.send("custom role couldn't be found")

        if v2 is None:
            await role.edit(name=name, colour=discord.Colour(v1))
        else:
            await role.edit(
                name=name,
                colour=discord.Colour(v1),
                secondary_colour=discord.Colour(v2),
            )

        embed = discord.Embed(
            description=f"Edited {role.mention}",
            color=self.bot.DEFAULT_EMBED_COLOR,
        )
        await ctx.send(embed=embed)

    @commands.command(name="give-custom-role")
    @admin_only()
    async def give_custom_role(
        self,
        ctx,
        member: discord.Member,
        name: str,
        hex1: str,
        hex2: str | None = None,
    ):
        """Creates a new custom color role, links it to a member, and gives it to them."""
        parsed = parse_hex_colours(hex1, hex2)
        if parsed is None:
            return await ctx.send("Invalid hex code.")
        v1, v2 = parsed

        booster_role = ctx.guild.get_role(self.bot.vars.get("booster-role-id"))
        if booster_role is None:
            return await ctx.send("booster role isn't configured/found")

        kwargs = {"name": name, "colour": discord.Colour(v1)}
        if v2 is not None:
            kwargs["secondary_colour"] = discord.Colour(v2)

        role = await ctx.guild.create_role(**kwargs)
        await role.edit(position=booster_role.position + 1)
        await member.add_roles(role)

        custom_roles = json.loads(self.bot.vars.get("custom-roles"))
        custom_roles[str(member.id)] = role.id
        await set_var(self.bot, "custom-roles", json.dumps(custom_roles, indent=4))

        await ctx.send(
            f"Created and linked {role.mention} to {member.mention}, and gave it to them.",
            allowed_mentions=discord.AllowedMentions.none(),
        )


async def setup(bot):
    await bot.add_cog(CustomRoles(bot))
