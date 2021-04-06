import asyncio
import inspect
import typing

import discord
from discord.ext import tasks

from source import utilities, shared

log = utilities.getLog("events")


class Event(set):
    def __init__(self, name="DefaultName"):
        super(Event, self).__init__()
        self.name = name

    async def trigger(self, *args, **kwargs):
        for f in self:
            log.debug(f"Calling {f.__name__}")
            try:
                if inspect.iscoroutinefunction(f):
                    await f(*args, **kwargs)
                else:
                    await asyncio.to_thread(f, *args, **kwargs)
            except Exception as e:
                log.error(f"Error calling {f.__name__}: {e}")


class PaladinEvents:
    def __init__(self):
        self._queue = asyncio.Queue()
        self.process = False

        self.events = {
            "modAction": Event(name="modAction"),
        }

    def subscribe_to_event(self, function: typing.Callable, event="modAction"):
        """Subscribes to a mod action event"""
        self.events[event].add(function)

    async def add_item(self, item: shared.Action):
        """Add item to queue"""
        log.debug("Adding item to queue")
        await self._queue.put(item)

    async def get_item(self) -> shared.Action:
        """Get item from queue"""
        item = await self._queue.get()
        return item

    async def event_loop(self):
        while self.process:
            await asyncio.sleep(0)
            if not self._queue.empty():
                item = await self.get_item()
                if item.event_type in self.events:
                    await self.events[item.event_type].trigger(item)
