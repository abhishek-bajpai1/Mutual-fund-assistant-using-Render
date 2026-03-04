const form = document.getElementById('chat-form');
const input = document.getElementById('user-input');
const sendBtn = document.getElementById('send-btn');
const messagesArea = document.getElementById('chat-messages');
const welcomeScreen = document.getElementById('welcome-screen');
const restartBtn = document.getElementById('restart-btn');
const fullscreenBtn = document.getElementById('fullscreen-btn');

let isFirstMessage = true;

// Fullscreen Toggle Logic
fullscreenBtn.addEventListener('click', () => {
    if (!document.fullscreenElement) {
        document.documentElement.requestFullscreen().catch((err) => {
            console.error(`Error attempting to enable fullscreen: ${err.message}`);
        });
    } else {
        document.exitFullscreen();
    }
});

// Restart Conversation Logic
restartBtn.addEventListener('click', () => {
    // 1. Remove all dynamically added chat bubbles
    const messages = document.querySelectorAll('.message');
    messages.forEach(msg => msg.remove());

    // 2. Restore Welcome Screen
    welcomeScreen.style.display = 'block';
    isFirstMessage = true;

    // 3. Clear input
    input.value = '';
    sendBtn.classList.add('hidden');
});

// Show/hide send button based on input
input.addEventListener('input', () => {
    if (input.value.trim().length > 0) {
        sendBtn.classList.remove('hidden');
    } else {
        sendBtn.classList.add('hidden');
    }
});

// Auto-scroll wrapper
function scrollToBottom() {
    messagesArea.scrollTop = messagesArea.scrollHeight;
}

// Format the API response string into HTML with citations
function formatResponse(data) {
    let html = `<div>${data.answer.replace(/\\n/g, '<br/>')}</div>`;

    // Append clickable source links if provided by the Phase 4 engine
    if (data.sources && data.sources.length > 0) {
        // Parse the scraped timestamp from the JSON metadata
        let timeStr = "Unknown time";
        if (data.last_updated && data.last_updated !== "Unknown time") {
            try {
                const scrapedDate = new Date(data.last_updated);
                timeStr = scrapedDate.toLocaleString([], {
                    year: 'numeric', month: 'short', day: 'numeric',
                    hour: '2-digit', minute: '2-digit'
                });
            } catch (e) {
                timeStr = data.last_updated; // Fallback to raw string if parsing fails
            }
        }

        // Exact wording as requested by user
        let citationHtml = `<br><br>Last updated from sources : ${timeStr}<br>Sources:<br>`;

        const uniqueSources = [...new Set(data.sources)];
        const links = uniqueSources.map(url => {
            return `<a href="${url}" target="_blank" rel="noopener noreferrer">${url}</a>`;
        });

        citationHtml += links.join('<br>');

        html += `<div class="citation">${citationHtml}</div>`;
    }

    return html;
}

// Append chat bubbles
function appendMessage(role, contentHtml) {
    const div = document.createElement('div');
    div.className = `message ${role}`;

    const contentDiv = document.createElement('div');
    contentDiv.className = 'message-content';
    contentDiv.innerHTML = contentHtml;

    div.appendChild(contentDiv);
    messagesArea.appendChild(div);
    scrollToBottom();
}

// Show animated typing bubbles
function createTypingIndicator() {
    const div = document.createElement('div');
    div.className = 'message assistant typing-container';

    const contentDiv = document.createElement('div');
    contentDiv.className = 'message-content';

    for (let i = 0; i < 3; i++) {
        const dot = document.createElement('div');
        dot.className = 'dot';
        contentDiv.appendChild(dot);
    }

    div.appendChild(contentDiv);
    return div;
}

// Function triggered by the suggested prompt buttons
window.submitPrompt = function (promptText) {
    input.value = promptText;
    sendBtn.classList.remove('hidden');

    // Programmatically trigger a submit event
    const event = new Event('submit', { cancelable: true });
    form.dispatchEvent(event);
};


// Handle Chat Submission
form.addEventListener('submit', async (e) => {
    e.preventDefault();

    const query = input.value.trim();
    if (!query) return;

    // Hide welcome screen on first interaction
    if (isFirstMessage) {
        welcomeScreen.style.display = 'none';
        isFirstMessage = false;
    }

    // Process UI State
    appendMessage('user', query);
    input.value = '';
    sendBtn.classList.add('hidden');

    const typingIndicator = createTypingIndicator();
    messagesArea.appendChild(typingIndicator);
    scrollToBottom();

    try {
        // FastAPI Request
        const response = await fetch('/api/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ query: query })
        });

        const data = await response.json();
        typingIndicator.remove();

        if (!response.ok) {
            appendMessage('assistant', `Error: ${data.detail || 'Failed to connect to server.'}`);
            return;
        }

        appendMessage('assistant', formatResponse(data));

    } catch (error) {
        typingIndicator.remove();
        appendMessage('assistant', `Network Error: Could not reach the server. Make sure FastAPI is running.`);
        console.error(error);
    }
});

// Dropdown Menu Logic
const headerTitle = document.getElementById('header-title');
const dropdownMenu = document.getElementById('dropdown-menu');
const dropdownIcon = document.getElementById('dropdown-icon');

headerTitle.addEventListener('click', (e) => {
    e.stopPropagation(); // Prevent immediate closing
    dropdownMenu.classList.toggle('hidden');
    if (dropdownMenu.classList.contains('hidden')) {
        dropdownIcon.style.transform = 'rotate(0deg)';
    } else {
        dropdownIcon.style.transform = 'rotate(180deg)';
    }
});

// Close dropdown when clicking outside
window.addEventListener('click', (e) => {
    if (!dropdownMenu.classList.contains('hidden') && !dropdownMenu.contains(e.target) && !headerTitle.contains(e.target)) {
        dropdownMenu.classList.add('hidden');
        dropdownIcon.style.transform = 'rotate(0deg)';
    }
});
