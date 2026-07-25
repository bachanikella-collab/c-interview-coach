"""
Voice-enabled chat UI for the Interview Coach ADK agent.
Serves on port 8081. Proxies to the ADK server on port 8080.
- Speech-to-text:  browser Web Speech API (free, Chrome)
- Text-to-speech:  Gemini TTS API (gemini-3.1-flash-tts-preview)
"""

import base64
import io
import os
import uuid
import wave
from contextlib import asynccontextmanager

import httpx
import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, File, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, Response
from pypdf import PdfReader

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), ".env"))

ADK_BASE      = "http://127.0.0.1:9000"
APP_NAME      = "coach"
TTS_MODEL     = "gemini-3.1-flash-tts-preview"
TTS_VOICE     = "Kore"
GEMINI_KEY    = os.environ.get("GOOGLE_API_KEY", "")
TTS_MAX_CHARS = 600   # truncate TTS for faster audio generation
RESUME_MAX    = 4000  # cap resume text to avoid token overflow

_http: httpx.AsyncClient | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _http
    _http = httpx.AsyncClient(
        limits=httpx.Limits(max_keepalive_connections=10, max_connections=20),
        timeout=httpx.Timeout(60.0),
    )
    yield
    await _http.aclose()


app = FastAPI(lifespan=lifespan)


def _truncate_for_tts(text: str) -> str:
    """Trim to first natural sentence break so TTS starts faster."""
    if len(text) <= TTS_MAX_CHARS:
        return text
    snippet = text[:TTS_MAX_CHARS]
    for ch in ('.', '?', '!'):
        idx = snippet.rfind(ch)
        if idx > TTS_MAX_CHARS // 2:
            return snippet[:idx + 1]
    return snippet.rstrip() + "…"


HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>Interview Coach</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    font-family: 'Segoe UI', sans-serif;
    background: #0f0f0f;
    color: #e0e0e0;
    display: flex;
    flex-direction: column;
    height: 100vh;
  }
  header {
    background: #1a1a2e;
    padding: 14px 20px;
    font-size: 1.1rem;
    font-weight: 600;
    color: #a78bfa;
    letter-spacing: 0.5px;
    border-bottom: 1px solid #2d2d4e;
    display: flex;
    align-items: center;
    gap: 10px;
  }
  #audio-toggle {
    margin-left: auto;
    background: #2d2d4e;
    border: none;
    border-radius: 8px;
    color: #a78bfa;
    padding: 5px 12px;
    font-size: 0.82rem;
    cursor: pointer;
    transition: background 0.2s;
  }
  #audio-toggle.on  { background: #4f46e5; color: #fff; }
  #messages {
    flex: 1;
    overflow-y: auto;
    padding: 20px;
    display: flex;
    flex-direction: column;
    gap: 14px;
  }
  .msg {
    max-width: 72%;
    padding: 12px 16px;
    border-radius: 16px;
    line-height: 1.55;
    font-size: 0.95rem;
    white-space: pre-wrap;
  }
  .msg.user  { align-self: flex-end;   background: #4f46e5; color: #fff; border-bottom-right-radius: 4px; }
  .msg.agent { align-self: flex-start; background: #1e1e2e; color: #e0e0e0; border-bottom-left-radius: 4px; border: 1px solid #2d2d4e; }
  .msg.system{ align-self: center; background: transparent; color: #666; font-size: 0.82rem; font-style: italic; }
  .msg.agent.speaking { border-color: #a78bfa; box-shadow: 0 0 0 1px #a78bfa44; }
  #input-area {
    display: flex;
    align-items: flex-end;
    gap: 10px;
    padding: 14px 20px;
    background: #141414;
    border-top: 1px solid #2d2d4e;
  }
  #msg-input {
    flex: 1;
    background: #1e1e2e;
    border: 1px solid #3d3d5c;
    border-radius: 12px;
    color: #e0e0e0;
    padding: 10px 14px;
    font-size: 0.95rem;
    resize: none;
    min-height: 44px;
    max-height: 140px;
    outline: none;
    transition: border-color 0.2s;
  }
  #msg-input:focus { border-color: #6d6dff; }
  button, #upload-btn {
    border: none;
    border-radius: 10px;
    cursor: pointer;
    font-size: 1.1rem;
    width: 44px;
    height: 44px;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: background 0.2s, transform 0.1s;
    flex-shrink: 0;
  }
  button:active, #upload-btn:active { transform: scale(0.93); }
  #upload-btn {
    background: #2d2d4e;
    color: #a78bfa;
    font-size: 1.2rem;
    user-select: none;
    text-decoration: none;
  }
  #upload-btn:hover { background: #3d3d5e; }
  #mic-btn  { background: #2d2d4e; color: #a78bfa; }
  #mic-btn.listening { background: #4f46e5; color: #fff; animation: pulse 1s infinite; }
  @keyframes pulse {
    0%,100% { box-shadow: 0 0 0 0 rgba(99,102,241,0.5); }
    50%      { box-shadow: 0 0 0 8px rgba(99,102,241,0); }
  }
  #send-btn { background: #4f46e5; color: #fff; font-size: 1.3rem; }
  #send-btn:disabled { background: #2d2d4e; color: #555; cursor: not-allowed; }
  #status {
    font-size: 0.78rem;
    color: #a78bfa;
    padding: 0 20px 6px;
    background: #141414;
    min-height: 20px;
  }
  ::-webkit-scrollbar { width: 6px; }
  ::-webkit-scrollbar-thumb { background: #2d2d4e; border-radius: 3px; }
</style>
</head>
<body>
<header>
  \U0001f399️ Interview Coach
  <button id="audio-toggle" title="Toggle voice replies">\U0001f507 Voice OFF</button>
</header>
<div id="messages"></div>
<div id="status"></div>
<div id="input-area">
  <textarea id="msg-input" rows="1" placeholder="Type or click \U0001f3a4 to speak…"></textarea>
  <label id="upload-btn" for="resume-input" title="Upload PDF resume">\U0001f4ce</label>
  <input type="file" id="resume-input" accept=".pdf" style="display:none">
  <button id="mic-btn" title="Click to speak">\U0001f3a4</button>
  <button id="send-btn" title="Send (Enter)">➤</button>
</div>

<script>
  const messagesEl   = document.getElementById('messages');
  const inputEl      = document.getElementById('msg-input');
  const micBtn       = document.getElementById('mic-btn');
  const sendBtn      = document.getElementById('send-btn');
  const statusEl     = document.getElementById('status');
  const audioToggle  = document.getElementById('audio-toggle');
  const resumeInput  = document.getElementById('resume-input');

  let userId      = 'user_' + Math.random().toString(36).slice(2, 9);
  let sessionId   = null;
  let isListening = false;
  let voiceOn         = false;
  let currentUtterance = null;

  // preload voice list (async in Chrome)
  let ttsVoices = [];
  if (window.speechSynthesis) {
    ttsVoices = window.speechSynthesis.getVoices();
    window.speechSynthesis.onvoiceschanged = () => { ttsVoices = window.speechSynthesis.getVoices(); };
  }

  function getBestVoice() {
    return ttsVoices.find(v => v.lang === 'en-US' && /google/i.test(v.name)) ||
           ttsVoices.find(v => v.lang === 'en-US') ||
           ttsVoices[0] || null;
  }

  function clipText(text, max = 600) {
    if (text.length <= max) return text;
    const s = text.slice(0, max);
    for (const c of ['.', '?', '!']) { const i = s.lastIndexOf(c); if (i > max / 2) return s.slice(0, i + 1); }
    return s.trimEnd() + '…';
  }

  // ── Audio toggle ────────────────────────────────────────────
  audioToggle.addEventListener('click', () => {
    voiceOn = !voiceOn;
    audioToggle.textContent = voiceOn ? '\U0001f50a Voice ON' : '\U0001f507 Voice OFF';
    audioToggle.classList.toggle('on', voiceOn);
    if (!voiceOn) { window.speechSynthesis.cancel(); currentUtterance = null; }
  });

  // ── Session init ────────────────────────────────────────────
  async function initSession() {
    // Show greeting immediately so the screen is never blank
    const GREETING = "Hello! I'm here to help you ace your next interview. I'll be guiding you through a structured, multi-part mock interview session tailored to your background and your target role.\\n\\nTo get started, please tell me a little bit about yourself — or you can upload your PDF resume using the 📎 button.";
    addBubble(GREETING, 'agent');
    setStatus('Connecting…');
    try {
      const r = await fetch('/api/session', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ userId })
      });
      const data = await r.json();
      sessionId = data.id;
      setStatus('');
    } catch(e) {
      setStatus('⚠️ Could not connect to agent. Is ADK running on port 8080?');
    }
  }

  // ── Send message ────────────────────────────────────────────
  async function sendMessage(opts) {
    const text = (opts && opts.text !== undefined) ? opts.text : inputEl.value.trim();
    const displayText = (opts && opts.display !== undefined) ? opts.display : text;
    if (!text || !sessionId) return;

    if (!opts || opts.text === undefined) { inputEl.value = ''; autoResize(); }

    addBubble(displayText, 'user');
    sendBtn.disabled = true;
    setStatus('Agent is thinking…');

    try {
      const r = await fetch('/api/chat', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ userId, sessionId, text })
      });
      const events = await r.json();
      const raw = extractReply(events);
      const reply = raw ? raw.replace(/[*]+/g, '').trim() : null;
      const bubble = addBubble(reply || '(no response)', 'agent');

      if (voiceOn && reply) {
        setStatus('\U0001f50a Speaking…');
        await speakText(reply, bubble);
      }
    } catch(e) {
      addBubble('⚠️ Error reaching agent.', 'system');
    } finally {
      sendBtn.disabled = false;
      setStatus('');
    }
  }

  function extractReply(events) {
    // Collect text from all model events and return the last non-empty one
    const replies = [];
    for (const ev of (events || [])) {
      const parts = ev?.content?.parts;
      if (!parts) continue;
      const txt = parts.map(p => p.text || '').join('').trim();
      if (txt) replies.push(txt);
    }
    return replies.length ? replies[replies.length - 1] : null;
  }

  // ── PDF Resume Upload ───────────────────────────────────────────
  resumeInput.addEventListener('change', async () => {
    const file = resumeInput.files[0];
    if (!file) return;
    if (!sessionId) { addBubble('⚠️ Please wait for the session to connect first.', 'system'); return; }

    setStatus('\U0001f4ce Reading resume PDF…');
    const formData = new FormData();
    formData.append('file', file);

    try {
      const r = await fetch('/api/upload-resume', { method: 'POST', body: formData });
      if (!r.ok) { const e = await r.json(); throw new Error(e.error || 'Upload failed'); }
      const { text } = await r.json();
      await sendMessage({
        text: 'Here is my resume:\\n\\n' + text,
        display: '\U0001f4ce Resume uploaded: ' + file.name
      });
    } catch(e) {
      addBubble('⚠️ Resume upload failed: ' + e.message, 'system');
      setStatus('');
    } finally {
      resumeInput.value = '';
    }
  });

  // ── Text-to-Speech via browser SpeechSynthesis ──────────────────────
  function speakText(text, bubble) {
    if (!window.speechSynthesis) return Promise.resolve();
    window.speechSynthesis.cancel();

    const utterance = new SpeechSynthesisUtterance(clipText(text));
    const voice = getBestVoice();
    if (voice) utterance.voice = voice;
    utterance.lang = 'en-US';
    utterance.rate = 1.0;

    if (bubble) bubble.classList.add('speaking');
    currentUtterance = utterance;

    return new Promise(resolve => {
      utterance.onend = () => { if (bubble) bubble.classList.remove('speaking'); currentUtterance = null; resolve(); };
      utterance.onerror = () => { if (bubble) bubble.classList.remove('speaking'); currentUtterance = null; resolve(); };
      window.speechSynthesis.speak(utterance);
    });
  }

  // ── UI helpers ────────────────────────────────────────────
  function addBubble(text, role) {
    const div = document.createElement('div');
    div.className = 'msg ' + role;
    div.textContent = text;
    messagesEl.appendChild(div);
    messagesEl.scrollTop = messagesEl.scrollHeight;
    return div;
  }

  function setStatus(msg) { statusEl.textContent = msg; }

  function autoResize() {
    inputEl.style.height = 'auto';
    inputEl.style.height = Math.min(inputEl.scrollHeight, 140) + 'px';
  }

  inputEl.addEventListener('input', autoResize);
  inputEl.addEventListener('keydown', e => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); }
  });
  sendBtn.addEventListener('click', () => sendMessage());

  // ── Web Speech API (STT) ──────────────────────────────────────────
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;

  if (!SpeechRecognition) {
    micBtn.disabled = true;
    micBtn.title = 'Speech recognition requires Chrome.';
    micBtn.style.opacity = '0.4';
  } else {
    const recognition = new SpeechRecognition();
    recognition.continuous     = false;
    recognition.interimResults = true;
    recognition.lang           = 'en-US';

    let finalTranscript = '';

    recognition.onstart = () => {
      isListening = true;
      finalTranscript = '';
      micBtn.classList.add('listening');
      setStatus('\U0001f3a4 Listening… speak now');
      if (currentUtterance) { window.speechSynthesis.cancel(); currentUtterance = null; }
    };

    recognition.onresult = (event) => {
      let interim = '';
      finalTranscript = '';
      for (let i = event.resultIndex; i < event.results.length; i++) {
        const t = event.results[i][0].transcript;
        if (event.results[i].isFinal) finalTranscript += t;
        else interim += t;
      }
      inputEl.value = finalTranscript || interim;
      autoResize();
    };

    recognition.onerror  = (e) => { setStatus('Mic error: ' + e.error); micBtn.classList.remove('listening'); isListening = false; };
    recognition.onend    = () => {
      micBtn.classList.remove('listening');
      isListening = false;
      if (finalTranscript.trim()) {
        setStatus('✅ Transcribed — press Enter or ➤ to send');
        inputEl.focus();
      } else {
        setStatus('');
      }
    };

    micBtn.addEventListener('click', () => {
      if (isListening) recognition.stop();
      else { inputEl.value = ''; recognition.start(); }
    });
  }

  initSession();
