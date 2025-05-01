"""
Script to run battles between Pokémon agents.

This script sets up and runs battles between multiple GAIA agents with different LLM backends
(OpenAI, Claude, Gemini, Grok) and other opponents on the Pokémon Showdown server.

Enhanced with:
- Battle monitoring to ensure battles complete successfully
- Configurable timeouts for turns and total battle duration
- Response caching to reduce API calls and speed up decisions
- Automatic recovery from stalled battles
"""

import os
import asyncio
import argparse
import random
import string
import time
import logging
import sys
from datetime import datetime
from dotenv import load_dotenv
from tabulate import tabulate

from poke_env.player import RandomPlayer
from poke_env import ServerConfiguration, LocalhostServerConfiguration
from poke_env.ps_client.account_configuration import AccountConfiguration

from gaia_agent import GAIAAgent

# Apply the player patch to fix issues and add monitoring
import player_fix
player_fix.apply_patch()

# Load environment variables
load_dotenv()

# LLM Provider Constants
OPENAI = "openai"
CLAUDE = "anthropic"
GEMINI = "gemini"
GROK = "grok"

# Default LLM models
DEFAULT_MODELS = {
    OPENAI: "gpt-4o",
    CLAUDE: "claude-3-opus-20240229",
    GEMINI: "gemini-pro",
    GROK: "grok-1"  # Update with correct model name if needed
}

# Default timeouts
DEFAULT_BATTLE_TIMEOUT = player_fix.DEFAULT_BATTLE_TIMEOUT

# Track used usernames to prevent collisions
_used_usernames = set()

def generate_random_username(provider=None, length=5, max_attempts=10):
    """
    Generate a random username to avoid name collision.
    Includes the LLM provider name for easy identification.
    
    Args:
        provider: The LLM provider (openai, anthropic, gemini, grok, None)
        length: Length of the random suffix
        max_attempts: Maximum number of attempts to generate a unique username
        
    Returns:
        A unique username with provider prefixed
    """
    import random
    import string
    import uuid
    import os
    import time
    
    for attempt in range(max_attempts):
        # Generate a short random suffix with letters only
        random_suffix = ''.join(random.choice(string.ascii_lowercase) for _ in range(length))
        
        # Use current process ID for some uniqueness
        pid = os.getpid() % 100  # Use last 2 digits of process ID
        
        # Get current microsecond count for additional uniqueness (higher precision than milliseconds)
        current_us = int(time.time() * 1000000) % 10000  # Last 4 digits of current time in microseconds
        
        # Generate a short UUID part for extreme uniqueness
        uuid_part = str(uuid.uuid4())[-6:]  # Use more UUID characters
        
        # Add a random number for even more entropy
        random_num = random.randint(100, 999)
        
        # Set prefix based on provider - use clear model names
        if provider == OPENAI:
            prefix = "GPT4_"
        elif provider == CLAUDE:
            prefix = "Claude_"
        elif provider == GEMINI:
            prefix = "Gemini_"
        elif provider == GROK:
            prefix = "Grok_"
        elif provider == "random":
            prefix = "Random_"
        else:
            prefix = "Bot_"
        
        # Format: [Provider Name][Random Letters][Random Number]
        # This creates a readable, unique username
        username = f"{prefix}{random_suffix}{random_num}"
        
        # Ensure username is not longer than 18 characters (Showdown limit)
        if len(username) > 17:
            username = username[:17]
        
        # Check if this username has been used before
        if username not in _used_usernames:
            _used_usernames.add(username)
            return username
            
        # If we're still having collisions after several attempts, add more randomness
        if attempt > 3:
            length += 1
    
    # As a last resort, use the full UUID if we've exhausted our attempts
    timestamp = int(time.time())
    fallback_username = f"{prefix}{timestamp % 10000}"
    _used_usernames.add(fallback_username)
    return fallback_username

