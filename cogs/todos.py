import discord
import asyncpg
from discord.ext import commands, menus
from .utils.paginators import ViewMenuPages


class Todo:
    def __init__(self, id, name, priority, completed, creator_id, time_created, time_completed):
        self.id = id
        self.name = name
        self.priority = priority
        self.completed = completed
        self.creator_id = creator_id
        self.time_created = time_created
        self.time_completed = time_completed

    @classmethod
    def from_record(cls, record):
        return cls(
            id=record['id'],
            name=record['name'],
            priority=record['priority'],
            completed=record['completed'],
            creator_id=record['creator_id'],
            time_created=record['time_created'],
            time_completed=record['time_completed']
        )


class TodoPageSource(menus.ListPageSource):
    def __init__(self, bot, todos, show_completed=False, sort_by='priority'):
        self.bot = bot 
        self.todos = [Todo.from_record(todo) for todo in todos]
        self.show_completed = show_completed
        self.sort_by = sort_by
        super().__init__(self.get_filtered_sorted_todos(), per_page=10)

    def get_filtered_sorted_todos(self):
        filtered_todos = [todo for todo in self.todos if self.show_completed or not todo.time_completed]
        sorted_todos = sorted(filtered_todos, key=lambda todo: (getattr(todo, self.sort_by) is None, getattr(todo, self.sort_by)))  # sorts while pushing Nones to the end
        return sorted_todos

    async def format_page(self, menu, todos):
        lines = []
        for todo in todos:
            if todo.time_completed:
                line = f"~~{todo.name}~~"
            else:
                line = f"**#{todo.priority}** - {todo.name}"
            lines.append(line)

        return discord.Embed(
            color=self.bot.DEFAULT_EMBED_COLOR,
            description="\n".join(lines)
        )


class TodoListView(ViewMenuPages):
    def __init__(self, source, *, ctx):
        super().__init__(source, ctx=ctx)
        self.sort_by_select.add_option(label='Priority', value='priority')
        self.sort_by_select.add_option(label='Time Created', value='time_created')
        self.sort_by_select.add_option(label='Time Completed', value='time_completed')
        self.my_fill_items()
    
    def my_fill_items(self) -> None:
        self.clear_items()
        super().fill_items()
        
        if self.source.show_completed:
            self.toggle_show_completed_button.label = 'Hide Completed'
        else:
            self.toggle_show_completed_button.label = 'Show Completed'

        # Add toggle show completed button
        self.add_item(self.toggle_show_completed_button)

        # Add sort by dropdown
        self.add_item(self.sort_by_select)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.ctx.author.id

    async def handle_toggle_show_completed(self, interaction: discord.Interaction):
        self.source.show_completed = not self.source.show_completed
        self.source.entries = self.source.get_filtered_sorted_todos()
        self.my_fill_items()
        await self.show_page(interaction, self.current_page)

    async def handle_sort_by(self, interaction: discord.Interaction, value):
        self.source.sort_by = value
        self.source.entries = self.source.get_filtered_sorted_todos()
        await self.show_page(interaction, self.current_page)

    @discord.ui.button(label='Show Completed', style=discord.ButtonStyle.secondary, row=1)
    async def toggle_show_completed_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_toggle_show_completed(interaction)

    @discord.ui.select(placeholder='Sort by...', row=2)
    async def sort_by_select(self, interaction: discord.Interaction, select: discord.ui.Select):
        await self.handle_sort_by(interaction, select.values[0])


class TodoEditView(discord.ui.View):
    def __init__(self, source, *, ctx, todo_name):
        super().__init__(timeout=60)
        self.source = source
        self.ctx = ctx
        self.todo_name = todo_name.lower()
        self.current_page = 0
        self.local_todos = self.source.entries.copy()
        self.update_todo_list()
    
    def update_todo_list(self):
        todos = self.local_todos
        todo_index = next((i for i, todo in enumerate(todos) if todo.name == self.todo_name), None)
        if todo_index is None:
            return
        
        start_index = max(0, todo_index - 2)
        end_index = min(len(todos), todo_index + 3)
        
        self.todos_to_display = todos[start_index:end_index]
        self.todo_index = todo_index - start_index
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.ctx.author.id
    
    def format_todo_list(self) -> discord.Embed:
        lines = []
        for i, todo in enumerate(self.todos_to_display):
            if i == self.todo_index:
                line = f"**`#{todo.priority}`** - `{todo.name}`"
            else:
                line = f"**#{todo.priority}** - {todo.name}"
            lines.append(line)

        return discord.Embed(
            color=self.ctx.bot.DEFAULT_EMBED_COLOR,
            description="\n".join(lines)
        )

    async def handle_move_to_top(self, interaction: discord.Interaction):
        await self.update_todo_priority(interaction, new_priority=1)

    async def handle_move_up(self, interaction: discord.Interaction):
        current_priority = self.todos_to_display[self.todo_index].priority
        await self.update_todo_priority(interaction, new_priority=max(1, current_priority - 1))

    async def handle_move_down(self, interaction: discord.Interaction):
        max_priority = len(self.local_todos)
        current_priority = self.todos_to_display[self.todo_index].priority
        await self.update_todo_priority(interaction, new_priority=min(max_priority, current_priority + 1))

    async def handle_move_to_bottom(self, interaction: discord.Interaction):
        max_priority = len(self.local_todos)
        await self.update_todo_priority(interaction, new_priority=max_priority)

    async def update_todo_priority(self, interaction: discord.Interaction, new_priority: int):
        current_todo = self.todos_to_display[self.todo_index]
        current_priority = current_todo.priority

        if current_priority == new_priority:
            return

        if new_priority < current_priority:
            for todo in self.local_todos:
                if new_priority <= todo.priority < current_priority:
                    todo.priority += 1
        else:
            for todo in self.local_todos:
                if current_priority < todo.priority <= new_priority:
                    todo.priority -= 1

        current_todo.priority = new_priority
        self.local_todos.sort(key=lambda todo: todo.priority)
        self.update_todo_list()
        await interaction.response.edit_message(embed=self.format_todo_list(), view=self)
    
    @discord.ui.button(label='⤒', style=discord.ButtonStyle.primary, row=0)
    async def move_to_top_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_move_to_top(interaction)
    
    @discord.ui.button(label='↑', style=discord.ButtonStyle.primary, row=0)
    async def move_up_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_move_up(interaction)
    
    @discord.ui.button(label='↓', style=discord.ButtonStyle.primary, row=0)
    async def move_down_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_move_down(interaction)
    
    @discord.ui.button(label='⤓', style=discord.ButtonStyle.primary, row=0)
    async def move_to_bottom_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_move_to_bottom(interaction)
    
    @discord.ui.button(label='Submit', style=discord.ButtonStyle.success, row=1)
    async def submit_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.apply_changes_to_db()
        await interaction.response.edit_message(content='Changes submitted.', view=None, embed=None)
        self.stop()

    @discord.ui.button(label='Cancel', style=discord.ButtonStyle.danger, row=1)
    async def cancel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(content='Edit canceled.', view=None, embed=None)
        self.stop()

    async def apply_changes_to_db(self):
        for todo in self.local_todos:
            await self.ctx.bot.db.execute('''
                UPDATE todos
                SET priority = $1
                WHERE name = $2
            ''', todo.priority, todo.name)



