#!/bin/bash
#
# Script to clean up Pokémon Showdown logs and kill running servers
#

echo "Cleaning up Pokémon Showdown..."

# Kill any running Pokémon Showdown servers
echo "Stopping running servers..."
pkill -f "node pokemon-showdown" || echo "No servers were running"

# Clean log directories
echo "Cleaning log directories..."
if [ -d "pokemon-showdown/logs" ]; then
  rm -rf pokemon-showdown/logs/*
  mkdir -p pokemon-showdown/logs/repl
  mkdir -p pokemon-showdown/logs/chat
  mkdir -p pokemon-showdown/logs/modlog
  mkdir -p pokemon-showdown/logs/repl/abusemonitor-local-7520
  mkdir -p pokemon-showdown/logs/repl/abusemonitor-remote-7521
  chmod -R 777 pokemon-showdown/logs
  echo "✅ Log directories cleaned and recreated"
else
  echo "⚠️ pokemon-showdown/logs directory not found"
fi

echo "✅ Cleanup complete"
echo "Run ./run_pokemon_server.sh to start a fresh server"