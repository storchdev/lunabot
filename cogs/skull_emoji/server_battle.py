from discord.ext import commands
import discord


import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from bot import LunaBot


class ServerBattle(commands.Cog):
    """The description for ServerBattle goes here."""

    def __init__(self, bot):
        self.bot: "LunaBot" = bot
        self.d = {}

    async def cog_load(self):
        # return 

        ch = self.bot.get_var_channel("server-battle")
        emoji = self.bot.vars.get("love-button-emoji")
        d={}
        async for msg in ch.history():
            if len(msg.reactions) == 0:
                continue
            r = msg.reactions[0]
            if str(r.emoji) != emoji:
                continue
            async for user in r.users():
                if user in d:
                    d[user].append(msg)
                else:
                    d[user] = [msg]
            
            logging.info(f"Loaded reactions for {msg.jump_url}")

        self.d = d
        
        log = []
        guild = self.bot.get_guild(self.bot.GUILD_ID)
        priv = self.bot.get_var_channel("private")

        for u, msgs in self.d.items():
            if guild.get_member(u.id) is None:
                for msg in msgs:
                    await msg.remove_reaction(emoji, u)
                    logging.info(f"Removed reaction from {u.name} ({u.id}) on {msg.jump_url}")
                log.append(f"Removed reaction from {u.mention} ({u.name}) on {", ".join(m.jump_url for m in msgs)} due to leaving")

        await priv.send('\n\n'.join(log))

        log=[]
        for user, msgs in self.d.items():
            if user.bot:
                continue
            if len(msgs)==1:
                continue
            jumps='\n'.join(m.jump_url for m in msgs)
            log.append(f'{user.mention} reacted on multiple:\n{jumps}')

        await priv.send('\n\n'.join(log))


    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):
        if payload.member.bot:
            return 

        ch = self.bot.get_var_channel("server-battle")
        emoji = self.bot.vars.get("love-button-emoji")

        if payload.channel_id != ch.id or str(payload.emoji) != emoji:
            return 

        msg = await ch.fetch_message(payload.message_id)
        if payload.member in self.d:
            await msg.remove_reaction(emoji, payload.member)
            priv = self.bot.get_var_channel("private")
            await priv.send(f"removed vote by {payload.member.mention} on {msg.jump_url}")
        else:
            self.d[payload.member] = [msg] 
    
    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload):
        if payload.member.bot:
            return 

        ch = self.bot.get_var_channel("server-battle")
        emoji = self.bot.vars.get("love-button-emoji")

        if payload.channel_id != ch.id or str(payload.emoji) != emoji:
            return 
        
        guild = self.bot.get_guild(payload.guild_id)
        if guild.get_member(payload.user_id) in self.d:
            self.d.pop(payload.member)


async def setup(bot):
    await bot.add_cog(ServerBattle(bot))
