import expr 
import re


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


    def __init__(self):
        self.funcs = {'th': self.th} 
        self.vars_builtin = {'name': 'bob', 'mention': '<@6969>'}
        self.vars = {'n': 0}

    def th(self, num):
        return str(num) + 'th'

    def parse(self, text):
        
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
                        raise UnmatchedBracket(f'Unmatched bracket: [')

                    inside = ordered_eval(string[i+1:j])

                    match = re.match(r'(\d+|(?:.+?))\s*(<|<=|=<|==|=|=>|>=|>)\s*(\d+|(?:.+?)):[ ]?', inside)
                    if match is None:
                        raise InvalidCondition(f'Invalid condition in {inside}')
                    
                    left = match.group(1)
                    left = clean(left)
                    op = match.group(2)
                    if op == '=':
                        op = '=='
                    right = match.group(3)
                    right = clean(right)

                    if eval(f'{left} {op} {right}') is True:
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
                        raise UnmatchedBracket(f'Unmatched bracket: (')

                    inside = ordered_eval(string[i+1:j])
                    args = inside.split(',')
                    args = [arg.strip() for arg in args]
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
                        raise UnmatchedBracket(f'Unmatched bracket: $')

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
                        for name, val in self.vars.items():
                            exec(f'{name} = {val}', locals(), locals())
                        exec(''.join(string[i+3:j]))
                        g = locals() 
                        print(g)
                        if 'updates' in g:
                            for varname in g['updates'].split():
                                if varname in g:
                                    self.vars[varname] = g[varname]
                    inner()
                    i += j - i + 4
                elif string[i] == '{':
                    j = i+1
                    while j < len(string) and string[j] != '}':
                        j += 1
                    varname = ''.join(string[i+1:j])
                    if varname in self.vars_builtin:
                        repl = self.vars_builtin[varname]
                    elif varname in self.vars:
                        repl = self.vars[varname]
                    else:
                        repl = ''
                    newstr.extend([char for char in str(repl)])
                    i += j - i + 1
                else:
                    newstr.append(string[i])
                    i += 1

            return ''.join(newstr)
        
        return ordered_eval(text)

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