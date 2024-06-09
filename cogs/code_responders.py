from discord.ext import commands 
import json 
import asyncio
import traceback
import discord 
import re
from inspect import cleandoc
from .utils import Cooldown, Layout


def format_err(err):
    return ''.join(traceback.format_exception(type(err), err, err.__traceback__))


def wrap_code(code):
    code = code.replace('\t', '    ')
    code = '\n'.join(f'    {line}' for line in code.split('\n'))
    return f'''
async def __ex():
{code}
    '''


class AddCrFlags(commands.FlagConverter):
    trigger: str
    detection: str 
    ignoreErrors: bool = False 
    cdBucket: str = None
    cd: int = None



class CodeResponderItem:
    def __init__(self, name, trigger, detection, code, ignore_errors=False, cooldown=None):
        self.name = name 
        self.trigger = trigger 
        self.code = code 
        self.detection = detection
        self.ignore_errors = ignore_errors 

        if cooldown:
            self.cooldown = commands.CooldownMapping.from_cooldown(
                cooldown.rate, cooldown.per, cooldown.type
            )

    @classmethod 
    def from_db_row(cls, row):
        if row['cooldown']:
            cooldown_dict = json.loads(row['cooldown'])
            cooldown = Cooldown(
                cooldown_dict['rate'], 
                cooldown_dict['per'], 
                cooldown_dict['bucket_type']
            )
        else:
            cooldown = None

        return cls(
            row['name'],
            row['trigger'],
            row['detection'],
            row['code'],
            True, # row['ignore_errors'], TODO: reformat db or smth idk
            cooldown
        )


class CodeResponderError(Exception):
    ...


def split_text(text, separator):
    pieces = []
    current_piece = []
    inside_quotes = False
    i = 0

    while i < len(text):
        if text[i] == '"' and not inside_quotes:
            inside_quotes = True
            i += 1  # Skip the quote
            continue
        elif text[i] == '"' and inside_quotes:
            inside_quotes = False
            i += 1  # Skip the quote
            continue

        if not inside_quotes and text[i:i+len(separator)] == separator:
            pieces.append(''.join(current_piece))
            current_piece = []
            i += len(separator) - 1  # Adjust for separator length
        else:
            current_piece.append(text[i])
        
        i += 1

    # Add the last piece
    if current_piece:
        pieces.append(''.join(current_piece))

    return pieces


class CodeResponderAPI:
    def __init__(self, bot: commands.Bot, ctx):
        self.bot = bot 
        self.ctx = ctx 
        self.message = ctx.message

    async def getVar(self, name):
        return self.bot.vars.get(name)

    async def numberOfParts(self, separator=' '):
        return len(split_text(self.message.content, separator))

    async def getParts(self, spec, separator=' '):
        if spec.endswith('+'):
            i_str = spec[:-1]
        else:
            i_str = spec
        ok = True
        try:
            i = int(i_str)
            if i < 0:
                ok = False
        except ValueError:
            ok = False

        if not ok: 
            raise CodeResponderError(f"invalid spec {spec}, must be 0 or more")

        parts = split_text(self.message.content, separator)
        if i >= len(parts):
            raise CodeResponderError(f"not enough parts in message to get part {i}")

        if spec.endswith('+'):
            return separator.join(parts[i:])
        return parts[i] 

    async def toEmbed(self, string):
        if not isinstance(string, str):
            raise CodeResponderError(f".toEmbed takes a string")
        if string not in self.bot.embeds:
            return None
        return self.bot.embeds[string].copy()
    
    async def fillEmbed(self, embed, var, repl):
        if isinstance(embed, str):
            embed = await self.toEmbed(embed)
        elif not isinstance(embed, discord.Embed):
            embed = await self.toEmbed(str(embed))
        return Layout.fill_embed_one(embed, var, repl)

    async def fillText(self, string, var, repl):
        if not isinstance(string, str):
            raise CodeResponderError(f".fillText takes a string")

        var = '{' + str(var) + '}'
        repl = str(repl)
        return string.replace(var, repl)
    
    async def send(self, text='', embed=None):
        if not isinstance(text, str):
            raise CodeResponderError(f".send takes a string")
        if not isinstance(embed, discord.Embed) and embed is not None:
            raise CodeResponderError(f".send takes an embed object")
        if not text and not embed:
            raise CodeResponderError(f".send takes either text or an embed")

        await self.message.channel.send(text, embed=embed)
    
    async def reply(self, text='', embed=None, *, ping=True):
        if not isinstance(text, str):
            raise CodeResponderError(f".send takes a string")
        if not isinstance(embed, discord.Embed) and embed is not None:
            raise CodeResponderError(f".send takes an embed object")
        if not text and not embed:
            raise CodeResponderError(f".send takes either text or an embed")

        await self.message.reply(text, embed=embed, mention_author=ping)
        
    async def toUser(self, arg):
        if isinstance(arg, int):
            member = self.ctx.guild.get_member(arg)
            if member is not None:
                return member
            return None
        conv = commands.MemberConverter()
        try:
            return await conv.convert(self.ctx, arg)
        except commands.MemberNotFound:
            return None
    
    async def toRole(self, arg):
        if isinstance(arg, int):
            role = self.ctx.guild.get_role(arg)
            if role is not None:
                return role
            return None
        conv = commands.RoleConverter()
        try:
            return await conv.convert(self.ctx, arg)
        except commands.RoleNotFound:
            return None

    async def toChannel(self, arg):
        if isinstance(arg, int):
            channel = self.ctx.bot.get_channel(arg)
            if channel is not None:
                return channel
            return None
        conv = commands.TextChannelConverterConverter()
        try:
            return await conv.convert(self.ctx, arg)
        except commands.ChannelNotFound:
            return None

    async def toEmoji(self, arg):
        if isinstance(arg, int):
            emoji = self.ctx.bot.get_emoji(arg)
            if emoji is not None:
                return emoji
            return None

        conv = commands.EmojiConverter()
        try:
            return await conv.convert(self.ctx, arg)
        except commands.EmojiNotFound:
            return None

    async def addRole(self, user, role):
        if not isinstance(user, discord.Member):
            user = await self.toUser(user)
        if not isinstance(role, discord.Role):
            role = await self.toRole(role)

        try:
            await user.add_roles(role)
        except discord.Forbidden:
            raise CodeResponderError(f"missing perms to add {role.name} to {user.name}")

    async def removeRole(self, user, role):
        if not isinstance(user, discord.Member):
            user = await self.toUser(user)
        if not isinstance(role, discord.Role):
            role = await self.toRole(role)

        try:
            await user.remove_roles(role)
        except discord.Forbidden:
            raise CodeResponderError(f"missing perms to remove {role.name} from {user.name}")

    async def hasRole(self, user, role):
        if not isinstance(user, discord.Member):
            user = await self.toUser(user)
        if not isinstance(role, discord.Role):
            role = await self.toRole(role)
        return role in user.roles
    
    async def addReaction(self, emoji):
        if isinstance(emoji, int):
            emoji = self.ctx.bot.get_emoji(emoji)
            if emoji is None:
                raise CodeResponderError(f"emoji {emoji} not found")
        try:
            await self.message.add_reaction(emoji)
        except discord.NotFound:
            raise CodeResponderError(f"emoji {emoji.name} not found")
    
    async def removeReaction(self, emoji):
        if isinstance(emoji, int):
            emoji = self.ctx.bot.get_emoji(emoji)
            if emoji is None:
                raise CodeResponderError(f"emoji {emoji} not found")
        try:
            await self.message.add_reaction(emoji)
        except discord.NotFound:
            raise CodeResponderError(f"emoji {emoji.name} not found")


