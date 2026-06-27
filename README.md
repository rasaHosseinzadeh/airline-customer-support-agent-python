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
- `OPENAI_API_KEY` in your environment, or ready to paste when prompted

## Start the App

Run the onboarding launcher from the repository root:

```sh
./start.sh
```

The script prompts for your OpenAI API key when needed, saves it to the ignored `.env` file, installs missing dependencies, starts the API and UI, and opens the web app in your browser. It uses `8000` for the API and `3000` for the UI when available, then automatically moves to the next open ports if either is already in use.

## Manual Start

If you prefer to run each process yourself, start the backend first:

```sh
uv sync
export OPENAI_API_KEY=sk-...
uv run uvicorn airline_support.main:app --reload --host 127.0.0.1 --port 8000
```

The API runs at `http://127.0.0.1:8000`.

Then start the UI:

```sh
npm --prefix web install
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000 npm --prefix web run dev
```

Open `http://localhost:3000`.

## Learning Tracks

Run commands from this repository root. The UI reveals one active step at a time: run the visible command or chat scenario, return to the app, and click the done/check button before the next step appears.

### Specify Intended Behavior

Create a learning environment from a simple response-signoff prompt, simulate the agent, then optimize toward that behavior.

```sh
relai init
```

```sh
relai learning-env create \
  --prompt "The agent should end all responses with 'please let me know if you have any questions'." \
  --name response-signoff
```

```sh
relai simulate \
  --learning-envs response-signoff \
  --result-json .relai/runs/response-signoff-simulation.json
```

```sh
relai optimize --learning-envs response-signoff
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

### Benchmark

Register the committed four-sample CSV benchmark, simulate the agent against the registered suite, then optimize with that benchmark.

```sh
relai benchmark register \
  --csv benchmarks/airline_support_benchmark.csv \
  --name airline-support-suite \
  --prompt "Create an end-to-end benchmark for the airline support agent. Treat the input column as the user message, expected_behavior as required behavior, and rubric as grading guidance."
```

```sh
relai simulate \
  --benchmarks airline-support-suite \
  --result-json .relai/runs/airline-support-suite-simulation.json
```

```sh
relai optimize --benchmarks airline-support-suite
```

### Global Evaluators

Create a small smoke learning environment, add a global evaluator that fails responses taking more than five seconds, simulate, then optimize with the evaluator active.

```sh
relai learning-env create \
  --prompt "Create a simple smoke test where a user asks the airline support agent for the standard baggage policy. The agent should answer briefly with the standard ticket baggage allowance." \
  --name response-time-smoke-test
```

```sh
relai evaluator create \
  --prompt "Create a global end-to-end evaluator that fails any simulation where the agent's total response time is greater than 5 seconds. Pass responses that finish in 5 seconds or less, and give concise feedback with the observed response time when available." \
  --name response-time
```

```sh
relai simulate \
  --learning-envs response-time-smoke-test \
  --result-json .relai/runs/response-time-smoke-test-simulation.json
```

```sh
relai optimize --learning-envs response-time-smoke-test
```

## Local Logs

Each chat session is saved as JSONL under `logs/`. Session files are ignored by Git.

## Checks

```sh
uv run pytest
npm --prefix web run lint
npm --prefix web run build
```
