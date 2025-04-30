#!/usr/bin/env python3
"""
Fast battle runner for Pokémon battles with reduced latency and LLM usage.
"""

import os
import sys
import asyncio
import argparse
import logging
import time
from dotenv import load_dotenv

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(f"battle_debug_{time.strftime('%Y%m%d_%H%M%S')}.log")
    ]
)

logger = logging.getLogger('fast_battles')

# Apply the player fixes and speed optimizations
from enhanced_player_fix import apply_patch
apply_patch()

# Apply battle speedups
from battle_speedup import apply_speedups
accelerator = apply_speedups()

# Import original battle runner
import run_battles

# Load environment variables
load_dotenv()

# Constants
OPENAI = "openai"
CLAUDE = "anthropic"
GEMINI = "gemini"
GROK = "grok"
RANDOM = "random"
SPEED = "speed"  # New agent type for maximum speed

# Battle status tracking
battle_stats = {
    "started": 0,
    "completed": 0,
    "turn_counts": [],
    "timeout_battles": 0,
    "start_time": None,
    "end_time": None
}

def print_battle_stats():
    """Print statistics about the battles."""
    if not battle_stats["turn_counts"]:
        logger.info("No battle statistics available")
        return
        
    duration = (battle_stats["end_time"] - battle_stats["start_time"]).total_seconds()
    avg_turns = sum(battle_stats["turn_counts"]) / len(battle_stats["turn_counts"])
    max_turns = max(battle_stats["turn_counts"])
    min_turns = min(battle_stats["turn_counts"])
    
    logger.info("\n===== Battle Statistics =====")
    logger.info(f"Total battles: {battle_stats['started']}")
    logger.info(f"Completed battles: {battle_stats['completed']}")
    logger.info(f"Timeout battles: {battle_stats['timeout_battles']}")
    logger.info(f"Total duration: {duration:.1f}s")
    logger.info(f"Average turns per battle: {avg_turns:.1f}")
    logger.info(f"Max turns: {max_turns}")
    logger.info(f"Min turns: {min_turns}")
    logger.info(f"Cache hits: {accelerator.cache_hit_count}")
    logger.info(f"Cache misses: {accelerator.cache_miss_count}")
    logger.info(f"Cache hit rate: {accelerator.cache_hit_count / (accelerator.cache_hit_count + accelerator.cache_miss_count) * 100:.1f}%")
    logger.info("=============================\n")

