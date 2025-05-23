"""
Agent interface and implementations for the Mafia game.
"""

import os
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any, Tuple
import time
import random
import logging


from langchain.chains import LLMChain
from langchain.prompts import PromptTemplate
from langchain.schema import BaseMessage, HumanMessage, AIMessage, SystemMessage

from src.models import (
    Player,
    GameState,
    GamePhase,
    PlayerRole,
    Action,
    Message,
    GameEvent,
)

logger = logging.getLogger(__name__)

class BaseAgent(ABC):
    """Abstract base class for all player agents."""

    def __init__(self, player: Player, config: Dict[str, Any]):
        """
        Initialize the agent.

        Args:
            player: The player this agent controls
            config: Configuration settings for the agent
        """
        self.player = player
        self.config = config
        self.memory_limit = config.get("memory_limit", None)
        self.max_message_length = config.get("max_message_length", 200)
        self.verbosity = config.get("verbosity", "elaborate")
        self.llm = None  # Will be set by subclasses
        self.model_name = None  # Will be set by subclasses
        self.model_name = config.get("model", "unknown")  # Store model name
        self.saved_memory: List[GameEvent] = []  # To track saved events
        self.system_message = SystemMessage(self._create_system_prompt())

    @abstractmethod
    def initialize_llm(self):
        """Initialize the language model for this agent."""
        pass

    def generate_response(self, prompt: str) -> str:
        """Generate a response from the agent based on the prompt."""
        if not self.llm:
            self.initialize_llm()

        # Generate response
        response = self.llm.invoke([self.system_message, HumanMessage(prompt)])

        # DeepSeek Reason models:
        if "</think>" in response.content:
            inner_thought, content = response.content.split("</think>")
            content = content.strip()
            inner_thought = inner_thought.replace("<think>", "").strip()
        else:                
            inner_thought = ""
            content = response.content.strip()

        return content, inner_thought

    def _add_inner_thought(self, inner_thought: str, game_state: GameState):
        """
        Add inner thought to the player's memory.

        Args:
            inner_thought: The inner thought to add
            game_state: Current state of the game
        """
        if inner_thought:
            memory_entry = {
                "type": "inner_thought",
                "round": game_state.current_round,
                "phase": game_state.current_phase.name,
                "description": inner_thought,
            }
            self.player.memory.append(memory_entry)

    def update_memory(self, game_state: GameState):
        """
        Update the agent's memory with relevant game events.

        Args:
            game_state: Current state of the game
        """
        # Get events visible to this player
        visible_events = game_state.get_player_events(self.player.id)
        visible_messages = game_state.get_player_messages(self.player.id)

        # Update player's memory with new events
        new_memories = []
        for event in visible_events:
            if event not in self.saved_memory:
                memory_entry = {
                    "type": "event",
                    "round": event.round_num,
                    "phase": event.phase.name,
                    "description": event.description,
                }
                new_memories.append(memory_entry)
                self.saved_memory.append(event)

        # Add messages to memory
        for msg in visible_messages:
            if msg not in self.saved_memory:
                memory_entry = {
                    "type": "message",
                    "round": msg.round_num,
                    "phase": msg.phase.name,
                    "sender_name": msg.sender_name,
                    "sender_id": msg.sender_id,
                    "content": msg.content,
                    "public": msg.public,
                }
                new_memories.append(memory_entry)
                self.saved_memory.append(msg)

        # Update memory with new entries
        self.player.memory.extend(new_memories)

        # Trim memory to limit if needed
        if self.memory_limit and len(self.player.memory) > self.memory_limit:
            # Keep the most recent events
            self.player.memory = self.player.memory[-self.memory_limit :]

    def format_game_state_for_prompt(self, game_state: GameState) -> str:
        """
        Format the current game state into a string for the prompt.

        Args:
            game_state: Current state of the game

        Returns:
            Formatted game state as a string
        """
        alive_players = list(game_state.alive_players.values())
        dead_players = list(game_state.dead_players.values())

        state_str = f"Round {game_state.current_round}, Phase: {game_state.current_phase.name}\n\n"

        # Add alive players
        state_str += "Alive Players:\n"
        for p in alive_players:
            # Only include role information if known to this player
            if p.id == self.player.id:
                state_str += f"- {p.name} ({p.id}) (You, {p.role.name})\n"
            elif p.id in self.player.known_roles:
                state_str += f"- {p.name} ({p.id}) ({self.player.known_roles[p.id].name})\n"
            else:
                state_str += f"- {p.name} ({p.id})\n"

        # Add dead players with their roles (if reveal_role_on_death is enabled)
        if dead_players:
            state_str += "\nDead Players:\n"
            for p in dead_players:
                if p.id in self.player.known_roles:
                    state_str += f"- {p.name} ({self.player.known_roles[p.id].name})\n"
                else:
                    state_str += f"- {p.name}\n"

        return state_str

    def format_memory_for_prompt(self) -> str:
        """
        Format the agent's memory into a string for the prompt.

        Returns:
            Formatted memory as a string
        """
        if not self.player.memory:
            return "No events to remember yet."

        memory_str = "Your Memory:\n"
        for i, memory in enumerate(self.player.memory):
            if memory["type"] == "event":
                memory_str += f"{i+1}. Round {memory['round']}, {memory['phase']}: {memory['description']}\n"
            elif memory["type"] == "message":
                context = "publicly" if memory.get("public", True) else "privately"
                memory_str += f"{i+1}. Round {memory['round']}, {memory['phase']}: {memory['sender_name']} ({memory['sender_id']}) said {context}: \"{memory['content']}\"\n"

        return memory_str

    def generate_day_discussion(self, game_state: GameState) -> str:
        """
        Generate a discussion message during the day phase.

        Args:
            game_state: Current state of the game

        Returns:
            The agent's discussion message
        """
        prompt = self._create_day_discussion_prompt(game_state)
        response, inner_thought = self.generate_response(prompt)

        # Truncate response if needed
        if len(response) > self.max_message_length:
            response = response[: self.max_message_length] + "..."

        self._add_inner_thought(inner_thought, game_state)
        return response

    def generate_day_vote(self, game_state: GameState) -> str:
        """
        Generate a vote during the day phase.

        Args:
            game_state: Current state of the game

        Returns:
            The ID of the player to vote for
        """
        prompt = self._create_day_vote_prompt(game_state)
        response, inner_thought = self.generate_response(prompt)
        self._add_inner_thought(inner_thought, game_state)
        # Extract the player name or ID from the response
        # This is a simple implementation and might need more robust parsing
        for player_id, player in game_state.alive_players.items():
            if (
                player.name.lower() in response.lower()
                or player_id.lower() in response.lower()
            ) and player_id != self.player.id:
                return player_id

        logger.warning(
            f'[{self.model_name}] No valid player found in response: "{response}" from player: "{self.player.name}"'
        )
        return ""

    def generate_mafia_discussion(self, game_state: GameState) -> str:
        """
        Generate a discussion message during the night phase for Mafia players.
        Args:
            game_state: Current state of the game
        Returns:
            The agent's discussion message
        """
        prompt = self._create_mafia_discussion_prompt(game_state)
        response, inner_thought = self.generate_response(prompt)

        # Truncate response if needed
        if len(response) > self.max_message_length:
            response = response[: self.max_message_length] + "..."

        self._add_inner_thought(inner_thought, game_state)
        return response

    def generate_night_action(self, game_state: GameState) -> Optional[Action]:
        """
        Generate a night action based on the player's role.

        Args:
            game_state: Current state of the game

        Returns:
            An Action object representing the night action, or None if no action
        """
        if self.player.role == PlayerRole.VILLAGER:
            # Villagers have no night action
            return None

        prompt = self._create_night_action_prompt(game_state)
        response, inner_thought = self.generate_response(prompt)
        self._add_inner_thought(inner_thought, game_state)
        # Extract the target player from the response
        target_id = None
        for player_id, player in game_state.alive_players.items():
            if (
                player.name.lower() in response.lower()
                or player_id.lower() in response.lower()
            ) and player_id != self.player.id:
                target_id = player_id
                break

        if not target_id:
            logger.warning(
                f'[{self.model_name}] No valid target found in response: "{response}" from player: "{self.player.name}"'
            )
            return None

        # Create the appropriate action based on role
        action_type = ""
        if (
            self.player.role == PlayerRole.MAFIA
            or self.player.role == PlayerRole.GODFATHER
        ):
            action_type = "kill"
        elif self.player.role == PlayerRole.DOCTOR:
            action_type = "protect"
        elif self.player.role == PlayerRole.DETECTIVE:
            action_type = "investigate"

        return Action(
            actor_id=self.player.id,
            action_type=action_type,
            target_id=target_id,
            round_num=game_state.current_round,
            phase=GamePhase.NIGHT_ACTION,
        )

    def react_to_message(self, message: Message, game_state: GameState) -> str:
        """
        Generate a reaction to another player's message.

        Args:
            message: The message to react to
            game_state: Current state of the game

        Returns:
            A reaction string ("agree" or "disagree")
        """
        # Format the prompt for reaction
        prompt = self._create_reaction_prompt(message, game_state)

        # Generate reaction
        response, inner_thought = self.generate_response(prompt)
        self._add_inner_thought(inner_thought, game_state)

        # Parse the response to get just "agree" or "disagree"
        if "agree" in response.lower() and "disagree" not in response.lower():
            return "agree"
        elif "disagree" in response.lower():
            return "disagree"
        else:
            # Default to a neutral response if unclear
            return "neutral"

    def _create_system_prompt(self) -> str:
        """Create a system prompt for the agent."""
        nl = "\n"
        prompt = f"""You are an AI model called {self.player.name} ({self.player.id}). You are playing a Mafia (Werewolf) game with other AI models.
Your role is {self.player.role.name} and you are on the {self.player.team.name} team.
Your goal is to use your knowledge and reasoning to win the game for your team.
        
This game starts with these roles:
{self.config['roles']}

The game has the following players:
{nl.join([f'{p_id}: {p.name}' for p_id, p in self.config['players'].items()])}

Game Rules:
- Villagers win if all Mafia are eliminated.
- Mafia win if they outnumber or equal the Villagers.

Special Roles:
- Doctor (villager): Protects a player from being eliminated at night (includes self).
- Detective (villager): Investigates a player to check if they are Mafia.
- Godfather (Mafia): Appears as a Villager to the Detective. Has the final say in Mafia decisions.
Special roles can be used only once per round, starting from round 2.

Each round has two phases:
- Day (everyone talks and votes to eliminate someone)
- Night (Mafia secretly choose someone to eliminate and other roles may take actions)
(No voting and night actions in round 1)

Important notes:
- Pay attention to what others say. Look for inconsistencies or suspicious behavior.
- Speak in short, clear messages. Convince others, defend yourself, or sow confusion (if Mafia).
- You may lie or tell the truth — depending on your goal.
- Speak up with your own reasoning. Don’t just agree — challenge or question what others say.
- Use firm language: “I believe X is Mafia because…” or “That logic doesn’t make sense.”
- Don’t copy tone or repeat others. Try to add something new to the discussion with each point.
- Take attention to voting patterns and alliances. Who is working with whom?
- If you have no guess or clue, you can accuse someone and conclude based on their and others' reactions.
- Avoid complecated language.

You can also use the following format to have your inner thoughts before generating a response:
<think>
Your inner thoughts here
</think>
Everything inside <think> and </think> tags will be considered your inner thoughts and will not be shared with other players.
"""
        return prompt

    def _create_day_discussion_prompt(self, game_state: GameState) -> str:
        """Create a prompt for day discussion."""
        prompt = f"""
{self.format_game_state_for_prompt(game_state)}

{self.format_memory_for_prompt()}

It's now the day discussion phase. Based on your role and the information you have, 
what would you like to say to the group? 
Everything you say will be visible to all players, so do not include any extra information.

Your response should be limited to {self.max_message_length} characters.
"""
        return prompt

    def _create_day_vote_prompt(self, game_state: GameState) -> str:
        """Create a prompt for day voting."""
        prompt = f"""
{self.format_game_state_for_prompt(game_state)}

{self.format_memory_for_prompt()}


It's now time to vote for someone to eliminate. Based on your role and the information you have,
who do you think is most suspicious and should be eliminated?

If you're in the villagers team, try to vote for a Mafia member.
If you're in Mafia, try to vote for a Villager to protect yourself and your team, but be careful not to draw suspicion.

Your response should ONLY contain the name of the player you want to target. Do not include any other information or reasoning!
"""
        return prompt

    def _create_mafia_discussion_prompt(self, game_state: GameState) -> str:
        """Create a prompt for mafia discussion during the night phase."""
        prompt = f"""Mafia team members are: {', '.join(game_state.mafia_players_names)}.

{self.format_game_state_for_prompt(game_state)}

{self.format_memory_for_prompt()}

It's now the night phase, and you are with your Mafia teammates. This is a private discussion.
Based on your role and the information you have, what would you like to discuss with your team?

You should discuss your strategy for the night and the following days.
{
    "You should also decide on a target to eliminate during the night phase based on your strategy" if game_state.current_round > 1 else "No elimination takes place at this round."
}

Your response should be a message to your Mafia teammates, limited to {self.max_message_length} characters.
"""
        return prompt

    def _create_night_action_prompt(self, game_state: GameState) -> str:
        """Create a prompt for night actions."""
        action_description = ""
        if (
            self.player.role == PlayerRole.MAFIA
            or self.player.role == PlayerRole.GODFATHER
        ):
            action_description = "choose a player to eliminate"
        elif self.player.role == PlayerRole.DOCTOR:
            action_description = "choose a player to protect for the night"
        elif self.player.role == PlayerRole.DETECTIVE:
            action_description = "choose a player to investigate"
        else:
            raise ValueError(
                f"Invalid role for night action: {self.player.role.name}"
            )

        prompt = f"""
        
{self.format_game_state_for_prompt(game_state)}

{self.format_memory_for_prompt()}

It's now the night phase. Based on your role, you need to {action_description}.

Your response should ONLY contain the name of the player you want to target. Do not include any other information or reasoning!
"""
        return prompt

    def _create_reaction_prompt(self, message: Message, game_state: GameState) -> str:
        """
        Create a prompt for reacting to a message.

        Args:
            message: The message to react to
            game_state: Current state of the game

        Returns:
            A formatted prompt string
        """
        sender = game_state.players[message.sender_id].name

        prompt = f"""
{self.format_game_state_for_prompt(game_state)}

{self.format_memory_for_prompt()}

Player {sender} just said: "{message.content}"

Based on your role, knowledge, and strategy, do you agree or disagree with this statement?
Respond with either "agree" or "disagree" and a very brief explanation of your reasoning.
"""
        return prompt

    @abstractmethod
    def _get_monitoring_kwargs(self) -> Dict[str, Any]:
        """Get monitoring kwargs for the LLM."""
        pass


