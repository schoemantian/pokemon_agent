"""
GAIA Pokémon Battle Agent - A custom implementation for Pokémon battles.

This file contains your custom agent implementation based on the LLMAgentBase.
The agent uses an LLM to make strategic battle decisions.
"""

import os
import asyncio
from typing import Dict, Any, Optional, List
from dotenv import load_dotenv

from agents import LLMAgentBase, AnthropicAgent, OpenAIAgent, GeminiAgent
from utils import normalize_name, format_battle_state, TypeAnalyzer

# Load environment variables
load_dotenv()

# Customize your agent by selecting which LLM provider to use
# You can choose between 'openai', 'anthropic', or 'gemini'
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "anthropic")


class BattleMemory:
    """Advanced memory system to track battle patterns and opponent strategies."""
    
    def __init__(self, max_history=10):
        # Track overall battle state history
        self.state_history = []
        self.max_history = max_history
        
        # Track opponent's Pokémon and their moves
        self.opponent_pokemon = {}
        
        # Track successful and unsuccessful moves
        self.move_outcomes = {
            "successful": {},  # Moves that worked well
            "unsuccessful": {}  # Moves that didn't work well
        }
        
        # Track type effectiveness observations
        self.type_effectiveness = {}
        
        # Track opponent's patterns
        self.opponent_patterns = {
            "switches": [],  # When opponent switches
            "repeated_moves": {}  # Frequency of move usage
        }

    def update_state_history(self, battle_state):
        """Add current battle state to history."""
        self.state_history.append(battle_state)
        if len(self.state_history) > self.max_history:
            self.state_history = self.state_history[-self.max_history:]
    
    def record_opponent_pokemon(self, pokemon):
        """Record information about opponent's Pokémon."""
        if pokemon.species not in self.opponent_pokemon:
            self.opponent_pokemon[pokemon.species] = {
                "types": pokemon.types,
                "moves": [],
                "ability": pokemon.ability,
                "item": pokemon.item
            }
        
        # Update existing knowledge with new observations
        for move in pokemon.moves.values():
            if move.id not in [m["id"] for m in self.opponent_pokemon[pokemon.species]["moves"]]:
                self.opponent_pokemon[pokemon.species]["moves"].append({
                    "id": move.id,
                    "type": move.type,
                    "base_power": move.base_power
                })
    
    def record_move_outcome(self, move, was_effective, context):
        """Record if a move was effective or not."""
        category = "successful" if was_effective else "unsuccessful"
        if move.id not in self.move_outcomes[category]:
            self.move_outcomes[category][move.id] = []
        
        self.move_outcomes[category][move.id].append(context)
    
    def record_type_effectiveness(self, attacker_type, defender_types, effectiveness):
        """Record observed type effectiveness."""
        key = f"{attacker_type} vs {'/'.join(str(t) for t in defender_types if t)}"
        self.type_effectiveness[key] = effectiveness
    
    def record_opponent_switch(self, trigger_context):
        """Record when opponent switches and potential triggers."""
        self.opponent_patterns["switches"].append(trigger_context)
    
    def record_opponent_move(self, move_id):
        """Record opponent's move usage patterns."""
        if move_id not in self.opponent_patterns["repeated_moves"]:
            self.opponent_patterns["repeated_moves"][move_id] = 0
        self.opponent_patterns["repeated_moves"][move_id] += 1
    
    def get_formatted_memory(self):
        """Format memory for LLM consumption."""
        memory_str = "Battle Memory Analysis:\n"
        
        # Add opponent Pokémon knowledge
        if self.opponent_pokemon:
            memory_str += "\nOpponent's Team Knowledge:\n"
            for species, data in self.opponent_pokemon.items():
                moves_str = ", ".join([m["id"] for m in data["moves"]]) if data["moves"] else "Unknown"
                memory_str += f"- {species}: Types: {'/'.join(str(t) for t in data['types'] if t)}, "
                memory_str += f"Moves: {moves_str}, Ability: {data['ability']}\n"
        
        # Add move effectiveness patterns
        if self.move_outcomes["successful"] or self.move_outcomes["unsuccessful"]:
            memory_str += "\nMove Effectiveness Patterns:\n"
            
            # Successful moves
            if self.move_outcomes["successful"]:
                memory_str += "- Effective moves:\n"
                for move_id, contexts in self.move_outcomes["successful"].items():
                    if len(contexts) > 1:  # Only include if observed multiple times
                        memory_str += f"  * {move_id} was effective {len(contexts)} times\n"
            
            # Unsuccessful moves
            if self.move_outcomes["unsuccessful"]:
                memory_str += "- Ineffective moves:\n"
                for move_id, contexts in self.move_outcomes["unsuccessful"].items():
                    if len(contexts) > 1:  # Only include if observed multiple times
                        memory_str += f"  * {move_id} was ineffective {len(contexts)} times\n"
        
        # Add opponent patterns
        if self.opponent_patterns["repeated_moves"]:
            memory_str += "\nOpponent's Patterns:\n"
            frequent_moves = sorted(
                self.opponent_patterns["repeated_moves"].items(), 
                key=lambda x: x[1], 
                reverse=True
            )
            for move_id, count in frequent_moves[:3]:  # Top 3 most frequent moves
                memory_str += f"- Opponent frequently uses {move_id} ({count} times)\n"
        
        return memory_str


