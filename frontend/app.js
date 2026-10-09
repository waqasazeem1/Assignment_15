// ==========================================================================
// AI Multi-Agent Assistant - Clean Interactive Frontend Logic
// ==========================================================================

document.addEventListener("DOMContentLoaded", () => {
  const chatForm = document.getElementById("chat-form");
  const userInput = document.getElementById("user-input");
  const sendBtn = document.getElementById("send-btn");
  const chatMessages = document.getElementById("chat-messages");
  const fileInput = document.getElementById("pdf-file-input");
  const pdfCountBadge = document.getElementById("pdf-count-badge");
  const traceRoutedAgent = document.getElementById("trace-routed-agent");
  const traceRoutingReason = document.getElementById("trace-routing-reason");
  const clearChatBtn = document.getElementById("clear-chat-btn");

  // Fetch initial system status
  fetchSystemStatus();
  checkEmailConfig();

  // Clear chat
  if (clearChatBtn) {
    clearChatBtn.addEventListener("click", () => {
      chatMessages.innerHTML = "";
      if (traceRoutedAgent) traceRoutedAgent.textContent = "Supervisor";
      if (traceRoutingReason) traceRoutingReason.textContent = "Chat cleared. Ready for next query.";
    });
  }

  // Handle general chat message submission
  chatForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const query = userInput.value.trim();
    if (!query) return;

    userInput.value = "";
    userInput.style.height = "auto";
    sendBtn.disabled = true;

    // Show user message
    appendMessage("user", query);

    if (traceRoutedAgent) traceRoutedAgent.textContent = "Supervisor (Routing...)";
    if (traceRoutingReason) traceRoutingReason.textContent = "Processing query...";

    try {
      const response = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: query }),
      });

      if (!response.ok) {
        throw new Error(`Server returned status ${response.status}`);
      }

      const data = await response.json();

      if (traceRoutedAgent) {
        traceRoutedAgent.textContent = formatAgentName(data.active_agent);
      }
      if (traceRoutingReason) {
        traceRoutingReason.textContent = data.routing_reason || "Direct routing";
      }

      appendMessage(data.active_agent, data.reply);
    } catch (err) {
      appendMessage("supervisor", `Error connecting to agent: ${err.message}`);
      if (traceRoutedAgent) traceRoutedAgent.textContent = "Error";
    } finally {
      sendBtn.disabled = false;
      userInput.focus();
    }
  });

  // Auto-expand textarea
  userInput.addEventListener("input", () => {
    userInput.style.height = "auto";
    userInput.style.height = Math.min(userInput.scrollHeight, 120) + "px";
  });

  // Enter sends, Shift+Enter for newline
  userInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      chatForm.dispatchEvent(new Event("submit"));
    }
  });

  // PDF File Input change
  fileInput.addEventListener("change", () => {
    if (fileInput.files.length > 0) {
      uploadPDF(fileInput.files[0]);
    }
  });

  async function uploadPDF(file) {
    if (!file.name.toLowerCase().endsWith(".pdf")) {
      alert("Please upload a PDF file.");
      return;
    }

    appendMessage("user", `📎 Uploading & analyzing document "${file.name}"...`);
    if (traceRoutedAgent) traceRoutedAgent.textContent = "RAG Sub-Agent";
    if (traceRoutingReason) traceRoutingReason.textContent = `Reading ${file.name} and generating step-by-step briefing...`;

    const formData = new FormData();
    formData.append("file", file);

    try {
      const res = await fetch("/api/upload-pdf", {
        method: "POST",
        body: formData,
      });

      const data = await res.json();
      if (res.ok) {
        if (pdfCountBadge) {
          pdfCountBadge.textContent = "Active: " + file.name.slice(0, 12) + "...";
        }
        fetchSystemStatus();

        // Render the step-by-step document brief directly in chat!
        const briefContent = data.briefing || "Document analyzed successfully.";
        appendMessage("rag_agent", briefContent);

        if (traceRoutingReason) {
          traceRoutingReason.textContent = `Completed step-by-step briefing for ${file.name}`;
        }
      } else {
        appendMessage("rag_agent", `❌ Failed to process PDF: ${data.detail || "Upload error"}`);
      }
    } catch (err) {
      appendMessage("rag_agent", `❌ Network error uploading PDF: ${err.message}`);
    }
  }

  async function fetchSystemStatus() {
    try {
      const res = await fetch("/api/status");
      if (!res.ok) return;
      const data = await res.json();
      if (data.sub_agents && data.sub_agents.rag_agent && pdfCountBadge) {
        const count = data.sub_agents.rag_agent.indexed_chunks;
        if (!pdfCountBadge.textContent.startsWith("Memory:")) {
          pdfCountBadge.textContent = `${count} Chunks Indexed`;
        }
      }
    } catch (err) {
      console.warn("Status fetch failed:", err);
    }
  }

  function appendMessage(sender, rawContent) {
    const isUser = sender === "user";
    const msgDiv = document.createElement("div");
    msgDiv.className = `message ${isUser ? "user-msg" : "assistant-msg"}`;

    const meta = getAgentMeta(sender);

    // Markdown rendering
    let renderedHtml = rawContent;
    if (typeof marked !== "undefined" && marked.parse) {
      renderedHtml = marked.parse(rawContent);
    } else {
      renderedHtml = `<p>${rawContent.replace(/\n/g, "<br>")}</p>`;
    }

    // Ensure links open in new tab and Google Calendar link gets dedicated button style
    try {
      const tempDiv = document.createElement("div");
      tempDiv.innerHTML = renderedHtml;
      tempDiv.querySelectorAll("a").forEach((a) => {
        a.setAttribute("target", "_blank");
        a.setAttribute("rel", "noopener noreferrer");
        if (a.href && a.href.includes("calendar.google.com")) {
          a.classList.add("gcal-btn");
        }
        if (a.href && a.href.includes("mail.google.com")) {
          a.classList.add("gmail-btn");
        }
      });
      renderedHtml = tempDiv.innerHTML;
    } catch (_) {}

    const timeStr = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });

    msgDiv.innerHTML = `
      <div class="msg-avatar-box">${meta.avatar}</div>
      <div class="msg-bubble">
        <div class="msg-header">
          <span class="agent-tag ${meta.badgeClass}">${meta.name}</span>
          <span class="msg-time">${timeStr}</span>
        </div>
        <div class="msg-content">${renderedHtml}</div>
      </div>
    `;

    chatMessages.appendChild(msgDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;
  }

  function getAgentMeta(agentKey) {
    switch (agentKey) {
      case "user":
        return { name: "You", avatar: "👤", badgeClass: "" };
      case "rag_agent":
        return { name: "RAG Agent", avatar: "📄", badgeClass: "rag-badge" };
      case "github_agent":
        return { name: "GitHub Agent", avatar: "🐙", badgeClass: "github-badge" };
      case "calendar_agent":
        return { name: "Calendar Agent", avatar: "📅", badgeClass: "calendar-badge" };
      case "email_agent":
        return { name: "Gmail Agent", avatar: "✉️", badgeClass: "email-badge" };
      case "supervisor":
      default:
        return { name: "Supervisor", avatar: "⚡", badgeClass: "supervisor-badge" };
    }
  }

  function formatAgentName(key) {
    if (key === "rag_agent") return "RAG Sub-Agent";
    if (key === "github_agent") return "GitHub Sub-Agent";
    if (key === "calendar_agent") return "Calendar Sub-Agent";
    if (key === "email_agent") return "Gmail Sub-Agent";
    return "Supervisor";
  }

  // Export functions to window
  window.triggerPdfUpload = () => {
    if (fileInput) fileInput.click();
  };

  window.setQuery = (text) => {
    if (userInput && chatForm) {
      userInput.value = text;
      chatForm.dispatchEvent(new Event("submit"));
    }
  };

  window.appendMessage = appendMessage;
  window.updateRouting = (agent, reason) => {
    if (traceRoutedAgent) traceRoutedAgent.textContent = formatAgentName(agent);
    if (traceRoutingReason) traceRoutingReason.textContent = reason;
  };
});

