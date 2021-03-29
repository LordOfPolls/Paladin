import logging

from discord.ext import commands
from discord_slash import SlashContext, cog_ext
from discord_slash.utils import manage_commands

from source import utilities, dataclass, messageObject

log: logging.Logger = utilities.getLog("Cog::mail")


class ModMail(commands.Cog):
    """Configuration commands"""

    def __init__(self, bot: dataclass.Bot, s="📬"):
        self.bot = bot

        self.slash = bot.slash

        self.emoji = s

    @cog_ext.cog_subcommand(
        base="mail",
        name="send",
        description="Send a message to your moderators",
        options=[
            manage_commands.create_option(
                name="content",
                description="The content of your message",
                option_type=str,
                required=True,
            ),
            manage_commands.create_option(
                name="title",
                description="An optional title of for your message",
                option_type=str,
                required=False,
            ),
        ],
        guild_ids=[701347683591389185],
    )
    async def send(self, ctx: SlashContext, **kwargs):
        """Send a message to Modmail"""
        await ctx.respond()

        mod_message = messageObject.Message(self.bot, ctx.guild_id, ctx.author_id)
        mod_message.content = kwargs["content"]
        mod_message.title = kwargs["title"] if "title" in kwargs else None
        await mod_message.store()

        await ctx.send("Sent 📫")


def setup(bot):
    """Called when this cog is mounted"""
    bot.add_cog(ModMail(bot))
    log.info("Mail mounted")


manage_commands


def teardown(bot):
    """Called when this cog is unmounted"""
    log.warning("Mail un-mounted")
    for handler in log.handlers[:]:
        log.removeHandler(handler)
