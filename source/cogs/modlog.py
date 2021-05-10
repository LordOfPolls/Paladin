import asyncio
import logging
import os
from datetime import datetime

from discord_slash import cog_ext
from PIL import Image

from source import dataclass, shared, utilities
from source.shared import *

log: logging.Logger = utilities.getLog("Cog::Log")


class ModLog(commands.Cog):
    """Configuration commands"""

    def __init__(self, bot: dataclass.Bot, s="📬"):
        self.bot = bot

        self.slash = bot.slash

        self.emoji = bot.emoji_list

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

    async def event_handler(self, event, **kwargs):
        """Handles all discord py events"""

        guild_data = await self.bot.get_guild_data(kwargs.get("guild").id)
        if guild_data:
            if guild_data.channel_mod_log_id is None:
                return
            output_channel: discord.TextChannel = self.bot.get_channel(int(guild_data.channel_mod_log_id))
            if not output_channel:
                return
        else:
            return

        emb = discord.Embed(colour=discord.Colour.blurple())
        file = None

        # todo: replace this ugliness with a match statement when 3.10 is fully released
        if event == EventFlags.memJoin:
            await self.fmt_member_add(emb, kwargs.get("member"))
        elif event == EventFlags.memLeave:
            await self.fmt_member_leave(emb, kwargs.get("member"))
        elif event == EventFlags.memUpdate:
            resp = await self.fmt_member_update(emb, kwargs)
            if resp is None:
                return
        elif event == EventFlags.memBan:
            await self.fmt_ban(emb, kwargs.get("member"))
        elif event == EventFlags.memUnban:
            await self.fmt_unban(emb, kwargs.get("member"))
        elif event == EventFlags.msgEdit:
            await self.fmt_msg_edit(emb, kwargs)
        elif event == EventFlags.msgDelete:
            file = await self.fmt_msg_delete(emb, kwargs)
        elif event == EventFlags.chnlPurge:
            await self.fmt_purge(emb, kwargs)
        else:
            # catches un-handled events
            return log.error(f"Uncaught event: {event}")

        if not emb == discord.Embed(colour=discord.Colour.blurple()):
            await shared.send_with_webhook("Moderation Log", output_channel, emb, file)
            if file:
                file.fp.close()

    # region: formatters
    async def fmt_msg_delete(self, emb: discord.Embed, kwargs: dict):
        emb.title = f"{self.emoji['deleted']} Message Deleted"
        emb.colour = discord.Colour.orange()

        before: discord.Message = kwargs.get("before")
        file = None

        # add a jump to context link
        async for msg in before.channel.history(limit=1, around=before):
            if msg:
                emb.description = f"{self.emoji['link']}[**Jump To Location**]({msg.jump_url})"
                break

        if before.clean_content:
            emb.add_field(name="Content", value=before.clean_content, inline=False)

        if before.attachments:
            for attachment in before.attachments:
                if str(attachment.content_type).startswith("image/"):
                    extension = str(attachment.filename).split(".")[-1]
                    f = open(f"data/images/{before.guild.id}_{before.id}_{before.id}.{extension}", "rb")
                    file = discord.File(f)
        emb.add_field(name="Channel", value=kwargs["before"].channel.mention, inline=False)
        return file

    async def fmt_msg_edit(self, emb: discord.Embed, kwargs: dict):
        if kwargs["after"].edited_at is None:
            # misfire due to attachment
            return None

        emb.title = f"{self.emoji['edit']} Message Edited"
        emb.description = f"{self.emoji['link']}[**Jump To Message**]({kwargs['after'].jump_url})"
        emb.add_field(
            name=f"Original",
            value=f"{kwargs['before'].clean_content}",
            inline=False,
        )
        emb.add_field(name=f"Edited", value=f"{kwargs['after'].clean_content}", inline=False)
        emb.add_field(
            name="Edit Time:",
            value=self.bot.formatDate(kwargs["after"].edited_at),
            inline=False,
        )

    async def fmt_member_update(self, emb: discord.Embed, kwargs: dict):
        emb.title = f"{self.emoji['members']} User Updated"
        emb.colour = discord.Colour.dark_grey()

        before: typing.Union[discord.Member, discord.User] = kwargs.get("before")
        after: typing.Union[discord.Member, discord.User] = kwargs.get("after")

        if (
            before.status != after.status
            or before.activity != after.activity
            or before.discriminator != after.discriminator
            or before.avatar_url != after.avatar_url
            or before is None
            or after is None
            or before == after
        ):
            # ignore certain changes
            return None

        emb.set_thumbnail(url=after.avatar_url)
        emb.add_field(name=after.display_name, value=f"#{after.discriminator}", inline=False)

        if before.nick != after.nick:
            # nickname has changed
            emb.add_field(name="Old nickname", value=before.nick, inline=False)
            emb.add_field(name="New nickname", value=after.nick, inline=False)

        if before.roles != after.roles:
            # roles have updated
            new_roles = []
            lost_roles = []

            # check for gained roles
            for role in after.roles:
                if role not in before.roles:
                    new_roles.append(role.name)

            # check for lost roles
            for role in before.roles:
                if role not in after.roles:
                    lost_roles.append(role.name)

            if new_roles:
                emb.add_field(name="New roles", value="\n".join(new_roles), inline=False)
            if lost_roles:
                emb.add_field(name="Lost roles", value="\n".join(lost_roles), inline=False)

        if before.pending != after.pending:
            if after.pending:
                emb.description = f"{after.display_name} is no longer pending verification"
            else:
                emb.description = f"{after.display_name} is now pending verification"

        if before.name != after.name:
            emb.add_field(name="Old name", value=before.name, inline=False)
            emb.add_field(name="New name", value=after.name, inline=False)

        return emb

    async def fmt_member_leave(self, emb: discord.Embed, member: discord.Member):
        emb.title = f"{self.emoji['MemberRemove']} User Left"
        emb.colour = discord.Colour.red()
        emb.set_thumbnail(url=member.avatar_url)
        emb.add_field(name=member.display_name, value=f"#{member.discriminator}", inline=False)

        emb.add_field(name="ID", value=member.id, inline=False)
        emb.add_field(
            name="Join Date:",
            value=self.bot.formatDate(member.joined_at),
            inline=False,
        )
        emb.add_field(
            name="Left After:",
            value=self.bot.strf_delta(datetime.utcnow() - member.joined_at),
            inline=False,
        )
        emb.set_thumbnail(url=member.avatar_url)

    async def fmt_member_add(self, emb: discord.Embed, member: discord.Member):
        emb.title = f"{self.emoji['MemberAdd']} User Joined"
        emb.colour = discord.Colour.green()
        emb.set_thumbnail(url=member.avatar_url)
        emb.add_field(name=member.display_name, value=f"#{member.discriminator}", inline=False)

        emb.add_field(name="ID", value=member.id, inline=False)
        emb.add_field(
            name="Account Creation Date:",
            value=self.bot.formatDate(member.created_at),
            inline=False,
        )
        emb.add_field(
            name="Account Age",
            value=self.bot.strf_delta(datetime.utcnow() - member.created_at),
            inline=False,
        )
        emb.set_footer(
            text=f"{member.name} #{member.discriminator}",
            icon_url=member.avatar_url,
        )
        emb.set_thumbnail(url=member.avatar_url)

    async def fmt_ban(self, emb: discord.Embed, member: discord.Member):
        emb.title = f"{self.emoji['banned']} User Banned"
        emb.colour = discord.Colour.dark_red()
        emb.set_thumbnail(url=member.avatar_url)
        emb.add_field(name=member.display_name, value=f"#{member.discriminator}")

        emb.add_field(
            name="Join Date:",
            value=self.bot.formatDate(member.joined_at),
            inline=False,
        )
        emb.add_field(
            name="Banned After:",
            value=self.bot.strf_delta(datetime.utcnow() - member.joined_at),
            inline=False,
        )

    async def fmt_unban(self, emb: discord.Embed, member: discord.Member):
        # todo: complete unban event - unsure what data to show in embed
        emb.title = f"{self.emoji['unbanned']} User Banned"
        emb.colour = discord.Colour.green()
        emb.set_thumbnail(url=member.avatar_url)
        emb.add_field(name=member.display_name, value=f"#{member.discriminator}")

    async def fmt_purge(self, emb: discord.Embed, kwargs: dict):
        emb.title = f"{self.emoji['deleted']} {len(kwargs['messages'])} Messages Deleted"
        emb.add_field(name="Channel", value=kwargs["channel"].mention)

    # endregion: formatters

    @staticmethod
    def compress_image(filename: str):
        """Compresses an image, intended to be used inside a thread"""
        image = Image.open(filename)

        if image.size[0] > 1920:
            # we dont want to save huge images, so downscale all images to be smaller than X-1920
            resize_factor = image.size[0] / 1920
            image = image.resize(
                (int(image.size[0] / resize_factor), int(image.size[1] / resize_factor)), Image.BICUBIC
            )
        elif image.size[1] > 1920:
            # catch images that are rotated and huge
            resize_factor = image.size[1] / 1920
            image = image.resize(
                (int(image.size[0] / resize_factor), int(image.size[1] / resize_factor)), Image.BICUBIC
            )

        # we dont want to ever be without a saved image, so create a temporary file and replace the original after compression
        tempName = filename.replace("data/images/", "data/images/TEMP")
        image.save(tempName, optimize=True, quality=85)
        os.replace(tempName, filename)

    # region: events
    async def on_message(self, message: discord.Message):
        """Handles storage of images for display when their message is deleted"""
        if message.attachments is not None:
            for attachment in message.attachments:
                attachment: discord.Attachment
                if str(attachment.content_type).startswith("image/"):
                    # attachment is an image
                    if not os.path.exists("data/images"):
                        os.makedirs("data/images", exist_ok=True)
                    extension = str(attachment.filename).split(".")[-1]

                    f = open(f"data/images/{message.guild.id}_{message.id}_{attachment.id}.{extension}", "wb")
                    try:
                        await attachment.save(f)
                    except discord.HTTPException or discord.NotFound:
                        return
                    f.close()
                    await asyncio.to_thread(
                        self.compress_image,
                        f"data/images/{message.guild.id}_{message.id}_{attachment.id}.{extension}",
                    )

    async def on_message_edit(self, before, after):
        if before.author != self.bot.user:
            await self.event_handler(event=EventFlags.msgEdit, guild=before.guild, before=before, after=after)

    async def on_message_delete(self, message):
        if message.author != self.bot.user:
            await self.event_handler(event=EventFlags.msgDelete, guild=message.guild, before=message)

    async def on_member_join(self, member):
        await self.event_handler(guild=member.guild, event=EventFlags.memJoin, member=member)

    async def on_member_remove(self, member):
        await self.event_handler(guild=member.guild, event=EventFlags.memLeave, member=member)

    async def on_member_update(self, before, after):
        await self.event_handler(guild=before.guild, event=EventFlags.memUpdate, before=before, after=after)

    async def on_member_ban(self, guild, user):
        await self.event_handler(guild=guild, event=EventFlags.memBan, member=user)

    async def on_member_unban(self, guild, user):
        await self.event_handler(guild=guild, event=EventFlags.memUnban, member=user)

    async def on_purge(self, payload: discord.RawBulkMessageDeleteEvent):
        channel: discord.TextChannel = self.bot.get_channel(payload.channel_id)
        guild: discord.Guild = channel.guild
        await self.event_handler(
            guild=guild,
            channel=channel,
            messages=payload.message_ids,
            event=EventFlags.chnlPurge,
        )

    # endregion: events

    @cog_ext.cog_subcommand(
        base="log",
        subcommand_group="moderation",
        name="set-channel",
        description="Set the channel for moderation event logging",
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
        guild_data.channel_mod_log_id = channel.id

        await self.bot.redis.set(guild_data.key, guild_data.to_json())

        await ctx.send(f"Set moderation log channel to {channel.mention}", hidden=True)

    @cog_ext.cog_subcommand(
        base="log",
        subcommand_group="moderation",
        name="clear-channel",
        description="Clear the set channel for moderation logs (disables it)",
    )
    async def _clear_channel(self, ctx):
        await ctx.defer()
        guild_data = await self.bot.get_guild_data(ctx.guild_id)
        guild_data.channel_mod_log_id = None

        await self.bot.redis.set(guild_data.key, guild_data.to_json())

        await ctx.send(f"Disabled moderation logging")


def setup(bot):
    """Called when this cog is mounted"""
    bot.add_cog(ModLog(bot))
    log.info("Modlog mounted")


def teardown(bot):
    """Called when this cog is unmounted"""
    log.warning("Mail un-mounted")
    for handler in log.handlers[:]:
        log.removeHandler(handler)
