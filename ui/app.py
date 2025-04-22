"""
Server-side implementation for the Mafia Game UI with improved features.
"""

import os
import json
import logging
import uuid
import tempfile
from datetime import datetime
from typing import List, Dict, Any, Optional, Callable, Union

from flask import (
    Flask,
    render_template,
    request,
    jsonify,
    session,
    copy_current_request_context,
)
from flask_socketio import SocketIO, emit, join_room

from src.game import MafiaGame
from src.models import TeamAlignment, Action, Message

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


class GameManager:
    """Manager class for the Mafia game state and operations."""
    
    def __init__(self):
        """Initialize the game manager."""
        self.game = None
        self.current_speaker_index = 0
        self.speakers_queue = []
        self.phase_messages = []  # Store messages generated during phase execution
        self.night_actions_queue = []  # Store night actions queue
        self.current_action_index = 0  # Track current action being displayed
        # Add transcript storage
        self.uploaded_transcript = None
        self.transcript_path = None

    def reset(self):
        """Reset the game manager state."""
        self.game = None
        self.current_speaker_index = 0
        self.speakers_queue = []
        self.phase_messages = []
        self.night_actions_queue = []
        self.current_action_index = 0
        # Don't reset transcript - we might want to replay

    def start_game(self, settings: Dict[str, Any]) -> bool:
        """
        Start a new game with the provided settings.
        
        Args:
            settings: Game configuration settings
            
        Returns:
            True if game started successfully, False otherwise
        """
        try:
            logger.info(f"Starting new game with settings: {settings}")
            
            # Reset game state
            self.speakers_queue = []
            self.current_speaker_index = 0
            self.phase_messages = []
            
            # Create role distribution based on settings
            roles = self._create_role_distribution(settings)
            
            # Create game config
            config = self._create_game_config(settings, roles)
            
            # Generate player names
            player_names = generate_player_names(settings["playerCount"])
            
            # Check if we should use an uploaded transcript
            if settings.get("useTranscript", False) and self.uploaded_transcript:
                logger.info("Starting game from uploaded transcript")
                
                # Create game instance using transcript
                self.game = MafiaGame(transcript=self.uploaded_transcript)
                
                # Initialize game
                self.game.initialize_game(player_names)
            else:
                # Start a new game from scratch
                logger.info("Starting fresh game")
                
                # Create game instance
                self.game = MafiaGame(config)
                
                # Initialize game
                self.game.initialize_game(player_names)

            return True
        except Exception as e:
            logger.error(f"Error starting game: {e}", exc_info=True)
            return False
    
    def save_uploaded_transcript(self, transcript_data: Dict[str, Any]) -> bool:
        """Save uploaded transcript data."""
        try:
            # Store in memory
            self.uploaded_transcript = transcript_data
            
            # Also save to temporary file for backup
            fd, self.transcript_path = tempfile.mkstemp(suffix='.json', prefix='mafia_transcript_')
            with os.fdopen(fd, 'w') as f:
                json.dump(transcript_data, f)
            
            logger.info(f"Transcript saved to {self.transcript_path}")
            return True
        except Exception as e:
            logger.error(f"Error saving transcript: {e}", exc_info=True)
            self.uploaded_transcript = None
            self.transcript_path = None
            return False
    
    def clear_uploaded_transcript(self):
        """Clear uploaded transcript data."""
        self.uploaded_transcript = None
        
        # Remove temporary file if it exists
        if self.transcript_path and os.path.exists(self.transcript_path):
            try:
                os.remove(self.transcript_path)
            except Exception as e:
                logger.error(f"Error removing transcript file: {e}")
        
        self.transcript_path = None
        logger.info("Transcript cleared")
    
    def _create_role_distribution(self, settings: Dict[str, Any]) -> Dict[str, int]:
        """Create role distribution based on settings."""
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
        
        return roles
    
    def _create_game_config(self, settings: Dict[str, Any], roles: Dict[str, int]) -> Dict[str, Any]:
        """Create game configuration from settings."""
        return {
            "num_players": settings["playerCount"],
            "roles": roles,
            "phases": {
                "day": {
                    "discussion_rounds": settings["discussionRounds"],
                    "voting_time": 1,
                },
                "night": {
                    "mafia_discussion_rounds": settings["discussionRounds"],
                    "action_time": 1,
                },
            },
            "agent": {
                "verbosity": "elaborate" if settings["verboseMode"] else "brief",
                "max_message_length": 300,
                "memory_limit": None,
            },
            "llm_providers": {
                # Configure your LLM providers here
                "debug": {"model": "debug"},
            },
            "mechanics": {
                "godfather_appears_innocent": True,
                "reveal_role_on_death": True,
            },
            "monitoring": {
                "helicone": {
                    "enabled": True,
                    "api_key_env": "HELICONE_API_KEY",
                }
            },
        }
    
    def register_callbacks(self):
        """Register event callbacks with the game controller."""
        if not self.game or not self.game.game_controller:
            return
            
        self.game.game_controller.register_callback("game_event", emit_game_event)
        self.game.game_controller.register_callback("message", handle_message_callback)
        self.game.game_controller.register_callback("action", emit_action)
        self.game.game_controller.register_callback("vote", emit_vote)
    
    def execute_phase(self):
        """Execute the current game phase in the background."""
        if not self.game:
            return
            
        logger.info(f"Executing phase {self.game.game_state.current_phase.name} in background")
        
        # Check if game is over
        if self.game.game_controller.check_game_over():
            return
            
        try:
            # Run the current phase - will trigger message callbacks
            phase_result = self.game.game_controller.run_phase()
            
            # Advance to next phase
            self.game.game_controller.advance_phase()
            
            logger.info("Background phase execution completed")
            
        except Exception as e:
            logger.error(f"Error in phase execution: {e}", exc_info=True)
    
    def handle_message(self, message: Message):
        """Handle incoming messages during phase execution."""
        try:
            # Log the received message for debugging
            logger.info(
                f"Message callback received: {message.sender_id} - {message.content[:20]}..."
            )
            
            # Add to phase messages
            self.phase_messages.append(message)
            
            # If this is a discussion phase message, also add to speakers queue
            if self.game and self.game.game_state and "discussion" in self.game.game_state.current_phase.name.lower():
                self.speakers_queue.append(message)
                
                # If this is the first message and no speaker is active, initiate speaker display
                if len(self.speakers_queue) == 1 and self.current_speaker_index == 0:
                    logger.info("Emitting first speaker prompt")
                    emit_speaker_prompt(message)
                    emit_message(message)
        except Exception as e:
            logger.error(f"Error in message callback: {e}", exc_info=True)
    
    def handle_action(self, action: Action):
        """Handle night actions during phase execution."""
        try:
            # Get current phase
            if not self.game or not self.game.game_state:
                return
                
            current_phase = self.game.game_state.current_phase.name.lower()
            
            # Add to queue
            self.night_actions_queue.append(action)
            
            logger.info(f"Added night action to queue: {action.action_type}")
            
            # If this is the first action and nothing is being displayed, show it
            if len(self.night_actions_queue) == 1 and self.current_action_index == 0:
                self.display_next_action()
                
        except Exception as e:
            logger.error(f"Error in emit_action: {e}", exc_info=True)
    
    def display_next_action(self):
        """Display the next action in the queue."""
        if not self.night_actions_queue or self.current_action_index >= len(self.night_actions_queue):
            return
            
        action = self.night_actions_queue[self.current_action_index]
        
        # Log for debugging
        logger.info(f"Displaying action: {action.action_type}")
        
        actor_name = self.game.game_state.players[action.actor_id].name
        target_name = self.game.game_state.players[action.target_id].name
        
        socketio.emit(
            "center_display",
            {
                "active": True,
                "is_action": True,
                "action_type": action.action_type,
                "actor": actor_name,
                "target": target_name,
            },
        )
        
        logger.info(
            f"Displayed action {self.current_action_index + 1} of {len(self.night_actions_queue)}"
        )
    
    def continue_action(self):
        """Handle continuing to the next action."""
        # If we have no actions, do nothing
        if not self.night_actions_queue:
            return
            
        self.current_action_index += 1
        
        # Check if we have more actions
        if self.current_action_index < len(self.night_actions_queue):
            # Display next action
            self.display_next_action()
        else:
            # No more actions, clear the center display
            socketio.emit("center_display", {"active": False})
            logger.info("No more actions to display")
    
    def continue_speaker(self):
        """Handle continuing to the next speaker."""
        if not self.speakers_queue:
            logger.info("No speakers in queue")
            emit("center_display", {"active": False})
            return
            
        # Move to next speaker
        self.current_speaker_index += 1
        
        # Check if we've gone through all current speakers
        if self.current_speaker_index < len(self.speakers_queue):
            # Send next speaker
            emit_speaker_prompt(self.speakers_queue[self.current_speaker_index])
            emit_message(self.speakers_queue[self.current_speaker_index])
        else:
            logger.info("No more speakers in queue currently")
            
            # Check if we're in a discussion phase and if the phase is still running
            if self.game and not self.game.game_controller.phase_completed:
                # If the phase is still running, inform client that more speakers may be coming
                logger.info("Phase still running, waiting for more messages")
                # Reset current speaker index to the last one
                self.current_speaker_index -= 1  # Reset to last speaker
                # Update center display to show waiting state
                socketio.emit(
                    "center_display",
                    {
                        "active": True,
                        "waiting": True,
                        "message": "Waiting for more messages...",
                    },
                )
            else:
                # No more speakers and phase is complete
                logger.info("No more speakers and phase is complete")
                emit("next_speaker", {"speaker_id": None})
                emit("center_display", {"active": False})


