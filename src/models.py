"""
Core data models for the Mafia game.
"""

from enum import Enum, auto
from typing import Dict, List, Optional, Set, Union
from dataclasses import dataclass, field


class GamePhase(Enum):
    """Enum representing the different phases of the game."""
    DAY_DISCUSSION = auto()
    DAY_VOTING = auto()
    NIGHT_MAFIA_DISCUSSION = auto()
    NIGHT_ACTION = auto()


class PlayerRole(Enum):
    """Enum representing the different roles a player can have."""
    VILLAGER = auto()
    MAFIA = auto()
    DOCTOR = auto()
    DETECTIVE = auto()
    GODFATHER = auto()


class PlayerStatus(Enum):
    """Enum representing the different statuses a player can have."""
    ALIVE = auto()
    DEAD = auto()


class TeamAlignment(Enum):
    """Enum representing the team alignment of a role."""
    VILLAGE = auto()
    MAFIA = auto()


@dataclass
class Player:
    """Class representing a player in the game."""
    id: str
    name: str
    role: PlayerRole
    status: PlayerStatus = PlayerStatus.ALIVE
    protected: bool = False  # Whether the player is protected by the Doctor
    
    # Player's memory and knowledge
    memory: List[Dict] = field(default_factory=list)
    known_roles: Dict[str, PlayerRole] = field(default_factory=dict)
    
    @property
    def is_alive(self) -> bool:
        """Check if the player is alive."""
        return self.status == PlayerStatus.ALIVE
    
    @property
    def team(self) -> TeamAlignment:
        """Get the team alignment of the player."""
        if self.role in [PlayerRole.MAFIA, PlayerRole.GODFATHER]:
            return TeamAlignment.MAFIA
        return TeamAlignment.VILLAGE


@dataclass
class GameEvent:
    """Class representing an event that occurred during the game."""
    event_type: str
    round_num: int
    phase: GamePhase
    description: str
    public: bool  # Whether this event is visible to all players
    targets: List[str] = field(default_factory=list)  # Player IDs affected by this event


@dataclass
class Vote:
    """Class representing a vote cast by a player."""
    voter_id: str
    target_id: str
    round_num: int
    phase: GamePhase


@dataclass
class Action:
    """Class representing an action taken by a player."""
    actor_id: str
    action_type: str
    target_id: Optional[str]
    round_num: int
    phase: GamePhase
    success: bool = True


@dataclass
class Message:
    """Class representing a message sent by a player."""
    sender_name: str
    sender_id: str
    content: str
    round_num: int
    phase: GamePhase
    public: bool  # Whether this message is visible to all players
    recipients: List[str] = field(default_factory=list)  # Player IDs who can see this message if not public


@dataclass
class GameState:
    """Class representing the current state of the game."""
    players: Dict[str, Player]
    current_round: int = 1
    current_phase: GamePhase = GamePhase.DAY_DISCUSSION
    events: List[GameEvent] = field(default_factory=list)
    votes: List[Vote] = field(default_factory=list)
    actions: List[Action] = field(default_factory=list)
    messages: List[Message] = field(default_factory=list)
    game_over: bool = False
    winning_team: Optional[TeamAlignment] = None
    
    @property
    def alive_players(self) -> Dict[str, Player]:
        """Get all players who are still alive."""
        return {pid: player for pid, player in self.players.items() if player.is_alive}
    
    @property
    def dead_players(self) -> Dict[str, Player]:
        """Get all players who are dead."""
        return {pid: player for pid, player in self.players.items() if not player.is_alive}
    
    @property
    def mafia_players(self) -> Dict[str, Player]:
        """Get all mafia players (both alive and dead)."""
        return {pid: player for pid, player in self.players.items() 
                if player.team == TeamAlignment.MAFIA}
    
    @property
    def village_players(self) -> Dict[str, Player]:
        """Get all village players (both alive and dead)."""
        return {pid: player for pid, player in self.players.items() 
                if player.team == TeamAlignment.VILLAGE}
    
    @property
    def alive_mafia_count(self) -> int:
        """Get the number of mafia players who are still alive."""
        return sum(1 for player in self.players.values() 
                  if player.is_alive and player.team == TeamAlignment.MAFIA)
    
    @property
    def alive_village_count(self) -> int:
        """Get the number of village players who are still alive."""
        return sum(1 for player in self.players.values() 
                  if player.is_alive and player.team == TeamAlignment.VILLAGE)
    
    def check_game_over(self) -> bool:
        """Check if the game is over and determine the winning team."""
        if self.alive_mafia_count == 0:
            self.game_over = True
            self.winning_team = TeamAlignment.VILLAGE
            return True
        
        if self.alive_mafia_count >= self.alive_village_count:
            self.game_over = True
            self.winning_team = TeamAlignment.MAFIA
            return True
        
        return False
    
    def get_public_events(self) -> List[GameEvent]:
        """Get all public events."""
        return [event for event in self.events if event.public]
    
    def get_player_events(self, player_id: str) -> List[GameEvent]:
        """Get all events visible to a specific player."""
        return [event for event in self.events 
                if event.public or player_id in event.targets]
    
    def get_public_messages(self) -> List[Message]:
        """Get all public messages."""
        return [msg for msg in self.messages if msg.public]
    
    def get_player_messages(self, player_id: str) -> List[Message]:
        """Get all messages visible to a specific player."""
        return [msg for msg in self.messages 
                if msg.public or player_id in msg.recipients or msg.sender_id == player_id]
