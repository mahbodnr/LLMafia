"""
Server-side implementation for the Mafia Game UI with improved features.
"""

import os
import json
import logging
from datetime import datetime
from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit

from src.game import MafiaGame
from src.models import TeamAlignment

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    filename="mafia_game_server.log",
)
logger = logging.getLogger(__name__)

# Create Flask app
app = Flask(
    __name__,
    template_folder=os.path.join(os.path.dirname(__file__), "templates"),
    static_folder=os.path.join(os.path.dirname(__file__), "static"),
)
app.config["SECRET_KEY"] = "mafia_game_secret_key"
socketio = SocketIO(app, cors_allowed_origins="*")

# Game instance
game = None
current_speaker_index = 0
speakers_queue = []


@app.route("/")
def index():
    """Render the main page."""
    return render_template("index.html")


@socketio.on("connect")
def handle_connect():
    """Handle client connection."""
    logger.info(f"Client connected: {request.sid}")
    emit("connect", {"data": "Connected"})


@socketio.on("disconnect")
def handle_disconnect():
    """Handle client disconnection."""
    logger.info(f"Client disconnected: {request.sid}")


@socketio.on("start_game")
def handle_start_game(settings):
    """Handle start game request."""
    global game, speakers_queue, current_speaker_index

    logger.info(f"Starting new game with settings: {settings}")

    # Reset speakers queue
    speakers_queue = []
    current_speaker_index = 0

    # Create role distribution based on settings
    roles = {
        "Villager": settings["playerCount"]
        - settings["mafiaCount"]
        - (1 if settings["includeDoctor"] else 0)
        - (1 if settings["includeDetective"] else 0),
        "Mafia": settings["mafiaCount"] - (1 if settings["includeGodfather"] else 0),
    }

    if settings["includeDoctor"]:
        roles["Doctor"] = 1
    if settings["includeDetective"]:
        roles["Detective"] = 1
    if settings["includeGodfather"]:
        roles["Godfather"] = 1

    # Create game config
    config = {
        "num_players": settings["playerCount"],
        "roles": roles,
        "phases": {
            "day": {
                "discussion_rounds": settings["discussionRounds"],
                "voting_time": 1,
            },
            "night": {
                "mafia_discussion_rounds": 1,
                "action_time": 1,
            },
        },
        "agent": {
            "verbosity": "elaborate" if settings["verboseMode"] else "brief",
            "max_message_length": 200,
            "memory_limit": None,
        },
        "mechanics": {
            "godfather_appears_innocent": True,
            "reveal_role_on_death": True,
        },
    }

    # Create game instance
    game = MafiaGame(config)

    # Generate player names
    player_names = generate_player_names(settings["playerCount"])

    # Initialize game
    game.initialize_game(player_names)

    # Register event handlers
    game.game_controller.register_callback("game_event", emit_event)

    # Send initial game state
    emit_game_state()

    # Send game start event
    emit(
        "game_event",
        {
            "event_type": "game_start",
            "description": "The game has started. All players are gathering in the village.",
            "public": True,
            "timestamp": datetime.now().isoformat(),
        },
    )

    logger.info("Game started successfully")


@socketio.on("next_phase")
def handle_next_phase():
    """Handle next phase request."""
    global game, speakers_queue, current_speaker_index

    if not game or game.game_state.game_over:
        return

    logger.info("Moving to next phase")

    
    # Run the current phase
    phase_result = game.game_controller.run_phase()

    # Reset speakers queue for the new phase
    speakers_queue = []
    current_speaker_index = 0

    # If this is a discussion phase, prepare speakers queue
    current_phase = game.game_state.current_phase
    cuurent_round = game.game_state.current_round
    logger.info(f"Current phase: {current_phase.name}, Round: {cuurent_round}")

    if "discussion" in current_phase.name.lower():
        logger.info("Preparing speakers queue for discussion phase")
        # Get all messages for this phase
        for message in game.game_state.messages:
            if message.phase == current_phase and message.round_num == cuurent_round:
                # and message.public?
                speakers_queue.append(
                    message
                )

        logger.info(f"Speakers queue prepared with {len(speakers_queue)} speakers")

        # Start with the first speaker if available
        if speakers_queue:
            emit_speaker_prompt(speakers_queue[0])
            emit_message(speakers_queue[0])
            current_speaker_index = 0

    # Send updated game state
    emit_game_state()

    # Check if game is over
    if game.game_state.game_over:
        emit_game_over()

    game.game_controller.advance_phase()

@socketio.on("next_speaker")
def handle_next_speaker():
    """Handle next speaker request."""
    global speakers_queue, current_speaker_index

    if not speakers_queue:
        logger.info("No speakers in queue")
        emit("center_display", {"active": False})
        return

    # Move to next speaker
    current_speaker_index += 1

    # Check if we've gone through all speakers
    if current_speaker_index < len(speakers_queue):
        # Send next speaker
        emit_speaker_prompt(speakers_queue[current_speaker_index])
        emit_message(speakers_queue[current_speaker_index])
    else:
        logger.info("No more speakers in queue")
        # No more speakers
        emit("next_speaker", {"speaker_id": None})
        emit("center_display", {"active": False})


@socketio.on("reset_game")
def handle_reset_game():
    """Handle reset game request."""
    global game, speakers_queue, current_speaker_index

    game = None
    speakers_queue = []
    current_speaker_index = 0
    logger.info("Game reset")


