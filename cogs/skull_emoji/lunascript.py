import discord 
from discord.ext import commands 
import expr 
from num2words import num2words
import re
import datetime 
import time
from levels import get_level 


class LayoutNotFound(Exception):
    pass


class Layout:
    def __init__(self, bot, name, content=None, embed=None):
        self.bot = bot
        self.name = name
        self.content = content

        if embed is None:
            self.embed = None 
        else:
            self.embed = bot.embeds[embed]
    
    @classmethod
    def from_name(cls, bot, name):
        if name not in bot.layouts:
            raise LayoutNotFound(f'Layout {name} not found')
        return cls(bot, name, bot.layouts[name][0], bot.layouts[name][1])
    
    
def clean(token):
    try:
        token = int(token)
    except ValueError:
        try:
            token = float(token)
        except ValueError:
            repl = r'\"'
            token = f'''"{token.replace('"', repl)}"'''
    return token 


class ScriptContext:
    def __init__(self, bot, channel, guild=None, member=None, message=None, args=None):
        self.bot = bot 
        self.guild = guild 
        self.channel = channel 
        self.member = member 
        self.message = message 
        self.vars = self.bot.vars

        self.args = {}
        if isinstance(args, list) or isinstance(args, tuple):
            for i, arg in enumerate(args):
                self.args[f'${i+1}'] = arg 
        elif isinstance(args, dict):
            for name, val in args.items():
                self.args[name] = val

        self.vars_builtin_tuples = {
            ('serverid',): self.serverid,
            ('server', 'servername'): self.servername,
            ('members', 'membercount', 'servermembercount'): self.membercount,
            ('boosts', 'boostcount', 'serverboostcount'): self.boosts,
            ('boostlevel', 'serverboostlevel', 'boosttier', 'serverboosttier'): self.boostlevel,
            ('channelid',): self.channelid,
            ('channel', 'channelmention'): self.channelmention,
            ('channelname',): self.channelname,
            ('memberid',): self.memberid,
            ('mention', 'ping', 'member', 'membermention'): self.membermention,
            ('avatar', 'memberavatar', 'pfp', 'memberpfp'): self.avatar,
            ('memberusername', 'username'): self.memberusername,
            ('membername', 'name', 'displayname', 'memberdisplayname'): self.membername
        }
        self.funcs_tuples = {
            ('th', 'ordinal'): self.th,
            ('now',): self.now,
            ('timethingy',): self.timethingy,
            ('xp',): self.xp,
            ('level',): self.level
        }
        self.vars_builtin = {}
        for k, v in self.vars_builtin_tuples.items():
            for n in k:
                self.vars_builtin[n] = v
        self.funcs = {}
        for k, v in self.funcs_tuples.items():
            for n in k:
                self.funcs[n] = v

    @classmethod 
    def from_ctx(cls, ctx, args=None):
        return cls(ctx.bot, ctx.channel, ctx.guild, ctx.author, ctx.message, args)
    
    # make a decorator that will add the function to self.repls
    # make it take an optional argument called aliases 

    def servername(self):
        """Name of the current server"""
        return self.guild.name
    
    def serverid(self):
        """ID of the current server"""
        return self.guild.id

    def membercount(self):
        """Number of members in the current server"""
        return len(self.guild.members) 

    def boosts(self):
        """Number of boosts in the current server"""
        return self.guild.premium_subscription_count

    def boostlevel(self):
        """Boost level of the current server"""
        return self.guild.premium_tier

    def channelid(self):
        """ID of the current channel"""
        return self.channel.id

    def channelmention(self):
        """Mention of the current channel"""
        return self.channel.mention

    def channelname(self):
        """Name of the current channel"""
        return self.channel.name

    def memberid(self):
        """ID of the current member"""
        return self.member.id
    
    def membermention(self):
        """Mention of the current member"""
        return self.member.mention

    def avatar(self):
        """Avatar of the current member"""
        asset = self.member.display_avatar 
        if asset.is_animated():
            return asset.with_format('gif').url 
        else:
            return asset.with_format('png').url

    def memberusername(self):
        """Username of the current member"""
        return self.member.name 

    def membername(self):
        """Display name of the current member"""
        return self.member.display_name 

    def th(self, num: str):
        """Converts a number to its ordinal form"""
        return num2words(int(num), to='ordinal_num')
    
    def now(self):
        """Gets the current time as a number"""
        return int(time.time())
    
    def timethingy(self, timestamp: str, fmt='R'):
        """Turns a time number into a readable time thingy on Discord"""
        timestamp = int(timestamp)
        return discord.utils.format_dt(datetime.datetime.fromtimestamp(timestamp), fmt)
    
    def xp(self, memberid: str):
        """Gets the XP of a member"""
        return self.bot.xp_cache[int(memberid)]
    
    def level(self, memberid: str):
        """Gets the level of a member"""
        return get_level(self.bot.xp_cache[int(memberid)])


    
