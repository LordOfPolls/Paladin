import json
import typing
import asyncio
from source import dataclass, utilities

log = utilities.getLog("message")


class Message:
    def __init__(self, bot: dataclass.Bot, guild_id: int = 0, author_id: int = 0):
        # a ref to the bot
        self.bot = bot
        # a ref to the bot's db client
        self.db = bot.db
        # the message id
        self._message_id = None
        # is this message open?
        self.open: bool = True
        # the guild this message belongs to
        self.guildID: int = guild_id
        # the author of this message
        self.authorID: int = author_id
        # the title of this message
        self.title: typing.Union[None, str] = None
        # the content of this message
        self.content: typing.Union[None, str] = None

    def __eq__(self, other):
        if isinstance(other, Message):
            if self._message_id == other._message_id:
                return True
        return False

    def __str__(self):
        data = {
            "message_id": self._message_id,
            "open": self.open,
            "guild_id": self.guildID,
            "author_id": self.authorID,
            "title": self.title,
            "content": self.content,
        }
        return json.dumps(data)

    async def importMessage(
        self,
        guildID: int,
        authorID: typing.Union[None, int] = None,
        index: typing.Union[None, int] = None,
    ):
        """
        Imports a message from the db and loads all the attributes into this object
        By default this fetches the latest message, however you can fetch a specific one
        :param guildID: The ID of the guild in question
        :param authorID: The author of the message
        :param index: The index of this message
        :return:
        """
        while not self.bot.is_ready() or not self.db.dbPool:
            # if bot or DB is not ready, wait
            await asyncio.sleep(1)
        log.debug("Importing message object...")

        operation = f"SELECT * FROM paladin.messages WHERE guildID = '{guildID}'"
        if authorID:
            operation += " AND authorID = '{authorID}'"

        data = await self.db.execute(operation)

        if data:
            index = index if index else 0
            msgData: dict = data[index]

            self._message_id = int(msgData["messageID"])
            self.guildID = guildID
            self.authorID = int(msgData["authorID"])
            self.title = json.loads(data["title"])
            self.content = json.loads(data["content"])
            self.open = json.loads(data["open"])

            return self
        return None

    async def store(self):
        """Store this object in the database"""
        while not self.bot.is_ready() or not self.db.dbPool:
            # if bot or DB is not ready, wait
            await asyncio.sleep(1)

        log.debug("Storing message object...")
        title = (
            f"'{await self.db.escape(json.dumps(self.title))}'"
            if self.title is not None
            else None
        )
        content = await self.db.escape(json.dumps(self.content))
        await self.db.execute(
            f"INSERT INTO paladin.messages (guildID, authorID, title, content, open) VALUES "
            f"('{self.guildID}', "
            f"'{self.authorID}', "
            f"{title}, "
            f"'{content}', "
            f"{self.open})"
        )

    async def update(self):
        """Update an existing message in the database"""
        while not self.bot.is_ready() or not self.db.dbPool:
            # if bot or DB is not ready, wait
            await asyncio.sleep(1)

        log.debug("Updating message object...")
        title = (
            f"'{await self.db.escape(json.dumps(self.title))}'"
            if self.title is not None
            else None
        )
        content = await self.db.escape(json.dumps(self.content))
        await self.db.execute(
            f"UPDATE paladin.messages SET "
            f"guildID = '{self.guildID}', authorID='{self.authorID}', title={title}, content='{content}', "
            f"open={self.open} WHERE messageID = {self._message_id}"
        )


async def getMessage(
    bot: dataclass.Bot,
    guildID: int,
    authorID: typing.Union[None, int] = None,
    index: typing.Union[None, int] = None,
):
    """
    Imports a message from the db and loads all the attributes into this object
    By default this fetches the latest message, however you can fetch a specific one
    :param bot: A reference to the bot
    :param guildID: The ID of the guild in question
    :param authorID: The author of the message/x
    :param index: The index of this message
    :return:
    """
    message: Message = Message(bot)
    await message.importMessage(guildID=guildID, authorID=authorID, index=index)
    return Message
