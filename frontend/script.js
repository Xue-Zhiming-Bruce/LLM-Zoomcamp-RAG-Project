class RAGChatApp {
    constructor() {
        this.apiBaseUrl = window.location.origin;
        this.initializeElements();
        this.bindEvents();
        this.checkServerStatus();
    }

    initializeElements() {
        this.chatMessages = document.getElementById('chatMessages');
        this.questionInput = document.getElementById('questionInput');
        this.sendButton = document.getElementById('sendButton');
        this.loadingOverlay = document.getElementById('loadingOverlay');
        this.statusIndicator = document.getElementById('statusIndicator');
        this.statusText = document.getElementById('statusText');
    }

    bindEvents() {
        // Send button click
        this.sendButton.addEventListener('click', () => this.sendMessage());

        // Enter key handling
        this.questionInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.sendMessage();
            }
        });

        // Auto-resize textarea
        this.questionInput.addEventListener('input', () => {
            this.autoResizeTextarea();
        });
    }

    autoResizeTextarea() {
        this.questionInput.style.height = 'auto';
        this.questionInput.style.height = Math.min(this.questionInput.scrollHeight, 120) + 'px';
    }

    async checkServerStatus() {
        try {
            const response = await fetch(`${this.apiBaseUrl}/api/health`);
            const data = await response.json();
            
            if (data.status === 'healthy') {
                this.updateStatus('connected', 'Connected');
            } else {
                this.updateStatus('error', 'Server issues detected');
            }
        } catch (error) {
            this.updateStatus('error', 'Server not available');
            console.error('Health check failed:', error);
        }
    }

    updateStatus(type, message) {
        this.statusIndicator.className = `status-indicator ${type}`;
        this.statusText.textContent = message;
    }

    showLoading() {
        this.loadingOverlay.classList.add('show');
        this.sendButton.disabled = true;
        this.updateStatus('loading', 'Processing...');
    }

    hideLoading() {
        this.loadingOverlay.classList.remove('show');
        this.sendButton.disabled = false;
        this.updateStatus('connected', 'Ready');
    }

    addMessage(content, isUser = false, sources = null) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${isUser ? 'user-message' : 'bot-message'}`;

        const messageContent = document.createElement('div');
        messageContent.className = 'message-content';

        if (typeof content === 'string') {
            // Handle text content
            const paragraphs = content.split('\n').filter(p => p.trim());
            paragraphs.forEach(paragraph => {
                const p = document.createElement('p');
                p.textContent = paragraph;
                messageContent.appendChild(p);
            });
        } else {
            // Handle HTML content
            messageContent.appendChild(content);
        }

        // Add sources if provided
        if (sources && sources.length > 0) {
            const sourcesDiv = this.createSourcesElement(sources);
            messageContent.appendChild(sourcesDiv);
        }

        messageDiv.appendChild(messageContent);
        this.chatMessages.appendChild(messageDiv);
        this.scrollToBottom();
    }

    createSourcesElement(sources) {
        const sourcesDiv = document.createElement('div');
        sourcesDiv.className = 'sources';

        const title = document.createElement('h4');
        title.textContent = `📚 Sources (${sources.length})`;
        sourcesDiv.appendChild(title);

        sources.forEach((source, index) => {
            const sourceItem = document.createElement('div');
            sourceItem.className = 'source-item';

            const sourceTitle = document.createElement('div');
            sourceTitle.className = 'source-title';
            sourceTitle.textContent = source.title;

            const sourceTag = document.createElement('span');
            sourceTag.className = 'source-tag';
            sourceTag.textContent = source.tag;

            const sourceScore = document.createElement('span');
            sourceScore.className = 'source-score';
            sourceScore.textContent = `${(source.score * 100).toFixed(1)}%`;

            const sourcePreview = document.createElement('div');
            sourcePreview.className = 'source-preview';
            sourcePreview.textContent = source.content_preview;

            sourceItem.appendChild(sourceTitle);
            sourceItem.appendChild(sourceTag);
            sourceItem.appendChild(sourceScore);
            sourceItem.appendChild(sourcePreview);

            sourcesDiv.appendChild(sourceItem);
        });

        return sourcesDiv;
    }

    scrollToBottom() {
        this.chatMessages.scrollTop = this.chatMessages.scrollHeight;
    }

    async sendMessage() {
        const question = this.questionInput.value.trim();
        if (!question) return;

        // Add user message
        this.addMessage(question, true);
        
        // Clear input
        this.questionInput.value = '';
        this.autoResizeTextarea();

        // Show loading
        this.showLoading();

        try {
            const response = await fetch(`${this.apiBaseUrl}/api/chat`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    query: question,
                    limit: 5
                })
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const data = await response.json();
            
            // Add bot response
            this.addMessage(data.answer, false, data.sources);

        } catch (error) {
            console.error('Error sending message:', error);
            
            let errorMessage = 'Sorry, I encountered an error while processing your question. ';
            
            if (error.message.includes('fetch')) {
                errorMessage += 'Please check if the server is running and try again.';
            } else if (error.message.includes('500')) {
                errorMessage += 'There was a server error. Please try again later.';
            } else {
                errorMessage += 'Please try again or rephrase your question.';
            }

            this.addMessage(errorMessage, false);
        } finally {
            this.hideLoading();
        }
    }

    // Utility method to format text with basic markdown-like formatting
    formatText(text) {
        return text
            .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
            .replace(/\*(.*?)\*/g, '<em>$1</em>')
            .replace(/`(.*?)`/g, '<code>$1</code>');
    }
}

// Initialize the app when the DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    new RAGChatApp();
});

// Add some helpful keyboard shortcuts
document.addEventListener('keydown', (e) => {
    // Focus on input when typing (if not already focused)
    if (e.key.length === 1 && document.activeElement !== document.getElementById('questionInput')) {
        document.getElementById('questionInput').focus();
    }
});