import json


class ReplayReader:
    def __init__(self, path: str):
        with open(path, encoding="utf-8") as f:
            self._data = json.load(f)
        self._pos = 0

    @property
    def header(self) -> dict:
        return {k: v for k, v in self._data.items() if k != "frames"}

    @property
    def total_frames(self) -> int:
        return self._data["total_frames"]

    def next_inputs(self) -> list[int] | None:
        if self._pos >= len(self._data["frames"]):
            return None
        inp = self._data["frames"][self._pos]
        self._pos += 1
        return inp

    def is_done(self) -> bool:
        return self._pos >= len(self._data["frames"])
