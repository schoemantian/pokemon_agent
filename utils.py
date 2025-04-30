"""
Utility functions for Pokémon Battle Agent.
"""
import re
from typing import Dict, List, Optional, Any, Tuple

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
    return re.sub(r'[^a-z0-9]', '', name.lower())

def extract_function_call(content: str) -> Dict[str, Any]:
    """
    Extract function call information from LLM response content.
    
    Args:
        content: The content to parse.
        
    Returns:
        A dictionary with function call information if present, otherwise empty dict.
    """
    function_pattern = r'```json\s*{\s*"name"\s*:\s*"([^"]+)"\s*,\s*"arguments"\s*:\s*({[^}]+})\s*}\s*```'
    match = re.search(function_pattern, content, re.DOTALL)
    
    if match:
        function_name = match.group(1)
        arguments_str = match.group(2)
        
        # Simple parsing of the arguments
        argument_pattern = r'"([^"]+)"\s*:\s*"([^"]+)"'
        arguments = {k: v for k, v in re.findall(argument_pattern, arguments_str)}
        
        return {
            "name": function_name,
            "arguments": arguments
        }
    
    return {}

def format_battle_state(battle: Any) -> str:
    """
    Format battle state into a string for LLM consumption.
    
    Args:
        battle: The battle object.
        
    Returns:
        A string representation of the battle state.
    """
    active_pkmn = battle.active_pokemon
    if not active_pkmn:
        return "No active Pokémon"
    
    active_pkmn_info = (
        f"Your active Pokemon: {active_pkmn.species} "
        f"(Type: {'/'.join(map(str, active_pkmn.types))}) "
        f"HP: {active_pkmn.current_hp_fraction * 100:.1f}% "
        f"Status: {active_pkmn.status.name if active_pkmn.status else 'None'} "
        f"Boosts: {active_pkmn.boosts}"
    )

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

    available_switches_info = "Available switches:\n"
    if battle.available_switches:
        available_switches_info += "\n".join(
            [
                f"- {pkmn.species} (HP: {pkmn.current_hp_fraction * 100:.1f}%, "
                f"Status: {pkmn.status.name if pkmn.status else 'None'})"
                for pkmn in battle.available_switches
            ]
        )
    else:
        available_switches_info += "- None"

    state_str = (
        f"{active_pkmn_info}\n"
        f"{opponent_pkmn_info}\n\n"
        f"{available_moves_info}\n\n"
        f"{available_switches_info}\n\n"
        f"Weather: {battle.weather}\n"
        f"Terrains: {battle.fields}\n"
        f"Your Side Conditions: {battle.side_conditions}\n"
        f"Opponent Side Conditions: {battle.opponent_side_conditions}"
    )
    
    return state_str.strip()


