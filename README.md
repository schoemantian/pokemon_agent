# GAIA: LLM-Powered Pokémon Battle Agent

<div align="center">
  <img src="https://raw.githubusercontent.com/smogon/pokemon-showdown/master/pokemonshowdown.png" alt="Pokémon Showdown Logo" width="300" />
</div>

GAIA (Game-Aware Intelligent Agent) is an advanced AI battle system for Pokémon that pits different Large Language Models against each other in strategic battles. This project allows multiple AI agents powered by leading LLMs (OpenAI's GPT-4, Anthropic's Claude, Google's Gemini, and xAI's Grok) to compete in Pokémon battles on the Pokémon Showdown platform.

## 🌟 Features

- **Multi-LLM Support**: Battle with agents powered by OpenAI (GPT-4), Anthropic (Claude), Google (Gemini), or xAI (Grok)
- **Strategic Decision Making**: Agents analyze type matchups, move effectiveness, and battle state
- **Battle Memory**: Agents remember opponent strategies and adapt accordingly
- **Type Analysis System**: In-depth evaluation of type advantages and disadvantages
- **Automated Battles**: Run single matches or tournaments with configurable settings
- **Battle Monitoring**: Ensures battles complete successfully with timeouts and recovery mechanisms
- **Local Server**: Built-in setup for a local Pokémon Showdown server

## 🚀 Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Set up your API keys in a .env file
# See the API Keys section below

# Start the Pokémon Showdown server
chmod +x setup_server.sh
./setup_server.sh

# In a new terminal, run a battle between GPT-4 and Claude
python3 run_battles.py --mode ai_vs_ai --agent1 openai --agent2 anthropic --battles 1
```

## 📋 Requirements

- Python 3.9+
- Node.js 14+
- OpenAI API key (for GPT-4 agent)
- Anthropic API key (for Claude agent)
- Google API key (for Gemini agent)
- xAI API key (optional, for Grok agent)

## 🔧 Setup Guide

### 1. Clone and Install Dependencies

```bash
# Clone the repository (if you haven't already)
git clone https://github.com/yourusername/pokemon_agent.git
cd pokemon_agent

# Create a virtual environment (recommended)
python3 -m venv pokemon_agent
source pokemon_agent/bin/activate  # On Windows: pokemon_agent\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. API Keys Setup

Create a `.env` file in the project root with your API keys:

```
# Required API keys (add whichever you need)
OPENAI_API_KEY=your-openai-key-here
ANTHROPIC_API_KEY=your-anthropic-key-here
GEMINI_API_KEY=your-gemini-key-here
GROK_API_KEY=your-grok-key-here

# Default provider (optional)
LLM_PROVIDER=anthropic  # Choose from: openai, anthropic, gemini, grok
```

### 3. Start the Pokémon Showdown Server

```bash
# Make the script executable
chmod +x setup_server.sh

# Start the server
./setup_server.sh
```

This script will:
- Clone the Pokémon Showdown repository if it doesn't exist
- Create necessary log directories
- Configure the server with no authentication required
- Start the server at http://localhost:8000

Wait until you see "Worker 1 now listening on 0.0.0.0:8000" in the console output. The server is now running and ready to host battles.

**Keep this terminal window open while running battles in a different terminal window.**

## 🏆 Battle Commands

Run these commands in a new terminal window while the Showdown server is running:

### AI vs AI Battles

#### All LLM Matchup Combinations