class SpeedAgent(run_battles.RandomPlayer):
    """
    An ultra-fast agent that makes instant decisions based on heuristics.
    This agent never uses LLMs and replies instantly for maximum battle speed.
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        logger.info(f"Created SpeedAgent with username: {self.username}")
    
    async def choose_move(self, battle):
        """
        Choose a move instantly using heuristics.
        """
        # Register battle activity with the accelerator
        if hasattr(accelerator, 'update_battle_activity'):
            accelerator.update_battle_activity(battle.battle_tag)
        
        # Use the accelerator's best move function
        fast_decision = accelerator.get_best_move(battle)
        if fast_decision:
            logger.debug(f"SpeedAgent using accelerator decision for battle {battle.battle_tag}")
            return fast_decision
            
        # Fallback to random moves if accelerator fails
        logger.debug(f"SpeedAgent falling back to random move for battle {battle.battle_tag}")
        return self.choose_random_move(battle)

def create_agent(agent_type, battle_format, server_config):
    """
    Create an agent based on the specified type.
    
    Args:
        agent_type: Type of agent to create (openai, anthropic, gemini, random, speed)
        battle_format: Battle format to use
        server_config: Server configuration
        
    Returns:
        The created agent
    """
    if agent_type == SPEED:
        # Create a pure speed-optimized agent that doesn't use LLMs
        username = run_battles.generate_random_username("SpeedA")
        from poke_env.player import AccountConfiguration
        account = AccountConfiguration(username, None)
        
        agent = SpeedAgent(
            account_configuration=account,
            battle_format=battle_format,
            server_configuration=server_config,
            avatar=None
        )
        logger.info(f"Created SPEED agent with username: {username}")
        return agent, username
    else:
        # Use the original function for other agent types
        return run_battles.create_gaia_agent(agent_type, battle_format, server_config)

# Patched version of run_single_battle with improved monitoring
async def fast_run_single_battle(gaia_agent, opponent, n_battles=1):
    """
    Run battles with improved speed and monitoring.
    
    Args:
        gaia_agent: Your GAIA agent
        opponent: The opponent agent
        n_battles: Number of battles to run
        
    Returns:
        The results of the battles
    """
    # Configure logging
    logging.basicConfig(level=logging.INFO)
    
    print(f"\nStarting {n_battles} battle(s) between {gaia_agent.username} and {opponent.username}")
    print(f"Battle format: {gaia_agent._battle_format}")
    print("Battle will appear in the Pokémon Showdown interface at http://localhost:8000")
    
    # Initialize stats
    battle_stats["start_time"] = time.time()
    battle_stats["started"] = n_battles
    
    # Setup monitoring
    previous_count = 0
    battle_turn_tracker = {}  # battle_id -> turn_count
    
    # Start the battle
    battle_coroutine = gaia_agent.battle_against(opponent, n_battles=n_battles)
    
    # Monitor battle progress
    while not battle_coroutine.done():
        current_battles = list(gaia_agent._battles.items())
        
        if len(current_battles) > previous_count:
            battle_ids = [battle_id for battle_id, _ in current_battles]
            new_battles = battle_ids[previous_count:]
            print(f"Battle(s) started! New battle IDs: {new_battles}")
            
            # Initialize turn tracking for new battles
            for battle_id in new_battles:
                battle_turn_tracker[battle_id] = 0
                
            previous_count = len(current_battles)
        
        # Check battle progress
        ongoing_battles = gaia_agent.n_battles_ongoing
        finished_battles = gaia_agent.n_finished_battles
        
        if ongoing_battles > 0 or finished_battles > 0:
            print(f"Status: {ongoing_battles} ongoing, {finished_battles} finished battles")
        
        # Check and record turn counts for each active battle
        for battle_id, battle in current_battles:
            current_turn = battle.turn
            if battle_id in battle_turn_tracker and current_turn > battle_turn_tracker[battle_id]:
                prev_turn = battle_turn_tracker[battle_id]
                battle_turn_tracker[battle_id] = current_turn
                print(f"Battle {battle_id}: Turn {prev_turn} → {current_turn}")
                
                # Print active Pokémon matchup
                active = battle.active_pokemon.species if battle.active_pokemon else "None"
                opponent_active = battle.opponent_active_pokemon.species if battle.opponent_active_pokemon else "None"
                print(f"  {active} vs {opponent_active}")
        
        await asyncio.sleep(1)  # Check every 1 second
    
    # Ensure coroutine completes
    await battle_coroutine
    
    # Record completion stats
    battle_stats["end_time"] = time.time()
    battle_stats["completed"] = gaia_agent.n_finished_battles
    
    # Record turn counts for completed battles
    for battle_id, turn_count in battle_turn_tracker.items():
        if turn_count > 0:  # Only add if battle progressed
            battle_stats["turn_counts"].append(turn_count)
    
    # Print results
    if gaia_agent.n_finished_battles > 0:
        print(f"\nResults against {opponent.__class__.__name__}:")
        print(f"GAIA Agent won {gaia_agent.n_won_battles} out of {gaia_agent.n_finished_battles} battles")
        print(f"Win rate: {(gaia_agent.n_won_battles / gaia_agent.n_finished_battles) * 100:.2f}%")
    else:
        print("\nNo battles were completed. Check if the server is running correctly.")
    
    # Print battle statistics
    print_battle_stats()
    
    return {
        "opponent": opponent.__class__.__name__,
        "wins": gaia_agent.n_won_battles,
        "total": gaia_agent.n_finished_battles,
        "win_rate": (gaia_agent.n_won_battles / gaia_agent.n_finished_battles) * 100 if gaia_agent.n_finished_battles > 0 else 0
    }

async def main():
    """Main entry point for the fast battle script."""
    parser = argparse.ArgumentParser(description="Run fast Pokémon battles")
    parser.add_argument("--battles", type=int, default=10, help="Number of battles to run")
    parser.add_argument("--format", type=str, default="gen9randombattle", help="Battle format")
    parser.add_argument("--server", type=str, default="localhost", help="Server to connect to (localhost or showdown)")
    parser.add_argument("--mode", type=str, default="ai_vs_ai", 
                      choices=["ai_vs_ai", "accept_human", "challenge_human", "tournament", "speed_test"], 
                      help="Battle mode")
    parser.add_argument("--agent", type=str, default=os.getenv("LLM_PROVIDER", "speed"),
                      choices=[OPENAI, CLAUDE, GEMINI, GROK, RANDOM, SPEED],
                      help="Agent type for single agent modes")
    parser.add_argument("--agent1", type=str, default=SPEED,
                      choices=[OPENAI, CLAUDE, GEMINI, GROK, RANDOM, SPEED],
                      help="First agent type for ai_vs_ai mode")
    parser.add_argument("--agent2", type=str, default=SPEED,
                      choices=[OPENAI, CLAUDE, GEMINI, GROK, RANDOM, SPEED],
                      help="Second agent type for ai_vs_ai mode")
    parser.add_argument("--human", type=str, default=None, help="Human username for challenge mode")
    parser.add_argument("--listen", action="store_true", help="Keep listening for challenges from humans")
    parser.add_argument("--debug", action="store_true", help="Enable debug output")
    args = parser.parse_args()
    
    # Configure debug mode
    if args.debug:
        logger.setLevel(logging.DEBUG)
        logging.getLogger('battle_speedup').setLevel(logging.DEBUG)
    
    # Configure the server
    if args.server == "showdown":
        server_config = run_battles.ServerConfiguration(
            "wss://sim3.psim.us/showdown/websocket",
            "https://play.pokemonshowdown.com/action.php?"
        )
    else:
        server_config = run_battles.LocalhostServerConfiguration
    
    # Special mode for speed testing
    if args.mode == "speed_test":
        logger.info("Running speed test battles with fast agents")
        
        # Create two speed agents for maximum battle throughput
        agent1, agent1_username = create_agent(SPEED, args.format, server_config)
        agent2, agent2_username = create_agent(SPEED, args.format, server_config)
        
        # Run battles
        await fast_run_single_battle(agent1, agent2, args.battles)
        
        # Clean up
        if hasattr(agent1, 'close'):
            agent1.close()
        if hasattr(agent2, 'close'):
            agent2.close()
    
    # AI vs AI battle between two specific agents
    elif args.mode == "ai_vs_ai":
        logger.info(f"Running {args.battles} AI vs AI battles in format {args.format}")
        
        # Create the first agent
        agent1, agent1_username = create_agent(args.agent1, args.format, server_config)
        
        # Create the second agent
        agent2, agent2_username = create_agent(args.agent2, args.format, server_config)
        
        # Run battles
        await fast_run_single_battle(agent1, agent2, args.battles)
        
        # Clean up
        if hasattr(agent1, 'close'):
            agent1.close()
        if hasattr(agent2, 'close'):
            agent2.close()
    
    # Other modes (tournament, human challenges) use the original run_battles behavior
    else:
        # Set the run_single_battle function to our optimized version
        run_battles.run_single_battle = fast_run_single_battle
        
        # Patch the create_gaia_agent function
        original_create_gaia_agent = run_battles.create_gaia_agent
        run_battles.create_gaia_agent = create_agent
        
        # Run original main with our patches applied
        await run_battles.main()
        
        # Restore original function (cleanup)
        run_battles.create_gaia_agent = original_create_gaia_agent

if __name__ == "__main__":
    # Set up asyncio event loop and run the main function
    asyncio.run(main())