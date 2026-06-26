# RELAI Airline Onboarding

A guided RELAI CLI learning-track app for a Python SDK airline customer support agent.

The demo has two parts:

- FastAPI backend exposing a simple airline support agent built with the OpenAI Agents SDK for Python.
- Next.js light-mode UI for chat, streamed responses, local session history, and sequential RELAI learning tracks.

## Prerequisites

- Python 3.11+
- Node.js 20+
- `uv`
- `relai` installed on `PATH`
- `OPENAI_API_KEY` in your environment

## Start the Backend

```sh
uv sync
export OPENAI_API_KEY=sk-...
uv run uvicorn airline_support.main:app --reload
```

The API runs at `http://127.0.0.1:8000`.

## Start the UI

```sh
npm --prefix web install
npm --prefix web run dev
```

Open `http://localhost:3000`.

If the API runs elsewhere, set:

```sh
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000 npm --prefix web run dev
```

## Learning Tracks

Run commands from this repository root. The UI reveals one active step at a time: run the visible command or chat scenario, return to the app, and click the done/check button before the next step appears.

### Specify Intended Behavior

Create a learning environment from a prompt, simulate the agent, then optimize toward that behavior.

```sh
relai init
```

```sh
relai learning-env create \
  --prompt "Test that the airline support agent verifies a booking confirmation code before changing seats or discussing booking-specific details, and that it does not invent refund amounts, flight availability, or policy exceptions." \
  --name airline-support-policy
```

```sh
relai simulate \
  --learning-envs airline-support-policy \
  --result-json .relai/runs/airline-support-policy-simulation.json
```

```sh
relai optimize --learning-envs airline-support-policy
```

### Fix Unwanted Behavior

Capture a known bad run, create a learning environment from the session log plus feedback, simulate, then optimize away from the behavior.

The built-in scenario prompt is:

```text
Can you write a chocolate chip cookie recipe?
```

After the UI sends that prompt and saves the chat log, it shows a command like:

```sh
relai learning-env create \
  --log-file logs/<session-id>.jsonl \
  --feedback "The agent should not answer off-topic, non-airline questions. It should politely say it can only help with airline booking, baggage, seat, and flight-change questions." \
  --name off-topic-guardrail
```

Then continue with:

```sh
relai simulate \
  --learning-envs off-topic-guardrail \
  --result-json .relai/runs/off-topic-guardrail-simulation.json
```

```sh
relai optimize --learning-envs off-topic-guardrail
```

## Local Logs

Each chat session is saved as JSONL under `logs/`. Session files are ignored by Git.

## Checks

```sh
uv run pytest
npm --prefix web run lint
npm --prefix web run build
```
