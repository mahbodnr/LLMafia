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
    waitingForMessages: false,
    voteResult: null,
    transcriptFile: null
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

// New DOM Elements for transcript upload
const transcriptFileInput = document.getElementById('transcript-file');
const uploadTranscriptButton = document.getElementById('upload-transcript');
const clearTranscriptButton = document.getElementById('clear-transcript');
const uploadStatusElement = document.getElementById('upload-status');

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
const memoryPlayerModel = document.getElementById('memory-player-model');
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
        const centerContent = centerDisplay.querySelector('.center-content'); // Get the content container

        if (data.active) {
            // Force update UI regardless of previous state
            centerDisplay.style.display = 'flex';

            // Clear previous content
            centerContent.innerHTML = '';

            // Check if this is a night action, vote result, or a speaker message
            if (data.is_action) {
                // This is a night action
                const centerContent = centerDisplay.querySelector('.center-content');
                
                // Set specific styles based on action type
                let actionIcon, actionColor, actionBackground, actionTitle, actionDescription;
                
                switch(data.action_type) {
                    case "kill":
                        actionIcon = "fa-skull";
                        actionColor = "#dc3545"; // Red
                        actionBackground = "rgba(220, 53, 69, 0.1)";
                        actionTitle = "KILL";
                        actionDescription = `is targeting`;
                        break;
                    case "protect":
                        actionIcon = "fa-shield-alt";
                        actionColor = "#28a745"; // Green
                        actionBackground = "rgba(40, 167, 69, 0.1)";
                        actionTitle = "PROTECT";
                        actionDescription = `is protecting`;
                        break;
                    case "investigate":
                        actionIcon = "fa-search";
                        actionColor = "#17a2b8"; // Info blue
                        actionBackground = "rgba(23, 162, 184, 0.1)";
                        actionTitle = "INVESTIGATE";
                        actionDescription = `is investigating`;
                        break;
                    default:
                        actionIcon = "fa-cogs";
                        actionColor = "#6c757d"; // Gray
                        actionBackground = "rgba(108, 117, 125, 0.1)";
                        actionTitle = data.action_type.replace(/_/g, ' ').toUpperCase();
                        actionDescription = `is performing an action on`;
                }
                
                centerContent.innerHTML = `
                    <div class="action-display" style="border-left: 5px solid ${actionColor}; background-color: ${actionBackground}; padding: 20px; border-radius: 5px;">
                        <h4 style="color: ${actionColor}; display: flex; align-items: center; gap: 10px; margin-bottom: 20px;">
                            <i class="fas ${actionIcon}"></i> ${actionTitle}
                        </h4>
                        <div class="action-content">
                            <div class="actor-target-container" style="display: flex; justify-content: space-between; align-items: center;">
                                <div class="actor" style="text-align: center; flex: 1;">
                                    <div class="avatar" style="height: 80px; width: 80px; background-color: ${actionColor}; border-radius: 50%; margin: 0 auto 10px; display: flex; align-items: center; justify-content: center;">
                                        <i class="fas fa-user" style="font-size: 40px; color: white;"></i>
                                    </div>
                                    <p style="font-weight: bold; font-size: 1.2rem;">${data.actor}</p>
                                </div>
                                
                                <div class="action-arrow" style="flex: 0 0 60px; text-align: center;">
                                    <i class="fas fa-long-arrow-alt-right" style="font-size: 30px; color: ${actionColor};"></i>
                                    <p style="margin-top: 5px; font-size: 0.9rem;">${actionDescription}</p>
                                </div>
                                
                                <div class="target" style="text-align: center; flex: 1;">
                                    <div class="avatar" style="height: 80px; width: 80px; background-color: #6c757d; border-radius: 50%; margin: 0 auto 10px; display: flex; align-items: center; justify-content: center;">
                                        <i class="fas fa-user" style="font-size: 40px; color: white;"></i>
                                    </div>
                                    <p style="font-weight: bold; font-size: 1.2rem;">${data.target}</p>
                                </div>
                            </div>
                        </div>
                        <div class="text-center mt-4">
                            <button id="continue-action-button" class="btn" style="background-color: ${actionColor}; color: white;">Continue</button>
                        </div>
                    </div>
                `;
                
                // Add event listener to continue button for actions
                const actionContinueButton = document.getElementById('continue-action-button');
                if (actionContinueButton) {
                    actionContinueButton.addEventListener('click', () => {
                        socket.emit('continue_action');
                    });
                } else {
                    console.error("Could not find action continue button.");
                }

                nextPhaseButton.disabled = true;
            } else if (data.is_vote_result) {
                // This is a vote result
                centerContent.innerHTML = `
                    <div class="vote-result-display" style="padding: 20px; border-radius: 5px; background-color: rgba(108, 117, 125, 0.1); border-left: 5px solid #6c757d;">
                        <h4 style="color: #6c757d; display: flex; align-items: center; gap: 10px; margin-bottom: 15px;">
                            <i class="fas fa-gavel"></i> ${data.title || 'Vote Result'}
                        </h4>
                        <p style="margin-bottom: 20px;">${data.message || 'No vote details available.'}</p>
                        <div class="text-center">
                            <button id="vote-result-continue-button" class="btn btn-secondary">OK</button>
                        </div>
                    </div>
                `;

                // Add event listener to the OK button for vote results
                const voteResultContinueButton = document.getElementById('vote-result-continue-button');
                if (voteResultContinueButton) {
                    voteResultContinueButton.addEventListener('click', () => {
                        centerDisplay.style.display = 'none'; // Just hide the display
                        nextPhaseButton.disabled = false; // Re-enable next phase button
                    });
                } else {
                    console.error("Could not find vote result continue button.");
                }
                nextPhaseButton.disabled = true; // Disable next phase until OK is clicked

            } else {
                // This is a regular speaker message
                // Set the HTML for the speaker display
                centerContent.innerHTML = `
                    <div class="speaker-display" style="padding: 20px;">
                        <h4 id="current-speaker-name" style="margin-bottom: 15px;">${data.player_name || 'Speaker'}</h4>
                        <p id="current-speaker-message" style="margin-bottom: 20px;">${data.message || 'No message'}</p>
                        <div class="text-center">
                            <button id="continue-speaker-button" class="btn btn-primary">Continue</button>
                        </div>
                    </div>
                `;

                // Re-find the continue button *after* setting innerHTML
                const speakerContinueButton = document.getElementById('continue-speaker-button');
                if (speakerContinueButton) {
                    // Remove previous listener if any (safer) and add the correct one
                    speakerContinueButton.removeEventListener('click', continueAfterSpeaker); // Remove old listener if exists
                    speakerContinueButton.addEventListener('click', continueAfterSpeaker); // Add the correct listener
                    speakerContinueButton.disabled = false;
                } else {
                    console.error("Could not find speaker continue button after update.");
                }

                nextPhaseButton.disabled = true;
            }
        } else {
            // Hide center display
            centerDisplay.style.display = 'none';
            // Ensure next phase button is enabled when display is inactive
            // Check game state if needed, but generally should be enabled if nothing is blocking
            if (!gameState.waitingForContinue && !gameState.waitingForMessages) {
                 nextPhaseButton.disabled = false;
            }
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

    // Add handler for transcript upload response
    socket.on('transcript_upload_response', (data) => {
        console.log("Received transcript upload response:", data);
        if (data.success) {
            uploadStatusElement.textContent = "Transcript uploaded successfully!";
            uploadStatusElement.className = "small text-success mb-2";
            clearTranscriptButton.disabled = false;
            
            // Disable regular game settings when transcript is loaded
            toggleGameSettingsInputs(true);
            
            // Update start game button to indicate replay mode
            startGameButton.textContent = "Start Replay";
            startGameButton.classList.remove('btn-primary');
            startGameButton.classList.add('btn-info');
        } else {
            uploadStatusElement.textContent = `Upload failed: ${data.error}`;
            uploadStatusElement.className = "small text-danger mb-2";
            gameState.transcriptFile = null;
        }
    });
}

