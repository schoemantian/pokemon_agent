"""
Simple script to test the deployment of the GAIA Pokémon Battle Agent locally
without needing to connect to a Pokémon Showdown server.
"""

import os
import asyncio
import random
import string
from dotenv import load_dotenv

from gaia_agent import GAIAAgent
from agents import LLMAgentBase, AnthropicAgent, OpenAIAgent, GeminiAgent
from utils import format_battle_state

# Load environment variables
load_dotenv()

def generate_random_username(prefix="Agent", length=5):
    """Generate a random username to avoid name collision."""
    timestamp = int(random.random() * 10000)
    random_suffix = ''.join(random.choices(string.ascii_letters + string.digits, k=length))
    return f"{prefix}_{random_suffix}_{timestamp}"

class MockBattle:
    """A mock battle object for testing."""
    
    def __init__(self):
        """Initialize with mock data."""
        self.active_pokemon = None
        self.opponent_active_pokemon = None
        self.available_moves = []
        self.available_switches = []
        self.weather = "none"
        self.fields = []
        self.side_conditions = {}
        self.opponent_side_conditions = {}
        self.turn = 1
        self.team = {}
        self.opponent_team = {}
        
    def generate_random_state(self):
        """Generate a random battle state for testing."""
        # Simplified mock battle state
        from dataclasses import dataclass
        
        @dataclass
        class MockPokemon:
            species: str
            types: list
            current_hp_fraction: float
            status: object = None
            boosts: dict = None
            last_used_move: object = None
            
        @dataclass
        class MockStatus:
            name: str
            
        @dataclass
        class MockMove:
            id: str
            type: str
            base_power: int
            accuracy: float
            current_pp: int
            max_pp: int
            category: object
            
        @dataclass
        class MockCategory:
            name: str
        
        # Create mock active Pokémon
        self.active_pokemon = MockPokemon(
            species=random.choice(["Pikachu", "Charizard", "Bulbasaur", "Jigglypuff"]),
            types=[random.choice(["Electric", "Fire", "Grass", "Normal", "Water", "Flying"])],
            current_hp_fraction=random.random(),
            boosts={},
            status=MockStatus(name=random.choice(["", "PSN", "PAR", "SLP"]))
        )
        
        # Create mock opponent Pokémon
        self.opponent_active_pokemon = MockPokemon(
            species=random.choice(["Mewtwo", "Snorlax", "Gyarados", "Gengar"]),
            types=[random.choice(["Psychic", "Normal", "Water", "Ghost", "Dark", "Dragon"])],
            current_hp_fraction=random.random(),
            boosts={},
            status=MockStatus(name=random.choice(["", "BRN", "FRZ", "TOX"]))
        )
        
        # Create mock available moves
        self.available_moves = [
            MockMove(
                id=f"move{i}",
                type=random.choice(["Normal", "Fire", "Water", "Electric", "Grass"]),
                base_power=random.randint(40, 120),
                accuracy=random.choice([50, 70, 80, 90, 100]),
                current_pp=random.randint(5, 20),
                max_pp=20,
                category=MockCategory(name=random.choice(["PHYSICAL", "SPECIAL", "STATUS"]))
            )
            for i in range(random.randint(1, 4))
        ]
        
        # Create mock available switches
        self.available_switches = [
            MockPokemon(
                species=random.choice(["Eevee", "Squirtle", "Charmander", "Pidgey"]),
                types=[random.choice(["Normal", "Water", "Fire", "Flying"])],
                current_hp_fraction=random.random(),
                status=MockStatus(name=random.choice(["", "PSN", "PAR", "SLP"]))
            )
            for i in range(random.randint(0, 3))
        ]
        
        # Update battle conditions
        self.weather = random.choice(["none", "raindance", "sunnyday", "sandstorm", "hail"])
        self.fields = random.sample(["electricterrain", "psychicterrain", "mistyterrain", "grassyterrain"], 
                                   k=random.randint(0, 2))
        self.side_conditions = {}
        self.opponent_side_conditions = {}
        
        return self

async def test_gaia_agent():
    """Test the GAIA agent with a mock battle."""
    print("Testing GAIA agent with mock battle...")
    
    # Create mock battle
    battle = MockBattle().generate_random_state()
    
    # Format the battle state
    battle_state = format_battle_state(battle)
    print("\nMock Battle State:")
    print(battle_state)
    
    # Select an LLM provider
    llm_provider = os.getenv("LLM_PROVIDER", "anthropic")
    print(f"\nUsing LLM provider: {llm_provider}")
    
    # Create a minimal agent for testing
    if llm_provider == "openai":
        api_key = os.getenv("OPENAI_API_KEY")
        llm_client = OpenAIAgent(
            api_key=api_key,
            model="gpt-4o",
            battle_format="gen9randombattle"
        )
    elif llm_provider == "gemini":
        api_key = os.getenv("GEMINI_API_KEY")
        llm_client = GeminiAgent(
            api_key=api_key,
            model="gemini-pro",
            battle_format="gen9randombattle"
        )
    else:  # Default to Anthropic
        api_key = os.getenv("ANTHROPIC_API_KEY")
        llm_client = AnthropicAgent(
            api_key=api_key,
            model="claude-3-opus-20240229",
            battle_format="gen9randombattle"
        )
    
    # Test the LLM decision
    try:
        print("\nRequesting move decision from LLM...")
        decision_result = await llm_client._get_llm_decision(battle_state)
        
        print("\nLLM Response:")
        print(decision_result)
        
        if "decision" in decision_result:
            print("\nDecision details:")
            print(f"Function: {decision_result['decision'].get('name')}")
            print(f"Arguments: {decision_result['decision'].get('arguments')}")
            
            print("\nTest successful! The LLM is properly configured and can make battle decisions.")
        else:
            print("\nNo decision returned. Check if there's an error in the API response.")
            if "error" in decision_result:
                print(f"Error: {decision_result['error']}")
    except Exception as e:
        print(f"\nError testing LLM decision: {str(e)}")
    
if __name__ == "__main__":
    asyncio.run(test_gaia_agent())