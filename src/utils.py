def generate_player_names(count):
    """Generate player names."""
    names = [
        "Agnes", "Bertram", "Clara", "Dorothy", "Edgar", "Florence", "Gerald", "Harriet", "Irving", "Josephine",
        "Kenneth", "Lillian", "Milton", "Norma", "Otis", "Phyllis", "Quincy", "Ruth", "Stanley", "Thelma",
        "Ulysses", "Vera", "Walter", "Xenia", "Yvonne", "Zachary", "Albert", "Beatrice", "Cecil", "Della",
        "Eugene", "Frances", "Gilbert", "Helen", "Isaac", "Jennie", "Karl", "Lucille", "Morris", "Nina",
        "Oscar", "Pauline", "Raymond", "Sylvia", "Thomas", "Ursula", "Victor", "Wilma", "Xander", "Yolanda",
        "Aiden", "Bella", "Caleb", "Daisy", "Ethan", "Fiona", "Gavin", "Hazel", "Ian", "Jade",
        "Kai", "Luna", "Mason", "Nora", "Owen", "Piper", "Quinn", "Riley", "Sawyer", "Tessa",
        "Uri", "Violet", "Wyatt", "Ximena", "Yara", "Zane", "Aria", "Brody", "Chloe", "Declan",
        "Ellie", "Finn", "Grace", "Hudson", "Isla", "Jaxon", "Kinsley", "Leo", "Mila", "Nash",
        "Olivia", "Peyton", "Rowan", "Skylar", "Theo", "Uma", "Vivian", "Wren", "Xavier", "Zoe"
    ]

    # Ensure we have enough names
    if count > len(names):
        for i in range(len(names), count):
            names.append(f"Player_{i+1}")
            
    return names[:count]
