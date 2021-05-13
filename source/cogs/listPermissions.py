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

    @cog_ext.cog_subcommand(
        base="permissions",
        name="get",
        description="Get the permissions of a role or user",
        base_default_permission=True,
        options=[
            manage_commands.create_option(
                name="scope",
                description="Do you want guild perms, or channel overrides",
                required=True,
                option_type=4,
                choices=[
                    manage_commands.create_choice(value=1, name="guild"),
                    manage_commands.create_choice(value=2, name="channel"),
                ],
            ),
            manage_commands.create_option(
                name="target", description="The user or role you want to get perms for", required=True, option_type=9
            ),
        ],
    )
    async def get_permissions(self, ctx: SlashContext, **kwargs):
        mention = int(kwargs.get("target"))

        if user := ctx.guild.get_member(mention):
            if kwargs.get("scope") == 1:
                return await self.perms_guild(ctx, user)
            return await self.perms_channel(ctx, user)

        elif role := ctx.guild.get_role(mention):
            if kwargs.get("scope") == 1:
                return await self.perms_guild(ctx, role)
            return await self.perms_channel(ctx, role)

        else:
            await ctx.send("Sorry, i couldn't find that user or role")

    async def perms_guild(self, ctx: SlashContext, mention: typing.Union[discord.Role, discord.Member]):
        data = []

        if isinstance(mention, discord.Member):
            permissions = mention.guild_permissions
        else:
            permissions = mention.permissions

        for perm, value in permissions:
            data.append(f"{'✅' if value else '❌'} {perm.replace('_', ' ').title()}")
        await self.paginator.paginate(
            data,
            ctx,
            embed=discord.Embed(title=f"Guild Permissions For {mention.name}", colour=discord.Colour.blurple()),
            max_lines=10,
        )

    async def perms_channel(self, ctx: SlashContext, mention: typing.Union[discord.Role, discord.Member]):
        channel = ctx.channel
        data = []

        if isinstance(mention, discord.Member):
            permissions = channel.permissions_for(mention)
        else:
            permissions = channel.overwrites_for(mention)

        for perm, value in permissions:
            data.append(f"{'✅' if value else '❌'} {perm.replace('_', ' ').title()}")
        await self.paginator.paginate(
            data,
            ctx,
            embed=discord.Embed(
                title=f"Permissions For {mention.name} in {channel.name}", colour=discord.Colour.blurple()
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
