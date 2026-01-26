# Hunter Agent V3

## Overview
Hunter Agent V3 is an AI-powered business intelligence agent. It monitors news sources for strategic opportunities (M&A, Investments, New Hires, Innovations) relevant to YOUR COMPANY and clusters them by region.

**Key Features V3:**
*   **Smart Filter (Naive Bayes)**: Uses a local ML model trained on your feedback to discard 90%+ of irrelevant noise *before* calling the AI.
*   **Cost Optimization**: ML pre-filters reduce Gemini API costs significantly.
*   **Rate Limiting**: Built-in sleep timers respect the 5 RPM limit of Gemini Flash models.

## Installation

```bash
# Install dependencies
pip install -r requirements.txt
```

## Usage

### 1. Training the Brain (Important!)
Before running the agent, you must train the filter model. This script looks at your database (`opportunities.db`) and learns from your past feedback.

```bash
python train_model.py
```
*Run this periodically (e.g., weekly) to make the agent smarter.*

### 2. Running the Agent
```bash
python agent.py
```

## Configuration

### `config.json`
*   **`search_tiers`**: Defines which countries are searched.
*   **`trigger_lexicon`**: Keywords used for searching news.

### Deployment (PythonAnywhere)
The agent is designed to run as two scheduled tasks:
1.  **Training Task** (Daily/Weekly): `python train_model.py`
2.  **Agent Task** (Daily): `python agent.py`

**Virtual Environment Note:**
Always use the full path to the virtualenv python executable when creating tasks:
`/home/YOUR_USER/.virtualenvs/hunter-agent-env/bin/python ...`