class RandomAgent(BaseAgent):
    """Debug agent for testing purposes."""

    def __init__(
        self, player: Player, config: Dict[str, Any], sleep_time: Optional[float] = 0.0
    ):
        """
        Initialize the random agent.

        Args:
            player: The player this agent controls
            config: Configuration settings for the agent
            sleep_time: Time to sleep before generating a response (for testing)
        """
        super().__init__(player, config)
        self.sleep_time = sleep_time

    def initialize_llm(self):
        """Initialize the language model (no-op for random agent)."""
        self.llm = None
        self.model_name = "random"

    def generate_response(self, prompt: str) -> str:
        """Generate a response (echo the prompt for random agent)."""
        time.sleep(self.sleep_time)
        return "Debug agent response", "Debug agent inner thought"

    def generate_day_vote(self, game_state: GameState) -> str:
        """Generate a random vote."""
        # return a random alive player that isn't self
        time.sleep(self.sleep_time)
        alive_players = [
            pid for pid in game_state.alive_players.keys() if pid != self.player.id
        ]
        if alive_players:
            return random.choice(alive_players)
        return ""

    def generate_night_action(self, game_state: GameState) -> Optional[Action]:
        """Generate a random night action."""
        if self.player.role == PlayerRole.VILLAGER:
            # Villagers have no night action
            return None

        time.sleep(self.sleep_time)

        alive_players = [
            pid for pid in game_state.alive_players.keys() if pid != self.player.id
        ]
        if alive_players:
            target_id = random.choice(alive_players)

            # Create the appropriate action based on role
            action_type = ""
            if (
                self.player.role == PlayerRole.MAFIA
                or self.player.role == PlayerRole.GODFATHER
            ):
                # make sure the target is not mafia
                if game_state.players[target_id].team == PlayerRole.MAFIA:
                    target_id = random.choice(
                        [
                            pid
                            for pid in alive_players
                            if game_state.players[pid].team != PlayerRole.MAFIA
                        ]
                    )
                action_type = "kill"
            elif self.player.role == PlayerRole.DOCTOR:
                action_type = "protect"
            elif self.player.role == PlayerRole.DETECTIVE:
                action_type = "investigate"

            return Action(
                actor_id=self.player.id,
                action_type=action_type,
                target_id=target_id,
                round_num=game_state.current_round,
                phase=GamePhase.NIGHT_ACTION,
            )
        return None

    def _get_monitoring_kwargs(self):
        return


