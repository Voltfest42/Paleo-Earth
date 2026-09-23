/**
 * chat.js — Right-panel AI chat and summary card
 *
 * Responsibilities:
 *  - Display the static summary for the active keyframe
 *  - Maintain a persistent conversation history across keyframe changes
 *  - Send user messages to the AI (mock in DEV_MODE, Lambda in prod)
 *  - Render AI responses with inline image resolution ([[IMAGE: tag]])
 *  - Speaker buttons on summary and each AI response
 */

import { DEV_MODE, API_BASE } from './config.js';
import { speak } from './tts.js';

// ─── Markdown → simple HTML ───────────────────────────────────────────────
function simpleMarkdown(text) {
  if (!text) return '';
  return text
    .replace(/\[\[IMAGE:[^\]]*\]\]/gi, '') // strip image tags (handled separately)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    .replace(/`(.+?)`/g, '<code>$1</code>')
    .replace(/\n\n+/g, '</p><p>')
    .replace(/\n/g, '<br>')
    .trim();
}

// ─── Image tag resolution ─────────────────────────────────────────────────
function resolveImages(text, imageLibrary) {
  if (!imageLibrary) return { html: simpleMarkdown(text), images: [] };

  const pattern = /\[\[IMAGE:\s*([^\]]+)\]\]/gi;
  const matched = [];
  let m;

  while ((m = pattern.exec(text)) !== null) {
    const rawTag = m[1].trim().toLowerCase();
    const tag = rawTag.replace(/[()_.,]/g, ' ').replace(/\s+/g, ' ').trim();

    // 1. Exact or bidirectional match on title, ID, or tags
    let entry = imageLibrary.find(img => {
      const imgTitle = (img.title || '').toLowerCase();
      const imgId = (img.id || '').toLowerCase().replace(/_/g, ' ');
      if (imgId === tag || imgTitle === tag) return true;
      if (imgTitle.includes(tag) || tag.includes(imgTitle)) return true;
      if (imgId.includes(tag) || tag.includes(imgId)) return true;
      return (img.tags || []).some(t => {
        const tClean = t.toLowerCase().replace(/_/g, ' ');
        return tClean === tag || tag.includes(tClean) || tClean.includes(tag);
      });
    });

    // 2. Fallback: match significant words in tag against title/tags
    if (!entry) {
      const tagWords = tag.split(' ').filter(w => w.length > 3);
      entry = imageLibrary.find(img => {
        const titleWords = (img.title || '').toLowerCase().split(' ');
        return tagWords.some(tw => titleWords.includes(tw));
      });
    }

    if (entry && !matched.some(existing => existing.id === entry.id)) {
      matched.push(entry);
    }
  }

  return { html: simpleMarkdown(text), images: matched };
}

// ─── DEV mock response ────────────────────────────────────────────────────
async function mockChat(messages, context) {
  await new Promise(r => setTimeout(r, 700 + Math.random() * 600));

  const period = context?.label || 'this period';
  const ma     = context?.ma    || '?';

  const starters = [
    `Great question about ${period} (${ma} Ma)!`,
    `During ${period}, approximately ${ma} million years ago,`,
    `${period} is a fascinating chapter in Earth's history.`,
  ];
  const starter = starters[Math.floor(Math.random() * starters.length)];

  return `[DEV MODE] ${starter} This is a placeholder response generated locally — no AWS connection is needed in development mode.\n\nIn production, this response would come from Claude via Amazon Bedrock with detailed, scientifically accurate information about the paleogeography, climate, and life of this period. You can set DEV_MODE = false in js/config.js to switch to the live API once your Lambda is deployed.\n\nFeel free to explore the timeline and test the full UI flow. Your conversation history is being maintained across keyframe changes.`;
}

