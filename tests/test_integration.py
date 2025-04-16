"""
Integration tests for the Mafia game.
"""

import unittest
from unittest.mock import patch, MagicMock
import random
import json
import os
import logging

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


class TestGameSimulation(unittest.TestCase):
    """Integration tests for simulating a full game."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Disable logging for tests
        logging.disable(logging.CRITICAL)
        
        # Create game config for a smaller test game
        self.config = {
            "num_players": 5,
            "roles": {
                "Villager": 2,
                "Mafia": 1,
                "Doctor": 1,
                "Detective": 1,
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
                "max_message_length": 50,
                "memory_limit": 5,
            },
            "mechanics": {
                "godfather_appears_innocent": True,
                "reveal_role_on_death": True,
            }
        }
        
        # Create player names
        self.player_names = ["Alice", "Bob", "Charlie", "Dave", "Eve"]
        
        # Set random seed for reproducibility
        random.seed(42)
    
    def tearDown(self):
        """Clean up after tests."""
        # Re-enable logging
        logging.disable(logging.NOTSET)
    
    @patch('src.agents.OpenAIAgent.initialize_llm')
    @patch('src.agents.OpenAIAgent.generate_response')
    def test_full_game_simulation(self, mock_generate_response, mock_initialize_llm):
        """Test a full game simulation."""
        # Mock initialize_llm to avoid actual API calls
        mock_initialize_llm.return_value = None
        
        # Mock generate_response to provide deterministic responses
        def mock_response_generator(prompt):
            if "day discussion" in prompt.lower():
                return "I think we should be careful and observe everyone's behavior."
            elif "vote" in prompt.lower():
                # Return a random player name from the prompt
                for name in self.player_names:
                    if name.lower() in prompt.lower() and name != "You":
                        return name
                return self.player_names[0]
            elif "night action" in prompt.lower():
                # Return a random player name from the prompt
                for name in self.player_names:
                    if name.lower() in prompt.lower() and name != "You":
                        return name
                return self.player_names[0]
            elif "react" in prompt.lower():
                return "agree"
            else:
                return "I'm not sure what to do."
        
        mock_generate_response.side_effect = mock_response_generator
        
        # Create game
        game = MafiaGame(self.config)
        
        # Initialize game
        game.initialize_game(self.player_names)
        
        # Run game for a maximum of 10 rounds
        max_rounds = 10
        current_round = 0
        
        while not game.game_state.game_over and current_round < max_rounds:
            # Run one complete day-night cycle
            game.game_controller.run_phase()  # Day discussion
            game.game_controller.run_phase()  # Day voting
            game.game_controller.run_phase()  # Night mafia discussion
            game.game_controller.run_phase()  # Night action
            
            current_round += 1
        
        # Check that the game ended
        self.assertTrue(game.game_state.game_over or current_round == max_rounds)
        
        # If game ended naturally, check that a winning team was determined
        if game.game_state.game_over:
            self.assertIsNotNone(game.game_state.winning_team)
            
            # Check that the winning condition is valid
            if game.game_state.winning_team == TeamAlignment.MAFIA:
                self.assertGreaterEqual(game.game_state.alive_mafia_count, game.game_state.alive_village_count)
            else:
                self.assertEqual(game.game_state.alive_mafia_count, 0)
        
        # Check that events, messages, votes, and actions were created
        self.assertGreater(len(game.game_state.events), 0)
        self.assertGreater(len(game.game_state.messages), 0)
        self.assertGreater(len(game.game_state.votes), 0)
        
        # Test transcript saving
        transcript_file = game._save_transcript()
        self.assertTrue(os.path.exists(transcript_file))
        
        # Check transcript content
        with open(transcript_file, 'r') as f:
            transcript = json.load(f)
            
            self.assertIn("config", transcript)
            self.assertIn("players", transcript)
            self.assertIn("events", transcript)
            self.assertIn("messages", transcript)
            self.assertIn("votes", transcript)
            self.assertIn("actions", transcript)
            self.assertIn("result", transcript)
        
        # Clean up transcript file
        os.remove(transcript_file)


class TestScenarios(unittest.TestCase):
    """Tests for specific game scenarios."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Disable logging for tests
        logging.disable(logging.CRITICAL)
        
        # Set random seed for reproducibility
        random.seed(42)
    
    def tearDown(self):
        """Clean up after tests."""
        # Re-enable logging
        logging.disable(logging.NOTSET)
    
    @patch('src.agents.OpenAIAgent.initialize_llm')
    @patch('src.agents.OpenAIAgent.generate_response')
    def test_mafia_win_scenario(self, mock_generate_response, mock_initialize_llm):
        """Test a scenario where Mafia wins."""
        # Mock initialize_llm to avoid actual API calls
        mock_initialize_llm.return_value = None
        
        # Mock generate_response to provide deterministic responses
        mock_generate_response.return_value = "Test response"
        
        # Create a game state with 2 villagers and 2 mafia
        players = {
            "player_1": Player(id="player_1", name="Alice", role=PlayerRole.VILLAGER),
            "player_2": Player(id="player_2", name="Bob", role=PlayerRole.VILLAGER),
            "player_3": Player(id="player_3", name="Charlie", role=PlayerRole.MAFIA),
            "player_4": Player(id="player_4", name="Dave", role=PlayerRole.MAFIA),
        }
        
        game_state = GameState(
            players=players,
            current_round=1,
            current_phase=GamePhase.NIGHT_ACTION
        )
        
        # Create a game controller
        config = {
            "roles": {
                "Villager": 2,
                "Mafia": 2,
            },
            "mechanics": {
                "reveal_role_on_death": True,
            }
        }
        
        controller = GameController(config)
        controller.game_state = game_state
        
        # Mock the agents
        controller.agents = {
            player_id: MagicMock(spec=BaseAgent) for player_id in players
        }
        
        # Kill one villager
        night_action = NightActionController(controller)
        
        # Create a kill action
        action = Action(
            actor_id="player_3",
            action_type="kill",
            target_id="player_1",
            round_num=1,
            phase=GamePhase.NIGHT_ACTION
        )
        
        # Add action to game state
        game_state.actions.append(action)
        
        # Process the action
        night_action._process_night_actions({PlayerRole.MAFIA: action})
        
        # Check that the villager was killed
        self.assertEqual(players["player_1"].status, PlayerStatus.DEAD)
        
        # Check game over condition
        self.assertTrue(game_state.check_game_over())
        self.assertEqual(game_state.winning_team, TeamAlignment.MAFIA)
    
    @patch('src.agents.OpenAIAgent.initialize_llm')
    @patch('src.agents.OpenAIAgent.generate_response')
    def test_village_win_scenario(self, mock_generate_response, mock_initialize_llm):
        """Test a scenario where Village wins."""
        # Mock initialize_llm to avoid actual API calls
        mock_initialize_llm.return_value = None
        
        # Mock generate_response to provide deterministic responses
        mock_generate_response.return_value = "Test response"
        
        # Create a game state with 2 villagers and 1 mafia
        players = {
            "player_1": Player(id="player_1", name="Alice", role=PlayerRole.VILLAGER),
            "player_2": Player(id="player_2", name="Bob", role=PlayerRole.VILLAGER),
            "player_3": Player(id="player_3", name="Charlie", role=PlayerRole.MAFIA),
        }
        
        game_state = GameState(
            players=players,
            current_round=1,
            current_phase=GamePhase.DAY_VOTING
        )
        
        # Create a game controller
        config = {
            "roles": {
                "Villager": 2,
                "Mafia": 1,
            },
            "mechanics": {
                "reveal_role_on_death": True,
            }
        }
        
        controller = GameController(config)
        controller.game_state = game_state
        
        # Mock the agents
        controller.agents = {
            player_id: MagicMock(spec=BaseAgent) for player_id in players
        }
        
        # Create votes to eliminate the mafia
        for player_id in ["player_1", "player_2"]:
            vote = Vote(
                voter_id=player_id,
                target_id="player_3",
                round_num=1,
                phase=GamePhase.DAY_VOTING
            )
            game_state.votes.append(vote)
        
        # Run day voting
        day_voting = DayVotingController(controller)
        day_voting._run_voting_round()
        
        # Check that the mafia was eliminated
        self.assertEqual(players["player_3"].status, PlayerStatus.DEAD)
        
        # Check game over condition
        self.assertTrue(game_state.check_game_over())
        self.assertEqual(game_state.winning_team, TeamAlignment.VILLAGE)
    
    @patch('src.agents.OpenAIAgent.initialize_llm')
    @patch('src.agents.OpenAIAgent.generate_response')
    def test_doctor_protection_scenario(self, mock_generate_response, mock_initialize_llm):
        """Test a scenario where the Doctor protects a player from being killed."""
        # Mock initialize_llm to avoid actual API calls
        mock_initialize_llm.return_value = None
        
        # Mock generate_response to provide deterministic responses
        mock_generate_response.return_value = "Test response"
        
        # Create a game state with 1 villager, 1 doctor, and 1 mafia
        players = {
            "player_1": Player(id="player_1", name="Alice", role=PlayerRole.VILLAGER),
            "player_2": Player(id="player_2", name="Bob", role=PlayerRole.DOCTOR),
            "player_3": Player(id="player_3", name="Charlie", role=PlayerRole.MAFIA),
        }
        
        game_state = GameState(
            players=players,
            current_round=1,
            current_phase=GamePhase.NIGHT_ACTION
        )
        
        # Create a game controller
        config = {
            "roles": {
                "Villager": 1,
                "Doctor": 1,
                "Mafia": 1,
            },
            "mechanics": {
                "reveal_role_on_death": True,
            }
        }
        
        controller = GameController(config)
        controller.game_state = game_state
        
        # Mock the agents
        controller.agents = {
            player_id: MagicMock(spec=BaseAgent) for player_id in players
        }
        
        # Create actions
        kill_action = Action(
            actor_id="player_3",
            action_type="kill",
            target_id="player_1",
            round_num=1,
            phase=GamePhase.NIGHT_ACTION
        )
        
        protect_action = Action(
            actor_id="player_2",
            action_type="protect",
            target_id="player_1",
            round_num=1,
            phase=GamePhase.NIGHT_ACTION
        )
        
        # Add actions to game state
        game_state.actions.extend([kill_action, protect_action])
        
        # Process the actions
        night_action = NightActionController(controller)
        night_action._process_night_actions({
            PlayerRole.MAFIA: kill_action,
            PlayerRole.DOCTOR: protect_action
        })
        
        # Check that the villager was protected
        self.assertEqual(players["player_1"].status, PlayerStatus.ALIVE)
        
        # Check that the game is not over
        self.assertFalse(game_state.check_game_over())


if __name__ == '__main__':
    unittest.main()
