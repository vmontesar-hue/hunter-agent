# Hunter Agent V3

## Overview
Hunter Agent V3 is an AI-powered business intelligence agent designed to monitor, filter, and analyze strategic opportunities for Igeneris. It automates the discovery of M&A, investment, and innovation news across multiple regions.

### How It Works (The Pipeline)
The agent operates in a 4-stage pipeline designed for efficiency and cost control:

1.  **Collection (Tiered Search)**:
    *   The agent queries `NewsData.io` for keywords (M&A, New Hire, etc.) across defined country tiers (Tier 1: MX, ES, PT; Tier 2: CL, CO, etc.).
    *   It also scrapes Job Portals (e.g., Glassdoor) if enabled.

2.  **Smart Filtering (ML-Based)**:
    *   **Pre-Filtering**: A local **Naive Bayes Machine Learning model** (`filter_model.pkl`) analyzes the text *before* any API call.
    *   **Cost Efficiency**: This model discards ~90% of irrelevant articles (noise), ensuring that expensive LLM tokens are only spent on high-potential leads.

3.  **AI Analysis (Gemini)**:
    *   Items that pass the ML filter are sent to Google's Gemini models.
    *   **Model Rotation**: The agent automatically rotates between models (`gemini-2.5-flash`, `gemini-2.0`, etc.) to respect strict rate limits (RPM) and daily quotas.
    *   **Analysis**: The AI classifies the opportunity (Actionable vs. Noise) and extracts structured data (Company, Fit, Proposed Solution).

4.  **Notification & Feedback Loop**:
    *   **Slack**: Valid opportunities are posted to region-specific Slack channels with rich formatting.
    *   **Interactive Feedback**: Users can click "✅ Relevante" or "❌ No Relevante" directly in Slack.
    *   **Continuous Learning**: This feedback is saved to a local database (`opportunities.db`) and used to **retrain** the ML model, making the agent smarter over time.

---

## Prerequisites
*   Python 3.10 or higher.
*   A server or local machine to run the scripts (e.g., PythonAnywhere).

## Installation

1.  **Clone the repository/navigate to folder**:
    ```bash
    cd hunter-agentv3
    ```

2.  **Install dependencies**:
    ```bash
    pip install -r requirements.txt
    ```

3.  **Environment Variables**:
    Create a `.env` file with the following keys:
    ```env
    GOOGLE_API_KEY=your_gemini_api_key
    NEWS_API_KEY_V2=your_newsdata_io_key
    SLACK_BOT_TOKEN=xoxb-your-slack-bot-token
    SLACK_CHANNEL_ID_V1=C0XXXXXX  # Fallback channel
    ```

---

## Slack App Configuration
To enable the agent to post messages and receive feedback buttons, you must configure a Slack App.

1.  **Create App**: Go to [api.slack.com/apps](https://api.slack.com/apps) and create a new App from scratch.
2.  **Bot Scopes**: Go to "OAuth & Permissions" and add these **Bot Token Scopes**:
    *   `chat:write` (Send messages)
    *   `chat:write.public` (Send to channels without being invited - optional but recommended)
    *   `commands` (If using slash commands)
    *   `incoming-webhook`
3.  **Install App**: Install the app to your workspace and copy the `Bot User OAuth Token` (`xoxb-...`) to your `.env`.
4.  **Enable Interactivity (Crucial for Buttons)**:
    *   Go to "Interactivity & Shortcuts".
    *   Turn "Interactivity" **On**.
    *   **Request URL**: This must point to where your `web_app.py` is running (e.g., `https://your-domain.com/`). The agent listens on this URL for button clicks.
5.  **Channels**:
    *   The agent routes messages based on country codes in `slack_notifier.py`.
    *   Ensure the Bot is added to these channels or has `chat:write.public` scope.
    *   Update the `CHANNELS` dictionary in `slack_notifier.py` with your actual Channel IDs (Right click channel -> Copy Link -> The ID is the last part `C012345`).

---

## Usage Guide

### 1. Training the Brain (Mandatory First Step)
Before the agent can filter anything, it needs a model.
```bash
python train_model.py
```
*   **What it does**: Reads `opportunities.db`, finds past feedback, trains a Naive Bayes model, and saves it as `filter_model.pkl`.
*   **When to run**: Run this initially, and then periodically (e.g., weekly) to incorporate new feedback.

### 2. Running the Agent (Daily Operation)
```bash
python agent.py
```
*   **What it does**: Fetches news, filters them with the model, analyzes with AI, and posts to Slack.
*   **Deployment**: Schedule this to run daily (e.g., via Cron or PythonAnywhere Tasks).

### 3. Handling Feedback (Web Server)
To make the "Relevant/Not Relevant" buttons work, the web server must be running.
```bash
python web_app.py
```
*   **Note**: This needs to be hosted on a public IP/Domain (like PythonAnywhere Web Tab) so Slack can reach it.

---

## Configuration (`config.json`)
Customize the agent's behavior without changing code.

*   `search_tiers`: Defines which countries are grouped together for API calls.
*   `trigger_lexicon`: The keywords used to search for news (e.g., "acquired", "investment").
*   `data_sources`: Enable/Disable `news_api` or `job_portals`.

---

## Directory Structure
*   `agent.py`: Main logic (Collection -> Analysis).
*   `train_model.py`: Machine Learning training script.
*   `web_app.py`: Flask server for Slack Interactivity.
*   `slack_notifier.py`: Handles Slack message formatting.
*   `deduplicator.py`: Logic to avoid duplicate alerts.
*   `knowledge_extractor.py`: Helpers for prompt engineering.
