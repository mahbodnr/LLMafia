import numpy as np
import matplotlib
import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd
import math

results = np.load("analyze/results/random_agents_500.npz")["results"]
# results[results != -1] = 1 - results[results != -1]  # Invert win rates
player_range = range(5, 5 + len(results))

# Load the results from the CSV file
# model_name = "llama3.3:70b"
# results_db = pd.read_csv(f"analyze/transcripts/{model_name}/results.csv")
# player_range = range(results_db["num_players"].min(), results_db["num_players"].max() + 1)
# results = np.ones((len(player_range), math.ceil(max(player_range) / 2) - 1)) * -1
# for i, num_players in enumerate(player_range):
#     for mafia_count in range(1, math.ceil(num_players / 2)):
#         mafia_wins = results_db[
#             (results_db["num_players"] == num_players)
#             & (results_db["mafia_count"] == mafia_count)
#             & (results_db["winning_team"] == "MAFIA")
#         ].shape[0]
#         total_games = results_db[
#             (results_db["num_players"] == num_players)
#             & (results_db["mafia_count"] == mafia_count)
#         ].shape[0]
#         if total_games > 0:
#             results[i, mafia_count - 1] = mafia_wins / total_games

# Create a mask for the -1 values
mask = results == -1

# Transpose results and mask for rotated plot
results_T = results.T
mask_T = mask.T

# Get the colormap and set the color for masked values
cmap = matplotlib.colormaps["YlGnBu"]
cmap.set_bad(color='black')

sns.set(style="whitegrid")
plt.figure(figsize=(10, 8))
# Apply the transposed mask, use the modified colormap, add lines and adjust annotation size
sns.heatmap(results_T,
            annot=True,
            fmt=".2f",
            cmap=cmap,
            cbar_kws={'label': 'Mafia Win Rate'},
            mask=mask_T,
            linewidths=.5,
            linecolor='lightgray',
            annot_kws={"size": 10})
plt.title("Mafia Win Rate vs Number of Mafia and Total Players")
plt.xlabel("Number of Players")
plt.ylabel("Number of Mafia Players")

# Adjust ticks for transposed axes and center them
plt.xticks(ticks=np.arange(len(player_range)) + 0.5, labels=[str(i) for i in player_range], rotation=0)
max_mafia_count_simulated = results.shape[1]
plt.yticks(ticks=np.arange(max_mafia_count_simulated) + 0.5, labels=[str(i) for i in range(1, max_mafia_count_simulated + 1)], rotation=0)

# limit the matrix
# plt.xlim(0, 6)
# plt.ylim(0, 6)

# Reverse the y-axis
plt.gca().invert_yaxis()

# Save the figure
# plt.savefig(f"analyze/plots/{model_name}_mafia_win_rate.png", dpi=300, bbox_inches='tight')
plt.savefig(f"analyze/plots/random_agents_mafia_win_rate.png", dpi=300, bbox_inches='tight')

# plt.tight_layout()
plt.show()

