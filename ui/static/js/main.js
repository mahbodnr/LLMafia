// Main JavaScript for the Mafia Game UI

// Socket.io connection
let socket;

// Game state
let gameState = {
    started: false,
    phase: 'not_started',
    round: 0,
    time: 'day',
    players: [],
    messages: [],
    events: [],
    currentSpeaker: null,
    waitingForContinue: false,
    waitingForMessages: false
};

// DOM Elements
const gamePhaseElement = document.getElementById('game-phase');
const gameRoundElement = document.getElementById('game-round');
const gameTimeElement = document.getElementById('game-time');
const startGameButton = document.getElementById('start-game');
const nextPhaseButton = document.getElementById('next-phase');
const resetGameButton = document.getElementById('reset-game');
const playersContainer = document.getElementById('players-container');
const chatMessages = document.getElementById('chat-messages');
const gameLog = document.getElementById('game-log');
const currentSpeakerName = document.getElementById('current-speaker-name');
const currentSpeakerMessage = document.getElementById('current-speaker-message');
const continueButton = document.getElementById('continue-button');
const centerDisplay = document.getElementById('center-display');

// Game settings elements
const playerCountSelect = document.getElementById('player-count');
const mafiaCountSelect = document.getElementById('mafia-count');
const includeDoctorCheckbox = document.getElementById('include-doctor');
const includeDetectiveCheckbox = document.getElementById('include-detective');
const includeGodfatherCheckbox = document.getElementById('include-godfather');
const discussionRoundsSelect = document.getElementById('discussion-rounds');
const verboseModeCheckbox = document.getElementById('verbose-mode');

// Game results modal elements
const gameResultsModal = new bootstrap.Modal(document.getElementById('game-results-modal'));
const winningTeamElement = document.getElementById('winning-team');
const villagePlayers = document.getElementById('village-players');
const mafiaPlayers = document.getElementById('mafia-players');
const totalRoundsElement = document.getElementById('total-rounds');
const totalMessagesElement = document.getElementById('total-messages');
const totalVotesElement = document.getElementById('total-votes');
const downloadTranscriptButton = document.getElementById('download-transcript');
const newGameButton = document.getElementById('new-game');

// Player memory modal elements
const playerMemoryModal = new bootstrap.Modal(document.getElementById('player-memory-modal'));
const memoryPlayerName = document.getElementById('memory-player-name');
const memoryPlayerRole = document.getElementById('memory-player-role');
const memoryPlayerTeam = document.getElementById('memory-player-team');
const memoryPlayerStatus = document.getElementById('memory-player-status');
const memoryLoading = document.getElementById('memory-loading');
const memoryContent = document.getElementById('memory-content');

// Initialize the UI
document.addEventListener('DOMContentLoaded', () => {
    initializeSocket();
    setupEventListeners();
    console.log("UI initialized");
});

// Initialize Socket.io connection
function initializeSocket() {
    socket = io();

    // Socket event listeners
    socket.on('connect', () => {
        addLogEntry('Connected to server', 'success');
        console.log("Socket connected");
    });

    socket.on('disconnect', () => {
        addLogEntry('Disconnected from server', 'error');
        console.log("Socket disconnected");
    });

    socket.on('game_state', (state) => {
        console.log("Received game state:", state);
        updateGameState(state);
    });

    socket.on('game_event', (event) => {
        console.log("Received game event:", event);
        handleGameEvent(event);
    });

    socket.on('chat_message', (message) => {
        console.log("Received chat message:", message);
        addChatMessage(message);
    });

    socket.on('game_over', (result) => {
        console.log("Received game over:", result);
        showGameResults(result);
    });

    socket.on('vote', (vote) => {
        console.log("Received vote:", vote);
        drawVoteArrow(vote.voter_id, vote.target_id);
        addLogEntry(`${getPlayerNameById(vote.voter_id)} voted for ${getPlayerNameById(vote.target_id)}`, 'warning');
    });

    socket.on('next_speaker', (data) => {
        console.log("Received next speaker:", data);
        if (data.speaker_id) {
            // Make sure we update the UI immediately
            updateCurrentSpeaker(data.speaker_id, data.player_name, data.message);
            
            // Show center display explicitly
            centerDisplay.style.display = 'flex';
            currentSpeakerName.textContent = data.player_name;
            currentSpeakerMessage.textContent = data.message;
            continueButton.disabled = false;
            nextPhaseButton.disabled = true;
        } else {
            // No more speakers, enable next phase button
            nextPhaseButton.disabled = false;
            currentSpeakerName.textContent = 'None';
            currentSpeakerMessage.textContent = 'All players have spoken for this phase.';
            continueButton.disabled = true;
        }
    });

    socket.on('center_display', (data) => {
        console.log("Received center display update:", data);
        if (data.active) {
            // Force update UI regardless of previous state
            centerDisplay.style.display = 'flex';
            currentSpeakerName.textContent = data.player_name || 'Speaker';
            currentSpeakerMessage.textContent = data.message || 'No message';
            continueButton.disabled = false;
            nextPhaseButton.disabled = true;
        } else {
            // Hide center display
            centerDisplay.style.display = 'none';
            continueButton.disabled = true;
            nextPhaseButton.disabled = false;
        }
    });

    socket.on('player_reaction', (data) => {
        console.log("Received player reaction:", data);
        handlePlayerReaction(data.player_id, data.target_id, data.reaction_type);
    });

    socket.on('player_memory', (data) => {
        console.log("Received player memory:", data);
        displayPlayerMemory(data);
    });

    socket.on('waiting_for_messages', (data) => {
        console.log("Waiting for more messages:", data);
        gameState.waitingForMessages = data.active;
        
        if (data.active) {
            // Show waiting indicator and enable message check button
            showWaitingIndicator();
        } else {
            // Hide waiting indicator
            hideWaitingIndicator();
            nextPhaseButton.disabled = false;
        }
    });
}

