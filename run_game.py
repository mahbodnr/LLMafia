"""
Main entry point for running the Mafia game.
"""

import argparse
import os
import sys
import logging
from dotenv import load_dotenv

# Add the project root to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.game import MafiaGame
from src.config import DEFAULT_GAME_SETTINGS

# Load environment variables from .env file if it exists
load_dotenv()

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    filename="mafia_game.log",
)

logger = logging.getLogger(__name__)


def main():
    """Main entry point for the Mafia game."""
    parser = argparse.ArgumentParser(description="Run a Mafia game with LLM agents")
    parser.add_argument("--players", type=int, default=7, help="Number of players")
    parser.add_argument("--mafia", type=int, default=2, help="Number of mafia players")
    parser.add_argument(
        "--godfather", type=bool, default=True, help="Include godfather role"
    )
    parser.add_argument("--doctor", type=bool, default=True, help="Include doctor role")
    parser.add_argument(
        "--detective", type=bool, default=True, help="Include detective role"
    )
    parser.add_argument(
        "--rounds", type=int, default=3, help="Number of discussion rounds per day"
    )
    parser.add_argument("--verbose", type=bool, default=True, help="Verbose output")
    parser.add_argument(
        "--save-transcript", type=bool, default=True, help="Save game transcript"
    )

    args = parser.parse_args()

    # Check if API keys are set
    required_keys = []
    if not os.getenv("OPENAI_API_KEY"):
        required_keys.append("OPENAI_API_KEY")
    if not os.getenv("ANTHROPIC_API_KEY"):
        required_keys.append("ANTHROPIC_API_KEY")
    if not os.getenv("GOOGLE_API_KEY"):
        required_keys.append("GOOGLE_API_KEY")

    if required_keys:
        print(
            f"Warning: The following API keys are not set: {', '.join(required_keys)}"
        )
        print("Some LLM providers may not work without their API keys.")
        print("You can set them as environment variables or in a .env file.")
        response = input("Do you want to continue anyway? (y/n): ")
        if response.lower() != "y":
            print("Exiting...")
            return

    # Create custom config based on arguments
    config = DEFAULT_GAME_SETTINGS.copy()

    # Update role distribution
    roles = {
        "Villager": args.players
        - args.mafia
        - (1 if args.godfather else 0)
        - (1 if args.doctor else 0)
        - (1 if args.detective else 0),
        "Mafia": args.mafia,
    }

    if args.godfather:
        roles["Godfather"] = 1
    if args.doctor:
        roles["Doctor"] = 1
    if args.detective:
        roles["Detective"] = 1

    config["num_players"] = args.players
    config["roles"] = roles
    config["phases"]["day"]["discussion_rounds"] = args.rounds
    config["agent"]["verbosity"] = "elaborate" if args.verbose else "brief"

    config["ai"] = {
        "debug": {"model": "debug"},
    }

    # Print game configuration
    print("\n=== Mafia Game Configuration ===")
    print(f"Players: {args.players}")
    print(f"Roles: {roles}")
    print(f"Discussion Rounds: {args.rounds}")
    print(f"Verbose Mode: {args.verbose}")
    print(f"Save Transcript: {args.save_transcript}")
    print("===============================\n")

    # Create and run game
    try:
        print("Initializing game...")
        game = MafiaGame(config)
        game.initialize_game()

        print("Running game...")
        game_over, winning_team = game.run_game()

        # Print result
        team_name = "Village" if winning_team.name == "VILLAGE" else "Mafia"
        print(f"\nGame over! The {team_name} team has won!")

    except KeyboardInterrupt:
        print("\nGame interrupted by user.")
    except Exception as e:
        logger.error(f"Error running game: {e}", exc_info=True)
        print(f"Error running game: {e}")
        print("Check mafia_game.log for details.")


if __name__ == "__main__":
    main()
