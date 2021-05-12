import logging
import re
import typing

import discord
from discord.ext import commands
from discord_slash import cog_ext, SlashContext
from discord_slash.utils import manage_commands

from source import utilities, dataclass, shared

log: logging.Logger = utilities.getLog("Cog::LinkDetect")


class LinkDetection(commands.Cog):
    """Configuration commands"""

    def __init__(self, bot):
        self.bot: dataclass.Bot = bot

        self.emoji = bot.emoji_list

    @cog_ext.cog_subcommand(
        base="guild",
        name="get_config",
        description="Show the current config for this server",
        guild_ids=[701347683591389185],
    )
    async def get_guild_config(self, ctx: SlashContext):
        await ctx.defer()

        guild_data = await self.bot.get_guild_data(ctx.guild_id)

        emb = discord.Embed(title=f"{ctx.guild.name} Configuration", colour=discord.Colour.blurple())

        emb.add_field(name="ID", value=ctx.guild_id, inline=False)
        emb.add_field(name="Owner", value=ctx.guild.owner.mention, inline=False)
        emb.set_thumbnail(url=ctx.guild.icon_url)

        # config data

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

        if guild_data.block_guild_invites:
            emb.add_field(
                name="Allowed Guild Invites",
                value="\n".join(guild_data.allowed_guild_invites) if guild_data.allowed_guild_invites else "None Set",
                inline=False,
            )

        await ctx.send(embed=emb)


def setup(bot):
    """Called when this cog is mounted"""
    bot.add_cog(LinkDetection(bot))
    log.info("LinkDetection mounted")


def teardown(bot):
    """Called when this cog is unmounted"""
    log.warning("LinkDetection un-mounted")
    for handler in log.handlers[:]:
        log.removeHandler(handler)
