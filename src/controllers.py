"""
Game controllers for managing different phases of the Mafia game.
"""

from typing import Dict, List, Optional, Any, Tuple
import random
import logging
import uuid

from src.models import (
    GameState,
    Player,
    GamePhase,
    PlayerRole,
    PlayerStatus,
    TeamAlignment,
    GameEvent,
    Vote,
    Action,
    Message,
)
from src.agents import BaseAgent, create_agent

logger = logging.getLogger(__name__)


class GameController:
    """Main controller for the Mafia game."""

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the game controller.

        Args:
            config: Configuration settings for the game
        """
        self.config = config
        self.game_state = None
        self.agents: Dict[str, BaseAgent] = {}
        self.phase_controllers = {
            GamePhase.DAY_DISCUSSION: DayDiscussionController(self),
            GamePhase.DAY_VOTING: DayVotingController(self),
            GamePhase.NIGHT_MAFIA_DISCUSSION: NightMafiaDiscussionController(self),
            GamePhase.NIGHT_ACTION: NightActionController(self),
        }

        self.event_callbacks = {
            "message": [],
            "game_event": [],
            "action": [],
            "vote": [],
            # "elimination": [],
            "vote_result": [],
        }

    def initialize_game(self, player_names: List[str]) -> GameState:
        """
        Initialize a new game with the given player names.

        Args:
            player_names: List of player names

        Returns:
            The initial game state
        """
        # generate a game id:
        self.game_id = str(uuid.uuid4())
        self.config["game_id"] = self.game_id

        # Get role distribution from config
        role_distribution = self.config.get(
            "roles",
            {
                "Villager": 3,
                "Mafia": 2,
                "Doctor": 1,
                "Detective": 1,
                "Godfather": 1,
            },
        )
        self.config["roles"] = role_distribution

        # Validate that we have the right number of players
        total_roles = sum(role_distribution.values())
        if len(player_names) != total_roles:
            raise ValueError(
                f"Expected {total_roles} players, got {len(player_names)}"
                + f"\nThe given role distribution: {role_distribution}"
                + f"\nPlayer names: {player_names}"
            )

        # Create role assignment
        roles = []
        for role_name, count in role_distribution.items():
            role = getattr(PlayerRole, role_name.upper())
            roles.extend([role] * count)

        # Shuffle roles
        random.shuffle(roles)

        # Create players
        players = {}
        for i, (name, role) in enumerate(zip(player_names, roles)):
            player_id = f"player_{i+1}"
            players[player_id] = Player(
                id=player_id, name=name, role=role, status=PlayerStatus.ALIVE
            )

            # Initialize known roles (each player knows their own role)
            players[player_id].known_roles[player_id] = role

            # If player is Mafia or Godfather, they know who the other Mafia members are
            if role in [PlayerRole.MAFIA, PlayerRole.GODFATHER]:
                for pid, p in players.items():
                    if p.role in [PlayerRole.MAFIA, PlayerRole.GODFATHER]:
                        players[player_id].known_roles[pid] = p.role

        # Create initial game state
        self.game_state = GameState(
            players=players,
            current_round=1,
            current_phase=GamePhase.DAY_DISCUSSION,
            events=[],
            votes=[],
            actions=[],
            messages=[],
            game_over=False,
            winning_team=None,
        )

        # Initialize agents
        self._initialize_agents()

        # Add initial game event
        self._add_game_event(
            event_type="game_start",
            description="The game has started. All players are gathering in the village.",
            public=True,
        )

        self.phase_completed = False

        return self.game_state

    def _initialize_agents(self):
        """Initialize agents for all players."""
        # Get agent settings from config
        agent_config = self.config.get(
            "agent",
            {
                "verbosity": "elaborate",
                "max_message_length": 200,
                "memory_limit": None,
            },
        )
        self.config["agent"] = agent_config

        game_config = {
            "players": self.game_state.players,
            "roles": self.config.get("roles", {}),
            "game_id": self.game_id,
        }

        moitoring_config = self.config.get("monitoring", {})

        # Get LLM provider settings
        ai_models = self.config.get(
            "ai_models",
            [
                {"provider": "debug", "model": "debug"},
                # {"provider": "openai", "model": "gpt-4o-mini"},
                # {"provider":"anthropic", "model": "claude-3-5-sonnet-latest"},
                # {"provider":"google", "model": "gemini-2.0-flash"},
            ],
        )
        self.config["ai_models"] = ai_models

        # Assign providers to players (round-robin)
        for i, (player_id, player) in enumerate(self.game_state.players.items()):
            agent = None
            for j in range(len(ai_models)):
                model_config = ai_models[(i+j) % len(ai_models)]

                if "team" in model_config:
                    # Check if the model is for a specific team
                    if player.team.name.lower() != model_config["team"].lower():
                        continue
                
                if "role" in model_config:
                    # Check if the model is for a specific role
                    if player.role.name.lower() != model_config["role"].lower():
                        continue

                # Merge provider config with agent config
                combined_config = {
                    **agent_config,
                    **game_config,
                    **model_config,
                    **moitoring_config,
                }

                # Create agent
                agent = create_agent(player, model_config["provider"], combined_config)
                break
                
            
            if agent is None:
                raise ValueError(
                    f"No valid LLM provider found for player {player.name} with role {player.role.name}."+
                    f"\nAI models config: {ai_models}"
                )
            self.agents[player_id] = agent

    def register_callback(self, event_type: str, callback):
        """
        Register a callback for a specific event type.

        Args:
            event_type: Type of event ('message', 'vote', 'elimination', 'game_event')
            callback: Function to call when event occurs
        """
        if event_type in self.event_callbacks:
            self.event_callbacks[event_type].append(callback)
        else:
            logger.warning(f"Unknown event type: {event_type}")

    def emit_event(self, event_type: str, data: Any):
        """
        Emit an event to all registered callbacks.

        Args:
            event_type: Type of event
            data: Event data to pass to callbacks
        """
        if event_type in self.event_callbacks:
            for callback in self.event_callbacks[event_type]:
                try:
                    callback(data)
                except Exception as e:
                    logger.error(f"Error in {event_type} callback: {e}")

    def _add_game_event(
        self, event_type: str, description: str, public: bool, targets: List[str] = None
    ):
        """
        Add a new event to the game state.

        Args:
            event_type: Type of event
            description: Description of the event
            public: Whether this event is visible to all players
            targets: List of player IDs affected by this event
        """
        if targets is None:
            targets = []

        event = GameEvent(
            event_type=event_type,
            round_num=self.game_state.current_round,
            phase=self.game_state.current_phase,
            description=description,
            public=public,
            targets=targets,
        )

        self.emit_event("game_event", event)

        self.game_state.events.append(event)
        logger.info(f"Event: {description}")

    def run_game(self) -> Tuple[bool, Optional[TeamAlignment]]:
        """
        Run the game until completion.

        Returns:
            A tuple of (game_over, winning_team)
        """
        while not self.game_state.game_over:

            self.run_phase()

            # Check if game is over
            if self.check_game_over():
                break

            # Move to the next phase
            self.advance_phase()

            self.phase_completed = False

        return self.game_state.game_over, self.game_state.winning_team

    def run_phase(self):
        """Run the current game phase."""
        # Get the current phase
        current_phase = self.game_state.current_phase

        # Get the controller for the current phase
        controller = self.phase_controllers[current_phase]

        # Run the phase
        controller.run()

        # update agent memories
        controller._update_agent_memories()

        # Mark phase as completed
        self.phase_completed = True

    def advance_phase(self):
        """Advance to the next game phase."""
        current_phase = self.game_state.current_phase

        # Define phase order
        phase_order = [
            GamePhase.DAY_DISCUSSION,
            GamePhase.DAY_VOTING,
            GamePhase.NIGHT_MAFIA_DISCUSSION,
            GamePhase.NIGHT_ACTION,
        ]

        # Get index of current phase
        current_index = phase_order.index(current_phase)

        # Get next phase
        next_index = (current_index + 1) % len(phase_order)
        next_phase = phase_order[next_index]

        # In round 1, there is no voting and no night actions:
        if self.game_state.current_round == 1:
            if next_phase == GamePhase.DAY_VOTING:
                next_phase = GamePhase.NIGHT_MAFIA_DISCUSSION
            elif next_phase == GamePhase.NIGHT_ACTION:
                next_phase = GamePhase.DAY_DISCUSSION

        # reverse the order of the alive players for the next phase
        if next_phase == GamePhase.DAY_DISCUSSION:
            self.game_state.reverse_players_order()

        # If we're moving from night to day, increment the round number
        if next_phase == GamePhase.DAY_DISCUSSION:
            self.game_state.current_round += 1
            self._add_game_event(
                event_type="new_round",
                description=f"Round {self.game_state.current_round} has begun.",
                public=True,
            )

        # Update current phase
        self.game_state.current_phase = next_phase

        # Log phase change
        phase_name = next_phase.name
        logger.info(f"Moving to phase: {phase_name}")
        self._add_game_event(
            event_type="phase_change",
            description=f"Moving to {phase_name}.",
            public=True,
        )

    def check_game_over(self):
        """Check if the game is over and update the game state accordingly."""
        if self.game_state.check_game_over():
            winning_team = self.game_state.winning_team
            winning_team_name = (
                "Village" if winning_team == TeamAlignment.VILLAGE else "Mafia"
            )
            self._add_game_event(
                event_type="game_over",
                description=f"Game over! The {winning_team_name} team has won!",
                public=True,
            )
            return True
        return False


class PhaseController:
    """Base class for phase controllers."""

    def __init__(self, game_controller: GameController):
        """
        Initialize the phase controller.

        Args:
            game_controller: The main game controller
        """
        self.game_controller = game_controller

    def run(self):
        """Run this phase."""
        raise NotImplementedError("Subclasses must implement run()")

    def _update_agent_memories(self):
        """Update all agents' memories with the current game state."""
        for agent in self.agents.values():
            agent.update_memory(self.game_state)

    def emit_event(self, event_type: str, data: Any):
        """Emit an event to the game controller."""
        self.game_controller.emit_event(event_type, data)

    @property
    def game_state(self) -> GameState:
        """Get the current game state."""
        return self.game_controller.game_state

    @property
    def agents(self) -> Dict[str, BaseAgent]:
        """Get the agents dictionary."""
        return self.game_controller.agents

    @property
    def config(self) -> Dict[str, Any]:
        """Get the game configuration."""
        return self.game_controller.config


