# Pokémon Battle Agent with GAIA: Multi-LLM Strategic Battles

This project implements an advanced Pokémon battle agent system that leverages multiple Large Language Models (LLMs) to make strategic battle decisions. The GAIA (Generative AI Agent) framework enables different LLM-powered agents to battle against each other or human players, with each agent leveraging unique strategic approaches based on their underlying AI model.

## What It Does

This system enables you to:

1. **Run AI vs AI Battles**: Pit different LLM-powered agents against each other (OpenAI vs Anthropic vs Gemini vs Grok)
2. **Challenge Human Players**: Have an LLM-powered agent challenge human players on Pokémon Showdown
3. **Accept Human Challenges**: Let humans challenge your LLM-powered agents
4. **Analyze Battle Strategies**: The agents record memory of past interactions and adapt their strategies
5. **Deploy to Hugging Face Spaces**: Host your AI agents online for others to battle against

## How It Works

### Agent Architecture

Each GAIA agent is composed of:

1. **LLM Core**: Interfaces with one of four LLM providers:
   - **OpenAI Agent** (GPT-4o): Precise and strategic battling style
   - **Claude Agent** (Claude 3 Opus): Adaptive and context-aware battling style 
   - **Gemini Agent** (Gemini Pro): Creative and unpredictable battling style
   - **Grok Agent** (Optional): Experimental battling style

2. **Battle Memory System**: Records opponent moves, effectiveness patterns, and strategies to improve over time

3. **Strategic Decision Engine**: Analyzes type matchups, move effectiveness, battle phases, and recommends optimal actions

4. **Type Analyzer**: Provides detailed analysis of type effectiveness and team coverage

### Battle System

