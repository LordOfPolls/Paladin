import logging
import traceback
from datetime import datetime, timedelta

import discord.errors
import discord.errors
import pytz
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers import cron
from discord.ext.commands import BucketType
from discord_slash import cog_ext

from source import utilities, dataclass, jsonManager
from source.shared import *

log: logging.Logger = utilities.getLog("Cog::Mute")

del_channel_template = [
    {
        "channel_id": None,
        "delete_after": None,
    }
]


class Mute(commands.Cog):
    """Auto Delete Messages in a specified channel"""

    def __init__(self, bot):
        self.bot: dataclass.Bot = bot

        self.emoji = bot.emoji_list

        self.guild_data = {}

        # i know i could use tasks, however i dont want to use interval scheduling, due to the
        # chance it can fail if not checked second by second
        self.scheduler: AsyncIOScheduler = AsyncIOScheduler()  # the task scheduler

    async def setup(self):
        log.debug("Starting scheduler...")
        self.scheduler.start()
        await self.cache_and_schedule()
        log.debug(f"Started scheduler with {len(self.scheduler.get_jobs())} jobs")

    def cog_unload(self):
        log.debug("Shutting down scheduler")
        self.scheduler.shutdown(wait=False)

    async def cache_and_schedule(self):
        """Caches guild data and schedules auto-un-mutes"""
        all_user_data: dict = await self.bot.db.execute(f"SELECT * FROM paladin.users")
        for user_data in all_user_data:
            await self._schedule_job(user_data)

        # # cache guild data
        # all_guild_data = await self.bot.db.execute(f"SELECT * FROM paladin.guilds")
        # temp = {}
        # for guild_data in all_guild_data:
        #     temp[guild_data["guildID"]] = guild_data
        #
        # self.guild_data = temp.copy()

    async def _schedule_job(self, user_data: dict):
        """Schedules a job based on user_data passed"""
        try:
            job_id = f"{user_data.get('guildID')}|{user_data.get('userID')}"
            run_time: datetime = user_data.get("unmuteTime")

            if run_time is not None and run_time <= datetime.utcnow():
                # bumps events in the past a few seconds into the future
                # to handle events that should have occurred while the bot
                # was offline
                run_time = datetime.utcnow() + timedelta(seconds=10)

            job = self.scheduler.get_job(job_id)

            if run_time is not None:
                # the trigger for an job
                trigger = cron.CronTrigger(
                    year=run_time.year,
                    month=run_time.month,
                    day=run_time.day,
                    hour=run_time.hour,
                    minute=run_time.minute,
                    second=run_time.second,
                    timezone=pytz.utc,
                )

                if job:
                    job.reschedule(trigger=trigger)
                    log.debug(f"Unmute job rescheduled for {run_time.ctime()}")
                else:
                    self.scheduler.add_job(
                        func=self.auto_unmute,
                        kwargs={"user_id": user_data.get("userID"), "guild_id": user_data.get("guildID")},
                        trigger=trigger,
                        id=job_id,
                        name=f"Auto-unmute job for {job_id}",
                    )
                    log.debug(f"Unmute job scheduled for {run_time.ctime()}")
            else:
                # runtime is none, delete the job
                if job:
                    self.scheduler.remove_job(job_id)
                    log.debug(f"Job deleted due to empty run_time {job_id}")
        except Exception as e:
            log.error("Error scheduling job:\n" + "".join(traceback.format_exception(type(e), e, e.__traceback__)))

    async def auto_unmute(self, user_id, guild_id):
        """Called at a set time to automatically unmute a user"""
        try:
            log.debug(f"Running unmute task for {guild_id}/{user_id}")

            # grab db data to check the user is *actually* due for un-muting
            guild: discord.Guild = self.bot.get_guild(int(guild_id))
            user: discord.Member = guild.get_member(int(user_id))

            if not guild or not user:
                return

            user_data: dict = await self.bot.db.execute(
                f"SELECT * FROM paladin.users WHERE guildID = '{guild.id}' AND userID = '{user.id}'", getOne=True
            )
            # check if user is still muted
            if not bool(user_data.get("muted")):
                # user has been unmuted already
                return

            unmute_time = user_data.get("unmuteTime")
            if not unmute_time <= datetime.utcnow():
                # todo: reschedule for correct time
                return

            # actually unmute
            await user.remove_roles(await self.get_mute_role(guild))

            # remove from db
            await self.bot.db.execute(
                f"UPDATE paladin.users SET muted=false, unmuteTime=NULL WHERE guildID = '{guild.id}' AND userID = '{user.id}'"
            )

            me = guild.get_member(self.bot.user.id)
            await self.bot.paladinEvents.add_item(
                Action(
                    actionType=ModActions.mute,
                    moderator=me,
                    guild=guild,
                    user=user,
                    reason=f"AUTOMATIC ACTION: \nMute scheduled to be removed at `{unmute_time.ctime()}` (UTC)",
                )
            )
        except Exception as e:
            log.error("Error un-muting:\n" + "".join(traceback.format_exception(type(e), e, e.__traceback__)))

    async def write_user_to_db(self, user: discord.Member, muted: bool, mute_time: typing.Optional[datetime] = None):
        """Write a users mute status to the database"""
        muted = "true" if muted else "false"  # sql-ify
        mute_time = f"'{mute_time}'" if mute_time else "NULL"  # sql-ify

        await self.bot.db.execute(
            f"INSERT INTO paladin.users (userID, guildID, muted, unmuteTime) VALUES ('{user.id}', '{user.guild.id}', {muted}, {mute_time}) "
            f"ON DUPLICATE KEY UPDATE muted = {muted}, unmuteTime = {mute_time}"
        )
        # todo: eliminate the need for this db call (not strictly necessary but would be cleaner)
        user_data = await self.bot.db.execute(
            f"SELECT * FROM paladin.users WHERE guildID = '{user.guild.id}' and userID = '{user.id}'", getOne=True
        )
        await self._schedule_job(user_data)

    async def get_mute_role(self, guild: discord.Guild) -> typing.Optional[discord.Role]:
        """Gets the mute role for a specified guild"""
        guild_data = await self.bot.db.execute(
            f"SELECT * FROM paladin.guilds WHERE guildID = '{guild.id}'", getOne=True
        )
        if guild_data is None or guild_data.get("muteRoleID") is None:
            return None

        role = guild.get_role(int(guild_data.get("muteRoleID")))
        return role

    # region: commands

    @cog_ext.cog_subcommand(**jsonManager.getDecorator("setrole.mute.user"))
    @commands.max_concurrency(1, BucketType.guild, wait=False)
    @commands.check_any(
        commands.has_permissions(manage_messages=True),
        commands.has_permissions(manage_roles=True),
        commands.has_permissions(mute_members=True),
    )
    async def set_mute_role(self, ctx: SlashContext, role: discord.Role):
        await ctx.defer()

        try:
            await self.bot.db.execute(
                f"INSERT INTO paladin.guilds (guildID, muteRoleID) VALUES ('{ctx.guild_id}', '{role.id}') "
                f"ON DUPLICATE KEY UPDATE muteRoleID = '{role.id}'"
            )
        except Exception as e:
            log.error(f"Error setting mute role: {e}")
            return await ctx.send("Failed to set mute role... please try again later")
        await ctx.send(
            f"Your server's mute role has been set to {role.mention}", allowed_mentions=discord.AllowedMentions.none()
        )

    @cog_ext.cog_subcommand(**jsonManager.getDecorator("add.mute.user"))
    @commands.check_any(
        commands.has_permissions(manage_messages=True),
        commands.has_permissions(manage_roles=True),
        commands.has_permissions(mute_members=True),
    )
    async def mute(self, ctx: SlashContext, user: discord.Member, time: int, unit: int, reason: str = None):
        # scale up time value to match unit (ie minutes/hours/days
        await ctx.defer(hidden=True)
        # search database for muteRole
        role = await self.get_mute_role(ctx.guild)
        if not role:
            return await ctx.send("Sorry, you haven't set a mute role to use", hidden=True)

        # handle time
        if time >= 1:
            if unit == 2:
                time *= 60
            elif unit == 3:
                time *= 1440
            mute_time = datetime.utcnow() + timedelta(minutes=time)
        else:
            # mute forever
            mute_time = None
            time = None

        timefmt = f"for {self.bot.strf_delta(timedelta(minutes=time))}" if time else "forever"

        await user.add_roles(role, reason=f"Mute requested by {ctx.author.name}#{ctx.author.discriminator}")
        await ctx.send(f"Muted {user.mention} {timefmt}", hidden=True, allowed_mentions=discord.AllowedMentions.none())
        await self.bot.paladinEvents.add_item(
            Action(
                actionType=ModActions.mute,
                moderator=ctx.author,
                guild=ctx.guild,
                user=user,
                reason=reason,
            )
        )
        await self.write_user_to_db(user, muted=True, mute_time=mute_time)

    @cog_ext.cog_subcommand(**jsonManager.getDecorator("clear.mute.user"))
    @commands.check_any(
        commands.has_permissions(manage_messages=True),
        commands.has_permissions(manage_roles=True),
        commands.has_permissions(mute_members=True),
    )
    async def unmute(self, ctx: SlashContext, user: discord.Member, reason: str = None):
        # search database for muteRole id
        role = await self.get_mute_role(ctx.guild)
        if not role:
            return await ctx.send("Sorry, you haven't set a mute role to use", hidden=True)

        await user.remove_roles(role)

        await ctx.send(
            f"{user.mention} is no longer muted", hidden=True, allowed_mentions=discord.AllowedMentions.none()
        )
        await self.write_user_to_db(user, muted=False, mute_time=None)

        await self.bot.paladinEvents.add_item(
            Action(
                actionType=ModActions.unmute,
                moderator=ctx.author,
                guild=ctx.guild,
                user=user,
                reason=reason,
            )
        )

    @unmute.error
    @mute.error
    async def mute_error(self, ctx: SlashContext, error):
        me: discord.Member = ctx.guild.get_member(self.bot.user.id)
        perms: discord.Permissions = me.guild_permissions
        if isinstance(error, discord.errors.Forbidden) and perms.manage_roles:
            await ctx.send(
                "I'm too low in the role hierarchy to add that role,\n"
                "please move my role above any roles you want me to add",
                hidden=True,
            )
        elif isinstance(error, commands.CheckFailure):
            await ctx.send(
                "Sorry you are missing permissions. You need one of the following:\n"
                "- `manage_messages`\n- `manage_roles`\n- `mute_members`"
            )
        else:
            await ctx.send("An error occurred executing that command... please try again later", hidden=True)

    @set_mute_role.error
    async def role_error(self, ctx: SlashContext, error):
        if isinstance(error, commands.MaxConcurrencyReached):
            await ctx.send("Hang on, another user in your server is updating your server's settings", hidden=True)
        elif isinstance(error, commands.CheckFailure):
            await ctx.send(
                "Sorry you are missing permissions. You need one of the following:\n"
                "- `manage_messages`\n- `manage_roles`\n- `mute_members`"
            )
        else:
            log.error(error)
            await ctx.send("An error occurred executing that command... please try again later", hidden=True)

    # endregion


def setup(bot):
    """Called when this cog is mounted"""
    bot.add_cog(Mute(bot))
    log.info("Mute mounted")


def teardown(bot):
    """Called when this cog is unmounted"""
    log.warning("Mute un-mounted")
    for handler in log.handlers[:]:
        log.removeHandler(handler)