class DayDiscussionController(PhaseController):
    """Controller for the day discussion phase."""

    def run(self):
        """Run the day discussion phase."""
        # Get discussion settings from config
        discussion_rounds = (
            self.config.get("phases", {}).get("day", {}).get("discussion_rounds", 1)
        )

        # Update agent memories
        self._update_agent_memories()

        # Run discussion rounds
        for round_num in range(1, discussion_rounds + 1):
            self._run_discussion_round(round_num)

    def _run_discussion_round(self, round_num: int):
        """
        Run a single discussion round.

        Args:
            round_num: The discussion round number
        """
        # Get alive players
        alive_players = list(self.game_state.alive_players.values())

        # Shuffle player order
        # random.shuffle(alive_players)

        # Each player takes a turn to speak
        for player in alive_players:
            agent = self.agents[player.id]

            # Update agent memory with the current game state
            # agent.update_memory(self.game_state)

            # Update all agents' memories
            self._update_agent_memories()

            # Generate discussion message
            message_content = agent.generate_day_discussion(self.game_state)

            # Create message object
            message = Message(
                sender_name=player.name,
                sender_id=player.id,
                content=message_content,
                round_num=self.game_state.current_round,
                phase=GamePhase.DAY_DISCUSSION,
                public=True,
            )

            # Add message to game state
            self.game_state.messages.append(message)

            # Emit message event
            self.emit_event("message", message)

            # Log message
            logger.info(f"{player.name} says: {message_content}")

            # Other players react to the message if it is enabled
            if (
                self.config.get("phases", {})
                .get("day", {})
                .get("enable_reactions", False)
            ):
                self._collect_reactions(message, player)

    def _collect_reactions(self, message: Message, speaker: Player):
        """
        Collect reactions from other players to a message.

        Args:
            message: The message to react to
            speaker: The player who sent the message
        """
        # Get alive players excluding the speaker
        alive_players = [
            p for p in self.game_state.alive_players.values() if p.id != speaker.id
        ]

        # Each player reacts to the message
        for player in alive_players:
            agent = self.agents[player.id]

            # Generate reaction
            reaction = agent.react_to_message(message, self.game_state)

            # Log reaction
            logger.info(f"{player.name} {reaction}s to {speaker.name}'s message")

            # Add reaction as an event
            self.game_controller._add_game_event(
                event_type="reaction",
                description=f"{player.name} {reaction}s to {speaker.name}'s message",
                public=True,
                targets=[player.id, speaker.id],
            )


