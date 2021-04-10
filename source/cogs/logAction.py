import base64
import json
import logging

from discord.ext import commands
from discord_slash import cog_ext, SlashContext

from source import utilities
from source.shared import *

log: logging.Logger = utilities.getLog("Cog::ActLog")


class LogAction(commands.Cog):
    """Configuration commands"""

    def __init__(self, bot):
        self.bot = bot

        self.emoji = bot.emoji_list

        self.bot.paladinEvents.subscribe_to_event(self.log_mod_action, "modAction")

    async def _get_new_action_id(self, guild: discord.Guild) -> int:
        """Gets an action ID for a new action"""
        count = await self.bot.db.execute(
            f"SELECT COUNT(*) FROM paladin.modActions WHERE guildID = '{guild.id}'",
            getOne=True,
        )
        actionID = int(count["COUNT(*)"]) + 1
        return actionID

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
            query = "INSERT INTO paladin.modActions (actionID, guildID, action, moderatorID, userID, roleID, reason, channelID, messageID) VALUES ({actionID}, '{guild}', {action}, '{modID}', {userID}, {role}, '{reason}', '{messageID}', '{channelID}')".format(
                actionID=actionID,
                guild=guild.id,
                action=modAction,
                modID=moderator.id,
                userID=f"'{user.id}'" if user else "NULL",
                role=f"'{role.id}'" if role else "NULL",
                reason=await self.bot.db.escape(reason),
                messageID=message.id,
                channelID=message.channel.id,
            )
            log.info("writing to db")
            await self.bot.db.execute(query)
        except Exception as e:
            log.error(e)

    async def log_mod_action(self, action: Action):
        """Logs a moderation action"""
        channel: discord.TextChannel = self.bot.get_channel(743377002647519274)
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
        emb.title = f"{self.emoji['members']}Role {'Given' if action == ModActions.roleGive else 'Removed'}"
        emb.add_field(
            name="User",
            value=f"{action.user.name} #{action.user.discriminator} ({action.user.mention})",
            inline=False,
        )
        emb.add_field(name="Role", value=action.extra.name, inline=False)
        return emb

    def fmt_warn(self, action, emb):
        if "Cleared" in str(action.extra):
            emb.title = f"{self.emoji['rules']}User Warnings Cleared"
        else:
            emb.title = f"{self.emoji['rules']}User Warned"

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
        emb.title = f"{self.emoji['deleted']}Channel Purged"
        emb.add_field(name="Channel", value=actChannel.mention, inline=False)
        return emb

    # endregion: formatters

    @cog_ext.cog_slash(
        name="reason",
        options=[
            manage_commands.create_option(
                name="id",
                description="The id of the action you want to attach a reason to",
                option_type=int,
                required=True,
            ),
            manage_commands.create_option(
                name="reason", description="The reason for this action", option_type=str, required=True
            ),
        ],
        description="Add a reason to an action",
    )
    async def reason_cmd(self, ctx: SlashContext, id, reason):
        await ctx.defer(hidden=True)
        action_data: dict = await self.bot.db.execute(
            f"SELECT * FROM paladin.modActions WHERE actionID = {id} AND guildID = '{ctx.guild_id}'", getOne=True
        )
        if action_data is None:
            return await ctx.send("No action exists with that ID")

        chnl = ctx.guild.get_channel(int(action_data.get("channelID")))

        # update value in db
        db_reason = json.dumps(reason)
        db_reason = base64.b64encode(db_reason.encode()).decode("utf-8")
        await self.bot.db.execute(
            f"UPDATE paladin.modActions SET reason = '{db_reason}' WHERE actionID = {id} AND guildID = '{ctx.guild_id}'"
        )

        # try to update message in discord
        message: discord.Message = await self.bot.getMessage(channel=chnl, messageID=int(action_data.get("messageID")))

        if message:
            original_embed = message.embeds[0]
            for i in range(len(original_embed.fields)):
                field = original_embed.fields[i]
                if field.name.startswith("Reason"):
                    original_embed.remove_field(i)
            original_embed.add_field(name="Reason", value=reason, inline=False)
            original_embed.add_field(name="Action ID", value=str(id), inline=False)
            await message.edit(embed=original_embed)
        await ctx.send(f"Your reason has been stored for action #{id}")


def setup(bot):
    """Called when this cog is mounted"""
    bot.add_cog(LogAction(bot))
    log.info("ActionLog mounted")


def teardown(bot):
    """Called when this cog is unmounted"""
    log.warning("ActionLog un-mounted")
    for handler in log.handlers[:]:
        log.removeHandler(handler)
