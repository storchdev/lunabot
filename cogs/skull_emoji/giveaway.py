from discord.ext import commands
import json 
from humanize import precisedelta
from lunascript import Layout, LunaScript
import time
from datetime import datetime, timedelta
import discord
import asyncio
from emoji import is_emoji
import random
# from cogs.levels import 
import dateparser 


# IN PROGRESS

APPROVED_ROLE_ID = 923416499107037195


class Giveaway:
    def __init__(self, gvwy_id, prize, end_time, channel_id, message_id, wl_roles, bl_roles, wl_users, bl_users):
        self.gvwy_id = gvwy_id
        self.prize = prize 
        self.end_time = end_time 
        self.message_id = message_id 
        self.channel_id = channel_id
        self.wl_roles = wl_roles 
        self.bl_roles = bl_roles 
        self.wl_users = wl_users 
        self.bl_users = bl_users



class GiveawayView(discord.ui.View): 
    EMOJI = '<a:LC_lilac_heart_NF2U_DNS:1046191564055138365>'

    def __init__(self, gvwy_id):
        super().__init__(timeout=None)

        async def callback(inter):
            gvwy = inter.client.giveaways[gvwy_id] 
            # TODO: CHECK IF USER CAN ENTER 

            if inter.author.id in gvwy.bl_users:
                # TODO: send layout
                return

            if gvwy.wl_users and inter.author.id not in gvwy.wl_users:
                # send layout
                return 
            
            if gvwy.bl_roles:


        button = discord.ui.Button(style=discord.ButtonStyle.gray, label='\u200b', emoji=self.EMOJI, custom_id=gvwy_id)
        self.add_item(button)


