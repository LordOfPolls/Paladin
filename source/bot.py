import asyncio
import logging
import traceback
from datetime import datetime

import discord
import discord_slash
import discord_slash.error
from discord.ext import commands
from discord_slash import SlashContext
from discord_slash.utils import manage_commands

from . import dataclass, utilities

log: logging.Logger = utilities.getLog("Bot", level=logging.DEBUG)
intents = discord.Intents.all()
intents.presences = False

bot = dataclass.Bot(
    command_prefix=">",
    description="Paladin",
    case_insensitive=True,
    intents=intents,
    cogList=[
        "source.cogs.base",
        "source.cogs.mute",
        "source.cogs.modlog",
        "source.cogs.logAction",
        "source.cogs.baseModeration",
        "source.cogs.userWarn",
        "source.cogs.userInfo",
        "source.cogs.listPermissions",
        "source.cogs.autoDelete",
        "source.cogs.voteChannel",
        "source.cogs.linkDetection",
        "source.cogs.config",
    ],
    help_command=None,
    sync_commands=False,
    activity=discord.Game("Startup"),
)
slash = bot.slash

utilities.getLog("discord", logging.INFO)
utilities.getLog("discord_slash", logging.DEBUG)
bot.perms = "8"


def run():
    if bot.cogList:
        log.info("Mounting cogs...")
        for cog in bot.cogList:
            log.spam(f"Mounting {cog}...")
            bot.load_extension(cog)
    else:
        log.warning("No cogs to load!")
    log.info("Connecting to discord...")
    bot.run(utilities.getToken(), bot=True, reconnect=True)


async def startupTasks():
    """All the tasks the bot needs to run when it starts up"""
    log.debug("Running startup tasks...")
    bot.appInfo = await bot.application_info()
    bot.startTime = datetime.now()

    log.info("Caching permission data")
    slash.perms_cache = {}
    for guild in bot.guilds:
        guild_data = await bot.get_guild_data(guild.id)
        if guild_data:
            slash.perms_cache[guild.id] = guild_data.moderation_roles

    async with asyncio.Lock():
        log.info("Running cog setup tasks")
        for cog in bot.cogs:
            _c = bot.get_cog(cog)
            try:
                if hasattr(_c, "setup"):
                    await _c.setup()
            except Exception as e:
                log.error("".join(traceback.format_exception(type(e), e, e.__traceback__)))
    bot.paladinEvents.process = True
    bot.paladinEvents.task = asyncio.create_task(bot.paladinEvents.event_loop())


@bot.event
async def on_ready():
    """Called when the bot is ready"""
    if not bot.startTime:
        await startupTasks()

    update = await bot.determine_update()

    output = [
        "",
        f"Logged in as         : {bot.user.name} #{bot.user.discriminator}",
        f"User ID              : {bot.user.id}",
        f"Start Time           : {bot.startTime.ctime()}",
        f"Server Count         : {len(bot.guilds)}",
        f"Cog Count            : {len(bot.cogs)}",
        f"Command Count        : {len(slash.commands)}",
        f"Update Status        : {update}",
        f"Paladin Version      : {bot.version}",
        f"Discord.py Version   : {discord.__version__}",
        f"DiscordSlash Version : {discord_slash.__version__}",
    ]

    length = len(max(output, key=len))
    output.insert(1, "INFO".center(length, "-"))
    output.append("END-INFO".center(length, "-"))
    log.info("\n".join(output))

    await bot.change_presence(
        status=discord.Status.online,
        activity=discord.Activity(type=discord.ActivityType.watching, name="over your server"),
    )


@bot.event
async def on_slash_command(ctx: SlashContext):
    subcommand = ""
    try:
        if ctx.subcommand_name:
            subcommand = ctx.subcommand_name
    except AttributeError:
        pass
    if ctx.guild:
        log.info(f"CMD - {ctx.guild.id}::{ctx.author.id}: {ctx.command} {subcommand}")
    else:
        log.info(f"CMD - Direct Message::{ctx.author.id}: {ctx.command} {subcommand}")


@bot.event
async def on_command_error(ctx, ex):
    await on_slash_command_error(ctx, ex)


@bot.event
async def on_slash_command_error(ctx, ex):

    # default error messages
    if isinstance(ex, commands.CheckFailure) or isinstance(ex, discord_slash.error.CheckFailure):
        try:
            await ctx.send("Sorry you don't have the correct permissions for that command")
        except:
            pass
    elif isinstance(ex, commands.MaxConcurrencyReached):
        try:
            await ctx.send("Hang on, too many people are using this command")
        except:
            pass
    elif isinstance(ex, commands.CommandOnCooldown):
        try:
            await ctx.send("Slow Down! Wait {:.2f}s".format(ex.retry_after))
        except:
            pass
    else:
        # log anything that isnt the above
        log.error(
            "Ignoring exception in command {}: {}".format(
                ctx.command,
                "".join(traceback.format_exception(type(ex), ex, ex.__traceback__)),
            )
        )


async def guildPurge(guildID: int):
    """Purges all data related to a guild"""
    # await bot.db.execute(
    #     f"DELETE FROM [placeholder] WHERE guildID='{guildID}'"
    # )
    try:
        await manage_commands.remove_all_commands_in(bot_id=bot.user.id, bot_token=bot.http.token, guild_id=guildID)
    except:
        pass


@bot.event
async def on_guild_join(guild: discord.Guild):
    """Called when bot is added to a guild"""
    while not bot.is_ready():
        await asyncio.sleep(5)
    log.info(f"Joined Guild {guild.id}. {len([m for m in guild.members if not m.bot])} users")
    # todo: pregen data on db


@bot.event
async def on_guild_remove(guild):
    while not bot.is_ready():
        await asyncio.sleep(5)
    if guild.id == 110373943822540800:
        return
    log.info(f"Left Guild {guild.id} || Purging data...")
    # todo: implement purging
