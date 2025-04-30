#!/usr/bin/env python3
"""
Enhanced utility functions for Pokémon Battle Agent with detailed logging and debugging.
"""
import re
import json
import time
import logging
import traceback
from typing import Dict, List, Optional, Any, Tuple, Union

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger('enhanced_utils')

# Enable debug mode if environment variable is set
import os
DEBUG = os.environ.get('DEBUG', '0').lower() in ('1', 'true', 'yes', 'on')
if DEBUG:
    logger.setLevel(logging.DEBUG)

def normalize_name(name: str) -> str:
    """
    Normalizes a name to match Pokémon Showdown's ID format.
    
    Args:
        name: The name to normalize.
        
    Returns:
        The normalized name.
    """
    if not name:
        return ""
    normalized = re.sub(r'[^a-z0-9]', '', name.lower())
    if DEBUG:
        logger.debug(f"Normalized name: '{name}' -> '{normalized}'")
    return normalized

def extract_function_call(content: str) -> Dict[str, Any]:
    """
    Enhanced function to extract function call information from LLM response content.
    Handles multiple formats and provides detailed logging.
    
    Args:
        content: The content to parse.
        
    Returns:
        A dictionary with function call information if present, otherwise empty dict.
    """
    if DEBUG:
        logger.debug(f"Extracting function call from content: {content[:50]}...")
    
    # Try multiple patterns to be more resilient
    patterns = [
        # JSON block pattern with name and arguments
        r'```(?:json)?\s*{\s*"name"\s*:\s*"([^"]+)"\s*,\s*"arguments"\s*:\s*({[^}]+})\s*}\s*```',
        
        # Function call format pattern
        r'(?:call|use|invoke)\s+(\w+)\s*\(\s*(?:.*?[\'"](\w+)[\'"].*?)+\s*\)',
        
        # Direct JSON without code block
        r'{\s*"name"\s*:\s*"([^"]+)"\s*,\s*"arguments"\s*:\s*({[^}]+})\s*}',
        
        # Simple name-value pattern
        r'([a-zA-Z_]+):\s*([a-zA-Z0-9_-]+)'
    ]
    
    # Try each pattern in order
    for i, pattern in enumerate(patterns):
        try:
            match = re.search(pattern, content, re.DOTALL)
            if match:
                if i == 0 or i == 2:  # JSON patterns
                    function_name = match.group(1)
                    arguments_str = match.group(2)
                    
                    # Try to parse the arguments as JSON
                    try:
                        # First clean up the string to ensure it's valid JSON
                        # Replace single quotes with double quotes
                        arguments_str = arguments_str.replace("'", '"')
                        
                        # Try to parse as JSON
                        arguments = json.loads(arguments_str)
                        
                        result = {
                            "name": function_name,
                            "arguments": arguments
                        }
                        
                        logger.debug(f"Successfully extracted function call using pattern {i+1}: {result}")
                        return result
                        
                    except json.JSONDecodeError:
                        # Fallback to regex based parsing
                        argument_pattern = r'"([^"]+)"\s*:\s*"([^"]+)"'
                        arguments = {k: v for k, v in re.findall(argument_pattern, arguments_str)}
                        
                        result = {
                            "name": function_name,
                            "arguments": arguments
                        }
                        
                        logger.debug(f"Extracted function call using regex fallback: {result}")
                        return result
                
                elif i == 1:  # Function call format
                    function_name = match.group(1)
                    argument_val = match.group(2) if len(match.groups()) > 1 else None
                    
                    # Try to find all arguments
                    arg_pattern = r'[\'"](\w+)[\'"]'
                    all_args = re.findall(arg_pattern, match.group(0))
                    
                    # If we found arguments, use them
                    if all_args and len(all_args) > 1:
                        # Assume the first arg might be the function name and exclude it if it matches
                        if all_args[0].lower() == function_name.lower():
                            all_args = all_args[1:]
                        
                        # For functions like choose_move, use the first arg as move_name
                        if function_name == "choose_move":
                            result = {
                                "name": function_name,
                                "arguments": {"move_name": all_args[0]}
                            }
                        elif function_name == "choose_switch":
                            result = {
                                "name": function_name,
                                "arguments": {"pokemon_name": all_args[0]}
                            }
                        else:
                            # Generic args
                            result = {
                                "name": function_name,
                                "arguments": {"value": all_args[0]}
                            }
                        
                        logger.debug(f"Extracted function call using pattern {i+1}: {result}")
                        return result
                
                elif i == 3:  # Simple name-value pattern
                    # This is a simple fallback for basic answers like "move: thunderbolt"
                    key = match.group(1).lower()
                    value = match.group(2)
                    
                    if key in ["move", "attack", "use"]:
                        result = {
                            "name": "choose_move",
                            "arguments": {"move_name": value}
                        }
                    elif key in ["switch", "change", "pokemon"]:
                        result = {
                            "name": "choose_switch",
                            "arguments": {"pokemon_name": value}
                        }
                    else:
                        # Unknown key, use as-is
                        result = {
                            "name": key,
                            "arguments": {"value": value}
                        }
                    
                    logger.debug(f"Extracted function call using simple pattern: {result}")
                    return result
        
        except Exception as e:
            logger.warning(f"Error matching pattern {i+1}: {e}")
            if DEBUG:
                logger.debug(f"Stack trace: {traceback.format_exc()}")
    
    # Look for special keywords as a last resort
    move_keywords = ["choose move", "use move", "attack with", "use attack"]
    switch_keywords = ["switch to", "change to", "swap to", "switch pokemon"]
    
    for keyword in move_keywords:
        match = re.search(f"{keyword}\\s+['\"]?([\\w-]+)['\"]?", content, re.IGNORECASE)
        if match:
            result = {
                "name": "choose_move",
                "arguments": {"move_name": match.group(1)}
            }
            logger.debug(f"Extracted move using keyword match: {result}")
            return result
    
    for keyword in switch_keywords:
        match = re.search(f"{keyword}\\s+['\"]?([\\w-]+)['\"]?", content, re.IGNORECASE)
        if match:
            result = {
                "name": "choose_switch",
                "arguments": {"pokemon_name": match.group(1)}
            }
            logger.debug(f"Extracted switch using keyword match: {result}")
            return result
    
    logger.warning("Failed to extract function call from content")
    if DEBUG:
        logger.debug(f"Full content that failed extraction: {content}")
    
    return {}

