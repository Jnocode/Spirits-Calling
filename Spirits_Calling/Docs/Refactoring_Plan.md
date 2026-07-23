# Refactoring Plan: Spirit Possession Architecture

## Goal

Transform the monolithic `BP_XRPawn` into a modular system supporting **RTS Spirit View** and **First-Person Possession**.

## 1. Class Structure

### A. `BP_SpiritController` (PlayerController)

**Role**: The persistent brain of the player.

- Manages Input Mode (RTS vs VR).
- Handles "Possession" logic (Event Possess / Unpossess).
- Stores Global State (Current Civilization, Mana).

### B. `BP_UnitBase` (Character)

**Role**: The physical body in the world (Minions, Heroes, and the original VR Body).

- **Inheritance**: All summonable units inherit from this.
- **Components**:
  - `CapsuleComponent` (Collision)
  - `SkeletalMesh` (Visuals)
  - `UniMovementComponent` (Custom movement logic)

### C. `BPC_VRMovement` (Actor Component)

**Role**: Encapsulates VR-specific locomotion.

- **Why**: Not all units need VR movement (AI doesn't). Only the *possessed* unit needs it.
- **Functions**:
  - `HandleTwist` (Snap Turn)
  - `HandleTeleport` (Arc Visualizer)
  - `HandleSmoothLocomotion`

## 2. Refactoring Steps (Automated)

1. **Create New Assets**:
    - `BP_SpiritController` (Parent: PlayerController)
    - `BP_UnitBase` (Parent: Character)
    - `BPC_VRMovement` (Parent: ActorComponent)

2. **Add Components**:
    - Add `BPC_VRMovement` to `BP_UnitBase` (Disabled by default, enabled on Possession).

3. **Variable Migration (Manual)**:
    - User moves `MotionController_L` / `_R` logic from `BP_XRPawn` to `BP_UnitBase`.

## 3. Implementation Script (`ScaffoldRefactor.py`)

I will execute a script to create these empty Blueprint Assets automatically.
