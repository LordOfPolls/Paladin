import logging
import typing
from datetime import datetime

import discord
from discord.ext import commands
from discord_slash import SlashContext, cog_ext
from discord_slash.utils import manage_commands

from source import utilities, jsonManager, shared, dataclass

log: logging.Logger = utilities.getLog("Cog::uInfo")


class UserInfo(commands.Cog):
    """Gets information about a user"""

    def __init__(self, bot):
        self.bot: dataclass.Bot = bot

        self.emoji = bot.emoji_list

    # todo: add additional user info commands

    @cog_ext.cog_subcommand(**jsonManager.getDecorator("info.user"))
    async def userInfo(self, ctx: SlashContext, user: typing.Union[discord.Member, discord.User]):
        emb = discord.Embed(colour=discord.Colour.blurple())
        emb.set_thumbnail(url=user.avatar_url)
        emb.description = ""

        # get db data on user
        user_data = await self.bot.get_member_data(ctx.guild.id, user.id)
        user_perms: discord.Permissions = ctx.author.permissions_in(ctx.channel)
        if shared.is_user_moderator(user_perms):
            if user_data:
                if user_data.warnings != 0:
                    warnings = user_data.warnings
                    emb.description += f"{self.emoji['rules']} {warnings} warning{'s' if warnings > 1 else ''}\n"
                if user_data.muted == 1:
                    emb.description += f"{self.emoji['voiceLocked']} Muted\n"

        # names
        emb.add_field(name="ID", value=user.id, inline=False)
        emb.add_field(name="Username", value=f"{user.name} #{user.discriminator}", inline=False)
        if user.display_name != user.name:
            emb.add_field(name="Display name", value=user.display_name, inline=False)
        emb.add_field(
            name="Account Creation Date",
            value=f"{self.bot.formatDate(user.created_at)}\n"
            f"{self.emoji['time']}*{self.bot.strf_delta(datetime.utcnow() - user.created_at)}*",
            inline=False,
        )
        emb.add_field(
            name="Join Date",
            value=f"{self.bot.formatDate(user.joined_at)}\n"
            f"{self.emoji['time']}*{self.bot.strf_delta(datetime.utcnow() - user.joined_at)}*",
            inline=False,
        )
        emb.add_field(name="Highest Role", value=f"{user.top_role.name}", inline=False)

        # user flags
        flags: discord.UserFlags = user.public_flags
        if user.bot:
            emb.description += f"{self.emoji['bot']}{'Verified ' if flags.verified_bot else ''}Bot Account\n"
        if user.id == ctx.guild.owner_id:
            emb.description += f"{self.emoji['settings']}Server Owner\n"
        elif user.guild_permissions.administrator:
            emb.description += f"{self.emoji['settings']}Server Admin\n"
        elif (
            user.guild_permissions.manage_channels
            or user.guild_permissions.manage_guild
            or user.guild_permissions.manage_roles
        ):
            emb.description += f"{self.emoji['settings']}Server Staff\n"
        elif user.guild_permissions.kick_members or user.guild_permissions.ban_members:
            emb.description += f"{self.emoji['settings']}Server Moderator\n"
        if user.pending:
            emb.description += "⚠ User is pending verification\n"
        if user.premium_since is not None:
            emb.description += f"{self.emoji['spaceship']}Server Booster\n"
        if flags.verified_bot_developer:
            emb.description += f"{self.emoji['bot']} Verified Bot Developer\n"
        if flags.staff:
            emb.description += f"{self.emoji['settings']}Discord Staff\n"
        if flags.partner:
            emb.description += f"{self.emoji['members']}Discord Partner\n"
        if flags.bug_hunter or flags.bug_hunter_level_2:
            emb.description += f"{self.emoji['settingsOverride']}Bug Hunter\n"

        await ctx.send(embed=emb)


def setup(bot):
    """Called when this cog is mounted"""
    bot.add_cog(UserInfo(bot))
    log.info("UserInfo mounted")


def teardown(bot):
    """Called when this cog is unmounted"""
    log.warning("UserInfo un-mounted")
    for handler in log.handlers[:]:
        log.removeHandler(handler)
