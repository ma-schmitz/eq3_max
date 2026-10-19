"""Test doubles for the protocol layer."""

from __future__ import annotations

import asyncio
from collections.abc import Callable


class FakeClock:
    def __init__(self, t: float = 1000.0) -> None:
        self.t = t

    def __call__(self) -> float:
        return self.t


async def until(cond: Callable[[], bool], timeout: float = 2.0) -> None:
    loop = asyncio.get_running_loop()
    end = loop.time() + timeout
    while not cond():
        if loop.time() > end:
            raise AssertionError("condition not reached")
        await asyncio.sleep(0.001)


def line(counter: int, flags: int, msg_type: int, src: int, dst: int, group: int,
         payload_hex: str, rssi: str | None = "3F") -> str:
    body = f"{counter:02X}{flags:02X}{msg_type:02X}{src:06X}{dst:06X}{group:02X}{payload_hex}"
    out = f"Z{len(body) // 2:02X}{body}"
    return out + (rssi or "")


class _Writer:
    def __init__(self, cul: FakeCul, reader: asyncio.StreamReader) -> None:
        self._cul = cul
        self._reader = reader
        self._closed = False
        self.lines: list[str] = []

    def write(self, data: bytes) -> None:
        if self._closed:
            raise ConnectionError("closed")
        if self._cul.fail_writes:
            raise OSError("write failed")
        for part in data.decode().split("\n"):
            if not part:
                continue
            self.lines.append(part)
            if part == "V" and self._cul.answer_version:
                asyncio.get_running_loop().call_soon(self._cul.feed, self._cul.version)

    async def drain(self) -> None:
        return None

    def close(self) -> None:
        if not self._closed:
            self._closed = True
            self._reader.feed_eof()

    async def wait_closed(self) -> None:
        return None

    def is_closing(self) -> bool:
        return self._closed


class FakeCul:
    """Simulates a nanoCUL on a serial line."""

    def __init__(self, version: str = "V 1.66 nanoCUL868") -> None:
        self.version = version
        self.opened = 0
        self.fail_open = False
        self.fail_writes = False
        self.answer_version = True
        self.reader: asyncio.StreamReader | None = None
        self.writer: _Writer | None = None
        self.all_written: list[str] = []

    async def open(self, port: str):
        if self.fail_open:
            raise OSError(f"cannot open {port}")
        self.opened += 1
        if self.writer is not None:
            self.all_written.extend(self.writer.lines)
        self.reader = asyncio.StreamReader()
        self.writer = _Writer(self, self.reader)
        return self.reader, self.writer

    def feed(self, text: str) -> None:
        assert self.reader is not None
        self.reader.feed_data((text + "\r\n").encode())

    def unplug(self) -> None:
        assert self.writer is not None
        self.writer.close()

    @property
    def written(self) -> list[str]:
        return [] if self.writer is None else self.writer.lines
