"""
Example usage of the Mafia game with LLM agents.

This script demonstrates how to use the Mafia game library programmatically.
"""

import os
import sys
import logging
from dotenv import load_dotenv

# Add the project root to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.game import MafiaGame
from src.models import TeamAlignment

# Load environment variables from .env file if it exists
load_dotenv()

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    filename="example_usage.log"
)

logger = logging.getLogger(__name__)


def run_simple_game():
    """Run a simple game with default settings."""
    print("Running a simple game with default settings...")
    
    # Create game instance with default settings
    game = MafiaGame()
    
    # Initialize game with default player names
    game.initialize_game()
    
    # Run game
    game_over, winning_team = game.game_controller.run_game()
    
    # Print result
    team_name = "Village" if winning_team == TeamAlignment.VILLAGE else "Mafia"
    print(f"Game over! The {team_name} team has won!")


def run_custom_game():
    """Run a custom game with specific settings."""
    print("Running a custom game with specific settings...")
    
    # Create custom config
    config = {
        "num_players": 5,
        "roles": {
            "Villager": 2,
            "Mafia": 1,
            "Doctor": 1,
            "Detective": 1,
        },
        "phases": {
            "day": {
                "discussion_rounds": 2,
                "voting_time": 1,
            },
            "night": {
                "mafia_discussion_rounds": 1,
                "action_time": 1,
            }
        },
        "agent": {
            "verbosity": "brief",
            "max_message_length": 100,
            "memory_limit": 5,
        },
        "mechanics": {
            "godfather_appears_innocent": True,
            "reveal_role_on_death": True,
        }
    }
    
    # Create game instance with custom config
    game = MafiaGame(config)
    
    # Initialize game with custom player names
    player_names = ["Alice", "Bob", "Charlie", "Dave", "Eve"]
    game.initialize_game(player_names)
    
    # Run game
    game_over, winning_team = game.game_controller.run_game()
    
    # Print result
    team_name = "Village" if winning_team == TeamAlignment.VILLAGE else "Mafia"
    print(f"Game over! The {team_name} team has won!")


def run_step_by_step_game():
    """Run a game step by step, controlling each phase manually."""
    print("Running a game step by step...")
    
    # Create game instance
    game = MafiaGame()
    
    # Initialize game
    game.initialize_game()
    
    # Run game phases manually
    max_rounds = 3
    current_round = 0
    
    while not game.game_state.game_over and current_round < max_rounds:
        print(f"\nRound {game.game_state.current_round}")
        
        # Day discussion phase
        print("Day Discussion Phase")
        game.game_controller.run_phase()
        
        # Day voting phase
        print("Day Voting Phase")
        game.game_controller.run_phase()
        
        # Night mafia discussion phase
        print("Night Mafia Discussion Phase")
        game.game_controller.run_phase()
        
        # Night action phase
        print("Night Action Phase")
        game.game_controller.run_phase()
        
        current_round += 1
    
    # Print result
    if game.game_state.game_over:
        team_name = "Village" if game.game_state.winning_team == TeamAlignment.VILLAGE else "Mafia"
        print(f"Game over! The {team_name} team has won!")
    else:
        print("Game reached maximum rounds without a winner.")


def analyze_game_transcript(transcript_file):
    """Analyze a game transcript."""
    print(f"Analyzing game transcript: {transcript_file}")
    
    import json
    
    # Load transcript
    with open(transcript_file, 'r') as f:
        transcript = json.load(f)
    
    # Print basic statistics
    print("\nGame Statistics:")
    print(f"Players: {len(transcript['players'])}")
    print(f"Events: {len(transcript['events'])}")
    print(f"Messages: {len(transcript['messages'])}")
    print(f"Votes: {len(transcript['votes'])}")
    print(f"Actions: {len(transcript['actions'])}")
    print(f"Result: {transcript['result']['winning_team']} team won")
    
    # Analyze player roles
    roles = {}
    for player_id, player in transcript['players'].items():
        role = player['role']
        roles[role] = roles.get(role, 0) + 1
    
    print("\nRole Distribution:")
    for role, count in roles.items():
        print(f"{role}: {count}")
    
    # Analyze eliminations
    eliminations = [e for e in transcript['events'] 
                   if e['type'] in ['elimination', 'night_elimination']]
    
    print("\nEliminations:")
    for e in eliminations:
        print(f"Round {e['round']}, {e['phase']}: {e['description']}")


if __name__ == "__main__":
    print("Mafia Game with LLM Agents - Example Usage\n")
    
    # Check if API keys are set
    required_keys = []
    if not os.getenv('OPENAI_API_KEY'):
        required_keys.append('OPENAI_API_KEY')
    if not os.getenv('ANTHROPIC_API_KEY'):
        required_keys.append('ANTHROPIC_API_KEY')
    if not os.getenv('GOOGLE_API_KEY'):
        required_keys.append('GOOGLE_API_KEY')
    
    if required_keys:
        print(f"Warning: The following API keys are not set: {', '.join(required_keys)}")
        print("Some LLM providers may not work without their API keys.")
        print("You can set them as environment variables or in a .env file.")
        response = input("Do you want to continue anyway? (y/n): ")
        if response.lower() != 'y':
            print("Exiting...")
            sys.exit(0)
    
    # Menu
    while True:
        print("\nSelect an example to run:")
        print("1. Run a simple game with default settings")
        print("2. Run a custom game with specific settings")
        print("3. Run a game step by step")
        print("4. Analyze a game transcript")
        print("0. Exit")
        
        choice = input("\nEnter your choice (0-4): ")
        
        if choice == '0':
            print("Exiting...")
            break
        elif choice == '1':
            run_simple_game()
        elif choice == '2':
            run_custom_game()
        elif choice == '3':
            run_step_by_step_game()
        elif choice == '4':
            transcript_file = input("Enter the path to the transcript file: ")
            if os.path.exists(transcript_file):
                analyze_game_transcript(transcript_file)
            else:
                print(f"File not found: {transcript_file}")
        else:
            print("Invalid choice. Please try again.")
