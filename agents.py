"""
Pokémon Battle Agents using LLMs for decision making.

This module contains the base agent class and specific implementations
for different LLM providers.
"""

import json
import asyncio
import os
import traceback
from typing import Dict, Any, Optional, List, Tuple
import logging
from abc import ABC

import openai
import anthropic
import google.generativeai as genai
from poke_env.player import Player
from poke_env.environment import AbstractBattle, Battle, Pokemon, Move

from utils import normalize_name, extract_function_call, format_battle_state

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("pokemon_agent_debug.log")
    ]
)
logger = logging.getLogger("agents")

# Define the standard tool schema for battle actions
STANDARD_TOOL_SCHEMA = {
    "choose_move": {
        "description": "Choose a move for your Pokémon to use",
        "parameters": {
            "type": "object",
            "properties": {
                "move_name": {
                    "type": "string",
                    "description": "The name of the move to use. Must be one of the available moves."
                }
            },
            "required": ["move_name"]
        }
    },
    "choose_switch": {
        "description": "Switch your active Pokémon with one from your team",
        "parameters": {
            "type": "object",
            "properties": {
                "pokemon_name": {
                    "type": "string",
                    "description": "The name of the Pokémon to switch to. Must be one of the available Pokémon."
                }
            },
            "required": ["pokemon_name"]
        }
    }
}