class DayVotingController(PhaseController):
    """Controller for the day voting phase."""

    def run(self):
        """Run the day voting phase."""
        # Get voting settings from config
        voting_rounds = (
            self.config.get("phases", {}).get("day", {}).get("voting_time", 1)
        )

        # Update agent memories
        self._update_agent_memories()

        # Run voting rounds
        for round_num in range(1, voting_rounds + 1):
            self._run_voting_round()

    def _run_voting_round(self):
        """Run a single voting round."""
        # Get alive players
        alive_players = list(self.game_state.alive_players.values())

        # Each player casts a vote
        votes = {}
        for player in alive_players:
            agent = self.agents[player.id]

            # Update agent memory with the current game state
            agent.update_memory(self.game_state)

            # Generate vote
            target_id = agent.generate_day_vote(self.game_state)

            if not target_id:
                # Skip if no target is generated
                continue

            # Validate vote
            if target_id not in self.game_state.alive_players or target_id == player.id:
                # Invalid vote,
                logger.warning(
                    f"{player.name} attempted to vote for an invalid target: {target_id}"
                )
                continue  # Skip if no valid targets

            # Create vote object
            vote = Vote(
                voter_id=player.id,
                target_id=target_id,
                round_num=self.game_state.current_round,
                phase=GamePhase.DAY_VOTING,
            )

            # Add vote to game state
            self.game_state.votes.append(vote)

            # Emit vote event
            self.emit_event("vote", vote)

            # Count vote
            votes[target_id] = votes.get(target_id, 0) + 1

            # Get target player name
            target_name = self.game_state.players[target_id].name

            # Log vote
            logger.info(f"{player.name} votes for {target_name}")

            # Add vote as an event
            self.game_controller._add_game_event(
                event_type="vote",
                description=f"{player.name} votes for {target_name}",
                public=True,
                targets=[player.id, target_id],
            )

        # Determine the player with the most votes
        if votes:
            # check if there is a tie
            max_votes = max(votes.values())
            tied_players = [pid for pid, count in votes.items() if count == max_votes]
            if len(tied_players) > 1:
                eliminated_players = [
                    self.game_state.players[pid].name for pid in tied_players
                ]

                self.game_controller._add_game_event(
                    event_type="vote_result",
                    description=f"{', '.join(eliminated_players)} are tied with {max_votes} votes each. No one is eliminated.",
                    public=True,
                )

                logger.info("No one was eliminated due to a tie!")

            else:
                eliminated_id = max(votes.items(), key=lambda x: x[1])[0]
                eliminated_player = self.game_state.players[eliminated_id]

                # Eliminate the player
                eliminated_player.status = PlayerStatus.DEAD

                # Log elimination
                logger.info(f"{eliminated_player.name} has been eliminated!")

                self.game_controller._add_game_event(
                    event_type="vote_result",
                    description=f"{eliminated_player.name} has been eliminated with {max_votes} votes!",
                    public=True,
                    targets=[eliminated_id],
                )

                # Add elimination as an event
                if self.config.get("mechanics", {}).get("reveal_role_on_death", True):
                    self.game_controller._add_game_event(
                        event_type="elimination",
                        description=f"{eliminated_player.name} has been eliminated! They were a {eliminated_player.role.name}.",
                        public=True,
                        targets=[eliminated_id],
                    )

                    # Update all players' known roles
                    for player in self.game_state.players.values():
                        player.known_roles[eliminated_id] = eliminated_player.role
                else:
                    self.game_controller._add_game_event(
                        event_type="elimination",
                        description=f"{eliminated_player.name} has been eliminated!",
                        public=True,
                        targets=[eliminated_id],
                    )


