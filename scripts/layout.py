#!/usr/bin/env python3
"""Inspect and edit layouts/embeds on the live bot.

Layouts (`layouts` table -> bot.layouts) are content + a list of embed names.
The actual title/description/color text usually lives in the referenced
embed(s) (`embeds` table -> bot.embeds). Editing either one requires writing
the DB row *and* updating the live in-memory cache in the same operation --
this script does both remotely via /api/exec, the same way the `!embed edit`
and `!layout edit` Discord commands do.

Usage:
    scripts/layout.py get <name> [-o FILE]        # dump layout+embeds JSON
    scripts/layout.py set-embed <embed_name> FILE  # push an edited embed dict back
    scripts/layout.py set-content <layout_name> [FILE | -]  # edit layout.content only
    scripts/layout.py list [substring]             # fuzzy-list layout names
"""

import argparse
import ast
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _remote import exec_code_or_die  # noqa: E402


def cmd_get(args):
    code = f"""
import json
name = {args.name!r}
l = bot.layouts.get(name)
if l is None:
    result = {{"error": f"no layout named {{name!r}}"}}
else:
    embeds = {{}}
    for en in l.embed_names:
        e = bot.embeds.get(en)
        embeds[en] = e.to_dict() if e else None
    result = {{"name": name, "content": l.content, "embed_names": l.embed_names, "embeds": embeds}}
json.dumps(result, indent=2)
"""
    raw = exec_code_or_die(code)
    data = json.loads(
        ast.literal_eval(raw)
    )  # repr(str) -> str, then parse the JSON it contains
    text = json.dumps(data, indent=2, ensure_ascii=False)
    if args.out:
        Path(args.out).write_text(text)
        print(f"Wrote {args.out}", file=sys.stderr)
    else:
        print(text)


def cmd_set_embed(args):
    embed_dict = json.loads(Path(args.file).read_text())
    json_str = json.dumps(embed_dict)
    code = f"""
import discord, json
name = {args.name!r}
data = json.dumps(json.loads({json_str!r}), indent=4)
await bot.db.execute(
    "INSERT INTO embeds (name, embed) VALUES ($1, $2) "
    "ON CONFLICT (name) DO UPDATE SET embed = EXCLUDED.embed",
    name, data,
)
bot.embeds[name] = discord.Embed.from_dict(json.loads(data))
f"Updated embed {{name!r}}"
"""
    print(exec_code_or_die(code))


def cmd_set_content(args):
    if args.file == "-":
        content = sys.stdin.read()
    else:
        content = Path(args.file).read_text()
    code = f"""
import json
from cogs.layouts.layout import Layout
name = {args.name!r}
content = {content!r}
if name not in bot.layouts:
    result = f"no layout named {{name!r}}"
else:
    embed_names = bot.layouts[name].embed_names
    await bot.db.execute("UPDATE layouts SET content = $1 WHERE name = $2", content, name)
    bot.layouts[name] = Layout(bot, name, content, embed_names)
    result = f"Updated layout content for {{name!r}}"
result
"""
    print(exec_code_or_die(code))


def cmd_list(args):
    substr = args.substring or ""
    code = f"""
sorted([n for n in bot.layouts.keys() if {substr!r} in n])
"""
    raw = exec_code_or_die(code)
    for name in ast.literal_eval(raw):
        print(name)


def main():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_get = sub.add_parser("get", help="dump a layout's content + resolved embed JSON")
    p_get.add_argument("name")
    p_get.add_argument("-o", "--out", help="write to this file instead of stdout")
    p_get.set_defaults(func=cmd_get)

    p_set_embed = sub.add_parser(
        "set-embed", help="push an edited embed dict (JSON file) back to DB + cache"
    )
    p_set_embed.add_argument("name")
    p_set_embed.add_argument(
        "file", help="path to a JSON file containing the full embed dict"
    )
    p_set_embed.set_defaults(func=cmd_set_embed)

    p_set_content = sub.add_parser(
        "set-content",
        help="overwrite a layout's raw content (text), keeping its embed_names",
    )
    p_set_content.add_argument("name")
    p_set_content.add_argument("file", help="path to a text file, or '-' for stdin")
    p_set_content.set_defaults(func=cmd_set_content)

    p_list = sub.add_parser(
        "list", help="list layout names, optionally filtered by substring"
    )
    p_list.add_argument("substring", nargs="?")
    p_list.set_defaults(func=cmd_list)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
