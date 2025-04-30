"""
Simplified deployment script for Pokémon Battle Agent with GAIA.
This script is designed to work with Hugging Face Spaces or other deployment platforms.
"""

import os
import asyncio
from time import sleep
import random
import string
import gradio as gr
from dotenv import load_dotenv

from poke_env.player import RandomPlayer
from poke_env import ServerConfiguration
from poke_env.ps_client.account_configuration import AccountConfiguration

from gaia_agent import GAIAAgent

# Load environment variables
load_dotenv()

# LLM Provider Constants
OPENAI = "openai"
CLAUDE = "anthropic"
GEMINI = "gemini"
GROK = "grok"
RANDOM = "random"

# Default LLM models
DEFAULT_MODELS = {
    OPENAI: "gpt-4o",
    CLAUDE: "claude-3-opus-20240229",
    GEMINI: "gemini-pro",
    GROK: "grok-1"  # Update with correct model name if needed
}

def generate_random_username(provider=None, length=8):
    """
    Generate a random username to avoid name collision.
    Includes the LLM provider name for easy identification.
    
    Args:
        provider: The LLM provider (openai, anthropic, gemini, grok, None)
        length: Length of the random suffix
        
    Returns:
        A unique username with provider prefixed
    """
    # Use microsecond-level timestamp and random UUID for maximum uniqueness
    import uuid
    timestamp = int(time.time() * 1000) % 1000000  # Use microsecond precision
    random_suffix = str(uuid.uuid4())[:length]
    
    # Set prefix based on provider
    if provider == OPENAI:
        prefix = "GPT"
    elif provider == CLAUDE:
        prefix = "CLD"
    elif provider == GEMINI:
        prefix = "GEM"
    elif provider == GROK:
        prefix = "GRK"
    elif provider == RANDOM:
        prefix = "RND"
    else:
        prefix = "BOT"
        
    return f"{prefix}{random_suffix}{timestamp}"

# Global variables to track the agent state
AGENT = None
AGENT_USERNAME = None
AGENT_TYPE = None
BATTLE_FORMAT = os.getenv("BATTLE_FORMAT", "gen9randombattle")
BATTLE_SERVER = os.getenv("SHOWDOWN_SERVER_URL", "ws://localhost:8000/showdown/websocket")
BATTLE_AUTH = os.getenv("SHOWDOWN_AUTHENTICATION_URL", "https://play.pokemonshowdown.com/action.php?")

async def create_agent(agent_type=OPENAI):
    """
    Create and return a new agent.
    
    Args:
        agent_type: Type of agent to create (openai, anthropic, gemini, grok, random)
        
    Returns:
        Tuple of (agent, username)
    """
    global AGENT, AGENT_USERNAME, AGENT_TYPE
    
    # Clean up existing agent if there is one
    if AGENT:
        AGENT.close()
    
    # Configure the server
    server_config = ServerConfiguration(BATTLE_SERVER, BATTLE_AUTH)
    
    # Generate a new username
    AGENT_USERNAME = generate_random_username(agent_type)
    
    # Create account with no password for local development
    account = AccountConfiguration(AGENT_USERNAME, None)
    
    # Create the agent based on type
    if agent_type == RANDOM:
        AGENT = RandomPlayer(
            account_configuration=account,
            battle_format=BATTLE_FORMAT,
            server_configuration=server_config,
            avatar=None
        )
    else:
        # Set environment variable for GAIA agent creation
        os.environ["LLM_PROVIDER"] = agent_type
        
        # Create GAIA agent with specified LLM provider
        AGENT = GAIAAgent(
            account_configuration=account,
            battle_format=BATTLE_FORMAT,
            server_configuration=server_config,
            start_timer_on_battle_start=True,
            avatar=None
        )
    
    # Store the agent type
    AGENT_TYPE = agent_type
    
    return AGENT, AGENT_USERNAME

async def challenge_player(opponent_username, agent_type=None):
    """
    Have the agent challenge a human player.
    
    Args:
        opponent_username: Username of the opponent to challenge
        agent_type: Type of agent to use (if None, uses existing agent)
    """
    global AGENT, AGENT_USERNAME, AGENT_TYPE
    
    # Create or recreate agent if needed
    if not AGENT or (agent_type and agent_type != AGENT_TYPE):
        AGENT, AGENT_USERNAME = await create_agent(agent_type or AGENT_TYPE or OPENAI)
    
    try:
        # Send challenge to the human player
        await AGENT.send_challenges(opponent_username, n_challenges=1)
        return f"Challenge sent from {AGENT_USERNAME} ({AGENT_TYPE.upper()}) to {opponent_username}!"
    except Exception as e:
        return f"Error sending challenge: {str(e)}"