class StrategicDecisionEngine:
    """
    Advanced strategic decision engine for Pokémon battles.
    
    This system evaluates possible moves and switches based on multiple factors
    and provides strategic recommendations.
    """
    
    def __init__(self, battle_memory=None, type_analyzer=None):
        self.battle_memory = battle_memory
        self.type_analyzer = type_analyzer
        
        # Strategy weights - can be fine-tuned
        self.weights = {
            "type_advantage": 2.0,
            "hp_preservation": 1.5,
            "status_effects": 1.2,
            "setup_moves": 1.0,
            "predicted_opponent_move": 1.8,
            "weather_synergy": 0.8
        }
        
        # Track game state
        self.turn_count = 0
        self.remaining_pokemon_count = 0
        self.opponent_remaining_count = 0
        
        # Battle phases
        self.PHASE_EARLY = "early"
        self.PHASE_MID = "mid"
        self.PHASE_LATE = "late"
        
        # Strategy profiles
        self.strategy_profiles = {
            self.PHASE_EARLY: {
                "setup": 1.5,
                "offensive": 1.0,
                "defensive": 0.8
            },
            self.PHASE_MID: {
                "setup": 0.7,
                "offensive": 1.5,
                "defensive": 1.0
            },
            self.PHASE_LATE: {
                "setup": 0.3,
                "offensive": 2.0,
                "defensive": 1.2
            }
        }
    
    def update_game_state(self, battle):
        """Update internal game state tracking."""
        self.turn_count = battle.turn
        self.remaining_pokemon_count = sum(1 for p in battle.team.values() if not p.fainted)
        self.opponent_remaining_count = sum(1 for p in battle.opponent_team.values() if not p.fainted)
    
    def get_battle_phase(self):
        """Determine the current battle phase."""
        # Simple phase determination based on turns and remaining Pokémon
        if self.turn_count <= 2:
            return self.PHASE_EARLY
        elif self.remaining_pokemon_count <= 2 or self.opponent_remaining_count <= 2:
            return self.PHASE_LATE
        else:
            return self.PHASE_MID
    
    def should_switch(self, battle):
        """Determine if the active Pokémon should switch out."""
        active_pokemon = battle.active_pokemon
        opponent_pokemon = battle.opponent_active_pokemon
        
        # Don't recommend switch if there are no available switches
        if not battle.available_switches:
            return False, None, 0
            
        # Check for critical health
        critical_health = active_pokemon.current_hp_fraction <= 0.25
        
        # Check for bad type matchup
        bad_matchup = False
        if self.type_analyzer and active_pokemon and opponent_pokemon:
            matchup = self.type_analyzer.analyze_matchup(active_pokemon, opponent_pokemon)
            bad_matchup = matchup["recommendation"] in ["DISADVANTAGE", "STRONG_DISADVANTAGE"]
        
        # Check for negative status conditions
        bad_status = active_pokemon.status is not None and active_pokemon.status.name not in ["PSN", ""]
        
        # Check if trapped
        trapped = battle.trapped or battle.maybe_trapped
        
        # If trapped, can't switch
        if trapped:
            return False, None, 0
            
        # Calculate switch score
        switch_score = 0
        switch_score += 2.0 if critical_health else 0
        switch_score += 1.5 if bad_matchup else 0
        switch_score += 1.0 if bad_status else 0
        
        # Find best switch-in if score is high enough
        if switch_score >= 1.5 and battle.available_switches:
            best_switch = None
            best_score = -float('inf')
            
            for pokemon in battle.available_switches:
                if not opponent_pokemon:
                    # If we don't know opponent, just check HP
                    score = pokemon.current_hp_fraction
                else:
                    # Analyze matchup
                    matchup = self.type_analyzer.analyze_matchup(pokemon, opponent_pokemon) if self.type_analyzer else {"overall_score": 0}
                    
                    # Calculate switch score based on matchup and HP
                    score = (matchup.get("overall_score", 0) * 0.7) + (pokemon.current_hp_fraction * 0.3)
                
                if score > best_score:
                    best_score = score
                    best_switch = pokemon
            
            return True, best_switch, switch_score
        
        return False, None, switch_score
    
    def evaluate_moves(self, battle):
        """
        Evaluate all available moves and return them with scores.
        
        Returns:
            list: Sorted list of (move, score, explanation) tuples
        """
        if not battle.available_moves:
            return []
            
        active_pokemon = battle.active_pokemon
        opponent_pokemon = battle.opponent_active_pokemon
        
        move_evaluations = []
        current_phase = self.get_battle_phase()
        phase_profile = self.strategy_profiles[current_phase]
        
        for move in battle.available_moves:
            score = 0
            explanations = []
            
            # Base move power (0-3 points)
            power_score = min(3.0, move.base_power / 40)
            score += power_score
            if move.base_power >= 100:
                explanations.append("High power move")
            
            # Type effectiveness (0-5 points)
            if self.type_analyzer and opponent_pokemon:
                effectiveness_score, explanation = self.type_analyzer.rate_move_effectiveness(move, opponent_pokemon)
                score += effectiveness_score * self.weights["type_advantage"]
                explanations.append(explanation)
            
            # Status moves
            if move.category.name == "STATUS":
                # Boost moves are more valuable early game
                if "boost" in move.id or any(word in move.id for word in ["swords", "nasty", "dragon", "quiver", "bulk"]):
                    score += 2.0 * phase_profile["setup"]
                    explanations.append("Stat boosting move")
                
                # Status effect moves
                elif any(word in move.id for word in ["toxic", "paralyze", "sleep", "confuse"]):
                    score += 1.5 * phase_profile["defensive"]
                    explanations.append("Status effect move")
                
                # Entry hazards more valuable early
                elif any(word in move.id for word in ["spikes", "toxic-spikes", "stealth-rock"]):
                    score += (3.0 if current_phase == self.PHASE_EARLY else 1.0)
                    explanations.append("Entry hazard move")
                    
                # Support moves
                elif any(word in move.id for word in ["heal", "protect", "wish", "substitute"]):
                    # More valuable when HP is lower
                    hp_factor = 2.0 - active_pokemon.current_hp_fraction
                    score += hp_factor * phase_profile["defensive"]
                    explanations.append("Support/healing move")
                
                # Default score for other status moves
                else:
                    score += 1.0
                    explanations.append("Status move")
            
            # Weather and terrain moves
            if any(word in move.id for word in ["rain", "sun", "hail", "sand", "terrain"]):
                score += 2.0 if current_phase == self.PHASE_EARLY else 1.0
                explanations.append("Weather/terrain move")
            
            # Move with secondary effects
            if hasattr(move, "secondary") and move.secondary:
                score += 0.5
                explanations.append("Has secondary effect")
            
            # PP consideration
            if move.current_pp <= 5:
                score -= 0.3
                explanations.append("Low PP remaining")
            
            # Final score adjustments based on phase
            if move.category.name == "PHYSICAL" or move.category.name == "SPECIAL":
                score *= phase_profile["offensive"]
            
            move_evaluations.append((move, score, ", ".join(explanations)))
        
        # Sort by score in descending order
        return sorted(move_evaluations, key=lambda x: x[1], reverse=True)
    
    def get_strategic_decision(self, battle):
        """
        Get the strategic decision for the current battle state.
        
        Returns:
            dict: Decision information with explanation
        """
        try:
            self.update_game_state(battle)
            
            # Check if we should switch
            try:
                should_switch, best_switch, switch_score = self.should_switch(battle)
                
                if should_switch and best_switch:
                    return {
                        "action": "switch",
                        "target": best_switch,
                        "score": switch_score,
                        "explanation": f"Switching to {best_switch.species} due to unfavorable position"
                    }
            except Exception:
                # Continue if switch evaluation fails
                pass
            
            # Evaluate moves if not switching
            try:
                evaluated_moves = self.evaluate_moves(battle)
                
                if evaluated_moves:
                    best_move, best_score, explanation = evaluated_moves[0]
                    
                    # Check for Terastallize opportunity
                    should_tera = False
                    if battle.can_tera:
                        # Strategic use of Terastallize - save for powerful moves or critical moments
                        if (best_move.base_power > 90 or 
                            battle.active_pokemon.current_hp_fraction < 0.5 or
                            self.turn_count > 5):
                            should_tera = True
                    
                    return {
                        "action": "move",
                        "target": best_move,
                        "score": best_score,
                        "explanation": explanation,
                        "terastallize": should_tera
                    }
            except Exception:
                # Continue if move evaluation fails
                pass
            
        except Exception:
            # Fall through to random action if any major error occurs
            pass
            
        # Choose a simple action based on available options
        if battle.available_moves:
            # Pick the highest base power move
            best_move = max(battle.available_moves, key=lambda m: m.base_power)
            return {
                "action": "move",
                "target": best_move,
                "score": 5.0,
                "explanation": "Fallback to highest power move",
                "terastallize": battle.can_tera
            }
        elif battle.available_switches:
            # Pick the switch with highest HP
            best_switch = max(battle.available_switches, key=lambda p: p.current_hp_fraction)
            return {
                "action": "switch",
                "target": best_switch,
                "score": 2.0,
                "explanation": "Fallback to highest HP switch"
            }
        
        # Final fallback to random action
        return {
            "action": "random",
            "explanation": "No clear strategic move available"
        }