# Initialize game manager
game_manager = GameManager()


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
    if game_manager.start_game(settings):
        # Register callbacks
        game_manager.register_callbacks()
        
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
    if not game_manager.game or not game_manager.game.game_state or game_manager.game.game_state.game_over:
        return
        
    logger.info("Moving to next phase")
    
    # Update game state
    emit_game_state()
    
    # Reset for new phase
    game_manager.phase_messages = []
    game_manager.speakers_queue = []
    game_manager.current_speaker_index = 0
    game_manager.night_actions_queue = []
    game_manager.current_action_index = 0
    
    # Save the current request context for the background thread
    current_sid = request.sid
    
    # Execute phase in a background thread to avoid blocking
    @copy_current_request_context
    def run_phase_with_context():
        game_manager.execute_phase()
        
    socketio.start_background_task(run_phase_with_context)


@socketio.on("continue_action")
def handle_continue_action():
    """Handle continue button click for night actions."""
    game_manager.continue_action()


@socketio.on("continue_speaker_button")
def handle_continue_speaker_button():
    """Handle continue button click for speakers during day phase."""
    game_manager.continue_speaker()


@socketio.on("next_speaker")
def handle_next_speaker():
    """Handle next speaker request."""
    # Forward to the specialized handler
    handle_continue_speaker_button()