async def run_single_battle(gaia_agent, opponent, n_battles=1, turn_timeout=player_fix.DEFAULT_TURN_TIMEOUT, battle_timeout=player_fix.DEFAULT_BATTLE_TIMEOUT):
    """
    Run a battle between the GAIA agent and an opponent with improved monitoring.
    
    Args:
        gaia_agent: Your GAIA agent
        opponent: The opponent agent
        n_battles: Number of battles to run
        turn_timeout: Maximum time per turn in seconds (default: 3 minutes)
        battle_timeout: Maximum time per battle in seconds (default: 20 minutes)
        
    Returns:
        The results of the battles
    """
    # Configure logging
    logging.basicConfig(level=logging.INFO)
    
    # Patch both agents with battle monitoring
    gaia_agent = player_fix.patch_player_with_monitoring(gaia_agent, turn_timeout, battle_timeout)
    opponent = player_fix.patch_player_with_monitoring(opponent, turn_timeout, battle_timeout)
    
    print(f"\nStarting {n_battles} battle(s) between {gaia_agent.username} and {opponent.username}")
    print(f"Battle format: {getattr(gaia_agent, 'battle_format', 'Unknown')}")
    print(f"Timeouts: {turn_timeout}s per turn, {battle_timeout}s per battle")
    print("Battle will appear in the Pokémon Showdown interface at http://localhost:8000")
    print("You can view the battle by logging in as a spectator with any username\n")
    
    # Create battle monitor for progress tracking
    battle_monitor = player_fix.BattleMonitor(max_turn_time=turn_timeout, max_battle_time=battle_timeout)
    
    # Setup monitoring
    previous_battles = {}
    previous_count = 0
    start_time = time.time()
    
    # Create a task for the battle
    battle_task = asyncio.create_task(gaia_agent.battle_against(opponent, n_battles=n_battles))
    
    try:
        # Set up a timeout for the entire battle
        monitor_task = None
        
        async def monitor_battles():
            previous_battles = {}
            previous_count = 0
            
            while not battle_task.done():
                # Get current battle states
                current_battles = {}
                if hasattr(gaia_agent, '_battles'):
                    for battle_id, battle in gaia_agent._battles.items():
                        current_battles[battle_id] = battle
                        
                        # Register new battles with the monitor
                        if battle_id not in previous_battles:
                            battle_monitor.register_battle(battle_id)
                        
                        # Update battle state in monitor
                        battle_monitor.update_battle_state(battle_id, battle.turn)
                
                # Check for newly started battles
                current_count = len(current_battles)
                if current_count > previous_count:
                    battle_ids = list(current_battles.keys())
                    print(f"Battle started! Active battles: {battle_ids}")
                    previous_count = current_count
                
                # Check for completed battles
                for battle_id in list(previous_battles.keys()):
                    if battle_id not in current_battles:
                        battle_monitor.mark_battle_complete(battle_id)
                
                # Update previous battles record
                previous_battles = current_battles.copy()
                
                # Check for stalled battles
                battle_monitor.check_for_stalled_battles(gaia_agent)
                
                # Print status
                ongoing_battles = gaia_agent.n_battles_ongoing
                finished_battles = gaia_agent.n_finished_battles
                
                if ongoing_battles > 0 or finished_battles > 0:
                    elapsed = time.time() - start_time
                    print(f"Status: {ongoing_battles} ongoing, {finished_battles} finished battles (elapsed: {elapsed:.1f}s)")
                
                # Wait before next check
                await asyncio.sleep(5)  # Check every 5 seconds
        
        # Start monitor task
        monitor_task = asyncio.create_task(monitor_battles())
        
        # Wait for battle to complete with timeout
        try:
            await asyncio.wait_for(battle_task, timeout=battle_timeout)
        except asyncio.TimeoutError:
            print(f"Battle timeout exceeded ({battle_timeout}s). Forcing battle completion.")
            # Force battle completion
            for battle_id in gaia_agent._battles:
                try:
                    gaia_agent.forfeit_battle(battle_id)
                except:
                    pass
        
        # Cancel monitor task
        if monitor_task and not monitor_task.done():
            monitor_task.cancel()
            try:
                await monitor_task
            except asyncio.CancelledError:
                pass
        
    except Exception as e:
        logging.error(f"Error in battle monitoring: {e}")
        
        # Try to forfeit any remaining battles
        for battle_id in gaia_agent._battles:
            try:
                gaia_agent.forfeit_battle(battle_id)
            except:
                pass
    
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

async def run_cross_evaluation(gaia_agent, opponents, n_battles=10):
    """
    Run a cross-evaluation between the GAIA agent and multiple opponents.
    
    Args:
        gaia_agent: Your GAIA agent
        opponents: List of opponent agents
        n_battles: Number of battles to run against each opponent
        
    Returns:
        List of results for each opponent
    """
    results = []
    
    for opponent in opponents:
        # Reset the agent's state for a fresh start against each opponent
        gaia_agent.reset_battles()
        opponent.reset_battles()
        
        # Run battles against this opponent
        result = await run_single_battle(gaia_agent, opponent, n_battles)
        results.append(result)
    
    # Print summary table
    table_data = [
        [r["opponent"], f"{r['wins']}/{r['total']}", f"{r['win_rate']:.2f}%"]
        for r in results
    ]
    
    print("\nSummary:")
    print(tabulate(
        table_data,
        headers=["Opponent", "Wins/Total", "Win Rate"],
        tablefmt="grid"
    ))
    
    return results

