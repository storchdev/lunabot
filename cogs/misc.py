from discord.ext import commands
import json 
import random 
import discord 
import asyncio 


class Misc(commands.Cog):

    def __init__(self, bot):
        self.bot = bot 

        with open('cogs/static/topics.json') as f:
            self.topics = json.load(f)
        with open('cogs/static/embeds.json') as f:
            self.embedjson = json.load(f)['topic']
        # TODO: use db
        with open('cogs/webhooks.json') as f:
            self.webhooks = json.load(f)

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
        # TODO: make it a layout
        embed = discord.Embed.from_dict(self.embedjson)
        embed.description = embed.description.replace('{q}', random.choice(self.topics))
        await ctx.send(embed=embed)
    
    @commands.hybrid_command()
    async def polyjuice(self, ctx, member: discord.Member, *, sentence: str):
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
        


async def setup(bot):
    await bot.add_cog(Misc(bot))
