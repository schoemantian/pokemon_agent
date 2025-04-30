#!/bin/bash
# Script to kill running Pokémon Showdown server instances and restart

echo "Stopping any running Pokémon Showdown server instances..."
pkill -f "node pokemon-showdown" || true

echo "Cleaning up any zombie processes..."
pkill -9 -f "node pokemon-showdown" || true

echo "Waiting for processes to fully terminate..."
sleep 2

echo "Ensuring correct permissions for log directories..."
# Create all required directories
mkdir -p pokemon-showdown/logs/repl
mkdir -p pokemon-showdown/logs/chat
mkdir -p pokemon-showdown/logs/modlog
mkdir -p pokemon-showdown/logs/battles

# Create specific repl directories
mkdir -p pokemon-showdown/logs/repl/abusemonitor-local-*
mkdir -p pokemon-showdown/logs/repl/abusemonitor-remote-*
mkdir -p pokemon-showdown/logs/repl/app
mkdir -p pokemon-showdown/logs/repl/chat-db
mkdir -p pokemon-showdown/logs/repl/sim-*
mkdir -p pokemon-showdown/logs/repl/sockets-*
mkdir -p pokemon-showdown/logs/repl/team-validator-*
mkdir -p pokemon-showdown/logs/repl/verifier

# Set permissions
chmod -R 777 pokemon-showdown/logs

echo "Starting Pokémon Showdown server in the background..."
cd pokemon-showdown && node pokemon-showdown start --no-security &

echo "Server started. You can view battles at: http://localhost:8000"
echo "Wait a few seconds before trying to connect."
echo "To stop the server, run: pkill -f 'node pokemon-showdown'"