def create_gaia_agent(provider, battle_format, server_config):
    """
    Create a GAIA agent with a specific LLM provider.
    
    Args:
        provider: The LLM provider (openai, anthropic, gemini, grok)
        battle_format: Battle format string
        server_config: Server configuration object
        
    Returns:
        A configured GAIA agent
    """
    # Generate username based on provider
    username = generate_random_username(provider)
    
    # Create account configuration
    account = AccountConfiguration(username, None)
    
    # Set environment variable for agent creation
    os.environ["LLM_PROVIDER"] = provider
    
    # Create and return the agent
    agent = GAIAAgent(
        account_configuration=account,
        battle_format=battle_format,
        server_configuration=server_config,
        start_timer_on_battle_start=True,
        avatar=None  # Set to None to avoid avatar-related issues
    )
    
    print(f"Created {provider.upper()} agent with username: {username}")
    return agent, username

async def run_tournament(agents, n_battles, format_name):
    """
    Run a tournament between multiple agents.
    
    Args:
        agents: List of (agent, username) tuples
        n_battles: Number of battles between each pair
        format_name: Battle format name
        
    Returns:
        Tournament results
    """
    results = {}
    
    # Initialize results table
    for agent, username in agents:
        results[username] = {"wins": 0, "losses": 0, "total": 0}
    
    # Run battles between all pairs of agents
    for i in range(len(agents)):
        for j in range(i+1, len(agents)):
            agent1, username1 = agents[i]
            agent2, username2 = agents[j]
            
            print(f"\nRunning {n_battles} battle(s) between {username1} and {username2}")
            
            # Reset agent states
            agent1.reset_battles()
            agent2.reset_battles()
            
            # Run the battles
            try:
                battle_task = asyncio.create_task(agent1.battle_against(agent2, n_battles=n_battles))
                await asyncio.wait_for(battle_task, timeout=DEFAULT_BATTLE_TIMEOUT * n_battles)
            except asyncio.TimeoutError:
                logging.error(f"Battle timeout exceeded. Forcing completion.")
                # Force battle completion for any remaining battles
                for battle_id in agent1._battles:
                    try:
                        agent1.forfeit_battle(battle_id)
                    except:
                        pass
            except Exception as e:
                logging.error(f"Error in battle: {e}")
            
            # Record results
            agent1_wins = agent1.n_won_battles
            agent2_wins = agent2.n_won_battles
            total = agent1.n_finished_battles
            
            results[username1]["wins"] += agent1_wins
            results[username1]["losses"] += agent2_wins
            results[username1]["total"] += total
            
            results[username2]["wins"] += agent2_wins
            results[username2]["losses"] += agent1_wins
            results[username2]["total"] += total
            
            print(f"Results: {username1} won {agent1_wins}, {username2} won {agent2_wins} out of {total} battles")
    
    # Print tournament results
    table_data = []
    for username, stats in results.items():
        win_rate = (stats["wins"] / stats["total"] * 100) if stats["total"] > 0 else 0
        table_data.append([
            username, 
            stats["wins"], 
            stats["losses"], 
            stats["total"],
            f"{win_rate:.2f}%"
        ])
    
    print("\nTournament Results:")
    print(tabulate(
        table_data,
        headers=["Agent", "Wins", "Losses", "Total", "Win Rate"],
        tablefmt="grid"
    ))
    
    return results