class TextEmbed:
    def __init__(self, text=None, embed=None):
        self.text = text 
        if embed is None:
            self.embed = None 
        else:
            self.embed = embed.copy()


class LunaScript(TextEmbed):

    def __init__(self, msgble, text=None, embed=None, **kwargs):
        super().__init__(text, embed)
        if isinstance(msgble, commands.Context):
            self.script_ctx = ScriptContext.from_ctx(msgble, kwargs.pop('args'))
            self.msgble = self.script_ctx.channel
        else:
            if 'channel' in kwargs:
                channel = kwargs.pop('channel')
            else:
                channel = msgble

            args = kwargs.pop('args', None)
            if 'guild' not in kwargs and 'member' in kwargs:
                kwargs['guild'] = kwargs['member'].guild

            self.script_ctx = ScriptContext(kwargs.pop('bot'), args=args, channel=channel, **kwargs)
            self.msgble = msgble
        self.parser = LunaScriptParser(self.script_ctx)

    @classmethod 
    def from_layout(cls, msgble, layout, **kwargs):
        return cls(msgble, layout.content, layout.embed, bot=layout.bot, **kwargs)

    async def reply(self, msg):
        try:
            if self.text is None:
                text = None 
            else:
                text = await self.parser.parse(self.text)
            return await msg.reply(text, embed=await self.transform_embed())
        except LunaScriptError as e:
            return await msg.reply(f'An error occurred while parsing the LunaScript: `{e}`')

    async def send(self, *args, **kwargs):
        try:
            if self.text is None:
                text = None 
            else:
                text = await self.parser.parse(self.text)
            return await self.msgble.send(text, embed=await self.transform_embed(), *args, **kwargs)
        except LunaScriptError as e:
            return await self.msgble.send(f'An error occurred while parsing the LunaScript: `{e}`')

    async def transform_embed(self):
        if self.embed is None:
            return 
        if self.embed.title:
            self.embed.title = await self.parser.parse(self.embed.title)
        if self.embed.description:
            self.embed.description = await self.parser.parse(self.embed.description)
        for field in self.embed.fields:
            field.name = await self.parser.parse(field.name)
            field.value = await self.parser.parse(field.value)
        if self.embed.author.name is not None:
            self.embed.set_author(name=await self.parser.parse(self.embed.author.name), icon_url=self.embed.author.icon_url)
        if self.embed.footer.text is not None:
            self.embed.set_footer(text=await self.parser.parse(self.embed.footer.text), icon_url=self.embed.footer.icon_url)
        return self.embed
        

class LunaScriptError(Exception):
    pass

class UnmatchedBracket(LunaScriptError):
    pass

class InvalidMathExpression(LunaScriptError):
    pass 

class InvalidFunctionArgs(LunaScriptError):
    pass 

class InvalidCondition(LunaScriptError):
    pass



