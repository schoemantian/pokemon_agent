#!/bin/bash
# Script to completely clean up and restart the server environment

echo "Killing any running Pokémon Showdown server instances..."
pkill -f "node pokemon-showdown" || true
sleep 2
pkill -9 -f "node pokemon-showdown" || true

echo "Cleaning up log directories..."
rm -rf pokemon-showdown/logs/repl/*
rm -rf pokemon-showdown/logs/chat/*
rm -rf pokemon-showdown/logs/modlog/*
rm -rf pokemon-showdown/logs/battles/*

echo "Recreating log directories with proper permissions..."
mkdir -p pokemon-showdown/logs/repl
mkdir -p pokemon-showdown/logs/repl/abusemonitor-local-*
mkdir -p pokemon-showdown/logs/repl/abusemonitor-remote-*
mkdir -p pokemon-showdown/logs/repl/app
mkdir -p pokemon-showdown/logs/repl/chat-db
mkdir -p pokemon-showdown/logs/repl/sim-*
mkdir -p pokemon-showdown/logs/repl/sockets-*
mkdir -p pokemon-showdown/logs/repl/team-validator-*
mkdir -p pokemon-showdown/logs/repl/verifier
mkdir -p pokemon-showdown/logs/chat
mkdir -p pokemon-showdown/logs/modlog
mkdir -p pokemon-showdown/logs/battles

echo "Setting permissions..."
chmod -R 777 pokemon-showdown/logs

echo "Starting server in fresh state..."
cd pokemon-showdown && node pokemon-showdown start --no-security &

echo "Waiting for server to initialize..."
sleep 5

echo "========================================================"
echo "Environment reset complete!"
echo "Server is running at: http://localhost:8000"
echo ""
echo "To test if battles are working, try:"
echo "source pokemon_agent/bin/activate"
echo "python3 run_battles.py --mode ai_vs_ai --battles 1 --agent1 random --agent2 random"
echo "========================================================"