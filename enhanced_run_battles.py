#!/usr/bin/env python3
"""
Enhanced battle runner with debugging and monitoring features for Pokémon battles.
"""

import os
import sys
import asyncio
import time
import argparse
import logging
import traceback
import json
from typing import Dict, List, Optional, Any, Set
import random
import string
from datetime import datetime, timedelta
from collections import defaultdict

# Apply the enhanced player fix patch first
from enhanced_player_fix import apply_patch
apply_patch()

# Import the original run_battles module for its functionality
import run_battles

# Configure logging
DEBUG = os.environ.get('DEBUG', '0').lower() in ('1', 'true', 'yes', 'on')
LOG_LEVEL = logging.DEBUG if DEBUG else logging.INFO

logging.basicConfig(
    level=LOG_LEVEL,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(f"battle_debug_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
    ]
)

logger = logging.getLogger('enhanced_battles')
logger.info(f"Debug mode: {'enabled' if DEBUG else 'disabled'}")

# Monkey patch the run_battles username generation to ensure even more uniqueness
original_generate_username = run_battles.generate_random_username

def enhanced_generate_random_username(provider=None, length=5):
    """
    Enhanced random username generation with better uniqueness guarantees.
    
    Args:
        provider: The LLM provider (openai, anthropic, gemini, grok, None)
        length: Length of the random suffix
        
    Returns:
        A unique username with provider prefixed and guaranteed uniqueness
    """
    # Get timestamp components for uniqueness
    timestamp = int(time.time())
    millis = int(time.time() * 1000) % 1000
    
    # Get a truly random suffix
    random_suffix = ''.join(random.choice(string.ascii_lowercase) for _ in range(length))
    
    # Use process ID
    pid = os.getpid() % 100  # Last 2 digits
    
    # Generate a unique hash based on all components
    unique_hash = hash(f"{provider}_{random_suffix}_{timestamp}_{pid}") % 1000
    
    # Set prefix based on provider - use very short prefixes
    if provider == run_battles.OPENAI:
        prefix = "O"
    elif provider == run_battles.CLAUDE:
        prefix = "C"
    elif provider == run_battles.GEMINI:
        prefix = "G"
    elif provider == run_battles.GROK:
        prefix = "K"
    elif provider == "random":
        prefix = "R"
    else:
        prefix = "B"
    
    # Format: [Provider Letter][Random Letters][Unique Hash]
    username = f"{prefix}{random_suffix}{unique_hash}"
    
    # Ensure username is not longer than 17 characters (Showdown limit is 18)
    if len(username) > 17:
        username = username[:17]
    
    logger.debug(f"Generated username: {username} for provider: {provider}")    
    return username

# Apply the monkey patch
run_battles.generate_random_username = enhanced_generate_random_username


