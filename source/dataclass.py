import json
import typing
from datetime import datetime, timedelta

import discord
from discord.ext import commands
from discord_slash import SlashCommand

from source import databaseManager, events


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

        super().__init__(*args, **kwargs)

        self.slash = SlashCommand(
            self,
            sync_commands=False
            if "sync_commands" not in kwargs
            else kwargs["sync_commands"],
        )
        """The slash command system"""

    async def getMessage(
        self, messageID: int, channel: discord.TextChannel
    ) -> typing.Union[discord.Message, None]:
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
