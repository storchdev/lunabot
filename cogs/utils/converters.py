import re

from discord.ext import commands

__all__ = ("TimeConverter",)

time_regex = re.compile(r"(\d{1,5}(?:[.,]?\d{1,5})?)([smhd])")
time_dict = {"h": 3600, "s": 1, "m": 60, "d": 86400}


class TimeConverter(commands.Converter):
    async def convert(self, ctx, argument):
        matches = time_regex.findall(argument.lower())
        time = 0
        for v, k in matches:
            try:
                time += time_dict[k] * float(v)
            except KeyError:
                await ctx.send(
                    "{} is an invalid time-key! h/m/s/d are valid!".format(k),
                    ephemeral=True,
                )
                return None
            except ValueError:
                await ctx.send("{} is not a number!".format(v), ephemeral=True)
                return None
        return time