// ==========================================================================
// Modal Control & Specific Form Submissions
// ==========================================================================

function openModal(modalId) {
  const backdrop = document.getElementById("modal-backdrop");
  const modal = document.getElementById(modalId);
  if (backdrop) backdrop.style.display = "block";
  if (modal) {
    modal.style.display = "flex";
    const firstInput = modal.querySelector("input, textarea");
    if (firstInput) setTimeout(() => firstInput.focus(), 100);
  }
}

function closeAllModals() {
  const backdrop = document.getElementById("modal-backdrop");
  if (backdrop) backdrop.style.display = "none";
  document.querySelectorAll(".app-modal").forEach((m) => {
    m.style.display = "none";
  });
}

// 1. Handle GitHub Username Form Submit
async function handleGithubSubmit(e) {
  e.preventDefault();
  const usernameInput = document.getElementById("input-github-username");
  const username = (usernameInput ? usernameInput.value : "").trim().replace(/^@/, "");
  if (!username) return;

  closeAllModals();

  if (window.appendMessage) {
    window.appendMessage("user", `Search GitHub user: @${username}`);
  }
  if (window.updateRouting) {
    window.updateRouting("github_agent", `Querying GitHub API for user: ${username}`);
  }

  try {
    const res = await fetch("/api/github-user", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username: username }),
    });

    const data = await res.json();
    if (res.ok && window.appendMessage) {
      window.appendMessage("github_agent", data.reply);
    } else if (window.appendMessage) {
      window.appendMessage("github_agent", `❌ Error fetching user: ${data.detail || "User not found"}`);
    }
  } catch (err) {
    if (window.appendMessage) {
      window.appendMessage("github_agent", `❌ Network error querying GitHub: ${err.message}`);
    }
  }
}

