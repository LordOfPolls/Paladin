import logging

from discord_slash import cog_ext

from source import utilities, dataclass, jsonManager, shared
from source.shared import *

log: logging.Logger = utilities.getLog("Cog::warn")


class UserWarnings(commands.Cog):
    """Configuration commands"""

    def __init__(self, bot: dataclass.Bot):
        self.bot: dataclass.Bot = bot

        self.slash = bot.slash

        self.emoji = bot.emoji_list

    @cog_ext.cog_subcommand(**jsonManager.getDecorator("add.warn.user"))
    async def warnCMD(
        self,
        ctx: SlashContext,
        user: typing.Union[discord.User, discord.Member],
        reason: str = None,
    ):
        """Warns a user, 3 warnings and the user will be kicked"""
        await ctx.defer()
        user_data = await self.bot.get_member_data(ctx.guild_id, user.id)
        warning_num = int(user_data.warnings) + 1

        embed = discord.Embed(title=f"Warning for {user.name} #{user.discriminator}", color=0xE7C30D)
        embed.add_field(
            name="Warning LVL.1",
            value=":white_check_mark:" if warning_num >= 1 else ":x:",
            inline=False,
        )
        embed.add_field(
            name="Warning LVL.2",
            value=":white_check_mark:" if warning_num >= 2 else ":x:",
            inline=False,
        )
        embed.add_field(
            name="Warning LVL.3",
            value=":white_check_mark:" if warning_num >= 3 else ":x:",
            inline=False,
        )
        embed.set_footer(
            text=f"Warned by {ctx.author.name}#{ctx.author.discriminator}",
            icon_url=ctx.author.avatar_url,
        )
        if warning_num >= 3:
            embed.colour = discord.Colour.red()
            action = None
            autoReason = None
            if warning_num == 4:
                action = ModActions.kick
                autoReason = "Auto: 4th warning"
                embed.description = "User has 4 warnings, they have been kicked"
                await user.kick(reason=autoReason)
            elif warning_num >= 5:
                action = ModActions.ban
                autoReason = f"Auto: {warning_num}th warning"
                embed.description = "User has 5 warnings, they have been banned"
                await ctx.guild.ban(user, reason=autoReason, delete_message_days=0)
            if action and autoReason:
                await self.bot.paladinEvents.add_item(
                    Action(
                        actionType=action,
                        moderator=ctx.author,
                        guild=ctx.guild,
                        user=user,
                        reason=autoReason,
                    )
                )
        await ctx.send(embed=embed)

        await self.bot.paladinEvents.add_item(
            Action(
                actionType=ModActions.warn,
                moderator=ctx.author,
                guild=ctx.guild,
                user=user,
                extra=warning_num,
                reason=reason,
            )
        )

        user_data.warnings = warning_num
        await self.bot.redis.set(user_data.key, user_data.to_json())

    @cog_ext.cog_subcommand(**jsonManager.getDecorator("clear.warn.user"))
    async def warnClearCMD(
        self,
        ctx: SlashContext,
        user: typing.Union[discord.User, discord.Member],
        reason: str = None,
    ):
        await ctx.defer()

        try:
            user_data = await self.bot.get_member_data(ctx.guild_id, user.id)
            user_data.warnings = 0
            await self.bot.redis.set(user_data.key, user_data.to_json())

            await ctx.send(f"Cleared warnings for {user.name} #{user.discriminator}")
        except Exception as e:
            log.error(f"Error clearing warnings: {e}")
            await ctx.send("Unable to clear warnings... please try again later")
        else:
            await self.bot.paladinEvents.add_item(
                Action(
                    actionType=ModActions.warn,
                    moderator=ctx.author,
                    guild=ctx.guild,
                    user=user,
                    extra="Cleared to 0",
                    reason=reason,
                )
            )


def setup(bot):
    """Called when this cog is mounted"""
    bot.add_cog(UserWarnings(bot))
    log.info("Warn mounted")


def teardown(bot):
    """Called when this cog is unmounted"""
    log.warning("Warn un-mounted")
    for handler in log.handlers[:]:
        log.removeHandler(handler)
