import json
import os
import logging
from pprint import pprint

from discord_slash.utils import manage_commands

from source import utilities
from source.shared import reasonOption

log = utilities.getLog("slashParser", level=40)

path = "data/commands/"


def read(name: str):
    """Read a json file and returns its information"""
    log.debug(f"Reading {name} from json")
    _path = path + f"{name}.json"
    if not os.path.isfile(_path):
        log.error(f"{_path} does not exist")
        raise FileNotFoundError

    data = json.load(open(_path, "r"))
    return data


def getDecorator(name: str):
    """Get the decorator data for a command"""
    return read(name)["decorator"]


def write(name: str, description: str, options: list = None, guild_ids: list = None, **kwargs):
    """Writes a basic command json fle
    Used in development"""
    # assure basic information

    # determine filename
    _path = f"{path}{name}"
    if kwargs.get("subcommand_group"):
        _path += f".{kwargs['subcommand_group']}"
    if kwargs.get("base"):
        _path += f".{kwargs['base']}"

    # create data
    data = {"decorator": {"name": name.lower(), "description": description, "options": options, "guild_ids": guild_ids}}
    for kw in kwargs:
        data["decorator"][kw] = kwargs[kw]

    # write to file
    json.dump(data, open(f"{_path}.json", "w"), indent=2)
    print(f"**jsonManager.getDecorator(\"{_path.split('/')[-1]}\")")


# write(
#     base="user",
#     subcommand_group="warn",
#     name="clear",
#     description="Clears all warnings from a user",
#     options=[
#         manage_commands.create_option(
#             name="user",
#             option_type=6,
#             description="The user in question",
#             required=True,
#         ),
#         reasonOption,
#     ],
# )