@socketio.on("get_transcript")
def handle_get_transcript(callback):
    """Handle get transcript request."""
    global game

    if not game:
        callback({})
        return

    # Save transcript
    transcript_file = game._save_transcript()

    # Read transcript
    with open(transcript_file, "r") as f:
        transcript = json.load(f)

    # Return transcript
    callback(transcript)


@socketio.on("player_reaction")
def handle_player_reaction(data):
    """Handle player reaction."""
    logger.info(f"Player reaction received: {data}")

    # Broadcast reaction to all clients
    socketio.emit("player_reaction", data)

    # Log reaction
    logger.info(
        f"Player {data['player_id']} reacted to {data['target_id']} with {data['reaction_type']}"
    )


@socketio.on("clear_center_display")
def handle_clear_center_display():
    """Handle clearing the center display when not needed."""
    emit("center_display", {"active": False})


@socketio.on("get_player_memory")
def handle_get_player_memory(player_id):
    """Handle request for player memory."""
    global game
    
    if not game or player_id not in game.game_state.players:
        emit("player_memory", {"player_id": player_id, "memory": [], "name": "Unknown"})
        return
    
    player = game.game_state.players[player_id]
    memory_entries = []
    
    # Convert memory entries to serializable format
    if hasattr(player, 'memory') and player.memory:
        for entry in player.memory:
            memory_item = {}
            
            memory_item["type"] = entry["type"]
            memory_item["round"] = entry["round"]
            memory_item["phase"] = entry["phase"]
            
            if entry["type"] == "event":
                memory_item["description"] = entry["description"]
            elif entry["type"] == "message":
                memory_item["sender"] = entry["sender"]
                memory_item["content"] = entry["content"]
                memory_item["public"] = entry["public"]
                
            memory_entries.append(memory_item)
    
    # Send player memory back to client
    emit("player_memory", {
        "player_id": player_id,
        "name": player.name,
        "role": player.role.name.capitalize(),
        "team": player.team.name.capitalize(),
        "is_alive": player.is_alive,
        "memory": memory_entries
    })


def emit_game_state():
    """Emit the current game state to all clients."""
    global game

    if not game:
        return

    # Get current phase
    phase_name = game.game_state.current_phase.name.lower()

    # Determine if it's day or night
    time = "day" if "day" in phase_name else "night"

    # Create player list
    players = []
    for player_id, player in game.game_state.players.items():
        players.append(
            {
                "id": player_id,
                "name": player.name,
                "role": player.role.name.capitalize(),
                "status": "Alive" if player.is_alive else "Dead",
                "team": player.team.name.capitalize(),
            }
        )

    # Create game state object
    state = {
        "started": True,
        "phase": phase_name,
        "round": game.game_state.current_round,
        "time": time,
        "players": players,
    }

    # Emit game state
    socketio.emit("game_state", state)


def emit_event(event):
    """Emit a game event to all clients."""
    socketio.emit(
        "game_event",
        {
            "event_type": event.event_type,
            "description": event.description,
            "public": event.public,
            "timestamp": datetime.now().isoformat(),
        },
    )


def emit_message(message):
    """Emit a chat message to all clients."""
    sender_name = game.game_state.players[message.sender_id].name

    socketio.emit(
        "chat_message",
        {
            "sender_id": message.sender_id,
            "sender_name": sender_name,
            "content": message.content,
            "public": message.public,
            "timestamp": datetime.now().isoformat(),
        },
    )

def emit_speaker_prompt(message):
    """Emit speaker prompt."""
    
    emit("next_speaker", {
        "speaker_id": message.sender_id,
        "player_name": game.game_state.players[message.sender_id].name,
        "message": message.content,
    })
    
    emit("center_display", {
        "active": True,
        "speaker_id": message.sender_id,
        "player_name": game.game_state.players[message.sender_id].name,
        "message": message.content
    })

def emit_game_over():
    """Emit game over event to all clients."""
    global game

    if not game or not game.game_state.game_over:
        return

    # Get winning team
    winning_team = (
        "Village" if game.game_state.winning_team == TeamAlignment.VILLAGE else "Mafia"
    )

    # Create player list
    players = []
    for player_id, player in game.game_state.players.items():
        players.append(
            {
                "id": player_id,
                "name": player.name,
                "role": player.role.name.capitalize(),
                "status": "Alive" if player.is_alive else "Dead",
                "team": player.team.name.capitalize(),
            }
        )

    # Create result object
    result = {
        "winning_team": winning_team,
        "players": players,
        "total_rounds": game.game_state.current_round,
        "total_messages": len(game.game_state.messages),
        "total_votes": len(game.game_state.votes),
    }

    # Emit game over event
    socketio.emit("game_over", result)


def generate_player_names(count):
    """Generate player names."""
    names = [
        "Alice",
        "Bob",
        "Charlie",
        "Dave",
        "Eve",
        "Frank",
        "Grace",
        "Heidi",
        "Ivan",
        "Julia",
        "Kevin",
        "Laura",
        "Mike",
        "Nina",
        "Oscar",
        "Peggy",
        "Quincy",
        "Rachel",
        "Steve",
        "Tina",
        "Ursula",
        "Victor",
        "Wendy",
        "Xavier",
        "Yvonne",
        "Zach",
    ]

    # Ensure we have enough names
    if count > len(names):
        for i in range(len(names), count):
            names.append(f"Player_{i+1}")

    return names[:count]


if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=5000, debug=True)
