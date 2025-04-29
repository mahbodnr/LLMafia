import math
from tqdm import tqdm
from src.game import MafiaGame
from src.models import TeamAlignment
import os
import argparse

# disable logging
import logging

logging.disable(logging.CRITICAL)

# model_name = "llama3.3:70b"

parser = argparse.ArgumentParser()
parser.add_argument(
    "--num-players",
    type=int,
    nargs="+",
    help="Number of players in the game",
)
parser.add_argument(
    "--model-name",
    type=str,
    help="Mafia model to use",
)
parser.add_argument(
    "--mafia-count",
    type=int,
    nargs="+",
    default=None,
    help="Number of mafia players in the game",
)
parser.add_argument(
    "--n-repeats",
    type=int,
    default=100,
    help="Number of times to repeat the game",
)
parser.add_argument(
    "--use-doctor",
    action="store_true",
    help="Include doctor role",
)
parser.add_argument(
    "--use-detective",
    action="store_true",
    help="Include detective role",
)
args = parser.parse_args()

for i, num_players in enumerate(args.num_players):
    if args.mafia_count is None:
        # If mafia_count is not provided, set it to half of num_players
        args.mafia_count = range(1,math.ceil(num_players / 2))
    for mafia_count in args.mafia_count:
        mafia_wins = 0
        print(
            f"Running simulations for {num_players} players and {mafia_count} mafia..."
        )
        for n in tqdm(range(args.n_repeats)):
            # Create custom config
            config = {
                "num_players": num_players,
                "roles": {
                    "Villager": num_players
                    - mafia_count
                    - int(args.use_doctor)
                    - int(args.use_detective),
                    "Mafia": mafia_count,
                    "Doctor": int(args.use_doctor),
                    "Detective": int(args.use_detective),
                },
                "phases": {
                    "day": {
                        "discussion_rounds": 1,
                        "voting_time": 1,
                    },
                    "night": {
                        "mafia_discussion_rounds": 1,
                        "action_time": 1,
                    },
                },
                "ai_models": [
                    {
                        "provider": "ollama",
                        "model": args.model_name,
                        "base_url": os.environ.get(
                            "OLLAMA_URL", "http://localhost:11434"
                        ),
                    },
                ],
            }

            # Create game instance with custom config
            game = MafiaGame(config)

            # Initialize game with custom player names
            game.initialize_game()

            # Run game
            game_over, winning_team = game.game_controller.run_game()

            filename = f"p{num_players}_m{mafia_count}_i{n}"
            if args.use_doctor:
                filename += "_doctor"
            if args.use_detective:
                filename += "_detective"
            filename += f"_{game.game_controller.game_id}"
            if not os.path.exists(f"analyze/transcripts/{args.model_name}/"):
                os.makedirs(f"analyze/transcripts/{args.model_name}/")
            game.save_transcript(
                f"analyze/transcripts/{args.model_name}/{filename}.json"
            )

            mafia_wins += int(winning_team == TeamAlignment.MAFIA)