class LLMAgentBase(Player):
    """Base class for LLM-powered Pokémon battle agents."""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.standard_tools = STANDARD_TOOL_SCHEMA
        self.battle_history = []
        
    def _format_battle_state(self, battle: Battle) -> str:
        """Format the battle state for the LLM."""
        return format_battle_state(battle)
        
    def _find_move_by_name(self, battle: Battle, move_name: str) -> Optional[Move]:
        """Find a move by name from the available moves."""
        normalized_name = normalize_name(move_name)
        
        # Prioritize exact ID match
        for move in battle.available_moves:
            if move.id == normalized_name:
                return move
                
        # Fallback: Check display name (less reliable)
        for move in battle.available_moves:
            if move.name.lower() == move_name.lower():
                print(f"Warning: Matched move by display name '{move.name}' instead of ID '{move.id}'. Input was '{move_name}'.")
                return move
                
        return None
        
    def _find_pokemon_by_name(self, battle: Battle, pokemon_name: str) -> Optional[Pokemon]:
        """Find a Pokémon by name from the available switches."""
        normalized_name = normalize_name(pokemon_name)
        
        for pkmn in battle.available_switches:
            # Normalize the species name for comparison
            if normalize_name(pkmn.species) == normalized_name:
                return pkmn
                
        return None
        
    async def choose_move(self, battle: Battle) -> str:
        """
        Choose a move for the current turn based on LLM decision.
        
        Args:
            battle: The current battle state.
            
        Returns:
            A string representing the chosen action in Pokémon Showdown format.
        """
        battle_tag = getattr(battle, 'battle_tag', 'unknown')
        logger.info(f"[Battle {battle_tag}] Choosing move for turn {battle.turn}")
        
        try:
            # Log available moves and switches for debugging
            available_moves = ", ".join([f"{m.id}(BP:{m.base_power})" for m in battle.available_moves]) if battle.available_moves else "None"
            available_switches = ", ".join([f"{p.species}(HP:{p.current_hp_fraction*100:.1f}%)" for p in battle.available_switches]) if battle.available_switches else "None"
            
            logger.debug(f"[Battle {battle_tag}] Available moves: {available_moves}")
            logger.debug(f"[Battle {battle_tag}] Available switches: {available_switches}")
            
            # Format battle state and get LLM decision
            battle_state_str = self._format_battle_state(battle)
            logger.debug(f"[Battle {battle_tag}] Formatted battle state: {battle_state_str}")
            
            logger.info(f"[Battle {battle_tag}] Requesting decision from LLM")
            decision_result = await self._get_llm_decision(battle_state_str)
            logger.debug(f"[Battle {battle_tag}] LLM decision result: {json.dumps(decision_result, indent=2)}")
            
            decision = decision_result.get("decision")
            error_message = decision_result.get("error")
            action_taken = False
            fallback_reason = ""
            
            if decision:
                function_name = decision.get("name")
                args = decision.get("arguments", {})
                logger.info(f"[Battle {battle_tag}] LLM decision: {function_name} with args: {args}")
                
                if function_name == "choose_move":
                    move_name = args.get("move_name")
                    if move_name:
                        logger.debug(f"[Battle {battle_tag}] Finding move: {move_name}")
                        chosen_move = self._find_move_by_name(battle, move_name)
                        
                        if chosen_move:
                            logger.debug(f"[Battle {battle_tag}] Found move: {chosen_move.id}")
                            if chosen_move in battle.available_moves:
                                action_taken = True
                                
                                # Check if we can terastallize
                                if battle.can_tera:
                                    chat_msg = f"AI Decision: Using move '{chosen_move.id}' with Terastallize."
                                    logger.info(f"[Battle {battle_tag}] {chat_msg}")
                                    return self.create_order(chosen_move, terastallize=True)
                                else:
                                    chat_msg = f"AI Decision: Using move '{chosen_move.id}'."
                                    logger.info(f"[Battle {battle_tag}] {chat_msg}")
                                    return self.create_order(chosen_move)
                            else:
                                fallback_reason = f"LLM chose unavailable move '{move_name}' (found as {chosen_move.id} but not in available moves)"
                        else:
                            fallback_reason = f"LLM chose invalid move '{move_name}' that could not be found"
                    else:
                        fallback_reason = "LLM 'choose_move' called without 'move_name'."
                        
                elif function_name == "choose_switch":
                    pokemon_name = args.get("pokemon_name")
                    if pokemon_name:
                        logger.debug(f"[Battle {battle_tag}] Finding Pokemon: {pokemon_name}")
                        chosen_switch = self._find_pokemon_by_name(battle, pokemon_name)
                        
                        if chosen_switch:
                            logger.debug(f"[Battle {battle_tag}] Found Pokemon: {chosen_switch.species}")
                            if chosen_switch in battle.available_switches:
                                action_taken = True
                                chat_msg = f"AI Decision: Switching to '{chosen_switch.species}'."
                                logger.info(f"[Battle {battle_tag}] {chat_msg}")
                                return self.create_order(chosen_switch)
                            else:
                                fallback_reason = f"LLM chose unavailable switch '{pokemon_name}' (found as {chosen_switch.species} but not in available switches)"
                        else:
                            fallback_reason = f"LLM chose invalid switch '{pokemon_name}' that could not be found"
                    else:
                        fallback_reason = "LLM 'choose_switch' called without 'pokemon_name'."
                else:
                    fallback_reason = f"LLM called unknown function '{function_name}'."
            
            # Handle fallback cases    
            if not action_taken:
                if not fallback_reason:
                    if error_message:
                        fallback_reason = f"API Error: {error_message}"
                    elif decision is None:
                        fallback_reason = "LLM did not provide a valid function call."
                    else:
                        fallback_reason = "Unknown error processing LLM decision."
                        
                logger.warning(f"[Battle {battle_tag}] Warning: {fallback_reason} Choosing random action.")
                
                if battle.available_moves or battle.available_switches:
                    random_action = self.choose_random_move(battle)
                    logger.info(f"[Battle {battle_tag}] Fallback: Using random action: {random_action}")
                    return random_action
                else:
                    logger.info(f"[Battle {battle_tag}] Fallback: No moves or switches available. Using Struggle/Default.")
                    return self.choose_default_move(battle)
                    
        except Exception as e:
            # Comprehensive error handling with complete stack trace
            logger.error(f"[Battle {battle_tag}] Unexpected error in choose_move: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            
            # Even more robust fallback logic in case of exceptions
            try:
                if battle.available_moves:
                    # Choose highest base power move as fallback during exception
                    best_move = max(battle.available_moves, key=lambda m: m.base_power)
                    logger.info(f"[Battle {battle_tag}] Exception fallback: Using highest power move: {best_move.id}")
                    return self.create_order(best_move)
                elif battle.available_switches:
                    # Choose Pokemon with highest HP as fallback
                    best_switch = max(battle.available_switches, key=lambda p: p.current_hp_fraction)
                    logger.info(f"[Battle {battle_tag}] Exception fallback: Switching to: {best_switch.species}")
                    return self.create_order(best_switch)
                else:
                    logger.info(f"[Battle {battle_tag}] Exception fallback: Using default move/struggle")
                    return self.choose_default_move(battle)
            except Exception as fallback_error:
                # Last resort fallback if even the fallback logic fails
                logger.error(f"[Battle {battle_tag}] Critical error in fallback logic: {fallback_error}")
                logger.error(f"Traceback: {traceback.format_exc()}")
                return self.choose_default_move(battle)
                
    async def _get_llm_decision(self, battle_state: str) -> Dict[str, Any]:
        """
        Get a decision from the LLM based on the current battle state.
        
        This is an abstract method that needs to be implemented by subclasses.
        
        Args:
            battle_state: The formatted battle state.
            
        Returns:
            A dictionary containing the decision and possibly error information.
        """
        raise NotImplementedError("Subclasses must implement _get_llm_decision")


class OpenAIAgent(LLMAgentBase):
    """Battle agent using OpenAI's API for decisions."""
    
    def __init__(self, api_key: str = None, model: str = "gpt-4o", *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.model = model
        self.client = openai.OpenAI(api_key=api_key)
        self.openai_tools = [
            {
                "type": "function",
                "function": {
                    "name": "choose_move",
                    "description": STANDARD_TOOL_SCHEMA["choose_move"]["description"],
                    "parameters": STANDARD_TOOL_SCHEMA["choose_move"]["parameters"]
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "choose_switch",
                    "description": STANDARD_TOOL_SCHEMA["choose_switch"]["description"],
                    "parameters": STANDARD_TOOL_SCHEMA["choose_switch"]["parameters"]
                }
            }
        ]
        
    async def _get_llm_decision(self, battle_state: str) -> Dict[str, Any]:
        """Get a decision from the OpenAI model."""
        openai_logger = logging.getLogger("openai_agent")
        
        system_prompt = (
            "You are a competitive Pokémon battle expert. Your task is to make optimal decisions "
            "in a Pokémon battle based on the current state. Analyze the types, moves, and status "
            "of both your active Pokémon and the opponent's. Consider type advantages, remaining HP, "
            "status conditions, and available moves/switches."
            "\n\n"
            "You MUST respond using the provided tools. Do not provide explanations or additional text."
        )
        
        user_prompt = f"Current battle state:\n{battle_state}\n\nPlease make a decision for this turn."
        
        # Log detailed information about the request
        openai_logger.info(f"Requesting decision from OpenAI model: {self.model}")
        openai_logger.debug(f"System prompt: {system_prompt}")
        openai_logger.debug(f"User prompt length: {len(user_prompt)} characters")
        
        try:
            openai_logger.debug("Sending request to OpenAI API")
            start_time = asyncio.get_event_loop().time()
            
            response = await asyncio.to_thread(
                self.client.chat.completions.create,
                model=self.model,
                tools=self.openai_tools,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ]
            )
            
            # Calculate and log response time
            end_time = asyncio.get_event_loop().time()
            response_time = (end_time - start_time) * 1000  # convert to ms
            openai_logger.info(f"Response received from OpenAI API in {response_time:.2f}ms")
            
            # Log detailed response information
            if hasattr(response, 'usage'):
                usage = response.usage
                openai_logger.debug(f"Token usage - Prompt: {usage.prompt_tokens}, Completion: {usage.completion_tokens}, Total: {usage.total_tokens}")
            
            message = response.choices[0].message
            openai_logger.debug(f"Response message: {message}")
            
            # Check if there's a tool call
            if message.tool_calls and len(message.tool_calls) > 0:
                tool_call = message.tool_calls[0]
                function_name = tool_call.function.name
                arguments = json.loads(tool_call.function.arguments)
                
                openai_logger.info(f"OpenAI returned tool call: {function_name} with arguments: {arguments}")
                return {"decision": {"name": function_name, "arguments": arguments}}
            else:
                # Fallback to extract function call from content
                content = message.content or ""
                openai_logger.debug(f"No tool call found, message content: {content}")
                
                extracted = extract_function_call(content)
                if extracted:
                    openai_logger.info(f"Extracted function call from content: {extracted}")
                    return {"decision": extracted}
                
                openai_logger.warning("No valid function call found in OpenAI response")
                return {"error": "No valid function call found in response"}
                
        except Exception as e:
            openai_logger.error(f"Unexpected error during OpenAI call: {e}", exc_info=True)
            openai_logger.error(f"Full traceback: {traceback.format_exc()}")
            return {"error": f"Unexpected error: {e}"}


class AnthropicAgent(LLMAgentBase):
    """Battle agent using Anthropic's API for decisions."""
    
    def __init__(self, api_key: str = None, model: str = "claude-3-opus-20240229", *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.model = model
        self.client = anthropic.Anthropic(api_key=api_key)
        self.tools = [
            {
                "name": "choose_move",
                "description": STANDARD_TOOL_SCHEMA["choose_move"]["description"],
                "input_schema": STANDARD_TOOL_SCHEMA["choose_move"]["parameters"]
            },
            {
                "name": "choose_switch",
                "description": STANDARD_TOOL_SCHEMA["choose_switch"]["description"],
                "input_schema": STANDARD_TOOL_SCHEMA["choose_switch"]["parameters"]
            }
        ]
        
    async def _get_llm_decision(self, battle_state: str) -> Dict[str, Any]:
        """Get a decision from the Anthropic Claude model."""
        claude_logger = logging.getLogger("claude_agent")
        
        system_prompt = (
            "You are a competitive Pokémon battle expert. Your task is to make optimal decisions "
            "in a Pokémon battle based on the current state. Analyze the types, moves, and status "
            "of both your active Pokémon and the opponent's. Consider type advantages, remaining HP, "
            "status conditions, and available moves/switches."
            "\n\n"
            "You MUST respond using the provided tools. Do not provide explanations or additional text."
        )
        
        user_prompt = f"Current battle state:\n{battle_state}\n\nPlease make a decision for this turn."
        
        # Log detailed information about the request
        claude_logger.info(f"Requesting decision from Claude model: {self.model}")
        claude_logger.debug(f"System prompt: {system_prompt}")
        claude_logger.debug(f"User prompt length: {len(user_prompt)} characters")
        claude_logger.debug(f"Tools provided to Claude: {json.dumps([t['name'] for t in self.tools])}")
        
        try:
            claude_logger.debug("Sending request to Anthropic API")
            start_time = asyncio.get_event_loop().time()
            
            response = await asyncio.to_thread(
                self.client.messages.create,
                model=self.model,
                max_tokens=1024,
                tools=self.tools,
                system=system_prompt,
                messages=[
                    {"role": "user", "content": user_prompt}
                ]
            )
            
            # Calculate and log response time
            end_time = asyncio.get_event_loop().time()
            response_time = (end_time - start_time) * 1000  # convert to ms
            claude_logger.info(f"Response received from Anthropic API in {response_time:.2f}ms")
            
            # Log detailed response information
            if hasattr(response, 'usage'):
                usage = response.usage
                claude_logger.debug(f"Token usage - Input: {usage.input_tokens}, Output: {usage.output_tokens}")
            
            claude_logger.debug(f"Response: {response}")
            content_types = [block.type for block in response.content] if response.content else []
            claude_logger.debug(f"Content block types: {content_types}")
            
            # Check for tool use
            if response.content and len(response.content) > 0:
                for content_block in response.content:
                    if content_block.type == 'tool_use':
                        claude_logger.info(f"Claude returned tool use: {content_block.name} with arguments: {content_block.input}")
                        return {
                            "decision": {
                                "name": content_block.name,
                                "arguments": content_block.input
                            }
                        }
            
            # Fallback to extract function call from text
            for content_block in response.content:
                if content_block.type == 'text':
                    claude_logger.debug(f"Text content block: {content_block.text}")
                    extracted = extract_function_call(content_block.text)
                    if extracted:
                        claude_logger.info(f"Extracted function call from text: {extracted}")
                        return {"decision": extracted}
            
            claude_logger.warning("No valid function call found in Claude response")
            
            # Log actual content for debugging
            if response.content:
                for i, block in enumerate(response.content):
                    claude_logger.debug(f"Content block {i} type={block.type}: {block}")
            
            return {"error": "No valid function call found in response"}
                
        except Exception as e:
            claude_logger.error(f"Unexpected error during Anthropic call: {e}", exc_info=True)
            claude_logger.error(f"Full traceback: {traceback.format_exc()}")
            return {"error": f"Unexpected error: {str(e)}"}


class GeminiAgent(LLMAgentBase):
    """Battle agent using Google's Gemini API for decisions."""
    
    def __init__(self, api_key: str = None, model: str = "gemini-pro", *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.model = model
        genai.configure(api_key=api_key)
        self.generation_config = {
            "temperature": 0.1,
            "top_p": 0.95,
            "top_k": 40,
            "max_output_tokens": 1024,
        }
        
    async def _get_llm_decision(self, battle_state: str) -> Dict[str, Any]:
        """Get a decision from the Gemini model."""
        gemini_logger = logging.getLogger("gemini_agent")
        
        system_prompt = (
            "You are a competitive Pokémon battle expert. Your task is to make optimal decisions "
            "in a Pokémon battle based on the current state. Analyze the types, moves, and status "
            "of both your active Pokémon and the opponent's. Consider type advantages, remaining HP, "
            "status conditions, and available moves/switches."
            "\n\n"
            "You MUST respond in the following JSON format for choosing a move:\n"
            "```json\n{\"name\": \"choose_move\", \"arguments\": {\"move_name\": \"MOVE_NAME\"}}\n```\n"
            "\n"
            "Or in the following format for switching Pokémon:\n"
            "```json\n{\"name\": \"choose_switch\", \"arguments\": {\"pokemon_name\": \"POKEMON_NAME\"}}\n```\n"
            "\n"
            "Do not provide explanations or additional text, only the JSON response."
        )
        
        user_prompt = f"Current battle state:\n{battle_state}\n\nPlease make a decision for this turn."
        
        # Log detailed information about the request
        gemini_logger.info(f"Requesting decision from Gemini model: {self.model}")
        gemini_logger.debug(f"System prompt: {system_prompt}")
        gemini_logger.debug(f"User prompt length: {len(user_prompt)} characters")
        gemini_logger.debug(f"Generation config: {self.generation_config}")
        
        try:
            gemini_logger.debug("Initializing Gemini model")
            model = genai.GenerativeModel(
                model_name=self.model,
                generation_config=self.generation_config
            )
            
            gemini_logger.debug("Sending request to Gemini API")
            start_time = asyncio.get_event_loop().time()
            
            response = await asyncio.to_thread(
                model.generate_content,
                [system_prompt, user_prompt]
            )
            
            # Calculate and log response time
            end_time = asyncio.get_event_loop().time()
            response_time = (end_time - start_time) * 1000  # convert to ms
            gemini_logger.info(f"Response received from Gemini API in {response_time:.2f}ms")
            
            # Log response information
            gemini_logger.debug(f"Raw response object: {response}")
            
            # Get text content
            content = response.text
            gemini_logger.debug(f"Response text content: {content}")
            
            # Extract function call from content
            extracted = extract_function_call(content)
            if extracted:
                gemini_logger.info(f"Successfully extracted function call: {extracted}")
                return {"decision": extracted}
            
            # If we couldn't extract a function call, try to find JSON in the response
            import re
            json_pattern = r'```(?:json)?\s*({.*?})\s*```'
            json_match = re.search(json_pattern, content, re.DOTALL)
            
            if json_match:
                json_str = json_match.group(1)
                gemini_logger.debug(f"Found JSON string in response: {json_str}")
                
                try:
                    json_data = json.loads(json_str)
                    if "name" in json_data and "arguments" in json_data:
                        gemini_logger.info(f"Parsed JSON decision: {json_data}")
                        return {"decision": json_data}
                except json.JSONDecodeError as json_err:
                    gemini_logger.warning(f"Failed to parse JSON: {json_err}")
            
            # Log entire response content for debugging
            gemini_logger.warning("No valid function call found in Gemini response")
            gemini_logger.debug(f"Full response content: {content}")
            
            return {"error": "No valid function call found in response"}
                
        except Exception as e:
            gemini_logger.error(f"Unexpected error during Gemini call: {e}", exc_info=True)
            gemini_logger.error(f"Full traceback: {traceback.format_exc()}")
            return {"error": f"Unexpected error: {str(e)}"}