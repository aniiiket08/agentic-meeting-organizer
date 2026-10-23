# Meeting Organizer Agent

> Multi-agent system that runs the full meeting lifecycle: **schedule → prepare → transcribe → approve → track → follow up.**

## Overview

Meeting Organizer Agent is an agentic system designed to handle scheduling, room booking, agenda preparation, transcription, human-in-the-loop approval, action item tracking, and reminder follow-ups.

## Quick Start

1. Copy `.env.example` to `.env` and fill in your keys:
   ```bash
   cp .env.example .env
   ```

2. Start the services:
   ```bash
   make up
   ```

3. Access the dashboard at `http://localhost:5173` and API docs at `http://localhost:8000/docs`.

## License

MIT