def format_battle_state(battle: Any) -> str:
    """
    Enhanced formatter for battle state with detailed logging.
    
    Args:
        battle: The battle object.
        
    Returns:
        A string representation of the battle state.
    """
    start_time = time.time()
    logger.debug(f"Formatting battle state for battle {getattr(battle, 'battle_tag', 'unknown')}")
    
    try:
        active_pkmn = battle.active_pokemon
        if not active_pkmn:
            logger.warning("No active Pokémon found in battle state")
            return "No active Pokémon"
        
        # Format your active Pokémon information
        active_pkmn_info = (
            f"Your active Pokemon: {active_pkmn.species} "
            f"(Type: {'/'.join(map(str, active_pkmn.types))}) "
            f"HP: {active_pkmn.current_hp_fraction * 100:.1f}% "
            f"Status: {active_pkmn.status.name if active_pkmn.status else 'None'} "
            f"Boosts: {active_pkmn.boosts}"
        )
        
        # Format opponent's active Pokémon information
        opponent_pkmn = battle.opponent_active_pokemon
        opp_info_str = "Unknown"
        if opponent_pkmn:
            opp_info_str = (
                f"{opponent_pkmn.species} "
                f"(Type: {'/'.join(map(str, opponent_pkmn.types))}) "
                f"HP: {opponent_pkmn.current_hp_fraction * 100:.1f}% "
                f"Status: {opponent_pkmn.status.name if opponent_pkmn.status else 'None'} "
                f"Boosts: {opponent_pkmn.boosts}"
            )
        opponent_pkmn_info = f"Opponent's active Pokemon: {opp_info_str}"
        
        # Format available moves
        available_moves_info = "Available moves:\n"
        if battle.available_moves:
            available_moves_info += "\n".join(
                [
                    f"- {move.id} (Type: {move.type}, BP: {move.base_power}, "
                    f"Acc: {move.accuracy}, PP: {move.current_pp}/{move.max_pp}, "
                    f"Cat: {move.category.name})"
                    for move in battle.available_moves
                ]
            )
        else:
            available_moves_info += "- None (Must switch or Struggle)"
        
        # Format available switches
        available_switches_info = "Available switches:\n"
        if battle.available_switches:
            available_switches_info += "\n".join(
                [
                    f"- {pkmn.species} (Type: {'/'.join(map(str, pkmn.types))}, "
                    f"HP: {pkmn.current_hp_fraction * 100:.1f}%, "
                    f"Status: {pkmn.status.name if pkmn.status else 'None'})"
                    for pkmn in battle.available_switches
                ]
            )
        else:
            available_switches_info += "- None"
        
        # Add battle metadata
        battle_metadata = (
            f"Battle ID: {getattr(battle, 'battle_tag', 'unknown')}\n"
            f"Turn: {battle.turn}\n"
            f"Weather: {battle.weather}\n"
            f"Terrains: {battle.fields}\n"
            f"Your Side Conditions: {battle.side_conditions}\n"
            f"Opponent Side Conditions: {battle.opponent_side_conditions}"
        )
        
        # Combine all sections
        state_str = (
            f"{battle_metadata}\n\n"
            f"{active_pkmn_info}\n"
            f"{opponent_pkmn_info}\n\n"
            f"{available_moves_info}\n\n"
            f"{available_switches_info}\n\n"
        )
        
        # Add extra debug information when in debug mode
        if DEBUG:
            # Add team information
            team_info = "Your team:\n"
            for pokemon_id, pokemon in battle.team.items():
                if not pokemon.active:
                    team_info += f"- {pokemon.species} (HP: {pokemon.current_hp_fraction * 100:.1f}%, Status: {pokemon.status.name if pokemon.status else 'None'})\n"
            
            # Add known opponent team information
            opponent_team_info = "Known opponent team:\n"
            for pokemon_id, pokemon in battle.opponent_team.items():
                if not pokemon.active:
                    opponent_team_info += f"- {pokemon.species} (Types: {'/'.join(map(str, pokemon.types))})\n"
            
            # Add to state string
            state_str += f"\n{team_info}\n{opponent_team_info}"
        
        end_time = time.time()
        logger.debug(f"Battle state formatted in {(end_time - start_time) * 1000:.2f}ms")
        
        return state_str.strip()
        
    except Exception as e:
        logger.error(f"Error formatting battle state: {str(e)}")
        if DEBUG:
            logger.debug(f"Stack trace: {traceback.format_exc()}")
        
        # Return a simplified battle state as fallback
        return f"Error formatting battle state: {str(e)}\nBattle ID: {getattr(battle, 'battle_tag', 'unknown')}, Turn: {getattr(battle, 'turn', 'unknown')}"