class BattleMonitor:
    """
    A class to monitor and log battle progress for debugging purposes.
    
    This class tracks:
    - Active battles
    - Battle progress (turns, actions)
    - Error counts
    - Timeouts and stalled battles
    """
    
    def __init__(self, timeout_seconds=300):
        self.active_battles = {}  # battle_id -> battle info
        self.completed_battles = {}  # battle_id -> battle result
        self.battle_errors = defaultdict(list)  # battle_id -> list of errors
        self.battle_actions = defaultdict(list)  # battle_id -> list of actions
        self.timeout_seconds = timeout_seconds
        self.stalled_battles = set()  # Set of stalled battle_ids
        
        # Initialize stats
        self.stats = {
            "battles_started": 0,
            "battles_completed": 0,
            "battles_error": 0,
            "battles_timeout": 0,
            "battles_stalled": 0,
            "total_turns": 0,
            "max_turns": 0,
            "avg_battle_duration": 0,
        }
    
    def start_battle(self, battle_id, player1, player2):
        """Record a new battle starting."""
        logger.info(f"Battle starting: {battle_id} between {player1} and {player2}")
        self.active_battles[battle_id] = {
            "battle_id": battle_id,
            "player1": player1,
            "player2": player2,
            "start_time": datetime.now(),
            "last_action_time": datetime.now(),
            "current_turn": 0,
            "status": "active"
        }
        self.stats["battles_started"] += 1
    
    def record_action(self, battle_id, action, player=None):
        """Record an action in a battle."""
        if battle_id not in self.active_battles:
            logger.warning(f"Trying to record action for unknown battle: {battle_id}")
            return
            
        # Update the last action time
        self.active_battles[battle_id]["last_action_time"] = datetime.now()
        
        # Record the action
        self.battle_actions[battle_id].append({
            "time": datetime.now().isoformat(),
            "player": player,
            "action": action
        })
        
        logger.debug(f"Battle {battle_id}: {player if player else 'System'} - {action}")
    
    def record_turn(self, battle_id, turn_number):
        """Record a new turn in a battle."""
        if battle_id not in self.active_battles:
            logger.warning(f"Trying to record turn for unknown battle: {battle_id}")
            return
            
        # Update turn information
        self.active_battles[battle_id]["current_turn"] = turn_number
        self.active_battles[battle_id]["last_action_time"] = datetime.now()
        
        logger.info(f"Battle {battle_id}: Turn {turn_number}")
        
        # Record as an action
        self.record_action(battle_id, f"Turn {turn_number}")
    
    def record_error(self, battle_id, error_message, error_type=None, stack_trace=None):
        """Record an error in a battle."""
        if battle_id not in self.active_battles and battle_id not in self.completed_battles:
            logger.warning(f"Trying to record error for unknown battle: {battle_id}")
            
        error_info = {
            "time": datetime.now().isoformat(),
            "error_message": error_message,
            "error_type": error_type or "Unknown",
            "stack_trace": stack_trace
        }
        
        self.battle_errors[battle_id].append(error_info)
        logger.error(f"Battle {battle_id}: Error - {error_message}")
        
        if stack_trace and DEBUG:
            logger.debug(f"Stack trace for battle {battle_id}:\n{stack_trace}")
    
    def complete_battle(self, battle_id, winner=None, reason=None):
        """Record a battle as completed."""
        if battle_id not in self.active_battles:
            logger.warning(f"Trying to complete unknown battle: {battle_id}")
            return
            
        battle_info = self.active_battles.pop(battle_id)
        end_time = datetime.now()
        duration = (end_time - battle_info["start_time"]).total_seconds()
        
        result = {
            **battle_info,
            "end_time": end_time,
            "duration": duration,
            "winner": winner,
            "completion_reason": reason or "normal"
        }
        
        self.completed_battles[battle_id] = result
        self.stats["battles_completed"] += 1
        self.stats["total_turns"] += battle_info["current_turn"]
        
        if battle_info["current_turn"] > self.stats["max_turns"]:
            self.stats["max_turns"] = battle_info["current_turn"]
            
        # Update average duration
        if self.stats["battles_completed"] > 0:
            self.stats["avg_battle_duration"] = (self.stats["avg_battle_duration"] * 
                                               (self.stats["battles_completed"] - 1) + 
                                               duration) / self.stats["battles_completed"]
        
        logger.info(f"Battle {battle_id} completed. Winner: {winner or 'unknown'}. Duration: {duration:.1f}s, Turns: {battle_info['current_turn']}")
        
    def check_timeouts(self):
        """Check for timed out or stalled battles."""
        now = datetime.now()
        for battle_id, battle_info in list(self.active_battles.items()):
            # Check for timeout
            duration = (now - battle_info["start_time"]).total_seconds()
            if duration > self.timeout_seconds:
                logger.warning(f"Battle {battle_id} timed out after {duration:.1f}s")
                self.complete_battle(battle_id, reason="timeout")
                self.stats["battles_timeout"] += 1
                continue
                
            # Check for stalled battle (no action for a while)
            inactivity = (now - battle_info["last_action_time"]).total_seconds()
            if inactivity > 60 and battle_id not in self.stalled_battles:  # 1 minute with no action
                logger.warning(f"Battle {battle_id} appears stalled. No action for {inactivity:.1f}s")
                self.stalled_battles.add(battle_id)
                self.stats["battles_stalled"] += 1
    
    def print_battle_status(self, battle_id=None):
        """Print detailed status of a specific battle or all battles."""
        if battle_id:
            if battle_id in self.active_battles:
                battle_info = self.active_battles[battle_id]
                status = "ACTIVE"
            elif battle_id in self.completed_battles:
                battle_info = self.completed_battles[battle_id]
                status = "COMPLETED"
            else:
                logger.warning(f"Unknown battle ID: {battle_id}")
                return
                
            logger.info(f"Battle {battle_id} - {status}")
            logger.info(f"  Players: {battle_info['player1']} vs {battle_info['player2']}")
            logger.info(f"  Current turn: {battle_info['current_turn']}")
            logger.info(f"  Started: {battle_info['start_time'].isoformat()}")
            
            if status == "COMPLETED":
                logger.info(f"  Ended: {battle_info['end_time'].isoformat()}")
                logger.info(f"  Duration: {battle_info['duration']:.1f}s")
                logger.info(f"  Winner: {battle_info.get('winner', 'unknown')}")
                
            # Show errors
            if battle_id in self.battle_errors:
                logger.info(f"  Errors: {len(self.battle_errors[battle_id])}")
                
            # Show recent actions (last 5)
            if battle_id in self.battle_actions:
                actions = self.battle_actions[battle_id]
                logger.info(f"  Recent actions:")
                for action in actions[-5:]:
                    logger.info(f"    {action['time']}: {action.get('player', 'System')} - {action['action']}")
        else:
            # Print summary of all battles
            logger.info("Active battles:")
            for battle_id, info in self.active_battles.items():
                duration = (datetime.now() - info["start_time"]).total_seconds()
                logger.info(f"  {battle_id}: Turn {info['current_turn']}, Duration: {duration:.1f}s")
    
    def print_summary(self):
        """Print a summary of all battles and statistics."""
        logger.info("========== Battle Monitor Summary ==========")
        logger.info(f"Total battles started: {self.stats['battles_started']}")
        logger.info(f"Battles completed: {self.stats['battles_completed']}")
        logger.info(f"Battles with errors: {len(self.battle_errors)}")
        logger.info(f"Battles timed out: {self.stats['battles_timeout']}")
        logger.info(f"Battles stalled: {self.stats['battles_stalled']}")
        logger.info(f"Average battle duration: {self.stats['avg_battle_duration']:.1f}s")
        logger.info(f"Maximum turns in a battle: {self.stats['max_turns']}")
        logger.info(f"Currently active battles: {len(self.active_battles)}")
        logger.info("===========================================")


