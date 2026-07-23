import unreal
import time

class WaveManager:
    def __init__(self):
        self.current_wave = 0
        self.is_active = False
        self.enemies_remaining = 0
        self.spawn_points = [
            unreal.Vector(1000, 0, 50),
            unreal.Vector(-1000, 0, 50),
            unreal.Vector(0, 1000, 50),
            unreal.Vector(0, -1000, 50)
        ]
        self.enemy_bp_path = "/Game/Core/Characters/BP_Orc" # Adjust path as needed
        unreal.log_warning("WaveManager Initialized")

    def start_wave(self, wave_index):
        self.current_wave = wave_index
        count = 3 + (wave_index * 2) # Curve: 3, 5, 7...
        unreal.log_warning(f"WaveManager: Starting Wave {wave_index} with {count} enemies.")
        
        for i in range(count):
            spawn_loc = self.spawn_points[i % len(self.spawn_points)]
            # Jitter
            spawn_loc.x += (i * 50)
            self.spawn_enemy(spawn_loc)
            
        self.enemies_remaining = count
        
        # Register Tick if not already
        if not self.is_active:
            self.tick_handle = unreal.register_slate_post_tick_callback(self.tick)
            self.is_active = True

    def tick(self, delta_time):
        # Python AI Loop: Move all Orcs to Center (0,0,0) or Player
        # Performance warning: This is heavy every tick. Throttle it?
        # Just do it every 60 ticks or use time.
        pass # Placeholder for optimization
        
        # Simple implementation: Find all Orcs and MoveTo (0,0,0)
        # Note: calling get_all_level_actors every tick is bad.
        # But for demo with < 20 units it is fine.
        actors = unreal.EditorLevelLibrary.get_all_level_actors()
        for actor in actors:
            if "BP_Orc" in actor.get_name():
                # Check distance
                loc = actor.get_actor_location()
                target = unreal.Vector(0, 0, 50) # Center
                
                # Move towards target (Basic slide)
                # Or use AI Controller if available
                # controller = unreal.AIBlueprintHelperLibrary.get_ai_controller(actor)
                # if controller: unreal.AIBlueprintHelperLibrary.simple_move_to_location(controller, target)
                pass

    def stop(self):
        if self.is_active:
             unreal.unregister_slate_post_tick_callback(self.tick_handle)
             self.is_active = False

# Singleton instance
wave_manager = WaveManager()

def start_demo():
    wave_manager.start_wave(1)

def stop_demo():
    wave_manager.stop()

if __name__ == "__main__":
    start_demo()
