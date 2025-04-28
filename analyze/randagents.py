import math
from tqdm import tqdm
from src.game import MafiaGame
from src.models import TeamAlignment
import numpy as np

# disable logging
import logging
logging.disable(logging.CRITICAL)

use_doctor = True
n_repeats = 500
player_range = range(5, 11)
results = np.ones((len(player_range), math.ceil(max(player_range) / 2) - 1)) * -1

for i, num_players in enumerate(player_range):
    print(f"Running simulations for {num_players} players...")
    for mafia_count in tqdm(range(1, math.ceil(num_players / 2))):
        mafia_wins = 0
        for _ in range(n_repeats):
            # Create custom config
            config = {
                "num_players": num_players,
                "roles": {
                    "Villager": num_players - mafia_count - int(use_doctor),
                    "Mafia": mafia_count,
                    "Doctor": 1 if use_doctor else 0,
                    "Detective": 0,
                },
                "phases": {
                    "day": {
                        "discussion_rounds": 0,
                        "voting_time": 1,
                    },
                    "night": {
                        "mafia_discussion_rounds": 0,
                        "action_time": 1,
                    }
                },
                "ai_models": {
                        # Configure your LLM providers here
                        "random": {"model": "random"},
                    },
            }

            # Create game instance with custom config
            game = MafiaGame(config)

            # Initialize game with custom player names
            game.initialize_game()

            # Run game
            game_over, winning_team = game.game_controller.run_game()

            mafia_wins += int(winning_team == TeamAlignment.MAFIA)

        results[i, mafia_count - 1] = mafia_wins / n_repeats

np.savez(f"analyze/results/random_agents_{n_repeats}.npz", results=results)





