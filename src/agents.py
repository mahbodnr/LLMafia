"""
Agent interface and implementations for the Mafia game.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any, Tuple
import json
import time

from langchain.chains import LLMChain
from langchain.prompts import PromptTemplate
from langchain.schema import BaseMessage, HumanMessage, AIMessage

from src.models import Player, GameState, GamePhase, PlayerRole, Action, Message


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
        self.chat_history: List[BaseMessage] = []
        self.saved_memory: List[GameEvent] = [] # To track saved events
    
    @abstractmethod
    def initialize_llm(self):
        """Initialize the language model for this agent."""
        pass
    
    @abstractmethod
    def generate_response(self, prompt: str) -> str:
        """Generate a response from the agent based on the prompt."""
        pass
    
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
                    "description": event.description
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
                    "public": msg.public
                }
                new_memories.append(memory_entry)
                self.saved_memory.append(msg)
        
        # Update memory with new entries
        self.player.memory.extend(new_memories)
        
        # Trim memory to limit if needed
        if self.memory_limit and len(self.player.memory) > self.memory_limit:
            # Keep the most recent events
            self.player.memory = self.player.memory[-self.memory_limit:]
    
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
                state_str += f"- {p.name} (You, {p.role.name})\n"
            elif p.id in self.player.known_roles:
                state_str += f"- {p.name} ({self.player.known_roles[p.id].name})\n"
            else:
                state_str += f"- {p.name}\n"
        
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
    
    @abstractmethod
    def generate_day_discussion(self, game_state: GameState) -> str:
        """
        Generate a discussion message during the day phase.
        
        Args:
            game_state: Current state of the game
            
        Returns:
            The agent's discussion message
        """
        pass
    
    @abstractmethod
    def generate_day_vote(self, game_state: GameState) -> str:
        """
        Generate a vote during the day phase.
        
        Args:
            game_state: Current state of the game
            
        Returns:
            The ID of the player to vote for
        """
        pass
    
    @abstractmethod
    def generate_night_action(self, game_state: GameState) -> Optional[Action]:
        """
        Generate a night action based on the player's role.
        
        Args:
            game_state: Current state of the game
            
        Returns:
            An Action object representing the night action, or None if no action
        """
        pass
    
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
        response = self.generate_response(prompt)
        
        # Parse the response to get just "agree" or "disagree"
        if "agree" in response.lower() and "disagree" not in response.lower():
            return "agree"
        elif "disagree" in response.lower():
            return "disagree"
        else:
            # Default to a neutral response if unclear
            return "neutral"
    
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
        
        prompt = f"""You are playing a Mafia/Werewolf game as a {self.player.role.name}.
        
{self.format_game_state_for_prompt(game_state)}

{self.format_memory_for_prompt()}

Player {sender} just said: "{message.content}"

