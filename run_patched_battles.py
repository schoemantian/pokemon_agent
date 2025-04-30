#!/usr/bin/env python3
"""
Enhanced battle runner with patched Player class to fix message attribute error.
Includes additional error handling, detailed logging, and debug mode.
"""

import os
import sys
import asyncio
import importlib.util
import traceback
import logging
import json
import time
from typing import Optional, Dict, Any

# Configure logging
DEBUG_MODE = os.environ.get("DEBUG", "0") == "1"
log_level = logging.DEBUG if DEBUG_MODE else logging.INFO

logging.basicConfig(
    level=log_level,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("pokemon_agent_debug.log")
    ]
)
logger = logging.getLogger("run_patched_battles")

def error_handler(func):
    """Decorator to handle and log errors."""
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            logger.error(f"Error in {func.__name__}: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            raise
    return wrapper

@error_handler
def apply_player_fix():
    """Apply the player fix patch with error handling."""
    try:
        logger.info("Applying player_fix patch...")
        # First, load and apply the player_fix patch
        from player_fix import apply_patch
        apply_patch()
        logger.info("Successfully applied the player_fix patch")
    except ImportError as e:
        logger.error(f"Failed to import player_fix: {e}")
        raise
    except Exception as e:
        logger.error(f"Failed to apply patch: {e}")
        raise

@error_handler
def import_run_battles():
    """Import the run_battles module with error handling."""
    try:
        logger.info("Importing run_battles module...")
        import run_battles
        logger.info("Successfully imported run_battles module")
        return run_battles
    except ImportError as e:
        logger.error(f"Failed to import run_battles: {e}")
        raise

class BattleMonitor:
    """Monitor for battles with enhanced debugging."""
    
    def __init__(self):
        self.start_time = time.time()
        self.battles = {}
        self.error_count = 0
        self.logger = logging.getLogger("battle_monitor")
    
    def register_battle(self, battle_id, agent_username):
        """Register a new battle for monitoring."""
        self.battles[battle_id] = {
            "start_time": time.time(),
            "status": "active",
            "turn_count": 0,
            "agent": agent_username,
            "last_activity": time.time(),
            "errors": []
        }
        self.logger.info(f"Registered new battle: {battle_id} with agent {agent_username}")
    
    def update_battle(self, battle_id, turn=None, status=None, error=None):
        """Update battle status information."""
        if battle_id not in self.battles:
            self.logger.warning(f"Attempted to update unknown battle: {battle_id}")
            return
        
        battle = self.battles[battle_id]
        battle["last_activity"] = time.time()
        
        if turn is not None:
            battle["turn_count"] = turn
            self.logger.debug(f"Battle {battle_id}: Turn {turn}")
        
        if status is not None:
            battle["status"] = status
            self.logger.info(f"Battle {battle_id}: Status changed to {status}")
        
        if error is not None:
            battle["errors"].append(error)
            self.error_count += 1
            self.logger.error(f"Battle {battle_id}: Error - {error}")
    
    def check_for_stalled_battles(self, timeout=60):
        """Check for battles that have been inactive for too long."""
        current_time = time.time()
        for battle_id, battle in list(self.battles.items()):
            if battle["status"] == "active":
                inactive_time = current_time - battle["last_activity"]
                if inactive_time > timeout:
                    self.logger.warning(f"Battle {battle_id} may be stalled (inactive for {inactive_time:.1f}s)")
                    battle["status"] = "stalled"
    
    def log_summary(self):
        """Log a summary of all monitored battles."""
        runtime = time.time() - self.start_time
        active_battles = sum(1 for b in self.battles.values() if b["status"] == "active")
        completed_battles = sum(1 for b in self.battles.values() if b["status"] == "completed")
        stalled_battles = sum(1 for b in self.battles.values() if b["status"] == "stalled")
        
        self.logger.info(f"Battle Monitor Summary:")
        self.logger.info(f"- Runtime: {runtime:.1f} seconds")
        self.logger.info(f"- Battles: {len(self.battles)} total, {active_battles} active, {completed_battles} completed, {stalled_battles} stalled")
        self.logger.info(f"- Errors: {self.error_count}")
        
        if self.error_count > 0 and DEBUG_MODE:
            self.logger.debug("Error summary:")
            for battle_id, battle in self.battles.items():
                if battle["errors"]:
                    self.logger.debug(f"Battle {battle_id}: {len(battle['errors'])} errors")
                    for i, error in enumerate(battle["errors"][:3]):  # Show first 3 errors
                        self.logger.debug(f"  Error {i+1}: {error}")
                    if len(battle["errors"]) > 3:
                        self.logger.debug(f"  ... and {len(battle['errors']) - 3} more errors")

class PatchedBattleRunner:
    """Enhanced battle runner with patched Player class."""
    
    def __init__(self):
        self.logger = logging.getLogger("patched_battle_runner")
        self.monitor = BattleMonitor()
        self.run_battles = None
    
    @error_handler
    def patch_and_import(self):
        """Apply patches and import modules."""
        apply_player_fix()
        self.run_battles = import_run_battles()
    
    @error_handler
    def patch_run_battles_for_monitoring(self):
        """Patch the run_battles module to add monitoring."""
        if not self.run_battles:
            self.logger.error("Cannot patch run_battles: Module not imported")
            return
        
        # Store the original run_single_battle function
        original_run_single_battle = self.run_battles.run_single_battle
        
        # Create a patched version that adds monitoring
        async def patched_run_single_battle(gaia_agent, opponent, n_battles=1):
            """Patched version of run_single_battle with enhanced logging and monitoring."""
            self.logger.info(f"Starting battle between {gaia_agent.username} and {opponent.username}")
            
            # Configure monitoring instance for the battle
            monitor = self.monitor
            
            # Track ongoing battles for monitoring
            original_battle_against = gaia_agent.battle_against
            
            async def monitored_battle_against(opponent, n_battles=1):
                """Monitor battles as they start and finish."""
                # Start the battles
                battle_coroutine = original_battle_against(opponent, n_battles=n_battles)
                
                # Register the initial battle with a placeholder ID
                monitor.register_battle("pending", gaia_agent.username)
                
                # Check for new battles periodically
                previous_battles = set()
                
                while not battle_coroutine.done():
                    current_battles = set(gaia_agent._battles.keys())
                    
                    # Register any new battles
                    for battle_id in current_battles - previous_battles:
                        # Update the placeholder or add a new battle
                        if "pending" in monitor.battles:
                            monitor.battles[battle_id] = monitor.battles.pop("pending")
                            monitor.battles[battle_id]["start_time"] = time.time()
                        else:
                            monitor.register_battle(battle_id, gaia_agent.username)
                    
                    # Update battle information
                    for battle_id in current_battles:
                        if battle_id in gaia_agent._battles:
                            battle = gaia_agent._battles[battle_id]
                            monitor.update_battle(battle_id, turn=battle.turn)
                    
                    # Check for stalled battles
                    monitor.check_for_stalled_battles()
                    
                    previous_battles = current_battles
                    await asyncio.sleep(2)  # Check every 2 seconds
                
                # Wait for the coroutine to complete
                result = await battle_coroutine
                
                # Mark all battles as completed
                for battle_id in gaia_agent._battles:
                    monitor.update_battle(battle_id, status="completed")
                
                # Log a summary
                monitor.log_summary()
                
                return result
            
            # Replace the battle_against method temporarily
            gaia_agent.battle_against = monitored_battle_against
            
            try:
                # Run the original function with the patched method
                return await original_run_single_battle(gaia_agent, opponent, n_battles)
            finally:
                # Restore the original method
                gaia_agent.battle_against = original_battle_against
        
        # Apply the patch
        self.run_battles.run_single_battle = patched_run_single_battle
        self.logger.info("Successfully patched run_battles for monitoring")
    
    @error_handler
    async def run(self):
        """Run the patched battles."""
        self.logger.info("Running patched battles")
        
        if DEBUG_MODE:
            self.logger.info("Debug mode enabled - using detailed logging")
        
        # Apply all patches
        self.patch_and_import()
        self.patch_run_battles_for_monitoring()
        
        # Run the main function from run_battles.py
        try:
            await self.run_battles.main()
            self.logger.info("Battles completed successfully")
            return 0
        except Exception as e:
            self.logger.error(f"Error during battle execution: {e}")
            self.logger.error(f"Traceback: {traceback.format_exc()}")
            return 1

if __name__ == "__main__":
    battle_runner = PatchedBattleRunner()
    exit_code = asyncio.run(battle_runner.run())
    sys.exit(exit_code)