class OpenAIAgent(BaseAgent):
    """Agent implementation using OpenAI's language models."""

    def initialize_llm(self):
        """Initialize the OpenAI language model."""
        from langchain_openai import ChatOpenAI

        model_name = self.config.get("model", "gpt-3.5-turbo")
        self.llm = ChatOpenAI(
            model_name=model_name, temperature=0.7, **self._get_monitoring_kwargs()
        )

    def _get_monitoring_kwargs(self) -> Dict[str, Any]:
        """Get monitoring kwargs for the LLM."""

        # Check if Helicone is enabled and set up the API key
        helicone_kwargs = {}
        if self.config.get("helicone", {}).get("enabled", False):
            helicone_api_key_env = self.config["helicone"].get("api_key_env", None)
            if helicone_api_key_env:
                helicone_api_key = os.getenv(helicone_api_key_env)
                if helicone_api_key:
                    helicone_kwargs = {
                        "openai_api_base": "https://oai.helicone.ai/v1",
                        "model_kwargs": {
                            "extra_headers": {
                                "Helicone-Auth": f"Bearer {helicone_api_key}",
                                "Helicone-Session-Id": self.config["game_id"],
                                "Helicone-User-Id": self.player.id,
                            }
                        },
                    }

        return helicone_kwargs


class AnthropicAgent(BaseAgent):
    """Agent implementation using Anthropic's Claude models."""

    def initialize_llm(self):
        """Initialize the Anthropic language model."""
        from langchain_anthropic import ChatAnthropic

        model_name = self.config.get("model", "claude-3-7-sonnet-latest")
        self.llm = ChatAnthropic(
            model_name=model_name, temperature=0.7, **self._get_monitoring_kwargs()
        )

    def _get_monitoring_kwargs(self) -> Dict[str, Any]:
        """Get monitoring kwargs for the LLM."""

        # Check if Helicone is enabled and set up the API key
        helicone_kwargs = {}
        if self.config.get("helicone", {}).get("enabled", False):
            helicone_api_key_env = self.config["helicone"].get("api_key_env", None)
            if helicone_api_key_env:
                helicone_api_key = os.getenv(helicone_api_key_env)
                if helicone_api_key:
                    helicone_kwargs = {
                        "anthropic_api_url": "https://anthropic.helicone.ai",
                        "model_kwargs": {
                            "extra_headers": {
                                "Helicone-Auth": f"Bearer {helicone_api_key}",
                                "Helicone-Session-Id": self.config["game_id"],
                                "Helicone-User-Id": self.player.id,
                            }
                        },
                    }

        return helicone_kwargs


