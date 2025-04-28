from tqdm import tqdm
from src.game import MafiaGame
from src.models import TeamAlignment
import os
from argparse import ArgumentParser

# disable logging
import logging

logging.disable(logging.CRITICAL)

use_doctor = True
use_detective = True
use_godfather = False

parser = ArgumentParser()
parser.add_argument(
    "--num_players",
    type=int,
    default=10,
    help="Number of players in the game",
)
parser.add_argument(
    "--mafia_count",
    type=int,
    default=3,
    help="Number of mafia players in the game",
)
parser.add_argument(
    "--mafia_model",
    type=str,
    default="llama3.3:70b",
    help="Mafia model to use",
)
parser.add_argument(
    "--village_model",
    type=str,
    default="llama3.3:70b",
    help="Village model to use",
)
parser.add_argument(
    "--n_repeats",
    type=int,
    default=100,
    help="Number of times to repeat the game",
)
args = parser.parse_args()

num_players = args.num_players
mafia_count = args.mafia_count
mafia_model = args.mafia_model
village_model = args.village_model
n_repeats = args.n_repeats

village_wins = 0
for n in tqdm(range(n_repeats)):
    # Create custom config
    config = {
        "num_players": num_players,
        "roles": {
            "Villager": num_players
            - mafia_count
            - int(use_doctor)
            - int(use_detective),
            "Mafia": mafia_count - int(use_godfather),
            "Doctor": int(use_doctor),
            "Detective": int(use_detective),
            "Godfather": int(use_godfather),
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
            { "provider": "ollama", 
                "model": mafia_model,
                "team": "Mafia",
                "base_url": os.environ.get(
                    "OLLAMA_URL", "http://localhost:11434"
                ),
            },
            { "provider": "ollama", 
                "model": village_model,
                "team": "Village",
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

    dir_name = f"analyze/transcripts/v:{village_model}_vs_m:{mafia_model}"

    filename = f"p{num_players}_m{mafia_count}_i{n}"
    if use_doctor:
        filename += "_doctor"
    if use_detective:
        filename += "_detective"
    if use_godfather:
        filename += "_godfather"
    
        
    if not os.path.exists(dir_name):
        os.makedirs(dir_name)
    game.save_transcript(f"{dir_name}/{filename}.json")

    village_wins += int(winning_team == TeamAlignment.VILLAGE)
