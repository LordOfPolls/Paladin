import enum
import typing

import discord
from discord.ext import commands
from discord_slash import SlashContext
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


def is_user_moderator(perms: discord.Permissions):
    """Does the user have *any* moderator perms"""
    if (
        perms.administrator
        or perms.manage_guild
        or perms.manage_channels
        or perms.manage_messages
        or perms.manage_roles
        or perms.mute_members
        or perms.manage_permissions
    ):
        return True
    return False


def check_is_moderator():
    async def sub_check(ctx: SlashContext):
        if ctx.guild is None:
            return False
        user_perms = ctx.author.permissions_in(ctx.channel)
        return is_user_moderator(user_perms)

    return commands.check(sub_check)


async def send_with_webhook(name: str, channel: discord.TextChannel, embed: discord.Embed = None, file=None):
    """Sends content as a webhook to the desired channel"""
    for _hook in await channel.webhooks():
        if _hook.name == name:
            hook: discord.Webhook = _hook
            break
    else:
        hook: discord.Webhook = await channel.create_webhook(name=name)

    await hook.send(
        embed=embed,
        allowed_mentions=discord.AllowedMentions(everyone=False, roles=True, users=False),
        avatar_url=channel.guild.icon_url,
        file=file,
    )