class NightMafiaDiscussionController(PhaseController):
    """Controller for the night mafia discussion phase."""

    def run(self):
        """Run the night mafia discussion phase."""
        # Get discussion settings from config
        discussion_rounds = (
            self.config.get("phases", {})
            .get("night", {})
            .get("mafia_discussion_rounds", 2)
        )

        # Update agent memories
        self._update_agent_memories()

        # Get alive mafia players
        alive_mafia = [
            p
            for p in self.game_state.alive_players.values()
            if p.team == TeamAlignment.MAFIA
        ]

        # If no mafia left, skip this phase
        if not alive_mafia:
            logger.info("No mafia players left, skipping mafia discussion")
            return

        # Run discussion rounds
        for round_num in range(1, discussion_rounds + 1):
            self._run_mafia_discussion_round(round_num, alive_mafia)

    def _run_mafia_discussion_round(self, round_num: int, mafia_players: List[Player]):
        """
        Run a single mafia discussion round.

        Args:
            round_num: The discussion round number
            mafia_players: List of alive mafia players
        """
        # Shuffle player order
        # random.shuffle(mafia_players)

        # Each mafia player takes a turn to speak
        for player in mafia_players:
            agent = self.agents[player.id]

            # Update agent memory with the current game state
            agent.update_memory(self.game_state)

            # Generate discussion message
            message_content = agent.generate_mafia_discussion(
                self.game_state
            )  # Reuse day discussion logic

            # Create message object
            message = Message(
                sender_name=player.name,
                sender_id=player.id,
                content=message_content,
                round_num=self.game_state.current_round,
                phase=GamePhase.NIGHT_MAFIA_DISCUSSION,
                public=False,
                recipients=[p.id for p in mafia_players],
            )

            # Add message to game state
            self.game_state.messages.append(message)

            # Emit message event
            self.emit_event("message", message)

            # Log message
            logger.info(f"[MAFIA] {player.name} says: {message_content}")

            # Other mafia players react to the message
            if (
                self.config.get("phases", {})
                .get("night", {})
                .get("enable_mafia_reactions", False)
            ):
                self._collect_mafia_reactions(message, player, mafia_players)

    def _collect_mafia_reactions(
        self, message: Message, speaker: Player, mafia_players: List[Player]
    ):
        """
        Collect reactions from other mafia players to a message.

        Args:
            message: The message to react to
            speaker: The player who sent the message
            mafia_players: List of all mafia players
        """
        # Get other mafia players excluding the speaker
        other_mafia = [p for p in mafia_players if p.id != speaker.id]

        # Each mafia player reacts to the message
        for player in other_mafia:
            agent = self.agents[player.id]

            # Generate reaction
            reaction = agent.react_to_message(message, self.game_state)

            # Log reaction
            logger.info(
                f"[MAFIA] {player.name} {reaction}s to {speaker.name}'s message"
            )

            # Add reaction as an event
            self.game_controller._add_game_event(
                event_type="mafia_reaction",
                description=f"{player.name} {reaction}s to {speaker.name}'s message",
                public=False,
                targets=[p.id for p in mafia_players],
            )