class GeminiAgent(BaseAgent):
    """Agent implementation using Google's Gemini models."""

    def initialize_llm(self):
        """Initialize the Google Gemini language model."""
        from langchain_google_genai import ChatGoogleGenerativeAI

        model_name = self.config.get("model", "gemini-pro")
        self.llm = ChatGoogleGenerativeAI(
            model=model_name, temperature=0.7, **self._get_monitoring_kwargs()
        )

    def _get_monitoring_kwargs(self) -> Dict[str, Any]:
        """Get monitoring kwargs for the LLM."""
        # Check if Helicone is enabled and set up the API key
        helicone_kwargs = {}
        if self.config.get("helicone", {}).get("enabled", False):
            helicone_api_key_env = self.config["helicone"].get("api_key_env", None)
            if helicone_api_key_env:
                helicone_api_key = os.getenv(helicone_api_key_env)
                if helicone_api_key:
                    helicone_kwargs = {
                        "client_options": {
                            "api_endpoint": "https://gateway.helicone.ai"
                        },
                        "additional_headers": {
                            "helicone-auth": f"Bearer {helicone_api_key}",
                            "helicone-target-url": "https://generativelanguage.googleapis.com",
                            "Helicone-Session-Id": self.config["game_id"],
                            "Helicone-User-Id": self.player.id,
                        },
                        "transport": "rest",
                    }
        return helicone_kwargs


