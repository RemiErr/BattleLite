import json
from src.python.replay.codec import decode_frames


class ReplayReader:
    def __init__(self, path: str):
        with open(path, encoding="utf-8") as f:
            self._data = json.load(f)
        raw = self._data["frames"]
        if isinstance(raw, str):       # v2：Columnar+Zstd+base64 壓縮字串
            self._frames: list[list[int]] = decode_frames(raw)
        else:                          # v1 / 無版本欄位：舊格式 list-of-lists
            self._frames = raw
        self._pos = 0

    @property
    def header(self) -> dict:
        return {k: v for k, v in self._data.items() if k != "frames"}

    @property
    def total_frames(self) -> int:
        return self._data["total_frames"]

    def next_inputs(self) -> list[int] | None:
        if self._pos >= len(self._frames):
            return None
        inp = self._frames[self._pos]
        self._pos += 1
        return inp

    def is_done(self) -> bool:
        return self._pos >= len(self._frames)