class NightActionController(PhaseController):
    """Controller for the night action phase."""

    def run(self):
        """Run the night action phase."""
        # Get action settings from config
        action_rounds = (
            self.config.get("phases", {}).get("night", {}).get("action_time", 1)
        )

        # Update agent memories
        self._update_agent_memories()

        # Run action rounds
        for round_num in range(1, action_rounds + 1):
            self._run_action_round()

    def _run_action_round(self):
        """Run a single action round."""
        # Get alive players
        alive_players = list(self.game_state.alive_players.values())

        # Collect actions from all players
        actions = {}
        for player in alive_players:
            agent = self.agents[player.id]

            # Generate night action
            action = agent.generate_night_action(self.game_state)

            if action:
                actions[player.role] = action

                # Add action to game state
                self.game_state.actions.append(action)

                # Log action (privately)
                target_name = self.game_state.players[action.target_id].name
                logger.info(
                    f"{player.name} ({player.role.name}) targets {target_name} with {action.action_type}"
                )

        # Process actions in the correct order
        self._process_night_actions(actions)

    def _process_night_actions(self, actions: Dict[PlayerRole, Action]):
        """
        Process night actions in the correct order.

        Args:
            actions: Dictionary mapping roles to their actions
        """
        # Get godfather action if available, otherwise use mafia action
        kill_action = None
        if PlayerRole.GODFATHER in actions:
            kill_action = actions[PlayerRole.GODFATHER]
        elif PlayerRole.MAFIA in actions:
            kill_action = actions[PlayerRole.MAFIA]

        # Get doctor action
        protect_action = actions.get(PlayerRole.DOCTOR)

        # Get detective action
        investigate_action = actions.get(PlayerRole.DETECTIVE)

        # Process detective action
        if investigate_action:
            self.emit_event("action", investigate_action)

            detective = self.game_state.players[investigate_action.actor_id]
            target = self.game_state.players[investigate_action.target_id]

            # Determine investigation result
            appears_innocent = False
            if target.role == PlayerRole.GODFATHER and self.config.get(
                "mechanics", {}
            ).get("godfather_appears_innocent", True):
                appears_innocent = True

            result = (
                "innocent"
                if (target.team == TeamAlignment.VILLAGE or appears_innocent)
                else "Mafia"
            )

            # Update detective's knowledge
            if not appears_innocent:
                detective.known_roles[target.id] = target.role

            # Add investigation event
            self.game_controller._add_game_event(
                event_type="investigation",
                description=f"You investigated {target.name} and found them to be {result}.",
                public=False,
                targets=[detective.id],
            )

        # Process doctor action
        protected_player_id = None
        if protect_action:
            self.emit_event("action", protect_action)

            protected_player_id = protect_action.target_id
            protected_player = self.game_state.players[protected_player_id]
            protected_player.protected = True

            # Add protection event
            self.game_controller._add_game_event(
                event_type="protection",
                description=f"You protected {protected_player.name} for the night.",
                public=False,
                targets=[protect_action.actor_id],
            )

        # Process kill action
        if kill_action:
            self.emit_event("action", kill_action)

            target_id = kill_action.target_id
            target = self.game_state.players[target_id]

            # Check if target is protected
            if target_id == protected_player_id:
                # Kill failed
                self.game_controller._add_game_event(
                    event_type="kill_failed",
                    description=f"You tried to eliminate {target.name}, but they were protected!",
                    public=False,
                    targets=[
                        p.id
                        for p in self.game_state.players.values()
                        if p.team == TeamAlignment.MAFIA
                    ],
                )

                # Public event
                self.game_controller._add_game_event(
                    event_type="night_result",
                    description="The night passes peacefully. No one was eliminated.",
                    public=True,
                )
            else:
                # Kill succeeded
                target.status = PlayerStatus.DEAD

                # Mafia notification
                self.game_controller._add_game_event(
                    event_type="kill_success",
                    description=f"You successfully eliminated {target.name}!",
                    public=False,
                    targets=[
                        p.id
                        for p in self.game_state.players.values()
                        if p.team == TeamAlignment.MAFIA
                    ],
                )

                # Public event
                if self.config.get("mechanics", {}).get("reveal_role_on_death", True):
                    self.game_controller._add_game_event(
                        event_type="night_elimination",
                        description=f"{target.name} was found dead! They were a {target.role.name}.",
                        public=True,
                        targets=[target_id],
                    )

                    # Update all players' known roles
                    for player in self.game_state.players.values():
                        player.known_roles[target_id] = target.role
                else:
                    self.game_controller._add_game_event(
                        event_type="night_elimination",
                        description=f"{target.name} was found dead!",
                        public=True,
                        targets=[target_id],
                    )
        else:
            # No kill action
            self.game_controller._add_game_event(
                event_type="night_result",
                description="The night passes peacefully. No one was eliminated.",
                public=True,
            )

        # Reset protection status for all players
        for player in self.game_state.players.values():
            player.protected = False


