import base64
import msgpack
import zstandard


def encode_frames(frames: list[list[int]]) -> str:
    """list[list[int]] → Columnar → bytes() → MessagePack → Zstd(level=3) → base64 str"""
    if not frames:
        packed: bytes = msgpack.packb([0, 0], use_bin_type=True)  # type: ignore[assignment]
        return base64.b64encode(zstandard.compress(packed, level=3)).decode()
    num_frames  = len(frames)
    num_players = len(frames[0])
    columns = [bytes(frames[f][p] for f in range(num_frames)) for p in range(num_players)]
    packed = msgpack.packb([num_frames, num_players, *columns], use_bin_type=True)  # type: ignore[assignment]
    return base64.b64encode(zstandard.compress(packed, level=3)).decode()


def decode_frames(encoded: str) -> list[list[int]]:
    """base64 str → Zstd decompress → MessagePack → de-Columnar → list[list[int]]"""
    data = msgpack.unpackb(zstandard.decompress(base64.b64decode(encoded)), raw=False)
    num_frames, num_players, *columns = data
    return [[columns[p][f] for p in range(num_players)] for f in range(num_frames)]
