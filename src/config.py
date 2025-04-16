"""
Configuration settings for the Mafia Game.
"""

# Game settings
DEFAULT_GAME_SETTINGS = {
    # Number of players in the game
    "num_players": 8,
    
    # Role distribution
    "roles": {
        "Villager": 3,
        "Mafia": 2,
        "Doctor": 1,
        "Detective": 1,
        "Godfather": 1,
    },
    
    # Game phases
    "phases": {
        "day": {
            "discussion_rounds": 3,  # Number of discussion rounds before voting
            "discussion_max_length": 200,  # Maximum length of each agent's message
            "voting_time": 1,  # Number of voting rounds
            "enable_reactions": False,  # Whether to enable reactions during discussion
        },
        "night": {
            "mafia_discussion_rounds": 2,  # Number of discussion rounds for mafia
            "action_time": 1,  # Number of action rounds
            "enable_mafia_reactions": False,  # Whether to enable reactions for mafia
        }
    },
    
    # Agent settings
    "agent": {
        "verbosity": "elaborate",  # "brief" or "elaborate"
        "max_message_length": 200,  # Maximum length of agent messages
        "memory_limit": 10,  # Number of past events to remember
    },
    
    # Game mechanics
    "mechanics": {
        "godfather_appears_innocent": True,  # Whether Godfather appears innocent to Detective
        "reveal_role_on_death": True,  # Whether to reveal a player's role when they die
        "allow_no_kill_night": False,  # Whether Mafia can choose not to kill anyone
    }
}

# LLM Provider settings
LLM_PROVIDERS = {
    "openai": {
        "model": "gpt-3.5-turbo",
        "api_key_env": "OPENAI_API_KEY",
    },
    "anthropic": {
        "model": "claude-3-7-sonnet-latest",
        "api_key_env": "ANTHROPIC_API_KEY",
    },
    "google": {
        "model": "gemini-pro",
        "api_key_env": "GOOGLE_API_KEY",
    }
}

# Web UI settings
UI_SETTINGS = {
    "port": 5000,
    "host": "0.0.0.0",
    "debug": True,
    "theme": "dark",
    "animation_speed": "normal",  # "slow", "normal", "fast"
    "auto_scroll": True,
}

# Logging settings
LOGGING = {
    "level": "INFO",
    "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    "file": "mafia_game.log",
    "save_transcripts": True,
    "transcript_dir": "transcripts",
}