class RecordedGameController(GameController):
    """Main controller for the Mafia game from a recorded game."""

    def __init__(self, transcript: Dict[str, Any]):
        """
        Initialize the game controller.

        Args:
            transcript: Transcript of a recorded game
        """
        self.transcript = transcript
        self.config = transcript["config"]
        self.game_state = None
        self.agents: Dict[str, BaseAgent] = {}
        self.phase_controllers = {
            GamePhase.DAY_DISCUSSION: DayDiscussionRecordController(self),
            GamePhase.DAY_VOTING: DayVotingRecordController(self),
            GamePhase.NIGHT_MAFIA_DISCUSSION: NightMafiaDiscussionRecordController(
                self
            ),
            GamePhase.NIGHT_ACTION: NightActionRecordController(self),
        }
        self.event_callbacks = {
            "message": [],
            "game_event": [],
            "action": [],
            "vote": [],
            # "elimination": [],
            "vote_result": [],
        }
        self.game_id = transcript.get("game_id", str(uuid.uuid4()))
        self.game_over = False

        self.winning_team = None
        self.stream_event_index = 0

    def initialize_game(self, player_names: List[str]) -> GameState:
        players = {
            player_id: Player(
                id=player_id,
                name=player["name"],
                role=PlayerRole[player["role"].upper()],
            )
            for player_id, player in self.transcript["players"].items()
        }

        self.game_state = GameState(
            players=players,
            current_round=1,
            current_phase=GamePhase.DAY_DISCUSSION,
            events=[],
            votes=[],
            actions=[],
            messages=[],
            game_over=False,
            winning_team=None,
        )

        # Initialize agents
        self._initialize_agents()

        # Add initial game event
        self._add_game_event()

        self.phase_completed = False

        return self.game_state

    def _initialize_agents(self):
        """Initialize agents for all players."""
        # Get agent settings from config
        agent_config = self.transcript["config"].get(
            "agent",
            {
                "verbosity": "elaborate",
                "max_message_length": 200,
                "memory_limit": None,
            },
        )
        game_config = {
            "players": self.game_state.players,
            "roles": self.transcript["config"]["roles"],
            "game_id": self.game_id,
        }
        # No monitoring for recorded games
        moitoring_config = {}
        

        # Get LLM provider settings
        ai_models = self.transcript["config"]["ai_models"]

        # Assign providers to players (round-robin)
        for i, (player_id, player) in enumerate(self.game_state.players.items()):
            agent = None
            for j in range(len(ai_models)):
                model_config = ai_models[(i+j) % len(ai_models)]

                if "team" in model_config:
                    # Check if the model is for a specific team
                    if player.team.name.lower() != model_config["team"].lower():
                        continue
                
                if "role" in model_config:
                    # Check if the model is for a specific role
                    if player.role.name.lower() != model_config["role"].lower():
                        continue

                # Merge provider config with agent config
                combined_config = {
                    **agent_config,
                    **game_config,
                    **model_config,
                    **moitoring_config,
                }

                # Create agent
                agent = create_agent(player, model_config["provider"], combined_config)
                break
                
            
            if agent is None:
                raise ValueError(
                    f"No valid LLM provider found for player {player.name} with role {player.role.name}."+
                    f"\nAI models config: {ai_models}"
                )
            self.agents[player_id] = agent


        moitoring_config = {}  # No monitoring for recorded games

    def _add_game_event(self):
        """Add a new event to the game state."""
        # Get event data from transcript
        event_data = self.transcript["events"][self.stream_event_index]
        self.stream_event_index += 1

        # Create event object
        event = GameEvent(
            event_type=event_data["type"],
            round_num=event_data["round"],
            phase=GamePhase.__members__[event_data["phase"]],
            description=event_data["description"],
            public=event_data["public"],
            targets=event_data.get("targets", []),
        )

        # Emit event
        self.emit_event("game_event", event)

        if event.event_type == "elimination":
            if event.targets:
                # Update player status
                eliminated_player = self.game_state.players[event.targets[0]]
                eliminated_player.status = PlayerStatus.DEAD

        # Add event to game state
        self.game_state.events.append(event)
        logger.info(f"Event ({event.event_type}): {event.description}")

    def advance_phase(self):
        """Advance to the next game phase."""
        if (
            self.stream_event_index >= len(self.transcript["events"]) - 1 
            or self.transcript["events"][self.stream_event_index]["type"] == "game_over"
        ):
            logger.info(f"Game over! The game has ended. stream_event_index: {self.stream_event_index} treanscript_events: {len(self.transcript['events'])}")
            self.game_state.game_over = True
            self.game_state.winning_team = TeamAlignment.__members__[
                self.transcript["result"]["winning_team"]
            ]

            # emit game over event
            event = GameEvent(
                event_type="game_over",
                round_num=self.game_state.current_round,
                phase=self.game_state.current_phase,
                description="Game over! The game has ended.",
                public=True,
            )
            self.emit_event("game_event", event)
            self.game_state.events.append(event)
            logger.info("Game over! The game has ended.")

            return

        # run until the next phase
        while (
            self.transcript["events"][self.stream_event_index]["type"] != "phase_change"
        ):
            self._add_game_event()

        self.game_state.current_phase = GamePhase.__members__[
            self.transcript["events"][self.stream_event_index]["phase"]
        ]
        self.game_state.current_round = self.transcript["events"][
            self.stream_event_index
        ]["round"]

        self._add_game_event()  # phase_change event