// Set up event listeners for UI elements
function setupEventListeners() {
    startGameButton.addEventListener('click', startGame);
    nextPhaseButton.addEventListener('click', () => {
        nextPhase();
    });
    resetGameButton.addEventListener('click', resetGame);
    downloadTranscriptButton.addEventListener('click', downloadTranscript);
    newGameButton.addEventListener('click', () => {
        gameResultsModal.hide();
        resetGame();
    });

    // Set up transcript upload listeners
    uploadTranscriptButton.addEventListener('click', uploadTranscript);
    clearTranscriptButton.addEventListener('click', clearTranscriptUpload);
    transcriptFileInput.addEventListener('change', handleFileInputChange);

    // Update mafia count options when player count changes
    playerCountSelect.addEventListener('change', updateMafiaCountOptions);
    updateMafiaCountOptions();
}

// Handle transcript file selection
function handleFileInputChange(event) {
    if (event.target.files && event.target.files.length > 0) {
        uploadStatusElement.textContent = `File selected: ${event.target.files[0].name}`;
        uploadStatusElement.className = "small text-primary mb-2";
        uploadTranscriptButton.disabled = false;
    } else {
        uploadStatusElement.textContent = "No file selected";
        uploadStatusElement.className = "small text-muted mb-2";
        uploadTranscriptButton.disabled = true;
    }
}

