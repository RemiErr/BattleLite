# BattleLite Project Handover Document (AI to AI)

## 📌 Project Overview
BattleLite is a 2D side-scrolling brawler (LF2 style) using **Python (Pygame)** for rendering and **Rust (GGRS)** for P2P Rollback Netcode.

## 🛠 Tech Stack
- **Languages**: Python 3.12, Rust (Latest stable).
- **Core Libraries**: 
    - `PyO3` / `Maturin`: Python-Rust Bridge.
    - `GGRS 0.11.1`: P2P Rollback Engine.
    - `ChaCha20-Poly1305`: Secure handoff encryption.
    - `FastAPI` / `WebSockets`: Signaling Lobby Server.
    - `CustomTkinter`: Modern Launcher UI.
    - `Pygame`: Game Rendering.

## 📜 Development History
1. **Stage 1**: Established Rust-Python bridge, validated basic movement.
2. **Stage 2**: Implemented 2.5D physics (Z-axis gravity), character state machine (IDLE/WALK/ATTACK/HURT/SKILL), and hitbox/hurtbox logic.
3. **Stage 3 (Current)**: Standardized networking. Implemented Signaling Lobby, Secure Launcher, and OOP Assets Manager.

## 🚧 Current Status
- **Composition Pattern Refactor**: Completed. `battlelite_core` now provides `OfflineSession` (no network) and `GGRSSession` (P2P).
- **Secure Handoff**: `launcher.py` successfully launches `main.py` with an encrypted payload containing session info.
- **Next Task**: Fine-tuning P2P connectivity between different OS environments (WSL2 vs. Windows).

## ⚠️ Known Issues & Constraints
1. **OS Binary Mismatch**: Rust code compiled in WSL2 (`.so`) will **NOT** run in native Windows (`.pyd`). Multi-device testing requires local compilation on each platform.
2. **Python Version Sensitivity**: Must use **Python 3.12** on all devices to match the `battlelite_core` ABI.
3. **WSL2 Networking**: Requires **Mirror Mode** (`networkingMode=mirrored` in `.wslconfig`) to allow STUN to correctly probe the host's public IP.
4. **Environment Isolation**: AI agents may struggle to call `pytest` in the venv; users should run tests manually and report back.

## 💡 Crucial Architectural Decisions
- **Determinism**: NO floats in Rust core. Use fixed-point (integers scaled by 1000).
- **Ownership**: Rust is the "Brain" (simulates everything). Python is the "Skin" (renders sprites).
- **Port Recycling (Method A)**: Launcher probes STUN then closes socket immediately to let Rust core reuse the same port for GGRS.
- **LOBBY_SERVER_URL**: Managed via `.env` file for easy cloud/local switching.

---
*Note: Read `DEVELOPMENT_STANDARDS.md` before writing code.*
