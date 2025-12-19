document.addEventListener('DOMContentLoaded', function() {
    const chatContainer = document.querySelector('.chat-container');
    const messagesContainer = document.querySelector('.messages');
    const messageInput = document.querySelector('.input-field');
    const sendButton = document.querySelector('.send-button');
    const form = document.querySelector('.input-area');
    
    let conversationId = null;
    
    // Initialize the chat
    function initChat() {
        addBotMessage(GREETING);
        scrollToBottom();
    }
    
    // Add a message to the chat
    function addMessage(content, isUser = false) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${isUser ? 'user' : 'bot'}`;
        messageDiv.textContent = content;
        messagesContainer.appendChild(messageDiv);
        scrollToBottom();
    }
    
    // Add a bot message
    function addBotMessage(content) {
        addMessage(content, false);
    }
    
    // Show typing indicator
    function showTypingIndicator() {
        const typingDiv = document.createElement('div');
        typingDiv.className = 'typing-indicator';
        typingDiv.id = 'typing-indicator';
        typingDiv.innerHTML = `
            <div class="typing-dot"></div>
            <div class="typing-dot"></div>
            <div class="typing-dot"></div>
        `;
        messagesContainer.appendChild(typingDiv);
        scrollToBottom();
    }
    
    // Hide typing indicator
    function hideTypingIndicator() {
        const typingIndicator = document.getElementById('typing-indicator');
        if (typingIndicator) {
            typingIndicator.remove();
        }
    }
    
    // Scroll to the bottom of the chat
    function scrollToBottom() {
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
    }
    
    // Send message to the server
    async function sendMessage(message) {
        showTypingIndicator();
        
        try {
            const response = await fetch('/api/chat', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    message: message,
                    conversation_id: conversationId
                })
            });
            
            const data = await response.json();
            
            if (data.status === 'success') {
                conversationId = data.conversation_id;
                hideTypingIndicator();
                addBotMessage(data.response);
            } else {
                throw new Error(data.error || 'Unknown error occurred');
            }
        } catch (error) {
            console.error('Error:', error);
            hideTypingIndicator();
            addBotMessage('Es ist ein Fehler aufgetreten. Bitte versuche es später noch einmal.');
        }
    }
    
    // Handle form submission
    form.addEventListener('submit', function(e) {
        e.preventDefault();
        const message = messageInput.value.trim();
        
        if (message) {
            // Add user message to chat
            addMessage(message, true);
            messageInput.value = '';
            
            // Send message to server
            sendMessage(message);
        }
    });
    
    // Handle send button click
    sendButton.addEventListener('click', function() {
        form.dispatchEvent(new Event('submit'));
    });
    
    // Allow sending message with Enter key
    messageInput.addEventListener('keypress', function(e) {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            form.dispatchEvent(new Event('submit'));
        }
    });
    
    // Initialize the chat when the page loads
    initChat();
});