// ─── Prod: call Lambda /chat ───────────────────────────────────────────────
async function prodChat(messages, context, userMessage) {
  const res = await fetch(`${API_BASE}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ messages, systemContext: context, userMessage }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.error || `API error ${res.status}`);
  }
  const data = await res.json();
  return data.reply || data.response || '';
}

// ─── Chat class ───────────────────────────────────────────────────────────
export class Chat {
  /**
   * @param {object}   elements         — DOM element references
   * @param {object[]} imageLibrary     — image-library.json images array
   */
  constructor(elements, imageLibrary) {
    this._el          = elements;
    this._imageLib    = imageLibrary || [];
    this._history     = [];   // [{role, content}] full conversation
    this._context     = null; // current keyframe context
    this._sending     = false;
    this._summaryText = '';
    this._lastCommittedKeyframeId = 'holocene';
    this._pendingDividerEl = null;

    this._attach();
  }

  // ── Event listeners ───────────────────────────────────────────────────
  _attach() {
    // Send on button click
    this._el.sendBtn.addEventListener('click', () => this._sendUserMessage());

    // Send on Enter key
    this._el.chatInput.addEventListener('keydown', e => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        this._sendUserMessage();
      }
    });

    // Summary TTS button
    this._el.summaryTtsBtn.addEventListener('click', () => {
      const text = this._el.summarySubtitle.textContent + '. ' + this._summaryText;
      speak(text, this._el.summaryTtsBtn);
    });
  }

  // ── Keyframe update ───────────────────────────────────────────────────

  /**
   * Called immediately in real-time when the active keyframe changes.
   * Updates summary card UI without cluttering the chat history.
   * @param {object} keyframe  — keyframe object from keyframes.json
   * @param {object} summary   — summary object from summaries.json
   */
  setKeyframe(keyframe, summary) {
    if (!keyframe || !summary) return;

    this._context = keyframe;

    // Update summary card in real-time
    this._el.keyframeTitle.textContent   = keyframe.label;
    this._el.summarySubtitle.textContent = summary.subtitle || '';
    this._summaryText = summary.body || '';
    this._el.summaryText.textContent = this._summaryText;

    // Badge style (period vs event)
    const badge = this._el.keyframeBadge;
    badge.textContent = keyframe.type === 'event' ? 'Event' : keyframe.period || 'Period';
    badge.className   = `keyframe-badge${keyframe.type === 'event' ? ' event' : ''}`;
  }

  /**
   * Called when the slider has stopped moving on a keyframe.
   * Replaces or updates the provisional divider so dividers never stack without messages.
   * @param {object} keyframe
   */
  onKeyframeSettled(keyframe) {
    if (!keyframe) return;

    // Only display dividers once a conversation has started
    if (this._history.length === 0) return;

    // If user returns to the keyframe where the last message was sent, remove provisional divider
    if (keyframe.id === this._lastCommittedKeyframeId) {
      if (this._pendingDividerEl) {
        this._pendingDividerEl.remove();
        this._pendingDividerEl = null;
      }
      return;
    }

    const text = `Viewing: ${keyframe.label} · ${keyframe.ma} Ma`;

    // If an uncommitted divider already exists, update it in place instead of creating another
    if (this._pendingDividerEl && this._pendingDividerEl.parentNode) {
      this._pendingDividerEl.textContent = text;
      this._scrollToBottom();
    } else {
      this._pendingDividerEl = this._appendDivider(text);
    }
  }

  // ── Message flow ──────────────────────────────────────────────────────

  async _sendUserMessage() {
    const text = this._el.chatInput.value.trim();
    if (!text || this._sending) return;

    this._el.chatInput.value = '';
    this._setSending(true);

    // If there is an active provisional divider, lock it into permanent chat history
    if (this._pendingDividerEl) {
      this._pendingDividerEl = null;
    } else if (this._history.length > 0 && this._context && this._context.id !== this._lastCommittedKeyframeId) {
      // Fallback: message sent before slider settle event fired
      this._appendDivider(`Viewing: ${this._context.label} · ${this._context.ma} Ma`);
    }

    this._lastCommittedKeyframeId = this._context ? this._context.id : null;

    // Append to history and DOM
    this._history.push({ role: 'user', content: text });
    this._appendMessage('user', text);

    // Show typing indicator
    const typingEl = this._appendTypingIndicator();

    try {
      // Enrich system context with available image gallery metadata
      const activeImages = this._imageLib.filter(img =>
        (img.keyframes || []).includes(this._context?.id)
      );
      const otherImages = this._imageLib.filter(img =>
        !(img.keyframes || []).includes(this._context?.id)
      );

      const enrichedContext = {
        ...(this._context || {}),
        currentPeriodImages: activeImages.map(img => ({
          title: img.title,
          tags: (img.tags || []).slice(0, 8).join(', '),
          description: img.description || ''
        })),
        otherImages: otherImages.map(img => ({
          title: img.title,
          period: (img.keyframes || []).join(', ')
        }))
      };

      let response;
      if (DEV_MODE) {
        response = await mockChat(this._history, enrichedContext);
      } else {
        response = await prodChat(this._history, enrichedContext, text);
      }

      typingEl.remove();
      this._history.push({ role: 'assistant', content: response });
      this._appendMessage('assistant', response);

    } catch (err) {
      typingEl.remove();
      this._appendError(`Connection error: ${err.message}`);
    }

    this._setSending(false);
  }

  _setSending(sending) {
    this._sending = sending;
    this._el.sendBtn.disabled   = sending;
    this._el.chatInput.disabled = sending;
  }

  // ── DOM builders ──────────────────────────────────────────────────────

  _appendMessage(role, text) {
    // Hide welcome message on first real message
    const welcome = document.getElementById('chatWelcome');
    if (welcome) welcome.style.display = 'none';

    const { html, images } = resolveImages(text, this._imageLib);

    const wrap = document.createElement('div');
    wrap.className = `chat-message ${role}`;

    const bubble = document.createElement('div');
    bubble.className = 'message-bubble';
    bubble.innerHTML = `<p>${html}</p>`;

    // Inline images for assistant messages
    if (role === 'assistant' && images.length > 0) {
      for (const img of images) {
        const imgPath = `images/${img.filename}`;
        const imgEl   = document.createElement('img');
        imgEl.src     = imgPath;
        imgEl.alt     = img.title || img.id;
        imgEl.className = 'message-image';
        imgEl.onerror   = () => { imgEl.style.display = 'none'; }; // hide if missing

        const cap = document.createElement('div');
        cap.className   = 'message-image-caption';
        cap.textContent = `${img.title} — ${img.credit}`;

        bubble.appendChild(imgEl);
        bubble.appendChild(cap);
      }
    }

    wrap.appendChild(bubble);

    // Footer: timestamp + TTS for assistant
    const footer = document.createElement('div');
    footer.className = 'message-footer';

    const time = document.createElement('span');
    time.className   = 'message-time';
    time.textContent = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    footer.appendChild(time);

    if (role === 'assistant') {
      const ttsBtn = document.createElement('button');
      ttsBtn.className = 'tts-btn';
      ttsBtn.title     = 'Listen to this response';
      ttsBtn.innerHTML = `<svg viewBox="0 0 24 24"><path d="M3 9v6h4l5 5V4L7 9H3zm13.5 3c0-1.77-1.02-3.29-2.5-4.03v8.05c1.48-.73 2.5-2.25 2.5-4.02zM14 3.23v2.06c2.89.86 5 3.54 5 6.71s-2.11 5.85-5 6.71v2.06c4.01-.91 7-4.49 7-8.77s-2.99-7.86-7-8.77z"/></svg>`;
      ttsBtn.addEventListener('click', () => speak(text, ttsBtn));
      footer.appendChild(ttsBtn);
    }

    wrap.appendChild(footer);
    this._el.chatMessages.appendChild(wrap);
    this._scrollToBottom();
  }

  _appendDivider(label) {
    const welcome = document.getElementById('chatWelcome');
    if (welcome) welcome.style.display = 'none';

    const div = document.createElement('div');
    div.className   = 'context-divider';
    div.textContent = label;
    this._el.chatMessages.appendChild(div);
    this._scrollToBottom();
    return div;
  }

  _appendTypingIndicator() {
    const wrap = document.createElement('div');
    wrap.className = 'chat-message assistant typing-indicator';
    wrap.innerHTML = `
      <div class="message-bubble">
        <div class="typing-dot"></div>
        <div class="typing-dot"></div>
        <div class="typing-dot"></div>
      </div>`;
    this._el.chatMessages.appendChild(wrap);
    this._scrollToBottom();
    return wrap;
  }

  _appendError(msg) {
    const div = document.createElement('div');
    div.style.cssText = 'font-size:12px;color:#e05050;padding:6px 14px;text-align:center;';
    div.textContent = msg;
    this._el.chatMessages.appendChild(div);
    this._scrollToBottom();
  }

  _scrollToBottom() {
    this._el.chatMessages.scrollTop = this._el.chatMessages.scrollHeight;
  }
}