@socketio.on("reset_game")
def handle_reset_game():
    """Handle reset game request."""
    game_manager.reset()
    
    # Clear any active message displays
    socketio.emit("center_display", {"active": False})
    
    logger.info("Game reset")


@socketio.on("get_transcript")
def handle_get_transcript(callback=None):
    """Handle get transcript request."""
    if not game_manager.game:
        logger.error("Cannot generate transcript: no active game")
        if callback:
            callback({"error": "No active game"})
        return
        
    try:
        # First check if the game has the _save_transcript method
        if not hasattr(game_manager.game, "_save_transcript"):
            logger.error("Game object does not have _save_transcript method")
            if callback:
                callback({"error": "Game does not support transcript generation"})
            return
            
        # Save transcript and get the file path
        transcript_file = game_manager.game._save_transcript()
        
        # Verify that we got a valid file path
        if not transcript_file or not os.path.exists(transcript_file):
            logger.error(f"Transcript file not created or not found: {transcript_file}")
            if callback:
                callback({"error": "Failed to generate transcript file"})
            return
            
        logger.info(f"Transcript saved to file: {transcript_file}")
        
        # Read transcript back from file with explicit encoding
        try:
            with open(transcript_file, "r", encoding="utf-8") as f:
                file_content = f.read()
                
            if not file_content:
                logger.error("Transcript file is empty")
                if callback:
                    callback({"error": "Generated transcript file is empty"})
                return
                
            # Parse the JSON content
            transcript_data = json.loads(file_content)
                
            # Log success and file size
            file_size = os.path.getsize(transcript_file)
            logger.info(f"Transcript loaded successfully: {file_size} bytes")
            
            # Create a minimal transcript if the data is empty
            if not transcript_data:
                logger.warning("Empty transcript data, creating minimal transcript")
                transcript_data = {
                    "generated_at": datetime.now().isoformat(),
                    "note": "This is a minimal transcript due to issues with the normal transcript generation",
                    "game_state": {
                        "players": [
                            {"name": p.name, "role": p.role.name, "team": p.team.name, "is_alive": p.is_alive}
                            for p in game_manager.game.game_state.players.values()
                        ],
                        "round": game_manager.game.game_state.current_round,
                        "phase": game_manager.game.game_state.current_phase.name
                    }
                }
                
            # Return transcript as serialized JSON data
            if callback:
                callback(transcript_data)
                logger.info(f"Transcript sent to client: {len(str(transcript_data))} bytes, {len(transcript_data.keys()) if isinstance(transcript_data, dict) else 'not a dict'} keys")
                
        except json.JSONDecodeError as je:
            logger.error(f"Failed to parse transcript file as JSON: {je}")
            # Try to read the raw content for debugging
            try:
                with open(transcript_file, "r", encoding="utf-8") as f:
                    raw_content = f.read(1000)  # Read first 1000 chars for debug
                logger.error(f"First 1000 chars of file: {raw_content}")
            except Exception:
                pass
                
            if callback:
                callback({"error": f"Invalid JSON in transcript file: {str(je)}"})
                
        except Exception as fe:
            logger.error(f"Failed to read transcript file: {fe}", exc_info=True)
            if callback:
                callback({"error": f"Failed to read transcript: {str(fe)}"})
                
    except Exception as e:
        logger.error(f"Error generating transcript: {e}", exc_info=True)
        if callback:
            callback({"error": f"Failed to generate transcript: {str(e)}"})


