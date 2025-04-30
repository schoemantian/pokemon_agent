#!/bin/bash
# Script to set up and run a local Pokémon Showdown server

# Check if Pokémon Showdown directory exists
if [ ! -d "pokemon-showdown" ]; then
    echo "Cloning Pokémon Showdown repository..."
    git clone https://github.com/smogon/pokemon-showdown.git
    cd pokemon-showdown
    npm install
    cp config/config-example.js config/config.js
else
    echo "Pokémon Showdown directory exists, updating..."
    cd pokemon-showdown
    git pull
    npm install
fi

# Create required directories to avoid ENOENT errors
echo "Creating necessary directories..."
mkdir -p logs/repl
mkdir -p logs/chat
mkdir -p logs/modlog
mkdir -p logs/battles

# Create all specific log directories mentioned in errors
mkdir -p logs/repl/abusemonitor-local-7520
mkdir -p logs/repl/abusemonitor-remote-7521
mkdir -p logs/repl/abusemonitor-local-8472
mkdir -p logs/repl/abusemonitor-remote-8473
mkdir -p logs/repl/abusemonitor-local-8978
mkdir -p logs/repl/abusemonitor-remote-8979
mkdir -p logs/repl/abusemonitor-local-9090
mkdir -p logs/repl/abusemonitor-remote-9091
mkdir -p logs/repl/abusemonitor-local-20703
mkdir -p logs/repl/abusemonitor-remote-20704
mkdir -p logs/repl/abusemonitor-local-22312
mkdir -p logs/repl/abusemonitor-remote-22313
mkdir -p logs/repl/abusemonitor-remote-22437
mkdir -p logs/repl/abusemonitor-local-23739
mkdir -p logs/repl/abusemonitor-remote-23740
mkdir -p logs/repl/abusemonitor-local-24380
mkdir -p logs/repl/abusemonitor-remote-24381

# Also create additional directories that might be needed
mkdir -p logs/repl/app
mkdir -p logs/repl/chat-db
mkdir -p logs/repl/sim-20706
mkdir -p logs/repl/sockets-1-20710
mkdir -p logs/repl/team-validator-20699
mkdir -p logs/repl/verifier

# Set permissions for log directories with more permissive approach
chmod -R 777 logs

# Modify the config.js file to disable authentication
# Using macOS/BSD compatible sed command
echo "Configuring server to disable authentication..."
sed -i '.bak' 's/exports.useladder = true/exports.useladder = false/g' config/config.js
sed -i '.bak' 's/exports.authmaintenance = true/exports.authmaintenance = false/g' config/config.js
sed -i '.bak' "s/trusted: \[\]/trusted: ['127.0.0.1', 'localhost']/g" config/config.js

# Display instructions
echo ""
echo "=================================================="
echo "Starting Pokémon Showdown server with no security..."
echo "Once the server is running, you can view battles at:"
echo "http://localhost:8000"
echo ""
echo "After battles are started, you can view them by:"
echo "1. Going to http://localhost:8000"
echo "2. Choose any username and click 'Choose Name'"
echo "3. Click 'Watch a battle' in the left sidebar"
echo "=================================================="
echo ""

# Start the server with no security
node pokemon-showdown start --no-security

# Note: Press Ctrl+C to stop the server 