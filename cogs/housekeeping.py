import asyncio 
import re
from datetime import timedelta

from discord.ext import commands, tasks
import discord

from .utils import LayoutContext

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from bot import LunaBot


VC_IDS = {
    899108709450543115: 1041061422706204802,
    # 1068342105006673972: 1068342105006673977,
    1314357693384888451: 1370519328608485417,   
    1004878848262934538: 1004881486991851570,
    1041468894487003176: 1041472654537932911,
}

# haha funny
class Housekeeping(commands.Cog):
    """The description for Housekeeping goes here."""

    def __init__(self, bot):
        self.bot: "LunaBot" = bot

    async def cog_load(self):
        self.edit.start()

    async def cog_unload(self):
        self.edit.cancel()

    @tasks.loop(minutes=15)
    async def edit(self):
        for guild_id, channel_id in VC_IDS.items():
            guild = self.bot.get_guild(guild_id)
            if guild is None:
                continue
            channel = self.bot.get_channel(channel_id)
            count = int(re.search(r'(\d+)', channel.name).group(1))
            if count != len(guild.members):
                count = len(guild.members)
                try:
                    await channel.edit(name=re.sub(r'\d+', str(count), channel.name))
                except discord.Forbidden:
                    print(f'failed to edit member count in {guild.name}')
                await asyncio.sleep(3)

    @commands.Cog.listener()
    async def on_message(self, msg: discord.Message):
        if msg.channel.id == self.bot.vars.get("welc-channel-id") and 'welc' in msg.content.lower():
            # remove emojis and links

            cleaned = re.sub(r'(<a?:\w+:\d+>)|(https:\/\/(?:media\.)?tenor\.com\/\S+)', '', msg.content)
            if len(cleaned) > 20:
                return

            query = "SELECT message_id FROM welc_messages ORDER BY time DESC LIMIT 1"
            bot_message_id = await self.bot.db.fetchval(query)

            if bot_message_id is None:
                return 

            query = "INSERT INTO user_welc_messages (message_id, bot_message_id, channel_id) VALUES ($1, $2, $3)"
            await self.bot.db.execute(query, msg.id, bot_message_id, msg.channel.id)

            print(f"--- added welc message by {msg.author.name} ---")

        # TODO: delete intros when someone leaves
        # elif msg.channel.id == self.bot.vars.get("intros-channel-id") and "my intro" in msg.content.lower():
            
                
    @commands.Cog.listener()
    async def on_member_join(self, member):
        name = member.display_name
        if len(name) > 28:
            name = name[:28]
        await asyncio.sleep(1)
        await member.edit(nick=f'✿❀﹕{name}﹕')

        if member.guild.id == self.bot.GUILD_ID:
            layout = self.bot.get_layout('welc')
            ctx = LayoutContext(author=member)
            channel = self.bot.get_var_channel('welc')
            bot_msg = await layout.send(channel, ctx)

            query = """INSERT INTO
                         welc_messages (user_id, channel_id, message_id)
                       VALUES
                         ($1, $2, $3)
                    """
            await self.bot.db.execute(query, member.id, bot_msg.channel.id, bot_msg.id)
    
    @commands.Cog.listener()
    async def on_member_remove(self, member):
        query = """SELECT * FROM welc_messages WHERE user_id = $1"""
        rows = await self.bot.db.fetch(query, member.id)

        for row in rows:
            channel = self.bot.get_channel(row["channel_id"])
            if channel is None:
                continue
            try:
                msg = await channel.fetch_message(row["message_id"])
                await msg.delete()
                await self.bot.get_var_channel("action-log").send(
                    f"Deleted welcome autoresponder for {member.mention} ({member.id})"
                )
            except (discord.HTTPException, discord.Forbidden):
                continue

            # delete user welcs
            query = "SELECT channel_id, message_id FROM user_welc_messages WHERE bot_message_id = $1"
            urows = await self.bot.db.fetch(query, row["message_id"])
            bulk_delete = []

            for urow in urows:
                msg = await channel.fetch_message(urow["message_id"])
                if (discord.utils.utcnow() - msg.created_at).total_seconds() > 7 * 86400:
                    await msg.delete()
                    print(f"Deleted welc message by {msg.author.name}")
                else:
                    bulk_delete.append(msg)
            
            if bulk_delete:
                await channel.delete_messages(bulk_delete, reason="welcomed a user who left")
                await self.bot.get_var_channel("action-log").send(
                    f"Bulk deleted {len(bulk_delete)} welc messages"
                )

                for msg in bulk_delete:
                    print(f"Deleted welc message from {msg.author.name} ({msg.jump_url})")
            
            query = "DELETE FROM user_welc_messages WHERE bot_message_id = $1" 
            await self.bot.db.execute(query, row["message_id"])

        query = """DELETE
                   FROM
                     welc_messages
                   WHERE
                     user_id = $1
                """
        await self.bot.db.execute(query, member.id)


    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        role = after.guild.get_role(self.bot.vars.get("sus-role-id"))
        if role not in before.roles and role in after.roles:
            await self.bot.schedule_future_task(
                "kick_sus_member",
                discord.utils.utcnow() + timedelta(days=1),
                user_id=after.id
            )

            await self.bot.get_var_channel("action-log").send(f"Suspicious user scheduled for kicking: {after.mention}") 
    
    @commands.Cog.listener()
    async def on_member_leave(self, member):
        channel = self.bot.get_var_channel("promo")
        if channel is None:
            return 

        to_delete = [] 
        async for msg in channel.history(limit=100):
            if (discord.utils.utcnow() - msg.created_at).total_seconds() > 86400 * 14:
                break
            if msg.author == member:
                to_delete.append(msg)
        
        await channel.delete_messages(to_delete)
        await self.bot.get_var_channel("action-log").send(f"Deleted {len(to_delete)} promo messages by {member.name} ({member.id})")

    

async def setup(bot):
    await bot.add_cog(Housekeeping(bot))

from .utils import LayoutContext
