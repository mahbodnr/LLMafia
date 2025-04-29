import os
import json
import pandas as pd

# model_name = "v:llama3.2:1b_vs_m:llama3.3:70b"
model_name = "v:llama3.3:70b_vs_m:llama3.2:1b"
# model_name = "llama3.2:1b"

def extract_results(model_name):
    results = []
    for filename in os.listdir(f"analyze/transcripts/{model_name}"):
        if filename.endswith(".json"):
            with open(os.path.join("analyze/transcripts", model_name, filename), "r") as f:
                transcript = json.load(f)

                results.append(
                    {
                        "num_players": transcript["config"]["num_players"],
                        "mafia_count": transcript["config"]["roles"]["Mafia"],
                        "doctor_count": transcript["config"]["roles"]["Doctor"],
                        "detective_count": transcript["config"]["roles"]["Detective"],
                        "winning_team": transcript["result"]["winning_team"],
                    }
                )

    df = pd.DataFrame(results)
    # save dataframe
    df.to_csv(f"analyze/results/{model_name}.csv", index=False) 

    return df