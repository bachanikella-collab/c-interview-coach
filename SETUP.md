# Interview Coach — Team Setup Guide

AI-powered mock interview coach with voice input/output, PDF resume upload, and real-time feedback.

---

## Requirements

- **Windows 10/11**
- **Python 3.11 or 3.12** — download at https://www.python.org/downloads/ (check "Add to PATH" during install)
- **Google Chrome** (required for microphone / speech features)
- **A Google API key** — free at https://aistudio.google.com/apikey

---

## Setup (one time only)

### 1. Get the project folder

Extract the zip (or clone the repo) so you have a folder called `interview-coach` on your machine.

### 2. Add your API key

Inside the folder, rename `.env.example` to `.env`, then open it and paste your key:

```
GOOGLE_API_KEY=AIza...your_key_here
```

### 3. Open PowerShell inside the folder

Right-click the `interview-coach` folder → **Open in Terminal** (or open PowerShell and `cd` to it).

### 4. Run the start script

```powershell
.\start.ps1
```

This will automatically:
- Create a Python virtual environment
- Install all dependencies
- Start the agent server on port 8080
- Start the voice UI on port 8081

Wait until you see: `Both servers running.`

### 5. Open Chrome and go to:

```
http://127.0.0.1:8081
```

---

## How to use it

| Action | How |
|---|---|
| Type a message | Use the text box, press **Enter** or **➤** |
| Speak | Click **🎤**, talk, then press **Enter** |
| Upload your resume (PDF) | Click **📎** and pick a PDF file |
| Toggle voice replies | Click **🔊 Voice ON** in the top-right |

### Interview flow

1. The coach greets you and asks for a brief intro (or upload your resume with 📎)
2. Paste in a job description when asked
3. The coach parses it into 3 assessment domains: behavioral, situational, technical
4. Pick a domain to start — you'll get 3 questions per domain (9 total)
5. After all sections, you receive a full evaluation report with scores and improvement tips

---

## Stopping the servers

Close the two terminal windows that opened, or press `Ctrl+C` in each one.

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `python` not found | Reinstall Python and check "Add to PATH" |
| Page won't load | Make sure both terminal windows are still open |
| Mic not working | Use Chrome (not Edge/Firefox); allow mic permission when prompted |
| Voice output silent | Make sure **🔊 Voice ON** is shown in the header |
