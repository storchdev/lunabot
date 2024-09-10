from discord.ext import commands
import math 
import asyncio 
import discord
from typing import TYPE_CHECKING
import random
from .utils import LayoutContext
import time

if TYPE_CHECKING:
    from bot import LunaBot
    

class Currency(commands.Cog):
    """The description for Currency goes here."""

    def __init__(self, bot):
        self.bot: 'LunaBot' = bot
        self.lunara = self.bot.vars.get('lunara')
        self.msg_count = 0
        self.drop_active = False
        self.low_drop = 1000 
        self.high_drop = 5000
        self.pick_limit = 1
        self.picks = 0

    async def add_balance(self, user_id, amount):
        # update and return 
        query = 'INSERT INTO balances (user_id, balance) VALUES ($1, $2) ON CONFLICT (user_id) DO UPDATE SET balance = balances.balance + $2 RETURNING balance'
        return await self.bot.db.fetchval(query, user_id, amount)


    @commands.hybrid_command()
    async def shop(self, ctx):
        """View the shop"""
        rows = await self.bot.db.fetch('SELECT * FROM shop_items')
        names = []
        descs = []
        for row in rows:
            names.append(row['common_name'])
            descs.append(row['description'])
        layout = self.bot.get_layout('shop')
        await layout.send(ctx, repls={
            'itemnames': names,
            'itemdescs': descs
        })
    
    @commands.hybrid_command(aliases=['balance'])
    async def bal(self, ctx, member: discord.Member = None):
        """Check your balance"""
        if member is None:
            member = ctx.author
        # initialize balance if not exists    
        await self.add_balance(member.id, 0)
        layout = self.bot.get_layout('bal')
        query = 'SELECT balance FROM balances WHERE user_id = $1'
        bal = await self.bot.db.fetchval(query, member.id)
        await layout.send(ctx, LayoutContext(author=member), repls={'balance': bal})
    
    @staticmethod
    def check_for_drop(message_count, max_messages=50):
        """
        This function simulates a drop happening based on the message count. 
        As the message count increases, the probability of a drop happening increases.
        Returns True if the drop happens, otherwise False.
        """

        # Sigmoid function to scale probability between 0 and 1
        probability = 1 / (1 + math.exp(-0.2 * (message_count - max_messages/2)))

        # Clamp probability to 0-1 range
        probability = min(max(probability, 0), 1)

        # Randomly return True or False based on the probability
        return random.random() < probability
        
    @commands.Cog.listener()
    async def on_message(self, msg):
        if msg.author.bot:
            return
        
        if msg.channel.id != self.bot.vars.get('general-channel-id'):
            return 
        
        self.msg_count += 1
        if self.check_for_drop(self.msg_count):
            self.msg_count = 0 
            layout = self.bot.get_layout('drop') 
            temp = await layout.send(msg.channel, LayoutContext(message=msg), repls={'low': self.low_drop, 'high': self.high_drop})
            self.drop_active = True
            await asyncio.sleep(30)
            self.drop_active = False
            self.picks = 0
            await temp.delete()
                    
        if 'welc' in msg.content.lower():
            et = await self.bot.get_cooldown_end('welc', 60, obj=msg.author)
            if et:
                await (self.bot.get_layout('welccd')).send(msg.channel, LayoutContext(message=msg), delete_after=7)
                return

            gained = 500 
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

        if self.picks >= self.pick_limit:
            layout = self.bot.get_layout('drop/limit')
            await layout.send(ctx, LayoutContext(message=ctx.message), delete_after=7)
            return

        self.picks += 1 

        amount = random.randint(self.low_drop, self.high_drop)
        await self.add_balance(ctx.author.id, amount)
        if 1000<=amount<=1999:
            layout = self.bot.get_layout('drop/1kto2k')
        elif 2000<=amount<3999:
            layout = self.bot.get_layout('drop/2kto4k')
        else:
            layout = self.bot.get_layout('drop/4kto5k')
        await layout.send(ctx, LayoutContext(message=ctx.message), repls={'amount': amount})
        


async def setup(bot):
    await bot.add_cog(Currency(bot))
