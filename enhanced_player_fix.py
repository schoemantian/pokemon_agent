#!/usr/bin/env python3
"""
Enhanced patch for the Player class in poke-env to fix the 'str' object has no attribute 'message' error.
Includes detailed debugging and logging to track the issue.
"""

import os
import sys
import asyncio
import traceback
import logging
import inspect
from typing import Union, Awaitable, Optional, Dict, Any

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

# Create a logger for this module
logger = logging.getLogger('player_fix')

# Enable debug mode if environment variable is set
DEBUG = os.environ.get('DEBUG', '0').lower() in ('1', 'true', 'yes', 'on')
if DEBUG:
    logger.setLevel(logging.DEBUG)
    logger.debug("Debug mode enabled in player_fix.py")

# Get the path to the poke-env library
SITE_PACKAGES_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), 
    "pokemon_agent/lib/python3.12/site-packages"
)

# Add the path to sys.path if it's not already there
if SITE_PACKAGES_PATH not in sys.path:
    sys.path.append(SITE_PACKAGES_PATH)
    logger.debug(f"Added {SITE_PACKAGES_PATH} to sys.path")

try:
    from poke_env.player.battle_order import BattleOrder, StringBattleOrder, DefaultBattleOrder
    from poke_env.player.player import Player
    logger.debug("Successfully imported poke-env modules")
except ImportError as e:
    logger.error(f"Failed to import poke-env modules: {str(e)}")
    raise

def log_object_details(obj, prefix=""):
    """Log detailed information about an object for debugging."""
    if DEBUG:
        logger.debug(f"{prefix} Object type: {type(obj)}")
        logger.debug(f"{prefix} Object representation: {repr(obj)}")
        logger.debug(f"{prefix} Object string: {str(obj)}")
        
        # Log attributes
        try:
            attrs = dir(obj)
            logger.debug(f"{prefix} Object attributes: {attrs}")
        except Exception as e:
            logger.debug(f"{prefix} Failed to get attributes: {str(e)}")
        
        # If it's a string, log its length
        if isinstance(obj, str):
            logger.debug(f"{prefix} String length: {len(obj)}")

