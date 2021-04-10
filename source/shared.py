import enum
import typing

import discord
from discord_slash.utils import manage_commands


class EventFlags(enum.IntEnum):
    memJoin = 1  # a user joined
    memLeave = 2  # a user left
    memUpdate = 3  # a user's details were updated
    memBan = 4  # a user was banned
    memUnban = 5  # a user was unbanned
    msgDelete = 6  # a message was deleted
    msgEdit = 7  # a message was edited
    chnlPurge = 8  # a channel was purged


class ModActions(enum.IntEnum):
    kick = 1
    ban = 2
    purge = 3
    warn = 4
    roleGive = 5
    roleRem = 6
    mute = 7
    unmute = 8


class Action:
    """
    A base action object

    :param actionType the type of action that this event is for
    :type actionType shared.ModActions

    :param moderator the user who made this action
    :type moderator discord.Member

    :param guild the guild of this action
    :type guild discord.Guild

    :param user the user who made this action (optional)
    :type user discord.Member

    :param event_type the type of event (default: "modAction")
    :type event_type str

    :param reason the reason for this action (optional)
    :type reason str

    :param extra Extra content for this event (optional)
    :type extra typing.Any
    """

    def __init__(
        self,
        actionType: ModActions,
        moderator: discord.Member,
        guild: discord.Guild,
        user: discord.Member = None,
        event_type: str = "modAction",
        reason: str = None,
        extra=None,
    ):
        self.event_type = event_type
        self.action_type = actionType
        self.guild: discord.Guild = guild
        self.user: typing.Optional[discord.Member] = user
        self.moderator: discord.Member = moderator
        self.reason: typing.Optional[str] = reason
        self.extra: typing.Any = extra


reasonOption = manage_commands.create_option(
    name="reason",
    description="Specify a reason for this action",
    option_type=str,
    required=False,
)