// 2. Handle Calendar Meeting Schedule Form Submit
async function handleCalendarSubmit(e) {
  e.preventDefault();
  const title = document.getElementById("input-calendar-title").value.trim();
  const datetime = document.getElementById("input-calendar-datetime").value.trim();
  const email = document.getElementById("input-calendar-email").value.trim();
  const draft = document.getElementById("input-calendar-draft").value.trim();

  if (!email || !datetime) {
    alert("Please provide both meeting time and attendee email.");
    return;
  }

  closeAllModals();

  if (window.appendMessage) {
    window.appendMessage("user", `Fix Meeting: "${title}" on ${datetime} with ${email}\nEmail Draft: "${draft}"`);
  }
  if (window.updateRouting) {
    window.updateRouting("calendar_agent", `Scheduling meeting and dispatching email to ${email}`);
  }

  try {
    const res = await fetch("/api/schedule-meeting", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        title: title || "Project Strategy Meeting",
        start_time: datetime,
        email: email,
        draft_message: draft,
      }),
    });

    const data = await res.json();
    if (res.ok && window.appendMessage) {
      window.appendMessage("calendar_agent", data.reply);

      // Automatically open Google Calendar in browser with Meet link and event pre-filled
      if (data.gcal_url) {
        try {
          const newTab = window.open(data.gcal_url, "_blank");
          if (!newTab || newTab.closed || typeof newTab.closed === "undefined") {
            console.log("Popup blocker may have blocked automatic tab. User can click the link in chat.");
          }
        } catch (_) {}
      }
    } else if (window.appendMessage) {
      window.appendMessage("calendar_agent", `❌ Scheduling failed: ${data.detail || "Error"}`);
    }
  } catch (err) {
    if (window.appendMessage) {
      window.appendMessage("calendar_agent", `❌ Network error scheduling meeting: ${err.message}`);
    }
  }
}

// 3. Handle Gmail Direct Send Form Submit
async function handleEmailSubmit(e) {
  e.preventDefault();
  const to = document.getElementById("input-email-to").value.trim();
  const subject = document.getElementById("input-email-subject").value.trim();
  const body = document.getElementById("input-email-body").value.trim();

  if (!to || !body) {
    alert("Please provide both recipient email and message body.");
    return;
  }

  closeAllModals();

  if (window.appendMessage) {
    window.appendMessage("user", `Send Email to: ${to}\nSubject: ${subject}\nMessage: "${body}"`);
  }
  if (window.updateRouting) {
    window.updateRouting("email_agent", `Dispatching email to ${to}`);
  }

  try {
    const res = await fetch("/api/send-email", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        to: to,
        subject: subject || "Important Notification",
        body: body,
      }),
    });

    const data = await res.json();
    if (res.ok && window.appendMessage) {
      window.appendMessage("email_agent", data.reply);
    } else if (window.appendMessage) {
      window.appendMessage("email_agent", `❌ Email sending failed: ${data.detail || "Error"}`);
    }
  } catch (err) {
    if (window.appendMessage) {
      window.appendMessage("email_agent", `❌ Network error sending email: ${err.message}`);
    }
  }
}