Based on your role, knowledge, and strategy, do you agree or disagree with this statement?
Respond with either "agree" or "disagree" and a very brief explanation of your reasoning.
"""
        return prompt


class DebugAgent(BaseAgent):
    """Debug agent for testing purposes."""
    def __init__(self, player: Player, config: Dict[str, Any], sleep_time: Optional[float] = 0.0):
        """
        Initialize the debug agent.
        
        Args:
            player: The player this agent controls
            config: Configuration settings for the agent
            sleep_time: Time to sleep before generating a response (for testing)
        """
        super().__init__(player, config)
        self.sleep_time = sleep_time

    def initialize_llm(self):
        """Initialize the language model (no-op for debug agent)."""
        self.llm = None
        self.model_name = "debug"

    def generate_response(self, prompt: str) -> str:
        """Generate a response (echo the prompt for debug agent)."""
        time.sleep(self.sleep_time)
        return f"Debug agent response to prompt: >>{prompt}<<"
    
    def generate_day_discussion(self, game_state: GameState) -> str:
        """Generate a debug discussion message."""
        time.sleep(self.sleep_time)
        prompt = self._create_day_discussion_prompt(game_state)
        return f"Debug agent discussion: >>{prompt}<<"

    def generate_mafia_discussion(self, game_state: GameState) -> str:
        """Generate a debug discussion message."""
        time.sleep(self.sleep_time)
        prompt = self._create_day_discussion_prompt(game_state)
        return f"Debug agent discussion: >>{prompt}<<"
     
    def generate_day_vote(self, game_state: GameState) -> str:
        """Generate a debug vote."""
        # If no valid player found, return a random alive player that isn't self
        time.sleep(self.sleep_time)
        import random
        alive_players = [pid for pid in game_state.alive_players.keys() if pid != self.player.id]
        if alive_players:
            return random.choice(alive_players)
        return ""
    
    def generate_night_action(self, game_state: GameState) -> Optional[Action]:
        """Generate a debug night action."""
        if self.player.role == PlayerRole.VILLAGER:
            # Villagers have no night action
            return None
        
        # If no valid target found, choose randomly
        time.sleep(self.sleep_time)
        import random
        alive_players = [pid for pid in game_state.alive_players.keys() if pid != self.player.id]
        if alive_players:
            target_id = random.choice(alive_players)
            
            # Create the appropriate action based on role
            action_type = ""
            if self.player.role == PlayerRole.MAFIA or self.player.role == PlayerRole.GODFATHER:
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
                phase=GamePhase.NIGHT_ACTION
            )
        return None

    def _create_day_discussion_prompt(self, game_state: GameState) -> str:
        """Create a debug prompt for day discussion."""
        time.sleep(self.sleep_time)
        return "Debug agent discussion prompt."


class OpenAIAgent(BaseAgent):
    """Agent implementation using OpenAI's language models."""
    
    def initialize_llm(self):
        """Initialize the OpenAI language model."""
        from langchain_openai import ChatOpenAI

        
        model_name = self.config.get("model", "gpt-3.5-turbo")
        self.llm = ChatOpenAI(model_name=model_name, temperature=0.7)
    
    def generate_response(self, prompt: str) -> str:
        """Generate a response using the OpenAI language model."""
        if not self.llm:
            self.initialize_llm()
        
        # Add the prompt to chat history
        self.chat_history.append(HumanMessage(content=prompt))
        
        # Generate response
        response = self.llm.invoke(self.chat_history)
        
        # Add response to chat history
        self.chat_history.append(AIMessage(content=response.content))
        
        # Trim chat history if it gets too long
        if len(self.chat_history) > 10:
            self.chat_history = self.chat_history[-10:]
        
        # Truncate response if needed
        if len(response.content) > self.max_message_length:
            return response.content[:self.max_message_length] + "..."
        
        return response.content
    
    def generate_day_discussion(self, game_state: GameState) -> str:
        """Generate a discussion message during the day phase."""
        prompt = self._create_day_discussion_prompt(game_state)
        return self.generate_response(prompt)
    
    def generate_mafia_discussion(self, game_state: GameState) -> str:
        """Generate a discussion message during the mafia night phase."""
        prompt = self._create_mafia_discussion_prompt(game_state)
        return self.generate_response(prompt)
    
    def generate_day_vote(self, game_state: GameState) -> str:
        """Generate a vote during the day phase."""
        prompt = self._create_day_vote_prompt(game_state)
        response = self.generate_response(prompt)
        
        # Extract the player name or ID from the response
        # This is a simple implementation and might need more robust parsing
        for player_id, player in game_state.alive_players.items():
            if player.name.lower() in response.lower() and player_id != self.player.id:
                return player_id
        
        print(f"[Debug] No valid player found in response: {response}")

        return ""
    
        # # If no valid player found, return a random alive player that isn't self
        # import random
        # alive_players = [pid for pid in game_state.alive_players.keys() if pid != self.player.id]
        # if alive_players:
        #     return random.choice(alive_players)
        # return ""
    
    def generate_night_action(self, game_state: GameState) -> Optional[Action]:
        """Generate a night action based on the player's role."""
        if self.player.role == PlayerRole.VILLAGER:
            # Villagers have no night action
            return None
        
        prompt = self._create_night_action_prompt(game_state)
        response = self.generate_response(prompt)
        
        # Extract the target player from the response
        target_id = None
        for player_id, player in game_state.alive_players.items():
            if player.name.lower() in response.lower():
                target_id = player_id
                break
        
        if not target_id:
            print(f"[Debug] No valid target found in response: {response}")
            # If no valid target found, choose randomly
            # import random
            # alive_players = [pid for pid in game_state.alive_players.keys() if pid != self.player.id]
            # if alive_players:
            #     target_id = random.choice(alive_players)
        
        if not target_id:
            return None
        
        # Create the appropriate action based on role
        action_type = ""
        if self.player.role == PlayerRole.MAFIA or self.player.role == PlayerRole.GODFATHER:
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
            phase=GamePhase.NIGHT_ACTION
        )
    
    def _create_day_discussion_prompt(self, game_state: GameState) -> str:
        """Create a prompt for day discussion."""
        prompt = f"""You are playing a Mafia/Werewolf game as a {self.player.role.name}.

{self.format_game_state_for_prompt(game_state)}

{self.format_memory_for_prompt()}

It's now the day discussion phase. Based on your role and the information you have, 
what would you like to say to the group? Remember to stay in character and be strategic.

If you're a Villager, try to identify suspicious behavior.
If you're Mafia or Godfather, try to blend in and deflect suspicion.
If you're the Doctor, be careful about revealing your role.
If you're the Detective, consider whether to share your investigation results.

Your response should be a message to the group, limited to {self.max_message_length} characters.
"""
        return prompt
    
    def _create_day_vote_prompt(self, game_state: GameState) -> str:
        """Create a prompt for day voting."""
        prompt = f"""You are playing a Mafia/Werewolf game as a {self.player.role.name}.

{self.format_game_state_for_prompt(game_state)}

{self.format_memory_for_prompt()}

It's now time to vote for someone to eliminate. Based on your role and the information you have,
who do you think is most suspicious and should be eliminated?

If you're a Villager, Detective, or Doctor, try to vote for someone you suspect is Mafia.
If you're Mafia or Godfather, try to vote for a Villager to protect yourself and your team.

Your response should clearly indicate which player you're voting for by name.
"""
        return prompt
    

    def _create_mafia_discussion_prompt(self, game_state: GameState) -> str:
        """Create a prompt for mafia discussion during the night phase."""
        prompt = f"""You are playing a Mafia/Werewolf game as a {self.player.role.name}.

Mafia team members are: {', '.join([name for name, p in game_state.players.items() if p.team == PlayerRole.MAFIA])}.

{self.format_game_state_for_prompt(game_state)}

{self.format_memory_for_prompt()}

It's now the night phase, and you are with your Mafia teammates. This is a private discussion.
Based on your role and the information you have, what would you like to discuss with your team?
Your response should be a message to your Mafia teammates, limited to {self.max_message_length} characters.
"""
        return prompt

    def _create_night_action_prompt(self, game_state: GameState) -> str:
        """Create a prompt for night actions."""
        action_description = ""
        if self.player.role == PlayerRole.MAFIA or self.player.role == PlayerRole.GODFATHER:
            action_description = "choose a player to eliminate"
        elif self.player.role == PlayerRole.DOCTOR:
            action_description = "choose a player to protect for the night"
        elif self.player.role == PlayerRole.DETECTIVE:
            action_description = "choose a player to investigate"
        else:
            action_description = "observe the night (you have no special action)"
        
        prompt = f"""You are playing a Mafia/Werewolf game as a {self.player.role.name}.

{self.format_game_state_for_prompt(game_state)}

{self.format_memory_for_prompt()}

It's now the night phase. Based on your role, you need to {action_description}.

Your response should clearly indicate which player you're targeting by name.
"""
        return prompt


