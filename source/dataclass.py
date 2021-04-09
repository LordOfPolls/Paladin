import asyncio
import inspect
import json
import subprocess
import typing
import toml
from datetime import datetime, timedelta

import discord
from discord.ext import commands
import discord_slash

from discord_slash import SlashContext

from source import databaseManager, events, monkeypatch


class Bot(commands.Bot):
    """
    Expands on the default bot class, and helps with type-hinting
    """

    def __init__(self, cogList=list, *args, **kwargs):
        self.cogList = cogList
        """A list of cogs to be mounted"""

        self.db = databaseManager.DBConnector()
        """The bots database"""

        self.appInfo: discord.AppInfo = None
        """A cached application info"""

        self.startTime = None
        """The time the bot started"""

        self.shouldUpdateBL = True
        """Should the bot try and update bot-lists"""

        self.perms = 0
        """The perms the bot needs"""

        self.paladinEvents: events.PaladinEvents = events.PaladinEvents()

        emoji = open("data/emoji.json", "r")
        self.emoji_list = json.load(emoji)
        emoji.close()
        """A dict of emoji the bot uses"""

        try:
            # grab version from poetry/version in pyproject.toml
            pyproject = open("./pyproject.toml", "r")
            self.version = toml.load(pyproject)["tool"]["poetry"]["version"]
            pyproject.close()
        except FileNotFoundError:
            self.version = "Unknown"

        super().__init__(*args, **kwargs)

        # monkey patch in some functionality to slashCommands while setting it up
        self.slash: discord_slash.SlashCommand = monkeypatch.monkeypatched_SlashCommand(
            self, sync_commands=False if "sync_commands" not in kwargs else kwargs["sync_commands"]
        )
        """The slash command system"""

    async def is_in_guild(self, ctx: SlashContext):
        """Prevents the bot being used in dm"""
        if ctx.guild is None:
            await ctx.send("Sorry this bot can only be used in a server")
            return False
        return True

    async def close(self):
        """Close the connection to discord"""

        for extension in tuple(self.extensions):
            try:
                self.unload_extension(extension)
            except Exception:
                pass

        for cog in tuple(self.cogs):
            try:
                self.remove_cog(cog)
            except Exception:
                pass

        # let the event loops close gracefully
        while not self.paladinEvents._queue.empty():
            await asyncio.sleep(0)
        self.paladinEvents.process = False
        if self.paladinEvents.task is not None:
            while not self.paladinEvents.task.done():
                await asyncio.sleep(0)

        # close db connection
        self.db.dbPool.close()
        await self.db.dbPool.wait_closed()

        if self._closed:
            return

        await self.http.close()
        self._closed = True

        for voice in self.voice_clients:
            try:
                await voice.disconnect()
            except Exception:
                # if an error happens during disconnects, disregard it.
                pass

        if self.ws is not None and self.ws.open:
            await self.ws.close(code=1000)

        self._ready.clear()

    async def getMessage(self, messageID: int, channel: discord.TextChannel) -> typing.Union[discord.Message, None]:
        """Gets a message using the id given
        we dont use the built in get_message due to poor rate limit
        """
        for message in self.cached_messages:
            if message.id == messageID:
                return message
        # bot has not cached this message, so search the channel for it
        try:
            o = discord.Object(id=messageID + 1)
            msg = await channel.history(limit=1, before=o).next()

            if messageID == msg.id:
                return msg

            return None
        except discord.NoMoreItems:
            # the message could not be found
            return None
        except Exception as e:
            print(e)
        return None

    @staticmethod
    def formatDate(date: datetime) -> str:
        return date.strftime("%b %d %Y %H:%M:%S")

    @staticmethod
    def strf_delta(timeDelta: timedelta) -> str:
        """Formats timedelta into a human readable string"""
        years, days = divmod(timeDelta.days, 365)
        hours, rem = divmod(timeDelta.seconds, 3600)
        minutes, seconds = divmod(rem, 60)

        yearsFmt = f"{years} year{'s' if years > 1 or years == 0 else ''}"
        daysFmt = f"{days} day{'s' if days > 1 or days == 0 else ''}"
        hoursFmt = f"{hours} hour{'s' if hours > 1 or hours == 0 else ''}"
        minutesFmt = f"{minutes} minute{'s' if minutes > 1 or minutes == 0 else ''}"
        secondsFmt = f"{seconds} second{'s' if seconds > 1 or seconds == 0 else ''}"

        if years >= 1:
            return f"{yearsFmt} and {daysFmt}"
        if days >= 1:
            return f"{daysFmt} and {hoursFmt}"
        if hours >= 1:
            return f"{hoursFmt} and {minutesFmt}"
        return f"{minutesFmt} and {secondsFmt}"

    @staticmethod
    def _determine_update():
        """Checks git if a newer version is available"""
        subprocess.run(["git", "fetch"])
        data = subprocess.check_output(["git", "status"])
        if "Your branch is behind" in data.decode():
            return "Update Available"
        return "Up to date"

    async def determine_update(self):
        """Checks git if a newer version is available"""
        return await asyncio.to_thread(self._determine_update)