class OllamaAgent(BaseAgent):
    """Agent implementation using Ollama models."""

    def initialize_llm(self):
        """Initialize the Ollama language model."""
        from langchain_ollama import ChatOllama

        model_name = self.config.get(
            "model", "llama3"
        )  # Default to llama3 or allow config override
        self.llm = ChatOllama(
            model=model_name,
            base_url=self.config.get("base_url", "http://localhost:11434"),
            temperature=0.7,
            **self._get_monitoring_kwargs(),
        )

    def _get_monitoring_kwargs(self) -> Dict[str, Any]:
        """Get monitoring kwargs for the LLM."""
        # Ollama typically runs locally, so no Helicone monitoring implementation is added
        # This can be extended in the future if needed
        return {}


def create_agent(player: Player, provider: str, config: Dict[str, Any]) -> BaseAgent:
    """
    Factory function to create an agent based on the specified provider.

    Args:
        player: The player this agent controls
        provider: The LLM provider to use ('openai', 'anthropic', 'google', 'ollama', or 'random')
        config: Configuration settings for the agent

    Returns:
        An instance of a BaseAgent subclass
    """
    if provider.lower() == "openai":
        return OpenAIAgent(player, config)
    elif provider.lower() == "anthropic":
        return AnthropicAgent(player, config)
    elif provider.lower() == "google":
        return GeminiAgent(player, config)
    elif provider.lower() == "ollama":
        return OllamaAgent(player, config)
    elif provider.lower() in ("random", "debug"):
        return RandomAgent(player, config)
    else:
        raise ValueError(f"Unsupported provider: {provider}")