@socketio.on("player_reaction")
def handle_player_reaction(data):
    """Handle player reaction."""
    try:
        logger.info(f"Player reaction received: {data}")
        
        # Broadcast reaction to all clients
        socketio.emit("player_reaction", data)
        
        # Log reaction
        logger.info(
            f"Player {data['player_id']} reacted to {data['target_id']} with {data['reaction_type']}"
        )
    except Exception as e:
        logger.error(f"Error handling player reaction: {e}")


@socketio.on("clear_center_display")
def handle_clear_center_display():
    """Handle clearing the center display when not needed."""
    emit("center_display", {"active": False})


@socketio.on("get_player_memory")
def handle_get_player_memory(player_id):
    """Handle request for player memory."""
    if not game_manager.game or player_id not in game_manager.game.game_state.players:
        emit("player_memory", {"player_id": player_id, "memory": [], "name": "Unknown"})
        return
        
    try:
        player = game_manager.game.game_state.players[player_id]
        memory_entries = []
        
        # Get player name for easier reference
        player_name = player.name
        
        # Get current game round for fallback
        current_game_round = game_manager.game.game_state.current_round
        logger.info(f"Current game round: {current_game_round}")
        
        # Extract base memory entries (messages and inner thoughts)
        if hasattr(player, "memory") and player.memory:
            for entry in player.memory:
                processed_entry = format_memory_entry(entry)
                # Only keep inner thoughts and messages from the player
                if processed_entry["type"] == "inner_thought" or (
                    processed_entry["type"] == "message" and 
                    processed_entry.get("sender") == player_name
                ):
                    memory_entries.append(processed_entry)
        
        # Add vote information (both from and to this player)
        try:
            # Try different possible attribute names
            votes = None
            for attr_name in ["votes", "all_votes"]:
                if hasattr(game_manager.game.game_state, attr_name):
                    votes = getattr(game_manager.game.game_state, attr_name)
                    break
            
            if votes:
                logger.info(f"Found {len(votes)} votes in game state")
                for vote in votes:
                    try:
                        # Debug log to see the vote object
                        debug_attrs = {
                            key: getattr(vote, key, None) 
                            for key in ["voter_id", "target_id", "round", "day", "phase"]
                            if hasattr(vote, key)
                        }
                        logger.info(f"Vote attributes: {debug_attrs}")
                        
                        # Get voter and target info safely
                        voter_id = getattr(vote, "voter_id", None)
                        target_id = getattr(vote, "target_id", None)
                        
                        if voter_id and target_id:
                            voter_name = game_manager.game.game_state.players[voter_id].name
                            target_name = game_manager.game.game_state.players[target_id].name
                            
                            # Get round information with better fallbacks
                            vote_round = None
                            # Try different attributes that might contain round info
                            for round_attr in ["round", "day"]:
                                if hasattr(vote, round_attr):
                                    vote_round = getattr(vote, round_attr)
                                    if vote_round is not None:
                                        break
                            
                            # If still no round, use current game round
                            if vote_round is None:
                                vote_round = current_game_round
                            
                            # Get phase information with fallback
                            vote_phase = "Voting"
                            if hasattr(vote, "phase") and getattr(vote, "phase") is not None:
                                phase_obj = getattr(vote, "phase")
                                if hasattr(phase_obj, "name"):
                                    vote_phase = phase_obj.name
                                else:
                                    vote_phase = str(phase_obj)
                            
                            # Only include votes involving this player
                            if voter_name == player_name or target_name == player_name:
                                vote_entry = {
                                    "type": "vote",
                                    "round": vote_round,
                                    "phase": vote_phase,
                                    "voter": voter_name,
                                    "target": target_name,
                                    "reason": getattr(vote, "reason", None)
                                }
                                memory_entries.append(vote_entry)
                                logger.info(f"Added vote in round {vote_round}, phase {vote_phase}: {voter_name} -> {target_name}")
                    except Exception as ve:
                        logger.error(f"Error processing vote: {ve}")
                        continue
        except Exception as e:
            logger.error(f"Error retrieving votes: {e}")
        
        # Add action information (only actions performed by this player)
        try:
            # Try different possible attribute names
            actions = None
            for attr_name in ["actions", "all_actions", "night_actions"]:
                if hasattr(game_manager.game.game_state, attr_name):
                    actions = getattr(game_manager.game.game_state, attr_name)
                    break
            
            if actions:
                logger.info(f"Found {len(actions)} actions in game state")
                for action in actions:
                    try:
                        # Debug log to see the action object
                        debug_attrs = {
                            key: getattr(action, key, None) 
                            for key in ["actor_id", "target_id", "round", "day", "phase", "action_type"]
                            if hasattr(action, key)
                        }
                        logger.info(f"Action attributes: {debug_attrs}")
                        
                        # Get actor and target info safely
                        actor_id = getattr(action, "actor_id", None)
                        target_id = getattr(action, "target_id", None)
                        
                        if actor_id and target_id:
                            actor_name = game_manager.game.game_state.players[actor_id].name
                            target_name = game_manager.game.game_state.players[target_id].name
                            
                            # Get round information with better fallbacks
                            action_round = None
                            # Try different attributes that might contain round info
                            for round_attr in ["round", "day"]:
                                if hasattr(action, round_attr):
                                    action_round = getattr(action, round_attr)
                                    if action_round is not None:
                                        break
                            
                            # If still no round, use current game round
                            if action_round is None:
                                action_round = current_game_round
                            
                            # Get phase information with fallback
                            action_phase = "Night Action"
                            if hasattr(action, "phase") and getattr(action, "phase") is not None:
                                phase_obj = getattr(action, "phase")
                                if hasattr(phase_obj, "name"):
                                    action_phase = phase_obj.name
                                else:
                                    action_phase = str(phase_obj)
                            
                            # Only include actions performed by this player
                            if actor_name == player_name:
                                action_entry = {
                                    "type": "action",
                                    "round": action_round,
                                    "phase": action_phase,
                                    "action_type": getattr(action, "action_type", "unknown"),
                                    "actor": actor_name,
                                    "target": target_name,
                                    "result": getattr(action, "result", None)
                                }
                                memory_entries.append(action_entry)
                                logger.info(f"Added action in round {action_round}, phase {action_phase}: {actor_name} {action_entry['action_type']} {target_name}")
                    except Exception as ae:
                        logger.error(f"Error processing action: {ae}")
                        continue
        except Exception as e:
            logger.error(f"Error retrieving actions: {e}")
        
        # Sort entries by round and phase
        memory_entries.sort(key=lambda x: (x.get("round", 0), x.get("phase", "")))
        
        # Get agent's model name
        agent = game_manager.game.game_controller.agents[player_id]
        model_name = getattr(agent, "model_name", "Unknown")
        
        # Send player memory back to client
        emit(
            "player_memory",
            {
                "player_id": player_id,
                "name": player.name,
                "role": player.role.name.capitalize(),
                "team": player.team.name.capitalize(),
                "is_alive": player.is_alive,
                "model_name": model_name,
                "memory": memory_entries,
            },
        )
        logger.info(f"Sent {len(memory_entries)} memory entries for {player.name}")
        
    except Exception as e:
        logger.error(f"Error retrieving player memory: {e}", exc_info=True)
        emit("player_memory", {"player_id": player_id, "memory": [], "error": str(e)})


