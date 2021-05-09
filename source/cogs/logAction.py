import base64
import json
import logging

from discord_slash import cog_ext

from source import utilities, jsonManager, dataclass
from source.shared import *

log: logging.Logger = utilities.getLog("Cog::ActLog")


class LogAction(commands.Cog):
    """Configuration commands"""

    def __init__(self, bot):
        self.bot: dataclass.Bot = bot

        self.emoji = bot.emoji_list

        self.bot.paladinEvents.subscribe_to_event(self.log_mod_action, "modAction")

    async def _get_new_action_id(self, guild: discord.Guild) -> int:
        """Gets an action ID for a new action"""
        keys = await self.bot.redis.keys(f"action||{guild.id}*")
        return len(keys) + 1

    async def _writeActionToDb(
        self,
        guild: discord.Guild,
        modAction: ModActions,
        moderator: discord.Member,
        reason: str,
        message: discord.Message,
        actionID: typing.Optional[int] = None,
        user: typing.Optional[discord.Member] = None,
        role: typing.Optional[discord.Role] = None,
    ):
        """Writes an action to the database"""
        try:
            if actionID is None:
                actionID = await self._get_new_action_id(guild)

            reason = json.dumps(reason)
            reason = base64.b64encode(reason.encode()).decode("utf-8")

            obj = dataclass.ModAction(guild.id, actionID, modAction, moderator.id)
            obj.reason = reason
            obj.message_id = message.id
            obj.channel_id = message.channel.id
            obj.user_id = user.id if user else None
            obj.role_id = role.id if role else None

            await self.bot.redis.set(obj.key, obj.to_json())
        except Exception as e:
            log.error(e)

    async def log_mod_action(self, action: Action):
        """Logs a moderation action"""
        guild_data = await self.bot.get_guild_data(guild_id=action.guild.id)

        if guild_data:
            if guild_data.channel_action_log_id is None:
                return
            channel: discord.TextChannel = self.bot.get_channel(int(guild_data.channel_action_log_id))
            if not channel:
                return
        else:
            return

        emb = discord.Embed(colour=discord.Colour.blurple())

        token = await self._get_new_action_id(action.guild)

        # todo: replace this ugliness with a match statement when 3.10 is fully released
        if action.action_type == ModActions.kick or action.action_type == ModActions.ban:
            emb = self.fmt_kick(action, emb)

        elif action.action_type == ModActions.roleGive or action.action_type == ModActions.roleRem:
            emb = self.fmt_role(action, emb)

        elif action.action_type == ModActions.purge:
            emb = self.fmt_purge(action, emb)

        elif action.action_type == ModActions.warn:
            emb = self.fmt_warn(action, emb)

        elif action.action_type == ModActions.mute:
            emb = self.fmt_mute(action, emb)

        elif action.action_type == ModActions.unmute:
            emb = self.fmt_unmute(action, emb)

        else:
            log.warning(f"Unhandled action: {ModActions(action.action_type).name}")
            emb.title = f"Uncaught event: {action.action_type}"
            emb.description = action.__repr__()

        # Add generic data to embed
        emb.add_field(
            name="Moderator",
            value=f"{action.moderator.name} #{action.moderator.discriminator} ({action.moderator.mention})",
            inline=False,
        )
        reason = action.reason if action.reason is not None else f"**Moderator:** Please use `/reason {token}`"
        emb.add_field(
            name="Reason",
            value=reason,
            inline=False,
        )

        msg = await channel.send(embed=emb, allowed_mentions=discord.AllowedMentions.none())
        await self._writeActionToDb(
            guild=action.guild,
            actionID=token,
            modAction=action.action_type,
            moderator=action.moderator,
            reason=reason,
            message=msg,
            user=action.user,
            role=action.extra if isinstance(action.extra, discord.Role) else None,
        )

    # region: formatters

    def fmt_kick(self, action, emb):
        emb.title = (
            f"{self.emoji['banned']} User Banned"
            if action == ModActions.ban
            else f"{self.emoji['MemberRemove']} User Kicked"
        )
        emb.add_field(
            name="User",
            value=f"{action.user.name} #{action.user.discriminator} ({action.user.mention})",
            inline=False,
        )
        return emb

    def fmt_role(self, action, emb):
        emb.title = f"{self.emoji['members']} Role {'Given' if action == ModActions.roleGive else 'Removed'}"
        emb.add_field(
            name="User",
            value=f"{action.user.name} #{action.user.discriminator} ({action.user.mention})",
            inline=False,
        )
        emb.add_field(name="Role", value=action.extra.name, inline=False)
        return emb

    def fmt_warn(self, action, emb):
        if "Cleared" in str(action.extra):
            emb.title = f"{self.emoji['rules']} User Warnings Cleared"
        else:
            emb.title = f"{self.emoji['rules']} User Warned"

        warnings = action.extra
        emb.add_field(
            name="User",
            value=f"{action.user.name} #{action.user.discriminator} ({action.user.mention})",
            inline=False,
        )
        emb.add_field(name="Warnings", value=warnings, inline=False)
        return emb

    def fmt_purge(self, action, emb):
        actChannel: discord.TextChannel = action.extra
        emb.title = f"{self.emoji['deleted']} Channel Purged"
        emb.add_field(name="Channel", value=actChannel.mention, inline=False)
        return emb

    def fmt_mute(self, action, emb):
        emb.title = f"{self.emoji['voiceLocked']} User Muted"
        emb.add_field(
            name="User",
            value=f"{action.user.name} #{action.user.discriminator} ({action.user.mention})",
            inline=False,
        )
        return emb

    def fmt_unmute(self, action, emb):
        emb.title = f"{self.emoji['voice']} User Un-Muted"
        emb.add_field(
            name="User",
            value=f"{action.user.name} #{action.user.discriminator} ({action.user.mention})",
            inline=False,
        )
        return emb

    # endregion: formattersguildID

    @cog_ext.cog_slash(**jsonManager.getDecorator("reason"))
    async def reason_cmd(self, ctx: SlashContext, id, reason):
        await ctx.defer(hidden=True)
        action_data = await self.bot.get_action_data(ctx.guild_id, id)
        if action_data is None:
            return await ctx.send("No action exists with that ID")

        if str(ctx.author.id) != str(action_data.moderator_id):
            return await ctx.send("You are not the person who performed that action", hidden=True)

        chnl = ctx.guild.get_channel(int(action_data.channel_id))

        # update value in db
        db_reason = json.dumps(reason)
        db_reason = base64.b64encode(db_reason.encode()).decode("utf-8")
        action_data.reason = db_reason
        await self.bot.redis.set(action_data.key, action_data.to_json())

        # try to update message in discord
        message: discord.Message = await self.bot.getMessage(channel=chnl, messageID=int(action_data.message_id))

        if message:
            original_embed = message.embeds[0]
            for i in range(len(original_embed.fields)):
                field = original_embed.fields[i]
                if field.name.startswith("Reason"):
                    original_embed.remove_field(i)
            original_embed.add_field(name="Action ID", value=str(id), inline=False)
            original_embed.add_field(name="Reason", value=reason, inline=False)
            await message.edit(embed=original_embed)
        await ctx.send(f"Your reason has been stored for action #{id}")

    @cog_ext.cog_subcommand(
        base="log",
        subcommand_group="action",
        name="set-channel",
        description="Set the channel for action logging",
        options=[
            manage_commands.create_option(
                name="channel", option_type=7, description="The channel to send to", required=True
            )
        ],
    )
    async def _set_channel(self, ctx: SlashContext, channel: discord.TextChannel):
        if not isinstance(channel, discord.TextChannel):
            return await ctx.send("Sorry, logs can only be sent to a text channel")

        await ctx.defer(hidden=True)

        guild_data = await self.bot.get_guild_data(ctx.guild_id)
        guild_data.channel_action_log_id = channel.id

        await self.bot.redis.set(guild_data.key, guild_data.to_json())

        await ctx.send(f"Set action log channel to {channel.mention}", hidden=True)

    @cog_ext.cog_subcommand(
        base="log",
        subcommand_group="action",
        name="clear-channel",
        description="Clear the set channel for action logs (disables it)",
    )
    async def _clear_channel(self, ctx):
        await ctx.defer()
        guild_data = await self.bot.get_guild_data(ctx.guild_id)
        guild_data.channel_action_log_id = None

        await self.bot.redis.set(guild_data.key, guild_data.to_json())

        await ctx.send(f"Disabled action logging")


def setup(bot):
    """Called when this cog is mounted"""
    bot.add_cog(LogAction(bot))
    log.info("ActionLog mounted")


def teardown(bot):
    """Called when this cog is unmounted"""
    log.warning("ActionLog un-mounted")
    for handler in log.handlers[:]:
        log.removeHandler(handler)
