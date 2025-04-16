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
    autoPlay: false,
    currentSpeaker: null,
    waitingForContinue: false
};

// DOM Elements
const gamePhaseElement = document.getElementById('game-phase');
const gameRoundElement = document.getElementById('game-round');
const gameTimeElement = document.getElementById('game-time');
const startGameButton = document.getElementById('start-game');
const nextPhaseButton = document.getElementById('next-phase');
const autoPlayButton = document.getElementById('auto-play');
const pauseGameButton = document.getElementById('pause-game');
const resetGameButton = document.getElementById('reset-game');
const playersContainer = document.getElementById('players-container');
const gameAnnouncements = document.getElementById('game-announcements');
const chatMessages = document.getElementById('chat-messages');
const gameLog = document.getElementById('game-log');
const currentSpeakerName = document.getElementById('current-speaker-name');
const currentSpeakerMessage = document.getElementById('current-speaker-message');
const continueButton = document.getElementById('continue-button');

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

    socket.on('next_speaker', (data) => {
        console.log("Received next speaker:", data);
        if (data.speaker_id) {
            updateCurrentSpeaker(data.speaker_id, data.player_name, data.message);
        } else {
            // No more speakers, enable next phase button
            nextPhaseButton.disabled = false;
            currentSpeakerName.textContent = 'None';
            currentSpeakerMessage.textContent = 'All players have spoken for this phase.';
            continueButton.disabled = true;
        }
    });

    socket.on('player_reaction', (data) => {
        console.log("Received player reaction:", data);
        handlePlayerReaction(data.player_id, data.target_id, data.reaction_type);
    });
}

// Set up event listeners for UI elements
function setupEventListeners() {
    startGameButton.addEventListener('click', startGame);
    nextPhaseButton.addEventListener('click', nextPhase);
    autoPlayButton.addEventListener('click', toggleAutoPlay);
    pauseGameButton.addEventListener('click', pauseGame);
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
    autoPlayButton.disabled = false;
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

// Toggle auto play mode
function toggleAutoPlay() {
    gameState.autoPlay = !gameState.autoPlay;
    
    if (gameState.autoPlay) {
        autoPlayButton.textContent = 'Stop Auto Play';
        autoPlayButton.classList.replace('btn-success', 'btn-danger');
        nextPhaseButton.disabled = true;
        pauseGameButton.disabled = false;
        
        // Start auto play
        socket.emit('auto_play', true);
    } else {
        autoPlayButton.textContent = 'Auto Play';
        autoPlayButton.classList.replace('btn-danger', 'btn-success');
        nextPhaseButton.disabled = false;
        pauseGameButton.disabled = true;
        
        // Stop auto play
        socket.emit('auto_play', false);
    }
}

// Pause the game
function pauseGame() {
    socket.emit('pause_game');
    pauseGameButton.disabled = true;
}

// Reset the game
function resetGame() {
    socket.emit('reset_game');
    
    // Reset UI
    startGameButton.disabled = false;
    nextPhaseButton.disabled = true;
    autoPlayButton.disabled = true;
    pauseGameButton.disabled = true;
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
        autoPlay: false,
        currentSpeaker: null,
        waitingForContinue: false
    };
    
    // Reset UI elements
    gamePhaseElement.querySelector('span').textContent = 'Not Started';
    gameRoundElement.querySelector('span').textContent = '0';
    gameTimeElement.querySelector('span').textContent = 'Day';
    playersContainer.innerHTML = '';
    gameAnnouncements.innerHTML = 'Welcome to the Mafia Game with LLM Agents! Configure your game settings and press "Start New Game" to begin.';
    chatMessages.innerHTML = '';
    gameLog.innerHTML = '';
    currentSpeakerName.textContent = 'None';
    currentSpeakerMessage.textContent = 'Waiting for the game to start...';
    continueButton.disabled = true;
    
    // Reset auto play button
    autoPlayButton.textContent = 'Auto Play';
    autoPlayButton.classList.replace('btn-danger', 'btn-success');
    
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
    // TODO: Implement player details modal or sidebar
    console.log('Player details:', player);
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
    
    // Add night mode class to game announcements
    gameAnnouncements.classList.add('night-mode');
    
    // Add night mode class to current speaker display
    document.querySelector('.current-speaker').classList.add('night-mode');
}

// Restore visibility for day phase
function restoreVisibilityForDay() {
    // Show all messages during day phase
    const hiddenMessages = document.querySelectorAll('.chat-message.night-hidden');
    hiddenMessages.forEach(msg => {
        msg.classList.remove('night-hidden');
    });
    
    // Remove night mode class from game announcements
    gameAnnouncements.classList.remove('night-mode');
    
    // Remove night mode class from current speaker display
    document.querySelector('.current-speaker').classList.remove('night-mode');
}

// Handle game events
function handleGameEvent(event) {
    // Add to game events
    gameState.events.push(event);
    
    // Update announcements
    if (event.public) {
        // Add to announcements instead of replacing
        gameAnnouncements.innerHTML += `<div class="fade-in announcement-item">${event.description}</div>`;
        
        // Scroll to bottom of announcements
        gameAnnouncements.scrollTop = gameAnnouncements.scrollHeight;
    }
    
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
    
    // Update current speaker display
    if (message.public) {
        updateCurrentSpeaker(message.sender_id, message.sender_name, message.content);
    }
}

// Update current speaker display
function updateCurrentSpeaker(speakerId, speakerName, message) {
    console.log(`Updating current speaker: ${speakerName}`);
    
    // Update game state
    gameState.currentSpeaker = speakerId;
    gameState.waitingForContinue = true;
    
    // Update UI
    currentSpeakerName.textContent = speakerName;
    currentSpeakerMessage.textContent = message;
    
    // Enable continue button
    continueButton.disabled = false;
    
    // Disable auto play and next phase buttons while waiting
    if (gameState.autoPlay) {
        pauseGame();
    }
    nextPhaseButton.disabled = true;
    
    // Highlight the current speaker's avatar
    highlightCurrentSpeaker(speakerId);
    
    // Scroll to the current speaker's message
    currentSpeakerMessage.scrollIntoView({ behavior: 'smooth' });
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
    
    // Enable next phase button
    nextPhaseButton.disabled = false;
    
    // Remove highlight from current speaker
    const playerAvatars = document.querySelectorAll('.player-avatar');
    playerAvatars.forEach(avatar => {
        avatar.classList.remove('pulse');
    });
    
    // If auto play was active, resume it
    if (gameState.autoPlay) {
        autoPlayButton.textContent = 'Stop Auto Play';
        autoPlayButton.classList.replace('btn-success', 'btn-danger');
        pauseGameButton.disabled = false;
        
        // Resume auto play
        socket.emit('auto_play', true);
    }
    
    // Log continuation
    addLogEntry('Continuing to next speaker', 'info');
    
    // Move to next speaker
    socket.emit('next_speaker');
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
