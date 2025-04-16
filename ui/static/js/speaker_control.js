// Function to continue after a speaker has finished
function continueAfterSpeaker() {
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
    
    // If in auto play mode, automatically move to next speaker/phase
    if (gameState.autoPlay) {
        // Wait a moment before continuing
        setTimeout(() => {
            socket.emit('next_speaker');
        }, 1000);
    }
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

// Socket event handler for player reactions
socket.on('player_reaction', (data) => {
    handlePlayerReaction(data.player_id, data.target_id, data.reaction_type);
});

// Socket event handler for next speaker
socket.on('next_speaker', (data) => {
    if (data.speaker_id) {
        updateCurrentSpeaker(data.speaker_id, data.speaker_name, data.message);
    } else {
        // No more speakers, enable next phase button
        nextPhaseButton.disabled = false;
        currentSpeakerName.textContent = 'None';
        currentSpeakerMessage.textContent = 'All players have spoken for this phase.';
    }
});
