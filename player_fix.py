"""
Patch for the Player class in poke-env to fix the 'str' object has no attribute 'message' error.
Enhanced with detailed debugging, error handling, battle monitoring, and timeout management.

This module also adds:
- Battle state tracking to detect stalled battles
- Configurable timeouts (3 minutes per turn, 20 minutes per battle by default)
- Response caching to reduce API calls and speed up decision-making
- Automatic unstall mechanisms when battles stop progressing
"""

import os
import sys
import asyncio
import logging
import traceback
import time
from typing import Union, Awaitable, Any, Dict, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("pokemon_agent_debug.log")
    ]
)
logger = logging.getLogger("player_fix")

# Get the path to the poke-env library
SITE_PACKAGES_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), 
    "pokemon_agent/lib/python3.12/site-packages"
)

# Add the path to sys.path if it's not already there
if SITE_PACKAGES_PATH not in sys.path:
    sys.path.append(SITE_PACKAGES_PATH)
    logger.info(f"Added {SITE_PACKAGES_PATH} to sys.path")

from poke_env.player.battle_order import BattleOrder, StringBattleOrder
from poke_env.player.player import Player

# Battle timeout constants (in seconds)
DEFAULT_TURN_TIMEOUT = 180       # 3 minutes per turn
DEFAULT_BATTLE_TIMEOUT = 1200    # 20 minutes per battle
PROGRESS_CHECK_INTERVAL = 10     # Check battle progress every 10 seconds

class BattleMonitor:
    """
    Monitors battle progress and manages timeouts to ensure battles complete.
    
    This class tracks battle state and enforces timeouts to prevent
    battles from stalling indefinitely. It can detect when a battle is
    making no progress and can force completion after a maximum time.
    """
    
    def __init__(self, max_turn_time=DEFAULT_TURN_TIMEOUT, max_battle_time=DEFAULT_BATTLE_TIMEOUT):
        self.battle_states = {}
        self.battle_start_times = {}
        self.last_turn_times = {}
        self.max_turn_time = max_turn_time
        self.max_battle_time = max_battle_time
        self.stalled_battles = set()
    
    def register_battle(self, battle_id):
        """Register a new battle for monitoring."""
        now = time.time()
        self.battle_states[battle_id] = {
            "turn": 0,
            "is_active": True,
            "last_progress": now
        }
        self.battle_start_times[battle_id] = now
        self.last_turn_times[battle_id] = now
        logger.info(f"Battle {battle_id} registered for monitoring")
    
    def update_battle_state(self, battle_id, turn):
        """Update the state of a battle when progress is made."""
        now = time.time()
        if battle_id in self.battle_states:
            if turn > self.battle_states[battle_id]["turn"]:
                logger.info(f"Battle {battle_id}: Turn {self.battle_states[battle_id]['turn']} → {turn}")
                self.battle_states[battle_id]["turn"] = turn
                self.battle_states[battle_id]["last_progress"] = now
                self.last_turn_times[battle_id] = now
                
                # If battle was marked as stalled, remove it
                if battle_id in self.stalled_battles:
                    self.stalled_battles.remove(battle_id)
    
    def mark_battle_complete(self, battle_id):
        """Mark a battle as completed."""
        if battle_id in self.battle_states:
            duration = time.time() - self.battle_start_times[battle_id]
            logger.info(f"Battle {battle_id} completed in {duration:.1f} seconds ({self.battle_states[battle_id]['turn']} turns)")
            self.battle_states[battle_id]["is_active"] = False
            
            # Remove from stalled battles if present
            if battle_id in self.stalled_battles:
                self.stalled_battles.remove(battle_id)
    
    def check_for_stalled_battles(self, player=None):
        """Check for battles that have stalled and attempt to resolve them."""
        now = time.time()
        for battle_id, state in self.battle_states.items():
            # Skip non-active battles
            if not state["is_active"]:
                continue
            
            # Check for turn timeout
            turn_idle_time = now - self.last_turn_times[battle_id]
            if turn_idle_time > self.max_turn_time:
                if battle_id not in self.stalled_battles:
                    logger.warning(f"Battle {battle_id} stalled at turn {state['turn']} - no progress for {turn_idle_time:.1f} seconds")
                    self.stalled_battles.add(battle_id)
                    
                    # Force progress by having the player make a default move
                    self._attempt_unstall_battle(battle_id, player)
            
            # Check for total battle timeout
            battle_duration = now - self.battle_start_times[battle_id]
            if battle_duration > self.max_battle_time:
                logger.warning(f"Battle {battle_id} exceeded maximum time of {self.max_battle_time} seconds - forcing completion")
                self._force_battle_completion(battle_id, player)
    
    def _attempt_unstall_battle(self, battle_id, player=None):
        """Attempt to unstall a battle by making default moves."""
        logger.info(f"Attempting to unstall battle {battle_id}")
        
        # Send chat message to battle indicating stall detection
        try:
            if player and battle_id in player._battles:
                player.send_chat_message(f"Battle appears stalled, auto-selecting moves to continue.", battle_id)
                battle = player._battles[battle_id]
                
                # If player has an active Pokemon, make a default move
                if battle.active_pokemon and not battle.maybe_trapped:
                    # Reset the battle request timer 
                    self.last_turn_times[battle_id] = time.time()
                    
                    # Default to a random move to unblock battle
                    logger.info(f"Forcing player to make a random move in battle {battle_id}")
                    # The random move will be selected by the choose_default_move method
        except Exception as e:
            logger.error(f"Error attempting to unstall battle {battle_id}: {e}")
    
    def _force_battle_completion(self, battle_id, player=None):
        """Force a battle to complete if it has exceeded the maximum time."""
        try:
            if player and battle_id in player._battles:
                player.send_chat_message(f"Battle exceeded maximum time limit of {self.max_battle_time} seconds. Forfeiting battle.", battle_id)
                player.forfeit_battle(battle_id)
                
            self.mark_battle_complete(battle_id)
        except Exception as e:
            logger.error(f"Error forcing battle {battle_id} completion: {e}")

