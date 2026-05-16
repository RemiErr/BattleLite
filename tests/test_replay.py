import json
import pytest
from src.python.replay.codec import encode_frames, decode_frames
from src.python.replay import REPLAY_FORMAT_VERSION


# --- codec 單元測試 ---

def test_encode_decode_roundtrip():
    frames = [[0, 64, 0, 32], [0, 0, 8, 0], [16, 64, 64, 0]]
    assert decode_frames(encode_frames(frames)) == frames


def test_encode_empty_frames():
    encoded = encode_frames([])
    assert isinstance(encoded, str)
    assert decode_frames(encoded) == []


def test_encode_single_player():
    frames = [[42]] * 10
    assert decode_frames(encode_frames(frames)) == frames


def test_encode_result_is_base64_str():
    import base64
    encoded = encode_frames([[0, 64]] * 5)
    assert isinstance(encoded, str)
    base64.b64decode(encoded)  # 不應拋出


def test_encode_reduces_size_vs_json():
    frames = [[0, 64, 0, 0]] * 1000
    json_size = len(json.dumps(frames))
    encoded_size = len(encode_frames(frames))
    assert encoded_size < json_size


def test_encode_four_player_roundtrip():
    import random
    random.seed(0)
    frames = [[random.randint(0, 127) for _ in range(4)] for _ in range(500)]
    assert decode_frames(encode_frames(frames)) == frames


# --- writer / reader end-to-end ---

@pytest.fixture
def tmp_replay_dir(monkeypatch, tmp_path):
    import src.python.replay as rmod
    import src.python.replay.writer as wmod
    monkeypatch.setattr(rmod, "get_replay_dir", lambda: str(tmp_path))
    monkeypatch.setattr(wmod, "get_replay_dir", lambda: str(tmp_path))
    return tmp_path


def test_writer_creates_v2_file(tmp_replay_dir):
    from src.python.replay.writer import ReplayWriter
    writer = ReplayWriter({
        "timestamp": "2026-05-17T00:00:00",
        "match_id": "m1", "room_code": "ABCD",
        "room_type": "custom", "num_players": 2,
        "seed": 1, "players": [],
    })
    writer.append_frame([0, 64])
    writer.append_frame([32, 0])
    path = writer.finalize(winner=0)
    with open(path) as f:
        data = json.load(f)
    assert data["version"] == REPLAY_FORMAT_VERSION
    assert isinstance(data["frames"], str)


def test_reader_v2(tmp_replay_dir):
    from src.python.replay.writer import ReplayWriter
    from src.python.replay.reader import ReplayReader
    original = [[0, 64], [32, 8], [0, 0]]
    writer = ReplayWriter({
        "timestamp": "2026-05-17T00:00:00",
        "match_id": "m2", "room_code": "XYZW",
        "room_type": "custom", "num_players": 2,
        "seed": 2, "players": [],
    })
    for f in original:
        writer.append_frame(f)
    path = writer.finalize(winner=1)
    reader = ReplayReader(path)
    assert reader.total_frames == 3
    recovered = []
    while not reader.is_done():
        recovered.append(reader.next_inputs())
    assert recovered == original


def test_reader_v1_legacy(tmp_path):
    from src.python.replay.reader import ReplayReader
    frames = [[0, 64], [32, 8]]
    data = {"version": 1, "frames": frames, "total_frames": 2}
    path = str(tmp_path / "legacy.json")
    with open(path, "w") as f:
        json.dump(data, f)
    reader = ReplayReader(path)
    assert reader.next_inputs() == [0, 64]
    assert reader.next_inputs() == [32, 8]
    assert reader.is_done()


def test_reader_returns_none_when_exhausted(tmp_replay_dir):
    from src.python.replay.writer import ReplayWriter
    from src.python.replay.reader import ReplayReader
    writer = ReplayWriter({
        "timestamp": "2026-05-17T00:00:00",
        "match_id": "m3", "room_code": "ZZZ1",
        "room_type": "custom", "num_players": 1,
        "seed": 3, "players": [],
    })
    writer.append_frame([0])
    path = writer.finalize(winner=0)
    reader = ReplayReader(path)
    reader.next_inputs()
    assert reader.is_done()
    assert reader.next_inputs() is None
