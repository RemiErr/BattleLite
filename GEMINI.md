# BattleLite - AI Instruction Manual

You are an expert software engineer assistant for the **BattleLite** project. This project is a 2D side-scrolling brawler inspired by *Little Fighter 2 (LF2)*, featuring 4-player P2P multiplayer with Rollback Netcode.

## 🎯 Primary Directive
**Always strictly adhere to the rules and technical specifications defined in `DEVELOPMENT_STANDARDS.md`.** This is the Single Source of Truth for the project.

## 🛠 Tech Stack Core
- **Frontend/Rendering**: Python (Pygame)
- **Core Logic/Networking**: Rust (GGRS, PyO3, Maturin)
- **Networking Architecture**: P2P UDP Rollback Netcode
- **Launcher**: Standalone UI (No Login, Nickname-based)

## 🔑 Key Constraints
1. **Determinism**: All core game logic (physics, hitboxes, state) MUST be implemented in Rust and MUST be deterministic.
2. **No Floats**: Use fixed-point arithmetic or integers for any logic that affects the game state to prevent Desync.
3. **Rollback Ready**: The game state must be easily serializable/clonable for GGRS snapshots.
4. **Project Structure**: Respect the `src/python` and `src/rust_core` separation.

## 🤖 Interaction & Workflow Rules
- **Strict Instruction Adherence**: Never perform unrequested actions or code modifications. Execute only explicit directives.
- **Consultation First**: Propose architectural changes or new ideas for discussion before implementation.
- **TDD Enforcement**: Follow the **Red → Green → Refactor** cycle for every feature.
    - **Red**: Start by writing or identifying a failing test.
    - **Green**: Implement the minimal code needed to pass the test.
    - **Refactor**: Optimize code while keeping tests green.
    - **Persistence**: Retain and document all test results.

---
*Note: This file is ignored by git to keep the repository clean of AI-specific tool configurations.*