class DayDiscussionRecordController(PhaseController):
    """Controller for the day discussion phase."""

    def run(self):
        """Run the day discussion phase."""
        # Update agent memories
        self._update_agent_memories()

        # Run discussion rounds
        round_messages = filter(
            lambda m: (m["phase"] == "DAY_DISCUSSION")
            and (m["round"] == self.game_state.current_round),
            self.game_controller.transcript["messages"],
        )
        for msg in round_messages:
            message = Message(
                sender_name=msg["sender"],
                sender_id=msg["sender"],
                content=msg["content"],
                round_num=msg["round"],
                phase=GamePhase.DAY_DISCUSSION,
                public=True,
            )
            self.game_state.messages.append(message)
            self.emit_event("message", message)
            logger.info(f"{msg['sender']} says: {msg['content']}")

            # TODO: reactions


class DayVotingRecordController(PhaseController):
    """Controller for the day voting phase."""

    def run(self):
        """Run the day voting phase."""
        # Update agent memories
        self._update_agent_memories()

        # Run voting rounds
        round_votes = filter(
            lambda v: (v["phase"] == "DAY_VOTING")
            and (v["round"] == self.game_state.current_round),
            self.game_controller.transcript["votes"],
        )
        for vote in round_votes:
            vote_obj = Vote(
                voter_id=vote["voter"],
                target_id=vote["target"],
                round_num=vote["round"],
                phase=GamePhase.DAY_VOTING,
            )
            self.game_state.votes.append(vote_obj)
            self.emit_event("vote", vote_obj)
            logger.info(f"{vote['voter']} votes for {vote['target']}")


