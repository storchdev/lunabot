import json
import logging
from datetime import datetime
from io import StringIO
from typing import TYPE_CHECKING, Optional

import discord
from discord import ui
from discord.ext import commands, tasks

from .utils import View, admin_only, staff_only

if TYPE_CHECKING:
    from bot import LunaBot, LunaCtx


class Ticket:
    def __init__(
        self,
        opener: discord.Member,
        timestamp: datetime,
        id: Optional[int] = None,
        thread: Optional[discord.Thread] = None,
    ):
        self.opener = opener
        self.timestamp = timestamp
        self.id: Optional[int] = id
        self.thread: Optional[discord.Thread] = thread


async def create_ticket(
    bot: "LunaBot",
    creator: discord.Member,
    reason: str,
    *,
    opening_layout_name: str = "ticketinfo",
) -> Ticket:
    bot.log(f"create_ticket called by {creator} ({creator.id})", "ticket")

    ticket = Ticket(creator, discord.utils.utcnow())

    query = "UPDATE ticket_counter SET num = num + 1 RETURNING num"
    ticket_id = await bot.db.fetchval(query)

    ticket.id = ticket_id

    helpdesk = bot.get_var_channel("helpdesk")
    ticket.thread = await helpdesk.create_thread(
        name=f"Ticket {ticket_id}",
        type=discord.ChannelType.private_thread,
        invitable=False,
    )

    bot.log(f"thread created with id {ticket_id}", "ticket")

    await bot.get_layout(opening_layout_name).send(ticket.thread)

    try:
        await ticket.thread.add_user(creator)
        bot.log(f"added {creator} ({creator.id}) to Ticket {ticket_id}", "ticket")
    except Exception as e:
        await ticket.thread.send(
            f"I failed to add {creator.mention} to this ticket normally. "
            "Maybe pinging fixed it, or Storch will need to investigate."
        )
        logging.error(
            f"failed to add {creator} ({creator.id}) to Ticket {ticket_id}. Error: {e}"
        )

    query = """INSERT INTO
                    active_tickets (ticket_id, channel_id, opener_id, timestamp)
                VALUES
                    ($1, $2, $3, $4)
            """
    await bot.db.execute(
        query,
        ticket.id,
        ticket.thread.id,
        ticket.opener.id,
        ticket.timestamp.timestamp(),
    )
    # view = CloseView(bot, ticket.id, ticket.channel, ticket.opener.id, ticket.timestamp)

    luna_id = bot.vars.get("luna-id")
    pm_id = bot.vars.get("pm-role-id")
    staff_id = bot.vars.get("staff-role-id")
    molly_id = 675058943596298340

    if reason == "VIP Artist":
        pings = f"<@{luna_id}> <@{molly_id}>"
    elif reason == "Trusted Seller":
        pings = f"<@{luna_id}> <@{molly_id}>"
    elif reason == "Partnership Request":
        pings = f"<@&{pm_id}>"
    elif reason == "PM Request":
        pings = f"<@{luna_id}>"
    elif reason == "Booster Perks":
        pings = f"<@{luna_id}>"
    elif reason == "User Report":
        pings = f"<@&{staff_id}>"
    elif reason == "General Inquiry":
        pings = f"<@&{staff_id}>"
    elif reason == "Other":
        pings = f"<@&{staff_id}>"
    elif "Shoutout" in reason:
        pings = f"<@{luna_id}>"
    else:
        pings = f"<@{bot.owner_id}>"

    log_channel = bot.get_channel(bot.vars.get("archive-channel-id"))

    layout = bot.get_layout("ticket/opened")
    repls = {
        "user": creator.mention,
        "ID": ticket.id,
        "reason": reason,
        "thread": ticket.thread.mention,
        "mention": pings,
    }

    await layout.send(log_channel, repls=repls, special=False)
    return ticket


class TicketView(ui.View):
    def __init__(self, bot, *, button: Optional[ui.Button] = None):
        super().__init__(timeout=None)
        self.bot: "LunaBot" = bot

        if button:
            self.open_ticket.label = button.label
            self.open_ticket.emoji = button.emoji
            self.open_ticket.style = button.style

    @ui.button(label="joe", custom_id="helpdeskv2")
    async def open_ticket(self, interaction, button):
        menu = TicketTypeMenu(self.bot, interaction.user)
        await interaction.response.send_message(
            "**Please select an option from the menu**", view=menu, ephemeral=True
        )


class TicketTypeMenu(View):
    def __init__(self, bot, owner):
        super().__init__(bot=bot, owner=owner)

        for option in [
            "VIP Artist",
            "Trusted Seller",
            "PM Request",
            "Booster Perks",
            "User Report",
            "General Inquiry",
            "Other",
        ]:
            self.ticket_type.add_option(label=option)

        if owner.id in self.bot.owner_ids:
            self.ticket_type.add_option(label="test")

    async def interaction_check(self, inter):
        end_time = await self.bot.get_cooldown_end("ticket", 60, obj=inter.user)
        if end_time:
            layout = self.bot.get_layout("ticketcd")
            await layout.send(
                inter,
                None,
                ephemeral=True,
                repls={"timethingy": discord.utils.format_dt(end_time, "R")},
            )
            return False

        return True

    @ui.select(placeholder="What is this ticket for?")
    async def ticket_type(self, interaction, select):
        await interaction.response.edit_message(
            content="Please wait a moment...", view=None
        )
        ticket = await create_ticket(self.bot, self.owner, select.values[0])
        embed = discord.Embed(
            title="New Ticket",
            color=self.bot.DEFAULT_EMBED_COLOR,
            description=f"Opened a new ticket: {ticket.thread.mention}",
        )
        msg = await interaction.original_response()
        await msg.edit(content=None, embed=embed)