class LunaScriptParser:

    def __init__(self, script_ctx):
        self.script_ctx = script_ctx
        self.vars_builtin = self.script_ctx.vars_builtin
        self.funcs = self.script_ctx.funcs
        self.vars = self.script_ctx.bot.vars  
        self.args = self.script_ctx.args

        
    async def parse(self, text):
        return await self.script_ctx.bot.loop.run_in_executor(None, self.parse_sync, text)

    def parse_sync(self, text):
        
        def ordered_eval(string):
            string = [char for char in string]
            newstr = []
            i = 0
            while i < len(string):
                if i > 0 and string[i-1] == '\\':
                    newstr.append(string[i])
                    i += 1
                    continue
                if string[i] == '[':
                    # find the closing bracket
                    counter = 0
                    j = i+1

                    found = False
                    while j < len(string):
                        if string[j] == '[' and string[j-1] != '\\':
                            counter += 1
                        elif string[j] == ']' and string[j-1] != '\\':
                            if counter == 0:
                                found = True
                                break 
                            else:
                                counter -= 1 
                        j += 1  
                    if not found:
                        newstr.append('[')
                        i += 1
                        continue
                    inside = ordered_eval(string[i+1:j])

                    comp = True
                    match = re.match(r'(\d+|(?:.+?))\s*(<|<=|=<|==|=|=>|>=|>)\s*(\d+|(?:.+?)):[ ]?', inside)
                    if match is None:
                        match = re.match(r'(true|false):[ ]?', inside)
                        if match is None:
                            newstr.append('[')
                            i += 1
                            continue
                        comp = False

                    if comp: 
                        left = match.group(1)
                        left = clean(left)
                        op = match.group(2)
                        if op == '=':
                            op = '=='
                        right = match.group(3)
                        right = clean(right)

                        if eval(f'{left} {op} {right}') is True:
                            newstr.extend([char for char in inside[match.end():]])
                    else:
                        if match.group(1) == 'true':
                            newstr.extend([char for char in inside[match.end():]])

                    i += j - i + 1
                elif string[i] == '(':
                    k = i-1
                    while k >= 0 and string[k] != ' ':
                        k -= 1
                    funcname = ''.join(string[k+1:i])
                    if funcname not in self.funcs:
                        newstr += string[i]
                        i += 1
                        continue
                    # find the closing bracket
                    counter = 0
                    j = i+1
                    found = False

                    while j < len(string):
                        if string[j] == '(':
                            counter += 1
                        elif string[j] == ')':
                            if counter == 0:
                                found = True
                                break 
                            else:
                                counter -= 1 
                        j += 1  
                    if not found:
                        newstr.append('(')
                        i += 1
                        continue

                    inside = ordered_eval(string[i+1:j])
                    args = inside.split(',')
                    args = [arg.strip() for arg in args if arg != '']
                    func = self.funcs[funcname]
                    try:
                        repl = func(*args)
                    except TypeError:
                        raise InvalidFunctionArgs(f'Invalid arguments for {funcname}: {inside}')
                    for _ in range(len(funcname)):
                        newstr.pop()
                    newstr.extend([char for char in str(repl)])

                    i += j - i + 1
                elif string[i] == '$':
                    # find next $ 
                    j = i+1
                    found = False 

                    while j < len(string):
                        if string[j] == '$' and string[j-1] != '\\':
                            found = True
                            break
                        j += 1
                    if not found:
                        newstr.append('$')
                        i += 1
                        continue

                    inside = ordered_eval(string[i+1:j])
                    try:
                        repl = expr.evaluate(inside)
                    except Exception:
                        raise InvalidMathExpression(f'Invalid math expression: {inside}')
                    newstr.extend([char for char in str(repl)])
                    i += j - i + 1
                elif string[i] == '<':
                    if i >= len(string) - 2 or string[i+1].lower() != 's' or string[i+2] != '>':
                        newstr += string[i]
                        i += 1
                        continue
                    
                    j = i+3
                    found = False
                    while j < len(string) - 3:
                        if string[j:j+4] in (['<', '/', 's', '>'], ['<', '/', 'S', '>']):
                            found = True
                            break
                        j += 1

                    if not found:
                        raise UnmatchedBracket(f'Unmatched bracket: <s>')

                    def inner():
                        vars = [
                            ('bot', 'self.script_ctx.bot'), 
                            ('server', 'self.script_ctx.guild'), 
                            ('channel', 'self.script_ctx.channel'), 
                            ('member', 'self.script_ctx.member'), 
                            ('message', 'self.script_ctx.message')
                        ]
                        for name, val in vars:
                            exec(f'{name} = {val}', locals(), locals())
                        for name, val in self.vars.items():
                            if isinstance(val, str):
                                repl = '\\"'
                                val = '"' + val.replace('"', repl) + '"'
                            exec(f'{name} = {val}', locals(), locals())
                        exec(''.join(string[i+3:j]))
                        g = locals() 
                        if 'updates' in g:
                            for varname in g['updates'].split():
                                if varname in g:
                                    self.vars[varname] = g[varname]
                                    self.script_ctx.bot.vars[varname] = g[varname]
                    inner()
                    i += j - i + 4
                elif string[i] == '{':
                    j = i+1
                    while j < len(string) and string[j] != '}':
                        j += 1
                    varname = ''.join(string[i+1:j])
                    if varname in self.vars_builtin:
                        repl = self.vars_builtin[varname]()
                    elif varname in self.vars:
                        repl = self.vars[varname]
                    elif varname in self.args:
                        repl = self.args[varname]
                    else:
                        repl = ''
                    
                    newstr.extend([char for char in str(repl)])
                    i += j - i + 1
                else:
                    newstr.append(string[i])
                    i += 1

            return ''.join(newstr)
        
        return ordered_eval(text)

if __name__ == '__main__':
    teststr = '''<s>
    n+=1
    updates = 'n'
    </s>
    hi {mention}! you are the th({n}) person to use this.
    [{n}<10: we need $10-{n}$ more to reach 10]
    [{n}>=10: we reached 10!]'''
    teststr = 'th(6)'

    parser = LunaScriptParser()
    for i in range(100):
        print(parser.parse(teststr))
    print(parser.vars)