async def main():
    """Main entry point for the battle script."""
    parser = argparse.ArgumentParser(description="Run Pokémon battles with GAIA agent and battle monitoring")
    parser.add_argument("--battles", type=int, default=1, help="Number of battles to run")
    parser.add_argument("--format", type=str, default="gen9randombattle", help="Battle format")
    parser.add_argument("--server", type=str, default="localhost", help="Server to connect to (localhost or showdown)")
    parser.add_argument("--mode", type=str, default="ai_vs_ai", 
                        choices=["ai_vs_ai", "accept_human", "challenge_human", "tournament"], 
                        help="Battle mode: ai_vs_ai, accept_human, challenge_human, or tournament")
    parser.add_argument("--agent", type=str, default=os.getenv("LLM_PROVIDER", "openai"),
                        choices=[OPENAI, CLAUDE, GEMINI, GROK, "random"],
                        help="Agent type to use (for accept_human and challenge_human modes)")
    parser.add_argument("--agent1", type=str, default=OPENAI,
                        choices=[OPENAI, CLAUDE, GEMINI, GROK, "random"],
                        help="First agent type (for ai_vs_ai mode)")
    parser.add_argument("--agent2", type=str, default=CLAUDE,
                        choices=[OPENAI, CLAUDE, GEMINI, GROK, "random"],
                        help="Second agent type (for ai_vs_ai mode)")
    parser.add_argument("--human", type=str, default=None, help="Human username for challenge mode")
    parser.add_argument("--listen", action="store_true", help="Keep listening for challenges from humans")
    parser.add_argument("--turn-timeout", type=int, default=player_fix.DEFAULT_TURN_TIMEOUT,
                        help=f"Maximum seconds per turn (default: {player_fix.DEFAULT_TURN_TIMEOUT}s)")
    parser.add_argument("--battle-timeout", type=int, default=player_fix.DEFAULT_BATTLE_TIMEOUT,
                        help=f"Maximum seconds per battle (default: {player_fix.DEFAULT_BATTLE_TIMEOUT}s)")
    args = parser.parse_args()
    
    # Configure the server
    if args.server == "showdown":
        server_config = ServerConfiguration(
            "wss://sim3.psim.us/showdown/websocket",
            "https://play.pokemonshowdown.com/action.php?"
        )
    else:
        # Use LocalhostServerConfiguration for localhost
        server_config = LocalhostServerConfiguration
    
    # Different modes of operation
    if args.mode == "ai_vs_ai":
        # AI vs AI battle between two specific agents
        print(f"Running {args.battles} AI vs AI battles in format {args.format}")
        print(f"Timeouts: {args.turn_timeout}s per turn, {args.battle_timeout}s per battle")
        
        # Create the first agent
        if args.agent1 == "random":
            agent1_username = generate_random_username("random")
            agent1_account = AccountConfiguration(agent1_username, None)
            agent1 = RandomPlayer(
                account_configuration=agent1_account,
                battle_format=args.format,
                server_configuration=server_config,
                avatar=None
            )
            print(f"Created Random agent with username: {agent1_username}")
        else:
            agent1, agent1_username = create_gaia_agent(args.agent1, args.format, server_config)
        
        # Create the second agent
        if args.agent2 == "random":
            agent2_username = generate_random_username("random")
            agent2_account = AccountConfiguration(agent2_username, None)
            agent2 = RandomPlayer(
                account_configuration=agent2_account,
                battle_format=args.format,
                server_configuration=server_config,
                avatar=None
            )
            print(f"Created Random agent with username: {agent2_username}")
        else:
            agent2, agent2_username = create_gaia_agent(args.agent2, args.format, server_config)
        
        # Run battles with enhanced monitoring to ensure completion
        print(f"Starting monitored battle(s) with timeouts to ensure completion...")
        try:
            result = await run_single_battle(
                agent1, 
                agent2, 
                n_battles=args.battles,
                turn_timeout=args.turn_timeout,
                battle_timeout=args.battle_timeout
            )
        except Exception as e:
            logging.error(f"Error in AI vs AI battle: {e}")
            print("Battle failed. Check server connection and try restarting the server.")
        
        # Clean up resources
        if hasattr(agent1, 'close'):
            agent1.close()
        if hasattr(agent2, 'close'):
            agent2.close()
    
    elif args.mode == "tournament":
        # Tournament mode - all agents battle each other
        print(f"Running tournament with {args.battles} battles per matchup in format {args.format}")
        print(f"Timeouts: {args.turn_timeout}s per turn, {args.battle_timeout}s per battle")
        
        # Create all agents
        agents = []
        
        # Add LLM-powered agents
        for provider in [OPENAI, CLAUDE, GEMINI]:
            # Skip if API key is not set
            env_var = f"{provider.upper()}_API_KEY"
            if os.getenv(env_var):
                agent, username = create_gaia_agent(provider, args.format, server_config)
                # Apply battle monitoring to each agent
                agent = player_fix.patch_player_with_monitoring(
                    agent, 
                    args.turn_timeout, 
                    args.battle_timeout
                )
                agents.append((agent, username))
        
        # Add random agent
        random_username = generate_random_username("random")
        random_account = AccountConfiguration(random_username, None)
        random_agent = RandomPlayer(
            account_configuration=random_account,
            battle_format=args.format,
            server_configuration=server_config,
            avatar=None
        )
        # Apply battle monitoring to random agent too
        random_agent = player_fix.patch_player_with_monitoring(
            random_agent, 
            args.turn_timeout, 
            args.battle_timeout
        )
        print(f"Created Random agent with username: {random_username}")
        agents.append((random_agent, random_username))
        
        # Run battles between all pairs of agents
        results = {}
        
        # Initialize results table
        for agent, username in agents:
            results[username] = {"wins": 0, "losses": 0, "total": 0}
        
        # Run battles between all pairs of agents
        for i in range(len(agents)):
            for j in range(i+1, len(agents)):
                agent1, username1 = agents[i]
                agent2, username2 = agents[j]
                
                print(f"\nRunning {args.battles} battle(s) between {username1} and {username2}")
                
                # Run battles with enhanced monitoring
                try:
                    battle_result = await run_single_battle(
                        agent1, 
                        agent2, 
                        args.battles,
                        turn_timeout=args.turn_timeout,
                        battle_timeout=args.battle_timeout
                    )
                except Exception as e:
                    logging.error(f"Error in tournament battle: {e}")
                    # Continue with next battle pair on error
                
                # Record results
                agent1_wins = agent1.n_won_battles
                agent2_wins = agent2.n_won_battles
                total = agent1.n_finished_battles
                
                results[username1]["wins"] += agent1_wins
                results[username1]["losses"] += agent2_wins
                results[username1]["total"] += total
                
                results[username2]["wins"] += agent2_wins
                results[username2]["losses"] += agent1_wins
                results[username2]["total"] += total
        
        # Print tournament results
        table_data = []
        for username, stats in results.items():
            win_rate = (stats["wins"] / stats["total"] * 100) if stats["total"] > 0 else 0
            table_data.append([
                username, 
                stats["wins"], 
                stats["losses"], 
                stats["total"],
                f"{win_rate:.2f}%"
            ])
        
        print("\nTournament Results:")
        print(tabulate(
            table_data,
            headers=["Agent", "Wins", "Losses", "Total", "Win Rate"],
            tablefmt="grid"
        ))
        
        # Clean up resources
        for agent, _ in agents:
            if hasattr(agent, 'close'):
                agent.close()
    
    elif args.mode == "accept_human":
        # Accept challenges from humans
        # Create the agent based on specified type
        if args.agent == "random":
            agent_username = generate_random_username("Random")
            agent_account = AccountConfiguration(agent_username, None)
            agent = RandomPlayer(
                account_configuration=agent_account,
                battle_format=args.format,
                server_configuration=server_config,
                avatar=None
            )
            print(f"Created Random agent with username: {agent_username}")
        else:
            agent, agent_username = create_gaia_agent(args.agent, args.format, server_config)
        
        print(f"Agent {agent_username} is listening for challenges...")
        print(f"Go to http://localhost:8000 and challenge {agent_username} to a battle!")
        print(f"Battle format: {args.format}")
        
        if args.listen:
            print("Press Ctrl+C to stop listening")
            while True:
                try:
                    await agent.accept_challenges(None, 1)
                    await asyncio.sleep(5)  # Wait a bit before accepting another challenge
                except KeyboardInterrupt:
                    print("\nStopping challenge listener...")
                    break
        else:
            # Accept a single challenge
            await agent.accept_challenges(None, 1)
            print("Challenge completed.")
        
        # Clean up resources
        if hasattr(agent, 'close'):
            agent.close()
    
    elif args.mode == "challenge_human":
        # Challenge a specific human
        if not args.human:
            print("Error: You must specify a human username with --human")
            return
        
        # Create the agent based on specified type
        if args.agent == "random":
            agent_username = generate_random_username("Random")
            agent_account = AccountConfiguration(agent_username, None)
            agent = RandomPlayer(
                account_configuration=agent_account,
                battle_format=args.format,
                server_configuration=server_config,
                avatar=None
            )
            print(f"Created Random agent with username: {agent_username}")
        else:
            agent, agent_username = create_gaia_agent(args.agent, args.format, server_config)
        
        print(f"Agent {agent_username} is challenging {args.human}...")
        print(f"Make sure {args.human} is logged in to http://localhost:8000")
        
        # Send challenge to the human player
        await agent.send_challenges(args.human, n_challenges=1)
        print("Challenge sent and completed.")
        
        # Clean up resources
        if hasattr(agent, 'close'):
            agent.close()
    
    print("\nBattles completed. Check the results above.")

if __name__ == "__main__":
    # Set up asyncio event loop and run the main function
    asyncio.run(main())