FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8081

# Start ADK agent server in background, then start the voice UI
CMD ["sh", "-c", "adk web coach --port 9000 & sleep 8 && python voice_ui.py"]
