from discord.ext import commands
import json 
import random 
import discord 
import asyncio 

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from bot import LunaBot 


class Misc(commands.Cog):

    def __init__(self, bot):
        self.bot: 'LunaBot' = bot 

        # TODO: use db
        with open('cogs/webhooks.json') as f:
            self.webhooks = json.load(f)
        with open('cogs/static/8ball.json') as f:
            self._8ball_answers = json.load(f)

    @commands.Cog.listener()
    async def on_member_join(self, member):
        # TODO: could move to a different cog
        name = member.display_name
        if len(name) > 28:
            name = name[:28]
        await asyncio.sleep(1)
        await member.edit(nick=f'✿❀﹕{name}﹕')
    
    @commands.hybrid_command()
    async def topic(self, ctx):
        """Get a random topic to talk about"""
        with open('cogs/static/topics.json') as f:
            topics = json.load(f)
            topics.append(topics.pop(0))
            topic = topics[0] 
        with open('cogs/static/topics.json', 'w') as f:
            json.dump(topics, f, indent=4)

        layout = self.bot.get_layout('topic')
        await layout.send(ctx, repls={'question': topic})
    
    @commands.hybrid_command()
    async def polyjuice(self, ctx, member: discord.Member, *, sentence: str):
        """Send a message as another user"""
        if ctx.interaction is None:
            await ctx.message.delete()
        else:
            await ctx.interaction.response.send_message('Sending...', ephemeral=True)
        if str(ctx.channel.id) not in self.webhooks:
            webhook = await ctx.channel.create_webhook(name='polyjuice')
            self.webhooks[str(ctx.channel.id)] = webhook.url
            with open('webhooks.json', 'w') as f:
                json.dump(self.webhooks, f)
        else:
            webhook = discord.Webhook.from_url(self.webhooks[str(ctx.channel.id)], session=self.bot.session)
        
        await webhook.send(sentence, username=member.display_name, avatar_url=member.display_avatar.url)

    @commands.hybrid_command(name='8ball')
    async def _8ball(self, ctx, *, question: str):
        """Ask the magic 8ball a question"""
        answer = random.choice(self._8ball_answers)
        answer = f'*{answer}*'
        layout = self.bot.get_layout('8ball')
        await layout.send(ctx, repls={'question': question, 'answer': answer})
    
    @commands.hybrid_command(name='qna')
    async def qna(self, ctx, *, question: str):
        """Ask a question to the QnA channel"""
        channel = self.bot.get_var_channel('qna') 
        layout = self.bot.get_layout('qna')
        msg = await layout.send(channel, repls={'question': question})
        await msg.create_thread(name="⁺﹒Luna's Answer﹗𖹭﹒⁺")
        await ctx.send(f'Your question has been sent to the QnA channel! {msg.jump_url}')


async def setup(bot):
    await bot.add_cog(Misc(bot))
