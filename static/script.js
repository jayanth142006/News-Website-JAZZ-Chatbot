// Function to send a message
function sendMessage() {
    let userInput = document.getElementById("user-input").value.trim();
    if (userInput === "") return;

    let chatBox = document.getElementById("chat-box");

    // Add user message to chat
    let userMessage = `<div class="user-message">${userInput}</div>`;
    chatBox.innerHTML += userMessage;
    document.getElementById("user-input").value = "";

    chatBox.scrollTop = chatBox.scrollHeight;

    document.getElementById("loading-overlay").style.display = "flex";

    fetch("/chat", {
        method: "POST",
        body: JSON.stringify({ message: userInput }),
        headers: { "Content-Type": "application/json" }
    })
    .then(response => response.json())
    .then(data => {
        let botMessage = `<div class="bot-message">${formatBotResponse(data.response)}</div>`;
        chatBox.innerHTML += botMessage;
        chatBox.scrollTop = chatBox.scrollHeight;
    })
    .catch(error => {
        console.error("Error fetching news:", error);
        chatBox.innerHTML += `<div class="bot-message error">Oops! Something went wrong. Please try again.</div>`;
    })
    .finally(() => {
        document.getElementById("loading-overlay").style.display = "none";
        document.getElementById("user-input").focus();
    });
}

// Handle Enter key
function handleKeyPress(event) {
    if (event.key === "Enter") {
        sendMessage();
    }
}

// Format the bot response and insert Read More buttons
function formatBotResponse(response) {
    return response.replace(/\n/g, "<br><br>").replace(/\[Read More\]\((.*?)\)/g, function (_, url) {
        return `<button class="read-more-btn" onclick="fetchFullSummary('${url}')">Read More</button>`;
    });
}

// ✅ Updated: Fetch full article summary and add to chat
function fetchFullSummary(url) {
    document.getElementById("loading-overlay").style.display = "flex";

    fetch("/read_more", {
        method: "POST",
        body: JSON.stringify({ url }),
        headers: { "Content-Type": "application/json" }
    })
    .then(response => response.json())
    .then(data => {
        let chatBox = document.getElementById("chat-box");
        let summaryMessage = `
            <div class="bot-message">
                <strong>News Details:</strong><br>${data.summary.replace(/\n/g, "<br>")}
            </div>
        `;
        chatBox.innerHTML += summaryMessage;
        chatBox.scrollTop = chatBox.scrollHeight;
    })
    .catch(error => {
        console.error("Error fetching summary:", error);
        let chatBox = document.getElementById("chat-box");
        chatBox.innerHTML += `<div class="bot-message error">Unable to fetch detailed news. Please try again.</div>`;
    })
    .finally(() => {
        document.getElementById("loading-overlay").style.display = "none";
    });
}

// ✅ Remove modal-related function
// function closeSummary() { ... } — no longer needed

// Hide loading screen on load
window.onload = function () {
    document.getElementById("loading-overlay").style.display = "none";
};

// 🎙️ Voice Recognition
const voiceButton = document.getElementById("voice-button");
const userInput = document.getElementById("user-input");

voiceButton.addEventListener("click", () => {
    let recognition = new (window.SpeechRecognition || window.webkitSpeechRecognition)();
    recognition.lang = "en-US";
    recognition.start();

    recognition.onstart = function () {
        voiceButton.innerHTML = "🎤 Listening...";
    };

    recognition.onspeechend = function () {
        recognition.stop();
        voiceButton.innerHTML = "🎙️";
    };

    recognition.onresult = function (event) {
        let transcript = event.results[0][0].transcript;
        userInput.value = transcript;
        sendMessage();
    };

    recognition.onerror = function (event) {
        console.error("Speech recognition error:", event.error);
        alert("Speech recognition failed. Please try again.");
    };
});

