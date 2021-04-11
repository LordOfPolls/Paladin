import asyncio
import inspect
import traceback
import typing

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
                log.error(
                    "Ignoring exception in {}: {}".format(
                        f.__name__,
                        "".join(traceback.format_exception(type(e), e, e.__traceback__)),
                    )
                )


class PaladinEvents:
    def __init__(self):
        self._queue = asyncio.Queue()
        self.process = False

        self.events = {
            "modAction": Event(name="modAction"),
        }

        self.task = None

    def subscribe_to_event(self, function: typing.Callable, event="modAction"):
        """Subscribes to a mod action event"""
        if event not in self.events:
            self.events[event] = Event(name=event)
        self.events[event].add(function)

    async def add_item(self, item: typing.Union[shared.Action, str]):
        """Add item to queue"""
        log.debug("Adding item to queue")
        await self._queue.put(item)

        # if event loop isn't running, start it
        if self.task is None or self.task.done():
            self.task = asyncio.create_task(self.event_loop())

    async def get_item(self) -> typing.Union[shared.Action, str]:
        """Get item from queue"""
        item = await self._queue.get()
        return item

    async def event_loop(self):
        """The event loop for paladin events
        Checks for pending events, calls their corresponding event system,"""
        while self.process:
            await asyncio.sleep(0)
            if not self._queue.empty():
                item = await self.get_item()

                # handle both Action objects, and str
                if isinstance(item, shared.Action):
                    if item.event_type in self.events:
                        await self.events[item.event_type].trigger(item)
                if isinstance(item, str):
                    if item in self.events:
                        await self.events[item].trigger()
