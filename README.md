# Mafia Game with LLM Agents

A social deduction party game (similar to Werewolf) where multiple language model agents play different roles and interact through structured prompts. The game is fully automated with LLM agents participating by chatting, reasoning, and voting.

## Overview

This project implements a Mafia/Werewolf game where language model agents (LLMs) play different roles and interact with each other. The game alternates between Day and Night phases, with players working to identify the Mafia members or eliminate the Villagers, depending on their role.

### Game Roles

- **Villager**: No special powers, can vote and discuss
- **Mafia**: Works secretly to eliminate one player per night
- **Doctor**: Can choose one player to protect each night
- **Detective**: Can investigate one player per night
- **Godfather**: Mafia leader who can override decisions and may appear innocent when investigated

### Game Flow

1. Players are randomly assigned roles
2. The game alternates between Day and Night phases:
   - **Day Phase**: All players discuss and vote to eliminate a suspected Mafia member
   - **Night Phase**: Mafia members choose a player to eliminate, while the Doctor and Detective use their special abilities
3. The game continues until either:
   - All Mafia members are eliminated (Village team wins)
   - Mafia members outnumber Villagers (Mafia team wins)

## Features

- Multiple LLM agents playing different roles (OpenAI, Anthropic, Google)
- Agent memory system to track game events and discussions
- Role-specific behaviors and actions
- Day/Night phase transitions
- Voting and elimination mechanics
- Web UI for visualizing the game
- Comprehensive testing framework
- Game transcripts for analysis

## Project Structure

```
mafia_game/
├── src/                  # Source code
│   ├── models.py         # Core data models
│   ├── agents.py         # Agent implementations
│   ├── controllers.py    # Game controllers
│   ├── game.py           # Main game logic
│   └── config.py         # Configuration settings
├── tests/                # Test suite
│   ├── test_game.py      # Unit tests
│   └── test_integration.py # Integration tests
├── ui/                   # Web interface
│   ├── app.py            # Flask server
│   ├── templates/        # HTML templates
│   └── static/           # CSS, JS, and assets
├── venv/                 # Python virtual environment
├── requirements.txt      # Project dependencies
└── README.md             # Project documentation
```

## Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/mafia-game.git
cd mafia-game
```

2. Create and activate a virtual environment:
```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Set up API keys for LLM providers:
```bash
export OPENAI_API_KEY="your_openai_key"
export ANTHROPIC_API_KEY="your_anthropic_key"
export GOOGLE_API_KEY="your_google_key"
```

## Usage

### Running the Game (Command Line)

To run the game with default settings:

```bash
python -m src.game
```

With custom settings:

```bash
python -m src.game --players 7 --mafia 2 --godfather True --doctor True --detective True --rounds 3 --verbose True
```

### Running the Web UI

To start the web interface:

```bash
python -m ui.app
```

Then open your browser and navigate to `http://localhost:5000`.

### Running Tests

To run the test suite:

```bash
python -m unittest discover tests
```

## Configuration

The game can be configured through the `config.py` file or by passing command-line arguments. Key configuration options include:

- Number of players
- Role distribution
- Discussion rounds per day
- Agent verbosity
- Game mechanics (e.g., whether the Godfather appears innocent)

## Extending the Game

### Adding New Roles

To add a new role:

1. Add the role to the `PlayerRole` enum in `models.py`
2. Update the team alignment logic in the `Player` class
3. Implement role-specific behavior in the agent classes
4. Add role-specific actions to the night phase controller

### Using Different LLM Providers

The game supports multiple LLM providers through the agent factory pattern. To add a new provider:

1. Create a new agent class that inherits from `BaseAgent`
2. Implement the required methods (`initialize_llm`, `generate_response`, etc.)
3. Add the new provider to the `create_agent` factory function

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- Inspired by the classic Mafia/Werewolf party game
- Built with LangChain for LLM integration
- Uses Flask and Socket.IO for the web interface
