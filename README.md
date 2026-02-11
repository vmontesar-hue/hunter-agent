# Hunter Agent v3: Autonomous Opportunity Scout

## 🚀 Overview
Hunter Agent v3 is an intelligent, autonomous system designed to identify, analyze, and distribute high-value business opportunities (News & Jobs) in real-time. It uses a **multi-stage filtering pipeline** combining semantic search, machine learning, and Generative AI (Gemini 2.0) to find "needles in the haystack" for business development.

The system is deployed on a cloud server (PythonAnywhere) and integrates with **Slack** for real-time notifications and **Human-in-the-Loop (HITL)** feedback.

---

## 📂 Project Structure & File Descriptions

### 1. Core Logic
| File | Purpose |
|------|---------|
| **`agent.py`** | **The Main Brain.** Orchestrates the entire workflow: fetching data, filtering, deduplicating, analyzing with AI, and triggering notifications. Use this to run the agent manually. |
| **`semantic_filter.py`** | **The Machine Learning Engine.** Implements the vector-based semantic search. It compares new articles against a database of past "Relevant" and "Irrelevant" examples to predict interest. |
| **`database.py`** | **The Memory.** Handles all SQLite database operations: storing opportunities, status updates, saving feedback, and logging history. |
| **`deduplicator.py`** | **The Guard.** Prevents duplicate alerts. Uses "fuzzy matching" to detect if the same story is covered by different sources or slightly rephrased. |
| **`scrapers.py`** | **The Eyes.** specialized scrapers (e.g., Glassdoor via ScrapingBee) to fetch job listings that standard APIs might miss. |
| **`knowledge_extractor.py`** | **The Teacher.** Analyzes your feedback history to extract specific items of interest (Concept Distillation) and improves the system's "implicit knowledge". |

### 2. Interfaces & Integration
| File | Purpose |
|------|---------|
| **`web_app.py`** | **The Feedback Server.** A Flask application that listens for Slack interactions (button clicks, modal submissions). It connects your Slack feedback back to the agent's database. |
| **`slack_notifier.py`** | **The Messenger.** Formats and sends rich Slack notifications to specific channels based on the opportunity's region (Spain, LatAm, Brazil, etc.). |
| **`config.json`** | **The Configuration.** Central settings file for search queries, target countries, API keys placeholders, and tier structures. |

### 3. Utility & Maintenance Scripts
| File | Purpose |
|------|---------|
| **`bootstrap_semantic.py`** | **The Training Starter.** One-time script to populate the semantic filter with your entire history of ~2,700 past opportunities. Run this after a fresh install. |
| **`process_db_opportunities.py`** | **The Backfill Worker.** Processes opportunities that were "detected" but not yet analyzed/notified (e.g., if the process crashed). |
| **`check_db_stats.py`** | **The Diagnostic.** Utility to count how many opportunities are in each status (relevant, rejected, notified) to verify system health. |
| **`reset_semantic.py`** | **The Reset Button.** Deletes the semantic model file (`semantic_filter.pkl`) to force a full re-training from scratch using `bootstrap`. |
| **`seed_examples.py`** | **The Manual Trainer.** Allows you to manually type in "ideal" opportunity descriptions to teach the AI what you want, even if you haven't found one yet. |

---

## 🛠️ Key Functions by File

### `agent.py`
*   `run_collection_phase(config)`: The master function. Runs the loop: Collect -> Deduplicate -> Filter -> Analyze -> Notify.
*   `get_news_from_newsdata(config)`: Fetches global news based on your keywords and country tiers.
*   `analyze_text_with_ai(prompt)`: Sends content to Gemini 2.0 Flash for deep reasoning and scoring.

### `semantic_filter.py`
*   `predict_relevance(text)`: Returns a 0-1 score and explanation. Calls the vector model.
*   `batch_filter_articles(articles)`: Optimization. Filters 50 items at once and guarantees the Top-10 pass to ensure data flows to the AI.
*   `add_positive_example(text)` / `add_negative_example(text)`: Updates the training database. Enforces a **2,000 item limit** (FIFO rotation) to optimize storage.
*   `get_model()`: Lazy-loads the `sentence-transformers` model (multilingual).

### `database.py`
*   `initialize_db()`: Creates the `opportunities.db` tables if missing.
*   `add_opportunity(...)`: Saves a new raw finding.
*   `log_feedback_with_rationale(...)`: Updates an item's status based on your Slack click (Relevant/Irrelevant) and saves your comment.
*   `get_recent_opportunities()`: Fetches last 7 days of history for deduplication.

### `web_app.py`
*   `handle_all_feedback()`: Main endpoint for Slack webhooks. Routes requests to the right handler.
*   `handle_v2_interaction()`: Opens the "Add Feedback" modal in Slack.
*   `log_feedback_to_db_v2()`: Writes the user's decision to the local database.

---

## 🔄 The "Learning Loop"
1.  **Agent** finds an article.
2.  **Semantic Filter** (embedding model) scores it.
3.  **Gemini AI** analyzes the winners.
4.  **You** receive a Slack alert.
5.  **You** click "Relevant" or "Irrelevant" in Slack.
6.  **Web App** saves this feedback.
7.  **Semantic Filter** AUTOMATICALLY learns from this feedback (adding it to its database) for the next run.

---

## 📦 Deployment
The system runs on **PythonAnywhere**.
*   **Virtual Environment:** `hunter-agent-env`
*   **Command:** `python agent.py` (Scheduled daily/hourly)
*   **Web Server:** `web_app.py` (Always running to listen to Slack)
