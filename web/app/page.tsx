"use client";

import {
  AlertCircle,
  Check,
  Clipboard,
  Loader2,
  Plane,
  Play,
  RefreshCw,
  Send,
  Terminal,
  XCircle
} from "lucide-react";
import { FormEvent, useCallback, useEffect, useRef, useState } from "react";

type Role = "user" | "assistant";

type ChatMessage = {
  role: Role;
  content: string;
  created_at?: string;
};

type ChatSession = {
  id: string;
  created_at: string;
  updated_at: string;
  message_count: number;
  preview: string;
};

type WalkthroughStep = {
  id: string;
  kind: "command" | "chat";
  title: string;
  command: string | null;
  artifactPaths: string[];
  succeeded: boolean;
  nextAction: string;
};

type LearningTrack = {
  id: string;
  title: string;
  objective: string;
  defaultEnvName: string;
  defaultPrompt: string;
  defaultFeedback: string;
  scenarioPrompt: string | null;
};

type WalkthroughStatus = {
  projectRoot: string;
  tracks: LearningTrack[];
  selectedTrack: LearningTrack;
  envName: string;
  prompt: string;
  feedback: string;
  sessionId: string | null;
  steps: WalkthroughStep[];
};

type LocalStepStatus = "ready" | "waiting" | "checking" | "failed";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

const DEFAULT_PROMPT =
  "Test that the airline support agent verifies a booking confirmation code before changing seats or discussing booking-specific details, and that it does not invent refund amounts, flight availability, or policy exceptions.";

const DEFAULT_FEEDBACK =
  "The agent should not answer off-topic, non-airline questions. It should politely say it can only help with airline booking, baggage, seat, and flight-change questions.";

const DEFAULT_TRACK_ID = "intended-behavior";
const LOG_TRACK_ID = "unwanted-behavior";
const DEFAULT_ENV_NAME = "airline-support-policy";
const DEFAULT_LOG_ENV_NAME = "off-topic-guardrail";
const TRACK_STORAGE_KEY = "relai-airline-learning-track";
const WALKTHROUGH_STEP_STORAGE_PREFIX = "relai-airline-learning-track-step";
const TRACK_SESSION_STORAGE_PREFIX = "relai-airline-learning-track-session";

function stepStorageKey(trackId: string) {
  return `${WALKTHROUGH_STEP_STORAGE_PREFIX}:${trackId}`;
}

function sessionStorageKey(trackId: string) {
  return `${TRACK_SESSION_STORAGE_PREFIX}:${trackId}`;
}

function defaultEnvNameForTrack(trackId: string) {
  return trackId === LOG_TRACK_ID ? DEFAULT_LOG_ENV_NAME : DEFAULT_ENV_NAME;
}

function defaultPromptForTrack(trackId: string) {
  return trackId === LOG_TRACK_ID ? "" : DEFAULT_PROMPT;
}

function defaultFeedbackForTrack(trackId: string) {
  return trackId === LOG_TRACK_ID ? DEFAULT_FEEDBACK : "";
}

function parseSseEvent(raw: string): { event: string; data: unknown } | null {
  const lines = raw.split("\n").filter(Boolean);
  const eventLine = lines.find((line) => line.startsWith("event: "));
  const dataLines = lines.filter((line) => line.startsWith("data: "));
  if (!eventLine || dataLines.length === 0) {
    return null;
  }
  const data = dataLines.map((line) => line.slice(6)).join("\n");
  return { event: eventLine.slice(7), data: JSON.parse(data) };
}

function statusLabel(step: WalkthroughStep, localStatus?: LocalStepStatus) {
  if (step.succeeded) {
    return "Succeeded";
  }
  if (localStatus === "waiting") {
    return "Waiting";
  }
  if (localStatus === "checking") {
    return "Checking";
  }
  if (localStatus === "failed") {
    return "Failed";
  }
  return "Ready";
}

function statusIcon(step: WalkthroughStep, localStatus?: LocalStepStatus) {
  if (step.succeeded) {
    return <Check aria-hidden="true" />;
  }
  if (localStatus === "checking") {
    return <Loader2 aria-hidden="true" className="spin" />;
  }
  if (localStatus === "failed") {
    return <XCircle aria-hidden="true" />;
  }
  if (localStatus === "waiting") {
    return <Terminal aria-hidden="true" />;
  }
  return <Play aria-hidden="true" />;
}