class CreateGiveawayView(discord.ui.View):

    def __init__(self, ctx, embed):
        super().__init__(timeout=300)
        self.ctx = ctx
        self.channel = None 
        self.prize = None 
        self.end = None 
        self.num_winners = 1 
        self.wl_users = []
        self.bl_users = []
        self.wl_roles = []
        self.bl_roles = []
        self.embed = embed 
        self.bot.giveaways = {}

        self.reqs = []
        self.antireqs = []
    
    @discord.ui.select(cls=discord.ui.ChannelSelect, placeholder='Choose a channel', max_values=1)
    async def channel(self, inter, sel):
        self.channel = sel[0]
        self.embed.set_field_at(1, name='Channel', value=self.channel.mention)
        await inter.response.edit_message(embed=self.embed)
    
    @discord.ui.button(label='Set prize', style=discord.ButtonStyle.blurple)
    async def prize(self, button, interaction):
        def check(m):
            return m.author == self.ctx.author and m.channel == self.ctx.channel

        await interaction.response.send_message('What is the prize?')
        try:
            msg = await self.ctx.bot.wait_for('message', check=check, timeout=60)
        except asyncio.TimeoutError:
            await interaction.delete_original_response()
            return
        
        self.prize = msg.content 
        await interaction.delete_original_response()
        await msg.delete()
        self.embed.set_field_at(0, name='Prize', value=self.prize)
        await interaction.response.edit_message(embed=self.embed)
    
    @discord.ui.button(label='Set end time', style=discord.ButtonStyle.blurple)
    async def endtime(self, button, interaction):
        def check(m):
            return m.author == self.ctx.author and m.channel == self.ctx.channel
        
        await interaction.response.send_message('When does the giveaway end?')
        try:
            msg = await self.ctx.bot.wait_for('message', check=check, timeout=60)
        except asyncio.TimeoutError:
            await interaction.delete_original_response()
            return
        
        try:
            dt = dateparser.parse(msg.content)
        except ValueError:
            await interaction.response.send_message('I couldn\'t understand that. Try again.', delete_after=5)
            return
        
        self.end = dt
        await interaction.delete_original_response()
        await msg.delete()
        self.embed.set_field_at(2, name='Ends', value=discord.utils.format_dt(dt, 'R'))
        await interaction.response.edit_message(embed=self.embed)
    
    @discord.ui.button(label='Change # of winners', style=discord.ButtonStyle.blurple)
    async def num_winners(self, button, interaction):
        def check(m):
            return m.author == self.ctx.author and m.channel == self.ctx.channel
        
        await interaction.response.send_message('How many winners?')
        try:
            msg = await self.ctx.bot.wait_for('message', check=check, timeout=60)
        except asyncio.TimeoutError:
            await interaction.delete_original_response()
            return
        
        try:
            num = int(msg.content)
        except ValueError:
            await interaction.response.send_message('I couldn\'t understand that. Try again.', delete_after=5)
            return
        
        self.num_winners = num 
        await interaction.delete_original_response()
        await msg.delete()
        self.embed.set_field_at(3, name='# of Winners', value=str(self.num_winners))
        await interaction.response.edit_message(embed=self.embed)

    @discord.ui.button(label='Set requirements', style=discord.ButtonStyle.blurple) 
    async def reqs(self, button, interaction):
        # collect input then split by newlines

        def check(m):
            return m.author == self.ctx.author and m.channel == self.ctx.channel
        
        await interaction.response.send_message('What are the requirements?')
        try:
            msg = await self.ctx.bot.wait_for('message', check=check, timeout=60)
        except asyncio.TimeoutError:
            await interaction.delete_original_response()
            return
        
        self.reqs = msg.content.split('\n')
        await interaction.delete_original_response()
        await msg.delete()
        self.embed.set_field_at(4, name='Requirements', value='\n'.join(self.reqs))
        await interaction.response.edit_message(embed=self.embed)
    
    @discord.ui.button(label='Set anti-requirements', style=discord.ButtonStyle.blurple)
    async def antireqs(self, button, interaction):
        def check(m):
            return m.author == self.ctx.author and m.channel == self.ctx.channel
        
        await interaction.response.send_message('What are the anti-requirements?')
        try:
            msg = await self.ctx.bot.wait_for('message', check=check, timeout=60)
        except asyncio.TimeoutError:
            await interaction.delete_original_response()
            return
        
        self.antireqs = msg.content.split('\n')
        await interaction.delete_original_response()
        await msg.delete()
        self.embed.set_field_at(5, name='Anti-requirements', value='\n'.join(self.antireqs))
        await interaction.response.edit_message(embed=self.embed)

    @discord.ui.select(cls=discord.ui.RoleSelect, placeholder='Whitelist roles', max_values=25)
    async def wl_roles(self, inter, sel):
        self.wl_roles = sel 
        self.embed.set_field_at(6, name='Whitelisted Roles', value='\n'.join(r.mention for r in self.wl_roles))
        await inter.response.edit_message(embed=self.embed)
    
    @discord.ui.select(cls=discord.ui.RoleSelect, placeholder='Blacklist roles', max_values=25)
    async def bl_roles(self, inter, sel):
        self.bl_roles = sel 
        self.embed.set_field_at(7, name='Blacklisted Roles', value='\n'.join(r.mention for r in self.bl_roles))
        await inter.response.edit_message(embed=self.embed)
    
    @discord.ui.select(cls=discord.ui.UserSelect, placeholder='Whitelist users', max_values=25)
    async def wl_users(self, inter, sel):
        self.wl_users = sel 
        self.embed.set_field_at(8, name='Whitelisted Users', value='\n'.join(u.mention for u in self.wl_users))
        await inter.response.edit_message(embed=self.embed)
    
    @discord.ui.select(cls=discord.ui.UserSelect, placeholder='Blacklist users', max_values=25)
    async def bl_users(self, inter, sel):
        self.bl_users = sel 
        self.embed.set_field_at(9, name='Blacklisted Users', value='\n'.join(u.mention for u in self.bl_users))
        await inter.response.edit_message(embed=self.embed)
    
    @discord.ui.button(label='Submit', style=discord.ButtonStyle.green)
    async def submit(self, button, interaction):
        if not self.channel:
            await interaction.response.send_message('You need to choose a channel.', ephemeral=True)
            return
        if not self.prize:
            await interaction.response.send_message('You need to set a prize.', ephemeral=True)
            return
        if not self.end:
            await interaction.response.send_message('You need to set an end time.', ephemeral=True)
            return

        self.final_inter = interaction 
        self.stop()


