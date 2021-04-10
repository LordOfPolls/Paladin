import logging
import typing
from datetime import datetime

import discord
from discord.ext import commands
from discord_slash import SlashContext, cog_ext
from discord_slash.utils import manage_commands

from source import utilities, pagination, jsonManager

log: logging.Logger = utilities.getLog("Cog::lsPerms")


class ListPermissions(commands.Cog):
    """List Permissions for a specified user/role"""

    def __init__(self, bot):
        self.bot = bot

        self.emoji = bot.emoji_list

        self.paginator = pagination.LinePaginator(prefix="", suffix="")

    @cog_ext.cog_subcommand(**jsonManager.getDecorator("guild.role.permissions"))
    async def role_perms_guild(self, ctx: SlashContext, role: discord.Role):
        data = []
        for perm, value in role.permissions:
            data.append(f"{'✅' if value else '❌'} {perm.replace('_', ' ').title()}")
        await self.paginator.paginate(
            data,
            ctx,
            embed=discord.Embed(title=f"Guild Permissions For {role.name}", colour=discord.Colour.blurple()),
            max_lines=10,
        )

    @cog_ext.cog_subcommand(**jsonManager.getDecorator("channel.role.permissions"))
    async def role_perms_channel(
        self,
        ctx: SlashContext,
        role: discord.Role,
        channel: typing.Union[discord.TextChannel, discord.VoiceChannel, discord.CategoryChannel] = None,
    ):
        if not channel:
            channel = ctx.channel
        data = []

        for perm, value in channel.overwrites_for(role):
            data.append(f"{'✅' if value else '❌'} {perm.replace('_', ' ').title()}")
        await self.paginator.paginate(
            data,
            ctx,
            embed=discord.Embed(
                title=f"Permissions For {role.name} in {channel.name}", colour=discord.Colour.blurple()
            ),
            max_lines=10,
        )

    @cog_ext.cog_subcommand(**jsonManager.getDecorator("guild.user.permissions"))
    async def user_perms_guild(self, ctx: SlashContext, user: discord.Member):
        data = []
        for perm, value in user.guild_permissions:
            data.append(f"{'✅' if value else '❌'} {perm.replace('_', ' ').title()}")
        await self.paginator.paginate(
            data,
            ctx,
            embed=discord.Embed(title=f"Guild Permissions For {user.name}", colour=discord.Colour.blurple()),
            max_lines=10,
        )

    @cog_ext.cog_subcommand(**jsonManager.getDecorator("channel.user.permissions"))
    async def user_perms_channel(
        self,
        ctx: SlashContext,
        user: discord.Member,
        channel: typing.Union[discord.TextChannel, discord.VoiceChannel, discord.CategoryChannel] = None,
    ):
        if not channel:
            channel = ctx.channel
        data = []

        for perm, value in channel.permissions_for(user):
            data.append(f"{'✅' if value else '❌'} {perm.replace('_', ' ').title()}")
        await self.paginator.paginate(
            data,
            ctx,
            embed=discord.Embed(
                title=f"Permissions For {user.name} in {channel.name}", colour=discord.Colour.blurple()
            ),
            max_lines=10,
        )


def setup(bot):
    """Called when this cog is mounted"""
    bot.add_cog(ListPermissions(bot))
    log.info("listPerms mounted")


def teardown(bot):
    """Called when this cog is unmounted"""
    log.warning("listPerms un-mounted")
    for handler in log.handlers[:]:
        log.removeHandler(handler)
