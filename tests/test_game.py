"""
Unit tests for the Mafia game.
"""

import unittest
from unittest.mock import patch, MagicMock
import random

from src.models import (
    GamePhase, PlayerRole, PlayerStatus, TeamAlignment,
    Player, GameEvent, Vote, Action, Message, GameState
)
from src.agents import BaseAgent, OpenAIAgent, AnthropicAgent, GeminiAgent, create_agent
from src.controllers import (
    GameController, PhaseController, DayDiscussionController,
    DayVotingController, NightMafiaDiscussionController, NightActionController
)
from src.game import MafiaGame


class TestModels(unittest.TestCase):
    """Test cases for the game models."""
    
    def test_player_properties(self):
        """Test Player class properties."""
        # Create a villager
        villager = Player(
            id="player_1",
            name="Alice",
            role=PlayerRole.VILLAGER,
            status=PlayerStatus.ALIVE
        )
        
        # Create a mafia member
        mafia = Player(
            id="player_2",
            name="Bob",
            role=PlayerRole.MAFIA,
            status=PlayerStatus.ALIVE
        )
        
        # Test is_alive property
        self.assertTrue(villager.is_alive)
        
        villager.status = PlayerStatus.DEAD
        self.assertFalse(villager.is_alive)
        
        # Test team property
        self.assertEqual(villager.team, TeamAlignment.VILLAGE)
        self.assertEqual(mafia.team, TeamAlignment.MAFIA)
    
    def test_game_state_properties(self):
        """Test GameState class properties."""
        # Create players
        players = {
            "player_1": Player(id="player_1", name="Alice", role=PlayerRole.VILLAGER),
            "player_2": Player(id="player_2", name="Bob", role=PlayerRole.MAFIA),
            "player_3": Player(id="player_3", name="Charlie", role=PlayerRole.DOCTOR),
            "player_4": Player(id="player_4", name="Dave", role=PlayerRole.DETECTIVE),
            "player_5": Player(id="player_5", name="Eve", role=PlayerRole.GODFATHER),
        }
        
        # Create game state
        game_state = GameState(players=players)
        
        # Test alive_players property
        self.assertEqual(len(game_state.alive_players), 5)
        
        # Test dead_players property
        self.assertEqual(len(game_state.dead_players), 0)
        
        # Test mafia_players property
        self.assertEqual(len(game_state.mafia_players), 2)
        
        # Test village_players property
        self.assertEqual(len(game_state.village_players), 3)
        
        # Test alive_mafia_count property
        self.assertEqual(game_state.alive_mafia_count, 2)
        
        # Test alive_village_count property
        self.assertEqual(game_state.alive_village_count, 3)
        
        # Test check_game_over method
        self.assertFalse(game_state.check_game_over())
        
        # Kill all villagers
        for player_id in ["player_1", "player_3", "player_4"]:
            players[player_id].status = PlayerStatus.DEAD
        
        # Test check_game_over method again
        self.assertTrue(game_state.check_game_over())
        self.assertEqual(game_state.winning_team, TeamAlignment.MAFIA)
        
        # Reset game state
        game_state = GameState(players=players.copy())
        
        # Kill all mafia
        for player_id in ["player_2", "player_5"]:
            players[player_id].status = PlayerStatus.DEAD
        
        # Test check_game_over method again
        self.assertTrue(game_state.check_game_over())
        self.assertEqual(game_state.winning_team, TeamAlignment.VILLAGE)


