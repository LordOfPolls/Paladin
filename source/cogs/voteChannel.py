import json
import logging

import discord
from discord.ext import commands
from discord_slash import SlashContext, cog_ext
from discord_slash.utils import manage_commands

from source import dataclass, utilities

log: logging.Logger = utilities.getLog("Cog::Voting")


class VoteChannel(commands.Cog):
    """Configuration commands"""

    def __init__(self, bot: dataclass.Bot):
        self.bot = bot

        self.slash = bot.slash

        self.emoji = bot.emoji_list
        self.bot.add_listener(self.on_message, "on_message")

        self.cache: set = set()

    async def setup(self):
        log.info("Caching vote channels...")
        keys = await self.bot.redis.keys("guild||*")
        for key in keys:
            data = json.loads(await self.bot.redis.get(key))
            vote_channels = data.get("vote_channel_data") if data.get("vote_channel_data") is not None else None
            if vote_channels is not None:
                for channel in vote_channels:
                    self.cache.add(channel)
        log.debug("Cache complete")

    async def on_message(self, message: discord.Message):
        """Adds a vote reaction to all messages posted in a channel"""
        if message.author.id != self.bot.user.id:
            if message.channel.id in self.cache:
                # only check the cache to avoid spamming redis, and improve resp time
                if message.channel.slowmode_delay < 60:
                    # slow mode has been removed, stop trying to react in this channel
                    self.cache.remove(message.channel.id)
                    guild_data = await self.bot.get_guild_data(message.guild.id)
                    guild_data.vote_channel_data.remove(message.channel.id)

                    return await self.bot.redis.set(guild_data.key, guild_data.to_json())

                await message.add_reaction(self.emoji["checkMark"])
                await message.add_reaction(self.emoji["crossMark"])

    @cog_ext.cog_subcommand(
        base="set-channel",
        name="voting",
        description="Automatically add vote reactions to all messages sent in this channel",
        options=[
            manage_commands.create_option(
                name="channel",
                option_type=7,
                description="The channel in question, defaults to the current channel",
                required=False,
            )
        ],
    )
    @commands.has_permissions(manage_messages=True)
    async def _set_channel(self, ctx: SlashContext, channel: discord.TextChannel = None):
        if channel is None:
            channel = ctx.channel

        if not isinstance(channel, discord.TextChannel):
            return await ctx.send("Sorry, only text channels can have vote reactions")

        if channel.slowmode_delay < 60:
            return await ctx.send(
                "Sorry, a channel must have a slow-mode of at least 1 minute set to prevent bot abuse"
            )

        await ctx.defer()

        guild_data = await self.bot.get_guild_data(ctx.guild_id)
        if channel.id not in guild_data.vote_channel_data:
            guild_data.vote_channel_data.append(channel.id)
        self.cache.add(channel.id)
        await self.bot.redis.set(guild_data.key, guild_data.to_json())

        await ctx.send(f"New messages sent in {channel.mention} will now have vote reactions added")

    @cog_ext.cog_subcommand(
        base="clear-channel",
        name="voting",
        description="Stop reacting to messages in the chosen channel",
        options=[
            manage_commands.create_option(
                name="channel",
                option_type=7,
                description="The channel in question, defaults to the current channel",
                required=False,
            )
        ],
    )
    @commands.has_permissions(manage_messages=True)
    async def _clear_channel(self, ctx, channel: discord.TextChannel = None):
        if channel is None:
            channel = ctx.channel

        if not isinstance(channel, discord.TextChannel):
            return await ctx.send("Sorry, only text channels can have vote reactions")

        await ctx.defer()
        guild_data = await self.bot.get_guild_data(ctx.guild_id)

        if channel.id not in guild_data.vote_channel_data:
            return await ctx.send(f"{channel.mention} does not have vote reactions enabled")

        guild_data.vote_channel_data.remove(channel.id)
        self.cache.remove(channel.id)
        await self.bot.redis.set(guild_data.key, guild_data.to_json())

        await ctx.send(f"Vote reactions in {channel.mention} have been disabled")


def setup(bot):
    """Called when this cog is mounted"""
    bot.add_cog(VoteChannel(bot))
    log.info("VoteChannel mounted")


def teardown(bot):
    """Called when this cog is unmounted"""
    log.warning("VoteChannel un-mounted")
    for handler in log.handlers[:]:
        log.removeHandler(handler)