async def enhanced_patched_handle_battle_request(self, battle, from_teampreview_request=False, maybe_default_order=False):
    """
    Enhanced patched version of the _handle_battle_request method with improved error handling and debugging.
    
    This method fixes the issue where a string response causes an AttributeError when accessing the 'message' attribute.
    It includes detailed logging to track the flow and issues.
    """
    battle_tag = battle.battle_tag if hasattr(battle, 'battle_tag') else 'unknown'
    logger.info(f"[{battle_tag}] Handling battle request (teampreview: {from_teampreview_request}, maybe_default: {maybe_default_order})")
    
    try:
        # Default order case
        if maybe_default_order and (
            "illusion" in [p.ability for p in battle.team.values()]
            or asyncio.get_event_loop().time() * 1000 % 100 < self.DEFAULT_CHOICE_CHANCE * 100
        ):
            logger.debug(f"[{battle_tag}] Using default move")
            default_order = self.choose_default_move()
            message = default_order.message
            logger.debug(f"[{battle_tag}] Default order message: {message}")
            await self.ps_client.send_message(message, battle.battle_tag)
            return

        # Team preview case
        if battle.teampreview:
            if not from_teampreview_request:
                logger.debug(f"[{battle_tag}] Skip non-teampreview request during teampreview")
                return
            logger.debug(f"[{battle_tag}] Handling teampreview")
            message = self.teampreview(battle)
            logger.debug(f"[{battle_tag}] Teampreview message: {message}")
            await self.ps_client.send_message(message, battle.battle_tag)
            return

        # Set trying_again if this is a retry
        if maybe_default_order and hasattr(self, '_trying_again'):
            logger.debug(f"[{battle_tag}] Setting trying_again flag")
            self._trying_again.set()

        # Get the choice from the agent
        logger.debug(f"[{battle_tag}] Getting choice from choose_move")
        choice = self.choose_move(battle)
        
        # Handle awaitable choice
        if inspect.isawaitable(choice):
            logger.debug(f"[{battle_tag}] Choice is awaitable, awaiting result")
            try:
                choice = await choice
                logger.debug(f"[{battle_tag}] Awaited choice result type: {type(choice)}")
            except Exception as e:
                logger.error(f"[{battle_tag}] Error awaiting choice: {str(e)}")
                stack_trace = traceback.format_exc()
                logger.error(f"[{battle_tag}] Stack trace: {stack_trace}")
                # Fallback to default move in case of error
                logger.info(f"[{battle_tag}] Falling back to default move after await error")
                choice = self.choose_default_move()
        
        # Log detailed information about the choice
        log_object_details(choice, prefix=f"[{battle_tag}] Choice:")
        
        # Process the choice based on its type
        try:
            if isinstance(choice, str):
                # String choice - use directly
                logger.debug(f"[{battle_tag}] Choice is string: '{choice}'")
                message = choice
            elif hasattr(choice, 'message'):
                # BattleOrder with message attribute
                logger.debug(f"[{battle_tag}] Choice has message attribute: '{choice.message}'")
                message = choice.message
            elif hasattr(choice, 'order') and isinstance(choice.order, str):
                # Object with order attribute that's a string
                logger.debug(f"[{battle_tag}] Choice has order attribute: '{choice.order}'")
                message = choice.order
            elif isinstance(choice, dict) and 'message' in choice:
                # Dictionary with message key
                logger.debug(f"[{battle_tag}] Choice is dict with message key: '{choice['message']}'")
                message = choice['message']
            elif isinstance(choice, dict) and 'order' in choice:
                # Dictionary with order key
                logger.debug(f"[{battle_tag}] Choice is dict with order key: '{choice['order']}'")
                message = choice['order']
            else:
                # Try to convert to string as a last resort
                logger.warning(f"[{battle_tag}] Choice has no message attribute, attempting fallbacks")
                
                # Try to create a StringBattleOrder
                try:
                    string_order = StringBattleOrder(str(choice))
                    logger.debug(f"[{battle_tag}] Created StringBattleOrder: {string_order.message}")
                    message = string_order.message
                except Exception as string_error:
                    logger.error(f"[{battle_tag}] Failed to create StringBattleOrder: {str(string_error)}")
                    
                    # Final fallback - try to use default move
                    try:
                        default_order = self.choose_default_move()
                        logger.debug(f"[{battle_tag}] Falling back to default move: {default_order.message}")
                        message = default_order.message
                    except Exception as default_error:
                        logger.error(f"[{battle_tag}] Failed to create default order: {str(default_error)}")
                        # Last resort - hardcoded default
                        logger.error(f"[{battle_tag}] Using hardcoded default 'default'")
                        message = "default"
        
        except Exception as e:
            logger.error(f"[{battle_tag}] Error processing choice: {str(e)}")
            stack_trace = traceback.format_exc()
            logger.error(f"[{battle_tag}] Stack trace: {stack_trace}")
            # Use a hardcoded default as last resort
            message = "default"
            logger.error(f"[{battle_tag}] Using hardcoded default after processing error")
        
        # Send the message
        logger.info(f"[{battle_tag}] Sending message: '{message}'")
        await self.ps_client.send_message(message, battle.battle_tag)
        logger.debug(f"[{battle_tag}] Message sent successfully")
        
    except Exception as e:
        logger.error(f"[{battle_tag}] Unhandled exception in enhanced_patched_handle_battle_request: {str(e)}")
        stack_trace = traceback.format_exc()
        logger.error(f"[{battle_tag}] Stack trace: {stack_trace}")
        
        # Try to send a default message as a last resort
        try:
            logger.error(f"[{battle_tag}] Attempting to send default message after unhandled exception")
            await self.ps_client.send_message("default", battle.battle_tag)
        except Exception as send_error:
            logger.error(f"[{battle_tag}] Failed to send default message: {str(send_error)}")

def apply_patch():
    """Apply the enhanced patch to the Player class."""
    original_method = Player._handle_battle_request
    
    # Store the original method for reference
    if not hasattr(Player, '_original_handle_battle_request'):
        Player._original_handle_battle_request = original_method
    
    # Apply the patch
    Player._handle_battle_request = enhanced_patched_handle_battle_request
    
    logger.info("Applied enhanced patch to fix the 'str' object has no attribute 'message' error")
    logger.info("Added detailed logging and robust error handling")

def remove_patch():
    """Remove the patch and restore the original method."""
    if hasattr(Player, '_original_handle_battle_request'):
        Player._handle_battle_request = Player._original_handle_battle_request
        delattr(Player, '_original_handle_battle_request')
        logger.info("Removed patch and restored original _handle_battle_request method")
    else:
        logger.warning("Cannot remove patch: original method not found")

if __name__ == "__main__":
    apply_patch()