// Set up event listeners for UI elements
function setupEventListeners() {
    startGameButton.addEventListener('click', startGame);
    nextPhaseButton.addEventListener('click', nextPhase);
    resetGameButton.addEventListener('click', resetGame);
    downloadTranscriptButton.addEventListener('click', downloadTranscript);
    newGameButton.addEventListener('click', () => {
        gameResultsModal.hide();
        resetGame();
    });
    
    // Add continue button event listener
    continueButton.addEventListener('click', continueAfterSpeaker);

    // Update mafia count options when player count changes
    playerCountSelect.addEventListener('change', updateMafiaCountOptions);
    updateMafiaCountOptions();
}

// Update mafia count options based on player count
function updateMafiaCountOptions() {
    const playerCount = parseInt(playerCountSelect.value);
    const mafiaCount = mafiaCountSelect.value;
    
    // Clear existing options
    mafiaCountSelect.innerHTML = '';
    
    // Add new options (max mafia is playerCount / 3, rounded up)
    const maxMafia = Math.min(Math.ceil(playerCount / 3), 4);
    for (let i = 1; i <= maxMafia; i++) {
        const option = document.createElement('option');
        option.value = i;
        option.textContent = `${i} Mafia`;
        mafiaCountSelect.appendChild(option);
    }
    
    // Try to keep the previous selection if possible
    if (mafiaCount <= maxMafia) {
        mafiaCountSelect.value = mafiaCount;
    }
}

// Start a new game
function startGame() {
    // Get game settings
    const settings = {
        playerCount: parseInt(playerCountSelect.value),
        mafiaCount: parseInt(mafiaCountSelect.value),
        includeDoctor: includeDoctorCheckbox.checked,
        includeDetective: includeDetectiveCheckbox.checked,
        includeGodfather: includeGodfatherCheckbox.checked,
        discussionRounds: parseInt(discussionRoundsSelect.value),
        verboseMode: verboseModeCheckbox.checked
    };
    
    console.log("Starting game with settings:", settings);
    
    // Send start game request to server
    socket.emit('start_game', settings);
    
    // Update UI
    startGameButton.disabled = true;
    nextPhaseButton.disabled = false;
    resetGameButton.disabled = false;
    
    // Disable settings
    playerCountSelect.disabled = true;
    mafiaCountSelect.disabled = true;
    includeDoctorCheckbox.disabled = true;
    includeDetectiveCheckbox.disabled = true;
    includeGodfatherCheckbox.disabled = true;
    discussionRoundsSelect.disabled = true;
    verboseModeCheckbox.disabled = true;
    
    addLogEntry('Starting new game...', 'info');
}

// Move to the next game phase
function nextPhase() {
    console.log("Moving to next phase");
    socket.emit('next_phase');
}