class AnthropicAgent(BaseAgent):
    """Agent implementation using Anthropic's Claude models."""
    
    def initialize_llm(self):
        """Initialize the Anthropic language model."""
        from langchain.chat_models import ChatAnthropic
        
        model_name = self.config.get("model", "claude-3-7-sonnet-latest")
        self.llm = ChatAnthropic(model_name=model_name, temperature=0.7)
    
    def generate_response(self, prompt: str) -> str:
        """Generate a response using the Anthropic language model."""
        if not self.llm:
            self.initialize_llm()
        
        # Add the prompt to chat history
        self.chat_history.append(HumanMessage(content=prompt))
        
        # Generate response
        response = self.llm.invoke(self.chat_history)
        
        # Add response to chat history
        self.chat_history.append(AIMessage(content=response.content))
        
        # Trim chat history if it gets too long
        if len(self.chat_history) > 10:
            self.chat_history = self.chat_history[-10:]
        
        # Truncate response if needed
        if len(response.content) > self.max_message_length:
            return response.content[:self.max_message_length] + "..."
        
        return response.content
    
    # The rest of the methods are identical to OpenAIAgent
    generate_day_discussion = OpenAIAgent.generate_day_discussion
    generate_mafia_discussion = OpenAIAgent.generate_mafia_discussion
    generate_day_vote = OpenAIAgent.generate_day_vote
    generate_night_action = OpenAIAgent.generate_night_action
    _create_day_discussion_prompt = OpenAIAgent._create_day_discussion_prompt
    _create_mafia_discussion_prompt = OpenAIAgent._create_mafia_discussion_prompt
    _create_day_vote_prompt = OpenAIAgent._create_day_vote_prompt
    _create_night_action_prompt = OpenAIAgent._create_night_action_prompt


