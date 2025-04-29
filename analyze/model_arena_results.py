from .extract_results import extract_results
import numpy as np
from matplotlib import pyplot as plt
import seaborn as sns


model_1 = "llama3.2:1b"
model_2 = "llama3.3:70b"

win_rate = lambda df: (
    df[df["winning_team"] == "VILLAGE"].shape[0] / df.shape[0]
    if df.shape[0] > 0
    else -1
)

results = np.zeros((2, 2))
results[0, 0] = win_rate(extract_results(model_1))
results[1, 1] = win_rate(extract_results(model_2))
results[1, 0] = win_rate(extract_results(f"v:{model_1}_vs_m:{model_2}"))
results[0, 1] = win_rate(extract_results(f"v:{model_2}_vs_m:{model_1}"))


# plot the results
sns.set(style="whitegrid")
plt.figure(figsize=(8, 6))
sns.heatmap(
    results,
    annot=True,
    fmt=".2f",
    cmap="YlGnBu",
    linewidths=0.5,
    linecolor="lightgray",
    annot_kws={"size": 10},
    cbar=False,
)
plt.title("Village Win Rate Comparison")
plt.xlabel("Villager Model")
plt.ylabel("Mafia Model")
plt.xticks(ticks=[0.5, 1.5], labels=[model_1, model_2], rotation=0)
plt.yticks(ticks=[0.5, 1.5], labels=[model_1, model_2], rotation=0)
plt.tight_layout()
plt.show()

# Save the figure
plt.savefig(
    f"analyze/plots/{model_1}_vs_{model_2}_village_win_rate.png",
    dpi=300,
    bbox_inches="tight",
)