// Reset the game
function resetGame() {
    socket.emit('reset_game');
    
    // Reset UI
    startGameButton.disabled = false;
    nextPhaseButton.disabled = true;
    resetGameButton.disabled = true;
    
    // Enable settings
    playerCountSelect.disabled = false;
    mafiaCountSelect.disabled = false;
    includeDoctorCheckbox.disabled = false;
    includeDetectiveCheckbox.disabled = false;
    includeGodfatherCheckbox.disabled = false;
    discussionRoundsSelect.disabled = false;
    verboseModeCheckbox.disabled = false;
    
    // Reset game state
    gameState = {
        started: false,
        phase: 'not_started',
        round: 0,
        time: 'day',
        players: [],
        messages: [],
        events: [],
        currentSpeaker: null,
        waitingForContinue: false,
        waitingForMessages: false
    };
    
    // Reset UI elements
    gamePhaseElement.querySelector('span').textContent = 'Not Started';
    gameRoundElement.querySelector('span').textContent = '0';
    gameTimeElement.querySelector('span').textContent = 'Day';
    playersContainer.innerHTML = '';
    chatMessages.innerHTML = '';
    gameLog.innerHTML = '';
    currentSpeakerName.textContent = 'None';
    currentSpeakerMessage.textContent = 'Waiting for the game to start...';
    continueButton.disabled = true;
    
    addLogEntry('Game reset', 'info');
}

// Update the game state
function updateGameState(state) {
    gameState = {...gameState, ...state};
    
    // Update UI elements
    gamePhaseElement.querySelector('span').textContent = formatPhase(state.phase);
    gameRoundElement.querySelector('span').textContent = state.round;
    gameTimeElement.querySelector('span').textContent = state.time === 'day' ? 'Day' : 'Night';
    
    // Update player display
    updatePlayers(state.players);
    
    // Update day/night cycle
    updateDayNightCycle(state.time);
}

// Format phase name for display
function formatPhase(phase) {
    return phase.split('_').map(word => word.charAt(0).toUpperCase() + word.slice(1)).join(' ');
}

// Update player display
function updatePlayers(players) {
    playersContainer.innerHTML = '';
    
    const centerX = playersContainer.offsetWidth / 2;
    const centerY = playersContainer.offsetHeight / 2;
    const radius = Math.min(centerX, centerY) * 0.8;
    
    players.forEach((player, index) => {
        const angle = (index / players.length) * 2 * Math.PI;
        const x = centerX + radius * Math.cos(angle);
        const y = centerY + radius * Math.sin(angle);
        
        const playerElement = document.createElement('div');
        playerElement.className = `player-avatar ${player.status.toLowerCase()} ${player.role ? player.role.toLowerCase() : 'unknown'}`;
        playerElement.setAttribute('data-player-id', player.id);
        playerElement.style.left = `${x}px`;
        playerElement.style.top = `${y}px`;
        
        // Add icon based on role (if known)
        let iconClass = 'fa-user';
        if (player.role) {
            switch (player.role.toLowerCase()) {
                case 'villager':
                    iconClass = 'fa-person';
                    break;
                case 'mafia':
                    iconClass = 'fa-user-ninja';
                    break;
                case 'doctor':
                    iconClass = 'fa-user-md';
                    break;
                case 'detective':
                    iconClass = 'fa-user-secret';
                    break;
                case 'godfather':
                    iconClass = 'fa-crown';
                    break;
            }
        }
        
        playerElement.innerHTML = `
            <div class="player-icon">
                <i class="fas ${iconClass}"></i>
            </div>
            <div class="player-name">${player.name}</div>
        `;
        
        // Add tooltip with player info
        playerElement.setAttribute('data-bs-toggle', 'tooltip');
        playerElement.setAttribute('data-bs-placement', 'top');
        playerElement.setAttribute('title', `${player.name} (${player.status}${player.role ? ` - ${player.role}` : ''})`);
        
        // Add click event to show player details
        playerElement.addEventListener('click', () => {
            showPlayerDetails(player);
        });
        
        playersContainer.appendChild(playerElement);
    });
    
    // Initialize tooltips
    const tooltips = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltips.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
}

