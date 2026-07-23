import unreal
import random

def simulate_summon():
    # Load Asset
    unit_bp = unreal.load_asset("/Game/Core/Characters/BP_UnitBase")
    
    # Random Location
    x = random.uniform(-500, 500)
    y = random.uniform(-500, 500)
    
    loc = unreal.Vector(x, y, 50)
    rot = unreal.Rotator(0, random.uniform(0, 360), 0)
    
    actor = unreal.EditorLevelLibrary.spawn_actor_from_object(unit_bp, loc, rot)
    if actor:
        actor.set_actor_label(f"Summoned_Unit_{random.randint(100,999)}")
        unreal.log_warning(f"SUMMONED UNIT at {loc}")
        
    # Effect?
    # spawn_emitter_at_location...

if __name__ == "__main__":
    simulate_summon()
