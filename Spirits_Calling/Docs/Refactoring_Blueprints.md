# Blueprint Refactoring Guide

## 1. Logic Separation (MVC Pattern)

Current Blueprints often mix data, logic, and UI. We want to separate them.

| Component | Responsibility | Example |
|-----------|----------------|---------|
| **Data (Model)** | Storing stats, inventory | `BP_CharacterStats` (ActorComp) |
| **Logic (Controller)** | Input handling, Game rules | `BP_PlayerController`, `BP_GameMode` |
| **View (UI/Visuals)** | Widget display, Animation | `WBP_HUD`, `ABP_Character` |

## 2. Common Anti-Patterns & Fixes

### A. The "Event Tick" Monster

**Problem**: Logic running every frame (e.g., checking distance to enemy).
**Fix**: Use **Timers** or **Collision Overlaps**.

- Instead of checking `Distance(Player, Enemy) < 500` every tick...
- Add a large `SphereCollision` (Radius 500) to the Enemy and use `OnComponentBeginOverlap`.

### B. Rigid Casting

**Problem**: `Cast To BP_Player` inside a Door blueprint.
**Fix**: Use **Blueprint Interfaces (BPI)**.

- Create `BPI_Interactable` with function `Interact()`.
- Door implements `Interact`.
- Player simply sends message `Interact` to any actor it hits. No casting needed.

### C. Hard References

**Problem**: `BP_GameMode` exists in your level, but referencing it directly loads *all* its dependencies into memory.
**Fix**: Use **Soft Class References** or **Soft Object References** for assets not immediately needed (like spawning a boss later).

## 3. Action Plan

1. **Screenshot** your most complex Blueprint (e.g., `BP_Player` or `BP_GameManager`).
2. **Share** the screenshot with me.
3. I will write a specific step-by-step refactor guide for that specific Blueprint.
