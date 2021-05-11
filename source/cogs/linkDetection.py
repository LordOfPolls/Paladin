import logging
import re
import typing

import discord
from discord.ext import commands
from discord_slash import cog_ext, SlashContext
from discord_slash.utils import manage_commands

from source import utilities, dataclass, shared

log: logging.Logger = utilities.getLog("Cog::LinkDetect")


class LinkDetection(commands.Cog):
    """Configuration commands"""

    def __init__(self, bot):
        self.bot: dataclass.Bot = bot

        self.emoji = bot.emoji_list

        self.bot.add_listener(self.on_message, "on_message")

    async def on_message(self, message: discord.Message):
        if message.author.id == self.bot.user.id:
            return

        discord_invite = "discord.gg/(.*)"
        bot_invite = "discord.com/oauth2/authorize\?client_id=(\d{18})"
        generic_url = "((http|ftp|https)://|[\w_-]+(?:(?:\.[\w_-]+)+))([\w.,@?^=%&:/~+#-]*[\w@?^=%&/~+#-])(.*)"

        if url := re.search(discord_invite, str(message.clean_content)):
            # discord link
            return await self.handle_guild_invite(message, url)

        elif url := re.search(bot_invite, str(message.clean_content)):
            # bot invite
            return await self.handle_bot_invite(message, url)

        elif url := re.search(generic_url, str(message.clean_content)):
            # generic link
            return await self.handle_generic_url(message, url)

    async def send_message(
        self, guild_id: int, emb: discord.Embed, guild_data: typing.Optional[dataclass.Guild] = None
    ):
        """Send a message to the guilds moderation log"""
        if not guild_data:
            guild_data = await self.bot.get_guild_data(guild_id)
        if guild_data is not None and emb is not None:
            if guild_data.channel_mod_log_id is None:
                return
            output_channel: discord.TextChannel = self.bot.get_channel(int(guild_data.channel_mod_log_id))
            if output_channel:
                await shared.send_with_webhook("Moderation Log", output_channel, emb)

    async def handle_guild_invite(self, message, url):
        """Handle guild invites"""

        guild_data = await self.bot.get_guild_data(message.guild.id)

        data: discord.Invite = await self.bot.fetch_invite(url.string, with_counts=True)
        if data:
            emb = discord.Embed(title="Invite Detected")

            if guild_data.block_guild_invites and data.guild.id not in guild_data.allowed_guild_invites:
                await message.delete()

                async for msg in message.channel.history(limit=1, around=message):
                    emb.title = "Invite Deleted"
                    emb.colour = discord.Colour.red()
                    if msg:
                        emb.description = f"{self.emoji['link']}[**Jump To Location**]({msg.jump_url})"
                        break

            else:
                emb.colour = discord.Colour.orange()
                emb.description = f"{self.emoji['link']}[**Jump To Message**]({message.jump_url})"

            emb.add_field(name="Guild Name", value=data.guild.name)
            emb.add_field(name="Members", value=str(data.approximate_member_count))
            emb.add_field(name="Target", value=str(data.channel.name))
            if data.inviter is not None:
                emb.add_field(name="Invite Creator", value=str(data.inviter.mention))
            emb.add_field(name="Code", value=data.code)
            emb.set_thumbnail(url=data.guild.icon_url)

            emb.add_field(
                name="Sent By",
                value=f"{message.author.name}#{message.author.discriminator} {message.author.mention}",
            )
            await self.send_message(message.guild.id, emb, guild_data)

    async def handle_bot_invite(self, message, url):
        """Handle bot invites"""
        guild_data = await self.bot.get_guild_data(message.guild.id)

        if guild_data.block_bot_invites:
            await message.delete()
            emb = discord.Embed(title="Bot Invite Deleted", colour=discord.Colour.red())

            async for msg in message.channel.history(limit=1, around=message):
                emb.title = "Bot Invite Deleted"
                emb.colour = discord.Colour.red()
                if msg:
                    emb.description = f"{self.emoji['link']}[**Jump To Location**]({msg.jump_url})"
                    break
        else:
            emb = discord.Embed(title="Bot Invite Detected", colour=discord.Colour.orange())
            emb.description = f"{self.emoji['link']}[**Jump To Message**]({message.jump_url})"

        emb.add_field(name="URL", value=url.string, inline=False)
        emb.add_field(
            name="Sent By", value=f"{message.author.name}#{message.author.discriminator} {message.author.mention}"
        )
        await self.send_message(message.guild.id, emb, guild_data)

    async def handle_generic_url(self, message, url):
        """Handle generic urls"""
        guild_data = await self.bot.get_guild_data(message.guild.id)

        if guild_data.log_urls:
            emb = discord.Embed(title="URL Detected", colour=discord.Colour.orange())
            emb.description = f"{self.emoji['link']}[**Jump To Message**]({message.jump_url})"
            emb.add_field(name="URL", value=url.string, inline=False)
            emb.add_field(
                name="Sent By", value=f"{message.author.name}#{message.author.discriminator} {message.author.mention}"
            )
            await self.send_message(message.guild.id, emb)

    @cog_ext.cog_subcommand(
        base="block",
        name="bot_invites",
        description="Delete any messages containing a bot invite",
        options=[
            manage_commands.create_option(
                name="toggle", description="Enable or disable this feature", option_type=5, required=True
            )
        ],
    )
    @commands.has_permissions(manage_messages=True)
    async def block_bot_invites(self, ctx: SlashContext, toggle):
        await ctx.defer()
        guild_data = await self.bot.get_guild_data(ctx.guild_id)

        guild_data.block_bot_invites = toggle

        await self.bot.redis.set(guild_data.key, guild_data.to_json())
        await ctx.send(f"Bot invites are now {'blocked' if toggle else 'allowed'}")

    @cog_ext.cog_subcommand(
        base="block",
        name="guild_invites",
        description="Delete any messages containing a guild invite",
        options=[
            manage_commands.create_option(
                name="toggle", description="Enable or disable this feature", option_type=5, required=True
            )
        ],
    )
    @commands.has_permissions(manage_messages=True)
    async def block_guild_invites(self, ctx: SlashContext, toggle):
        await ctx.defer()
        guild_data = await self.bot.get_guild_data(ctx.guild_id)

        guild_data.block_guild_invites = toggle

        await self.bot.redis.set(guild_data.key, guild_data.to_json())
        await ctx.send(f"Guild invites are now {'blocked' if toggle else 'allowed'}")

    @cog_ext.cog_subcommand(
        base="log",
        name="links",
        description="Log any links posted to your server",
        options=[
            manage_commands.create_option(
                name="toggle", description="Enable or disable this feature", option_type=5, required=True
            )
        ],
    )
    @commands.has_permissions(manage_messages=True)
    async def log_links(self, ctx: SlashContext, toggle):
        await ctx.defer()
        guild_data = await self.bot.get_guild_data(ctx.guild_id)

        guild_data.log_urls = toggle

        await self.bot.redis.set(guild_data.key, guild_data.to_json())
        await ctx.send(f"URLs are now being {'logged' if toggle else 'ignored'}")

    @cog_ext.cog_subcommand(
        base="exception",
        name="guild_invites",
        description="Add or remove an exception to guild invite blocking",
        options=[
            manage_commands.create_option(
                name="guild", description="The id of the guild to allow invites for", option_type=3, required=True
            ),
            manage_commands.create_option(
                name="add_or_remove",
                description="To add or remove this guild",
                option_type=3,
                required=True,
                choices=[
                    manage_commands.create_choice(value="add", name="add"),
                    manage_commands.create_choice(value="remove", name="remove"),
                ],
            ),
        ],
    )
    async def guild_exception(self, ctx: SlashContext, guild: int, add_or_remove: str):
        await ctx.defer()

        guild_data = await self.bot.get_guild_data(ctx.guild_id)

        if add_or_remove == "add":
            if guild in guild_data.allowed_guild_invites:
                return await ctx.send(f"Invites for `{guild}` are already allowed")

            guild_data.allowed_guild_invites.append(guild)
            await self.bot.redis.set(guild_data.key, guild_data.to_json())

            return await ctx.send(f"Invites for `{guild}` are now allowed")

        elif add_or_remove == "remove":
            if guild not in guild_data.allowed_guild_invites:
                return await ctx.send(f"Invites for `{guild}` aren't allowed")

            guild_data.allowed_guild_invites.remove(guild)
            await self.bot.redis.set(guild_data.key, guild_data.to_json())

            return await ctx.send(f"Invites for `{guild}` are no longer allowed")


def setup(bot):
    """Called when this cog is mounted"""
    bot.add_cog(LinkDetection(bot))
    log.info("LinkDetection mounted")


def teardown(bot):
    """Called when this cog is unmounted"""
    log.warning("LinkDetection un-mounted")
    for handler in log.handlers[:]:
        log.removeHandler(handler)