# Create a global battle monitor
battle_monitor = BattleMonitor()


async def monitor_battles(check_interval=10):
    """
    Task to monitor battles and check for timeouts/stalls.
    
    Args:
        check_interval: How often to check for timeouts (seconds)
    """
    while True:
        try:
            battle_monitor.check_timeouts()
            if DEBUG:
                logger.debug(f"Active battles: {len(battle_monitor.active_battles)}")
            await asyncio.sleep(check_interval)
        except Exception as e:
            logger.error(f"Error in battle monitor: {str(e)}")
            traceback.print_exc()
            await asyncio.sleep(check_interval)


# Monkey patch the run_single_battle function to add monitoring
original_run_single_battle = run_battles.run_single_battle

async def enhanced_run_single_battle(gaia_agent, opponent, n_battles=1):
    """
    Enhanced battle runner with monitoring and logging.
    
    Args:
        gaia_agent: Your GAIA agent
        opponent: The opponent agent
        n_battles: Number of battles to run
        
    Returns:
        The results of the battles
    """
    try:
        # Configure logging
        logging.basicConfig(level=LOG_LEVEL)
        
        print(f"\nStarting {n_battles} battle(s) between {gaia_agent.username} and {opponent.username}")
        print(f"Battle format: {gaia_agent._battle_format}")
        print("Battle will appear in the Pokémon Showdown interface at http://localhost:8000")
        
        # Setup monitoring
        previous_count = 0
        
        # Start the battle
        battle_coroutine = gaia_agent.battle_against(opponent, n_battles=n_battles)
        
        # Monitor battle progress
        while not battle_coroutine.done():
            current_battles = len(gaia_agent._battles)
            if current_battles > previous_count:
                battle_ids = list(gaia_agent._battles.keys())
                new_battles = battle_ids[previous_count:]
                print(f"Battle(s) started! New battle IDs: {new_battles}")
                
                # Register new battles with monitor
                for battle_id in new_battles:
                    battle_monitor.start_battle(
                        battle_id, 
                        gaia_agent.username, 
                        opponent.username
                    )
                
                previous_count = current_battles
            
            # Check battle progress
            ongoing_battles = gaia_agent.n_battles_ongoing
            finished_battles = gaia_agent.n_finished_battles
            
            if ongoing_battles > 0 or finished_battles > 0:
                status_msg = f"Status: {ongoing_battles} ongoing, {finished_battles} finished battles"
                print(status_msg)
                logger.info(status_msg)
            
            # Check and record current battle state for each active battle
            for battle_id, battle in gaia_agent._battles.items():
                if battle_id in battle_monitor.active_battles:
                    # Record current turn if it changed
                    current_turn = battle.turn
                    prev_turn = battle_monitor.active_battles[battle_id]["current_turn"]
                    if current_turn > prev_turn:
                        battle_monitor.record_turn(battle_id, current_turn)
                    
                    # Record battle state
                    if DEBUG:
                        active_pokemon = battle.active_pokemon.species if battle.active_pokemon else "None"
                        opponent_pokemon = battle.opponent_active_pokemon.species if battle.opponent_active_pokemon else "None"
                        logger.debug(f"Battle {battle_id}: {active_pokemon} vs {opponent_pokemon}")
            
            await asyncio.sleep(2)  # Check every 2 seconds
        
        await battle_coroutine  # Ensure coroutine completes
        
        # Mark all battles as completed
        for battle_id in list(battle_monitor.active_battles.keys()):
            # Find winner if possible
            winner = None
            if battle_id in gaia_agent._battles:
                battle = gaia_agent._battles[battle_id]
                if battle.won:
                    winner = gaia_agent.username
                elif battle.lost:
                    winner = opponent.username
                    
            battle_monitor.complete_battle(battle_id, winner=winner)
        
        # Print results
        if gaia_agent.n_finished_battles > 0:
            print(f"\nResults against {opponent.__class__.__name__}:")
            print(f"GAIA Agent won {gaia_agent.n_won_battles} out of {gaia_agent.n_finished_battles} battles")
            print(f"Win rate: {(gaia_agent.n_won_battles / gaia_agent.n_finished_battles) * 100:.2f}%")
        else:
            print("\nNo battles were completed. Check if the server is running correctly.")
        
        return {
            "opponent": opponent.__class__.__name__,
            "wins": gaia_agent.n_won_battles,
            "total": gaia_agent.n_finished_battles,
            "win_rate": (gaia_agent.n_won_battles / gaia_agent.n_finished_battles) * 100 if gaia_agent.n_finished_battles > 0 else 0
        }
        
    except Exception as e:
        logger.error(f"Error in enhanced_run_single_battle: {str(e)}")
        stack_trace = traceback.format_exc()
        logger.error(f"Stack trace: {stack_trace}")
        
        # Try to run the original function as fallback
        logger.info("Falling back to original run_single_battle function")
        return await original_run_single_battle(gaia_agent, opponent, n_battles)