```bash
# GPT-4 vs Claude
python3 run_battles.py --mode ai_vs_ai --agent1 openai --agent2 anthropic --battles 1

# GPT-4 vs Gemini
python3 run_battles.py --mode ai_vs_ai --agent1 openai --agent2 gemini --battles 1

# GPT-4 vs Grok
python3 run_battles.py --mode ai_vs_ai --agent1 openai --agent2 grok --battles 1

# Claude vs GPT-4
python3 run_battles.py --mode ai_vs_ai --agent1 anthropic --agent2 openai --battles 1

# Claude vs Gemini
python3 run_battles.py --mode ai_vs_ai --agent1 anthropic --agent2 gemini --battles 1

# Claude vs Grok
python3 run_battles.py --mode ai_vs_ai --agent1 anthropic --agent2 grok --battles 1

# Gemini vs GPT-4
python3 run_battles.py --mode ai_vs_ai --agent1 gemini --agent2 openai --battles 1

# Gemini vs Claude
python3 run_battles.py --mode ai_vs_ai --agent1 gemini --agent2 anthropic --battles 1

# Gemini vs Grok
python3 run_battles.py --mode ai_vs_ai --agent1 gemini --agent2 grok --battles 1

# Grok vs GPT-4
python3 run_battles.py --mode ai_vs_ai --agent1 grok --agent2 openai --battles 1

# Grok vs Claude
python3 run_battles.py --mode ai_vs_ai --agent1 grok --agent2 anthropic --battles 1

# Grok vs Gemini
python3 run_battles.py --mode ai_vs_ai --agent1 grok --agent2 gemini --battles 1
```

#### Additional Options

```bash
# Run battles with longer timeouts (5 min per turn, 30 min per battle)
python3 run_battles.py --mode ai_vs_ai --agent1 anthropic --agent2 gemini --battles 1 --turn-timeout 300 --battle-timeout 1800

# Battle against random player
python3 run_battles.py --mode ai_vs_ai --agent1 openai --agent2 random --battles 1

# Use a specific battle format
python3 run_battles.py --mode ai_vs_ai --agent1 openai --agent2 anthropic --format gen9randombattle --battles 1

# Run multiple battles at once
python3 run_battles.py --mode ai_vs_ai --agent1 openai --agent2 anthropic --battles 5
```

### Tournament Mode

Run a round-robin tournament that automatically plays all LLM combinations against each other:

```bash
# Standard tournament with 1 battle per matchup
python3 run_battles.py --mode tournament --battles 1

# Tournament with extended timeouts
python3 run_battles.py --mode tournament --battles 1 --turn-timeout 300 --battle-timeout 1800

# Tournament with more battles per matchup
python3 run_battles.py --mode tournament --battles 3
```

Tournament mode is the easiest way to run all possible LLM agent combinations against each other in a single command. The system will automatically:

1. Create agents for all available LLM providers (those with API keys in your .env file)
2. Run battles between each pair of agents (all possible combinations)
3. Track and report win rates across all matches
4. Output comprehensive tournament statistics at the end

This provides a great way to benchmark different LLM models' performance in strategic Pokemon battles.

### Command-line Options

```
--mode          Battle mode: ai_vs_ai, tournament, accept_human, challenge_human
--agent1        First agent (for ai_vs_ai): openai, anthropic, gemini, grok, random
--agent2        Second agent (for ai_vs_ai): openai, anthropic, gemini, grok, random
--battles       Number of battles to run
--format        Battle format (default: gen9randombattle)
--turn-timeout  Maximum seconds per turn (default: 180s)
--battle-timeout Maximum seconds per battle (default: 1200s)
--human         Human username for challenge mode
--listen        Keep listening for challenges from humans
```

## 🔍 Viewing Battles

Battles are displayed in the Pokémon Showdown interface:

1. Go to http://localhost:8000 in your web browser
2. Enter any username and click "Choose Name"
3. Click "Watch a battle" in the left sidebar
4. You should see ongoing battles listed - click on one to watch

## 🧠 Agent Intelligence Features

Each GAIA agent incorporates several advanced systems:

### Type Analyzer

Evaluates type matchups between Pokémon and calculates move effectiveness. The system:
- Analyzes offensive and defensive type matchups
- Identifies super-effective and resistant types
- Rates moves based on type advantage, STAB, and power
- Provides strategic recommendations

### Battle Memory

Tracks and learns from battle patterns:
- Records opponent's Pokémon and their moves
- Tracks successful and unsuccessful move outcomes
- Observes opponent switching patterns
- Provides strategic insights based on previous turns