</script>
</body>
</html>"""


@app.get("/", response_class=HTMLResponse)
async def index():
    return HTML


@app.post("/api/session")
async def create_session(request: Request):
    body = await request.json()
    user_id = body.get("userId", str(uuid.uuid4()))
    r = await _http.post(
        f"{ADK_BASE}/apps/{APP_NAME}/users/{user_id}/sessions",
        timeout=10,
    )
    return JSONResponse(r.json())


@app.post("/api/chat")
async def chat(request: Request):
    body = await request.json()
    payload = {
        "appName": APP_NAME,
        "userId": body["userId"],
        "sessionId": body["sessionId"],
        "newMessage": {
            "role": "user",
            "parts": [{"text": body["text"]}],
        },
    }
    r = await _http.post(f"{ADK_BASE}/run", json=payload, timeout=60)
    data = r.json()
    print(f"[ADK] events returned: {len(data) if isinstance(data, list) else data}")
    for i, ev in enumerate(data if isinstance(data, list) else []):
        content = ev.get("content", {})
        parts = content.get("parts", [])
        texts = [p.get("text", "") for p in parts if p.get("text")]
        if texts:
            print(f"[ADK] event[{i}] author={ev.get('author')} text={texts[0][:80]}")
    return JSONResponse(data)


@app.post("/api/upload-resume")
async def upload_resume(file: UploadFile = File(...)):
    contents = await file.read()
    try:
        reader = PdfReader(io.BytesIO(contents))
        text = "\n".join(page.extract_text() or "" for page in reader.pages).strip()
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    if not text:
        return JSONResponse({"error": "No readable text found in PDF."}, status_code=400)
    return JSONResponse({"text": text[:RESUME_MAX]})


@app.post("/api/tts")
async def text_to_speech(request: Request):
    body = await request.json()
    text = _truncate_for_tts(body.get("text", "").strip())
    if not text:
        return Response(status_code=400)

    payload = {
        "contents": [{"parts": [{"text": text}]}],
        "generationConfig": {
            "responseModalities": ["AUDIO"],
            "speechConfig": {
                "voiceConfig": {
                    "prebuiltVoiceConfig": {"voiceName": TTS_VOICE}
                }
            },
        },
    }

    r = await _http.post(
        f"https://generativelanguage.googleapis.com/v1beta/models/{TTS_MODEL}:generateContent",
        json=payload,
        headers={"x-goog-api-key": GEMINI_KEY},
        timeout=30,
    )
    if r.status_code != 200:
        print(f"[TTS] Gemini error {r.status_code}: {r.text[:500]}")
        return JSONResponse({"error": r.text[:200]}, status_code=502)
    data = r.json()

    try:
        audio_b64 = data["candidates"][0]["content"]["parts"][0]["inlineData"]["data"]
    except (KeyError, IndexError, TypeError) as e:
        print(f"[TTS] Unexpected response: {data}")
        return JSONResponse({"error": "Unexpected TTS response"}, status_code=502)
    pcm_bytes = base64.b64decode(audio_b64)

    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(24000)
        wf.writeframes(pcm_bytes)
    buf.seek(0)

    return Response(content=buf.read(), media_type="audio/wav")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8081))
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
