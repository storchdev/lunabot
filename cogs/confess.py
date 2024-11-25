from discord.ext import commands
import discord
from .utils import staff_only
from .utils import View, LayoutContext
from datetime import datetime

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
    
    @commands.hybrid_group(invoke_without_command=True)
    async def confess(self, ctx):
        """Confess something anonymously."""
        pass

    @confess.command(name='send')
    async def confess_send(self, ctx, *, confession: str):
        """Send a confession anonymously."""
        if ctx.interaction is None:
            await ctx.message.delete()
        
        channel = self.bot.get_var_channel('confess')
        query = """INSERT INTO
                       confessions (confession, user_id, channel_id)
                   VALUES
                       ($1, $2, $3)
                   RETURNING
                       id
                """
        confession_id = await self.bot.db.fetchval(query, confession, ctx.author.id, channel.id)

        layout = self.bot.get_layout('confess')
        repls = {
            'number': confession_id,
            'message': confession
        }
        msg = await layout.send(channel, repls=repls)

        query = 'UPDATE confessions SET message_id = $1 WHERE id = $2'
        await self.bot.db.execute(query, msg.id, confession_id)
        await ctx.send(f'Confession sent! View it in {msg.jump_url}', ephemeral=True)
    
    @confess.command(name='delete')
    async def confess_delete(self, ctx, number: int):
        """Delete a confession you made."""

        query = 'SELECT channel_id, message_id FROM confessions WHERE id = $1 AND user_id = $2' 
        row = await self.bot.db.fetchrow(query, number, ctx.author.id)
        if row is None:
            return await ctx.send('Confession not found.', ephemeral=True)
        
        # temporary fix
        elif row['channel_id'] is None:
            channel = self.bot.get_channel(933877494598225930)
            found = False
            after = datetime.fromtimestamp(1721754100)
            before = datetime.fromtimestamp(1724893500)
            async for msg in channel.history(after=after, before=before, limit=None): 
                if msg.author.id == self.bot.user.id and msg.embeds and msg.embeds[0].description.startswith(f'> \u207a <a:ML_heart_point:917958056409706497>\ufe52**Confession #{number}'):
                    await msg.delete()
                    found = True
                    break
            if not found:
                return await ctx.send('Confession message not found.', ephemeral=True)
        
        else:
            channel = self.bot.get_channel(row['channel_id'])
            msg = await channel.fetch_message(row['message_id'])
            await msg.delete()

        query = 'DELETE FROM confessions WHERE id = $1 AND user_id = $2'
        await self.bot.db.execute(query, number, ctx.author.id)
        await ctx.send('Confession deleted.', ephemeral=True)

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
