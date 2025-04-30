"""
Patch for the Player class in poke-env to fix the 'str' object has no attribute 'message' error.
Enhanced with detailed debugging and error handling.
"""

import os
import sys
import asyncio
import logging
import traceback
from typing import Union, Awaitable, Any

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

# Create a modified version of the _handle_battle_request method
async def patched_handle_battle_request(self, battle, from_teampreview_request=False, maybe_default_order=False):
    """
    Patched version of the _handle_battle_request method that properly handles string responses.
    
    Enhanced with detailed debugging and error handling to diagnose issues with message attribute.
    """
    logger.info(f"Battle request received for {battle.battle_tag}")
    message = None
    choice = None
    
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
                
            logger.debug("Calling choose_move method")
            choice = self.choose_move(battle)
            
            # Debug the choice object before awaiting
            if asyncio.iscoroutine(choice) or isinstance(choice, Awaitable):
                logger.debug("Choice is awaitable, awaiting result")
                choice = await choice
                
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

# Apply the patch to the Player class
def apply_patch():
    """Apply the patch to the Player class."""
    Player._handle_battle_request = patched_handle_battle_request
    logger.info("Applied enhanced patch to fix the 'str' object has no attribute 'message' error")
    
if __name__ == "__main__":
    apply_patch()