### Strategic Decision Engine

Makes nuanced battle decisions based on:
- Current battle phase (early, mid, late game)
- Type matchups and move effectiveness
- HP levels and status conditions
- Weather and field conditions
- Statistical analysis of possible outcomes

## 🔄 Battle Monitoring and Recovery

The system includes robust battle monitoring to ensure battles complete successfully:

- **Turn Timeouts**: Limits maximum time per turn (default: 3 minutes)
- **Battle Timeouts**: Ensures battles don't run indefinitely (default: 20 minutes)
- **State Tracking**: Monitors battle progress and detects stalled states
- **Recovery Actions**: Takes default actions if an agent fails to respond
- **Automatic Forfeiting**: Ends battles that exceed the timeout limit

## 🛠️ Troubleshooting

### Common Issues and Solutions

1. **Username Already Taken Errors**
   - This happens when a previous session didn't properly close
   - Run the cleanup script: `chmod +x cleanup.sh && ./cleanup.sh`
   - Then restart the server with `./setup_server.sh`

2. **Battles Start But Don't Complete**
   - Use longer timeouts: `--turn-timeout 300 --battle-timeout 1800`
   - If that doesn't work, clean up and restart the server

3. **API Key Errors**
   - Verify that your API keys are correctly set in the `.env` file
   - Ensure there are no spaces around the equals sign
   - Check that you have access to the specified models

4. **Server Connection Issues**
   - Make sure the server is fully initialized before starting battles
   - Run the cleanup script and restart the server if you encounter connection errors

### Server Cleanup and Restart

The cleanup script provides an easy way to reset the server:

```bash
# Make the script executable (if not already)
chmod +x cleanup.sh

# Run the cleanup script to kill all servers and clean logs
./cleanup.sh

# Start a fresh server
./setup_server.sh
```

## 📊 Battle Examples

### Individual Matchups

```bash
# OpenAI vs Claude (3 battles)
python3 run_battles.py --mode ai_vs_ai --agent1 openai --agent2 anthropic --battles 3

# Claude vs Gemini (5 battles)
python3 run_battles.py --mode ai_vs_ai --agent1 anthropic --agent2 gemini --battles 5

# Gemini vs Grok (2 battles)
python3 run_battles.py --mode ai_vs_ai --agent1 gemini --agent2 grok --battles 2

# GPT-4 vs Grok (1 battle with extended timeouts)
python3 run_battles.py --mode ai_vs_ai --agent1 openai --agent2 grok --battles 1 --turn-timeout 300 --battle-timeout 1800
```

### LLM Tournament

```bash
# Full tournament (all LLMs, 2 battles per matchup)
python3 run_battles.py --mode tournament --battles 2

# Extended tournament (3 battles per matchup, longer timeouts)
python3 run_battles.py --mode tournament --battles 3 --turn-timeout 300 --battle-timeout 1800
```

### Custom Battle Formats

```bash
# Run battles with a different format
python3 run_battles.py --mode ai_vs_ai --agent1 openai --agent2 anthropic --format gen9monotype --battles 2
```

## 📝 Project Structure

- `run_battles.py` - Main script to run battles between agents
- `gaia_agent.py` - Implementation of the GAIA battle agent
- `agents.py` - Base classes for different LLM providers
- `utils.py` - Utility functions for type analysis and battle state formatting
- `player_fix.py` - Enhanced battle monitoring and timeout handling
- `setup_server.sh` - Script to set up and run the Pokémon Showdown server
- `cleanup.sh` - Script to clean up server processes and logs

## 🔗 Credits and Acknowledgments

This project is built using:
- [poke-env](https://github.com/hsahovic/poke-env) - Pokémon Showdown API wrapper for Python
- [Pokémon Showdown](https://pokemonshowdown.com/) - Pokémon battle simulator
- LLM APIs from OpenAI, Anthropic, Google, and xAI

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🤝 Contributing

Contributions are welcome! Feel free to submit issues or pull requests to improve the project.