// Show player details
function showPlayerDetails(player) {
    console.log('Showing player details:', player);
    
    // Set player information in the modal
    memoryPlayerName.textContent = player.name;
    
    // Style badges according to player status
    memoryPlayerRole.textContent = player.role || 'Unknown';
    memoryPlayerRole.className = `badge rounded-pill bg-${getRoleBadgeColor(player.role)}`;
    
    memoryPlayerTeam.textContent = player.team || 'Unknown';
    memoryPlayerTeam.className = `badge rounded-pill bg-${player.team === 'Village' ? 'success' : 'danger'}`;
    
    memoryPlayerStatus.textContent = player.status;
    memoryPlayerStatus.className = `badge rounded-pill bg-${player.status === 'Alive' ? 'success' : 'danger'}`;
    
    // Show loading indicator
    memoryLoading.style.display = 'block';
    memoryContent.innerHTML = '';
    
    // Show the modal
    playerMemoryModal.show();
    
    // Request player memory from the server
    socket.emit('get_player_memory', player.id);
}

// Get appropriate badge color for role
function getRoleBadgeColor(role) {
    if (!role) return 'secondary';
    
    switch (role.toLowerCase()) {
        case 'mafia':
            return 'danger';
        case 'villager':
            return 'success';
        case 'doctor':
            return 'info';
        case 'detective':
            return 'primary';
        case 'godfather':
            return 'dark';
        default:
            return 'secondary';
    }
}

// Display player memory
function displayPlayerMemory(data) {
    // Hide loading indicator
    memoryLoading.style.display = 'none';
    
    // If no memory entries, show a message
    if (!data.memory || data.memory.length === 0) {
        memoryContent.innerHTML = '<div class="alert alert-info">This player has no memory entries.</div>';
        return;
    }
    
    // Create memory timeline
    let html = '<div class="memory-timeline">';
    
    data.memory.forEach(entry => {
        // Check if it's an event or message type
        if (entry.type === "event") {
            html += createEventMemoryEntry(entry);
        } else if (entry.type === "message") {
            html += createMessageMemoryEntry(entry, data.name);
        } else {
            // Fallback for unknown types
            html += createEventMemoryEntry({
                round: entry.round,
                phase: entry.phase,
                description: "Unknown memory entry type"
            });
        }
    });
    
    html += '</div>';
    memoryContent.innerHTML = html;
}

// Create HTML for an event memory entry
function createEventMemoryEntry(entry) {
    return `
        <div class="memory-entry memory-event fade-in">
            <div class="memory-entry-header">
                <span class="memory-round">Round ${entry.round}</span>
                <span class="memory-phase">${entry.phase}</span>
                <span class="memory-type-badge event-badge">Event</span>
            </div>
            <div class="memory-entry-content">${entry.description}</div>
        </div>
    `;
}

// Create HTML for a message memory entry
function createMessageMemoryEntry(entry, playerName) {
    // Determine if the message is from the player or someone else
    const isPlayerMessage = entry.sender === playerName;
    const messageClass = isPlayerMessage ? 'my-message' : 'other-message';
    const publicPrivate = entry.public ? 'Public' : 'Private';
    
    return `
        <div class="memory-entry memory-message ${messageClass} fade-in">
            <div class="memory-entry-header">
                <span class="memory-round">Round ${entry.round}</span>
                <span class="memory-phase">${entry.phase}</span>
                <span class="memory-type-badge message-badge ${entry.public ? 'public-message' : 'private-message'}">${publicPrivate}</span>
            </div>
            <div class="message-details">
                <div class="message-sender">${entry.sender}</div>
                <div class="memory-entry-content">${entry.content}</div>
            </div>
        </div>
    `;
}

// Update day/night cycle with visibility adjustments
function updateDayNightCycle(time) {
    const body = document.body;
    
    if (time === 'night' && !body.classList.contains('night-mode')) {
        body.classList.remove('day-mode');
        body.classList.add('night-mode', 'day-to-night');
        setTimeout(() => {
            body.classList.remove('day-to-night');
        }, 2000);
        
        // Adjust visibility for night phase
        adjustVisibilityForNight();
    } else if (time === 'day' && !body.classList.contains('day-mode')) {
        body.classList.remove('night-mode');
        body.classList.add('day-mode', 'night-to-day');
        setTimeout(() => {
            body.classList.remove('night-to-day');
        }, 2000);
        
        // Restore visibility for day phase
        restoreVisibilityForDay();
    }
}

