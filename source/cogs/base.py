import io
import logging
import textwrap
import traceback
from contextlib import redirect_stdout

import aiohttp
import discord
from discord.ext import commands
from discord_slash import cog_ext

from source import dataclass, utilities

log: logging.Logger = utilities.getLog("Cog::base")


class Base(commands.Cog):
    """Configuration commands"""

    def __init__(self, bot: dataclass.Bot):
        self.bot = bot

        self.slash = bot.slash

        self.emoji = "🚩"

    @commands.command(name="Shutdown", brief="Shuts down the bot")
    @commands.is_owner()
    async def cmdShutdown(self, ctx: commands.Context):
        if await self.bot.is_owner(ctx.author):
            log.warning("Shutdown called")
            await ctx.send("Shutting down 🌙")
            await self.bot.close()

    @commands.command(name="setname", brief="Renames the bot")
    @commands.is_owner()
    async def cmdSetName(self, ctx: commands.Context, name: str):
        if await self.bot.is_owner(ctx.author):
            await self.bot.user.edit(username=name)
            await ctx.send(f"Set name to {name}")

    @commands.command(name="setAvatar", brief="Sets the bots avatar")
    @commands.is_owner()
    async def cmdSetAvatar(self, ctx: commands.Context):
        if await self.bot.is_owner(ctx.author):
            if ctx.message.attachments:
                photo = ctx.message.attachments[0].url
                async with aiohttp.ClientSession() as session:
                    async with session.get(photo) as r:
                        if r.status == 200:
                            data = await r.read()
                            try:
                                await self.bot.user.edit(avatar=data)
                                return await ctx.send("Set avatar, how do i look?")
                            except discord.HTTPException:
                                await ctx.send("Unable to set avatar")
                                return
            await ctx.send("I cant read that")

    def get_syntax_error(self, e):
        if e.text is None:
            return "```py\n{0.__class__.__name__}: {0}\n```".format(e)
        return "```py\n{0.text}{1:>{0.offset}}\n{2}: {0}```".format(e, "^", type(e).__name__)

    @commands.command(name="exec", brief="Execute some code")
    @commands.is_owner()
    async def _exec(self, ctx: commands.Context, *, body: str):
        env = {
            "bot": self.bot,
            "slash": self.bot.slash,
            "ctx": ctx,
            "channel": ctx.channel,
            "author": ctx.author,
            "server": ctx.guild,
            "guild": ctx.guild,
            "message": ctx.message,
        }
        env.update(globals())

        if body.startswith("```") and body.endswith("```"):
            body = "\n".join(body.split("\n")[1:-1])
        else:
            body = body.strip("` \n")

        stdout = io.StringIO()

        to_compile = "async def func():\n%s" % textwrap.indent(body, "  ")
        async with ctx.channel.typing():
            try:
                exec(to_compile, env)
            except SyntaxError as e:
                return await ctx.send(self.get_syntax_error(e))

        func = env["func"]
        try:
            with redirect_stdout(stdout):
                ret = await func()
        except Exception as e:
            value = stdout.getvalue()
            await ctx.send("```py\n{}{}\n```".format(value, traceback.format_exc()))
        else:
            value = stdout.getvalue()
            try:
                await ctx.message.add_reaction("\u2705")
            except:
                pass

            if ret is None:
                if value:
                    try:
                        await ctx.message.reply("```py\n%s\n```" % value)
                    except:
                        await ctx.send("```py\n%s\n```" % value)
            else:
                self._last_result = ret
                try:
                    await ctx.message.reply("```py\n%s%s\n```" % (value, ret))
                except:
                    await ctx.send("```py\n%s%s\n```" % (value, ret))

    @cog_ext.cog_slash(name="invite", description="Get an invite link for the bot", default_permission=True)
    async def _invite(self, ctx):
        await ctx.send(
            f"https://discord.com/oauth2/authorize?client_id={self.bot.user.id}"
            f"&permissions=8&scope=applications.commands%20bot"
        )


def setup(bot):
    """Called when this cog is mounted"""
    bot.add_cog(Base(bot))
    log.info("Base mounted")


def teardown(bot):
    """Called when this cog is unmounted"""
    log.warning("Base un-mounted")
    for handler in log.handlers[:]:
        log.removeHandler(handler)
