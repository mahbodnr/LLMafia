// Highlight current speaker and add functions for reactions
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