// Adjust visibility for night phase
function adjustVisibilityForNight() {
    // Hide public messages during night phase
    const publicMessages = document.querySelectorAll('.chat-message.public');
    publicMessages.forEach(msg => {
        msg.classList.add('night-hidden');
    });
    
    // Hide certain UI elements during night phase
    if (!gameState.players.some(p => p.id === gameState.currentSpeaker && p.team === 'Mafia')) {
        // If current speaker is not Mafia, hide Mafia messages
        const mafiaMessages = document.querySelectorAll('.chat-message.mafia');
        mafiaMessages.forEach(msg => {
            msg.classList.add('night-hidden');
        });
    }
    
    // Add night mode class to center display
    centerDisplay.classList.add('night-mode');
}

// Restore visibility for day phase
function restoreVisibilityForDay() {
    // Show all messages during day phase
    const hiddenMessages = document.querySelectorAll('.chat-message.night-hidden');
    hiddenMessages.forEach(msg => {
        msg.classList.remove('night-hidden');
    });
    
    // Remove night mode class from center display
    centerDisplay.classList.remove('night-mode');
}

// Handle game events
function handleGameEvent(event) {
    // Add to game events
    gameState.events.push(event);
    
    // Add to log
    addLogEntry(event.description, getEventLogType(event.event_type));
}

// Get log entry type based on event type
function getEventLogType(eventType) {
    switch (eventType) {
        case 'game_start':
        case 'new_round':
        case 'phase_change':
            return 'info';
        case 'elimination':
        case 'night_elimination':
        case 'kill_success':
            return 'error';
        case 'protection':
        case 'investigation':
            return 'warning';
        case 'game_over':
            return 'success';
        default:
            return 'info';
    }
}

