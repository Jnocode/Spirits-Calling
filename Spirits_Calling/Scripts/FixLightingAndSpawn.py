import unreal

def fix_lighting_and_spawn():
    # 1. Fix Lighting (Make Dynamic)
    lib = unreal.EditorLevelLibrary
    actors = lib.get_all_level_actors()
    
    for actor in actors:
        # Check for Light
        is_light = isinstance(actor, unreal.DirectionalLight) or isinstance(actor, unreal.SkyLight)
        if is_light:
            # Set Mobility to Movable (2)
            # Enum: EComponentMobility::Movable
            # In Python: unreal.ComponentMobility.MOVABLE
            
            # Root Component holds mobility
            root = actor.root_component
            if root:
                root.set_editor_property("Mobility", unreal.ComponentMobility.MOVABLE)
                unreal.log_warning(f"Set {actor.get_actor_label()} to Movable (Dynamic).")
                
        # 2. Fix PlayerStart
        if isinstance(actor, unreal.PlayerStart):
            # Move it up
            current_loc = actor.get_actor_location()
            new_loc = unreal.Vector(current_loc.x, current_loc.y, 1000) # High up
            actor.set_actor_location(new_loc, False, True)
            unreal.log_warning(f"Moved PlayerStart to {new_loc}")

    # Force update
    lib.save_current_level()
    unreal.log_warning("Lighting & Spawn Fixed.")

if __name__ == "__main__":
    fix_lighting_and_spawn()
