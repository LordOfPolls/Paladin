import logging
from datetime import datetime, timedelta

from discord.ext import commands
from discord_slash import SlashContext, cog_ext

from source import utilities, dataclass
from source.shared import *

log: logging.Logger = utilities.getLog("Cog::BaseMod")


class BaseModeration(commands.Cog):
    """Configuration commands"""

    def __init__(self, bot: dataclass.Bot, s="📬"):
        self.bot = bot

        self.slash = bot.slash

        self.emoji = bot.emoji_list

    @cog_ext.cog_subcommand(
        base="messages",
        name="purge",
        description="Purge messages from this channel",
        options=[
            manage_commands.create_option(
                name="total",
                description="How many messages should be purged",
                option_type=int,
                required=True,
            ),
            manage_commands.create_option(
                name="user",
                description="Purge only from a specific user",
                option_type=6,
                required=False,
            ),
            manage_commands.create_option(
                name="channel",
                description="Specify a channel to purge",
                option_type=7,
                required=False,
            ),
            reasonOption,
        ],
        guild_ids=[701347683591389185],
    )
    async def purge(
        self,
        ctx: SlashContext,
        total: int,
        user: discord.User = None,
        channel: discord.TextChannel = None,
        reason: str = None,
    ):

        totalDeleted = set()

        def check(m):
            if len(totalDeleted) >= total:
                return False
            if m.id == msg.id:
                return False
            if user is None or m.author == user:
                totalDeleted.add(m.id)
                return True
            return False

        if not channel:
            channel = ctx.channel

        emb = discord.Embed(
            title="⚠ **Purging Channel** ⚠",
            description=f"Requested by {ctx.author.mention}",
            colour=discord.Colour.red(),
        )
        if channel == ctx.channel:
            msg = await ctx.send(embed=emb)
        else:
            await ctx.send(f"Purging {channel.mention}")
            msg = await channel.send(embed=emb)

        output = await channel.purge(
            limit=1000,
            after=datetime.utcnow() - timedelta(days=14),
            check=check,
        )
        if len(totalDeleted) == 0:
            emb.title = "Channel Purge Failed"
            emb.description = "**Note:** Discord only allows bots to purge messages that are less than 2 weeks old"
        else:
            emb.title = "Channel Purge Complete"
            emb.add_field(name="Deleted", value=f"{len(output)} messages", inline=False)
            if user is not None:
                emb.add_field(
                    name="Filter",
                    value=f"Messages from {user.name} #{user.discriminator}",
                    inline=False,
                )

        try:
            await msg.edit(embed=emb)
        except:
            await ctx.send(embed=emb)

        await self.bot.paladinEvents.add_item(
            Action(
                actionType=ModActions.purge,
                moderator=ctx.author,
                guild=ctx.guild,
                extra=channel,
                reason=reason,
            )
        )

    @cog_ext.cog_subcommand(
        base="user",
        subcommand_group="role",
        name="add",
        description="Give a user a role",
        options=[
            manage_commands.create_option(name="role", description="The role to add", option_type=8, required=True),
            manage_commands.create_option(
                name="user",
                option_type=6,
                description="The user in question",
                required=False,
            ),
            reasonOption,
        ],
    )
    async def giveRole(
        self,
        ctx: SlashContext,
        role: discord.Role,
        user: discord.Member = None,
        reason: str = None,
    ):
        if not user:
            user = ctx.author
        # ive seen this take a while to execute, so defer is a good idea
        await ctx.defer()

        if role.id in [r.id for r in user.roles]:
            return await ctx.send(f"{user.name} #{user.discriminator} already has {role.name}")

        try:
            await user.add_roles(role)
            await ctx.send(f"{user.name} #{user.discriminator} now has {role.name}")
        except Exception as e:
            log.error(f"Error adding role: {e}")
            return await ctx.send(f"Unable to add {role.name} to {user.name} #{user.discriminator}")

        await self.bot.paladinEvents.add_item(
            Action(
                actionType=ModActions.roleGive,
                moderator=ctx.author,
                guild=ctx.guild,
                user=user,
                extra=role,
                reason=reason,
            )
        )

    @cog_ext.cog_subcommand(
        base="user",
        subcommand_group="role",
        name="remove",
        description="Give a user a role",
        options=[
            manage_commands.create_option(
                name="role",
                description="The role to remove",
                option_type=8,
                required=True,
            ),
            manage_commands.create_option(
                name="user",
                option_type=6,
                description="The user in question",
                required=False,
            ),
            reasonOption,
        ],
    )
    async def removeRole(
        self,
        ctx: SlashContext,
        role: discord.Role,
        user: discord.Member = None,
        reason: str = None,
    ):
        if not user:
            user = ctx.author
        # ive seen this take a while to execute, so defer is a good idea
        await ctx.defer()

        if role not in user.roles:
            return await ctx.send(f"{user.name} #{user.discriminator} does not have {role.name}")

        try:
            await user.remove_roles(role)
            await ctx.send(f"{user.name} #{user.discriminator} no longer has {role.name}")
        except Exception as e:
            log.error(f"Error adding role: {e}")
            return await ctx.send(f"Unable to remove {role.name} from {user.name} #{user.discriminator}")

        await self.bot.paladinEvents.add_item(
            Action(
                actionType=ModActions.roleRem,
                moderator=ctx.author,
                guild=ctx.guild,
                user=user,
                extra=role,
                reason=reason,
            )
        )

    @cog_ext.cog_subcommand(
        base="user",
        name="kick",
        description="Kick a user",
        options=[
            manage_commands.create_option(
                name="User",
                description="The user in question",
                option_type=6,
                required=True,
            ),
            reasonOption,
        ],
    )
    async def kick(
        self,
        ctx: SlashContext,
        user: typing.Union[discord.Member, discord.User],
        reason: str = None,
    ):
        try:
            await user.kick()
            await ctx.send(f"Kicked {user.name} #{user.discriminator}")
        except Exception as e:
            log.error(f"Failed to kick: {e}")
            return await ctx.send(f"Failed to kick {user.name} #{user.discriminator}", hidden=True)
        await self.bot.paladinEvents.add_item(
            Action(
                actionType=ModActions.kick,
                moderator=ctx.author,
                guild=ctx.guild,
                user=user,
                reason=reason,
            )
        )

    @cog_ext.cog_subcommand(
        base="user",
        name="ban",
        description="Ban a user",
        options=[
            manage_commands.create_option(
                name="User",
                description="The user in question",
                option_type=6,
                required=True,
            ),
            reasonOption,
        ],
    )
    async def ban(
        self,
        ctx: SlashContext,
        user: typing.Union[discord.Member, discord.User],
        reason: str = None,
    ):
        try:
            await user.ban()
            await ctx.send(f"Banned {user.name} #{user.discriminator}")
        except Exception as e:
            log.error(f"Failed to ban: {e}")
            return await ctx.send(f"Failed to ban {user.name} #{user.discriminator}", hidden=True)
        await self.bot.paladinEvents.add_item(
            Action(
                actionType=ModActions.ban,
                moderator=ctx.author,
                guild=ctx.guild,
                user=user,
                reason=reason,
            )
        )


def setup(bot):
    """Called when this cog is mounted"""
    bot.add_cog(BaseModeration(bot))
    log.info("BaseMod mounted")


def teardown(bot):
    """Called when this cog is unmounted"""
    log.warning("BaseMod un-mounted")
    for handler in log.handlers[:]:
        log.removeHandler(handler)