class GiveawayCog(commands.Cog, name='Giveaways'):

    def __init__(self, bot):
        self.bot = bot
        self.tasks = []

    def launch_task(self, gvwy):
        async def task():
            await asyncio.sleep(gvwy.end_time - time.time())
            await self.win(gvwy)
        
        self.tasks.append(self.bot.loop.create_task(task()))

    async def win(self, gvwy):
        # TODO: 
        pass 

    async def cog_load(self):
        query = 'select * from gvwys where joever = ?'
        rows = await self.bot.db.fetch(query, 0)
        for row in rows:
            gvwy = Giveaway(
                gvwy_id=row['gvwy_id'],
                prize=row['prize'],
                end_time=row['end_time'],
                channel_id=row['channel_id'],
                message_id=row['message_id'],
                wl_roles=json.loads(row['wl_role_ids']),
                bl_roles=json.loads(row['bl_role_ids']),
                wl_users=json.loads(row['wl_user_ids']),
                bl_users=json.loads(row['bl_user_ids'])
            )
            view = GiveawayView(gvwy.gvwy_id)
            self.bot.add_view(view)
            await self.launch_task(gvwy)

    async def cog_unload(self):
        for task in self.tasks:
            task.cancel()

    async def cog_check(self, ctx):
        return ctx.author.guild_permissions.administrator or ctx.author.id == self.bot.STORCH_ID

    @commands.command(name='set-role-entries')
    async def set_role_entries(self, ctx, role: discord.Role, num: int):
        if num == 1:
            query = 'delete from num_entries where role_id = ?'
            await self.bot.db.execute(query, role.id)
            await ctx.send('Done!')
            return 
        
        query = 'insert into num_entries (role_id, num) values (?, ?) on conflict (role_id) do update set num = ?'
        await self.bot.db.execute(query, role.id, num, num)
        await ctx.send('Done!')

    @commands.command(name='giveaway')
    async def giveaway(self, ctx):
        embed = discord.Embed(title='Create a giveaway', color=0xcab7ff)
        embed.add_field(name='Prize', value='...')
        embed.add_field(name='Channel', value='...')
        embed.add_field(name='Ends', value='...')
        embed.add_field(name='# of Winners', value='1')
        embed.add_field(name='Requirements', value='...')
        embed.add_field(name='Anti-requiremments', value='...')
        embed.add_field(name='Whitelisted Roles', value='...')
        embed.add_field(name='Blacklisted Roles', value='...')
        embed.add_field(name='Whitelisted Users', value='...')
        embed.add_field(name='Blacklisted Users', value='...')

        view = CreateGiveawayView(ctx, embed)
        msg = await ctx.send(embed=embed, view=view)
        await view.wait()

        antireqs = '\n'.join([f'> <:LC_reply_F2U:1081275742765195355> {r} \u273f\u2740' for r in view.antireqs])
        reqs = '\n'.join([f'> <:LC_reply_F2U:1081275742765195355> {r} \u273f\u2740' for r in view.reqs])
        layout = Layout.from_name('giveaway_main')
        args = {
            'prize': view.prize,
            'timethingy': discord.utils.format_dt(view.end, 'R'),
            'has_reqs': 1 if len(view.reqs) > 0 else 0,
            'has_antireqs': 1 if len(view.antireqs) > 0 else 0,
            'reqs': reqs,
            'antireqs': antireqs
        }
        ls = LunaScript.from_layout(view.channel, layout, args=args)

        gvwy_id = f'{view.prize}-{int(view.end_time.timestamp())}' 
        gvwy_view = GiveawayView(gvwy_id)
        gvwy_msg = await ls.send(view=gvwy_view)

        giveaway = Giveaway(
            gvwy_id=gvwy_id,
            prize=view.prize,
            end_time=view.end_time.timestamp(),
            channel_id = view.channel.id,
            message_id = gvwy_msg.id,
            wl_roles=view.wl_roles,
            bl_roles=view.bl_roles,
            wl_users=view.wl_users,
            bl_users=view.bl_users
        )
        self.bot.giveaways[gvwy_id] = giveaway 

        def jsonify(lst):
            return json.dumps([o.id for o in lst])

        query = 'insert into gvwys (gvwy_id, prize, host_id, num_winners, joever, end_time, channel_id, message_id, wl_role_ids, bl_role_ids, wl_user_ids, bl_user_ids) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)'
        await self.bot.db.execute(query, gvwy_id, view.prize, ctx.author.id, view.num_winners, 0, int(view.end_time.timestamp()), view.channel.id, gvwy_msg.id, jsonify(view.wl_roles), jsonify(view.bl_roles), jsonify(view.wl_users), jsonify(view.bl_users))
        await self.launch_task(giveaway)
        await msg.delete()
        await view.inter.response.send_message(f'Created your giveaway for [**{view.prize}**]({gvwy_msg.jump_url})')


        


    #     self.msg_ids = []
    #     self.bot.loop.create_task(self.dispatch())

    # async def win(self, res, *, reroll=False):
    #     msg_id = res['msg_id']

    #     if not reroll and msg_id not in self.msg_ids:
    #         return

    #     channel = self.bot.get_channel(res['ch_id'])
    #     msg = await channel.fetch_message(msg_id)
    #     reaction = msg.reactions[0]
    #     entered = await reaction.users().flatten()

    #     if self.bot.user in entered:
    #         entered.remove(self.bot.user)

    #     winners = []

    #     if reroll:
    #         while True:
    #             try:
    #                 winner = random.choice(entered)
    #             except IndexError:
    #                 return await channel.send('A new winner couldn\'t be picked ((')
    #             entered.remove(winner)
    #             if res['role_id']:
    #                 if not await self.reqs(res, reaction.emoji, winner, remove_reaction=False):
    #                     continue
    #                 else:
    #                     break
    #             else:
    #                 break
    #         embed = msg.embeds[0].to_dict()
    #         value = embed['fields'][0]['value']
    #         mentions = value.splitlines()
    #         if winner.mention not in mentions:
    #             if value == 'Nobody':
    #                 embed['fields'][0]['value'] = f'\n{winner.mention}'
    #             else:
    #                 embed['fields'][0]['value'] += f'\n{winner.mention}'
    #         await msg.edit(embed=discord.Embed.from_dict(embed))
    #         return await channel.send(f'Our new winner is {winner.mention}! Congrats ))')

    #     self.msg_ids.remove(res['msg_id'])
    #     query = 'UPDATE gvwys SET ended = $1 WHERE msg_id = $2'
    #     await self.bot.db.execute(query, True, res['msg_id'])

    #     while True:
    #         try:
    #             winner = random.choice(entered)
    #         except IndexError:
    #             break
    #         entered.remove(winner)

    #         if res['role_id']:
    #             if not (await self.reqs(res, reaction.emoji, winner, remove_reaction=False))[0]:
    #                 continue

    #         winners.append(winner)
    #         if len(winners) == res['winners']:
    #             break

    #     host = self.bot.get_user(res['host_id'])
    #     if len(winners) == 0:
    #         await channel.send(f'Nobody has entered the giveaway for **{res["prize"]}** ((')
    #         mentions = 'Nobody'
    #     else:
    #         mentions = '\n'.join(m.mention for m in winners)
    #         await channel.send(f':tada: The giveaway for `{res["prize"]}` has ended! :tada:\n'
    #                            f'__**Our winners are:**__\n\n{mentions}\n\n'
    #                            f'Congratulations on winning ))')
    #         for m in winners:
    #             await m.send(f':tada: Congratulations on winning the giveaway for **{res["prize"]}** in SLounge!\n'
    #                          f'You might have to DM the host ({host.mention}) to officially claim your prize.')
    #         embed = discord.Embed(
    #             title='Your Giveaway Has Ended!',
    #             color=discord.Colour.blue()
    #         ).add_field(
    #             name='Winners', value=mentions, inline=False
    #         ).add_field(
    #             name='Prize', value=res['prize'], inline=False
    #         ).add_field(
    #             name='Channel', value=f'{channel.mention}\n[Jump to Giveaway]({msg.jump_url})', inline=False
    #         )
    #         await host.send(embed=embed)
    #     embed = discord.Embed(
    #         title=res['prize'],
    #         description='*Giveaway ended*',
    #         color=discord.Colour.blue(),
    #         timestamp=datetime.utcnow()
    #     ).add_field(
    #         name='\U0001f389 Winners', value=mentions, inline=False
    #     ).add_field(
    #         name='\U0001f451 Host', value=host.mention, inline=False
    #     ).set_footer(
    #         text='\U000023f0 Time ended \u27a1',
    #         icon_url='https://cdn.discordapp.com/emojis/795660003369025546.gif?v=1'
    #     ).set_thumbnail(url='https://cdn.discordapp.com/attachments/725093929481142292/792530547120799764/'
    #                         'download_-_2020-12-26T181245.032.png')
    #     await msg.edit(embed=embed)

    # async def wait_for_msg(self, ctx, timeout):

    #     def check(m):
    #         return m.author == ctx.author and m.channel == ctx.channel

    #     try:
    #         return await self.bot.wait_for('message', check=check, timeout=timeout)
    #     except asyncio.TimeoutError:
    #         await ctx.send('Looks like you went AFK. Please try again.')
    #         return

    # async def dispatch(self):
    #     res = await self.bot.db.fetch('SELECT * FROM gvwys WHERE ended = $1', False)
    #     self.msg_ids = [res['msg_id'] for res in res]

    #     for row in res:
    #         async def task():
    #             await asyncio.sleep(row['end'] - time.time())
    #             await self.win(row)

    #         self.bot.loop.create_task(task())

    # async def reqs(self, res, emoji, member, *, remove_reaction=True):
    #     es = str(emoji)

    #     async def remove():
    #         msg = await self.bot.get_channel(res['ch_id']).fetch_message(res['msg_id'])
    #         await msg.remove_reaction(es, member)

    #     if 0 < res['role_id'] < 69:
    #         query = 'SELECT total_xp FROM xp WHERE user_id = $1'
    #         xp = await self.bot.db.fetchrow(query, member.id)
    #         if not xp:
    #             req = False
    #         else:
    #             level = get_level(xp['total_xp'])
    #             if res['role_id'] > level:
    #                 if remove_reaction:
    #                     await remove()
    #                 req = False
    #             else:
    #                 req = True
    #         if not req:
    #             return False, f'You can\'t enter this giveaway because you need to be at least ' \
    #                           f'**Level {res["role_id"]}**!'
    #     else:
    #         if res['role_id'] not in [r.id for r in member.roles]:
    #             if remove_reaction:
    #                 await remove()
    #             role = self.bot.slounge.get_role(res['role_id'])
    #             return False, f'You can\'t enter this giveaway because you don\'t have the `{role.name}` role.\n' \
    #                           'If this is a Reaction Role, you can obtain it in <#724745898726391850>.'
    #     return True, ''

    # @commands.Cog.listener()
    # async def on_raw_reaction_add(self, payload):
    #     if payload.member.bot:
    #         return
    #     if payload.message_id in self.msg_ids:
    #         query = 'SELECT * FROM gvwys WHERE msg_id = $1'
    #         res = await self.bot.db.fetchrow(query, payload.message_id)
    #         if str(payload.emoji) != res['emoji']:
    #             return
    #         if res['role_id']:
    #             enter, msg = await self.reqs(res, payload.emoji, payload.member)
    #             if not enter:
    #                 await payload.member.send(msg)

    # @commands.command()
    # @commands.has_role(794618677806104576)
    # async def reroll(self, ctx, msg_id: int):
    #     """Picks a new winner for an ended giveaway.
    #        You need the `Giveaways` role in SLounge to do this.

    #        **Usage:** `$reroll <message ID>`
    #     """
    #     query = 'SELECT * FROM gvwys WHERE msg_id = $1 AND ended = $2'
    #     res = await self.bot.db.fetchrow(query, msg_id, True)
    #     if not res:
    #         return await ctx.send(f'There is no ended giveaway with message ID `{msg_id}`.')
    #     await ctx.send('Rerolling...')
    #     await self.win(res, reroll=True)

    # @commands.command()
    # @commands.has_role(794618677806104576)
    # async def end(self, ctx, msg_id: int):
    #     """Force-ends a giveaway that hasn't automatically ended yet.
    #        You need the `Giveaways` role in SLounge to do this.

    #        **Usage:** `$end <message ID>`
    #     """
    #     query = 'SELECT * FROM gvwys WHERE msg_id = $1 AND ended = $2'
    #     res = await self.bot.db.fetchrow(query, msg_id, False)
    #     if not res:
    #         return await ctx.send(f'There is no active giveaway with message ID `{msg_id}`.')
    #     await ctx.send('Ending...')
    #     await self.win(res)

    # @commands.command()
    # @commands.has_role(794618677806104576)
    # async def giveaway(self, ctx):
    #     """Starts an interactive giveaway-making process.
    #        You need the `Giveaways` role in SLounge to do this.
    #        If you want to host a giveaway, ask an admin.
    #     """
    #     await ctx.send('Channel?')
    #     while True:
    #         msg = await self.wait_for_msg(ctx, 30)
    #         if not msg:
    #             return
    #         try:
    #             channel = await commands.TextChannelConverter().convert(ctx, msg.content)
    #             break
    #         except commands.BadArgument:
    #             await ctx.send(f'`{msg.content}` isn\'t a valid channel. '
    #                            'Try again.')
    #     await ctx.send('Prize?')
    #     while True:
    #         msg = await self.wait_for_msg(ctx, 60)
    #         if not msg:
    #             return
    #         if len(msg.content) > 256:
    #             await ctx.send('The prize must be 256 characters or under. '
    #                            'Try a shorter prize so it can fit ))')
    #         else:
    #             prize = msg.content
    #             break
    #     await ctx.send('# of Winners?')
    #     while True:
    #         msg = await self.wait_for_msg(ctx, 60)
    #         if not msg:
    #             return
    #         if not msg.content.isdigit() or int(msg.content) < 1:
    #             await ctx.send('Does that look like a positive integer to you? '
    #                            'Try again, baka.')
    #         else:
    #             winners = int(msg.content)
    #             break
    #     await ctx.send('Duration?')
    #     while True:
    #         msg = await self.wait_for_msg(ctx, 60)
    #         if not msg:
    #             return
    #         duration = await TimeConverter().convert(ctx, msg.content)
    #         if duration == 0:
    #             await ctx.send('That doesn\'t seem to be a valid time... '
    #                            'try something like `6d 9m 42s`.')
    #         else:
    #             break
    #     prompt = await ctx.send('Role requirement? (optional, press \u23e9 to skip)\n'
    #                             '**If this is a level role, simply type out the level number.**')
    #     await prompt.add_reaction('\u23e9')

    #     def msg_check(m):
    #         return m.author == ctx.author and m.channel == ctx.channel

    #     def r_check(p):
    #         return p.message_id == prompt.id and p.user_id == ctx.author.id and str(p.emoji) == '\u23e9'

    #     while True:
    #         done, pending = await asyncio.wait([
    #             self.bot.wait_for('message', check=msg_check),
    #             self.bot.wait_for('raw_reaction_add', check=r_check)
    #         ], return_when=asyncio.FIRST_COMPLETED, timeout=60)

    #         for future in pending:
    #             future.cancel()
    #         if len(done) == 0:
    #             return await ctx.send('BAKA, imagine going AFK now ((')
    #         payload = done.pop().result()
    #         role_id = 0
    #         level = False

    #         if isinstance(payload, discord.Message):
    #             msg = payload
    #             if msg.content.isdigit():
    #                 if 0 < int(msg.content) < 69:
    #                     role_id = int(msg.content)
    #                     level = True
    #                     break
    #             try:
    #                 role = await commands.RoleConverter().convert(ctx, msg.content)
    #                 role_id = role.id
    #                 break
    #             except commands.BadArgument:
    #                 await ctx.send(f'I couldn\'t find a role that matches `{msg.content}`... '
    #                                f'try again and make sure you spelled things right!')
    #         else:
    #             break

    #     prompt = await ctx.send('Description? (optional, press \u23e9 to skip).')
    #     await prompt.add_reaction('\u23e9')
    #     done, pending = await asyncio.wait([
    #         self.bot.wait_for('message', check=msg_check),
    #         self.bot.wait_for('raw_reaction_add', check=r_check)
    #     ], return_when=asyncio.FIRST_COMPLETED, timeout=60)

    #     for future in pending:
    #         future.cancel()
    #     if len(done) == 0:
    #         return await ctx.send('BAKA, imagine going AFK now ((')
    #     payload = done.pop().result()
    #     desc = ''
    #     if isinstance(payload, discord.Message):
    #         desc = payload.content

    #     await ctx.send('Last but not least, emoji? ))')
    #     while True:
    #         msg = await self.wait_for_msg(ctx, 60)
    #         if not msg:
    #             return
    #         try:
    #             emoji = await commands.EmojiConverter().convert(ctx, msg.content)
    #             break
    #         except commands.BadArgument:
    #             if is_emoji(msg.content):
    #                 emoji = msg.content
    #                 break
    #             else:
    #                 await ctx.send(f'I couldn\'t find an emoji called `{msg.content}`... '
    #                                f'if it\'s a custom one, make sure it\'s in this server!')

    #     end = int(time.time() + duration)
    #     end_dt = discord.utils.utcnow() + timedelta(seconds=duration) 
    #     embed = discord.Embed(
    #         title=prize + f' - {winners} Winners',
    #         description=desc,
    #         color=discord.Colour.blue()
    #     ).add_field(
    #         name='\U0001f451 Host', value=ctx.author.mention, inline=False
    #     ).add_field(
    #         name='\U000023f0 Ending', value=discord.utils.format_dt(end_dt, 'R'), inline=False
    #     ).set_footer(
    #         text='React with the first emoji below to enter',
    #         icon_url='https://cdn.discordapp.com/emojis/795660003369025546.gif?v=1'
    #     )# .set_thumbnail(url='https://cdn.discordapp.com/attachments/725093929481142292/792530547120799764/'
    #       #                  'download_-_2020-12-26T181245.032.png')
    #     if role_id:
    #         if level:
    #             value = f'Must be at least **Level {role_id}**'
    #         else:
    #             mention = ctx.guild.get_role(role_id).mention
    #             value = f'Must have the {mention} role'
    #         embed = embed.to_dict()
    #         embed['fields'].insert(0, {'name': '\U0001f4dd Requirement', 'value': value, 'inline': False})
    #         embed = discord.Embed.from_dict(embed)
    #     embed = await channel.send(embed=embed)
    #     await embed.add_reaction(emoji)
    #     await channel.send('<@&728666898597937163>')
    #     self.msg_ids.append(embed.id)
    #     query = '''INSERT INTO gvwys (ch_id, msg_id, prize, winners, host_id, role_id, "end", ended, emoji) 
    #                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
    #             '''
    #     await self.bot.db.execute(
    #         query, channel.id, embed.id, prize, winners, ctx.author.id, role_id, end, False, str(emoji))
    #     await ctx.send(f'Your giveaway has started! {emoji}')

    #     async def task():
    #         await asyncio.sleep(duration)
    #         res = await self.bot.db.fetchrow('SELECT * FROM gvwys WHERE msg_id = $1', embed.id)
    #         await self.win(res)

    #     self.bot.loop.create_task(task())

    # @commands.command(aliases=['timers'])
    # async def giveaways(self, ctx):
    #     res = await self.bot.db.fetch('SELECT msg_id, ch_id, prize, "end" '
    #                                   'FROM gvwys WHERE ended = $1', False)
    #     if not res:
    #         return await ctx.send('No active giveaways.')
    #     desc = []
    #     for row in res:
    #         jump_url = f'https://discord.com/channels/{ctx.guild.id}/{row["ch_id"]}/{row["msg_id"]}'
    #         delta = precisedelta(row['end'] - time.time())
    #         desc.append(f'[**{row["prize"]}**]({jump_url})\nEnds in {delta}')

    #     embed = discord.Embed(
    #         title='Active Giveaways in SLounge',
    #         color=ctx.author.color,
    #         description='\n\n'.join(desc)
    #     ).set_thumbnail(url=ctx.guild.icon_url_as(format='png'))
    #     await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(Giveaway(bot))
