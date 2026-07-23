import unreal
import time

class CombatManager:
    def __init__(self):
        self.player_health = 100
        self.is_game_over = False
        self.attack_range = 150.0 # cm
        self.damage_per_hit = 10
        self.last_damage_time = 0
        self.damage_cooldown = 1.0 # sec
        
        unreal.log_warning("CombatManager Initialized. Health: 100")

    def check_collisions(self):
        if self.is_game_over:
            return

        # 1. Find Player
        # In Editor/PIE, we look for SpiritPawn
        editor_subsystem = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
        world = editor_subsystem.get_editor_world()
        
        if not world: 
             return

        actors = unreal.EditorLevelLibrary.get_all_level_actors()
        player = None
        enemies = []
        
        for a in actors:
            name = a.get_name()
            if "SpiritPawn" in name or "Player" in name:
                player = a
            if "BP_Orc" in name:
                enemies.append(a)
        
        if not player:
            return

        # 2. Check Distances
        player_loc = player.get_actor_location()
        current_time = time.time()
        
        for enemy in enemies:
            enemy_loc = enemy.get_actor_location()
            dist = player_loc.distance(enemy_loc)
            
            if dist < self.attack_range:
                # Attack!
                if current_time - self.last_damage_time > self.damage_cooldown:
                    self.take_damage(self.damage_per_hit)
                    self.last_damage_time = current_time

    def take_damage(self, amount):
        self.player_health -= amount
        unreal.log_warning(f"Player took {amount} damage! HP: {self.player_health}")
        
        if self.player_health <= 0:
            self.game_over()

    def game_over(self):
        self.is_game_over = True
        unreal.log_warning("=== GAME OVER ===")

    def tick(self, delta_time):
        self.check_collisions()

# Global Instance
combat_manager = CombatManager()

# We need to hook this into a tick loop, similar to WaveManager.
# Let's create a combined runner or just expose start/stop methods.

def start_combat_loop():
    # Register to Slate Tick (reusing the pattern)
    global hook
    hook = unreal.register_slate_post_tick_callback(combat_manager.tick)
    unreal.log_warning("Combat Loop Started")

def stop_combat_loop():
    global hook
    if 'hook' in globals():
        unreal.unregister_slate_post_tick_callback(hook)
        unreal.log_warning("Combat Loop Stopped")

if __name__ == "__main__":
    start_combat_loop()