@socketio.on("check_new_messages")
def handle_check_new_messages(callback=None):
    """Handle checking for new messages."""
    # Implement logic to check for new messages
    # This is just a placeholder response
    if callback:
        callback(False)  # Indicate no new messages available


@socketio.on("upload_transcript")
def handle_transcript_upload(data):
    """Handle transcript file upload."""
    try:
        logger.info(f"Received transcript upload: {data.get('filename', 'unknown')}")
        
        # Validate transcript data
        if not data.get('content'):
            logger.error("No content in uploaded transcript")
            emit("transcript_upload_response", {
                "success": False,
                "error": "No content in uploaded transcript"
            })
            return
            
        # Save transcript data
        if game_manager.save_uploaded_transcript(data['content']):
            emit("transcript_upload_response", {
                "success": True,
                "filename": data.get('filename', 'unknown')
            })
        else:
            emit("transcript_upload_response", {
                "success": False,
                "error": "Failed to save transcript"
            })
            
    except Exception as e:
        logger.error(f"Error handling transcript upload: {e}", exc_info=True)
        emit("transcript_upload_response", {
            "success": False,
            "error": f"Error: {str(e)}"
        })


@socketio.on("clear_transcript")
def handle_clear_transcript():
    """Handle clearing uploaded transcript."""
    game_manager.clear_uploaded_transcript()


