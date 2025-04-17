"""
Server-side implementation for the Mafia Game UI with improved features.
"""

import os
import json
import logging
from datetime import datetime
from flask import Flask, render_template, request, jsonify, session, copy_current_request_context
from flask_socketio import SocketIO, emit, join_room

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
phase_messages = []  # Store messages generated during phase execution


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
    global game, speakers_queue, current_speaker_index, phase_messages

    logger.info(f"Starting new game with settings: {settings}")

    # Reset speakers queue
    speakers_queue = []
    current_speaker_index = 0
    phase_messages = []

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
    game.game_controller.register_callback("message", handle_message_callback)  # Register message callback

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
    global game, speakers_queue, current_speaker_index, phase_messages

    if not game or game.game_state.game_over:
        return

    logger.info("Moving to next phase")
    
    # Reset for new phase
    phase_messages = []
    speakers_queue = []
    current_speaker_index = 0

    # Save the current request context for the background thread
    current_sid = request.sid
    
    # Execute phase in a background thread to avoid blocking
    @copy_current_request_context
    def run_phase_with_context():
        execute_phase_in_background(current_sid)
    
    socketio.start_background_task(run_phase_with_context)
    
    # Update game state immediately
    emit_game_state()


def execute_phase_in_background(sid):
    """Execute game phase in background to allow real-time updates."""
    global game
    
    if not game:
        return
    
    logger.info("Executing phase in background")
    
    try:
        # Run the current phase - will trigger message callbacks
        phase_result = game.game_controller.run_phase()
        
        # Check if game is over
        if game.game_state.game_over:
            emit_game_over()
        
        # Advance to next phase
        game.game_controller.advance_phase()
        
        # Send updated game state
        emit_game_state()
        
        logger.info("Background phase execution completed")
        
    except Exception as e:
        logger.error(f"Error in background thread: {e}", exc_info=True)


def handle_message_callback(message):
    """Handle messages as they are generated during phase execution."""
    global phase_messages, speakers_queue
    
    try:
        # Log the received message for debugging
        logger.info(f"Message callback received: {message.sender_id} - {message.content[:20]}...")
        
        # Add to phase messages
        phase_messages.append(message)
        
        # If this is a discussion phase message, also add to speakers queue
        current_phase = game.game_state.current_phase
        if "discussion" in current_phase.name.lower():
            speakers_queue.append(message)
            
            # If this is the first message and no speaker is active, initiate speaker display
            if len(speakers_queue) == 1 and current_speaker_index == 0:
                logger.info("Emitting first speaker prompt")
                emit_speaker_prompt(message)
                emit_message(message)
    except Exception as e:
        logger.error(f"Error in message callback: {e}", exc_info=True)


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
        
        # If the phase is still running, inform client that more speakers may be coming
        # if not game.game_state.current_phase.complete:
        #     emit("waiting_for_messages", {"active": True})


@socketio.on("check_new_messages")
def handle_check_new_messages():
    """Check if new messages are available for the current phase."""
    global speakers_queue, current_speaker_index
    
    if current_speaker_index < len(speakers_queue) - 1:
        current_speaker_index += 1
        emit_speaker_prompt(speakers_queue[current_speaker_index])
        emit_message(speakers_queue[current_speaker_index])
        return True
    
    return False


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
                memory_item["sender"] = entry["sender_name"]
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

    agent = game.game_controller.agents[player_id]


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
    try:
        sender_name = game.game_state.players[message.sender_id].name
        
        logger.info(f"Emitting message: {sender_name} - {message.content[:20]}...")
        
        # Use socketio.emit for background thread compatibility
        socketio.emit(
            "chat_message",
            {
                "sender_id": message.sender_id,
                "sender_name": sender_name,
                "content": message.content,
                "public": message.public,
                "timestamp": datetime.now().isoformat(),
            }
        )
    except Exception as e:
        logger.error(f"Error in emit_message: {e}", exc_info=True)


def emit_speaker_prompt(message):
    """Emit speaker prompt."""
    try:
        player_name = game.game_state.players[message.sender_id].name
        message_content = message.content
        
        logger.info(f"Emitting speaker prompt: {player_name}")
        
        # Use socketio.emit instead of emit for background thread compatibility
        socketio.emit("next_speaker", {
            "speaker_id": message.sender_id,
            "player_name": player_name,
            "message": message_content,
        })
        
        socketio.emit("center_display", {
            "active": True,
            "speaker_id": message.sender_id,
            "player_name": player_name,
            "message": message_content
        })
    except Exception as e:
        logger.error(f"Error in emit_speaker_prompt: {e}", exc_info=True)


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
