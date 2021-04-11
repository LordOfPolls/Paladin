import asyncio
import base64
import json
import logging
import time
import traceback
from datetime import datetime, timedelta

from discord.ext import commands, tasks
from discord.ext.commands import BucketType
from discord_slash import cog_ext, SlashContext

from source import utilities, dataclass, jsonManager
from source.shared import *

log: logging.Logger = utilities.getLog("Cog::AutoDel")

del_channel_template = [
    {
        "channel_id": None,
        "delete_after": None,
    }
]


class AutoDelete(commands.Cog):
    """Auto Delete Messages in a specified channel"""

    def __init__(self, bot):
        self.bot: dataclass.Bot = bot

        self.lock = asyncio.Lock()
        self.emoji = bot.emoji_list
        self.prefix = "delMessage"

        self.guild_data = {}

    # have multiple commands share the same max_concurrency object
    max_concurrency = commands.max_concurrency(1, BucketType.guild, wait=False)

    async def setup(self):
        await self.cache_guild_data()

        self.task.start()

    async def cache_guild_data(self):
        """Caches the guild data to avoid waiting on db operations constantly"""
        log.debug("Caching guild data from DB")
        all_guild_data = await self.bot.db.execute(f"SELECT * FROM paladin.guilds")
        temp = {}
        for guild_data in all_guild_data:
            # preload autodel data
            guild_data["autoDelChannel"] = json.loads(guild_data["autoDelChannel"])

            temp[guild_data["guildID"]] = guild_data

        self.guild_data = temp.copy()

    @tasks.loop(minutes=1)
    async def task(self):
        try:
            log.spam("Running delete task...")

            for guild in self.bot.guilds:
                guild_data = self.guild_data.get(str(guild.id))
                if guild_data:
                    auto_del_data = guild_data["autoDelChannel"]
                    for channel_data in auto_del_data:
                        channel: discord.TextChannel = self.bot.get_channel(int(channel_data["channel_id"]))
                        if channel:
                            if (
                                len(
                                    await channel.history(
                                        before=datetime.utcnow() - timedelta(minutes=channel_data["delete_after"]),
                                        after=datetime.utcnow() - timedelta(days=14),
                                        limit=1,
                                    ).flatten()
                                )
                                != 0
                            ):
                                await channel.purge(
                                    before=datetime.utcnow() - timedelta(minutes=channel_data["delete_after"]),
                                    after=datetime.utcnow() - timedelta(days=14),
                                    limit=500,
                                    oldest_first=True,
                                )
                                log.spam(f"Deleted messages from {channel.id}")
                await asyncio.sleep(0)
        except Exception as e:
            log.error("".join(traceback.format_exception(type(e), e, e.__traceback__)))

    @cog_ext.cog_subcommand(**jsonManager.getDecorator("disable.autodelete"))
    @max_concurrency
    @commands.has_permissions(manage_messages=True)
    async def disable_cmd(self, ctx: SlashContext, channel: discord.TextChannel = None):
        await ctx.defer(hidden=True)

        if channel is None:
            channel = ctx.channel
        guild_data = self.guild_data[str(ctx.guild.id)]

        auto_del_data: list = guild_data.get("autoDelChannel")

        if guild_data is None or str(channel.id) not in str(auto_del_data):
            return await ctx.send(f"I'm not auto-deleting messages in {channel.mention}", hidden=True)

        index = next(
            (index for (index, d) in enumerate(auto_del_data) if str(d["channel_id"]) == str(channel.id)), None
        )

        del auto_del_data[index]

        to_upload = json.dumps(auto_del_data)
        await self.bot.db.execute(
            f"INSERT INTO paladin.guilds (guildID, autoDelChannel) VALUES ('{ctx.guild.id}', '{to_upload}') "
            f"ON DUPLICATE KEY UPDATE autoDelChannel = '{to_upload}'"
        )

        await self.cache_guild_data()
        await ctx.send(f"Got it, auto-deletion has been disabled in {channel.mention}", hidden=True)

    @cog_ext.cog_subcommand(**jsonManager.getDecorator("setup.autodelete"))
    @max_concurrency
    @commands.has_permissions(manage_messages=True)
    async def setup_cmd(self, ctx: SlashContext, time: int, unit: int, channel: discord.TextChannel = None):
        await ctx.defer(hidden=True)

        # sanity check

        if channel is None:
            channel = ctx.channel
        if not isinstance(channel, discord.TextChannel):
            return await ctx.send("Only text channels are supported")

        if time < 1:
            return await ctx.send("Time must be at least 1 minute", hidden=True)
        if time >= 1:
            if unit == 2:
                time *= 60
            elif unit == 3:
                time *= 1440

        # get current guild data
        guild_data = self.guild_data[str(ctx.guild.id)]
        if guild_data is not None:
            auto_del_data = guild_data["autoDelChannel"]
        else:
            auto_del_data = []

        if str(channel.id) in str(auto_del_data):
            # channel already in db, update data instead
            index = next(
                (index for (index, d) in enumerate(auto_del_data) if str(d["channel_id"]) == str(channel.id)), None
            )
            data: dict = auto_del_data[index]
            data["delete_after"] = time
            auto_del_data[index] = data
        else:
            data: dict = del_channel_template[0].copy()
            data["channel_id"] = str(ctx.channel_id)
            data["delete_after"] = time
            auto_del_data.append(data)

        try:
            to_upload = json.dumps(auto_del_data)
            await self.bot.db.execute(
                f"INSERT INTO paladin.guilds (guildID, autoDelChannel) VALUES ('{ctx.guild.id}', '{to_upload}') "
                f"ON DUPLICATE KEY UPDATE autoDelChannel = '{to_upload}'"
            )
            await ctx.send(
                f"New Messages sent in `{channel.name}` will now be deleted after `{time}` minute{'s' if time > 1 else ''}\n"
                f"**Note:** This channel will be checked for messages that match that rule within the a minute",
                hidden=True,
            )
        except Exception as e:
            log.error(f"Error saving autoDelete data: {e}")
            await ctx.send("An error occurred saving that data... please try again later")
        await self.cache_guild_data()

    @setup_cmd.error
    @disable_cmd.error
    async def cmd_error(self, ctx, error):
        if isinstance(error, commands.MaxConcurrencyReached):
            await ctx.send("Hang on, another user in your server is updating your server's settings", hidden=True)
        elif isinstance(error, commands.CheckFailure):
            await ctx.send("Sorry you need `manage_messages` to use that command", hidden=True)
        else:
            log.error(error)
            await ctx.send("An error occurred executing that command... please try again later", hidden=True)


def setup(bot):
    """Called when this cog is mounted"""
    bot.add_cog(AutoDelete(bot))
    log.info("AutoDelete mounted")


def teardown(bot):
    """Called when this cog is unmounted"""
    log.warning("AutoDelete un-mounted")
    for handler in log.handlers[:]:
        log.removeHandler(handler)
