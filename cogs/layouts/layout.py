import json
import re
from typing import TYPE_CHECKING

import discord
from discord.ext import commands
from jinja2 import Environment, TemplateError

if TYPE_CHECKING:
    from bot import LunaBot


class LayoutContext:
    def __init__(
        self,
        *,
        author: discord.Member | None = None,
        channel: discord.TextChannel | None = None,
        guild: discord.Guild | None = None,
        message: discord.Message | None = None,
    ):
        if author is None and message is not None:
            author = message.author
        if channel is None and message is not None:
            channel = message.channel
        if guild is None:
            if channel is not None:
                guild = channel.guild
            if author is not None:
                guild = author.guild

        self.author = author
        self.channel = channel
        self.guild = guild
        self.message = message


SPECIAL_REPLS = {
    "membercount": lambda ctx: ctx.guild.member_count,
    "mention": lambda ctx: ctx.author.mention,
    "username": lambda ctx: ctx.author.name,
    "name": lambda ctx: ctx.author.display_name,
    "nickname": lambda ctx: ctx.author.display_name,
    "server": lambda ctx: ctx.guild.name,
    "channel": lambda ctx: ctx.channel.mention,
    "channelname": lambda ctx: ctx.channel.name,
    "channelid": lambda ctx: ctx.channel.id,
    "serverid": lambda ctx: ctx.guild.id,
    "userid": lambda ctx: ctx.author.id,
    "boostcount": lambda ctx: ctx.guild.premium_subscription_count,
    "boostlevel": lambda ctx: ctx.guild.premium_tier,
}