The battle system uses [poke-env](https://github.com/hsahovic/poke-env) to interface with Pokémon Showdown, handling:

1. **Automatic Username Generation**: Creates unique usernames that identify each agent's LLM type (e.g., "Claude_a2b3c4", "Gemini_x7y8z9")
2. **Battle State Processing**: Converts game state into a format the LLMs can understand
3. **Decision Processing**: Translates LLM strategic decisions into valid Pokémon Showdown commands
4. **Battle Tracking**: Monitors ongoing battles and collects performance statistics

### Agent Technology Stack

- **Frontend**: Local terminal or Gradio web interface (for Hugging Face Spaces deployment)
- **Backend**: Python with asyncio for handling concurrent battles
- **LLM Integration**: Direct API calls to OpenAI, Anthropic, Google, and optionally xAI
- **Game Interface**: poke-env library connecting to Pokémon Showdown servers (local or remote)

## Running Locally

### 1. Environment Setup

First, clone the repository and set up your environment:

```bash
# Clone the repository (if you haven't already)
git clone https://github.com/yourusername/pokemon_agent.git
cd pokemon_agent

# Option 1: Using conda
conda env create -f environment.yml
conda activate pokemon_agent

# Option 2: Using pip
pip install -r requirements.txt
```

### 2. Setting Up API Keys

Create a `.env` file in the project root with your API keys:

```
# Choose your LLM providers
# You can set different providers for different agents
OPENAI_AGENT_PROVIDER=openai
CLAUDE_AGENT_PROVIDER=anthropic
GEMINI_AGENT_PROVIDER=gemini
GROK_AGENT_PROVIDER=grok  # Optional

# API Keys for LLM Providers - Add all keys you plan to use
OPENAI_API_KEY=sk-your-openai-api-key-here
ANTHROPIC_API_KEY=sk-ant-your-anthropic-api-key-here
GEMINI_API_KEY=your-gemini-api-key-here
GROK_API_KEY=your-grok-api-key-here  # Optional

# Pokémon Showdown Server Configuration
# Use 'ws://localhost:8000/showdown/websocket' for local server
SHOWDOWN_SERVER_URL=ws://localhost:8000/showdown/websocket
SHOWDOWN_AUTHENTICATION_URL=https://play.pokemonshowdown.com/action.php?

# Battle Configuration
# Default format to use for battles
BATTLE_FORMAT=gen9randombattle
```

### 3. Start the Pokémon Showdown Server

Run the setup script to install and start the local Pokémon Showdown server:

```bash
chmod +x setup_server.sh
./setup_server.sh
```

This script will:
1. Clone the Pokémon Showdown repository (if not already present)
2. Install dependencies and configure the server
3. Create necessary directories with proper permissions
4. Start the server in no-security mode for easier testing

### 4. Running Different Battle Modes

#### AI vs AI Battles

To run battles between different LLM agents:

```bash
# Use the enhanced start script for a clean start with better debugging
./enhanced_start_battles.sh --agent1 openai --agent2 anthropic --battles 5

# Enable debug mode for verbose logging
./enhanced_start_battles.sh --debug --agent1 openai --agent2 anthropic --battles 5

# Run with original script (may encounter issues with existing server instances)
./start_battles.sh --mode ai_vs_ai --battles 5 --agent1 openai --agent2 anthropic

# Alternative: Run directly (not recommended unless debugging specific issues)
python run_patched_battles.py --mode ai_vs_ai --battles 3 --agent1 gemini --agent2 claude

# Run a tournament between all available agents
./enhanced_start_battles.sh -- --mode tournament --battles 2
```

#### Human vs AI Battles

To challenge an AI agent as a human player:

```bash
# Start an AI agent that will accept challenges from any player
./enhanced_start_battles.sh -- --mode accept_human --agent openai --listen

# Then go to http://localhost:8000, choose a username, and challenge the agent
# The agent's username will be displayed in the terminal (e.g., "Oabcde1234")
```

To have an AI agent challenge a human player:

```bash
# Have the Claude agent challenge a specific human player
./enhanced_start_battles.sh -- --mode challenge_human --agent claude --human YourUsername
```

## Customizing Agents

You can customize each agent by editing its configuration and behavior:

### Changing the Default LLM for an Agent

Edit the `.env` file to change which LLM provider is used by default:

```
# Default to Claude for all agents if not specified
LLM_PROVIDER=anthropic
```

### Customizing Agent Strategies

Each agent can be customized by modifying the weights in `gaia_agent.py`:

```python
# Example: Make the agent more aggressive in the early game
self.strategy_profiles = {
    self.PHASE_EARLY: {
        "setup": 0.7,      # Reduced from 1.5
        "offensive": 2.0,  # Increased from 1.0
        "defensive": 0.5   # Reduced from 0.8
    },
    # ... other phases
}
```

## Debugging and Monitoring

The enhanced system includes comprehensive debugging and monitoring features:

### Enhanced Logging

- Detailed logging of battle events
- Separate log files for server, battles, and debug info
- Color-coded terminal output

Enable debug mode to get more verbose logging:

```bash
# Enable debug mode with the flag
./enhanced_start_battles.sh --debug

# Or set the environment variable
DEBUG=1 ./enhanced_start_battles.sh
```

### Battle Monitor

The enhanced system includes a Battle Monitor that:

- Tracks battle progress in real-time
- Detects stalled battles
- Provides detailed battle statistics
- Logs errors and actions per battle

View battle status during or after battles:

```bash
# The monitor will automatically print summary statistics when battles complete
```

### Error Handling

The enhanced system includes robust error handling:

- Detailed logging of errors with stack traces
- Automatic retries for failed battles
- Graceful degradation on error conditions
- Recovery mechanisms for common issues

### Debug Flags

You can control debugging features with these options:

```bash
# Clean up server logs and restart (fixes many issues)
./enhanced_start_battles.sh --clean

# Set custom timeout for server startup
./enhanced_start_battles.sh --timeout 120

# Set number of retries for failed operations
./enhanced_start_battles.sh --retries 5

# Show help with all available options
./enhanced_start_battles.sh --help
```

## Technical Details

### Agent Naming Convention

Each agent is automatically given a unique username based on its LLM provider:

- OpenAI agents: `O[random string][timestamp]`
- Claude agents: `C[random string][timestamp]`
- Gemini agents: `G[random string][timestamp]`
- Grok agents: `K[random string][timestamp]`

This naming convention helps identify which LLM is behind each agent during battles.

### Battle State Representation

The battle state is represented as a formatted string that includes:

- Your active Pokémon (species, type, HP, status, boosts)
- Opponent's active Pokémon (species, type, HP, status, boosts)
- Available moves (name, type, base power, accuracy, PP, category)
- Available switches (Pokémon, HP, status)
- Weather, terrains, and side conditions
- Battle memory (patterns observed during the battle)

### Decision Making Process

1. The battle state is formatted into a prompt
2. Type analysis is performed to evaluate matchups
3. Strategic analysis determines optimal actions based on battle phase
4. The battle memory is consulted for information about the opponent
5. All this information is sent to the LLM with a carefully crafted prompt
6. The LLM returns a structured decision (move or switch)
7. The decision is converted to a Pokémon Showdown command

## Troubleshooting

### Common Issues

- **Server Connection Issues**: Make sure the Pokémon Showdown server is running at http://localhost:8000
- **API Key Errors**: Verify your API keys in the `.env` file
- **Permission Errors**: Run `chmod -R 777 pokemon-showdown/logs` if you encounter permission issues 
- **Battle Not Starting**: Ensure the usernames are correct when challenging or accepting challenges
- **Username Already Taken Errors**: Always use `./enhanced_start_battles.sh` to properly reset the server
- **Type Analysis Errors**: Fixed in the current code with a more robust type chart
- **Message Attribute Error**: Fixed by the enhanced player patches

### Quick Reset

If you encounter any issues with battles not starting or usernames already taken:

```bash
# Use the comprehensive enhanced start script with cleanup
./enhanced_start_battles.sh --clean -- --mode ai_vs_ai --battles 1 --agent1 random --agent2 random
```

### Recent Fixes

The latest version includes several important fixes:

1. **Enhanced Player Class Patch**: Added detailed logging and robust error handling for the `'str' object has no attribute 'message'` error in poke-env library
2. **Battle Monitor**: Added comprehensive monitoring of battles with stall detection and detailed statistics
3. **Improved Type Analysis**: Implemented a complete type chart with all 18 types for accurate effectiveness calculations
4. **Robust Error Handling**: Added comprehensive error handling throughout the system
5. **Detailed Logging**: Enhanced logging to help diagnose issues
6. **Auto-Retry Logic**: Added automatic retry mechanisms for failed operations

### Logs

Check these logs for troubleshooting:

- **Main Log**: Available in the `logs/battle_*.log` file
- **Server Log**: Available in the `logs/server_*.log` file
- **Debug Log**: Available in the `logs/debug_*.log` file when running in debug mode
- **Error Logs**: Located in `pokemon-showdown/logs/errors.txt`

### Type Analysis Troubleshooting

If you're experiencing issues with type effectiveness calculations:

1. The code uses a pre-defined type chart instead of relying on the poke-env's `damage_multiplier()` method
2. STAB (Same Type Attack Bonus) calculations are now handled by checking the active Pokémon's types instead of using the non-existent `move.pokemon` attribute
3. All type lookups have fallbacks to default effectiveness (1.0) if type combinations aren't found in the chart

## Credits

This project is built using:
- [poke-env](https://github.com/hsahovic/poke-env) by Haris Sahovic
- [Pokémon Showdown](https://pokemonshowdown.com/)
- LLM APIs: OpenAI, Anthropic Claude, Google Gemini, and optionally xAI Grok