async def accept_challenges(agent_type=None):
    """
    Have the agent accept challenges from any player.
    
    Args:
        agent_type: Type of agent to use (if None, uses existing agent)
    """
    global AGENT, AGENT_USERNAME, AGENT_TYPE
    
    # Create or recreate agent if needed
    if not AGENT or (agent_type and agent_type != AGENT_TYPE):
        AGENT, AGENT_USERNAME = await create_agent(agent_type or AGENT_TYPE or OPENAI)
    
    try:
        # Accept a single challenge from any player
        await AGENT.accept_challenges(None, 1)
        return f"Challenge accepted and battle completed by {AGENT_USERNAME} ({AGENT_TYPE.upper()})!"
    except Exception as e:
        return f"Error accepting challenge: {str(e)}"

def challenge_player_sync(opponent_username, agent_type=None):
    """Synchronous wrapper for challenge_player."""
    return asyncio.get_event_loop().run_until_complete(challenge_player(opponent_username, agent_type))

def accept_challenges_sync(agent_type=None):
    """Synchronous wrapper for accept_challenges."""
    return asyncio.get_event_loop().run_until_complete(accept_challenges(agent_type))

def create_agent_sync(agent_type):
    """
    Synchronous wrapper for create_agent.
    
    Args:
        agent_type: Type of agent to create
    """
    agent, username = asyncio.get_event_loop().run_until_complete(create_agent(agent_type))
    return f"Created {agent_type.upper()} agent with username: {username}"

# Create the Gradio interface
with gr.Blocks(title="Pokémon Battle Agent") as app:
    gr.Markdown("# Pokémon Battle Agent with Multi-LLM Support")
    gr.Markdown("This interface lets you interact with AI agents powered by different LLMs.")
    
    with gr.Tab("Challenge a Player"):
        with gr.Row():
            opponent_input = gr.Textbox(label="Opponent Username")
            agent_dropdown = gr.Dropdown(
                [OPENAI, CLAUDE, GEMINI, GROK, RANDOM], 
                label="Agent Type", 
                value=OPENAI
            )
            challenge_btn = gr.Button("Send Challenge")
        challenge_output = gr.Textbox(label="Result")
        
        challenge_btn.click(challenge_player_sync, inputs=[opponent_input, agent_dropdown], outputs=challenge_output)
    
    with gr.Tab("Accept Challenges"):
        with gr.Row():
            agent_accept_dropdown = gr.Dropdown(
                [OPENAI, CLAUDE, GEMINI, GROK, RANDOM], 
                label="Agent Type", 
                value=OPENAI
            )
            accept_btn = gr.Button("Accept One Challenge")
        accept_output = gr.Textbox(label="Result")
        
        accept_btn.click(accept_challenges_sync, inputs=agent_accept_dropdown, outputs=accept_output)
    
    with gr.Tab("Create New Agent"):
        with gr.Row():
            agent_create_dropdown = gr.Dropdown(
                [OPENAI, CLAUDE, GEMINI, GROK, RANDOM], 
                label="Agent Type", 
                value=OPENAI
            )
            create_btn = gr.Button("Create New Agent")
        create_output = gr.Textbox(label="Result")
        
        create_btn.click(create_agent_sync, inputs=agent_create_dropdown, outputs=create_output)
    
    # Check which API keys are available
    api_status = {}
    for provider in [OPENAI, CLAUDE, GEMINI, GROK]:
        env_var = f"{provider.upper()}_API_KEY"
        api_status[provider] = "✅ Available" if os.getenv(env_var) else "❌ Not configured"
    
    gr.Markdown(f"""
    ## Current Configuration
    - Battle Format: {BATTLE_FORMAT}
    - Available LLM Providers:
      - OpenAI: {api_status[OPENAI]}
      - Claude: {api_status[CLAUDE]}
      - Gemini: {api_status[GEMINI]}
      - Grok: {api_status[GROK]}
    
    ## How to Use
    1. Create a new agent using the "Create New Agent" tab, selecting your preferred LLM
    2. Note the agent's username
    3. Either:
       - Challenge a player: Enter their username, select agent type, and click "Send Challenge"
       - Accept challenges: Select agent type and click "Accept One Challenge" to wait for an incoming challenge
    
    ## Agent Types
    - **OpenAI**: Powered by GPT-4o, provides precise and strategic battling
    - **Claude**: Powered by Claude 3 Opus, adaptive and context-aware battling
    - **Gemini**: Powered by Gemini Pro, creative and unpredictable battling
    - **Grok**: Experimental battling style (requires API key)
    - **Random**: Simple agent that makes random moves, useful for testing
    
    ## Watching Battles
    Once battles are started, you can watch them on the Pokémon Showdown server.
    """)

# Create an agent on startup with the default provider
agent_type = OPENAI
if os.getenv(f"{OPENAI.upper()}_API_KEY") is None:
    # Fall back to the first available provider
    for provider in [CLAUDE, GEMINI, GROK]:
        if os.getenv(f"{provider.upper()}_API_KEY"):
            agent_type = provider
            break
    else:
        # If no LLM provider is available, use Random
        agent_type = RANDOM

asyncio.get_event_loop().run_until_complete(create_agent(agent_type))
print(f"Created {AGENT_TYPE.upper()} agent with username: {AGENT_USERNAME}")

# For direct script execution (not via Gradio)
if __name__ == "__main__":
    app.launch()