class TodoCog(commands.Cog, name='Todos'):
    """The description for Todo goes here."""

    def __init__(self, bot):
        self.bot = bot
    
    async def cog_check(self, ctx):
        return ctx.author.guild_permissions.administrator or ctx.author.id == self.bot.owner_id 

    @commands.group(name="todo", aliases=["todos"], invoke_without_command=True)
    async def todo_group(self, ctx):
        await ctx.send_help(ctx.command)

    @todo_group.command(name="add", aliases=["create"])
    async def add_todo_command(self, ctx, *, name: str):
        name = name.lower()

        current_todo_count = await self.bot.db.fetchval('SELECT COUNT(*) FROM todos WHERE completed = FALSE')
        priority = current_todo_count + 1
        
        try:
            await self.bot.db.execute('''
                INSERT INTO todos (name, priority, creator_id, completed)
                VALUES ($1, $2, $3, FALSE)
            ''', name, priority, ctx.author.id)
            await ctx.send(f'Todo "{name}" added with priority {priority}.')
        except asyncpg.UniqueViolationError:
            await ctx.send(f'A todo with the name "{name}" already exists.')

    @todo_group.command(name="remove", aliases=["delete"])
    async def remove_todo_command(self, ctx, *, name: str):
        name = name.lower()
        result = await self.bot.db.execute('DELETE FROM todos WHERE name = $1', name)
        if result == 'DELETE 0':
            await ctx.send(f'Todo "{name}" not found')
        else:
            await ctx.send(f'Todo "{name}" removed.')

    @todo_group.command(name="list", aliases=["show"])
    async def list_todos_command(self, ctx):
        todos = await self.bot.db.fetch('SELECT * FROM todos ORDER BY priority')
        if len(todos) == 0:
            return await ctx.send('No todos found.')
        source = TodoPageSource(self.bot, todos, show_completed=False, sort_by='priority')
        view = TodoListView(source, ctx=ctx)
        await view.start()
    
    @todo_group.command(name='complete', aliases=['finish'])
    async def complete_todo_command(self, ctx, *, name: str):
        name = name.lower()

        row = await self.bot.db.fetchrow('SELECT priority FROM todos WHERE name = $1', name)
        if row is None:
            await ctx.send(f'Todo "{name}" not found')
            return

        if row['priority'] is None:
            await ctx.send(f'Todo "{name}" already completed.')
            return

        await self.bot.db.execute('''
            UPDATE todos
            SET completed = TRUE, time_completed = $1, priority = NULL
            WHERE name = $2
        ''', discord.utils.utcnow(), name)
        await self.bot.db.execute('''
            UPDATE todos 
            SET priority = priority - 1
            WHERE priority > $1
        ''', row['priority'])

        await ctx.send(f'Todo "{name}" completed.')
    
    @todo_group.command(name='uncomplete', aliases=['unfinish'])
    async def uncomplete_todo_command(self, ctx, *, name: str):
        name = name.lower()

        current_todo_count = await self.bot.db.fetchval('SELECT COUNT(*) FROM todos WHERE completed = FALSE')
        priority = current_todo_count + 1

        result = await self.bot.db.execute('''
            UPDATE todos
            SET completed = FALSE, time_completed = NULL, priority = $1
            WHERE name = $2
        ''', name, priority)
        if result == 'UPDATE 0':
            await ctx.send(f'Todo "{name}" not found')
        else:
            await ctx.send(f'Todo "{name}" uncompleted.')
    
    @todo_group.command(name="edit")
    async def edit_todo_command(self, ctx, *, name: str):
        todos = await self.bot.db.fetch('SELECT * FROM todos WHERE completed = FALSE ORDER BY priority')
        if len(todos) == 0:
            return await ctx.send('No todos found.')

        source = TodoPageSource(self.bot, todos, show_completed=True, sort_by='priority')
        view = TodoEditView(source, ctx=ctx, todo_name=name)
        await ctx.send(embed=view.format_todo_list(), view=view)


async def setup(bot):
    await bot.add_cog(TodoCog(bot))
