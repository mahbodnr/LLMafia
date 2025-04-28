import math
from tqdm import tqdm
from src.game import MafiaGame
from src.models import TeamAlignment
import numpy as np
import os

# disable logging
import logging

logging.disable(logging.CRITICAL)

use_doctor = True
use_detective = True

n_repeats = 100
model_name = "llama3.3:70b"

for i, num_players in enumerate(range(10,11)):
    for mafia_count in range(1, math.ceil(num_players / 2)):
        mafia_wins = 0
        print(f"Running simulations for {num_players} players and {mafia_count} mafia...")
        for n in tqdm(range(n_repeats)):
            # Create custom config
            config = {
                "num_players": num_players,
                "roles": {
                    "Villager": num_players
                    - mafia_count
                    - int(use_doctor)
                    - int(use_detective),
                    "Mafia": mafia_count,
                    "Doctor": int(use_doctor),
                    "Detective": int(use_detective),
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
                "ai_models": {
                    "ollama": {
                        "model": model_name,
                        "base_url": os.environ.get(
                            "OLLAMA_URL", "http://localhost:11434"
                        ),
                    },
                },
            }

            # Create game instance with custom config
            game = MafiaGame(config)

            # Initialize game with custom player names
            game.initialize_game()

            # Run game
            game_over, winning_team = game.game_controller.run_game()

            filename = f"p{num_players}_m{mafia_count}_i{n}"
            if use_doctor:
                filename += "_doctor"
            if use_detective:
                filename += "_detective"
            if not os.path.exists(f"analyze/transcripts/{model_name}/"):
                os.makedirs(f"analyze/transcripts/{model_name}/")
            game.save_transcript(f"analyze/transcripts/{model_name}/{filename}.json")

            mafia_wins += int(winning_team == TeamAlignment.MAFIA)

