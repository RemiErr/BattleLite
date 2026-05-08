import json
import os
from src.python.replay import get_replay_dir


class ReplayWriter:
    def __init__(self, header: dict):
        self._header = header
        self._frames: list[list[int]] = []

    def append_frame(self, inputs: list[int]) -> None:
        self._frames.append(list(inputs))

    def finalize(self, winner: int | None) -> str:
        d = get_replay_dir()
        os.makedirs(d, exist_ok=True)
        ts = self._header["timestamp"].replace(":", "").replace("-", "")[:15]
        fname = f"{ts}_{self._header['room_code']}.json"
        path = os.path.join(d, fname)
        data = {
            **self._header,
            "winner": winner,
            "total_frames": len(self._frames),
            "frames": self._frames,
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
        return path