// Upload transcript file to server
function uploadTranscript() {
    const fileInput = document.getElementById('transcript-file');
    const file = fileInput.files[0];
    
    if (!file) {
        uploadStatusElement.textContent = "No file selected";
        uploadStatusElement.className = "small text-danger mb-2";
        return;
    }
    
    // Show loading state
    uploadStatusElement.textContent = "Uploading...";
    uploadStatusElement.className = "small text-primary mb-2";
    uploadTranscriptButton.disabled = true;
    
    const reader = new FileReader();
    
    reader.onload = function(e) {
        try {
            // Parse JSON to validate format
            const content = JSON.parse(e.target.result);
            
            // Send to server
            socket.emit('upload_transcript', {
                filename: file.name,
                content: content
            });
            
            // Save reference to file
            gameState.transcriptFile = file.name;
            
        } catch (error) {
            console.error("Error parsing transcript file:", error);
            uploadStatusElement.textContent = "Invalid JSON file";
            uploadStatusElement.className = "small text-danger mb-2";
            uploadTranscriptButton.disabled = false;
        }
    };
    
    reader.onerror = function() {
        uploadStatusElement.textContent = "Error reading file";
        uploadStatusElement.className = "small text-danger mb-2";
        uploadTranscriptButton.disabled = false;
    };
    
    reader.readAsText(file);
}

// Clear transcript upload
function clearTranscriptUpload() {
    // Reset file input
    document.getElementById('transcript-file').value = '';
    
    // Update UI
    uploadStatusElement.textContent = "Upload cleared";
    uploadStatusElement.className = "small text-muted mb-2";
    uploadTranscriptButton.disabled = true;
    clearTranscriptButton.disabled = true;
    
    // Reset game state
    gameState.transcriptFile = null;
    
    // Re-enable regular game settings
    toggleGameSettingsInputs(false);
    
    // Restore start game button
    startGameButton.textContent = "Start New Game";
    startGameButton.classList.remove('btn-info');
    startGameButton.classList.add('btn-primary');
    
    // Tell server to clear any uploaded transcript
    socket.emit('clear_transcript');
}

// Helper function to enable/disable game settings inputs
function toggleGameSettingsInputs(disabled) {
    playerCountSelect.disabled = disabled;
    mafiaCountSelect.disabled = disabled;
    includeDoctorCheckbox.disabled = disabled;
    includeDetectiveCheckbox.disabled = disabled;
    includeGodfatherCheckbox.disabled = disabled;
    discussionRoundsSelect.disabled = disabled;
    verboseModeCheckbox.disabled = disabled;
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
        verboseMode: verboseModeCheckbox.checked,
        useTranscript: gameState.transcriptFile !== null // Add this flag
    };
    
    console.log("Starting game with settings:", settings);
    
    // Send start game request to server
    socket.emit('start_game', settings);
    
    // Update UI
    startGameButton.disabled = true;
    nextPhaseButton.disabled = false;
    resetGameButton.disabled = false;
    
    // Disable settings and upload
    toggleGameSettingsInputs(true);
    transcriptFileInput.disabled = true;
    uploadTranscriptButton.disabled = true;
    clearTranscriptButton.disabled = true;
    
    addLogEntry('Starting new game...', 'info');
}

// Move to the next game phase
function nextPhase() {
    console.log("Moving to next phase");
    socket.emit('next_phase');
    // Show loading message in center display
    showPhaseLoadingMessage();
}

