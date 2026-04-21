# Development Standards - BattleLite

**CRITICAL: All AI contributors MUST read `AI_HANDOVER.md` before analyzing the codebase or suggesting changes.** This document contains essential information regarding environment constraints (WSL2 quirks), cross-platform binary compatibility, and project history.

## 1. Technical Stack
- **Game Engine**: Pygame (for rendering, audio, and basic input).
- **Core Logic**: Rust (compiled as a Python extension via PyO3).
- **Networking**: GGRS (P2P Rollback Netcode).
- **Build System**: Maturin (for Rust/Python integration).

## 2. Core Architecture
- **Launcher**: Handles matchmaking and room setup. Passes session data (IPs, Seed) to the Game Client via command-line arguments.
- **Game Client**: A standalone process that initializes the P2P session and starts the fight.

## 3. Game Logic Rules (LF2 Style)
- **Axes**: The game uses X (Left/Right), Y (Up/Down - Depth), and Z (Vertical - Height/Jumping).
- **Physics**: All calculations must happen in the Rust core.
- **Determinism**: 
    - NO `float` types allowed in core logic. Use `i32` or `i64` for fixed-point calculations.
    - NO random functions from the standard library. Use a seed-based PRNG provided during session initialization.

## 4. P2P Rollback Protocol
- **Synchronization**: Only "Inputs" (bitmasks) are exchanged.
- **State Management**: Rust core must implement `SaveGameState` and `LoadGameState` for GGRS snapshots.
- **Input Delay**: Default to 2 frames of artificial delay to minimize visual rollbacks.

## 5. Development Workflow (TDD First)
- **Red**: Every new feature or fix must begin with a failing test case in `tests/`.
- **Green**: Implement the minimal, idiomatic code to make the test pass.
- **Refactor**: Clean up the implementation while ensuring the test suite remains green.
- **Test Preservation**: All test results and execution logs must be preserved for validation.

## 6. Project Structure
- `src/rust_core/`: Rust implementation of game logic, GGRS integration, and PyO3 bindings.
- `src/python/`: Pygame rendering, event loop, and Launcher.
- `docs/`: Design documents and protocol specifications.
- `tests/`: Integrated tests for Python and Rust core modules.
- `assets/`: Character sprites, UI elements, and audio files.

## 7. Sprite Asset Standards (LF2 Style)
- **Format**: `.png` with Alpha channel (transparency).
- **Organization**: One directory per character (e.g., `assets/characters/knight/`).
- **Storage**: Prefer single-row Sprite Sheets for each animation state (e.g., `idle.png`).
- **Naming**: `[action]_[frame_count].png` (e.g., `walk_6.png`).
- **Configuration**: Each character folder must contain a `config.json` defining hitbox offsets and animation speed per state.