class CodeResponders(commands.Cog):

    def __init__(self, bot):
        self.bot = bot 
        self.lookup = {}
        self.code_responders = []
        self.process_n = 0

    async def cog_check(self, ctx):
        return ctx.author.id == self.bot.STORCH_ID or ctx.author.guild_permissions.administrator

    async def cog_load(self):
        query = 'SELECT * FROM code_responders'
        rows = await self.bot.db.fetch(query)
        for row in rows:
            cr = CodeResponderItem.from_db_row(row)
            self.code_responders.append(cr)
            self.lookup[cr.name] = cr 
        
    async def run_code(self, ctx, code: str) -> dict: 
        api = CodeResponderAPI(self.bot, ctx)

        g = {}
        builtins = __builtins__.copy()
        del builtins['__import__']
        g['__builtins__'] = builtins
        g['LB'] = api
        g['BOT'] = self.bot 
        g['MSG'] = ctx.message 
        g['CHANNEL'] = ctx.channel
        g['USER'] = ctx.message.author
        loc = {}
        resp = {}
        
        try:
            def executor():
                byte_code = compile(wrap_code(code), '<inline>', 'exec')
                exec(byte_code, g, loc)

            await self.bot.loop.run_in_executor(None, executor)
        except Exception as err:
            resp['status'] = 'syntax_error'
            resp['error'] = err
            raise CodeResponderError('syntax error')

        coro = loc['__ex']
        try:
            await asyncio.wait_for(coro(), timeout=3)
        except asyncio.TimeoutError:
            resp['status'] = 'timeout'
            return resp
        except Exception as err:
            # runtime error
            resp['status'] = 'runtime_error'
            resp['error'] = err
            return resp

        resp['status'] = 'ok'
        return resp

    @commands.group(aliases=['coderesponder'], invoke_without_command=True)
    async def cr(self, ctx):
        await ctx.send_help(ctx.command)

    @cr.command(aliases=['create'])
    async def add(self, ctx, *, flags: AddCrFlags):
        name = name.lower()
        if name in self.lookup:
            await ctx.send("A coderesponder with this name already exists.")
            return 

        trigger = flags.trigger
        detection = flags.detection

        if detection not in ['full', 'word', 'start', 'end', 'regex']:
            await ctx.send("Invalid detection method. Must be one of: `full`, `word`, `start`, `end`, `regex`.")
            return

        ignore_errors = flags.ignoreErrors
        if flags.cd is not None:
            if flags.cdBucket is None:
                await ctx.send("Cooldown bucket must be specified if cooldown is set.")
                return
            
            if flags.cdBucket not in ['g', 'c', 'u']:
                await ctx.send("Invalid cooldown bucket. Must be one of: `g`, `c`, `u`.")
                return

            if flags.cdBucket == 'g':
                bucketstr = 'global'
            elif flags.cdBucket == 'c':
                bucketstr = 'channel'
            elif flags.cdBucket == 'u':
                bucketstr = 'user'
            cd = Cooldown(1, flags.cd, bucketstr)
        else:
            cd = None 

        await ctx.send('Please send the code that should be executed when this responder is triggered. Press `cancel` to cancel.') 

        while True:
            message = await self.bot.wait_for('message', check=lambda m: m.author == ctx.author and m.channel == ctx.channel)
            if message.content.lower() == 'cancel':
                await ctx.send('ok')
                return

            code = message.content.strip('`').removeprefix('py')

            try:
                compile(wrap_code(code), '<inline>', 'exec')
            except Exception as err:
                err_str = ''.join(traceback.format_exception(type(err), err, err.__traceback__)[3:])
                await message.channel.send(f'There was an error when compiling (probably a syntax error), please try again:\n```py\n{err_str}```')
                continue
            
            await ctx.send('No syntax errors, great! Send a message to give your code a test run, or type `skip`.')
            message = await self.bot.wait_for('message', check=lambda m: m.author == ctx.author and m.channel == ctx.channel)

            if message.content.lower() == 'skip':
                break

            resp = await self.run_code(await self.bot.get_context(message), code)
            if resp['status'] == 'err':
                err_str = resp['err_str']
                await message.channel.send(f'(As expected) Your code encountered an error:\n```py\n{err_str}```\nTake your time debugging and re-send whenever you\'re ready.')
                continue
            elif resp['status'] == 'timeout':
                await message.channel.send(f'Your code timed out! Ensure that there are no infinite loops and re-send whenever you\'re ready.')
                continue
            
            await message.channel.send('Nice, your code ran smoothly with no errors!\nDid it do what you intended? Type `yes` to confirm, type `no` to re-send.')
            message = await self.bot.wait_for('message', check=lambda m: m.author == ctx.author and m.channel == ctx.channel)
            if message.content.lower() == 'yes':
                break 
            else:
                await message.channel.send('Alright, take your time debugging and re-send whenever you\'re ready.')

        item = CodeResponderItem(name, trigger, detection, code, ignore_errors, cd)
        self.lookup.add(name)
        self.code_responders.append(item)
        query = '''INSERT INTO code_responders 
                       (name, trigger, detection, code, cooldown, author_id) 
                   VALUES
                       ($1, $2, $3, $4, $5, $6)
                '''

        await self.bot.db.execute(query, name, trigger, detection, code, cd.jsonify(), ctx.author.id)
        await ctx.send(f'Congratulations, you successfully created a coderesponder named `{name}`!')
    
    @cr.command(aliases=['delete'])
    async def remove(self, ctx, *, name):
        name = name.lower()

        if name not in self.lookup:
            await ctx.send("No coderesponder with this name exists.")
            return 

        self.lookup.remove(name)
        for i in range(len(self.code_responders)):
            if self.code_responders[i].name == name:
                del self.code_responders[i]
                break

        query = 'DELETE FROM code_responders WHERE name = $1'
        await self.bot.db.execute(query, name)

        await ctx.send(f'Coderesponder `{name}` has been deleted.')
    
    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return 
        
        respond = False
        lower = message.content.lower()

        for item in self.code_responders:
            if item.detection == 'full':
                if lower == item.name:
                    respond = True
                    break
            elif item.detection == 'word':
                if item.name in lower.split():
                    respond = True
                    break
            elif item.detection == 'start':
                if lower.startswith(item.name):
                    respond = True
                    break
            elif item.detection == 'end':
                if lower.endswith(item.name):
                    respond = True
                    break
            elif item.detection == 'regex':
                if re.search(item.regex, message.content):
                    respond = True 
                    break
        
        if respond:
            resp = await self.run_code(await self.bot.get_context(message), item.code)
            if resp['status'] == 'ok':
                return

            tb = format_err(resp['error'])            
            short_err = str(resp['error'])

            if resp['status'] == 'runtime_error':
                if not item.ignore_errors:
                    await message.channel.send(f'Code encountered a runtime error!\n`{short_err}`')
                storch = self.bot.get_user(self.bot.STORCH_ID)
                await storch.send(f'Coderesponder encountered an error!\n```py\n{tb}```{message.jump_url}')
            elif resp['status'] == 'timeout':
                if not item.ignore_errors:
                    await message.channel.send('Code timed out!')
                storch = self.bot.get_user(self.bot.STORCH_ID)
                await storch.send(f'Code timed out! {message.jump_url}')



async def setup(bot):
    cog = CodeResponders(bot)
    await bot.add_cog(cog)