class TestAgents(unittest.TestCase):
    """Test cases for the game agents."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Create a player
        self.player = Player(
            id="player_1",
            name="Alice",
            role=PlayerRole.VILLAGER,
            status=PlayerStatus.ALIVE
        )
        
        # Create agent config
        self.config = {
            "verbosity": "brief",
            "max_message_length": 100,
            "memory_limit": 5,
        }
    
    @patch('src.agents.OpenAIAgent.initialize_llm')
    def test_create_agent(self, mock_initialize_llm):
        """Test create_agent factory function."""
        # Mock initialize_llm to avoid actual API calls
        mock_initialize_llm.return_value = None
        
        # Test creating OpenAI agent
        agent = create_agent(self.player, "openai", self.config)
        self.assertIsInstance(agent, OpenAIAgent)
        
        # Test creating Anthropic agent
        agent = create_agent(self.player, "anthropic", self.config)
        self.assertIsInstance(agent, AnthropicAgent)
        
        # Test creating Google agent
        agent = create_agent(self.player, "google", self.config)
        self.assertIsInstance(agent, GeminiAgent)
        
        # Test invalid provider
        with self.assertRaises(ValueError):
            create_agent(self.player, "invalid", self.config)
    
    @patch('src.agents.OpenAIAgent.initialize_llm')
    def test_update_memory(self, mock_initialize_llm):
        """Test agent memory update."""
        # Mock initialize_llm to avoid actual API calls
        mock_initialize_llm.return_value = None
        
        # Create agent
        agent = OpenAIAgent(self.player, self.config)
        
        # Create game state
        players = {
            "player_1": self.player,
            "player_2": Player(id="player_2", name="Bob", role=PlayerRole.MAFIA),
        }
        game_state = GameState(players=players)
        
        # Add events to game state
        game_state.events.append(GameEvent(
            event_type="game_start",
            round_num=1,
            phase=GamePhase.DAY_DISCUSSION,
            description="The game has started.",
            public=True
        ))
        
        game_state.events.append(GameEvent(
            event_type="private_event",
            round_num=1,
            phase=GamePhase.DAY_DISCUSSION,
            description="This is a private event for player 1.",
            public=False,
            targets=["player_1"]
        ))
        
        # Add messages to game state
        game_state.messages.append(Message(
            sender_id="player_2",
            content="Hello everyone!",
            round_num=1,
            phase=GamePhase.DAY_DISCUSSION,
            public=True
        ))
        
        # Update agent memory
        agent.update_memory(game_state)
        
        # Check that memory was updated
        self.assertEqual(len(agent.player.memory), 3)
        
        # Check that memory contains the correct events
        event_types = [m.get("type") for m in agent.player.memory]
        self.assertIn("event", event_types)
        self.assertIn("message", event_types)
        
        # Check memory limit
        for _ in range(10):
            game_state.events.append(GameEvent(
                event_type=f"event_{_}",
                round_num=1,
                phase=GamePhase.DAY_DISCUSSION,
                description=f"Event {_}",
                public=True
            ))
        
        # Update agent memory again
        agent.update_memory(game_state)
        
        # Check that memory was limited
        self.assertEqual(len(agent.player.memory), agent.memory_limit)


class TestControllers(unittest.TestCase):
    """Test cases for the game controllers."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Create game config
        self.config = {
            "roles": {
                "Villager": 3,
                "Mafia": 2,
                "Doctor": 1,
                "Detective": 1,
                "Godfather": 1,
            },
            "phases": {
                "day": {
                    "discussion_rounds": 1,
                    "voting_time": 1,
                },
                "night": {
                    "mafia_discussion_rounds": 1,
                    "action_time": 1,
                }
            },
            "agent": {
                "verbosity": "brief",
                "max_message_length": 100,
                "memory_limit": 5,
            },
            "mechanics": {
                "godfather_appears_innocent": True,
                "reveal_role_on_death": True,
            }
        }
        
        # Create player names
        self.player_names = ["Alice", "Bob", "Charlie", "Dave", "Eve", "Frank", "Grace", "Heidi"]
        
        # Create game controller
        self.game_controller = GameController(self.config)
    
    @patch('src.agents.OpenAIAgent.initialize_llm')
    @patch('src.agents.OpenAIAgent.generate_response')
    def test_game_initialization(self, mock_generate_response, mock_initialize_llm):
        """Test game initialization."""
        # Mock initialize_llm and generate_response to avoid actual API calls
        mock_initialize_llm.return_value = None
        mock_generate_response.return_value = "Test response"
        
        # Initialize game
        game_state = self.game_controller.initialize_game(self.player_names)
        
        # Check that game state was created
        self.assertIsNotNone(game_state)
        
        # Check that players were created
        self.assertEqual(len(game_state.players), len(self.player_names))
        
        # Check that roles were assigned
        roles = [p.role for p in game_state.players.values()]
        self.assertEqual(roles.count(PlayerRole.VILLAGER), 3)
        self.assertEqual(roles.count(PlayerRole.MAFIA), 2)
        self.assertEqual(roles.count(PlayerRole.DOCTOR), 1)
        self.assertEqual(roles.count(PlayerRole.DETECTIVE), 1)
        self.assertEqual(roles.count(PlayerRole.GODFATHER), 1)
        
        # Check that agents were created
        self.assertEqual(len(self.game_controller.agents), len(self.player_names))
    
    @patch('src.agents.OpenAIAgent.initialize_llm')
    @patch('src.agents.OpenAIAgent.generate_response')
    @patch('src.agents.OpenAIAgent.generate_day_discussion')
    @patch('src.agents.OpenAIAgent.generate_day_vote')
    @patch('src.agents.OpenAIAgent.generate_night_action')
    @patch('src.agents.OpenAIAgent.react_to_message')
    def test_phase_controllers(self, mock_react, mock_night_action, mock_vote, 
                              mock_discussion, mock_response, mock_initialize_llm):
        """Test phase controllers."""
        # Mock methods to avoid actual API calls
        mock_initialize_llm.return_value = None
        mock_response.return_value = "Test response"
        mock_discussion.return_value = "I think we should investigate Bob."
        mock_vote.return_value = "player_2"  # Vote for Bob
        mock_night_action.return_value = Action(
            actor_id="player_1",
            action_type="protect",
            target_id="player_3",
            round_num=1,
            phase=GamePhase.NIGHT_ACTION
        )
        mock_react.return_value = "agree"
        
        # Initialize game
        self.game_controller.initialize_game(self.player_names)
        
        # Test day discussion controller
        day_discussion = DayDiscussionController(self.game_controller)
        day_discussion.run()
        
        # Check that messages were created
        self.assertGreater(len(self.game_controller.game_state.messages), 0)
        
        # Test day voting controller
        day_voting = DayVotingController(self.game_controller)
        day_voting.run()
        
        # Check that votes were created
        self.assertGreater(len(self.game_controller.game_state.votes), 0)
        
        # Check that a player was eliminated
        dead_players = [p for p in self.game_controller.game_state.players.values() 
                       if p.status == PlayerStatus.DEAD]
        self.assertEqual(len(dead_players), 1)
        
        # Test night mafia discussion controller
        night_mafia = NightMafiaDiscussionController(self.game_controller)
        night_mafia.run()
        
        # Test night action controller
        night_action = NightActionController(self.game_controller)
        night_action.run()
        
        # Check that actions were created
        self.assertGreater(len(self.game_controller.game_state.actions), 0)