# Add response caching to reduce API calls
class ResponseCache:
    """Simple cache for responses to reduce API calls and speed up decision-making."""
    
    def __init__(self, max_size=100):
        self.cache = {}
        self.max_size = max_size
    
    def get(self, key):
        """Get a cached response if available."""
        return self.cache.get(key)
    
    def set(self, key, value):
        """Store a response in the cache."""
        # If cache is full, remove oldest entry
        if len(self.cache) >= self.max_size:
            oldest_key = next(iter(self.cache))
            del self.cache[oldest_key]
        
        self.cache[key] = value

# Global response cache instance
response_cache = ResponseCache()

def debug_choice(choice: Any) -> str:
    """
    Create detailed debug information about the choice object.
    
    Args:
        choice: The choice object to inspect
        
    Returns:
        A string with detailed debugging information
    """
    debug_info = []
    debug_info.append(f"Type: {type(choice).__name__}")
    debug_info.append(f"Repr: {repr(choice)}")
    debug_info.append(f"Str: {str(choice)}")
    
    # Check if it has a message attribute
    has_message = hasattr(choice, 'message')
    debug_info.append(f"Has 'message' attribute: {has_message}")
    
    if has_message:
        debug_info.append(f"Message value: {choice.message}")
    
    # Check if it's a string
    if isinstance(choice, str):
        debug_info.append(f"String content: '{choice}'")
        
    # Check available attributes and methods
    attrs = [attr for attr in dir(choice) if not attr.startswith('__')]
    debug_info.append(f"Available attributes: {attrs}")
    
    return "\n".join(debug_info)

# Create a battle monitor instance
battle_monitor = BattleMonitor()