# Apply monkey patch
run_battles.run_single_battle = enhanced_run_single_battle


async def enhanced_main():
    """Enhanced main function with monitoring and debugging features."""
    parser = argparse.ArgumentParser(description="Enhanced Pokémon battle runner with debugging")
    parser.add_argument("--battles", type=int, default=10, help="Number of battles to run")
    parser.add_argument("--format", type=str, default="gen9randombattle", help="Battle format")
    parser.add_argument("--server", type=str, default="localhost", help="Server to connect to (localhost or showdown)")
    parser.add_argument("--mode", type=str, default="ai_vs_ai", 
                        choices=["ai_vs_ai", "accept_human", "challenge_human", "tournament"], 
                        help="Battle mode: ai_vs_ai, accept_human, challenge_human, or tournament")
    parser.add_argument("--agent", type=str, default=os.getenv("LLM_PROVIDER", "openai"),
                        choices=[run_battles.OPENAI, run_battles.CLAUDE, run_battles.GEMINI, run_battles.GROK, "random"],
                        help="Agent type to use (for accept_human and challenge_human modes)")
    parser.add_argument("--agent1", type=str, default=run_battles.OPENAI,
                        choices=[run_battles.OPENAI, run_battles.CLAUDE, run_battles.GEMINI, run_battles.GROK, "random"],
                        help="First agent type (for ai_vs_ai mode)")
    parser.add_argument("--agent2", type=str, default=run_battles.CLAUDE,
                        choices=[run_battles.OPENAI, run_battles.CLAUDE, run_battles.GEMINI, run_battles.GROK, "random"],
                        help="Second agent type (for ai_vs_ai mode)")
    parser.add_argument("--human", type=str, default=None, help="Human username for challenge mode")
    parser.add_argument("--listen", action="store_true", help="Keep listening for challenges from humans")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode with verbose logging")
    args = parser.parse_args()
    
    if args.debug:
        # Enable debug mode globally
        global DEBUG
        DEBUG = True
        logger.setLevel(logging.DEBUG)
        logging.getLogger('enhanced_player_fix').setLevel(logging.DEBUG)
        logging.getLogger('poke_env').setLevel(logging.DEBUG)
        os.environ['DEBUG'] = '1'
        logger.debug("Debug mode enabled via command line argument")
    
    # Start the battle monitor task
    monitor_task = asyncio.create_task(monitor_battles())
    
    try:
        # Record start time
        start_time = time.time()
        logger.info(f"Starting enhanced battle runner with mode: {args.mode}")
        
        # Print battle configuration
        logger.info(f"Battle Configuration:")
        logger.info(f"  Mode: {args.mode}")
        logger.info(f"  Battles: {args.battles}")
        logger.info(f"  Format: {args.format}")
        logger.info(f"  Server: {args.server}")
        
        if args.mode == "ai_vs_ai":
            logger.info(f"  Agent 1: {args.agent1}")
            logger.info(f"  Agent 2: {args.agent2}")
        
        # Run the original main function with our arguments
        await run_battles.main()
        
        # Print battle monitor summary
        battle_monitor.print_summary()
        
        # Log completion time
        elapsed = time.time() - start_time
        logger.info(f"Enhanced battle runner completed in {elapsed:.2f} seconds")
        
    except Exception as e:
        logger.error(f"Error in enhanced_main: {str(e)}")
        stack_trace = traceback.format_exc()
        logger.error(f"Stack trace: {stack_trace}")
    finally:
        # Clean up the monitor task
        monitor_task.cancel()
        try:
            await monitor_task
        except asyncio.CancelledError:
            pass


if __name__ == "__main__":
    # Set up asyncio event loop and run the enhanced main function
    asyncio.run(enhanced_main())