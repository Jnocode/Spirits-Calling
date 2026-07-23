# Logic Implementation Guide: RTS Camera & Possession

Since this is a Blueprint-only project, I cannot wire the nodes for you.
Please follow these steps to make the game Playable (MVP).

## 1. Implement RTS Camera (`BP_SpiritPawn`)

**Location**: `/Game/Core/Characters/BP_SpiritPawn`
**Event Graph**:

1. **Event BeginPlay**:
    * `GetPlayerController` -> `SetShowMouseCursor(True)`
    * `GetPlayerController` -> `SetInputModeGameAndUI`

2. **Input Action IA_RTS_Move**:
    * **Triggered**:
        * `ActionValue (Vector2D)` -> Break (X, Y)
        * **Move Forward**: `GetActorForwardVector` *X* `Speed`(10.0) -> `AddActorWorldOffset`
        * **Move Right**: `GetActorRightVector` *Y* `Speed`(10.0) -> `AddActorWorldOffset`

## 2. Implement Possession (`BP_SpiritController`)

**Location**: `/Game/Core/Controllers/BP_SpiritController`
**Event Graph**:

1. **Input Action IA_Select (Left Click)**:
    * **Started**:
        * `GetHitResultUnderCursorByChannel` (Visibility)
        * **Branch** (Blocking Hit?):
            * **True**: Break Hit Result -> Get `Hit Actor`
            * `Cast To BP_UnitBase` (Hit Actor):
                * **Success**: Call `Possess(Unit)` (Self)

2. **Input Action IA_Possess (Key P)**:
    * (Optional debug key to possess specific actor)

## 3. Play the Demo

1. Open `/Game/Maps/DemoMap`.
2. Hit **Play**.
3. You should spawn in the sky (RTS View).
4. You should see "MyMinion_01" (the unit we placed).
5. Use **WASD** to move camera.
6. **Click** the unit to Possess it (if logic 2 is done).

> I have set up the Map, the Assets, and the Inputs. Only the wiring above is needed!