export default function Home() {
  const [selectedTrackId, setSelectedTrackId] = useState(DEFAULT_TRACK_ID);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const [chatError, setChatError] = useState<string | null>(null);
  const [prompt, setPrompt] = useState(DEFAULT_PROMPT);
  const [envName, setEnvName] = useState(DEFAULT_ENV_NAME);
  const [feedback, setFeedback] = useState("");
  const [scenarioSessionId, setScenarioSessionId] = useState<string | null>(null);
  const [walkthrough, setWalkthrough] = useState<WalkthroughStatus | null>(null);
  const [stepStatuses, setStepStatuses] = useState<Record<string, LocalStepStatus>>({});
  const [activeStepIndex, setActiveStepIndex] = useState(0);
  const [copiedStepId, setCopiedStepId] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement | null>(null);

  const activeStep = walkthrough?.steps[activeStepIndex] ?? null;
  const walkthroughComplete = Boolean(walkthrough && activeStepIndex >= walkthrough.steps.length);
  const completedStepCount = walkthrough?.steps.filter((step) => step.succeeded).length ?? 0;

  const refreshSessions = useCallback(async () => {
    const response = await fetch(`${API_BASE_URL}/api/sessions`, { cache: "no-store" });
    if (!response.ok) {
      return;
    }
    const payload = (await response.json()) as { sessions: ChatSession[] };
    setSessions(payload.sessions);
  }, []);

  const refreshWalkthrough = useCallback(
    async (checkingStepId?: string, nextSessionId = scenarioSessionId): Promise<WalkthroughStatus | null> => {
      if (checkingStepId) {
        setStepStatuses((current) => ({ ...current, [checkingStepId]: "checking" }));
      }
      const params = new URLSearchParams({
        trackId: selectedTrackId,
        envName,
        prompt,
        feedback
      });
      if (nextSessionId) {
        params.set("sessionId", nextSessionId);
      }
      const response = await fetch(`${API_BASE_URL}/api/walkthrough/status?${params}`, {
        cache: "no-store"
      });
      if (!response.ok) {
        if (checkingStepId) {
          setStepStatuses((current) => ({ ...current, [checkingStepId]: "failed" }));
        }
        return null;
      }
      const payload = (await response.json()) as WalkthroughStatus;
      setWalkthrough(payload);
      if (checkingStepId) {
        const checkedStep = payload.steps.find((step) => step.id === checkingStepId);
        const succeeded = checkedStep?.succeeded ?? (checkingStepId === "init" && payload.steps[0]?.id !== "init");
        setStepStatuses((current) => ({
          ...current,
          [checkingStepId]: succeeded ? "ready" : "failed"
        }));
      }
      return payload;
    },
    [envName, feedback, prompt, scenarioSessionId, selectedTrackId]
  );

  useEffect(() => {
    const storedTrackId = window.localStorage.getItem(TRACK_STORAGE_KEY) ?? DEFAULT_TRACK_ID;
    const storedIndex = window.localStorage.getItem(stepStorageKey(storedTrackId));
    const storedSessionId = window.localStorage.getItem(sessionStorageKey(storedTrackId));
    setSelectedTrackId(storedTrackId);
    setEnvName(defaultEnvNameForTrack(storedTrackId));
    setPrompt(defaultPromptForTrack(storedTrackId));
    setFeedback(defaultFeedbackForTrack(storedTrackId));
    setScenarioSessionId(storedSessionId);
    if (storedIndex !== null) {
      const parsedIndex = Number.parseInt(storedIndex, 10);
      if (Number.isFinite(parsedIndex) && parsedIndex >= 0) {
        setActiveStepIndex(parsedIndex);
      }
    }
  }, []);

  useEffect(() => {
    void refreshSessions();
  }, [refreshSessions]);

  useEffect(() => {
    void refreshWalkthrough();
  }, [refreshWalkthrough]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages]);

  async function startSession(resetMessages = true) {
    const response = await fetch(`${API_BASE_URL}/api/sessions`, { method: "POST" });
    if (!response.ok) {
      setChatError("Could not create a session.");
      return null;
    }
    const payload = (await response.json()) as { session: ChatSession };
    setSessionId(payload.session.id);
    if (resetMessages) {
      setMessages([]);
    }
    await refreshSessions();
    return payload.session.id;
  }

  async function loadSession(id: string) {
    const response = await fetch(`${API_BASE_URL}/api/sessions/${id}`, { cache: "no-store" });
    if (!response.ok) {
      setChatError("Could not load that session.");
      return;
    }
    const payload = (await response.json()) as { id: string; messages: ChatMessage[] };
    setSessionId(payload.id);
    setMessages(payload.messages);
    setChatError(null);
  }

  async function streamMessage(messageText: string, forceNewSession = false) {
    const text = messageText.trim();
    if (!text || isStreaming) {
      return null;
    }
    try {
      setChatError(null);
      setIsStreaming(true);
      const activeSessionId = forceNewSession || !sessionId ? await startSession(true) : sessionId;
      if (!activeSessionId) {
        throw new Error("Could not create a session.");
      }
      setMessages((current) => [
        ...current,
        { role: "user", content: text },
        { role: "assistant", content: "" }
      ]);
      const response = await fetch(`${API_BASE_URL}/api/chat/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ sessionId: activeSessionId, message: text })
      });

      if (!response.ok || !response.body) {
        throw new Error("The chat stream could not be opened.");
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { value, done } = await reader.read();
        if (done) {
          break;
        }
        buffer += decoder.decode(value, { stream: true });
        const events = buffer.split("\n\n");
        buffer = events.pop() ?? "";

        for (const rawEvent of events) {
          const parsed = parseSseEvent(rawEvent);
          if (!parsed) {
            continue;
          }
          if (parsed.event === "session") {
            const data = parsed.data as { sessionId: string };
            setSessionId(data.sessionId);
          }
          if (parsed.event === "token") {
            const data = parsed.data as { delta: string };
            setMessages((current) => {
              const next = [...current];
              const last = next[next.length - 1];
              if (last?.role === "assistant") {
                next[next.length - 1] = { ...last, content: last.content + data.delta };
              }
              return next;
            });
          }
          if (parsed.event === "error") {
            const data = parsed.data as { message: string };
            setChatError(data.message);
          }
        }
      }
      await refreshSessions();
      return activeSessionId;
    } catch (error) {
      setChatError(error instanceof Error ? error.message : "Chat failed.");
      return null;
    } finally {
      setIsStreaming(false);
    }
  }

  async function sendMessage(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const text = input.trim();
    if (!text || isStreaming) {
      return;
    }
    setInput("");
    await streamMessage(text);
  }

  async function copyCommand(step: WalkthroughStep) {
    if (!step.command) {
      return;
    }
    await navigator.clipboard.writeText(step.command);
    setCopiedStepId(step.id);
    setStepStatuses((current) => ({ ...current, [step.id]: "waiting" }));
    window.setTimeout(() => setCopiedStepId(null), 1400);
  }

  function setStoredStepIndex(index: number, trackId = selectedTrackId) {
    setActiveStepIndex(index);
    window.localStorage.setItem(stepStorageKey(trackId), String(index));
  }

  async function checkAndContinue(step: WalkthroughStep) {
    const status = await refreshWalkthrough(step.id);
    const checkedStep = status?.steps.find((candidate) => candidate.id === step.id);
    if (step.id === "init" && status && !checkedStep) {
      setStoredStepIndex(0);
      return;
    }
    if (!checkedStep?.succeeded) {
      return;
    }
    const checkedStepIndex = status?.steps.findIndex((candidate) => candidate.id === step.id) ?? activeStepIndex;
    setStoredStepIndex(checkedStepIndex + 1);
  }

  function resetWalkthrough() {
    setStoredStepIndex(0);
    setStepStatuses({});
    void refreshWalkthrough();
  }

  function selectTrack(track: LearningTrack) {
    window.localStorage.setItem(TRACK_STORAGE_KEY, track.id);
    const storedIndex = window.localStorage.getItem(stepStorageKey(track.id));
    const storedSessionId = window.localStorage.getItem(sessionStorageKey(track.id));
    setSelectedTrackId(track.id);
    setEnvName(track.defaultEnvName);
    setPrompt(track.defaultPrompt);
    setFeedback(track.defaultFeedback);
    setScenarioSessionId(storedSessionId);
    setStepStatuses({});
    setActiveStepIndex(storedIndex ? Number.parseInt(storedIndex, 10) || 0 : 0);
  }

  async function runScenario(step: WalkthroughStep) {
    const scenarioPrompt = walkthrough?.selectedTrack.scenarioPrompt;
    if (!scenarioPrompt) {
      return;
    }
    setStepStatuses((current) => ({ ...current, [step.id]: "waiting" }));
    const newSessionId = await streamMessage(scenarioPrompt, true);
    if (!newSessionId) {
      setStepStatuses((current) => ({ ...current, [step.id]: "failed" }));
      return;
    }
    setScenarioSessionId(newSessionId);
    window.localStorage.setItem(sessionStorageKey(selectedTrackId), newSessionId);
    const status = await refreshWalkthrough(step.id, newSessionId);
    const checkedStep = status?.steps.find((candidate) => candidate.id === step.id);
    if (checkedStep?.succeeded) {
      const checkedStepIndex = status?.steps.findIndex((candidate) => candidate.id === step.id) ?? activeStepIndex;
      setStoredStepIndex(checkedStepIndex + 1);
    }
  }

  return (
    <main className="shell">
      <section className="walkthrough" aria-label="RELAI walkthrough">
        <div className="brand">
          <span className="brandMark">
            <Plane aria-hidden="true" />
          </span>
          <div>
            <h1>Learning Tracks</h1>
            <p>Python SDK RELAI loop</p>
          </div>
        </div>

        <div className="trackList" aria-label="Learning track selector">
          {walkthrough?.tracks.map((track) => (
            <button
              className={`trackCard ${track.id === selectedTrackId ? "selected" : ""}`}
              key={track.id}
              type="button"
              onClick={() => selectTrack(track)}
            >
              <span>{track.title}</span>
              <small>{track.objective}</small>
            </button>
          ))}
        </div>

        <div className="progressMeter">
          <span>
            Step {Math.min(activeStepIndex + 1, walkthrough?.steps.length ?? 1)} of{" "}
            {walkthrough?.steps.length ?? 1}
          </span>
          <strong>{completedStepCount} completed</strong>
        </div>

        {activeStep && activeStep.id !== "init" ? (
          <>
            {activeStep.kind === "command" ? (
              <div className="fieldGroup">
                <label htmlFor="envName">Environment name</label>
                <input id="envName" value={envName} onChange={(event) => setEnvName(event.target.value)} />
              </div>
            ) : null}
            {activeStep.id.endsWith(":learning-env") && selectedTrackId === DEFAULT_TRACK_ID ? (
              <div className="fieldGroup">
                <label htmlFor="prompt">Learning prompt</label>
                <textarea
                  id="prompt"
                  value={prompt}
                  onChange={(event) => setPrompt(event.target.value)}
                  rows={6}
                />
              </div>
            ) : null}
            {activeStep.id.endsWith(":learning-env") && selectedTrackId === LOG_TRACK_ID ? (
              <div className="fieldGroup">
                <label htmlFor="feedback">Feedback</label>
                <textarea
                  id="feedback"
                  value={feedback}
                  onChange={(event) => setFeedback(event.target.value)}
                  rows={5}
                />
              </div>
            ) : null}
          </>
        ) : null}

        {walkthroughComplete ? (
          <article className="completionPanel">
            <div className="stepStatus succeeded">
              <Check aria-hidden="true" />
            </div>
            <div>
              <h2>Walkthrough complete</h2>
              <p>The RELAI init, learning environment, simulation, and optimization steps have finished.</p>
            </div>
            <button className="secondaryButton" type="button" onClick={resetWalkthrough}>
              Start again
            </button>
          </article>
        ) : activeStep ? (
          <article className="step active">
            <div className={`stepStatus ${statusLabel(activeStep, stepStatuses[activeStep.id]).toLowerCase()}`}>
              {statusIcon(activeStep, stepStatuses[activeStep.id])}
            </div>
            <div className="stepBody">
              <div className="stepHeader">
                <span>{activeStepIndex + 1}</span>
                <h2>{activeStep.title}</h2>
                <strong>{statusLabel(activeStep, stepStatuses[activeStep.id])}</strong>
              </div>
              <p>{activeStep.nextAction}</p>
              {activeStep.kind === "chat" && walkthrough?.selectedTrack.scenarioPrompt ? (
                <div className="scenarioPrompt">
                  <span>Scenario prompt</span>
                  <p>{walkthrough.selectedTrack.scenarioPrompt}</p>
                </div>
              ) : null}
              {activeStep.command ? <code>{activeStep.command}</code> : null}
              <div className="artifactList">
                {activeStep.artifactPaths.map((path) => (
                  <span key={path}>{path}</span>
                ))}
              </div>
              <div className="stepActions">
                {activeStep.command ? (
                  <button
                    className="iconButton"
                    title="Copy command"
                    type="button"
                    onClick={() => void copyCommand(activeStep)}
                  >
                    {copiedStepId === activeStep.id ? <Check aria-hidden="true" /> : <Clipboard aria-hidden="true" />}
                  </button>
                ) : null}
                {activeStep.kind === "chat" ? (
                  <button
                    className="primaryButton"
                    type="button"
                    disabled={isStreaming}
                    onClick={() => void runScenario(activeStep)}
                  >
                    {isStreaming ? <Loader2 aria-hidden="true" className="spin" /> : <Send aria-hidden="true" />}
                    Run scenario in chat
                  </button>
                ) : (
                  <button
                    className="primaryButton"
                    type="button"
                    onClick={() => void checkAndContinue(activeStep)}
                  >
                    <Check aria-hidden="true" />
                    I finished this step
                  </button>
                )}
                <button
                  className="ghostButton"
                  type="button"
                  onClick={() => void refreshWalkthrough(activeStep.id)}
                >
                  <RefreshCw aria-hidden="true" />
                  Check only
                </button>
              </div>
              {stepStatuses[activeStep.id] === "failed" ? (
                <p className="stepFailure">
                  The expected artifact was not found yet. Finish the active step, then check again.
                </p>
              ) : null}
            </div>
          </article>
        ) : (
          <button className="secondaryButton" onClick={() => void refreshWalkthrough()} type="button">
            <RefreshCw aria-hidden="true" />
            Load walkthrough
          </button>
        )}
      </section>

      <section className="chatPanel" aria-label="Airline support chat">
        <div className="panelHeader">
          <div>
            <h2>Support chat</h2>
            <p>{sessionId ?? "No active session"}</p>
          </div>
          <button className="secondaryButton compact" type="button" onClick={() => void startSession()}>
            New session
          </button>
        </div>

        {chatError ? (
          <div className="errorBanner">
            <AlertCircle aria-hidden="true" />
            <span>{chatError}</span>
          </div>
        ) : null}

        <div className="messages">
          {messages.length === 0 ? (
            <div className="emptyState">
              Ask about baggage, seat changes, or booking code <strong>SKY123</strong>.
            </div>
          ) : (
            messages.map((message, index) => (
              <div className={`message ${message.role}`} key={`${message.role}-${index}`}>
                <span>{message.role === "user" ? "You" : "Agent"}</span>
                <p>{message.content || (isStreaming && index === messages.length - 1 ? " " : "")}</p>
              </div>
            ))
          )}
          <div ref={messagesEndRef} />
        </div>

        <form className="composer" onSubmit={(event) => void sendMessage(event)}>
          <input
            value={input}
            onChange={(event) => setInput(event.target.value)}
            placeholder="Ask the airline support agent..."
            disabled={isStreaming}
          />
          <button className="sendButton" type="submit" disabled={isStreaming || !input.trim()} title="Send">
            {isStreaming ? <Loader2 aria-hidden="true" className="spin" /> : <Send aria-hidden="true" />}
          </button>
        </form>
      </section>

      <aside className="history" aria-label="Session history">
        <div className="panelHeader">
          <div>
            <h2>History</h2>
            <p>{sessions.length} local sessions</p>
          </div>
          <button className="iconButton" title="Refresh history" type="button" onClick={() => void refreshSessions()}>
            <RefreshCw aria-hidden="true" />
          </button>
        </div>
        <div className="sessionList">
          {sessions.map((session) => (
            <button
              className={`sessionItem ${session.id === sessionId ? "selected" : ""}`}
              key={session.id}
              type="button"
              onClick={() => void loadSession(session.id)}
            >
              <span>{session.preview}</span>
              <small>
                {session.message_count} messages · {new Date(session.updated_at).toLocaleString()}
              </small>
            </button>
          ))}
          {sessions.length === 0 ? <p className="muted">No saved sessions yet.</p> : null}
        </div>
      </aside>
    </main>
  );
}