// Reset the game
function resetGame() {
    socket.emit('reset_game');
    
    // Reset UI
    startGameButton.disabled = false;
    nextPhaseButton.disabled = true;
    resetGameButton.disabled = true;
    
    // Re-enable settings based on whether we have a transcript
    if (gameState.transcriptFile) {
        toggleGameSettingsInputs(true); // Keep settings disabled if transcript is still loaded
        clearTranscriptButton.disabled = false; // Allow clearing
        startGameButton.textContent = "Start Replay"; // Keep button text
        startGameButton.classList.remove('btn-primary');
        startGameButton.classList.add('btn-info');
    } else {
        toggleGameSettingsInputs(false); // Enable settings if no transcript
        clearTranscriptButton.disabled = true;
        startGameButton.textContent = "Start New Game"; // Reset button text
        startGameButton.classList.remove('btn-info');
        startGameButton.classList.add('btn-primary');
    }
    
    // Re-enable file upload input
    transcriptFileInput.disabled = false;
    // Enable upload button only if a file is selected (handleFileInputChange will manage this)
    uploadTranscriptButton.disabled = !transcriptFileInput.files.length; 
    
    // Reset game state (keep transcriptFile if it exists)
    const currentTranscriptFile = gameState.transcriptFile; // Preserve transcript file name
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
        waitingForMessages: false,
        voteResult: null,
        transcriptFile: currentTranscriptFile // Restore transcript file name
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
    
    // Reset to day mode styling
    const body = document.body;
    body.classList.remove('night-mode', 'day-to-night');
    body.classList.add('day-mode');
    
    // Remove night mode class from center display
    centerDisplay.classList.remove('night-mode');
    
    // Restore any hidden elements
    restoreVisibilityForDay();
    
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
    
    // Display AI model name if available
    memoryPlayerModel.textContent = player.model_name || 'Unknown';
    memoryPlayerModel.className = 'badge rounded-pill bg-info';
    
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
    
    // Update the model name badge if available
    if (data.model_name) {
        memoryPlayerModel.textContent = data.model_name;
        memoryPlayerModel.className = 'badge rounded-pill bg-info';
    }
    
    // If no memory entries, show a message
    if (!data.memory || data.memory.length === 0) {
        memoryContent.innerHTML = '<div class="alert alert-info">This player has no memory entries.</div>';
        return;
    }
    
    // Log what we received to help debugging
    console.log(`Displaying ${data.memory.length} memory entries for ${data.name}`);
    console.log("Memory entries types:", data.memory.map(entry => entry.type));
    
    // Track memory entry filters
    const filterThoughts = document.getElementById('filter-thoughts');
    const filterMessages = document.getElementById('filter-messages');
    const filterVotes = document.getElementById('filter-votes');
    const filterActions = document.getElementById('filter-actions');
    
    // Add event listeners to filters if they don't exist
    if (!filterThoughts.dataset.listenerAdded) {
        filterThoughts.addEventListener('change', () => refreshMemoryDisplay(data));
        filterThoughts.dataset.listenerAdded = "true";
    }
    if (!filterMessages.dataset.listenerAdded) {
        filterMessages.addEventListener('change', () => refreshMemoryDisplay(data));
        filterMessages.dataset.listenerAdded = "true";
    }
    if (!filterVotes.dataset.listenerAdded) {
        filterVotes.addEventListener('change', () => refreshMemoryDisplay(data));
        filterVotes.dataset.listenerAdded = "true";
    }
    if (!filterActions.dataset.listenerAdded) {
        filterActions.addEventListener('change', () => refreshMemoryDisplay(data));
        filterActions.dataset.listenerAdded = "true";
    }
    
    // Store the data for filter refreshing
    memoryContent.dataset.playerMemory = JSON.stringify(data);
    
    // Display the memory
    refreshMemoryDisplay(data);
}