class TypeAnalyzer:
    """Advanced type analysis for Pokémon battles."""
    
    def __init__(self):
        # Track known type effectiveness for quick lookup
        self.effectiveness_cache = {}
    
    def analyze_matchup(self, attacker_pokemon, defender_pokemon):
        """
        Analyze the type matchup between two Pokémon.
        
        Args:
            attacker_pokemon: The attacking Pokémon
            defender_pokemon: The defending Pokémon
            
        Returns:
            dict: Detailed analysis of the matchup
        """
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
                return matchup
                
            # Safety check for types 
            if not hasattr(attacker_pokemon, 'types') or not hasattr(defender_pokemon, 'types'):
                return matchup
                
            # Predefined type effectiveness chart (for offense only)
            type_chart = {
                "normal": {"normal": 1.0, "fighting": 1.0, "flying": 1.0, "rock": 0.5, "ghost": 0.0, "steel": 0.5},
                "fire": {"normal": 1.0, "fire": 0.5, "water": 0.5, "grass": 2.0, "ice": 2.0, "bug": 2.0, "rock": 0.5, "steel": 2.0},
                "water": {"normal": 1.0, "fire": 2.0, "water": 0.5, "grass": 0.5, "ground": 2.0, "rock": 2.0},
                "electric": {"normal": 1.0, "water": 2.0, "electric": 0.5, "grass": 0.5, "ground": 0.0, "flying": 2.0},
                "grass": {"normal": 1.0, "fire": 0.5, "water": 2.0, "grass": 0.5, "poison": 0.5, "ground": 2.0, "flying": 0.5, "bug": 0.5},
                "ice": {"normal": 1.0, "fire": 0.5, "water": 0.5, "grass": 2.0, "ice": 0.5, "ground": 2.0, "flying": 2.0, "dragon": 2.0},
                "fighting": {"normal": 2.0, "ice": 2.0, "rock": 2.0, "dark": 2.0, "steel": 2.0, "poison": 0.5, "flying": 0.5, "psychic": 0.5, "bug": 0.5, "ghost": 0.0},
                "poison": {"normal": 1.0, "grass": 2.0, "poison": 0.5, "ground": 0.5, "rock": 0.5, "ghost": 0.5, "steel": 0.0},
                "ground": {"normal": 1.0, "fire": 2.0, "electric": 2.0, "grass": 0.5, "poison": 2.0, "flying": 0.0, "bug": 0.5, "rock": 2.0, "steel": 2.0},
                "flying": {"normal": 1.0, "grass": 2.0, "electric": 0.5, "fighting": 2.0, "bug": 2.0, "rock": 0.5, "steel": 0.5},
                "psychic": {"normal": 1.0, "fighting": 2.0, "poison": 2.0, "psychic": 0.5, "dark": 0.0, "steel": 0.5},
                "bug": {"normal": 1.0, "grass": 2.0, "fighting": 0.5, "poison": 0.5, "flying": 0.5, "psychic": 2.0, "ghost": 0.5, "dark": 2.0, "steel": 0.5, "fairy": 0.5},
                "rock": {"normal": 1.0, "fire": 2.0, "ice": 2.0, "fighting": 0.5, "ground": 0.5, "flying": 2.0, "bug": 2.0, "steel": 0.5},
                "ghost": {"normal": 0.0, "ghost": 2.0, "psychic": 2.0, "dark": 0.5},
                "dragon": {"normal": 1.0, "dragon": 2.0, "steel": 0.5, "fairy": 0.0},
                "dark": {"normal": 1.0, "ghost": 2.0, "psychic": 2.0, "fighting": 0.5, "dark": 0.5, "fairy": 0.5},
                "steel": {"normal": 1.0, "ice": 2.0, "rock": 2.0, "fairy": 2.0, "steel": 0.5, "fire": 0.5, "water": 0.5, "electric": 0.5},
                "fairy": {"normal": 1.0, "fighting": 2.0, "dragon": 2.0, "dark": 2.0, "poison": 0.5, "steel": 0.5, "fire": 0.5}
            }
            
            # Analyze offensive matchup
            for attacker_type in attacker_pokemon.types:
                if not attacker_type:
                    continue
                
                # Convert type to string and lowercase for dictionary lookup
                attacker_type_str = str(attacker_type).lower()
                
                # Calculate effectiveness using our type chart
                effectiveness = 1.0
                for defender_type in defender_pokemon.types:
                    if defender_type:
                        defender_type_str = str(defender_type).lower()
                        
                        # Check if we have this type combination in our chart
                        if attacker_type_str in type_chart and defender_type_str in type_chart.get(attacker_type_str, {}):
                            curr_effectiveness = type_chart[attacker_type_str][defender_type_str]
                        else:
                            # Default to neutral if we don't have data for this matchup
                            curr_effectiveness = 1.0
                            
                        # Store in cache for future use
                        type_key = f"{attacker_type_str}_{defender_type_str}"
                        self.effectiveness_cache[type_key] = curr_effectiveness
                        
                        effectiveness *= curr_effectiveness
                
                # Update matchup based on effectiveness
                if effectiveness > 1:
                    matchup["offensive_score"] += 1
                    matchup["super_effective_types"].append(str(attacker_type))
                    
                    if (matchup["best_offensive_type"] is None or 
                        effectiveness > matchup["best_offensive_type"][1]):
                        matchup["best_offensive_type"] = (str(attacker_type), effectiveness)
                
                elif effectiveness < 1:
                    matchup["offensive_score"] -= 1
                    if effectiveness == 0:
                        matchup["immunities"].append(str(attacker_type))
                    else:
                        matchup["not_effective_types"].append(str(attacker_type))
            
            # Analyze defensive matchup - use the same type chart but in reverse
            for defender_type in defender_pokemon.types:
                if not defender_type:
                    continue
                
                # For each attacking type, see how it affects the defender's type
                for attacking_type, effectiveness_dict in type_chart.items():
                    defender_type_str = str(defender_type).lower()
                    if defender_type_str in effectiveness_dict:
                        effectiveness = effectiveness_dict[defender_type_str]
                        
                        # Higher effectiveness means worse defense
                        if effectiveness > 1:
                            matchup["defensive_score"] -= 1
                            
                            if (matchup["worst_defensive_type"] is None or 
                                effectiveness > matchup["worst_defensive_type"][1]):
                                matchup["worst_defensive_type"] = (str(defender_type), effectiveness)
                        
                        # Lower effectiveness means better defense
                        elif effectiveness < 1:
                            matchup["defensive_score"] += 1
                
        except Exception as e:
            # If analysis fails for any reason, log the error and return a neutral matchup
            print(f"Error in analyze_matchup: {str(e)}")
            
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
            
        return matchup
    
    def rate_move_effectiveness(self, move, defender_pokemon) -> Tuple[float, str]:
        """
        Rate the effectiveness of a move against a defender.
        
        Args:
            move: The move to evaluate
            defender_pokemon: The defending Pokémon
            
        Returns:
            float: Effectiveness score (0-4)
            str: Explanation of the rating
        """
        # Base effectiveness from type matchup
        if not move.type:
            return 1.0, "Unknown move type"
            
        # Safely calculate type effectiveness
        try:
            # Use a simplified approach to calculate type effectiveness
            # based on known type matchups instead of relying on damage_multiplier
            
            # Predefined type effectiveness table (partial)
            # This is a simplified version of the type chart - in a real implementation
            # you would want to include all combinations
            type_chart = {
                "normal": {"normal": 1.0, "fighting": 1.0, "flying": 1.0, "rock": 0.5, "ghost": 0.0, "steel": 0.5},
                "fire": {"normal": 1.0, "fire": 0.5, "water": 0.5, "grass": 2.0, "ice": 2.0, "bug": 2.0, "rock": 0.5, "steel": 2.0},
                "water": {"normal": 1.0, "fire": 2.0, "water": 0.5, "grass": 0.5, "ground": 2.0, "rock": 2.0},
                "electric": {"normal": 1.0, "water": 2.0, "electric": 0.5, "grass": 0.5, "ground": 0.0, "flying": 2.0},
                "grass": {"normal": 1.0, "fire": 0.5, "water": 2.0, "grass": 0.5, "poison": 0.5, "ground": 2.0, "flying": 0.5, "bug": 0.5},
                "ice": {"normal": 1.0, "fire": 0.5, "water": 0.5, "grass": 2.0, "ice": 0.5, "ground": 2.0, "flying": 2.0, "dragon": 2.0},
                "fighting": {"normal": 2.0, "ice": 2.0, "rock": 2.0, "dark": 2.0, "steel": 2.0, "poison": 0.5, "flying": 0.5, "psychic": 0.5, "bug": 0.5, "ghost": 0.0},
                "poison": {"normal": 1.0, "grass": 2.0, "poison": 0.5, "ground": 0.5, "rock": 0.5, "ghost": 0.5, "steel": 0.0},
                "ground": {"normal": 1.0, "fire": 2.0, "electric": 2.0, "grass": 0.5, "poison": 2.0, "flying": 0.0, "bug": 0.5, "rock": 2.0, "steel": 2.0},
                "flying": {"normal": 1.0, "grass": 2.0, "electric": 0.5, "fighting": 2.0, "bug": 2.0, "rock": 0.5, "steel": 0.5},
                "psychic": {"normal": 1.0, "fighting": 2.0, "poison": 2.0, "psychic": 0.5, "dark": 0.0, "steel": 0.5},
                "bug": {"normal": 1.0, "grass": 2.0, "fighting": 0.5, "poison": 0.5, "flying": 0.5, "psychic": 2.0, "ghost": 0.5, "dark": 2.0, "steel": 0.5, "fairy": 0.5},
                "rock": {"normal": 1.0, "fire": 2.0, "ice": 2.0, "fighting": 0.5, "ground": 0.5, "flying": 2.0, "bug": 2.0, "steel": 0.5},
                "ghost": {"normal": 0.0, "ghost": 2.0, "psychic": 2.0, "dark": 0.5},
                "dragon": {"normal": 1.0, "dragon": 2.0, "steel": 0.5, "fairy": 0.0},
                "dark": {"normal": 1.0, "ghost": 2.0, "psychic": 2.0, "fighting": 0.5, "dark": 0.5, "fairy": 0.5},
                "steel": {"normal": 1.0, "ice": 2.0, "rock": 2.0, "fairy": 2.0, "steel": 0.5, "fire": 0.5, "water": 0.5, "electric": 0.5},
                "fairy": {"normal": 1.0, "fighting": 2.0, "dragon": 2.0, "dark": 2.0, "poison": 0.5, "steel": 0.5, "fire": 0.5}
            }
            
            # Safe string conversion since types might be objects or strings
            move_type_str = str(move.type).lower()
            
            type_effectiveness = 1.0
            for defender_type in defender_pokemon.types:
                if defender_type:
                    defender_type_str = str(defender_type).lower()
                    
                    # Try to get effectiveness from our chart
                    if move_type_str in type_chart and defender_type_str in type_chart.get(move_type_str, {}):
                        curr_effectiveness = type_chart[move_type_str][defender_type_str]
                    else:
                        # Default to neutral if not in our chart
                        curr_effectiveness = 1.0
                    
                    # Cache the effectiveness for future use
                    type_key = f"{move_type_str}_{defender_type_str}"
                    self.effectiveness_cache[type_key] = curr_effectiveness
                    
                    type_effectiveness *= curr_effectiveness
                    
        except Exception:
            # Default to neutral effectiveness if calculation fails
            type_effectiveness = 1.0
        
        # Start with base type effectiveness
        effectiveness_score = type_effectiveness
        
        # Check for STAB (Same Type Attack Bonus)
        # For our implementation, we'll check if the move type matches the active Pokemon's type
        has_stab = False
        try:
            # Instead of looking for 'battle', get types from the current battle context
            # We need to determine which Pokemon is actually using the move
            user_pokemon = None
            
            # This is a safer approach than relying on move.pokemon which doesn't exist
            if hasattr(move, '_BATTLE_CACHED_ATTR') and 'pokemon' in getattr(move, '_BATTLE_CACHED_ATTR', []):
                # If the move has a cached pokemon attribute, use it (unlikely in poke-env)
                user_pokemon = getattr(move, 'pokemon', None)
            else:
                # Otherwise, assume it's the current active Pokemon
                # This is an approximation but works well enough for most cases
                from poke_env.environment import Battle
                current_battle = None
                
                # Try to find the battle context
                if hasattr(defender_pokemon, 'battle'):
                    current_battle = defender_pokemon.battle
                
                if current_battle and isinstance(current_battle, Battle):
                    user_pokemon = current_battle.active_pokemon
            
            # If we found a user Pokemon, check for STAB
            if user_pokemon and hasattr(user_pokemon, 'types'):
                for poke_type in user_pokemon.types:
                    if poke_type and str(poke_type).lower() == str(move.type).lower():
                        has_stab = True
                        effectiveness_score *= 1.5
                        break
        except Exception:
            # Skip STAB bonus if there's an error
            pass
        
        # Adjust for move power (normalize to 0-1 range with sigmoid-like scaling)
        power_factor = min(1.0, move.base_power / 150)
        effectiveness_score *= (0.5 + power_factor / 2)
        
        # Adjust for critical hit moves
        if hasattr(move, 'crit_ratio') and move.crit_ratio and move.crit_ratio > 1:
            effectiveness_score *= 1.1
        
        # Explanation of the rating
        explanation = []
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
            
        return effectiveness_score, ", ".join(explanation)
    
    def analyze_team_coverage(self, team_pokemon, opponent_team=None):
        """
        Analyze how well a team covers different type matchups.
        
        Args:
            team_pokemon: List of Pokémon on the team
            opponent_team: Optional list of opponent's Pokémon
            
        Returns:
            dict: Analysis of type coverage and gaps
        """
        all_types = [
            'normal', 'fire', 'water', 'electric', 'grass', 'ice', 
            'fighting', 'poison', 'ground', 'flying', 'psychic', 'bug', 
            'rock', 'ghost', 'dragon', 'dark', 'steel', 'fairy'
        ]
        
        coverage = {type_name: 0 for type_name in all_types}
        team_types = set()
        
        # Collect all types on the team
        for pokemon in team_pokemon:
            for poke_type in pokemon.types:
                if poke_type:
                    team_types.add(str(poke_type).lower())
        
        # Calculate coverage against each type
        for pokemon in team_pokemon:
            # Get all the moves from this pokemon
            if hasattr(pokemon, 'moves'):
                for move in pokemon.moves.values():
                    if move and move.type:
                        for target_type in all_types:
                            try:
                                # Use poke-env's damage_multiplier to calculate effectiveness
                                # This requires move.type to have damage_multiplier method
                                if hasattr(move.type, 'damage_multiplier'):
                                    # We need to convert string to actual Type object
                                    # But since we don't have direct access to Type objects
                                    # We'll approximate based on observed effectiveness
                                    # against opponent Pokemon of this type
                                    for opp_pokemon in opponent_team or []:
                                        if opp_pokemon and opp_pokemon.types:
                                            for opp_type in opp_pokemon.types:
                                                if str(opp_type).lower() == target_type:
                                                    effectiveness = move.type.damage_multiplier(opp_type)
                                                    if effectiveness > 1:
                                                        coverage[target_type] += 1
                            except Exception as e:
                                # If there's an error in type calculations, continue without failing
                                pass
        
        # If we have no opponent team or couldn't calculate coverage, fall back to a simple measure
        if not opponent_team or sum(coverage.values()) == 0:
            # Simple type diversity measure
            for type_name in team_types:
                coverage[type_name] += 1
        
        # Find gaps in coverage (types with 0 or low coverage)
        coverage_gaps = [type_name for type_name, count in coverage.items() if count == 0]
        
        return {
            "team_types": sorted(list(team_types)),
            "coverage": coverage,
            "coverage_gaps": coverage_gaps,
            "coverage_score": sum(coverage.values()) / len(all_types)
        }