class Layout:
    def __init__(
        self,
        bot: "LunaBot" = None,
        name: str | None = None,
        content: str | None = None,
        embed_names: list[str] | None = None,
    ):
        self.bot = bot
        self.name = name
        self.content = content
        self.embed_names = embed_names if embed_names else []

    def __bool__(self):
        return bool(self.content) or bool(self.embed_names)

    # @staticmethod
    # def fill_text_one(text, key, value):
    #     return text.replace('{' + key + '}', str(value))

    # @staticmethod
    # def fill_embed_one(embed, key, value):
    #     embed = embed.copy()
    #     for field in embed.fields:
    #         field.name = Layout.fill_text_one(field.name, key, value)
    #         field.value = Layout.fill_text_one(field.value, key, value)

    #     if embed.title: embed.title = Layout.fill_text_one(embed.title, key, value)
    #     if embed.footer: embed.set_footer(text=Layout.fill_text_one(embed.footer.text, key, value))
    #     if embed.author: embed.author.name = Layout.fill_text_one(embed.author.name, key, value)
    #     if embed.description: embed.description = Layout.fill_text_one(embed.description, key, value)

    #     return embed

    @staticmethod
    async def fill_text(
        text: str,
        repls: dict[str, str],
        *,
        ctx: LayoutContext | None = None,
        special: bool = True,
        jinja: bool = False,
    ) -> str:
        if special and ctx is None:
            raise ValueError("Context is required for special replacements!")

        if jinja:
            try:
                env = Environment(enable_async=True)
                template = env.from_string(text)
                return await template.render_async(repls)
            except TemplateError as e:
                return f"`jinja error: {e}`"

        def replace_special(match):
            inside = match.group(1)
            if inside in SPECIAL_REPLS:
                return str(SPECIAL_REPLS[inside](ctx))
            return f"{{{inside}}}"

        def replace_single(match):
            inside = match.group(1)
            if inside in repls and not isinstance(repls[inside], list):
                return str(repls[inside])
            return f"{{{inside}}}"

        if special:
            text = re.sub(r"{(.*?)}", replace_special, text)
        text = re.sub(r"{(.*?)}", replace_single, text)

        # def replace_repeating(match):
        #     # example syntax: hi my name is {name}. i like [playing {sports} with {friend} |and|].
        #     # sports is a list and friend is a string.
        #     inside = match.group(1)
        #     delimiter = match.group(2)
        #     delimiter = re.sub(r'(enter|return|newline|\\n)', '\n', delimiter, re.IGNORECASE)
        #     keys = re.findall(r'{(.*?)}', inside)

        #     n = None
        #     for key in keys:
        #         value = repls.get(key)
        #         if value is None:
        #             continue

        #         if n is None:
        #             n = len(value)
        #         elif len(value) != n:
        #             raise ValueError(f'List {key} has different length than other lists!')

        #     blocks = []
        #     for i in range(n):
        #         ith_repls = {}
        #         for key in keys:
        #             value = repls.get(key)
        #             ith_repls[key] = value[i]

        #         blocks.append(await Layout.fill_text(inside, ith_repls, ctx=ctx, special=special))

        #     return delimiter.join(blocks)

        # text = re.sub(r'\[(.*?)\s?\|((?:[^|\\]|\\.)*)\|\s?\]', replace_repeating, text, flags=re.DOTALL)
        return text

    @staticmethod
    async def fill_embed(
        _embed: discord.Embed,
        repls: dict[str, str],
        *,
        ctx: LayoutContext | None = None,
        special: bool = True,
        jinja: bool = False,
    ) -> discord.Embed:
        embed = _embed.copy()
        for field in embed.fields:
            field.name = await Layout.fill_text(
                field.name, repls, ctx=ctx, special=special, jinja=jinja
            )
            field.value = await Layout.fill_text(
                field.value, repls, ctx=ctx, special=special, jinja=jinja
            )

        if embed.title:
            embed.title = await Layout.fill_text(
                embed.title, repls, ctx=ctx, special=special, jinja=jinja
            )
        if embed.footer:
            embed.set_footer(
                text=await Layout.fill_text(
                    embed.footer.text, repls, ctx=ctx, special=special, jinja=jinja
                )
            )
        if embed.author:
            embed.author.name = await Layout.fill_text(
                embed.author.name, repls, ctx=ctx, special=special, jinja=jinja
            )
        if embed.description:
            embed.description = await Layout.fill_text(
                embed.description, repls, ctx=ctx, special=special, jinja=jinja
            )

        return embed

    @property
    def embeds(self):
        embeds = []
        for name in self.embed_names:
            embeds.append(self.bot.get_embed(name))
        return embeds

    def to_dict(self):
        if self.name is None:
            return {"name": None, "content": self.content, "embeds": self.embed_names}
        else:
            return {
                "name": self.name,
            }

    def to_json(self, *, indent: int = 4):
        return json.dumps(self.to_dict(), indent=indent)

    async def send(
        self,
        msgble: discord.abc.Messageable | discord.Interaction,
        ctx: commands.Context | LayoutContext | None = None,
        *,
        repls: dict | None = None,
        special: bool = True,
        jinja: bool = False,
        **kwargs,
    ) -> discord.Message | None:
        if isinstance(msgble, discord.Message):
            if ctx is None:
                ctx = LayoutContext(message=msgble)
            if "reply" in kwargs and kwargs["reply"]:
                send_func = msgble.reply
            else:
                send_func = msgble.channel.send
        elif isinstance(msgble, commands.Context):
            if ctx is None:
                ctx = msgble

            if msgble.interaction is not None:
                if msgble.interaction.response.is_done():
                    send_func = msgble.interaction.followup.send
                else:
                    send_func = msgble.interaction.response.send_message

            send_func = msgble.send
        elif isinstance(msgble, discord.Interaction):
            if ctx is None:
                ctx = LayoutContext(
                    author=msgble.user,
                    channel=msgble.channel,
                )
            if msgble.response.is_done():
                send_func = msgble.followup.send
            else:
                send_func = msgble.response.send_message
        else:
            if ctx is None:
                ctx = LayoutContext(channel=msgble)
            send_func = msgble.send

        if repls is None:
            repls = {}

        if self.content:
            content = await self.fill_text(
                self.content, repls, ctx=ctx, special=special, jinja=jinja
            )
        else:
            content = None

        embeds = [
            await self.fill_embed(embed, repls, ctx=ctx, special=special, jinja=jinja)
            for embed in self.embeds
        ]

        cleaned_kwargs = {}

        if not isinstance(msgble, discord.Interaction):
            keys = ["mention_author", "delete_after"]

            # cleaned_kwargs = {
            #     'mention_author': kwargs.get('mention_author', False),
            #     'delete_after': kwargs.get('delete_after', None)
            # }
        else:
            keys = ["ephemeral"]

        keys.append("view")
        keys.append("allowed_mentions")

        for key in keys:
            if key in kwargs:
                cleaned_kwargs[key] = kwargs[key]

        try:
            return await send_func(content=content, embeds=embeds, **cleaned_kwargs)
        except discord.Forbidden:
            self.bot.log(f"failed to send layout, msgble={msgble}", "layout")

    async def edit(
        self,
        editable: discord.Message | discord.Interaction,
        ctx: commands.Context | LayoutContext | None = None,
        *,
        repls: dict | None = None,
        special: bool = True,
        jinja: bool = False,
        **kwargs,
    ):
        if isinstance(editable, discord.Message):
            if ctx is None:
                ctx = LayoutContext(message=editable)
            edit_func = editable.edit
        elif isinstance(editable, discord.Interaction):
            if ctx is None:
                ctx = LayoutContext(
                    author=editable.user,
                    channel=editable.channel,
                )
            edit_func = editable.response.edit_message
        else:
            raise ValueError("Editable must be a message or interaction.")

        if repls is None:
            repls = {}

        if self.content:
            content = await self.fill_text(
                self.content, repls, ctx=ctx, special=special, jinja=jinja
            )
        else:
            content = None

        embeds = []
        for embed in self.embeds:
            embeds.append(
                await self.fill_embed(
                    embed, repls, ctx=ctx, special=special, jinja=jinja
                )
            )

        cleaned_kwargs = {}
        if "view" in kwargs:
            cleaned_kwargs["view"] = kwargs["view"]

        # TODO: support more kwargs

        return await edit_func(content=content, embeds=embeds, **cleaned_kwargs)
