# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

BattleLite is a 2D side-scrolling brawler inspired by Little Fighter 2, supporting 4-player multiplayer via P2P rollback netcode (GGRS). The architecture splits concerns between two runtimes: **Rust is the Brain, Python is the Skin**.

## Development Setup

```bash
# First-time setup
python3 -m venv venv --without-pip
source venv/bin/activate
curl https://bootstrap.pypa.io/get-pip.py | python3
pip install maturin pygame pytest httpx fastapi uvicorn customtkinter cryptography websockets python-dotenv

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
- `Player` — 11 attributes (x, y, z, vx, vy, vz, state, timer, facing_right, hp, mp), all physics coords are `i32` scaled by 1000 (no floats, prevents P2P desync)
- `OfflineSession` — local 4-player simulation for dev/testing
- `GGRSSession` — P2P rollback netcode session using GGRS 0.11
- Both sessions share `perform_tick()` for deterministic physics; both expose `advance()`, `get_player()`, `set_player()`, `current_frame()`
- Player states: IDLE=0, WALK=1, ATTACK=2, HURT=3, SKILL=4
- Constants: GRAVITY=400, JUMP_IMPULSE=9000, MAX_MP=50000, MP regen=50/frame

### Python Layer (`src/python/`)
- `main.py` — game loop: reads keyboard input → u8 bitmask → `session.advance(mask)` → renders Rust state
- `renderer.py` — converts Rust 2.5D coords (X: lateral, Y: depth, Z: height) to screen pixels
- `launcher.py` — CustomTkinter UI for nickname, room codes, offline/online mode
- `launcher_settings.py` — JSON persistence for UI state (`settings.json`)
- `lobby_client.py` — WebSocket client connecting Launcher to lobby
- `crypto_utils.py` — ChaCha20-Poly1305 encryption/decryption for session handoff payloads
- `stun_utils.py` — STUN server probing to detect public IP/port (same port later reused by GGRS)
- `debug_manager.py` — debug overlay (frames, rollbacks, sync)
- `assets_manager/` — OOP sprite/animation management per character

### Lobby Server (`src/python/lobby_server/main.py`)
FastAPI + WebSocket signaling server. Manages rooms, collects STUN endpoints, triggers match start. Deployed via Docker (`src/python/lobby_server/Dockerfile`). `LOBBY_SERVER_URL` is set in `.env`.

### Session Handoff Flow
Launcher → (STUN probe) → Lobby → (room full) → Launcher encrypts session data (IP, port, seed) with ChaCha20-Poly1305 → passes encrypted payload as CLI arg to `main.py` → Rust decrypts via `decrypt_payload()`.

## Key Constraints

**Determinism (non-negotiable for rollback):** All physics lives in Rust with fixed-point `i32` arithmetic (×1000 scale). No floats, no `std::rand` — use seeded PRNG. Any state that affects gameplay must flow through `perform_tick()`.

**Input format:** 1-byte bitmask `[RIGHT|LEFT|UP|DOWN|JUMP|ATTACK|SKILL]` (bits 0–6).

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
