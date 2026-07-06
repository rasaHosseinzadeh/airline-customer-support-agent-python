# RELAI Sample Agent

A guided RELAI CLI learning-track app for a Python SDK airline customer support agent.

The demo has two parts:

- FastAPI backend exposing a simple airline support agent built with the OpenAI Agents SDK for Python.
- Next.js light-mode UI for chat, streamed responses, local session history, and sequential RELAI learning tracks.

## Prerequisites

- Python 3.11+
- Node.js 20+
- `uv`
- `OPENAI_API_KEY` in your environment, or ready to paste when prompted

## Start the App

Run the onboarding launcher from the repository root:

```sh
./start.sh
```

The script prompts for your OpenAI API key when needed, saves it to the ignored `.env` file, installs missing dependencies, starts the API and UI, and opens the web app in your browser. The app can install the `relai` CLI for you as the first onboarding step. It uses `8000` for the API and `3000` for the UI when available, then automatically moves to the next open ports if either is already in use.

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

Turn one simple plain-English behavior prompt into a learning environment,
measure the current agent against it, then optimize toward that behavior. Use
this when you have a target behavior in mind and want the agent to follow it
reliably.

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
relai optimize
```

### Fix Unwanted Behavior

Capture a real, undesirable behavior in a session log, then turn that log plus
your feedback into a learning environment and optimize the unwanted behavior
away. Use this when the agent did something wrong and you want to stop it from
happening again.

Run the built-in scenario prompt in the chat UI:

```text
Can you write a chocolate chip cookie recipe?
```

The app saves the chat as `logs/<session-id>.jsonl`.

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
relai optimize
```

### Benchmark

Register a reusable benchmark in CSV format, then run simulation and
optimization against it. Use this when you have a set of samples, each with
inputs, expected outputs, and sample-specific evaluators, that should be rerun
together.

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
relai optimize
```

### Global Evaluators

Create one evaluator that applies across all simulations for the agent. Use this
when one scoring rule should apply globally instead of living in a single
learning environment.

```sh
relai learning-env create \
  --prompt "Create a smoke test where a user asks the airline support agent to explain everything about the airline's policies in full detail, including baggage allowances for every fare class, carry-on rules, seat selection and change fees, cancellation and refund terms, boarding procedure, and loyalty perks. The agent should respond helpfully and completely." \
  --name response-token-smoke-test
```

```sh
relai evaluator create \
  --prompt "Create a global end-to-end evaluator that scores 1 when every agent response is 100 tokens or fewer, and scores 0 when any agent response is above 100 tokens. Give concise feedback with the observed token count when available." \
  --name response-token
```

```sh
relai simulate \
  --learning-envs response-token-smoke-test \
  --result-json .relai/runs/response-token-smoke-test-simulation.json
```

```sh
relai optimize
```

## Local Logs

Each chat session is saved as JSONL under `logs/`. Session files are ignored by Git.

## Checks

```sh
uv run pytest
npm --prefix web run lint
npm --prefix web run build
```