// Add chat message
function addChatMessage(message) {
    // Add to messages
    gameState.messages.push(message);
    
    console.log(`Adding chat message from ${message.sender_name}: ${message.content.substring(0, 30)}...`);
    
    // Create message element
    const messageElement = document.createElement('div');
    messageElement.className = `chat-message ${message.public ? 'public' : 'mafia'} fade-in`;
    
    // Format timestamp
    const timestamp = new Date(message.timestamp).toLocaleTimeString();
    
    messageElement.innerHTML = `
        <div class="message-sender">${message.sender_name}</div>
        <div class="message-time">${timestamp}</div>
        <div class="message-content">${message.content}</div>
    `;
    
    chatMessages.appendChild(messageElement);
    
    // Scroll to bottom
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

// Update current speaker display
function updateCurrentSpeaker(speakerId, speakerName, message) {
    console.log(`Updating current speaker: ${speakerName}`);
    
    // Update game state
    gameState.currentSpeaker = speakerId;
    gameState.waitingForContinue = true;
    
    // Highlight the current speaker's avatar
    highlightCurrentSpeaker(speakerId);
}

// Highlight current speaker
function highlightCurrentSpeaker(speakerId) {
    // Remove highlight from all players
    const playerAvatars = document.querySelectorAll('.player-avatar');
    playerAvatars.forEach(avatar => {
        avatar.classList.remove('pulse');
        // Also remove any existing reactions
        const existingReaction = avatar.querySelector('.reaction');
        if (existingReaction) {
            avatar.removeChild(existingReaction);
        }
    });
    
    // Find the current speaker's avatar
    const speakerAvatar = document.querySelector(`.player-avatar[data-player-id="${speakerId}"]`);
    if (speakerAvatar) {
        // Add pulse animation to highlight
        speakerAvatar.classList.add('pulse');
    }
}

// Add reaction to a player
function addReactionToPlayer(playerId, reactionType) {
    const playerAvatar = document.querySelector(`.player-avatar[data-player-id="${playerId}"]`);
    if (!playerAvatar) return;
    
    // Remove any existing reaction
    const existingReaction = playerAvatar.querySelector('.reaction');
    if (existingReaction) {
        playerAvatar.removeChild(existingReaction);
    }
    
    // Create reaction element
    const reactionElement = document.createElement('div');
    reactionElement.className = `reaction ${reactionType}`;
    
    // Add appropriate emoji
    let emoji = '';
    switch (reactionType) {
        case 'agree':
            emoji = '👍';
            break;
        case 'disagree':
            emoji = '👎';
            break;
        case 'neutral':
            emoji = '😐';
            break;
    }
    
    reactionElement.textContent = emoji;
    playerAvatar.appendChild(reactionElement);
    
    // Remove reaction after 5 seconds
    setTimeout(() => {
        if (playerAvatar.contains(reactionElement)) {
            playerAvatar.removeChild(reactionElement);
        }
    }, 5000);
}

// Handle player reaction to a message
function handlePlayerReaction(reactingPlayerId, targetPlayerId, reactionType) {
    // Add reaction to the player's avatar
    addReactionToPlayer(reactingPlayerId, reactionType);
    
    // Log the reaction
    const reactingPlayer = gameState.players.find(p => p.id === reactingPlayerId);
    const targetPlayer = gameState.players.find(p => p.id === targetPlayerId);
    
    if (reactingPlayer && targetPlayer) {
        addLogEntry(`${reactingPlayer.name} ${reactionType}s to ${targetPlayer.name}'s message`, 'info');
    }
}

// Function to continue after a speaker has finished
function continueAfterSpeaker() {
    console.log("Continuing after speaker");
    
    // Update game state
    gameState.waitingForContinue = false;
    
    // Disable continue button
    continueButton.disabled = true;
    
    // Remove highlight from current speaker
    const playerAvatars = document.querySelectorAll('.player-avatar');
    playerAvatars.forEach(avatar => {
        avatar.classList.remove('pulse');
    });
    
    // Log continuation
    addLogEntry('Continuing to next speaker', 'info');
    
    // Move to next speaker
    socket.emit('next_speaker');
}

// Show waiting indicator for more messages
function showWaitingIndicator() {
    // First, make sure we have the center display
    if (!centerDisplay) return;
    
    // Show center display with waiting message
    centerDisplay.style.display = 'flex';
    
    const centerContent = centerDisplay.querySelector('.center-content');
    centerContent.innerHTML = `
        <h4>Waiting for More Messages</h4>
        <div class="waiting-message">
            Agents are thinking... More messages will appear shortly.
        </div>
        <div class="text-center mt-3">
            <button id="check-messages-button" class="btn btn-primary">Check for Messages</button>
        </div>
    `;
    
    // Add check messages button event listener
    const checkMessagesButton = document.getElementById('check-messages-button');
    if (checkMessagesButton) {
        checkMessagesButton.addEventListener('click', checkForNewMessages);
    }
}

// Hide waiting indicator
function hideWaitingIndicator() {
    if (centerDisplay) {
        centerDisplay.style.display = 'none';
    }
    gameState.waitingForMessages = false;
}

// Check for new messages
function checkForNewMessages() {
    // Disable button while checking
    const checkMessagesButton = document.getElementById('check-messages-button');
    if (checkMessagesButton) {
        checkMessagesButton.disabled = true;
        checkMessagesButton.textContent = 'Checking...';
    }
    
    // Request server to check for new messages
    socket.emit('check_new_messages', (hasNewMessages) => {
        if (!hasNewMessages) {
            // Update UI to indicate no new messages
            const centerContent = centerDisplay.querySelector('.center-content');
            centerContent.innerHTML = `
                <h4>No More Messages Yet</h4>
                <div class="waiting-message">
                    No new messages available yet. Check again in a moment.
                </div>
                <div class="text-center mt-3">
                    <button id="check-again-button" class="btn btn-primary">Check Again</button>
                    <button id="proceed-button" class="btn btn-secondary ml-2">Proceed to Next Phase</button>
                </div>
            `;
            
            // Add event listeners to new buttons
            document.getElementById('check-again-button').addEventListener('click', checkForNewMessages);
            document.getElementById('proceed-button').addEventListener('click', () => {
                nextPhase();
                hideWaitingIndicator();
            });
        }
        // If there are new messages, they'll be handled by the next_speaker and center_display events
    });
}

// Get player name by ID helper function
function getPlayerNameById(playerId) {
    const player = gameState.players.find(p => p.id === playerId);
    return player ? player.name : 'Unknown Player';
}

// Draw vote arrow between two players
function drawVoteArrow(voterId, targetId) {
    // Clear any existing arrow from this voter first
    clearVoteArrow(voterId);
    
    // Find player elements
    const voterElement = document.querySelector(`.player-avatar[data-player-id="${voterId}"]`);
    const targetElement = document.querySelector(`.player-avatar[data-player-id="${targetId}"]`);
    
    if (!voterElement || !targetElement) {
        console.error("Could not find player elements for vote arrow");
        return;
    }
    
    // Get positions of the player elements
    const voterRect = voterElement.getBoundingClientRect();
    const targetRect = targetElement.getBoundingClientRect();
    
    // Calculate center points
    const voterX = voterRect.left + voterRect.width / 2;
    const voterY = voterRect.top + voterRect.height / 2;
    const targetX = targetRect.left + targetRect.width / 2;
    const targetY = targetRect.top + targetRect.height / 2;
    
    // Create SVG arrow
    const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svg.setAttribute("class", "vote-arrow");
    svg.setAttribute("data-voter-id", voterId);
    svg.setAttribute("data-target-id", targetId);
    svg.style.position = "absolute";
    svg.style.top = "0";
    svg.style.left = "0";
    svg.style.width = "100%";
    svg.style.height = "100%";
    svg.style.pointerEvents = "none";
    svg.style.zIndex = "1000";
    
    // Calculate container-relative positions
    const container = document.getElementById('players-container');
    const containerRect = container.getBoundingClientRect();
    
    const relVoterX = voterX - containerRect.left;
    const relVoterY = voterY - containerRect.top;
    const relTargetX = targetX - containerRect.left;
    const relTargetY = targetY - containerRect.top;
    
    // Calculate arrow direction and position
    const dx = relTargetX - relVoterX;
    const dy = relTargetY - relVoterY;
    const distance = Math.sqrt(dx * dx + dy * dy);
    
    // Adjust start and end points to be outside player avatars
    // Increase playerRadius to make arrows shorter
    const playerRadius = voterRect.width / 1.8;
    const startX = relVoterX + (dx / distance) * (playerRadius * 0.8);
    const startY = relVoterY + (dy / distance) * (playerRadius * 0.8);
    
    // Check if there's an opposite arrow (bi-directional voting)
    const hasOppositeArrow = document.querySelector(`.vote-arrow[data-voter-id="${targetId}"][data-target-id="${voterId}"]`);
    
    // Apply offset if there's an opposite arrow to prevent overlap
    let offsetFactor = hasOppositeArrow ? 0.15 : 0;
    
    // Calculate perpendicular vector for offset
    const perpX = -dy / distance;
    const perpY = dx / distance;
    
    // Apply offset to end point
    const endX = relTargetX - (dx / distance) * (playerRadius * 1.2) + (perpX * playerRadius * offsetFactor);
    const endY = relTargetY - (dy / distance) * (playerRadius * 1.2) + (perpY * playerRadius * offsetFactor);
    
    // Create arrow line
    const arrow = document.createElementNS("http://www.w3.org/2000/svg", "line");
    arrow.setAttribute("x1", startX);
    arrow.setAttribute("y1", startY);
    arrow.setAttribute("x2", startX); // Start with zero length
    arrow.setAttribute("y2", startY);
    arrow.setAttribute("stroke", "#ff4d4d");
    arrow.setAttribute("stroke-width", "3");
    arrow.setAttribute("marker-end", "url(#arrowhead)");
    arrow.setAttribute("filter", "drop-shadow(0px 0px 2px rgba(255, 77, 77, 0.7))");
    
    // Create arrowhead marker definition
    const defs = document.createElementNS("http://www.w3.org/2000/svg", "defs");
    const marker = document.createElementNS("http://www.w3.org/2000/svg", "marker");
    marker.setAttribute("id", "arrowhead");
    marker.setAttribute("markerWidth", "10");
    marker.setAttribute("markerHeight", "7");
    marker.setAttribute("refX", "0");
    marker.setAttribute("refY", "3.5");
    marker.setAttribute("orient", "auto");
    
    const polygon = document.createElementNS("http://www.w3.org/2000/svg", "polygon");
    polygon.setAttribute("points", "0 0, 10 3.5, 0 7");
    polygon.setAttribute("fill", "#ff4d4d");
    
    marker.appendChild(polygon);
    defs.appendChild(marker);
    svg.appendChild(defs);
    svg.appendChild(arrow);
    
    // Add the arrow to the players container
    container.appendChild(svg);
    
    // Add text element to show vote count (for multiple votes)
    const voteCount = countVotesForTarget(targetId);
    if (voteCount > 1) {
        const textElement = document.createElementNS("http://www.w3.org/2000/svg", "text");
        textElement.setAttribute("x", endX + perpX * 10);
        textElement.setAttribute("y", endY + perpY * 10);
        textElement.setAttribute("fill", "#ff4d4d");
        textElement.setAttribute("font-size", "12");
        textElement.setAttribute("font-weight", "bold");
        textElement.setAttribute("text-anchor", "middle");
        textElement.textContent = voteCount;
        svg.appendChild(textElement);
    }
    
    // Animate the arrow drawing
    animateArrow(arrow, startX, startY, endX, endY);
}

// Animate arrow drawing from start to end
function animateArrow(arrow, startX, startY, endX, endY) {
    // Duration of animation in milliseconds
    const duration = 500;
    const startTime = performance.now();
    
    // Animation function
    function animate(currentTime) {
        const elapsedTime = currentTime - startTime;
        const progress = Math.min(elapsedTime / duration, 1);
        
        // Linear interpolation between start and end points
        const currentX = startX + (endX - startX) * progress;
        const currentY = startY + (endY - startY) * progress;
        
        // Update arrow end point
        arrow.setAttribute("x2", currentX);
        arrow.setAttribute("y2", currentY);
        
        // Continue animation if not complete
        if (progress < 1) {
            requestAnimationFrame(animate);
        } else {
            // Add a pulse effect after animation completes
            arrow.animate([
                { opacity: 0.5, strokeWidth: "2px" },
                { opacity: 1, strokeWidth: "3px" },
                { opacity: 0.5, strokeWidth: "2px" }
            ], {
                duration: 2000,
                iterations: Infinity
            });
        }
    }
    
    // Start the animation
    requestAnimationFrame(animate);
}

// Count how many votes a target has received
function countVotesForTarget(targetId) {
    return document.querySelectorAll(`.vote-arrow[data-target-id="${targetId}"]`).length;
}

// Clear vote arrow from a specific voter
function clearVoteArrow(voterId) {
    const arrows = document.querySelectorAll(`.vote-arrow[data-voter-id="${voterId}"]`);
    arrows.forEach(arrow => arrow.remove());
}

// Clear all vote arrows
function clearAllVoteArrows() {
    const arrows = document.querySelectorAll('.vote-arrow');
    arrows.forEach(arrow => arrow.remove());
}

// Add log entry
function addLogEntry(message, type = 'info') {
    const logEntry = document.createElement('div');
    logEntry.className = `log-entry ${type} fade-in`;
    
    // Format timestamp
    const timestamp = new Date().toLocaleTimeString();
    
    logEntry.innerHTML = `<span class="log-time">[${timestamp}]</span> ${message}`;
    
    gameLog.appendChild(logEntry);
    
    // Scroll to bottom
    gameLog.scrollTop = gameLog.scrollHeight;
}

// Show game results
function showGameResults(result) {
    // Update winning team
    winningTeamElement.textContent = result.winning_team;
    winningTeamElement.className = result.winning_team.toLowerCase();
    
    // Update player lists
    villagePlayers.innerHTML = '';
    mafiaPlayers.innerHTML = '';
    
    result.players.forEach(player => {
        const playerElement = document.createElement('li');
        playerElement.className = player.status.toLowerCase();
        
        // Add icon based on role
        let iconClass = 'fa-user';
        switch (player.role.toLowerCase()) {
            case 'villager':
                iconClass = 'fa-person';
                break;
            case 'mafia':
                iconClass = 'fa-user-ninja';
                break;
            case 'doctor':
                iconClass = 'fa-user-md';
                break;
            case 'detective':
                iconClass = 'fa-user-secret';
                break;
            case 'godfather':
                iconClass = 'fa-crown';
                break;
        }
        
        playerElement.innerHTML = `
            <span class="role-icon"><i class="fas ${iconClass}"></i></span>
            <span>${player.name} (${player.role})</span>
        `;
        
        if (player.team.toLowerCase() === 'village') {
            villagePlayers.appendChild(playerElement);
        } else {
            mafiaPlayers.appendChild(playerElement);
        }
    });
    
    // Update statistics
    totalRoundsElement.textContent = result.total_rounds;
    totalMessagesElement.textContent = result.total_messages;
    totalVotesElement.textContent = result.total_votes;
    
    // Show modal
    gameResultsModal.show();
}

// Download game transcript
function downloadTranscript() {
    socket.emit('get_transcript', (transcript) => {
        // Create a blob with the transcript data
        const blob = new Blob([JSON.stringify(transcript, null, 2)], { type: 'application/json' });
        
        // Create a download link
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `mafia_game_transcript_${new Date().toISOString().slice(0, 19).replace(/:/g, '-')}.json`;
        
        // Trigger download
        document.body.appendChild(a);
        a.click();
        
        // Clean up
        setTimeout(() => {
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
        }, 0);
    });
}
