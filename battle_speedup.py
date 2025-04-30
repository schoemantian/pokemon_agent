#!/usr/bin/env python3
"""
Battle speed optimizer script for Pokémon battles.
This script reduces LLM decision latency and speeds up battles.
"""

import os
import sys
import time
import asyncio
import logging
import traceback
from typing import Dict, Any, Optional, List, Tuple, Union, Awaitable
import random

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger('battle_speedup')

# Apply the player fix patch first
from enhanced_player_fix import apply_patch
apply_patch()

# Import necessary classes from poke-env
try:
    from poke_env.player.battle_order import BattleOrder, StringBattleOrder
    from poke_env.player.player import Player
    from poke_env.environment.battle import Battle
    from poke_env.environment.pokemon import Pokemon
    from poke_env.environment.move import Move
    logger.info("Successfully imported poke-env classes")
except ImportError as e:
    logger.error(f"Failed to import poke-env classes: {str(e)}")
    sys.exit(1)

class BattleAccelerator:
    """
    Class to accelerate battle speed by optimizing LLM response times and adding caching.
    """
    
    def __init__(self):
        self.move_cache = {}  # battle_id -> {pokemon_id -> last_move}
        self.effectiveness_cache = {}  # (attacker_type, defender_type) -> effectiveness
        self.decision_cache = {}  # (pokemon_id, opponent_id, hp_percent) -> decision
        self.battle_timeouts = {}  # battle_id -> last_action_time
        self.timeout_threshold = 30  # seconds
        self.check_interval = 5  # seconds
        self.cache_hit_count = 0
        self.cache_miss_count = 0
        
        # Start the monitor task
        self.monitor_task = None
        
        # Create a centralized type chart for fast type effectiveness lookups
        self._init_type_chart()
        
        logger.info("BattleAccelerator initialized")
        
    def _init_type_chart(self):
        """Initialize the type effectiveness chart for fast lookups."""
        self.type_chart = {
            "normal": {"normal": 1.0, "fighting": 1.0, "flying": 1.0, "poison": 1.0, "ground": 1.0, "rock": 0.5, "bug": 1.0, "ghost": 0.0, "steel": 0.5, "fire": 1.0, "water": 1.0, "grass": 1.0, "electric": 1.0, "psychic": 1.0, "ice": 1.0, "dragon": 1.0, "dark": 1.0, "fairy": 1.0},
            "fighting": {"normal": 2.0, "fighting": 1.0, "flying": 0.5, "poison": 0.5, "ground": 1.0, "rock": 2.0, "bug": 0.5, "ghost": 0.0, "steel": 2.0, "fire": 1.0, "water": 1.0, "grass": 1.0, "electric": 1.0, "psychic": 0.5, "ice": 2.0, "dragon": 1.0, "dark": 2.0, "fairy": 0.5},
            "flying": {"normal": 1.0, "fighting": 2.0, "flying": 1.0, "poison": 1.0, "ground": 1.0, "rock": 0.5, "bug": 2.0, "ghost": 1.0, "steel": 0.5, "fire": 1.0, "water": 1.0, "grass": 2.0, "electric": 0.5, "psychic": 1.0, "ice": 1.0, "dragon": 1.0, "dark": 1.0, "fairy": 1.0},
            "poison": {"normal": 1.0, "fighting": 1.0, "flying": 1.0, "poison": 0.5, "ground": 0.5, "rock": 0.5, "bug": 1.0, "ghost": 0.5, "steel": 0.0, "fire": 1.0, "water": 1.0, "grass": 2.0, "electric": 1.0, "psychic": 1.0, "ice": 1.0, "dragon": 1.0, "dark": 1.0, "fairy": 2.0},
            "ground": {"normal": 1.0, "fighting": 1.0, "flying": 0.0, "poison": 2.0, "ground": 1.0, "rock": 2.0, "bug": 0.5, "ghost": 1.0, "steel": 2.0, "fire": 2.0, "water": 1.0, "grass": 0.5, "electric": 2.0, "psychic": 1.0, "ice": 1.0, "dragon": 1.0, "dark": 1.0, "fairy": 1.0},
            "rock": {"normal": 1.0, "fighting": 0.5, "flying": 2.0, "poison": 1.0, "ground": 0.5, "rock": 1.0, "bug": 2.0, "ghost": 1.0, "steel": 0.5, "fire": 2.0, "water": 1.0, "grass": 1.0, "electric": 1.0, "psychic": 1.0, "ice": 2.0, "dragon": 1.0, "dark": 1.0, "fairy": 1.0},
            "bug": {"normal": 1.0, "fighting": 0.5, "flying": 0.5, "poison": 0.5, "ground": 1.0, "rock": 1.0, "bug": 1.0, "ghost": 0.5, "steel": 0.5, "fire": 0.5, "water": 1.0, "grass": 2.0, "electric": 1.0, "psychic": 2.0, "ice": 1.0, "dragon": 1.0, "dark": 2.0, "fairy": 0.5},
            "ghost": {"normal": 0.0, "fighting": 1.0, "flying": 1.0, "poison": 1.0, "ground": 1.0, "rock": 1.0, "bug": 1.0, "ghost": 2.0, "steel": 1.0, "fire": 1.0, "water": 1.0, "grass": 1.0, "electric": 1.0, "psychic": 2.0, "ice": 1.0, "dragon": 1.0, "dark": 0.5, "fairy": 1.0},
            "steel": {"normal": 1.0, "fighting": 1.0, "flying": 1.0, "poison": 1.0, "ground": 1.0, "rock": 2.0, "bug": 1.0, "ghost": 1.0, "steel": 0.5, "fire": 0.5, "water": 0.5, "grass": 1.0, "electric": 0.5, "psychic": 1.0, "ice": 2.0, "dragon": 1.0, "dark": 1.0, "fairy": 2.0},
            "fire": {"normal": 1.0, "fighting": 1.0, "flying": 1.0, "poison": 1.0, "ground": 1.0, "rock": 0.5, "bug": 2.0, "ghost": 1.0, "steel": 2.0, "fire": 0.5, "water": 0.5, "grass": 2.0, "electric": 1.0, "psychic": 1.0, "ice": 2.0, "dragon": 0.5, "dark": 1.0, "fairy": 1.0},
            "water": {"normal": 1.0, "fighting": 1.0, "flying": 1.0, "poison": 1.0, "ground": 2.0, "rock": 2.0, "bug": 1.0, "ghost": 1.0, "steel": 1.0, "fire": 2.0, "water": 0.5, "grass": 0.5, "electric": 1.0, "psychic": 1.0, "ice": 1.0, "dragon": 0.5, "dark": 1.0, "fairy": 1.0},
            "grass": {"normal": 1.0, "fighting": 1.0, "flying": 0.5, "poison": 0.5, "ground": 2.0, "rock": 2.0, "bug": 0.5, "ghost": 1.0, "steel": 0.5, "fire": 0.5, "water": 2.0, "grass": 0.5, "electric": 1.0, "psychic": 1.0, "ice": 1.0, "dragon": 0.5, "dark": 1.0, "fairy": 1.0},
            "electric": {"normal": 1.0, "fighting": 1.0, "flying": 2.0, "poison": 1.0, "ground": 0.0, "rock": 1.0, "bug": 1.0, "ghost": 1.0, "steel": 1.0, "fire": 1.0, "water": 2.0, "grass": 0.5, "electric": 0.5, "psychic": 1.0, "ice": 1.0, "dragon": 0.5, "dark": 1.0, "fairy": 1.0},
            "psychic": {"normal": 1.0, "fighting": 2.0, "flying": 1.0, "poison": 2.0, "ground": 1.0, "rock": 1.0, "bug": 1.0, "ghost": 1.0, "steel": 0.5, "fire": 1.0, "water": 1.0, "grass": 1.0, "electric": 1.0, "psychic": 0.5, "ice": 1.0, "dragon": 1.0, "dark": 0.0, "fairy": 1.0},
            "ice": {"normal": 1.0, "fighting": 1.0, "flying": 2.0, "poison": 1.0, "ground": 2.0, "rock": 1.0, "bug": 1.0, "ghost": 1.0, "steel": 0.5, "fire": 0.5, "water": 0.5, "grass": 2.0, "electric": 1.0, "psychic": 1.0, "ice": 0.5, "dragon": 2.0, "dark": 1.0, "fairy": 1.0},
            "dragon": {"normal": 1.0, "fighting": 1.0, "flying": 1.0, "poison": 1.0, "ground": 1.0, "rock": 1.0, "bug": 1.0, "ghost": 1.0, "steel": 0.5, "fire": 1.0, "water": 1.0, "grass": 1.0, "electric": 1.0, "psychic": 1.0, "ice": 1.0, "dragon": 2.0, "dark": 1.0, "fairy": 0.0},
            "dark": {"normal": 1.0, "fighting": 0.5, "flying": 1.0, "poison": 1.0, "ground": 1.0, "rock": 1.0, "bug": 1.0, "ghost": 2.0, "steel": 1.0, "fire": 1.0, "water": 1.0, "grass": 1.0, "electric": 1.0, "psychic": 2.0, "ice": 1.0, "dragon": 1.0, "dark": 0.5, "fairy": 0.5},
            "fairy": {"normal": 1.0, "fighting": 2.0, "flying": 1.0, "poison": 0.5, "ground": 1.0, "rock": 1.0, "bug": 1.0, "ghost": 1.0, "steel": 0.5, "fire": 0.5, "water": 1.0, "grass": 1.0, "electric": 1.0, "psychic": 1.0, "ice": 1.0, "dragon": 2.0, "dark": 2.0, "fairy": 1.0}
        }
        logger.debug(f"Type chart initialized with {len(self.type_chart)} types")
    
    def start_monitoring(self):
        """Start the battle timeout monitoring task."""
        if self.monitor_task is None or self.monitor_task.done():
            self.monitor_task = asyncio.create_task(self._monitor_battles())
            logger.info("Battle monitoring started")
    
    async def _monitor_battles(self):
        """Monitor battles for timeouts and take action."""
        while True:
            try:
                current_time = time.time()
                for battle_id, last_time in list(self.battle_timeouts.items()):
                    if current_time - last_time > self.timeout_threshold:
                        logger.warning(f"Battle {battle_id} has timed out. Last action was {current_time - last_time:.1f}s ago")
                        # We can't intervene directly, but we can log this for debugging
                
                await asyncio.sleep(self.check_interval)
            except Exception as e:
                logger.error(f"Error in battle monitor: {str(e)}")
                await asyncio.sleep(self.check_interval)
    
    def update_battle_activity(self, battle_id: str):
        """Update the last activity time for a battle."""
        self.battle_timeouts[battle_id] = time.time()
    
    def get_type_effectiveness(self, attack_type: str, defend_type: str) -> float:
        """
        Get type effectiveness from cache or calculate it.
        
        Args:
            attack_type: The attacking type
            defend_type: The defending type
            
        Returns:
            float: The effectiveness multiplier
        """
        cache_key = (attack_type.lower(), defend_type.lower())
        if cache_key in self.effectiveness_cache:
            return self.effectiveness_cache[cache_key]
        
        effectiveness = self.type_chart.get(attack_type.lower(), {}).get(defend_type.lower(), 1.0)
        self.effectiveness_cache[cache_key] = effectiveness
        return effectiveness
    
    def calculate_move_effectiveness(self, move: Move, defender: Pokemon) -> float:
        """
        Calculate the effectiveness of a move against a defender.
        
        Args:
            move: The move to use
            defender: The defending Pokémon
            
        Returns:
            float: The effectiveness score
        """
        if not move or not defender:
            return 1.0
            
        move_type = str(move.type).lower()
        effectiveness = 1.0
        
        # Calculate against all defender types
        for def_type in defender.types:
            if def_type:
                type_effectiveness = self.get_type_effectiveness(move_type, str(def_type).lower())
                effectiveness *= type_effectiveness
        
        return effectiveness
    
    def get_best_move(self, battle: Battle) -> Optional[BattleOrder]:
        """
        Get the best move for the current battle state without using an LLM.
        
        Args:
            battle: The current battle state
            
        Returns:
            BattleOrder: The recommended battle order
        """
        active_pokemon = battle.active_pokemon
        opponent = battle.opponent_active_pokemon
        
        # Update battle activity
        self.update_battle_activity(battle.battle_tag)
        
        if not active_pokemon or not opponent:
            logger.warning(f"Missing active Pokémon or opponent in battle {battle.battle_tag}")
            return None
            
        # Create a cache key based on current state
        pokemon_id = active_pokemon.species
        opponent_id = opponent.species
        hp_percent = int(active_pokemon.current_hp_fraction * 100) // 10  # Round to nearest 10%
        cache_key = (pokemon_id, opponent_id, hp_percent)
        
        # Check cache first
        if cache_key in self.decision_cache:
            self.cache_hit_count += 1
            decision = self.decision_cache[cache_key]
            logger.debug(f"Cache hit for {pokemon_id} vs {opponent_id} at {hp_percent*10}% HP")
            return decision
            
        self.cache_miss_count += 1
        
        # If there are no available moves or switches, use default
        if not battle.available_moves and not battle.available_switches:
            logger.debug(f"No available moves or switches for {pokemon_id}")
            order = battle.create_order(battle.get_default_move())
            return order
            
        # Decide whether to switch based on HP and matchup
        should_switch = active_pokemon.current_hp_fraction < 0.3  # Switch if below 30% HP
        
        if should_switch and battle.available_switches:
            # Find the best switch-in based on matchup and HP
            best_switch = None
            best_score = -float('inf')
            
            for pokemon in battle.available_switches:
                # Simple score based on HP and basic type matchup
                score = pokemon.current_hp_fraction * 10  # Base on HP
                
                # Add type advantage/disadvantage
                for poke_type in pokemon.types:
                    if poke_type:
                        for opp_type in opponent.types:
                            if opp_type:
                                effectiveness = self.get_type_effectiveness(
                                    str(poke_type).lower(), 
                                    str(opp_type).lower()
                                )
                                # Higher effectiveness means better offensive capability
                                score += effectiveness
                                
                                # Check defensive capability too
                                defense = self.get_type_effectiveness(
                                    str(opp_type).lower(),
                                    str(poke_type).lower()
                                )
                                # Lower defense effectiveness means better defensive capability
                                score += (2 - defense)
                
                if score > best_score:
                    best_score = score
                    best_switch = pokemon
            
            if best_switch:
                logger.debug(f"Recommending switch to {best_switch.species} with score {best_score:.1f}")
                order = battle.create_order(best_switch)
                self.decision_cache[cache_key] = order
                return order
        
        # If not switching or no switches available, choose best move
        if battle.available_moves:
            # Score each move
            scored_moves = []
            for move in battle.available_moves:
                score = 0
                
                # Base score on power
                score += min(move.base_power / 30, 3.0)  # Max 3 points for power
                
                # Add type effectiveness
                effectiveness = self.calculate_move_effectiveness(move, opponent)
                score += effectiveness * 2  # Super effective = +4, neutral = +2, not very = +1, immune = 0
                
                # Bonus for STAB (Same Type Attack Bonus)
                for poke_type in active_pokemon.types:
                    if poke_type and str(poke_type).lower() == str(move.type).lower():
                        score += 1.5
                        break
                
                # Penalty for status moves when HP is low
                if move.category.name == "STATUS" and active_pokemon.current_hp_fraction < 0.5:
                    score -= 1
                
                # Bonus for priority moves when HP is very low
                if hasattr(move, 'priority') and move.priority > 0 and active_pokemon.current_hp_fraction < 0.2:
                    score += 2
                
                scored_moves.append((move, score))
            
            # Pick the highest scored move
            if scored_moves:
                best_move, best_score = max(scored_moves, key=lambda x: x[1])
                logger.debug(f"Recommending move {best_move.id} with score {best_score:.1f}")
                
                # Check if we can use a Z-move, Dynamax, or Terastallize
                terastallize = False
                if battle.can_tera:
                    # Only terastallize if the move is strong and the matchup is good
                    if best_score > 4.0:
                        terastallize = True
                        logger.debug(f"Recommending terastallize with {best_move.id}")
                
                order = battle.create_order(best_move, terastallize=terastallize)
                self.decision_cache[cache_key] = order
                return order
        
        # Fallback to random move if we get here
        logger.debug(f"Falling back to random move for {pokemon_id}")
        return battle.choose_random_move(battle)

# Create a Monkey Patching function to speed up battles
def apply_speedups():
    """Apply all battle speedup optimizations."""
    # Create an accelerator instance
    accelerator = BattleAccelerator()
    accelerator.start_monitoring()
    
    # Store original choose_move method
    original_choose_move = Player.choose_move
    
    # Create a patched version that first tries the accelerator
    async def accelerated_choose_move(self, battle):
        """
        Accelerated version of choose_move that uses cached decisions when possible.
        Only falls back to LLM when necessary.
        """
        # Try getting a move from the accelerator first
        fast_decision = accelerator.get_best_move(battle)
        if fast_decision:
            logger.debug(f"Using accelerator decision for battle {battle.battle_tag}")
            return fast_decision
        
        # Fall back to the original method
        logger.debug(f"Falling back to original decision method for battle {battle.battle_tag}")
        decision = await original_choose_move(self, battle)
        return decision
    
    # Apply the patch
    Player.choose_move = accelerated_choose_move
    logger.info("Applied battle speed optimizations")
    
    return accelerator

if __name__ == "__main__":
    print("Battle speed optimizer loaded. Apply optimizations with apply_speedups()")
    # The function can be imported and used in run_battles.py