// Refresh the memory display based on current filters
function refreshMemoryDisplay(data) {
    // If data is a string (from dataset), parse it
    if (typeof data === 'string') {
        data = JSON.parse(data);
    }
    
    // Get filter states
    const showThoughts = document.getElementById('filter-thoughts').checked;
    const showMessages = document.getElementById('filter-messages').checked;
    const showVotes = document.getElementById('filter-votes').checked;
    const showActions = document.getElementById('filter-actions').checked;
    
    // Create memory timeline
    let html = '<div class="memory-timeline">';
    
    // Filter entries first
    const filteredEntries = data.memory.filter(entry => {
        switch (entry.type) {
            case 'inner_thought': return showThoughts;
            case 'message': return showMessages;
            case 'vote': return showVotes;
            case 'action': return showActions;
            default: return false;
        }
    });
    
    // Sort entries by round (ensure numeric comparison) and phase
    filteredEntries.sort((a, b) => {
        const roundA = Number(a.round) || 0;
        const roundB = Number(b.round) || 0;
        if (roundA !== roundB) return roundA - roundB;
        return (a.phase || "").localeCompare(b.phase || "");
    });
    
    // Track phases to add separators
    let currentPhase = "";
    let currentRound = -1; // Use -1 to ensure first round is always displayed
    
    // Process entries, adding phase separators as needed
    filteredEntries.forEach(entry => {
        // Ensure round is a number for consistent comparison
        const entryRound = Number(entry.round) || 0;
        
        // Always add a separator for the first entry
        if (currentRound === -1 || entryRound !== currentRound || entry.phase !== currentPhase) {
            currentPhase = entry.phase;
            currentRound = entryRound;
            // For round 0, display as "Setup" instead
            const displayRound = entryRound === 0 ? "Setup" : entryRound;
            html += createPhaseChangeSeparator(displayRound, entry.phase);
        }
        
        // Process entry based on type
        if (entry.type === "inner_thought") {
            html += createInnerThoughtMemoryEntry(entry);
        } else if (entry.type === "message") {
            html += createMessageMemoryEntry(entry, data.name);
        } else if (entry.type === "vote") {
            html += createVoteMemoryEntry(entry, data.name);
        } else if (entry.type === "action") {
            html += createActionMemoryEntry(entry);
        }
    });
    
    html += '</div>';
    memoryContent.innerHTML = html;
}

// Create HTML for a phase change separator
function createPhaseChangeSeparator(round, phase) {
    // Handle round 0 as "Setup"
    const displayRound = round === 0 || round === "0" ? "Setup" : `Round ${round}`;
    
    return `
        <div class="phase-separator">
            <div class="phase-line"></div>
            <div class="phase-label">${displayRound} - ${phase}</div>
            <div class="phase-line"></div>
        </div>
    `;
}

// Create HTML for an inner thought memory entry
function createInnerThoughtMemoryEntry(entry) {
    return `
        <div class="memory-entry memory-inner-thought fade-in">
            <div class="memory-entry-header">
                <span class="memory-round">Round ${entry.round}</span>
                <span class="memory-phase">${entry.phase}</span>
                <span class="memory-type-badge thought-badge">Inner Thought</span>
            </div>
            <div class="memory-entry-content">
                <i class="fas fa-brain" style="margin-right: 8px; color: #9c27b0;"></i>
                ${entry.description}
            </div>
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

// Create HTML for a vote memory entry
function createVoteMemoryEntry(entry, playerName) {
    // Debug log for votes
    console.log("Creating vote entry:", entry);
    
    const isVoter = entry.voter === playerName;
    const voteClass = isVoter ? 'vote-from' : 'vote-to';
    const voteIcon = isVoter ? 'fa-arrow-circle-right' : 'fa-arrow-circle-left';
    const voteColor = isVoter ? '#dc3545' : '#007bff'; // Red for outgoing, blue for incoming
    
    return `
        <div class="memory-entry memory-vote ${voteClass} fade-in">
            <div class="memory-entry-header">
                <span class="memory-round">Round ${entry.round}</span>
                <span class="memory-phase">${entry.phase}</span>
                <span class="memory-type-badge vote-badge" style="background-color: ${voteColor}">Vote</span>
            </div>
            <div class="vote-details">
                <div class="vote-action">
                    <span class="voter">${entry.voter}</span>
                    <i class="fas ${voteIcon}" style="margin: 0 10px; color: ${voteColor};"></i>
                    <span class="target">${entry.target}</span>
                </div>
                ${entry.reason ? `<div class="vote-reason">${entry.reason}</div>` : ''}
            </div>
        </div>
    `;
}

// Create HTML for an action memory entry
function createActionMemoryEntry(entry) {
    // Debug log for actions
    console.log("Creating action entry:", entry);
    
    // Different styling for different action types
    let actionIcon, actionColor;
    
    switch(entry.action_type) {
        case "kill":
            actionIcon = "fa-skull";
            actionColor = "#dc3545"; // Red
            break;
        case "protect":
            actionIcon = "fa-shield-alt";
            actionColor = "#28a745"; // Green
            break;
        case "investigate":
            actionIcon = "fa-search";
            actionColor = "#17a2b8"; // Info blue
            break;
        default:
            actionIcon = "fa-cogs";
            actionColor = "#6c757d"; // Gray
    }
    
    return `
        <div class="memory-entry memory-action fade-in" style="border-left-color: ${actionColor};">
            <div class="memory-entry-header">
                <span class="memory-round">Round ${entry.round}</span>
                <span class="memory-phase">${entry.phase}</span>
                <span class="memory-type-badge action-badge" style="background-color: ${actionColor}">Action</span>
            </div>
            <div class="action-details">
                <i class="fas ${actionIcon}" style="margin-right: 10px; color: ${actionColor};"></i>
                <span>${entry.actor} used ${entry.action_type} on ${entry.target}</span>
            </div>
            ${entry.result ? `<div class="action-result">${entry.result}</div>` : ''}
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
    svg.style.zIndex = "100";
    
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
    
    // Reset to day mode styling for the entire UI
    const body = document.body;
    body.classList.remove('night-mode', 'day-to-night');
    body.classList.add('day-mode');
    
    // Remove night mode class from center display
    centerDisplay.classList.remove('night-mode');
    
    // Restore any hidden elements
    restoreVisibilityForDay();
    
    // Show modal
    gameResultsModal.show();
}

