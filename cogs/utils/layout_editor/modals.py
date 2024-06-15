import discord 


class TextModal(discord.ui.Modal, title='Set Layout Text'):
    text = discord.ui.TextInput(label='Enter text', max_length=2000, required=False)

    def __init__(self, parent_view, text, **kwargs):
        super().__init__(**kwargs)
        self.text.default = text
        self.parent_view = parent_view

    async def on_submit(self, interaction):
        text = self.text.value
        self.parent_view.content = text
        self.parent_view.update()
        await interaction.response.edit_message(view=self.parent_view, content=self.parent_view.content)
    
class EmbedsModal(discord.ui.Modal, title='Set Layout Embeds'):
    names = discord.ui.TextInput(
        label='Enter embed name(s). One per line.', 
        style=discord.TextStyle.long,
        max_length=256, 
        required=False
    )

    def __init__(self, parent_view, embed_names, **kwargs):
        super().__init__(**kwargs)
        self.parent_view = parent_view
        self.names.default = '\n'.join(embed_names)

    async def on_submit(self, interaction):
        if not self.names.value:
            self.parent_view.embed_names = [] 
        else:
            names = self.names.value.lower().split('\n')
            self.parent_view.embed_names = names
        self.parent_view.update()
        await interaction.response.edit_message(view=self.parent_view, embeds=self.parent_view.embeds)