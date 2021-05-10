import asyncio
import json
import logging
import subprocess
import typing
from datetime import datetime, timedelta

import discord
import discord_slash
import redis
import toml
from discord.ext import commands
from discord_slash import SlashContext

from source import events, monkeypatch, utilities


class AsyncRedis:
    def __init__(self, host="localhost", port=6379, db=0):
        self.log = utilities.getLog("Redis", logging.INFO)

        self.log.info("Connecting to redis...")
        self.__redis = redis.Redis(host=host, port=port, db=db)

        try:
            self.__redis.ping()
        except Exception as e:
            self.log.critical(e)
            exit(1)

    async def set(self, key, value, ex=None, px=None, nx=False, xx=False, keepttl=False):
        self.log.debug(f"SET:: {key=} {value=} {ex=} {px=} {nx=} {xx=} {keepttl=}")
        return await asyncio.to_thread(self.__redis.set, key, value, ex=ex, px=px, nx=nx, xx=xx, keepttl=keepttl)

    async def get(self, key):
        self.log.debug(f"GET:: {key=}")
        return await asyncio.to_thread(self.__redis.get, key)

    async def keys(self, pattern):
        self.log.debug(f"KEYS:: {pattern=}")
        return await asyncio.to_thread(self.__redis.keys, pattern)

    async def ping(self):
        self.log.debug(f"PING:: None")
        return await asyncio.to_thread(self.__redis.ping)


class Guild:
    """An object representing a guild"""

    def __init__(self, guild_id: int):
        self.guild_id: int = guild_id

        # roles for this guild
        self.role_mute_id: typing.Optional[int] = None

        # channels for this guild
        self.channel_action_log_id: typing.Optional[int] = None
        self.channel_mod_log_id: typing.Optional[int] = None

        # [{"channel_id": 11111111111111, "delete_after": 100},]
        self.auto_delete_data: list = []

    @property
    def key(self):
        """The key for this user in the redis db"""
        return f"guild||{self.guild_id}"

    def to_json(self):
        """Dump this object to json ready for push to redis"""
        return json.dumps(self, default=lambda o: o.__dict__, sort_keys=True, indent=0)

    def load_from_dict(self, raw_data: dict):
        """Load values from a dict"""
        for key in raw_data.keys():
            if hasattr(self, key):
                self.__setattr__(key, raw_data.get(key))


class Member:
    """An object representing a member of a guild"""

    def __init__(self, guild_id: int, user_id: int):
        self.guild_id: int = guild_id
        self.user_id: int = user_id

        # state of this user
        self.warnings: int = 0
        self.muted: bool = False
        self.unmute_time: typing.Optional[datetime] = None

    @property
    def key(self):
        """The key for this user in the redis db"""
        return f"member||{self.guild_id}{self.user_id}"

    def to_json(self):
        """Dump this object to json ready for push to redis"""

        # this is dirty but it works
        if self.unmute_time is not None:
            self.unmute_time = str(self.unmute_time)

        data = json.dumps(self, default=lambda o: o.__dict__, sort_keys=True, indent=0)

        if self.unmute_time is not None:
            self.unmute_time = datetime.strptime(self.unmute_time, "%Y-%m-%d %H:%M:%S.%f")

        return data

    def load_from_dict(self, raw_data: dict):
        """Load values from a dict"""

        for key in raw_data.keys():
            if hasattr(self, key):
                self.__setattr__(key, raw_data.get(key))

        if self.unmute_time is not None:
            self.unmute_time = datetime.strptime(self.unmute_time, "%Y-%m-%d %H:%M:%S.%f")


class ModAction:
    """An object representing a moderation action"""

    def __init__(self, guild_id: int, action_id: int, action_type: int, moderator_id: int):
        self.guild_id: int = guild_id
        self.action_id: int = action_id
        self.action_type: int = action_type

        self.message_id: typing.Optional[int] = None
        self.channel_id: typing.Optional[int] = None

        # users involved in this action
        self.moderator_id: int = moderator_id
        self.user_id: typing.Optional[int] = None

        self.role_id: typing.Optional[int] = None

        self.reason: str = f"**Moderator:** Please use `/reason {self.action_id}`"

    @property
    def key(self):
        """The key for this user in the redis db"""
        return f"action||{self.guild_id}{self.action_id}"

    def to_json(self):
        """Dump this object to json ready for push to redis"""
        return json.dumps(self, default=lambda o: o.__dict__, sort_keys=True, indent=0)

    def load_from_dict(self, raw_data: dict):
        """Load values from a dict"""
        for key in raw_data.keys():
            if hasattr(self, key):
                self.__setattr__(key, raw_data.get(key))


class Bot(commands.Bot):
    """
    Expands on the default bot class, and helps with type-hinting
    """

    def __init__(self, cogList=list, *args, **kwargs):
        self.cogList = cogList
        """A list of cogs to be mounted"""

        self.redis = AsyncRedis()
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

    async def get_guild_data(self, guild_id: int) -> Guild:
        data = await self.redis.get(f"guild||{guild_id}")
        if data is None:
            data = Guild(guild_id)
        else:
            raw_data = json.loads(data.decode())
            data = Guild(raw_data.get("guild_id"))
            data.load_from_dict(raw_data)

        return data

    async def get_action_data(self, guild_id: int, action_id: int) -> ModAction:
        data = await self.redis.get(f"action||{guild_id}{action_id}")
        if data is None:
            return None
        else:
            raw_data = json.loads(data.decode())
            data = ModAction(guild_id, action_id, 0, 0)
            data.load_from_dict(raw_data)

        return data

    async def get_member_data(self, guild_id: int, user_id: int) -> Member:
        data = await self.redis.get(f"member||{guild_id}{user_id}")
        if data is None:
            data = Member(guild_id, user_id)
        else:
            raw_data = json.loads(data.decode())
            data = Member(guild_id, user_id)
            data.load_from_dict(raw_data)

        return data

    async def close(self):
        """Close the connection to discord"""

        for extension in tuple(self.extensions):
            try:
                self.unload_extension(extension)
            except Exception:
                pass

        for cog in tuple(self.cogs):
            try:
                _c = self.get_cog(cog)
                if hasattr(_c, "scheduler"):
                    # cog has a scheduler, shut it down
                    _c.scheduler.shutdown(wait=False)
                    while not _c.scheduler.running:
                        await asyncio.sleep(1)
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
    def strf_delta(time_delta: timedelta, show_seconds=True) -> str:
        """Formats timedelta into a human readable string"""
        years, days = divmod(time_delta.days, 365)
        hours, rem = divmod(time_delta.seconds, 3600)
        minutes, seconds = divmod(rem, 60)

        years_fmt = f"{years} year{'s' if years > 1 or years == 0 else ''}"
        days_fmt = f"{days} day{'s' if days > 1 or days == 0 else ''}"
        hours_fmt = f"{hours} hour{'s' if hours > 1 or hours == 0 else ''}"
        minutes_fmt = f"{minutes} minute{'s' if minutes > 1 or minutes == 0 else ''}"
        seconds_fmt = f"{seconds} second{'s' if seconds > 1 or seconds == 0 else ''}"

        if years >= 1:
            return f"{years_fmt} and {days_fmt}"
        if days >= 1:
            return f"{days_fmt} and {hours_fmt}"
        if hours >= 1:
            return f"{hours_fmt} and {minutes_fmt}"
        if show_seconds:
            return f"{minutes_fmt} and {seconds_fmt}"
        return f"{minutes_fmt}"

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