# Helper functions

def format_memory_entry(entry):
    """Format a memory entry for transmission to client."""
    memory_item = {}
    
    memory_item["type"] = entry["type"]
    memory_item["round"] = entry["round"]
    memory_item["phase"] = entry["phase"]
    
    if entry["type"] in ["event", "inner_thought"]:
        memory_item["description"] = entry["description"]
    elif entry["type"] == "message":
        memory_item["sender"] = entry["sender_name"]
        memory_item["content"] = entry["content"]
        memory_item["public"] = entry["public"]
        
    return memory_item


def emit_game_state():
    """Emit the current game state to all clients."""
    if not game_manager.game:
        return
        
    try:
        # Get current phase
        phase_name = game_manager.game.game_state.current_phase.name.lower()
        
        # Determine if it's day or night
        time = "day" if "day" in phase_name else "night"
        
        # Create player list
        players = []
        for player_id, player in game_manager.game.game_state.players.items():
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
            "round": game_manager.game.game_state.current_round,
            "time": time,
            "players": players,
        }
        
        # Emit game state
        socketio.emit("game_state", state)
    except Exception as e:
        logger.error(f"Error emitting game state: {e}", exc_info=True)


def emit_game_event(event):
    """Emit a game event to all clients."""
    try:
        if event.event_type == "vote_result":
            # Emit vote result using the center_display mechanism
            socketio.emit(
                "center_display",
                {
                    "active": True,
                    "is_action": False,
                    "is_vote_result": True,
                    "message": event.description,
                    "title": "Vote Result",
                    "timestamp": datetime.now().isoformat(),
                },
            )
            # Also log it as a regular game event
            socketio.emit(
                "game_event",
                {
                    "event_type": event.event_type,
                    "description": event.description,
                    "public": event.public,
                    "timestamp": datetime.now().isoformat(),
                },
            )
            return
            
        if event.event_type == "vote":
            # Handled in emit_vote
            return
            
        if event.event_type == "game_over":
            return emit_game_over()
            
        socketio.emit(
            "game_event",
            {
                "event_type": event.event_type,
                "description": event.description,
                "public": event.public,
                "timestamp": datetime.now().isoformat(),
            },
        )
    except Exception as e:
        logger.error(f"Error emitting game event: {e}", exc_info=True)