class TestGame(unittest.TestCase):
    """Test cases for the main game class."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Create game config
        self.config = {
            "num_players": 8,
            "roles": {
                "Villager": 3,
                "Mafia": 2,
                "Doctor": 1,
                "Detective": 1,
                "Godfather": 1,
            },
            "phases": {
                "day": {
                    "discussion_rounds": 1,
                    "voting_time": 1,
                },
                "night": {
                    "mafia_discussion_rounds": 1,
                    "action_time": 1,
                }
            },
            "agent": {
                "verbosity": "brief",
                "max_message_length": 100,
                "memory_limit": 5,
            },
            "mechanics": {
                "godfather_appears_innocent": True,
                "reveal_role_on_death": True,
            }
        }
    
    @patch('src.controllers.GameController.initialize_game')
    def test_game_initialization(self, mock_initialize_game):
        """Test game initialization."""
        # Mock initialize_game to avoid actual API calls
        mock_initialize_game.return_value = GameState(players={})
        
        # Create game
        game = MafiaGame(self.config)
        
        # Initialize game
        game.initialize_game()
        
        # Check that game controller was created
        self.assertIsNotNone(game.game_controller)
        
        # Check that initialize_game was called
        mock_initialize_game.assert_called_once()
    
    @patch('src.controllers.GameController.initialize_game')
    @patch('src.controllers.GameController.run_game')
    def test_run_game(self, mock_run_game, mock_initialize_game):
        """Test running the game."""
        # Mock methods to avoid actual API calls
        mock_initialize_game.return_value = GameState(players={})
        mock_run_game.return_value = (True, TeamAlignment.VILLAGE)
        
        # Create game
        game = MafiaGame(self.config)
        
        # Initialize game
        game.initialize_game()
        
        # Run game
        game_over, winning_team = game.run_game()
        
        # Check that run_game was called
        mock_run_game.assert_called_once()
        
        # Check return values
        self.assertTrue(game_over)
        self.assertEqual(winning_team, TeamAlignment.VILLAGE)


if __name__ == '__main__':
    unittest.main()
