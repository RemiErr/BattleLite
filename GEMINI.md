# BattleLite - AI Instruction Manual

You are an expert software engineer assistant for the **BattleLite** project. This project is a 2D side-scrolling brawler inspired by *Little Fighter 2 (LF2)*, featuring 4-player P2P multiplayer with Rollback Netcode.

## 🎯 Primary Directive
**Always strictly adhere to the rules and technical specifications defined in `DEVELOPMENT_STANDARDS.md` and `ARCHITECTURE.md`.** These are the Single Sources of Truth for the project. Before starting any task, consult `AI_HANDOVER.md` for the latest project status and environmental constraints.

## 🛠 Tech Stack
- **Languages**: Python 3.12, Rust (Latest stable).
- **Frontend/Rendering**: Python (Pygame).
- **UI/Launcher**: CustomTkinter.
- **Core Logic/Networking**: Rust (GGRS 0.11.1, PyO3, Maturin).
- **Communication**: FastAPI/WebSockets (Signaling), UDP (P2P Rollback).
- **Security**: ChaCha20-Poly1305 (Secure Session Handoff).

## 🔑 Architectural Principles
1. **Brain vs. Skin**: Rust is the "Brain" (deterministic simulation, physics, state). Python is the "Skin" (rendering, animation, sound, UI).
2. **Determinism**: 
    - **NO FLOATS**: Use fixed-point arithmetic (integers scaled by 1000) for all game state logic.
    - **Seed-based PRNG**: Only use the provided deterministic random generator in Rust.
3. **2.5D Coordinate System**:
    - **X**: Horizontal position.
    - **Y**: Depth (affects Z-order/rendering layer).
    - **Z**: Height (Vertical position/Jumping).
4. **Rollback Ready**: The Rust `GameState` must be serializable/clonable for GGRS snapshots.

## ⚠️ Operational Constraints
1. **OS Binary Mismatch**: Rust binaries (`.so` vs `.pyd`) are platform-specific. Compile locally for the target OS (Windows vs. WSL2).
2. **WSL2 Networking**: Requires `networkingMode=mirrored` in `.wslconfig` for STUN/P2P to function correctly.
3. **Port Recycling**: The Launcher probes STUN then releases the port for the Game Client to reuse in GGRS sessions.

## 🤖 Workflow & Rules
- **TDD Enforcement**: Follow the **Red → Green → Refactor** cycle. 
    - Always start by identifying or writing a failing test in `tests/`.
- **Building Rust Core**: Use Maturin to compile the Rust extension for Python:
    ```bash
    cd src/rust_core && maturin develop && cd ../..
    ```
- **Project Structure**: 
    - `src/rust_core/`: Core logic and GGRS.
    - `src/python/`: Rendering, Assets, and Launcher.
- **Strict Adherence**: Execute only explicit directives. Propose changes for discussion before implementation.

---
*Note: This file is ignored by git to keep the repository clean of AI-specific tool configurations.*