def emit_vote(vote):
    """Emit a vote event to all clients."""
    try:
        socketio.emit(
            "vote",
            {
                "voter_id": vote.voter_id,
                "target_id": vote.target_id,
                "timestamp": datetime.now().isoformat(),
            },
        )
    except Exception as e:
        logger.error(f"Error emitting vote: {e}", exc_info=True)


def emit_action(action):
    """Emit an action event to the action queue."""
    game_manager.handle_action(action)


def emit_message(message):
    """Emit a chat message to all clients."""
    try:
        sender_name = game_manager.game.game_state.players[message.sender_id].name
        
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
            },
        )
    except Exception as e:
        logger.error(f"Error in emit_message: {e}", exc_info=True)


def emit_speaker_prompt(message):
    """Emit speaker prompt."""
    try:
        player_name = game_manager.game.game_state.players[message.sender_id].name
        message_content = message.content
        
        logger.info(f"Emitting speaker prompt: {player_name}")
        
        # Use socketio.emit instead of emit for background thread compatibility
        socketio.emit(
            "next_speaker",
            {
                "speaker_id": message.sender_id,
                "player_name": player_name,
                "message": message_content,
            },
        )
        
        socketio.emit(
            "center_display",
            {
                "active": True,
                "is_action": False,
                "speaker_id": message.sender_id,
                "player_name": player_name,
                "message": message_content,
            },
        )
    except Exception as e:
        logger.error(f"Error in emit_speaker_prompt: {e}", exc_info=True)


def emit_game_over():
    """Emit game over event to all clients."""
    if not game_manager.game or not game_manager.game.game_state.game_over:
        return
        
    try:
        # Get winning team
        winning_team = (
            "Village" if game_manager.game.game_state.winning_team == TeamAlignment.VILLAGE else "Mafia"
        )
        
        # Create player list
        players = []
        for player_id, player in game_manager.game.game_state.players.items():
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
            "total_rounds": game_manager.game.game_state.current_round,
            "total_messages": len(game_manager.game.game_state.messages),
            "total_votes": len(game_manager.game.game_state.votes),
        }
        
        # Clear all message displays
        socketio.emit("center_display", {"active": False})
        
        # Reset message tracking variables
        game_manager.speakers_queue = []
        game_manager.current_speaker_index = 0
        game_manager.night_actions_queue = []
        game_manager.current_action_index = 0
        
        # Emit game over event
        socketio.emit("game_over", result)
    except Exception as e:
        logger.error(f"Error emitting game over: {e}", exc_info=True)


def handle_message_callback(message):
    """Handle messages as they are generated during phase execution."""
    game_manager.handle_message(message)


def generate_player_names(count):
    """Generate player names."""
    names = [
        "Alice", "Bob", "Charlie", "Dave", "Eve", "Frank", "Grace", "Heidi",
        "Ivan", "Julia", "Kevin", "Laura", "Mike", "Nina", "Oscar", "Peggy",
        "Quincy", "Rachel", "Steve", "Tina", "Ursula", "Victor", "Wendy",
        "Xavier", "Yvonne", "Zach",
    ]
    
    # Ensure we have enough names
    if count > len(names):
        for i in range(len(names), count):
            names.append(f"Player_{i+1}")
            
    return names[:count]


if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=5000, debug=True)
