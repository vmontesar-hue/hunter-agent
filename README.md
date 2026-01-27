# Hunter Agent V3

## Overview
Hunter Agent V3 is an AI-powered business intelligence agent designed to monitor, filter, and analyze strategic opportunities for Igeneris. It automates the discovery of M&A, investment, and innovation news across multiple regions.

### How It Works (The Pipeline)
The agent operates in a 5-stage pipeline designed for efficiency and cost control:

1.  **Collection (Tiered Search)**:
    *   Queries `NewsData.io` for keywords (M&A, New Hire, etc.) across defined country tiers.
    *   Scrapes Job Portals (e.g., Glassdoor) if enabled.

2.  **Smart Filtering (Semantic ML)**:
    *   **Primary: Sentence Transformers** - Embedding-based filter that understands semantic meaning.
    *   **Fallback: Naive Bayes** - Used when no semantic training data exists yet.
    *   **Cost Efficiency**: Discards ~90% of irrelevant articles before expensive LLM calls.

3.  **AI Analysis (Gemini)**:
    *   Items passing the ML filter are sent to Google's Gemini models.
    *   **Model Rotation**: Automatically rotates between 5 models to respect rate limits.
    *   **Failure Queue**: API errors save articles for retry within the same cycle.

4.  **Continuous Learning**:
    *   **Positive Learning**: Opportunities train the semantic filter with successful examples.
    *   **Negative Learning**: AI rejections (with reasons) train the filter to avoid similar articles.
    *   **User Feedback**: Slack buttons let users mark items as Relevant/Irrelevant.

5.  **Notification**:
    *   Valid opportunities posted to region-specific Slack channels.
    *   Interactive feedback buttons for continuous improvement.

---

## Database Statuses

| Status | Meaning |
|--------|---------|
| `detected` | New article found |
| `notified` | User notified via Slack |
| `relevant` | User marked as relevant |
| `irrelevant` | User marked as irrelevant |
| `pending` | API failed, queued for retry (cleared at cycle end) |
| `ai_rejected` | AI rejected, saved for ML training |

---

## Prerequisites
*   Python 3.10 or higher.
*   A server or local machine to run the scripts (e.g., PythonAnywhere).

## Installation

1.  **Navigate to folder**:
    ```bash
    cd hunter-agentv3
    ```

2.  **Install dependencies** (CPU-only for smaller footprint):
    ```bash
    pip install torch --index-url https://download.pytorch.org/whl/cpu
    pip install -r requirements.txt
    ```

3.  **Environment Variables** - Create a `.env` file:
    ```env
    GOOGLE_API_KEY=your_gemini_api_key
    NEWS_API_KEY_V2=your_newsdata_io_key
    SLACK_BOT_TOKEN=xoxb-your-slack-bot-token
    SLACK_CHANNEL_ID_V1=C0XXXXXX  # Fallback channel
    ```

---

## Slack App Configuration
To enable the agent to post messages and receive feedback buttons:

1.  **Create App**: Go to [api.slack.com/apps](https://api.slack.com/apps) and create a new App.
2.  **Bot Scopes**: Add `chat:write`, `chat:write.public`, `commands`, `incoming-webhook`.
3.  **Install App**: Copy the `Bot User OAuth Token` (`xoxb-...`) to your `.env`.
4.  **Enable Interactivity**:
    *   Turn "Interactivity" **On**.
    *   **Request URL**: Point to your `web_app.py` (e.g., `https://your-domain.com/`).
5.  **Channels**: Update `CHANNELS` dictionary in `slack_notifier.py` with your Channel IDs.

---

## Usage Guide

### 1. Running the Agent (Daily Operation)
```bash
python agent.py
```
*   Fetches news, filters with ML, analyzes with AI, posts to Slack.
*   First run downloads the semantic model (~80MB, one-time).
*   Schedule daily via Cron or PythonAnywhere Tasks.

### 2. Training the Naive Bayes Fallback (Optional)
```bash
python train_model.py
```
*   Only needed if you want to bootstrap the filter before semantic data accumulates.
*   The semantic filter learns automatically during normal operation.

### 3. Handling Feedback (Web Server)
```bash
python web_app.py
```
*   Must be hosted publicly so Slack can reach it.

---

## Configuration (`config.json`)
*   `search_tiers`: Countries grouped for API calls.
*   `trigger_lexicon`: Keywords for news search.
*   `data_sources`: Enable/Disable `news_api` or `job_portals`.

---

## Directory Structure
| File | Purpose |
|------|---------|
| `agent.py` | Main logic (Collection → Filtering → Analysis) |
| `semantic_filter.py` | Sentence Transformers embedding-based filter |
| `train_model.py` | Naive Bayes training script (fallback) |
| `web_app.py` | Flask server for Slack Interactivity |
| `slack_notifier.py` | Slack message formatting |
| `database.py` | SQLite operations |
| `deduplicator.py` | Duplicate detection |
| `knowledge_extractor.py` | Prompt engineering helpers |

---

## Model Rotation (API Cost Control)
```python
MODEL_ROTATION = [
    {"name": "gemini-3-flash-preview",  "limit": 20},
    {"name": "gemini-2.5-flash",        "limit": 20},
    {"name": "gemini-2.5-flash-lite",   "limit": 20},
    {"name": "gemini-2.0-flash",        "limit": 20},
    {"name": "gemini-2.0-flash-lite",   "limit": 20},
]
# Total: 100 free API calls/day
```