class EnhancedTypeAnalyzer:
    """Enhanced type analysis for Pokémon battles with detailed logging."""
    
    def __init__(self):
        logger.debug("Initializing EnhancedTypeAnalyzer")
        # Track known type effectiveness for quick lookup
        self.effectiveness_cache = {}
        
        # Define the complete type chart - all 18 types against all 18 types
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
    
    def get_type_effectiveness(self, attacking_type: str, defending_type: str) -> float:
        """
        Get the effectiveness of an attacking type against a defending type.
        
        Args:
            attacking_type: The attacking type
            defending_type: The defending type
            
        Returns:
            The effectiveness multiplier (0.0, 0.5, 1.0, or 2.0)
        """
        # Normalize types to lowercase strings
        attacking_type = str(attacking_type).lower()
        defending_type = str(defending_type).lower()
        
        # Check if we have this in the cache
        cache_key = f"{attacking_type}_{defending_type}"
        if cache_key in self.effectiveness_cache:
            return self.effectiveness_cache[cache_key]
        
        # Look up in the type chart
        try:
            effectiveness = self.type_chart.get(attacking_type, {}).get(defending_type, 1.0)
            self.effectiveness_cache[cache_key] = effectiveness
            return effectiveness
        except Exception as e:
            logger.warning(f"Error getting type effectiveness for {attacking_type} vs {defending_type}: {e}")
            # Default to neutral
            return 1.0
    
    def calculate_type_effectiveness(self, attacking_type: str, defending_types: List[str]) -> float:
        """
        Calculate the combined effectiveness against multiple defending types.
        
        Args:
            attacking_type: The attacking type
            defending_types: List of defending types
            
        Returns:
            The combined effectiveness multiplier
        """
        if not defending_types:
            return 1.0
            
        # Calculate effectiveness against each defending type
        effectiveness = 1.0
        for defending_type in defending_types:
            if defending_type:
                type_effectiveness = self.get_type_effectiveness(attacking_type, defending_type)
                effectiveness *= type_effectiveness
                
                if DEBUG:
                    logger.debug(f"Type effectiveness: {attacking_type} vs {defending_type} = {type_effectiveness}")
        
        return effectiveness
    
    def analyze_matchup(self, attacker_pokemon, defender_pokemon):
        """
        Enhanced analyzer for type matchup between two Pokémon with detailed logging.
        
        Args:
            attacker_pokemon: The attacking Pokémon
            defender_pokemon: The defending Pokémon
            
        Returns:
            dict: Detailed analysis of the matchup
        """
        start_time = time.time()
        logger.debug(f"Analyzing matchup: {getattr(attacker_pokemon, 'species', 'unknown')} vs {getattr(defender_pokemon, 'species', 'unknown')}")
        
        matchup = {
            "offensive_score": 0,
            "defensive_score": 0,
            "best_offensive_type": None,
            "worst_defensive_type": None,
            "super_effective_types": [],
            "not_effective_types": [],
            "immunities": []
        }
        
        try:
            # Safety check for null Pokemon
            if not attacker_pokemon or not defender_pokemon:
                logger.warning("Null Pokémon in matchup analysis")
                return matchup
                
            # Safety check for types 
            if not hasattr(attacker_pokemon, 'types') or not hasattr(defender_pokemon, 'types'):
                logger.warning("Pokémon missing types attribute")
                return matchup
                
            # Get types with safety check
            attacker_types = [str(t).lower() for t in attacker_pokemon.types if t]
            defender_types = [str(t).lower() for t in defender_pokemon.types if t]
            
            # Log the types we're analyzing
            logger.debug(f"Attacker types: {attacker_types}")
            logger.debug(f"Defender types: {defender_types}")
            
            # Analyze offensive matchup
            for attacker_type in attacker_types:
                # Calculate effectiveness against defending types
                effectiveness = self.calculate_type_effectiveness(attacker_type, defender_types)
                
                # Update matchup based on effectiveness
                if effectiveness > 1:
                    matchup["offensive_score"] += 1
                    matchup["super_effective_types"].append(attacker_type)
                    
                    if (matchup["best_offensive_type"] is None or 
                        effectiveness > matchup["best_offensive_type"][1]):
                        matchup["best_offensive_type"] = (attacker_type, effectiveness)
                
                elif effectiveness < 1:
                    matchup["offensive_score"] -= 1
                    if effectiveness == 0:
                        matchup["immunities"].append(attacker_type)
                    else:
                        matchup["not_effective_types"].append(attacker_type)
            
            # Analyze defensive matchup - check how each possible attacking type affects defender
            for attacking_type in self.type_chart.keys():
                effectiveness = self.calculate_type_effectiveness(attacking_type, defender_types)
                
                # Higher effectiveness means worse defense
                if effectiveness > 1:
                    matchup["defensive_score"] -= 1
                    
                    if (matchup["worst_defensive_type"] is None or 
                        effectiveness > matchup["worst_defensive_type"][1]):
                        matchup["worst_defensive_type"] = (attacking_type, effectiveness)
                
                # Lower effectiveness means better defense
                elif effectiveness < 1:
                    matchup["defensive_score"] += 1
                    
        except Exception as e:
            logger.error(f"Error in analyze_matchup: {str(e)}")
            if DEBUG:
                logger.debug(f"Stack trace: {traceback.format_exc()}")
            
        # Overall matchup score (-5 to 5)
        matchup["overall_score"] = matchup["offensive_score"] + matchup["defensive_score"]
        matchup["overall_score"] = max(-5, min(5, matchup["overall_score"]))
        
        # Interpret the overall matchup
        if matchup["overall_score"] > 3:
            matchup["recommendation"] = "STRONG_ADVANTAGE"
        elif matchup["overall_score"] > 1:
            matchup["recommendation"] = "ADVANTAGE"
        elif matchup["overall_score"] < -3:
            matchup["recommendation"] = "STRONG_DISADVANTAGE"
        elif matchup["overall_score"] < -1:
            matchup["recommendation"] = "DISADVANTAGE"
        else:
            matchup["recommendation"] = "NEUTRAL"
        
        end_time = time.time()
        logger.debug(f"Matchup analysis completed in {(end_time - start_time) * 1000:.2f}ms: {matchup['recommendation']}")
        
        return matchup
    
    def rate_move_effectiveness(self, move, defender_pokemon) -> Tuple[float, str]:
        """
        Enhanced rating of move effectiveness with detailed logging.
        
        Args:
            move: The move to evaluate
            defender_pokemon: The defending Pokémon
            
        Returns:
            float: Effectiveness score (0-4)
            str: Explanation of the rating
        """
        start_time = time.time()
        logger.debug(f"Rating move effectiveness: {move.id} against {getattr(defender_pokemon, 'species', 'unknown')}")
        
        # Default values
        effectiveness_score = 1.0
        explanation = []
        
        try:
            # Base effectiveness from type matchup
            if not move.type:
                logger.warning(f"Move {move.id} has no type")
                return 1.0, "Unknown move type"
                
            # Get defender types
            defender_types = [str(t).lower() for t in defender_pokemon.types if t]
            
            # Calculate type effectiveness
            move_type_str = str(move.type).lower()
            type_effectiveness = self.calculate_type_effectiveness(move_type_str, defender_types)
            
            # Set base effectiveness score
            effectiveness_score = type_effectiveness
            
            # Check for STAB (Same Type Attack Bonus)
            has_stab = False
            try:
                # Get the user Pokémon - try multiple approaches
                user_pokemon = None
                
                # First approach: try to find the battle context from defender
                current_battle = None
                if hasattr(defender_pokemon, 'battle'):
                    current_battle = defender_pokemon.battle
                
                # If we found a battle, get the active Pokémon
                if current_battle:
                    user_pokemon = current_battle.active_pokemon
                    
                    # Check if the user's type matches the move type for STAB
                    if user_pokemon and hasattr(user_pokemon, 'types'):
                        for poke_type in user_pokemon.types:
                            if poke_type and str(poke_type).lower() == move_type_str:
                                has_stab = True
                                effectiveness_score *= 1.5
                                logger.debug(f"STAB bonus applied for {move.id}")
                                break
            except Exception as e:
                logger.warning(f"Error checking STAB: {e}")
                if DEBUG:
                    logger.debug(f"STAB check stack trace: {traceback.format_exc()}")
            
            # Adjust for move power (normalize to 0-1 range with sigmoid-like scaling)
            power_factor = min(1.0, move.base_power / 150)
            effectiveness_score *= (0.5 + power_factor / 2)
            
            # Adjust for accuracy if available
            if hasattr(move, 'accuracy') and move.accuracy and move.accuracy < 100:
                accuracy_factor = move.accuracy / 100
                effectiveness_score *= accuracy_factor
                logger.debug(f"Adjusting for accuracy: {move.accuracy}%, factor: {accuracy_factor}")
            
            # Adjust for critical hit moves
            if hasattr(move, 'crit_ratio') and move.crit_ratio and move.crit_ratio > 1:
                effectiveness_score *= 1.1
                logger.debug(f"Adjusting for high crit ratio: {move.crit_ratio}")
            
            # Build explanation
            if type_effectiveness > 1:
                explanation.append(f"Super effective (x{type_effectiveness})")
            elif type_effectiveness < 1:
                if type_effectiveness == 0:
                    explanation.append("No effect due to immunity")
                else:
                    explanation.append(f"Not very effective (x{type_effectiveness})")
            else:
                explanation.append("Normal effectiveness")
                
            if has_stab:
                explanation.append("STAB bonus applied")
                
            if move.base_power > 80:
                explanation.append("High base power")
            elif move.base_power < 40:
                explanation.append("Low base power")
                
            if hasattr(move, 'accuracy') and move.accuracy and move.accuracy < 90:
                explanation.append(f"Low accuracy ({move.accuracy}%)")
            
        except Exception as e:
            logger.error(f"Error rating move effectiveness: {str(e)}")
            if DEBUG:
                logger.debug(f"Stack trace: {traceback.format_exc()}")
            
            explanation = ["Error calculating effectiveness"]
            effectiveness_score = 1.0  # Default to neutral
        
        end_time = time.time()
        logger.debug(f"Move effectiveness rating completed in {(end_time - start_time) * 1000:.2f}ms: {effectiveness_score:.2f}")
        
        return effectiveness_score, ", ".join(explanation)


if __name__ == "__main__":
    # Test/demo code when run directly
    print("Enhanced utils module loaded")
    
    # Test normalize_name
    print(f"normalize_name('Charizard') = {normalize_name('Charizard')}")
    
    # Test extract_function_call
    json_content = '```json\n{"name": "choose_move", "arguments": {"move_name": "flamethrower"}}\n```'
    print(f"extract_function_call result: {extract_function_call(json_content)}")
    
    # Initialize type analyzer
    analyzer = EnhancedTypeAnalyzer()
    print(f"Type effectiveness: fire vs grass = {analyzer.get_type_effectiveness('fire', 'grass')}")
    print(f"Type effectiveness: water vs fire = {analyzer.get_type_effectiveness('water', 'fire')}")
    print(f"Type effectiveness: electric vs ground = {analyzer.get_type_effectiveness('electric', 'ground')}")