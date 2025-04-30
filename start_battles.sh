#!/bin/bash
# Complete solution to start the server, apply patches, and run battles

echo "==============================================="
echo "🚀 Pokemon Battle Agent - Complete Startup Script"
echo "==============================================="

# Step 1: Kill any existing server instances and clean up logs
echo "🧹 Cleaning up and resetting environment..."
pkill -f "node pokemon-showdown" || true
sleep 2
pkill -9 -f "node pokemon-showdown" || true
sleep 1

# Step 2: Clean and recreate log directories
echo "📁 Preparing log directories..."
mkdir -p pokemon-showdown/logs/repl
mkdir -p pokemon-showdown/logs/chat
mkdir -p pokemon-showdown/logs/modlog
mkdir -p pokemon-showdown/logs/battles

# Set permissions
chmod -R 777 pokemon-showdown/logs

# Step 3: Start the server in the background
echo "🖥️  Starting Pokémon Showdown server..."
cd pokemon-showdown && node pokemon-showdown start --no-security &
SERVER_PID=$!
cd ..

# Give the server time to start
echo "⏳ Waiting for server to initialize..."
sleep 5

# Step 4: Activate the Python environment
echo "🐍 Activating Python environment..."
source pokemon_agent/bin/activate

# Step 5: Run battles with the patched player class
echo "🎮 Running battles with fixed agent code..."
echo "----------------------------------------"
echo "Starting battle. You can view it at http://localhost:8000"
echo "----------------------------------------"

# Run the patched battle script with arguments passed to this script
python3 run_patched_battles.py "$@"

# If we get here, the battles have finished
echo "----------------------------------------"
echo "✅ Battles completed!"
echo "----------------------------------------"

# Ask if user wants to keep the server running
read -p "Keep the Pokémon Showdown server running? (y/n): " KEEP_SERVER
if [ "$KEEP_SERVER" != "y" ]; then
    echo "Shutting down server..."
    pkill -f "node pokemon-showdown" || true
    echo "Server stopped."
fi

echo "All done! 👋"