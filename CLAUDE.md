# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

BattleLite is a 4-player 2D brawler built from scratch with P2P rollback netcode (GGRS) as a core design goal. The architecture splits concerns between two runtimes: **Rust is the Brain, Python is the Skin**.

## Development Setup

```bash
# First-time setup
python3 -m venv venv --without-pip
source venv/bin/activate
curl https://bootstrap.pypa.io/get-pip.py | python3
pip install maturin pygame pytest httpx fastapi uvicorn customtkinter cryptography websockets python-dotenv aiosqlite slowapi msgpack zstandard

# Compile and install Rust core into venv
cd src/rust_core
maturin develop
cd ../..
```

After changing Rust code, re-run `maturin develop` from `src/rust_core/`.

## Commands

```bash
# Run all tests
pytest tests/

# Run a single test file
pytest tests/test_physics.py

# Start the game (offline dev mode)
python src/python/main.py --payload ""

# Start the launcher UI
python src/python/launcher.py

# Start the lobby signaling server
uvicorn src.python.lobby_server.main:app --reload --port 8000
```

## Architecture

### Rust Core (`src/rust_core/src/lib.rs`)
Exposes a PyO3 module (`battlelite_core`) with:
- `Player` — 14 attributes (x, y, z, vx, vy, vz, state, timer, facing_right, hp, mp, character_type, hitstop, shield_hp), all physics coords are `i32` scaled by 1000 (no floats, prevents P2P desync)
- `OfflineSession` — local 4-player simulation for dev/testing
- `GGRSSession` — P2P rollback netcode session using GGRS 0.11
- Both sessions share `perform_tick()` for deterministic physics; both expose `advance()`, `get_player()`, `set_player()`, `current_frame()`
- Player states: IDLE=0, WALK=1, ATTACK=2, HURT=3, SKILL=4, DEAD=5
- Constants: GRAVITY=400, JUMP_IMPULSE=9000, MAX_HP=100000, MAX_MP=50000, MP regen=50/frame

### Python Layer (`src/python/`)
- `main.py` — entry point: parses CLI payload, verifies Ed25519 sig, launches game loop
- `app_root.py` — resolves `PROJECT_ROOT` for both dev and PyInstaller frozen environments
- `game_constants.py` — re-exports Rust state constants and shared numeric literals
- `game/loop.py` — main game loop: reads keyboard input → u8 bitmask → `session.advance()` → renders Rust state
- `game/match_manager.py` — win/loss detection, match lifecycle (round start/end, result submission)
- `game/input_manager.py` — keyboard polling and bitmask assembly
- `renderer.py` — converts Rust 2.5D coords (X: lateral, Y: depth, Z: height) to screen pixels
- `hud.py` — HP/MP bars, player name tags, match status overlay
- `fx_manager.py` — visual effects (hit sparks, screen shake, etc.)
- `sfx_manager.py` — sound effect playback tied to game events
- `session/adapter.py` — unified Python wrapper over `OfflineSession` / `GGRSSession` (normalises differing `advance()` signatures)
- `session/char_config.py` — loads per-character JSON config and calls `set_physics_config` / `set_ability` on the session
- `ai/factory.py` — instantiates AI controllers (FSM, pattern-based) by difficulty level
- `ai/controllers/` — AI controller implementations (FSMAIController, PatternAIController, etc.)
- `ai/goap/`, `ai/fuzzy/` — GOAP planner and fuzzy logic modules used by AI controllers
- `replay/codec.py` — msgpack + zstandard serialisation for replay recording
- `replay/writer.py` / `reader.py` — frame-by-frame replay capture and playback
- `launcher.py` — CustomTkinter UI for nickname, room codes, offline/online mode; handles STUN probe and same-LAN IP resolution
- `launcher_settings.py` — JSON persistence for UI state (`settings.json`)
- `lobby_client.py` — WebSocket client connecting Launcher to lobby
- `crypto_utils.py` — **Deprecated.** Original ChaCha20-Poly1305 session encryption replaced by Ed25519 signing; kept as tombstone only.
- `stun_utils.py` — STUN server probing to detect public IP/port; Python socket is closed after probing, GGRS opens its own socket bound to the same port number
- `debug_manager.py` — debug overlay (frames, rollbacks, sync)
- `assets_manager/` — OOP sprite/animation management per character

### Lobby Server (`src/python/lobby_server/main.py`)
FastAPI + WebSocket signaling server. Manages rooms, collects STUN endpoints, triggers match start. Deployed via Docker (`src/python/lobby_server/Dockerfile`). `LOBBY_SERVER_URL` is set in `.env`.

### Session Handoff Flow
Launcher → (STUN probe) → Lobby → (room full) → Lobby signs `{match_id, seed, host_id}` with Ed25519 private key → sends signed session data via WebSocket to Launcher → Launcher passes plain JSON payload (including `sig`) as CLI arg to `main.py` → `main.py` verifies Ed25519 signature using `config/lobby_pubkey.txt` before initialising `state(0)`.

## Key Constraints

**Determinism (non-negotiable for rollback):** All physics lives in Rust with fixed-point `i32` arithmetic (×1000 scale). No floats, no `std::rand` — use seeded PRNG. Any state that affects gameplay must flow through `perform_tick()`.

**Input format:** 1-byte bitmask `[RIGHT|LEFT|UP|DOWN|JUMP|ATTACK|SKILL]` (bits 0–6). No combo-input system — all abilities are single-button triggered.

**Adding a new character requires changes in 6 places:**
1. `main.py` — add import and register in `_build_char_assets()` dict
2. `launcher.py` — append to `CHAR_NAMES` list
3. `lobby_server/main.py` — append to `CHAR_NAMES` dict
4. `ai/factory.py` — update comment and AI behaviour if needed
5. Rust `ggrs_session.rs` + `offline_session.rs` — increment `(0..5)` to `(0..N)` and recompile
6. New `assets_manager/characters/<name>.py` + `src/assets/char/<name>/` sprite sheet

**Known technical debt:**
- Desync is silently ignored (`advance_frame()` errors are swallowed) — no in-game notification or recovery
- No TURN relay fallback; symmetric NAT peers cannot connect
- AI is driven by the host client; host disconnect freezes all AI players

**WSL2 quirks:**
- Rust compiled in WSL2 produces a Linux `.so` — not usable on Windows native. Every dev device must compile its own `battlelite_core`.
- For STUN/P2P to work on WSL2, use mirror networking mode (`networkingMode=mirrored` in `.wslconfig`).
- Python 3.12 ABI must match the `maturin develop` compilation target across all connected devices.

## Testing

No `pytest.ini` or `pyproject.toml` config — run `pytest tests/` from project root. Tests cover: physics, PyO3 bridge, asset loading, lobby WebSocket protocol, multiplayer session spawning, STUN, renderer transforms, and settings persistence.

Every new feature should start with a failing test (Red → Green → Refactor).

## Docs to Read First

- `AI_HANDOVER.md` — current status, known issues, handover notes
- `DEVELOPMENT_STANDARDS.md` — mandatory technical rules and workflow
- `ARCHITECTURE.md` — design philosophy and data flow diagrams