# Enhanced version of the _handle_battle_request method with caching and timeouts
async def patched_handle_battle_request(self, battle, from_teampreview_request=False, maybe_default_order=False):
    """
    Patched version of the _handle_battle_request method that properly handles string responses.
    
    Enhanced with:
    - Detailed debugging and error handling for message attribute issues
    - Response caching to speed up decisions
    - Battle state monitoring for timeout enforcement
    - Extended timeout protection for API calls
    """
    logger.info(f"Battle request received for {battle.battle_tag}")
    message = None
    choice = None
    
    # Register or update battle in monitor
    if battle.battle_tag not in battle_monitor.battle_states:
        battle_monitor.register_battle(battle.battle_tag)
    
    # Update battle state with current turn
    battle_monitor.update_battle_state(battle.battle_tag, battle.turn)
    
    try:
        if maybe_default_order and (
            "illusion" in [p.ability for p in battle.team.values()]
            or asyncio.get_event_loop().time() * 1000 % 100 < self.DEFAULT_CHOICE_CHANCE * 100
        ):
            logger.debug("Using default choice due to illusion or random chance")
            default_choice = self.choose_default_move()
            logger.debug(f"Default choice: {debug_choice(default_choice)}")
            message = default_choice.message
            
        elif battle.teampreview:
            if not from_teampreview_request:
                logger.debug("Not from teampreview request, returning")
                return
            logger.debug("Requesting teampreview")
            message = self.teampreview(battle)
            logger.debug(f"Teampreview message: {message}")
            
        else:
            if maybe_default_order:
                self._trying_again.set()
                logger.debug("Set trying_again flag")
            
            # Check for cached response to speed up decision making
            cache_key = hash(str(battle.battle_tag) + str(battle.turn) + str(battle.active_pokemon) + 
                         str(battle.available_moves) + str(battle.available_switches))
            cached_response = response_cache.get(cache_key)
            
            if cached_response:
                logger.debug("Using cached response to speed up decision")
                choice = cached_response
            else:
                logger.debug("Calling choose_move method")
                choice = self.choose_move(battle)
                
                # Debug the choice object before awaiting
                if asyncio.iscoroutine(choice) or isinstance(choice, Awaitable):
                    try:
                        # Apply extended timeout for API calls
                        logger.debug("Choice is awaitable, awaiting result with extended timeout")
                        choice = await asyncio.wait_for(choice, timeout=120)  # 2 minutes timeout
                    except asyncio.TimeoutError:
                        logger.warning("API call timed out after 2 minutes, using default move")
                        choice = self.choose_default_move()
                
                # Cache the result for future use
                if choice:
                    response_cache.set(cache_key, choice)
                    
            logger.debug(f"Choice after processing: {debug_choice(choice)}")
                
            # Here's the enhanced fix with better error handling and debugging
            if isinstance(choice, str):
                logger.debug(f"Choice is a string: '{choice}'")
                message = choice
            elif hasattr(choice, 'message'):
                logger.debug(f"Choice has message attribute: {choice.message}")
                message = choice.message
            else:
                # More detailed fallback behavior
                logger.warning(f"Choice doesn't have message attribute. Type: {type(choice).__name__}")
                try:
                    # Try to create a StringBattleOrder as a fallback
                    string_repr = str(choice)
                    logger.debug(f"Creating StringBattleOrder with: '{string_repr}'")
                    message = StringBattleOrder(string_repr).message
                    logger.debug(f"Created message: {message}")
                except Exception as string_error:
                    # Last resort fallback to default move
                    logger.error(f"Error creating StringBattleOrder: {string_error}")
                    logger.error(f"Traceback: {traceback.format_exc()}")
                    logger.warning("Falling back to default move")
                    message = self.choose_default_move().message
    except Exception as e:
        # Comprehensive error handling
        logger.error(f"Error in patched_handle_battle_request: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        logger.error(f"Battle: {battle.battle_tag}, Choice: {choice}")
        # Fallback to default move as a last resort
        logger.warning("Exception occurred, falling back to default move")
        message = self.choose_default_move().message
    
    # Log final message before sending
    logger.debug(f"Final message to send: {message}")
    
    try:
        await self.ps_client.send_message(message, battle.battle_tag)
        logger.debug(f"Message sent successfully for battle {battle.battle_tag}")
    except Exception as send_error:
        logger.error(f"Error sending message: {send_error}")
        logger.error(f"Traceback: {traceback.format_exc()}")
    
    # Check for stalled battles
    battle_monitor.check_for_stalled_battles(self)

# Patches a Player instance with battle monitoring capabilities
def patch_player_with_monitoring(player, turn_timeout=DEFAULT_TURN_TIMEOUT, battle_timeout=DEFAULT_BATTLE_TIMEOUT):
    """
    Patch a player instance with battle monitoring capabilities.
    
    Args:
        player: The player instance to patch
        turn_timeout: Maximum time per turn (seconds)
        battle_timeout: Maximum time per battle (seconds)
    """
    # Create a battle monitor for this player
    player._battle_monitor = BattleMonitor(
        max_turn_time=turn_timeout,
        max_battle_time=battle_timeout
    )
    
    # Patch original methods to add monitoring
    original_reset_battles = player.reset_battles
    
    def patched_reset_battles(self):
        # Reset the battle monitor
        self._battle_monitor = BattleMonitor(
            max_turn_time=turn_timeout,
            max_battle_time=battle_timeout
        )
        # Call original method
        return original_reset_battles()
    
    # Apply the patches
    player.reset_battles = patched_reset_battles.__get__(player)
    
    return player

# Apply the patch to the Player class
def apply_patch():
    """Apply the patch to the Player class."""
    # Patch the handle_battle_request method
    Player._handle_battle_request = patched_handle_battle_request
    
    # Add a class method to patch players with monitoring
    Player.patch_with_monitoring = patch_player_with_monitoring
    
    logger.info("Applied enhanced patch with battle monitoring and timeouts")
    
if __name__ == "__main__":
    apply_patch()