class GAIAAgent(LLMAgentBase):
    """
    GAIA Pokémon Battle Agent based on LLM.
    
    This agent uses an LLM to make intelligent battle decisions by analyzing
    the current battle state, considering type advantages, move effectiveness,
    and other strategic factors.
    """
    
    def __init__(self, battle_format: str = "gen9randombattle", *args, **kwargs):
        """
        Initialize the GAIA agent.
        
        Args:
            battle_format: The format to use for battles
            args: Additional arguments to pass to the parent class
            kwargs: Additional keyword arguments to pass to the parent class
        """
        super().__init__(battle_format=battle_format, *args, **kwargs)
        
        # Initialize battle memory
        self.battle_memory = BattleMemory()
        
        # Initialize type analyzer
        self.type_analyzer = TypeAnalyzer()
        
        # Initialize strategic decision engine
        self.strategy_engine = StrategicDecisionEngine(
            battle_memory=self.battle_memory,
            type_analyzer=self.type_analyzer
        )
        
        # Choose the LLM provider based on the environment variable
        if LLM_PROVIDER == "openai":
            api_key = os.getenv("OPENAI_API_KEY")
            self.llm_client = OpenAIAgent(
                api_key=api_key,
                model="gpt-4o",
                battle_format=battle_format,
                *args, **kwargs
            )
        elif LLM_PROVIDER == "gemini":
            api_key = os.getenv("GEMINI_API_KEY")
            self.llm_client = GeminiAgent(
                api_key=api_key,
                model="gemini-pro",
                battle_format=battle_format,
                *args, **kwargs
            )
        else:  # Default to Anthropic
            api_key = os.getenv("ANTHROPIC_API_KEY")
            self.llm_client = AnthropicAgent(
                api_key=api_key,
                model="claude-3-opus-20240229",
                battle_format=battle_format,
                *args, **kwargs
            )
    
    def _analyze_current_matchup(self, battle):
        """
        Analyze the current battle matchup using the TypeAnalyzer.
        
        Args:
            battle: The current battle state
            
        Returns:
            str: A formatted analysis of the current matchup
        """
        try:
            if not battle.active_pokemon or not battle.opponent_active_pokemon:
                return "Insufficient data for type analysis."
            
            # Analyze overall matchup
            matchup = self.type_analyzer.analyze_matchup(
                battle.active_pokemon,
                battle.opponent_active_pokemon
            )
            
            # Start building the analysis
            analysis = f"Type Matchup Analysis:\n"
            
            # Overall matchup summary
            analysis += f"Matchup: {matchup['recommendation']} (Score: {matchup['overall_score']})\n"
            
            if matchup.get("best_offensive_type"):
                type_name, effectiveness = matchup["best_offensive_type"]
                analysis += f"Best offensive type: {type_name} (x{effectiveness})\n"
                
            if matchup.get("super_effective_types"):
                analysis += f"Super effective types: {', '.join(matchup['super_effective_types'])}\n"
                
            if matchup.get("immunities"):
                analysis += f"Opponent immune to: {', '.join(matchup['immunities'])}\n"
                
            # Rate available moves against opponent - with error handling
            move_ratings = []
            if battle.available_moves:
                # Process each move safely
                for move in battle.available_moves:
                    try:
                        # Use the improved rate_move_effectiveness method
                        effectiveness_score, explanation = self.type_analyzer.rate_move_effectiveness(
                            move, 
                            battle.opponent_active_pokemon
                        )
                        
                        move_ratings.append({
                            "move": move.id,
                            "effectiveness": effectiveness_score,
                            "explanation": explanation
                        })
                    except Exception as e:
                        # If rating a specific move fails, add a basic entry
                        move_ratings.append({
                            "move": move.id,
                            "effectiveness": 1.0,
                            "explanation": f"Basic move (error: {str(e)[:30]}...)" 
                        })
                
                # Sort moves by effectiveness (high to low)
                move_ratings.sort(key=lambda x: x["effectiveness"], reverse=True)
                
                # Move recommendations
                analysis += "\nMove Recommendations:\n"
                for i, rating in enumerate(move_ratings[:3]):  # Top 3 moves
                    analysis += f"{i+1}. {rating['move']} - Score: {rating['effectiveness']:.1f} ({rating['explanation']})\n"
            else:
                analysis += "\nNo moves available for analysis."
            
            return analysis
            
        except Exception as e:
            # Return a more helpful error message that includes the exception
            return f"Type analysis unavailable. Error: {str(e)[:50]}... Use best judgment."
    
    def _get_strategic_analysis(self, battle):
        """
        Get a strategic analysis and recommendation for the current battle state.
        
        Args:
            battle: The current battle state
            
        Returns:
            str: Formatted strategic analysis
        """
        # Get strategic decision
        decision = self.strategy_engine.get_strategic_decision(battle)
        
        # Format the analysis
        analysis = "Strategic Analysis:\n"
        
        # Decision recommendation
        if decision["action"] == "switch":
            analysis += f"Recommendation: Switch to {decision['target'].species}\n"
            analysis += f"Reasoning: {decision['explanation']}\n"
            analysis += f"Confidence: {decision['score']:.2f}/5.0\n"
        
        elif decision["action"] == "move":
            move = decision["target"]
            analysis += f"Recommendation: Use {move.id}\n"
            analysis += f"Reasoning: {decision['explanation']}\n"
            analysis += f"Confidence: {decision['score']:.2f}/10.0\n"
            
            if decision.get("terastallize", False):
                analysis += "Recommend Terastallizing this turn\n"
        
        else:
            analysis += "No clear strategic recommendation available\n"
        
        # Battle phase information
        phase = self.strategy_engine.get_battle_phase()
        analysis += f"\nBattle Phase: {phase.upper()}\n"
        analysis += f"Your Pokémon remaining: {self.strategy_engine.remaining_pokemon_count}\n"
        analysis += f"Opponent Pokémon remaining: {self.strategy_engine.opponent_remaining_count}\n"
        
        # If we're evaluating moves, add top move evaluations
        if battle.available_moves:
            evaluated_moves = self.strategy_engine.evaluate_moves(battle)
            
            if evaluated_moves:
                analysis += "\nMove Evaluations:\n"
                for i, (move, score, explanation) in enumerate(evaluated_moves[:3]):  # Top 3
                    analysis += f"{i+1}. {move.id}: {score:.2f} ({explanation})\n"
        
        return analysis
    
    def _update_battle_memory(self, battle):
        """
        Update the battle memory with new information from the current battle state.
        
        Args:
            battle: The current battle state
        """
        # Update state history
        battle_state_str = format_battle_state(battle)
        self.battle_memory.update_state_history(battle_state_str)
        
        # Record opponent's active Pokémon information
        if battle.opponent_active_pokemon:
            self.battle_memory.record_opponent_pokemon(battle.opponent_active_pokemon)
        
        # Instead of using battle_logs which doesn't exist, 
        # we'll use the last move information directly from the Pokémon objects
        
        # Track opponent's last move
        if (battle.opponent_active_pokemon and 
            hasattr(battle.opponent_active_pokemon, 'last_used_move') and
            battle.opponent_active_pokemon.last_used_move):
            
            move_id = battle.opponent_active_pokemon.last_used_move.id
            self.battle_memory.record_opponent_move(move_id)
        
        # Track when opponent switches - based on opponent_team changes
        if hasattr(battle, 'opponent_team') and battle.opponent_active_pokemon:
            # Record switch context
            context = {"previous_hp": battle.active_pokemon.current_hp_fraction}
            if hasattr(battle.active_pokemon, 'last_used_move') and battle.active_pokemon.last_used_move:
                context["our_move"] = battle.active_pokemon.last_used_move
            self.battle_memory.record_opponent_switch(context)
        
        # Track move effectiveness based on the last move used
        if (hasattr(battle.active_pokemon, 'last_used_move') and 
            battle.active_pokemon.last_used_move and 
            battle.opponent_active_pokemon):
            
            last_move = battle.active_pokemon.last_used_move
            
            # Get effectiveness based on type matchup safely
            effectiveness = 1.0  # Default to neutral
            if last_move.type and battle.opponent_active_pokemon.types:
                try:
                    # Calculate manually for safety
                    for defender_type in battle.opponent_active_pokemon.types:
                        if defender_type:
                            # Use cached effectiveness if available
                            type_key = f"{last_move.type}_{defender_type}"
                            if hasattr(self, 'type_analyzer') and type_key in self.type_analyzer.effectiveness_cache:
                                curr_effectiveness = self.type_analyzer.effectiveness_cache[type_key]
                            else:
                                # Default to neutral for now
                                curr_effectiveness = 1.0
                            effectiveness *= curr_effectiveness
                except Exception:
                    # Default to neutral if calculation fails
                    effectiveness = 1.0
                
                if effectiveness > 1.0:
                    # Record super effective move
                    self.battle_memory.record_move_outcome(last_move, True, {
                        "opponent": battle.opponent_active_pokemon.species,
                        "hp_fraction_before": getattr(battle.opponent_active_pokemon, "current_hp_fraction", 1.0),
                        "effectiveness": "super effective"
                    })
                    
                    # Also record type effectiveness
                    self.battle_memory.record_type_effectiveness(
                        last_move.type, 
                        battle.opponent_active_pokemon.types, 
                        effectiveness
                    )
                
                elif effectiveness < 1.0:
                    # Record not very effective move
                    self.battle_memory.record_move_outcome(last_move, False, {
                        "opponent": battle.opponent_active_pokemon.species,
                        "effectiveness": "not very effective"
                    })
                    
                    # Record type effectiveness
                    self.battle_memory.record_type_effectiveness(
                        last_move.type, 
                        battle.opponent_active_pokemon.types, 
                        effectiveness
                    )
    
    async def _get_llm_decision(self, battle_state: str) -> Dict[str, Any]:
        """
        Get a decision from the LLM for the current battle state.
        
        This method customizes the prompt for the GAIA agent to make it more strategic.
        
        Args:
            battle_state: The formatted battle state
            
        Returns:
            A dictionary containing the decision and possibly error information
        """
        # Enhanced system prompt with more strategic guidance and battle memory
        system_prompt = (
            "You are GAIA, an expert Pokémon battle strategist with deep knowledge of type matchups, "
            "move effectiveness, and battle mechanics. Your goal is to win Pokémon battles by making "
            "optimal decisions each turn.\n\n"
            
            "For each turn, analyze the following:\n"
            "1. Type matchups: Consider your Pokémon's types vs the opponent's Pokémon's types\n"
            "2. Move effectiveness: Prioritize super-effective moves when available\n"
            "3. Status conditions: Consider current status of both Pokémon and their effects\n"
            "4. HP levels: Switch out if your Pokémon is low on HP\n"
            "5. Weather and field conditions: Use moves that benefit from current conditions\n"
            "6. Boost stats: Consider moves that increase your stats or decrease opponent's\n\n"
            
            "You MUST respond using the provided tools. Do not provide explanations or additional text."
        )
        
        # Add battle memory and type analysis to the user prompt
        memory_str = self.battle_memory.get_formatted_memory()
        
        # Get type analysis if there's a battle object
        type_analysis = ""
        strategic_analysis = ""
        if hasattr(self, "current_battle") and self.current_battle:
            type_analysis = self._analyze_current_matchup(self.current_battle)
            strategic_analysis = self._get_strategic_analysis(self.current_battle)
        
        user_prompt = (
            f"Current battle state:\n{battle_state}\n\n"
            f"{memory_str}\n\n"
            f"{type_analysis}\n\n"
            f"{strategic_analysis}\n\n"
            "Please make a strategic decision for this turn."
        )
        
        # Update the LLM client with the new prompts
        self.llm_client.system_prompt = system_prompt
        
        # Use the underlying LLM client to get the decision
        return await self.llm_client._get_llm_decision(user_prompt)
    
    def _apply_strategic_decision(self, battle):
        """
        Apply the strategic decision directly without LLM involvement if confidence is high.
        
        Returns:
            str or None: Action to take or None if deferring to LLM
        """
        try:
            # Get the strategic decision
            decision = self.strategy_engine.get_strategic_decision(battle)
            
            # If the confidence is very high, apply the decision directly
            if decision["action"] == "switch" and decision["score"] >= 3.5:
                return f"/switch {battle.available_switches.index(decision['target']) + 1}"
                
            if decision["action"] == "move" and decision["score"] >= 7.0:
                move_command = f"/move {battle.available_moves.index(decision['target']) + 1}"
                
                # Add terastallize if recommended
                if decision.get("terastallize") and battle.can_tera:
                    move_command += " terastallize"
                    
                return move_command
        except Exception:
            # If there's any error in strategic decision making, just continue to LLM
            pass
            
        # Otherwise defer to LLM
        return None
        
    async def choose_move(self, battle):
        """
        Choose a move for the current turn based on strategic analysis and LLM decision.
        
        This method tries to make optimal decisions using the strategic engine when confidence 
        is high, and falls back to LLM decision-making for more complex situations.
        
        Args:
            battle: The current battle state
            
        Returns:
            A string representing the chosen action in Pokémon Showdown format
        """
        # Store current battle for type analysis
        self.current_battle = battle
        
        # Update battle memory with current state
        self._update_battle_memory(battle)
        
        # Track battle history for context
        battle_state_str = format_battle_state(battle)
        self.battle_history.append(battle_state_str)
        
        # Keep history limited to last 10 turns to avoid token limits
        if len(self.battle_history) > 10:
            self.battle_history = self.battle_history[-10:]
        
        # Try to apply strategic decision directly if confidence is high enough
        strategic_action = self._apply_strategic_decision(battle)
        if strategic_action:
            return strategic_action
            
        try:
            # Otherwise use the parent implementation to choose a move with LLM
            return await super().choose_move(battle)
        except AttributeError as e:
            # Handle the str object message attribute error and other potential errors
            if "message" in str(e):
                # If there's an error with message attribute, fall back to default move
                print(f"Error in LLM decision making: {e}. Falling back to highest power move.")
                
                # Choose the highest base power move as a fallback
                if battle.available_moves:
                    best_move = max(battle.available_moves, key=lambda m: m.base_power)
                    return self.create_order(best_move)
                elif battle.available_switches:
                    # If we can't move, switch to the Pokémon with highest HP
                    best_switch = max(battle.available_switches, key=lambda p: p.current_hp_fraction)
                    return self.create_order(best_switch)
                else:
                    # Last resort - struggle
                    return self.choose_default_move(battle)
            else:
                # For other attribute errors, re-raise
                raise
        
    def teampreview(self, battle):
        """
        Choose the team order during the team preview phase.
        
        This method uses the TypeAnalyzer to determine the best lead Pokémon
        based on the opponent's team composition.
        
        Args:
            battle: The current battle state
            
        Returns:
            A string representing the team order in Pokémon Showdown format
        """
        # For team preview, use type analysis to pick the lead
        if battle.teampreview_opponent_team and battle.teampreview_team:
            # Store the current battle for later reference
            self.current_battle = battle
            
            # Analyze team coverage
            team_coverage = self.type_analyzer.analyze_team_coverage(
                list(battle.teampreview_team)
            )
            
            # Simple type-based ordering - put Pokémon with type advantage first
            my_team = list(battle.teampreview_team)
            opponent_team = list(battle.teampreview_opponent_team)
            
            # This is a simple ranking based on perceived effectiveness
            ranked_mons = []
            
            for i, mon in enumerate(my_team):
                # Advanced scoring based on matchups against all opponent Pokémon
                score = 0
                for opp_mon in opponent_team:
                    # Use our type analyzer for better matchup analysis
                    matchup = self.type_analyzer.analyze_matchup(mon, opp_mon)
                    score += matchup["overall_score"]
                
                ranked_mons.append((i, score))
            
            # Sort by score (higher is better)
            ordered_mons = [i for i, _ in sorted(ranked_mons, key=lambda x: -x[1])]
            
            # Format the team order for Pokémon Showdown
            # We use i + 1 because Showdown's indexes start from 1, not 0
            return "/team " + "".join([str(i + 1) for i in ordered_mons])
        
        # Fallback to default order
        return "/team 123456"