REMIND_GAP = 86400 * 7


class TicketCog(commands.Cog, name="Tickets v2", description="thread tickets"):
    def __init__(self, bot):
        self.bot: "LunaBot" = bot

    async def cog_load(self):
        self.bot.add_view(TicketView(self.bot))
        self.remind_inactive.start()

    async def cog_unload(self):
        self.remind_inactive.cancel()

    @tasks.loop(hours=1)
    async def remind_inactive(self):
        rows = await self.bot.db.fetch("SELECT * FROM active_tickets")
        for row in rows:
            channel = self.bot.get_channel(row["channel_id"])

            if channel is None:
                query = "DELETE FROM active_tickets WHERE channel_id = $1"
                await self.bot.db.execute(query, row["channel_id"])
                continue

            assert isinstance(channel, discord.Thread)

            hist = [msg async for msg in channel.history(limit=1, oldest_first=False)]
            if len(hist) == 0:
                self.bot.log(f"message history for {channel.jump_url} empty", "ticket")
                continue

            last_msg = hist[0]
            if (discord.utils.utcnow() - last_msg.created_at).total_seconds() < 86400:
                continue
            if (
                row["remind_after"] is None
                or row["remind_after"] > discord.utils.utcnow()
            ):
                continue

            layout = self.bot.get_layout("ticketreminder")
            # pings = [u.mention for u in await channel.fetch_members()]
            await layout.send(channel, repls={"pings": "@everyone"})

            query = "UPDATE active_tickets SET remind_after = $1 WHERE channel_id = $2"
            await self.bot.db.execute(
                query,
                None,
                channel.id,
            )

    async def get_txt_file(self, ticket_id):
        query = "SELECT messages FROM ticket_transcripts WHERE ticket_id = $1"
        row = await self.bot.db.fetchrow(query, ticket_id)
        if not row:
            return None
        msgs = json.loads(row["messages"])
        output = StringIO()
        for msg in msgs:
            output.write(f"{msg['username']} ({msg['author_id']}): {msg['content']}\n")
            for a in msg["attachments"]:
                output.write(f"  {a}\n")
            output.write("\n")

        output.seek(0)
        return discord.File(output, filename=f"transcript-{ticket_id}.txt")

    # async def cog_check(self, ctx):
    #     return ctx.author.id == self.bot.owner_id or ctx.author.guild_permissions.administrator

    @commands.command()
    @staff_only()
    async def transcript(self, ctx, ticket_id: int):
        file = await self.get_txt_file(ticket_id)
        if file is None:
            helpdesk = self.bot.get_var_channel("helpdesk")
            await ctx.send(
                f"No transcript found for that ticket. Check the threads in {helpdesk.mention}?"
            )
            return
        await ctx.send(file=file)

    @commands.command()
    @admin_only()
    async def sendticketembed(
        self, ctx, channel: discord.TextChannel, *, embed_name: str
    ):
        embed_name = embed_name.lower()
        if embed_name not in self.bot.embeds:
            await ctx.send(f"Embed `{embed_name}` not found!")
            return

        button = ui.Button(
            label="❀﹒﹒Click me!﹒﹒❀",
            emoji="<a:Lumi_heart_float:924048498477891614>",
            style=discord.ButtonStyle.blurple,
        )
        view = TicketView(self.bot, button=button)
        await channel.send(embed=self.bot.get_embed(embed_name), view=view)

    @commands.command()
    @staff_only()
    async def close(self, ctx: commands.Context, *, reason: str):
        query = "SELECT * FROM active_tickets WHERE channel_id = $1"
        row = await self.bot.db.fetchrow(query, ctx.channel.id)
        if row is None:
            await ctx.send("This command can only be used in an open ticket thread!")
            return

        assert isinstance(ctx.channel, discord.Thread)

        query = "DELETE FROM active_tickets WHERE channel_id = $1"
        await self.bot.db.execute(query, ctx.channel.id)

        await ctx.send("Ticked closed!")
        await ctx.channel.edit(archived=True, locked=True)

        repls = {
            "ID": row["ticket_id"],
            "thread": ctx.channel.mention,
            "user": f"<@!{row['opener_id']}>",
            "mod": ctx.author.mention,
            "reason": reason,
        }
        archive = self.bot.get_var_channel("archive")

        if not isinstance(archive, discord.TextChannel):
            return await ctx.send("Archive channel not found.")

        layout = self.bot.get_layout("ticket/closed")
        await layout.send(archive, repls=repls)

    @commands.command()
    @staff_only()
    async def extend(self, ctx: "LunaCtx", *, time: str):
        query = "SELECT * FROM active_tickets WHERE channel_id = $1"
        row = await self.bot.db.fetchrow(query, ctx.channel.id)
        if row is None:
            await ctx.send("This command can only be used in an open ticket thread!")
            return

        dt = await ctx.parse_dt(time)
        if dt is None:
            return await ctx.send("You did not enter a valid time!")
        if dt < discord.utils.utcnow():
            return await ctx.send("You can only enter a *future* time!")

        query = "UPDATE active_tickets SET remind_after = $1 WHERE channel_id = $2"
        await self.bot.db.execute(query, dt, ctx.channel.id)
        mdtime = discord.utils.format_dt(dt, "d")
        await ctx.send(
            f"Extended this ticket to {mdtime}. I will not send out an inactivity reminder until then!"
        )


async def setup(bot):
    await bot.add_cog(TicketCog(bot))
