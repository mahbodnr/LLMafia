"""
Main game module for the Mafia game.
"""

import logging
import argparse
from typing import List, Dict, Any

from src.controllers import GameController, RecordedGameController
from src.utils import generate_player_names
from src.config import DEFAULT_GAME_SETTINGS, LLM_PROVIDERS, UI_SETTINGS, LOGGING

# Set up logging
logging.basicConfig(
    level=getattr(logging, LOGGING.get("level", "INFO")),
    format=LOGGING.get(
        "format", "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    ),
    filename=LOGGING.get("file", "mafia_game.log"),
)

logger = logging.getLogger(__name__)


class MafiaGame:
    """Main class for the Mafia game."""

    def __init__(self, config: Dict[str, Any] = None, transcript: List[str] = None):
        """
        Initialize the Mafia game.

        Args:
            config: Configuration settings for the game (optional)
        """
        if transcript is not None:
            self.config = transcript.get("config", DEFAULT_GAME_SETTINGS)
            self.game_controller = RecordedGameController(transcript)
            self.transcript = transcript
        else:
            self.config = config or DEFAULT_GAME_SETTINGS
            self.game_controller = GameController(self.config)
            self.transcript = []
        self.game_state = None

    def initialize_game(self, player_names: List[str] = None):
        """
        Initialize a new game with the given player names.

        Args:
            player_names: List of player names (optional)
        """
        # If no player names provided, generate random names
        if not player_names:
            if self.transcript:
                player_names = [p["name"] for p in self.transcript["players"].values()]
            else:
                num_players = self.config.get("num_players", 7)
                player_names = generate_player_names(num_players)

        # Initialize game
        self.game_state = self.game_controller.initialize_game(player_names)
        logger.info(f"Game initialized with {len(player_names)} players")

        # Log initial game state
        self._log_game_state()

    def run_game(self):
        """Run the game until completion."""
        if not self.game_state:
            raise ValueError("Game not initialized. Call initialize_game() first.")

        logger.info("Starting game")

        # Run game
        game_over, winning_team = self.game_controller.run_game()

        # Log final game state
        self._log_game_state()

        # Save transcript if enabled
        if LOGGING.get("save_transcripts", True):
            self.save_transcript()

        return game_over, winning_team

    def _log_game_state(self):
        """Log the current game state."""
        state = self.game_state

        logger.info(f"Round: {state.current_round}, Phase: {state.current_phase.name}")
        logger.info(f"Alive players: {len(state.alive_players)}")
        logger.info(f"Dead players: {len(state.dead_players)}")
        logger.info(f"Mafia count: {state.alive_mafia_count}")
        logger.info(f"Village count: {state.alive_village_count}")
        logger.info(f"Game over: {state.game_over}")

        if state.game_over and state.winning_team:
            logger.info(f"Winning team: {state.winning_team.name}")

    def save_transcript(self, filename: str = None):
        """Save the game transcript."""
        import os
        import json
        from datetime import datetime

        if filename is None:
            # Create transcript directory if it doesn't exist
            transcript_dir = LOGGING.get("transcript_dir", "transcripts")
            os.makedirs(transcript_dir, exist_ok=True)

            # Generate transcript filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{transcript_dir}/mafia_game_{timestamp}.json"

        # Prepare transcript data
        transcript = {
            "config": self.config,
            "players": {
                pid: {"name": p.name, "role": p.role.name, "team": p.team.name}
                for pid, p in self.game_state.players.items()
            },
            "events": [
                {
                    "round": e.round_num,
                    "phase": e.phase.name,
                    "type": e.event_type,
                    "description": e.description,
                    "public": e.public,
                }
                for e in self.game_state.events
            ],
            "messages": [
                {
                    "round": m.round_num,
                    "phase": m.phase.name,
                    "sender": m.sender_id,
                    "content": m.content,
                    "public": m.public,
                }
                for m in self.game_state.messages
            ],
            "votes": [
                {
                    "round": v.round_num,
                    "phase": v.phase.name,
                    "voter": v.voter_id,
                    "target": v.target_id,
                }
                for v in self.game_state.votes
            ],
            "actions": [
                {
                    "round": a.round_num,
                    "phase": a.phase.name,
                    "actor": a.actor_id,
                    "action": a.action_type,
                    "target": a.target_id,
                    "success": a.success,
                }
                for a in self.game_state.actions
            ],

            "inner_thoughts": [
                {
                    "player": player_id,
                    "round": memory["round"],
                    "phase": memory["phase"],
                    "description": memory["description"],
                }
                for player_id, agent in self.game_controller.agents.items()
                for memory in agent.player.memory
                if memory["type"] == "inner_thought"
            ],
            "result": {
                "game_over": self.game_state.game_over,
                "winning_team": (
                    self.game_state.winning_team.name
                    if self.game_state.winning_team
                    else None
                ),
            },
        }

        # Write transcript to file
        with open(filename, "w") as f:
            json.dump(transcript, f, indent=2)

        logger.info(f"Transcript saved to {filename}")
        return filename


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

    args = parser.parse_args()

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

    # Create and run game
    game = MafiaGame(config)
    game.initialize_game()
    game_over, winning_team = game.run_game()

    print(f"Game over! The {winning_team.name} team has won!")


if __name__ == "__main__":
    main()
