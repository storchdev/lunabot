from discord.ext import commands


class InvalidModalField(Exception): ...


class GuildOnly(commands.CheckFailure): ...


class InvalidURL(Exception): ...