// Download game transcript
function downloadTranscript() {
    // Show loading indicator
    addLogEntry("Requesting transcript...", "info");
    console.log("Requesting transcript...");
    
    socket.emit('get_transcript', (response) => {
        console.log("Received transcript response:", response ? 
            (typeof response === 'object' ? `${Object.keys(response).length} keys` : typeof response) 
            : 'undefined');
        
        // Check for error in response
        if (response && response.error) {
            console.error("Error from server:", response.error);
            addLogEntry(`Failed to download transcript: ${response.error}`, "error");
            alert(`Error: ${response.error}`);
            return;
        }
        
        // Check if we have valid data
        if (!response || typeof response === 'undefined') {
            console.error("Received empty transcript data");
            addLogEntry("Failed to download transcript: Empty data received", "error");
            alert("Error: Could not generate transcript - empty data received");
            return;
        }
        
        try {
            // Log what we're working with for debugging
            console.log("Transcript response type:", typeof response);
            if (typeof response === 'object') {
                console.log("Transcript keys:", Object.keys(response));
            }
            
            // Ensure we have valid JSON data by stringifying
            const jsonData = JSON.stringify(response, null, 2);
            console.log("Transcript data processed, size:", jsonData.length);
            
            // Create a blob with the transcript data
            const blob = new Blob([jsonData], { type: 'application/json' });
            
            // Create a download link
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            const timestamp = new Date().toISOString().slice(0, 19).replace(/:/g, '-');
            a.download = `mafia_game_transcript_${timestamp}.json`;
            
            // Trigger download
            document.body.appendChild(a);
            a.click();
            
            // Log success
            addLogEntry("Transcript downloaded successfully", "success");
            
            // Clean up
            setTimeout(() => {
                document.body.removeChild(a);
                URL.revokeObjectURL(url);
                console.log("Transcript download complete");
            }, 100);
        } catch (e) {
            console.error("Error processing transcript data:", e);
            addLogEntry(`Error processing transcript data: ${e.message}`, "error");
            alert(`Error processing transcript data: ${e.message}`);
        }
    });
}

// Function to show loading message during phase transition
function showPhaseLoadingMessage() {
    // Get the center display and content
    const centerDisplay = document.getElementById('center-display');
    const centerContent = centerDisplay.querySelector('.center-content');
    
    // Get the current time (day/night) for styling
    const isNight = gameState.time === 'night';
    const loadingColor = isNight ? '#375a7f' : '#3498db';
    const loadingBackground = isNight ? 'rgba(55, 90, 127, 0.1)' : 'rgba(52, 152, 219, 0.1)';
    
    // Update the center display with loading message
    centerDisplay.style.display = 'flex';
    centerContent.innerHTML = `
        <div class="loading-display" style="padding: 20px; border-radius: 5px; background-color: ${loadingBackground}; border-left: 5px solid ${loadingColor};">
            <h4 style="color: ${loadingColor}; display: flex; align-items: center; gap: 10px; margin-bottom: 15px;">
                <i class="fas fa-hourglass-half fa-spin"></i> Models are Thinking
            </h4>
            <div class="text-center mb-4">
                <div class="spinner-border" role="status" style="color: ${loadingColor};">
                    <span class="visually-hidden">Loading...</span>
                </div>
            </div>
            <p style="text-align: center;">Please wait while players prepare their speeches...</p>
        </div>
    `;
    
    // Disable next phase button while loading
    nextPhaseButton.disabled = true;
}
