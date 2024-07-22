from discord.ext import commands
import discord
from .utils import staff_only
from .utils import View, LayoutContext

from typing import TYPE_CHECKING 

if TYPE_CHECKING:
    from bot import LunaBot


class AffirmationView(View):
    def __init__(self, confession_id, user_id, *, ctx):
        self.confession_id = confession_id
        self.user_id = user_id
        super().__init__(bot=ctx.bot, owner=ctx.author)

    @discord.ui.button(label='Affirm', style=discord.ButtonStyle.blurple)
    async def affirm(self, interaction, button):
        layout = self.bot.get_layout('confesslog')
        repls = {
            'number': self.confession_id,
            'usermention': f'<@{self.user_id}>'
        }
        await layout.send(interaction, repls=repls, ephemeral=True)
        await self.message.delete()
    
    @discord.ui.button(label='Cancel')
    async def cancel(self, interaction, button):
        await interaction.response.defer()
        await self.message.delete()


class Confess(commands.Cog):
    """The description for Confess goes here."""

    def __init__(self, bot):
        self.bot: 'LunaBot' = bot
    
    @commands.hybrid_command()
    async def confess(self, ctx, *, confession: str):
        """Confess something anonymously."""
        if ctx.interaction is None:
            await ctx.message.delete()
        
        channel = self.bot.get_var_channel('confess')
        query = 'INSERT INTO confessions (confession, user_id) VALUES ($1, $2) RETURNING id'
        confession_id = await self.bot.db.fetchval(query, confession, ctx.author.id)

        layout = self.bot.get_layout('confess')
        repls = {
            'number': confession_id,
            'message': confession
        }
        msg = await layout.send(channel, repls=repls)
        await ctx.send(f'Confession sent! View it in {msg.jump_url}', ephemeral=True)
    
    @commands.command()
    @staff_only()
    async def confesslog(self, ctx, number: int):
        query = 'SELECT user_id FROM confessions WHERE id = $1'
        user_id = await self.bot.db.fetchval(query, number)
        if user_id is None:
            return await ctx.send('Confession not found.')

        embed = discord.Embed(title='Affirmation', color=self.bot.DEFAULT_EMBED_COLOR)
        embed.description = 'I will only use this command to investigate a confession that violates a server rule. I will not needlessly encroach on the privacy of others. I will ensure that the confession remains anonymous and that the punishment is delivered anonymously.'
        view = AffirmationView(number, user_id, ctx=ctx)
        view.message = await ctx.send(embed=embed, view=view)




async def setup(bot):
    await bot.add_cog(Confess(bot))
