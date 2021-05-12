import logging
import re
import traceback
import typing

import discord
from discord.ext import commands
from discord_slash import cog_ext, SlashContext, model
from discord_slash.utils import manage_commands

from source import utilities, dataclass, shared

log: logging.Logger = utilities.getLog("Cog::Config")


class Config(commands.Cog):
    """Configuration commands"""

    def __init__(self, bot):
        self.bot: dataclass.Bot = bot

        self.emoji = bot.emoji_list

    @cog_ext.cog_subcommand(
        base="guild",
        name="get_config",
        description="Show the current config for this server",
        base_default_permission=True,
    )
    async def get_guild_config(self, ctx: SlashContext):
        await ctx.defer()

        guild_data = await self.bot.get_guild_data(ctx.guild_id)

        emb = discord.Embed(title=f"{ctx.guild.name} Configuration", colour=discord.Colour.blurple())

        emb.add_field(name="ID", value=ctx.guild_id, inline=False)
        emb.add_field(name="Owner", value=ctx.guild.owner.mention, inline=False)
        emb.set_thumbnail(url=ctx.guild.icon_url)

        # config data
        mod_roles = []
        if guild_data.moderation_roles:
            for role_id in guild_data.moderation_roles:
                role = ctx.guild.get_role(role_id)
                if role:
                    mod_roles.append(f"{role.mention}")
        if mod_roles:
            emb.add_field(name="Moderation Roles", value="\n".join(mod_roles), inline=False)
        else:
            emb.add_field(name="Moderation Roles", value="None Set")

        mute_role = ctx.guild.get_role(guild_data.role_mute_id)
        emb.add_field(name="Mute Role", value=mute_role.mention if mute_role else "None Set", inline=False)

        action_channel = ctx.guild.get_channel(guild_data.channel_action_log_id)
        emb.add_field(
            name="Action Log Channel", value=action_channel.mention if action_channel else "None Set", inline=False
        )

        mod_channel = ctx.guild.get_channel(guild_data.channel_mod_log_id)
        emb.add_field(name="Mod Log Channel", value=mod_channel.mention if mod_channel else "None Set", inline=False)

        vote_channels = ""
        if guild_data.vote_channel_data:
            for channel_id in guild_data.vote_channel_data:
                vote_channel = ctx.guild.get_channel(channel_id)
                if vote_channel:
                    vote_channels += f" {vote_channel.mention}"
        emb.add_field(name="Vote Channels", value=vote_channels if vote_channels != "" else "None Set", inline=False)

        auto_delete = []
        if guild_data.auto_delete_data:

            for channel_data in guild_data.auto_delete_data:
                channel = ctx.guild.get_channel(int(channel_data.get("channel_id")))
                if channel:
                    auto_delete.append(f"{channel.mention}: `{channel_data.get('delete_after')}` minutes")
        if auto_delete:
            emb.add_field(name="Auto-Delete Channels", value="\n".join(auto_delete), inline=False)
        else:
            emb.add_field(name="Auto-Delete Channels", value="None Set", inline=False)

        emb.add_field(
            name="Block Guild Invites",
            value=self.emoji["checkMark"] if guild_data.block_guild_invites else self.emoji["crossMark"],
            inline=False,
        )
        emb.add_field(
            name="Block Bot Invites",
            value=self.emoji["checkMark"] if guild_data.block_bot_invites else self.emoji["crossMark"],
            inline=False,
        )
        emb.add_field(
            name="Log URLs",
            value=self.emoji["checkMark"] if guild_data.log_urls else self.emoji["crossMark"],
            inline=False,
        )
        emb.add_field(
            name="Log Images",
            value=self.emoji["checkMark"] if guild_data.store_images else self.emoji["crossMark"],
            inline=False,
        )

        if guild_data.block_guild_invites:
            emb.add_field(
                name="Allowed Guild Invites",
                value="\n".join(guild_data.allowed_guild_invites) if guild_data.allowed_guild_invites else "None Set",
                inline=False,
            )

        await ctx.send(embed=emb)

    @cog_ext.cog_subcommand(
        base="guild",
        name="enable_commands",
        description="Enable commands for a specified role",
        options=[
            manage_commands.create_option(name="role", description="The role in question", option_type=8, required=True)
        ],
        base_default_permission=True,
    )
    @commands.cooldown(1, 60, commands.BucketType.guild)
    @commands.has_permissions(administrator=True)
    async def enable_commands(self, ctx: SlashContext, role: discord.Role):
        await ctx.defer()
        guild_data = await self.bot.get_guild_data(ctx.guild_id)
        if guild_data:
            if role.id in guild_data.moderation_roles:
                return await ctx.send(
                    "Commands are already enabled for that role, if they aren't in Discord, try restarting Discord"
                )

            guild_data.moderation_roles.append(role.id)
            await self.bot.redis.set(guild_data.key, guild_data.to_json())
            await self.bot.add_permissions_to_commands()
            await self.sync_all_commands(ctx.guild_id)

            await ctx.send(
                f"Commands are now enabled for {role.mention}\n**Note:**It may take a few minutes for discord to show this change",
                allowed_mentions=discord.AllowedMentions.none(),
            )

    @cog_ext.cog_subcommand(
        base="guild",
        name="disable_commands",
        description="Disable commands for a specified role",
        options=[
            manage_commands.create_option(name="role", description="The role in question", option_type=8, required=True)
        ],
        base_default_permission=True,
    )
    @commands.cooldown(1, 60, commands.BucketType.guild)
    @commands.has_permissions(administrator=True)
    async def disable_commands(self, ctx: SlashContext, role: discord.Role):
        await ctx.defer()
        guild_data = await self.bot.get_guild_data(ctx.guild_id)
        if guild_data:
            if role.id not in guild_data.moderation_roles:
                return await ctx.send(
                    "Commands are already disabled for that role, if they aren't in Discord, try restarting Discord"
                )
            guild_data.moderation_roles.remove(role.id)
            await self.bot.redis.set(guild_data.key, guild_data.to_json())
            await self.bot.add_permissions_to_commands()
            await self.sync_all_commands(ctx.guild_id)

            await ctx.send(
                f"Commands are now disabled for {role.mention}\n**Note:**It may take a few minutes for discord to show this change",
                allowed_mentions=discord.AllowedMentions.none(),
            )

    @enable_commands.error
    @disable_commands.error
    async def on_error(self, ctx, error):
        if isinstance(error, commands.CheckFailure):
            await ctx.send("You need administrator permissions to use this command", hidden=True)
        elif isinstance(error, commands.CommandOnCooldown):
            await ctx.send("Sorry, you can only use this command once per minute", hidden=True)
        else:
            log.error("".join(traceback.format_exception(type(error), error, error.__traceback__)))
            await ctx.send("An error occurred trying to run this command, it has been logged. Please try again later")

    async def sync_all_commands(self, guild_id: int):
        """
        gutted version of slash.sync_all_commands to only modify one guild for permissions

        not efficient, but it works, and i didnt want to re-engineer it completely,
        seeing as itll likely be added to the lib eventually
        """
        permissions_map = {}
        cmds = await self.bot.slash.to_dict()
        cmds_formatted = {None: cmds["global"]}
        for guild in cmds["guild"]:
            cmds_formatted[guild] = cmds["guild"][guild]

        for scope in cmds_formatted:
            permissions = {}
            new_cmds = cmds_formatted[scope]
            existing_cmds = await self.bot.slash.req.get_all_commands(guild_id=scope)
            for command in new_cmds:
                cmd_name = command["name"]
                permissions[cmd_name] = command.pop("permissions")

            id_name_map = {}
            for cmd in existing_cmds:
                id_name_map[cmd["name"]] = cmd["id"]

            for cmd_name in permissions:
                cmd_permissions = permissions[cmd_name]
                cmd_id = id_name_map[cmd_name]
                for applicable_guild in cmd_permissions:
                    if applicable_guild not in permissions_map:
                        permissions_map[applicable_guild] = []
                    permission = {
                        "id": cmd_id,
                        "guild_id": applicable_guild,
                        "permissions": cmd_permissions[applicable_guild],
                    }
                    permissions_map[applicable_guild].append(permission)

        existing_perms = await self.bot.slash.req.get_all_guild_commands_permissions(guild_id)
        new_perms = permissions_map[guild_id]
        changed = False
        if len(existing_perms) != len(new_perms):
            changed = True
        else:
            existing_perms_model = {}
            for existing_perm in existing_perms:
                existing_perms_model[existing_perm["id"]] = model.GuildPermissionsData(**existing_perm)
            for new_perm in new_perms:
                if new_perm["id"] not in existing_perms_model:
                    changed = True
                    break
                if existing_perms_model[new_perm["id"]] != model.GuildPermissionsData(**new_perm):
                    changed = True
                    break

        if changed:
            log.debug(f"Detected permissions changes on {guild_id}, updating them")
            await self.bot.slash.req.update_guild_commands_permissions(guild_id, new_perms)
        else:
            log.debug(f"Detected no permissions changes on {guild_id}, skipping")


def setup(bot):
    """Called when this cog is mounted"""
    bot.add_cog(Config(bot))
    log.info("Config mounted")


def teardown(bot):
    """Called when this cog is unmounted"""
    log.warning("Config un-mounted")
    for handler in log.handlers[:]:
        log.removeHandler(handler)