class GeminiAgent(BaseAgent):
    """Agent implementation using Google's Gemini models."""
    
    def initialize_llm(self):
        """Initialize the Google Gemini language model."""
        from langchain_google_genai import ChatGoogleGenerativeAI
        
        model_name = self.config.get("model", "gemini-pro")
        self.llm = ChatGoogleGenerativeAI(model=model_name, temperature=0.7)
    
    def generate_response(self, prompt: str) -> str:
        """Generate a response using the Google Gemini language model."""
        if not self.llm:
            self.initialize_llm()
        
        # Add the prompt to chat history
        self.chat_history.append(HumanMessage(content=prompt))
        
        # Generate response
        response = self.llm.invoke(self.chat_history)
        
        # Add response to chat history
        self.chat_history.append(AIMessage(content=response.content))
        
        # Trim chat history if it gets too long
        if len(self.chat_history) > 10:
            self.chat_history = self.chat_history[-10:]
        
        # Truncate response if needed
        if len(response.content) > self.max_message_length:
            return response.content[:self.max_message_length] + "..."
        
        return response.content
    
    # The rest of the methods are identical to OpenAIAgent
    generate_day_discussion = OpenAIAgent.generate_day_discussion
    generate_mafia_discussion = OpenAIAgent.generate_mafia_discussion
    generate_day_vote = OpenAIAgent.generate_day_vote
    generate_night_action = OpenAIAgent.generate_night_action
    _create_day_discussion_prompt = OpenAIAgent._create_day_discussion_prompt
    _create_mafia_discussion_prompt = OpenAIAgent._create_mafia_discussion_prompt
    _create_day_vote_prompt = OpenAIAgent._create_day_vote_prompt
    _create_night_action_prompt = OpenAIAgent._create_night_action_prompt


def create_agent(player: Player, provider: str, config: Dict[str, Any]) -> BaseAgent:
    """
    Factory function to create an agent based on the specified provider.
    
    Args:
        player: The player this agent controls
        provider: The LLM provider to use ('openai', 'anthropic', or 'google')
        config: Configuration settings for the agent
        
    Returns:
        An instance of a BaseAgent subclass
    """
    if provider.lower() == 'openai':
        return OpenAIAgent(player, config)
    elif provider.lower() == 'anthropic':
        return AnthropicAgent(player, config)
    elif provider.lower() == 'google':
        return GeminiAgent(player, config)
    elif provider.lower() == 'debug':
        return DebugAgent(player, config)
    else:
        raise ValueError(f"Unsupported provider: {provider}")
