import json
import logging
import enum
import typing
from datetime import datetime, timedelta

import discord
from hashlib import md5
from discord.ext import commands
from discord_slash import SlashContext, cog_ext
from discord_slash.utils import manage_commands

from source import utilities, dataclass, messageObject

from source.enums import *


log: logging.Logger = utilities.getLog("Cog::Log")


class ModLog(commands.Cog):
    """Configuration commands"""

    def __init__(self, bot: dataclass.Bot, s="📬"):
        self.bot = bot

        self.slash = bot.slash

        self.emoji = bot.emoji_list

    async def _send_with_webhook(
        self, channel: discord.TextChannel, embed: discord.Embed
    ):
        """Sends content as a webhook"""
        for _hook in await channel.guild.webhooks():
            if "Paladin Log":
                hook: discord.Webhook = _hook
                break
        else:
            hook: discord.Webhook = await channel.create_webhook(name="Paladin Log")

        await hook.send(
            embed=embed,
            allowed_mentions=discord.AllowedMentions(
                everyone=False, roles=True, users=False
            ),
            avatar_url=channel.guild.icon_url,
        )

    async def setup(self):
        """The startup tasks for this cog"""
        self.bot.add_listener(self.on_message, "on_message")
        self.bot.add_listener(self.on_member_join, "on_member_join")
        self.bot.add_listener(self.on_member_remove, "on_member_remove")
        self.bot.add_listener(self.on_member_update, "on_member_update")
        self.bot.add_listener(self.on_message_edit, "on_message_edit")
        self.bot.add_listener(self.on_message_delete, "on_message_delete")
        self.bot.add_listener(self.on_member_ban, "on_member_ban")
        self.bot.add_listener(self.on_member_unban, "on_member_unban")
        self.bot.add_listener(self.on_purge, "on_raw_bulk_message_delete")

    async def log_mod_action(
        self,
        action: str,
        users: typing.List[typing.Union[discord.Member, discord.User]],
        guild: discord.Guild,
        reason: str = None,
    ):
        """Logs a moderation action"""
        channel: discord.TextChannel = self.bot.get_channel(743377002647519274)
        emb = discord.Embed(colour=discord.Colour.blurple())

        moderator = users[0]
        user = users[1]
        token = 1

        if action == ModActions.kick or ModActions.ban:
            emb.title = (
                f"{self.emoji['banned']} User Banned"
                if action == ModActions.ban
                else f"{self.emoji['MemberRemove']} User Kicked"
            )
            emb.add_field(
                name="User",
                value=f"{user.name} #{user.discriminator} ({user.mention})",
                inline=False,
            )
            emb.add_field(
                name="Moderator",
                value=f"{user.name} #{user.discriminator} ({user.mention})",
                inline=False,
            )

            emb.add_field(
                name="Reason", value=reason if reason else "**Moderator:** Please use "
            )

    async def eventHandler(self, event, **kwargs):
        """Handles all the discord py events"""
        print(f"{event=}, {kwargs=}")
        emb = discord.Embed(colour=discord.Colour.blurple())
        user: typing.Union[None, discord.Member, discord.User] = None
        channel: discord.TextChannel = self.bot.get_channel(743377002647519274)

        if event == EventFlags.memJoin:
            emb.title = f"{self.emoji['MemberAdd']} User Joined"
            emb.colour = discord.Colour.green()

            user = kwargs["member"]
            emb.add_field(name="ID", value=user.id, inline=False)
            emb.add_field(
                name="Account Creation Date:",
                value=self.bot.formatDate(user.created_at),
                inline=False,
            )
            emb.add_field(
                name="Account Age",
                value=self.bot.strf_delta(datetime.utcnow() - user.created_at),
                inline=False,
            )
            emb.set_thumbnail(url=user.avatar_url)

        elif event == EventFlags.memLeave:
            emb.title = f"{self.emoji['MemberRemove']} User Left"
            emb.colour = discord.Colour.red()

            user = kwargs["member"]
            emb.add_field(name="ID", value=user.id, inline=False)
            emb.add_field(
                name="Join Date:",
                value=self.bot.formatDate(user.joined_at),
                inline=False,
            )
            emb.add_field(
                name="Left After:",
                value=self.bot.strf_delta(datetime.utcnow() - user.joined_at),
                inline=False,
            )
            emb.set_thumbnail(url=user.avatar_url)

        elif event == EventFlags.memBan:
            emb.title = f"{self.emoji['banned']} User Banned"
            emb.colour = discord.Colour.dark_red()

        elif event == EventFlags.memUnban:
            emb.title = f"{self.emoji['unbanned']} User Banned"
            emb.colour = discord.Colour.green()

        elif event == EventFlags.msgEdit:
            emb.title = f"{self.emoji['edit']} Message Edited"
            print(emb.title)
            user = kwargs["after"].author
            emb.description = (
                f"{self.emoji['link']}[**Jump To Message**]({kwargs['after'].jump_url})"
            )

            emb.add_field(
                name=f"Original",
                value=f"{kwargs['before'].clean_content}",
                inline=False,
            )
            emb.add_field(
                name=f"Edited", value=f"{kwargs['after'].clean_content}", inline=False
            )
            emb.add_field(
                name="Edit Time:",
                value=self.bot.formatDate(kwargs["after"].edited_at),
                inline=False,
            )

        elif event == EventFlags.msgDelete:
            emb.title = f"{self.emoji['deleted']} Message Deleted"
            emb.colour = discord.Colour.orange()
            user = kwargs["before"].author
            # add a jump to context link
            async for msg in kwargs["before"].channel.history(
                limit=1, around=kwargs["before"]
            ):
                if msg:
                    emb.description = (
                        f"{self.emoji['link']}[**Jump To Location**]({msg.jump_url})"
                    )
                    break
            emb.add_field(
                name="Content", value=kwargs["before"].clean_content, inline=False
            )
            emb.add_field(
                name="Channel", value=kwargs["before"].channel.mention, inline=False
            )

        elif event == EventFlags.chnlPurge:
            emb.title = (
                f"{self.emoji['deleted']} {len(kwargs['messages'])} Messages Deleted"
            )
            emb.add_field(name="Channel", value=kwargs["channel"].mention)

        else:
            # shouldnt happen, but if someone messes around with the flags  this will be triggered
            return log.error(f"Uncaught event: {event}")

        if user:
            emb.set_footer(
                text=f"{user.name} #{user.discriminator}",
                icon_url=user.avatar_url,
            )

        await self._send_with_webhook(channel, emb)

    # region: events
    async def on_message(self, message):
        pass

    async def on_message_edit(self, before, after):
        if before.author != self.bot.user:
            await self.eventHandler(
                event=EventFlags.msgEdit, guild=before.guild, before=before, after=after
            )

    async def on_message_delete(self, message):
        if message.author != self.bot.user:
            await self.eventHandler(
                event=EventFlags.msgDelete, guild=message.guild, before=message
            )

    async def on_member_join(self, member):
        await self.eventHandler(
            guild=member.guild, event=EventFlags.memJoin, member=member
        )

    async def on_member_remove(self, member):
        await self.eventHandler(
            guild=member.guild, event=EventFlags.memLeave, member=member
        )

    async def on_member_update(self, before, after):
        await self.eventHandler(
            guild=before.guild, event=EventFlags.memUpdate, before=before, after=after
        )

    async def on_member_ban(self, guild, user):
        await self.eventHandler(guild=guild, event=EventFlags.memBan, member=user)

    async def on_member_unban(self, guild, user):
        await self.eventHandler(guild=guild, event=EventFlags.memUnban, member=user)

    async def on_purge(self, payload: discord.RawBulkMessageDeleteEvent):
        channel: discord.TextChannel = self.bot.get_channel(payload.channel_id)
        guild: discord.Guild = channel.guild
        await self.eventHandler(
            guild=guild,
            channel=channel,
            messages=payload.message_ids,
            event=EventFlags.chnlPurge,
        )

    # endregion: events


def setup(bot):
    """Called when this cog is mounted"""
    bot.add_cog(ModLog(bot))
    log.info("Modlog mounted")


def teardown(bot):
    """Called when this cog is unmounted"""
    log.warning("Mail un-mounted")
    for handler in log.handlers[:]:
        log.removeHandler(handler)