class NightMafiaDiscussionRecordController(PhaseController):
    """Controller for the night mafia discussion phase."""

    def run(self):
        """Run the night mafia discussion phase."""
        # Update agent memories
        self._update_agent_memories()

        # Run discussion rounds
        round_messages = filter(
            lambda m: (m["phase"] == "NIGHT_MAFIA_DISCUSSION")
            and (m["round"] == self.game_state.current_round),
            self.game_controller.transcript["messages"],
        )
        for msg in round_messages:
            message = Message(
                sender_name=msg["sender"],
                sender_id=msg["sender"],
                content=msg["content"],
                round_num=msg["round"],
                phase=GamePhase.NIGHT_MAFIA_DISCUSSION,
                public=False,
            )
            self.game_state.messages.append(message)
            self.emit_event("message", message)
            logger.info(f"[MAFIA] {msg['sender']} says: {msg['content']}")


class NightActionRecordController(PhaseController):
    """Controller for the night action phase."""

    def run(self):
        """Run the night action phase."""
        # Update agent memories
        self._update_agent_memories()

        # Run action rounds
        round_actions = filter(
            lambda a: (a["phase"] == "NIGHT_ACTION")
            and (a["round"] == self.game_state.current_round),
            self.game_controller.transcript["actions"],
        )
        for action in round_actions:
            action_obj = Action(
                actor_id=action["actor"],
                action_type=action["action"],
                target_id=action["target"],
                round_num=action["round"],
                phase=GamePhase.NIGHT_ACTION,
            )
            self.game_state.actions.append(action_obj)
            self.emit_event("action", action_obj)
            logger.info(
                f"{action['actor']} performs {action['action']} on {action['target']}"
            )
