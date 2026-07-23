import unreal

def list_level_actors():
    # Use the new Subsystem if possible, or fallback
    subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    
    # Get all level actors
    actors = subsystem.get_all_level_actors()
    
    report_path = "d:/Workspace/03_Dev_Projects/game/Spirits-Calling/Spirits_Calling/Scripts/LevelActors.txt"
    
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(f"Level Actors: {len(actors)}\n")
        f.write("-" * 30 + "\n")
        
        for a in actors:
            label = a.get_actor_label()
            cls = a.get_class().get_name()
            loc = a.get_actor_location()
            f.write(f"[{cls}] {label} @ {loc}\n")
            
    print(f"Report saved to {report_path}")

if __name__ == "__main__":
    list_level_actors()
