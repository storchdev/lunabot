import asyncio
import time
from typing import TYPE_CHECKING
from datetime import datetime

if TYPE_CHECKING:
    from .player import Player


class Powerup:
    def __init__(self, id, start: float, end: float):
        self.id = id
        self.start = start
        self.end = end
        self.n = None
        self.name = None
        self.log_name = None

    def __eq__(self, other):
        return self.id == other.id

    def apply(self, _: "Player"):
        raise NotImplementedError()


class Multiplier(Powerup):
    def __init__(self, n, start, end, *, id=None):
        super().__init__(id, start, end)
        self.n = n
        self.name = "Multiplier"
        self.log_name = "multi_powerup"

    async def _after_apply(self, player: "Player"):
        await asyncio.sleep(self.end - time.time())
        player.multi //= self.n
        player.powerups.remove(self)

    def apply(self, player: "Player"):
        player.powerups.append(self)
        self.multi *= self.n
        player.bot.loop.create_task(self._after_apply(player))


class CooldownReducer(Powerup):
    def __init__(self, cd, start, end, *, id=None):
        super().__init__(id, start, end)
        self.n = cd
        self.name = "Cooldown Reducer"
        self.log_name = "cd_powerup"

    async def _after_apply(self, player: "Player"):
        await asyncio.sleep(self.end - time.time())
        player.cds.remove(self.n)
        player.powerups.remove(self)

    def apply(self, player: "Player"):
        player.powerups.append(self)
        player.cds.append(self.n)
        player.bot.loop.create_task(self._after_apply(player))