// 4. Handle Gmail SMTP Setup Form Submit
async function handleEmailSettingsSubmit(e) {
  e.preventDefault();
  const emailInput = document.getElementById("input-setup-email");
  const passInput = document.getElementById("input-setup-password");
  const statusBox = document.getElementById("email-setup-status-box");
  const submitBtn = document.getElementById("btn-save-email-setup");

  const email = emailInput ? emailInput.value.trim() : "";
  const password = passInput ? passInput.value.trim() : "";

  if (!email || !password) return;

  if (submitBtn) {
    submitBtn.disabled = true;
    submitBtn.textContent = "Connecting & Testing...";
  }
  if (statusBox) {
    statusBox.style.display = "block";
    statusBox.style.background = "#eff6ff";
    statusBox.style.color = "#1d4ed8";
    statusBox.style.border = "1px solid #bfdbfe";
    statusBox.textContent = "Testing connection with smtp.gmail.com:587...";
  }

  try {
    const res = await fetch("/api/settings/email", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        sender_email: email,
        app_password: password
      })
    });

    const data = await res.json();
    if (res.ok) {
      if (statusBox) {
        statusBox.style.background = "#ecfdf5";
        statusBox.style.color = "#065f46";
        statusBox.style.border = "1px solid #a7f3d0";
        statusBox.textContent = "✅ " + data.message;
      }
      if (submitBtn) submitBtn.textContent = "Saved & Verified!";

      updateEmailStatusUI(true, email);
      setTimeout(() => {
        closeAllModals();
        if (submitBtn) {
          submitBtn.disabled = false;
          submitBtn.textContent = "Test & Save Connection";
        }
      }, 1500);
    } else {
      if (statusBox) {
        statusBox.style.background = "#fef2f2";
        statusBox.style.color = "#991b1b";
        statusBox.style.border = "1px solid #fecaca";
        statusBox.textContent = "❌ " + (data.detail || "Authentication failed. Please verify credentials.");
      }
      if (submitBtn) {
        submitBtn.disabled = false;
        submitBtn.textContent = "Try Again";
      }
    }
  } catch (err) {
    if (statusBox) {
      statusBox.style.background = "#fef2f2";
      statusBox.style.color = "#991b1b";
      statusBox.style.border = "1px solid #fecaca";
      statusBox.textContent = "❌ Network error: " + err.message;
    }
    if (submitBtn) {
      submitBtn.disabled = false;
      submitBtn.textContent = "Try Again";
    }
  }
}

async function checkEmailConfig() {
  try {
    const res = await fetch("/api/settings/email");
    if (res.ok) {
      const data = await res.json();
      updateEmailStatusUI(data.configured, data.sender_email);
      const emailInput = document.getElementById("input-setup-email");
      if (data.configured && emailInput && !emailInput.value) {
        emailInput.value = data.sender_email;
      }
    }
  } catch (_) {}
}

function updateEmailStatusUI(isConfigured, senderEmail) {
  const badgeText = document.getElementById("email-setup-badge-text");
  
  // 1. Calendar Banner
  const calBanner = document.getElementById("calendar-email-status-banner");
  const calIcon = document.getElementById("calendar-banner-icon");
  const calText = document.getElementById("calendar-banner-text");

  // 2. Direct Email Banner
  const mailBanner = document.getElementById("email-sender-status-banner");
  const mailIcon = document.getElementById("email-sender-banner-icon");
  const mailText = document.getElementById("email-sender-banner-text");

  if (isConfigured) {
    if (badgeText) badgeText.textContent = `🟢 Gmail Active (${senderEmail ? senderEmail.split('@')[0] : 'Live'})`;
    
    [calBanner, mailBanner].forEach(b => {
      if (b) {
        b.style.background = "#ecfdf5";
        b.style.color = "#065f46";
        b.style.border = "1px solid #a7f3d0";
      }
    });

    if (calIcon) calIcon.textContent = "✅";
    if (calText) calText.textContent = `Live Email Active. Real invites will be sent from: ${senderEmail}`;

    if (mailIcon) mailIcon.textContent = "✅";
    if (mailText) mailText.textContent = `Live Email Active. Emails will be sent from: ${senderEmail}`;
  } else {
    if (badgeText) badgeText.textContent = "⚙️ Setup Gmail";
    
    [calBanner, mailBanner].forEach(b => {
      if (b) {
        b.style.background = "#fef3c7";
        b.style.color = "#92400e";
        b.style.border = "1px solid #fde68a";
      }
    });

    if (calIcon) calIcon.textContent = "⚠️";
    if (calText) calText.textContent = "Live Email inactive. Attendee ko asli inbox email bhejne ke liye Gmail setup karein.";

    if (mailIcon) mailIcon.textContent = "⚠️";
    if (mailText) mailText.textContent = "Live Email inactive. Asli inbox mein email bhejne ke liye Gmail setup karein.";
  }
}
