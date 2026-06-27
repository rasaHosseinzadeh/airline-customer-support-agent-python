"use client";

import {
  AlertCircle,
  ArrowRight,
  Check,
  ChevronDown,
  CircleHelp,
  History,
  ListChecks,
  Loader2,
  MessageSquare,
  MoreVertical,
  PanelLeftClose,
  PanelLeftOpen,
  Plus,
  RefreshCw,
  Repeat2,
  RotateCcw,
  Send,
  Sparkles,
  Trash2
} from "lucide-react";
import { FormEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle
} from "@/components/ui/card";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger
} from "@/components/ui/dropdown-menu";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger
} from "@/components/ui/tooltip";
import { CommandBlock } from "@/components/command-block";
import { GuidedTour, type TourStep } from "@/components/tour";
import { SetupGate } from "@/components/setup-gate";
import { ThemeToggle } from "@/components/theme-toggle";
import { TrackPicker } from "@/components/track-picker";
import { cn } from "@/lib/utils";

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
  summary: string;
  useCase: string;
};

type PrerequisitesStatus = {
  ready: boolean;
  projectRoot: string;
  steps: WalkthroughStep[];
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
const HISTORY_COLLAPSED_STORAGE_KEY = "relai-history-collapsed";
const TOUR_SEEN_STORAGE_KEY = "relai-tour-seen";
const TRACK_CHOSEN_STORAGE_KEY = "relai-track-chosen";

const TOUR_STEPS: TourStep[] = [
  {
    selector: '[data-tour="chat"]',
    placement: "center",
    title: "Chat with the support agent",
    body: "This is an airline customer support agent. Talk to it here to see how it responds — it's the agent you'll be testing and improving."
  },
  {
    selector: '[data-tour="history"]',
    placement: "right",
    title: "Your chat sessions",
    body: "Every conversation is saved here. Start a new session or reopen an earlier one anytime."
  },
  {
    selector: '[data-tour="tracks"]',
    placement: "left",
    title: "Choose what to learn",
    body: "Each learning track is a short, guided lesson for one RELAI feature. We'll open the track picker right after this tour so you can choose — and you can switch tracks here anytime."
  },
  {
    selector: '[data-tour="step"]',
    placement: "left",
    title: "Follow one step at a time",
    body: "For each step, copy the command and run it in your terminal. The app watches for the result and moves you forward automatically — no clicking needed."
  },
  {
    selector: '[data-tour="progress"]',
    placement: "left",
    title: "Track your progress",
    body: "See how many steps you've completed in the current learning track."
  }
];

const POLL_INTERVAL_MS = 2500;

type MobileView = "steps" | "chat" | "sessions";

// Maps a tour step's target to the mobile tab that must be active to show it.
const STEP_TO_TAB: Record<string, MobileView> = {
  '[data-tour="chat"]': "chat",
  '[data-tour="history"]': "sessions",
  '[data-tour="tracks"]': "steps",
  '[data-tour="step"]': "steps",
  '[data-tour="progress"]': "steps"
};

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
  const [historyCollapsed, setHistoryCollapsed] = useState(false);
  const [tourOpen, setTourOpen] = useState(false);
  const [tourSeen, setTourSeen] = useState(false);
  const [prereq, setPrereq] = useState<PrerequisitesStatus | null>(null);
  const [gateEngaged, setGateEngaged] = useState(false);
  const [gateDismissed, setGateDismissed] = useState(false);
  const [expandedIndex, setExpandedIndex] = useState(0);
  const [pickerOpen, setPickerOpen] = useState(false);
  const [trackChosen, setTrackChosen] = useState(false);
  const [mobileView, setMobileView] = useState<MobileView>("steps");
  const [isDesktop, setIsDesktop] = useState(true);
  const messagesEndRef = useRef<HTMLDivElement | null>(null);
  const walkthroughRef = useRef<HTMLElement | null>(null);
  const pollInFlightRef = useRef(false);
  const prereqPollInFlightRef = useRef(false);
  const tourInitedRef = useRef(false);

  // Open the track picker the first time, once the gate + tour are out of the way.
  function maybeOpenPicker() {
    if (window.localStorage.getItem(TRACK_CHOSEN_STORAGE_KEY) !== "1") {
      setPickerOpen(true);
    }
  }

  function closeTour() {
    window.localStorage.setItem(TOUR_SEEN_STORAGE_KEY, "1");
    setTourSeen(true);
    setTourOpen(false);
    maybeOpenPicker();
  }

  function continueFromGate() {
    setGateDismissed(true);
    if (!tourSeen) {
      setTourOpen(true);
    } else {
      maybeOpenPicker();
    }
  }

  function closePicker() {
    window.localStorage.setItem(TRACK_CHOSEN_STORAGE_KEY, "1");
    setTrackChosen(true);
    setPickerOpen(false);
  }

  function choosePicker(picked: { id: string }) {
    const track = walkthrough?.tracks.find((candidate) => candidate.id === picked.id);
    if (track) {
      selectTrack(track);
    }
    closePicker();
  }

  function toggleHistory() {
    setHistoryCollapsed((current) => {
      const next = !current;
      window.localStorage.setItem(HISTORY_COLLAPSED_STORAGE_KEY, next ? "1" : "0");
      return next;
    });
  }

  const activeStep = walkthrough?.steps[activeStepIndex] ?? null;
  const walkthroughComplete = Boolean(walkthrough && activeStepIndex >= walkthrough.steps.length);
  const completedStepCount = walkthrough?.steps.filter((step) => step.succeeded).length ?? 0;
  const totalSteps = walkthrough?.steps.length ?? 1;
  const currentStepNumber = Math.min(activeStepIndex + 1, totalSteps);
  const progressPercent = walkthroughComplete
    ? 100
    : Math.round((Math.min(activeStepIndex, totalSteps) / totalSteps) * 100);

  // Blocking welcome gate: shown first, until `relai setup` + `relai init` are done. The tour
  // starts only after the gate is dismissed. `gateEngaged` latches once the gate first appears so
  // the success state stays visible until the user clicks through; an already-set-up user (ready on
  // load) never engages it and goes straight to the tour.
  const showGate = (gateEngaged || Boolean(prereq && !prereq.ready)) && !gateDismissed;

  const activeStepRef = useRef(activeStep);
  activeStepRef.current = activeStep;
  const activeStepIndexRef = useRef(activeStepIndex);
  activeStepIndexRef.current = activeStepIndex;

  const refreshPrerequisites = useCallback(async (): Promise<PrerequisitesStatus | null> => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/prerequisites/status`, { cache: "no-store" });
      if (!response.ok) {
        return null;
      }
      const payload = (await response.json()) as PrerequisitesStatus;
      setPrereq(payload);
      return payload;
    } catch {
      // Backend not reachable (e.g. starting up) — degrade gracefully; pollers retry.
      return null;
    }
  }, []);

  const refreshSessions = useCallback(async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/sessions`, { cache: "no-store" });
      if (!response.ok) {
        return;
      }
      const payload = (await response.json()) as { sessions: ChatSession[] };
      setSessions(payload.sessions);
    } catch {
      // Backend not reachable yet — ignore; this is refetched on the next action/poll.
    }
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
      try {
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
      } catch {
        if (checkingStepId) {
          setStepStatuses((current) => ({ ...current, [checkingStepId]: "failed" }));
        }
        return null;
      }
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
    setHistoryCollapsed(window.localStorage.getItem(HISTORY_COLLAPSED_STORAGE_KEY) === "1");
    setTourSeen(window.localStorage.getItem(TOUR_SEEN_STORAGE_KEY) === "1");
    setTrackChosen(window.localStorage.getItem(TRACK_CHOSEN_STORAGE_KEY) === "1");
  }, []);

  // Track the lg breakpoint so the collapsed history rail stays a desktop-only affordance.
  useEffect(() => {
    const query = window.matchMedia("(min-width: 1024px)");
    const update = () => setIsDesktop(query.matches);
    update();
    query.addEventListener("change", update);
    return () => query.removeEventListener("change", update);
  }, []);

  useEffect(() => {
    void refreshSessions();
  }, [refreshSessions]);

  useEffect(() => {
    void refreshWalkthrough();
  }, [refreshWalkthrough]);

  useEffect(() => {
    void refreshPrerequisites();
  }, [refreshPrerequisites]);

  // Latch the gate open once it first becomes relevant (so the success state can persist).
  useEffect(() => {
    if (prereq && !prereq.ready && !gateDismissed) {
      setGateEngaged(true);
    }
  }, [prereq, gateDismissed]);

  // Poll the prerequisite status while the gate is up (until ready) so it advances automatically.
  useEffect(() => {
    if (!showGate || prereq?.ready) {
      return;
    }
    let cancelled = false;
    const tick = async () => {
      if (prereqPollInFlightRef.current) {
        return;
      }
      prereqPollInFlightRef.current = true;
      try {
        await refreshPrerequisites();
      } finally {
        prereqPollInFlightRef.current = false;
      }
      if (cancelled) {
        return;
      }
    };
    const intervalId = window.setInterval(tick, POLL_INTERVAL_MS);
    return () => {
      cancelled = true;
      window.clearInterval(intervalId);
    };
  }, [showGate, prereq?.ready, refreshPrerequisites]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages]);

  // The walkthrough is a single-open accordion: auto-open the current step, and re-open the new
  // current step whenever progress advances (manual peeks persist until the next advance).
  useEffect(() => {
    setExpandedIndex(activeStepIndex);
  }, [activeStepIndex]);

  // Keep the "current" pointer on the first incomplete step: skip past any step that's already
  // done (e.g. several artifacts completed between polls, or resuming a partially-finished track).
  useEffect(() => {
    if (walkthrough && !walkthroughComplete && activeStep?.succeeded) {
      setStoredStepIndex(activeStepIndex + 1);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [walkthrough, walkthroughComplete, activeStep?.succeeded, activeStepIndex]);

  // Decide the first-load flow once both the walkthrough and prerequisite state are known.
  // Sequence: setup gate (if needed) → tour → track picker. If prerequisites are already met the
  // gate won't show, so start the tour here; if the tour was already seen, jump to the picker.
  // Otherwise the gate appears first and its "Start the tour" button continues the chain.
  useEffect(() => {
    if (tourInitedRef.current || !walkthrough || !prereq || !prereq.ready) {
      return;
    }
    tourInitedRef.current = true;
    if (!tourSeen) {
      setTourOpen(true);
    } else {
      maybeOpenPicker();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [walkthrough, prereq, tourSeen]);

  function setStoredStepIndex(index: number, trackId = selectedTrackId) {
    setActiveStepIndex(index);
    window.localStorage.setItem(stepStorageKey(trackId), String(index));
  }

  // Whether the active step can be auto-detected by polling the backend.
  const canPoll = Boolean(
    activeStep &&
      !walkthroughComplete &&
      !isStreaming &&
      !showGate &&
      !activeStep.succeeded &&
      (activeStep.kind === "command" || (activeStep.kind === "chat" && scenarioSessionId))
  );

  // Auto-detect: while waiting on a command/log artifact, poll the backend and
  // advance the moment the artifact appears — no clicking required.
  useEffect(() => {
    if (!canPoll) {
      return;
    }
    let cancelled = false;
    const tick = async () => {
      if (pollInFlightRef.current) {
        return;
      }
      pollInFlightRef.current = true;
      try {
        const step = activeStepRef.current;
        if (!step) {
          return;
        }
        const status = await refreshWalkthrough();
        if (cancelled || !status) {
          return;
        }
        const fresh = status.steps.find((candidate) => candidate.id === step.id);
        if (step.id === "init" && !fresh) {
          toast.success("RELAI initialized", { description: "Moving on to the next step." });
          setStoredStepIndex(0);
          return;
        }
        if (fresh?.succeeded) {
          const idx = status.steps.findIndex((candidate) => candidate.id === step.id);
          toast.success("Command ran successfully", { description: `"${step.title}" is complete.` });
          setStoredStepIndex((idx >= 0 ? idx : activeStepIndexRef.current) + 1);
        }
      } finally {
        pollInFlightRef.current = false;
      }
    };
    const intervalId = window.setInterval(tick, POLL_INTERVAL_MS);
    return () => {
      cancelled = true;
      window.clearInterval(intervalId);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [canPoll, refreshWalkthrough]);

  async function startSession(resetMessages = true) {
    try {
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
    } catch {
      setChatError("Could not reach the server. Is the backend running?");
      return null;
    }
  }

  async function loadSession(id: string) {
    try {
      const response = await fetch(`${API_BASE_URL}/api/sessions/${id}`, { cache: "no-store" });
      if (!response.ok) {
        setChatError("Could not load that session.");
        return;
      }
      const payload = (await response.json()) as { id: string; messages: ChatMessage[] };
      setSessionId(payload.id);
      setMessages(payload.messages);
      setChatError(null);
    } catch {
      setChatError("Could not reach the server. Is the backend running?");
    }
  }

  async function deleteSession(id: string) {
    try {
      const response = await fetch(`${API_BASE_URL}/api/sessions/${id}`, { method: "DELETE" });
      if (!response.ok) {
        setChatError("Could not delete that session.");
        return;
      }
      // If the deleted session was open or captured for a track, clear those references.
      if (sessionId === id) {
        setSessionId(null);
        setMessages([]);
      }
      if (scenarioSessionId === id) {
        setScenarioSessionId(null);
        window.localStorage.removeItem(sessionStorageKey(selectedTrackId));
      }
      toast.success("Session deleted");
      await refreshSessions();
    } catch {
      setChatError("Could not reach the server. Is the backend running?");
    }
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
    toast.success("Command copied", {
      description: "Paste and run it in your terminal — we'll detect it automatically."
    });
    window.setTimeout(() => setCopiedStepId(null), 1600);
  }

  // Non-destructive restart: reopen the track at step 1 (and scroll to the top) so the user can
  // review/re-run from the beginning. Completed steps keep their checks and the "current" marker
  // stays on the first unfinished step, since progress is derived from on-disk artifacts.
  function restartTrack() {
    setExpandedIndex(0);
    walkthroughRef.current?.scrollTo({ top: 0, behavior: "smooth" });
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
      toast.success("Scenario captured", { description: "Session log saved as the learning source." });
      setStoredStepIndex(checkedStepIndex + 1);
    }
  }

  const localStatus = activeStep ? stepStatuses[activeStep.id] : undefined;
  const verifyState: "detected" | "checking" | "watching" | "failed" | "idle" = useMemo(() => {
    if (!activeStep) return "idle";
    if (activeStep.succeeded) return "detected";
    if (localStatus === "checking") return "checking";
    if (canPoll) return "watching";
    if (localStatus === "failed") return "failed";
    return "idle";
  }, [activeStep, localStatus, canPoll]);

  return (
    <main
      className={cn(
        "flex h-screen flex-col overflow-hidden lg:grid lg:grid-rows-1",
        historyCollapsed
          ? "lg:grid-cols-[3.25rem_minmax(360px,1fr)_minmax(480px,1.5fr)]"
          : "lg:grid-cols-[clamp(220px,16vw,260px)_minmax(360px,1fr)_minmax(480px,1.5fr)]"
      )}
    >
      {/* Mobile top bar — brand + controls + tab switcher (hidden on desktop) */}
      <div className="flex shrink-0 flex-col gap-2 border-b border-border bg-card/40 px-4 py-3 lg:hidden">
        <div className="flex items-center justify-between gap-3">
          <div className="flex min-w-0 items-center gap-2.5">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img className="size-7 shrink-0 rounded-lg object-contain" src="/logo.png" alt="RELAI" />
            <h1 className="truncate text-sm font-semibold tracking-tight">RELAI Onboarding</h1>
          </div>
          <div className="flex items-center gap-1.5">
            <ThemeToggle />
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  size="icon"
                  variant="ghost"
                  className="size-8 text-muted-foreground"
                  onClick={() => setTourOpen(true)}
                  aria-label="Take a tour"
                >
                  <CircleHelp />
                </Button>
              </TooltipTrigger>
              <TooltipContent>Take a tour</TooltipContent>
            </Tooltip>
          </div>
        </div>
        <div className="flex items-center gap-1 rounded-lg bg-muted p-1">
          {(
            [
              { id: "steps", label: "Steps", icon: ListChecks },
              { id: "chat", label: "Chat", icon: MessageSquare },
              { id: "sessions", label: "Sessions", icon: History }
            ] as const
          ).map((tab) => (
            <button
              key={tab.id}
              type="button"
              onClick={() => setMobileView(tab.id)}
              className={cn(
                "flex flex-1 items-center justify-center gap-1.5 rounded-md px-2 py-1.5 text-sm font-medium transition-colors",
                mobileView === tab.id
                  ? "bg-background text-foreground shadow-sm"
                  : "text-muted-foreground hover:text-foreground"
              )}
            >
              <tab.icon className="size-4" />
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      {/* Right column — learning tracks / walkthrough */}
      <section
        ref={walkthroughRef}
        className={cn(
          mobileView === "steps" ? "flex" : "hidden",
          "min-h-0 flex-1 flex-col overflow-y-auto [scrollbar-gutter:stable] bg-muted/40 p-6 lg:flex lg:flex-1 lg:order-3 lg:border-l"
        )}
        aria-label="RELAI walkthrough"
      >
        <div data-tour="tracks">
          <p className="mb-1 text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
            Learning Track
          </p>
          <div className="flex items-center justify-between gap-3">
            <h2 className="min-w-0 truncate text-base font-semibold">
              {walkthrough?.selectedTrack.title ?? "—"}
            </h2>
            <div className="flex shrink-0 items-center gap-1.5">
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button
                    size="icon"
                    variant="ghost"
                    className="size-8 text-muted-foreground"
                    onClick={restartTrack}
                    disabled={!walkthrough}
                    aria-label="Start from the beginning"
                  >
                    <RotateCcw />
                  </Button>
                </TooltipTrigger>
                <TooltipContent>Start from the beginning</TooltipContent>
              </Tooltip>
              <Button size="sm" onClick={() => setPickerOpen(true)} disabled={!walkthrough}>
                <Repeat2 />
                Switch track
              </Button>
            </div>
          </div>
        </div>

        {walkthrough?.selectedTrack ? (
          <p className="mt-2 mb-5 text-[13px] leading-relaxed text-muted-foreground">
            {walkthrough.selectedTrack.objective}
          </p>
        ) : null}

        {/* Steps — single-open accordion */}
        {walkthrough ? (
          <div className="grid gap-2" data-tour="step">
            {walkthrough.steps.map((step, i) => {
              const isDone = step.succeeded;
              const isCurrent = i === activeStepIndex && !walkthroughComplete;
              const isOpen = expandedIndex === i;
              return (
                <div
                  key={step.id}
                  className={cn(
                    "overflow-hidden rounded-lg border bg-card transition-colors",
                    isCurrent ? "border-primary/50 ring-1 ring-primary/40" : "border-border"
                  )}
                >
                  <button
                    type="button"
                    aria-expanded={isOpen}
                    onClick={() => setExpandedIndex((current) => (current === i ? -1 : i))}
                    className="flex w-full items-center gap-3 px-3 py-2.5 text-left"
                  >
                    <StepChip done={isDone} current={isCurrent} number={i + 1} />
                    <span className="min-w-0 flex-1 truncate text-sm font-medium">{step.title}</span>
                    {isCurrent ? (
                      <span className="shrink-0 rounded-full bg-primary/15 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-primary">
                        Current
                      </span>
                    ) : null}
                    <ChevronDown
                      className={cn(
                        "size-4 shrink-0 text-muted-foreground transition-transform",
                        isOpen && "rotate-180"
                      )}
                    />
                  </button>

                  {isOpen ? (
                    <div className="grid gap-4 border-t border-border px-3 py-3.5">
                      <p className="text-[13px] leading-relaxed text-muted-foreground">{step.nextAction}</p>

                      {step.kind === "chat" && walkthrough.selectedTrack.scenarioPrompt ? (
                        <div className="rounded-lg border border-border bg-muted/50 p-3">
                          <p className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
                            Scenario prompt
                          </p>
                          <p className="mt-1.5 text-sm">{walkthrough.selectedTrack.scenarioPrompt}</p>
                        </div>
                      ) : null}

                      {step.command ? (
                        <CommandBlock
                          command={step.command}
                          projectRoot={walkthrough.projectRoot}
                          copied={copiedStepId === step.id}
                          onCopy={() => void copyCommand(step)}
                        />
                      ) : null}

                      {isCurrent || isDone ? (
                        <VerifyStatus state={isDone ? "detected" : verifyState} kind={step.kind} />
                      ) : (
                        <p className="px-0.5 text-sm text-muted-foreground">
                          Finish the current step to start this one.
                        </p>
                      )}

                      {step.kind === "chat" && isCurrent ? (
                        <Button className="w-full" disabled={isStreaming} onClick={() => void runScenario(step)}>
                          {isStreaming ? <Loader2 className="spin" /> : <Send />}
                          Run scenario in chat
                        </Button>
                      ) : null}
                    </div>
                  ) : null}
                </div>
              );
            })}
          </div>
        ) : (
          <Button onClick={() => void refreshWalkthrough()}>
            <RefreshCw />
            Load walkthrough
          </Button>
        )}

        {/* Completion */}
        {walkthroughComplete ? (
          <Card className="mt-3">
            <CardHeader>
              <div className="flex items-center gap-3">
                <div className="flex size-9 items-center justify-center rounded-lg border border-border bg-muted text-[color:var(--success)]">
                  <Sparkles className="size-4.5" />
                </div>
                <div>
                  <CardTitle className="text-base">Walkthrough complete</CardTitle>
                  <CardDescription>Init, learning environment, simulation, and optimization are done.</CardDescription>
                </div>
              </div>
            </CardHeader>
            <CardContent>
              <Button className="w-full" onClick={restartTrack}>
                <RotateCcw />
                Start again
              </Button>
            </CardContent>
          </Card>
        ) : null}

        {/* Progress */}
        <div className="mt-5" data-tour="progress">
          <div className="mb-2 flex items-center justify-between text-xs font-medium text-muted-foreground">
            <span>
              Step {currentStepNumber} of {totalSteps}
            </span>
            <span>{completedStepCount} completed</span>
          </div>
          <div className="h-1.5 w-full overflow-hidden rounded-full bg-muted">
            <div
              className="h-full rounded-full bg-primary transition-all duration-500"
              style={{ width: `${progressPercent}%` }}
            />
          </div>
        </div>
      </section>

      {/* Center — chat */}
      <section
        className={cn(
          mobileView === "chat" ? "flex" : "hidden",
          "min-h-0 flex-1 flex-col overflow-hidden bg-background lg:flex lg:flex-1 lg:order-2"
        )}
        aria-label="Airline support chat"
        data-tour="chat"
      >
        <header className="flex items-center justify-between gap-3 border-b border-border px-6 py-4">
          <div className="flex min-w-0 items-center gap-3">
            <div className="flex size-9 shrink-0 items-center justify-center rounded-lg border border-border bg-muted text-muted-foreground">
              <MessageSquare className="size-4.5" />
            </div>
            <div className="min-w-0">
              <h2 className="truncate text-sm font-semibold">Airline Customer Support Agent</h2>
              <p className="truncate font-mono text-xs text-muted-foreground">{sessionId ?? "No active session"}</p>
            </div>
          </div>
          <div className="flex shrink-0 items-center gap-1.5">
            <div className="hidden items-center gap-1.5 lg:flex">
              <ThemeToggle />
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button
                    size="icon"
                    variant="ghost"
                    className="size-8 text-muted-foreground"
                    onClick={() => setTourOpen(true)}
                    aria-label="Take a tour"
                  >
                    <CircleHelp />
                  </Button>
                </TooltipTrigger>
                <TooltipContent>Take a tour</TooltipContent>
              </Tooltip>
            </div>
            <Button size="sm" onClick={() => void startSession()}>
              New session
            </Button>
          </div>
        </header>

        {chatError ? (
          <div className="mx-6 mt-4 flex items-center gap-2 rounded-lg border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-[color:var(--destructive)]">
            <AlertCircle className="size-4 shrink-0" />
            <span>{chatError}</span>
          </div>
        ) : null}

        <div className="flex-1 overflow-y-auto [scrollbar-gutter:stable] px-6 py-6">
          {messages.length === 0 ? (
            <div className="flex h-full min-h-60 items-center justify-center text-center text-sm text-muted-foreground">
              <p>
                Ask about baggage, seat changes, or booking code{" "}
                <span className="rounded bg-muted px-1.5 py-0.5 font-mono font-semibold text-foreground">SKY123</span>.
              </p>
            </div>
          ) : (
            <div className="flex flex-col gap-5">
              {messages.map((message, index) => {
                const isLast = index === messages.length - 1;
                const streamingHere = isStreaming && isLast && message.role === "assistant";
                return (
                  <div
                    key={`${message.role}-${index}`}
                    className={cn("flex flex-col gap-1.5", message.role === "user" ? "items-end" : "items-start")}
                  >
                    <span className="px-1 text-xs font-semibold text-muted-foreground">
                      {message.role === "user" ? "You" : "Agent"}
                    </span>
                    <div
                      className={cn(
                        "max-w-[min(680px,86%)] rounded-xl px-3.5 py-2.5 text-sm leading-relaxed whitespace-pre-wrap",
                        message.role === "user"
                          ? "rounded-br-sm bg-secondary text-secondary-foreground"
                          : "rounded-bl-sm border border-border bg-card text-card-foreground"
                      )}
                    >
                      <span className={cn(streamingHere && !message.content && "caret")}>{message.content}</span>
                      {streamingHere && message.content ? <span className="caret" /> : null}
                    </div>
                  </div>
                );
              })}
              <div ref={messagesEndRef} />
            </div>
          )}
        </div>

        <form className="flex gap-2 border-t border-border px-6 py-4" onSubmit={(event) => void sendMessage(event)}>
          <Input
            value={input}
            onChange={(event) => setInput(event.target.value)}
            placeholder="Ask the airline support agent…"
            disabled={isStreaming}
            className="h-11"
          />
          <Button type="submit" size="icon" className="size-11" disabled={isStreaming || !input.trim()} title="Send">
            {isStreaming ? <Loader2 className="spin" /> : <Send />}
          </Button>
        </form>
      </section>

      {/* Left column — session history (collapsible) */}
      <aside
        className={cn(
          mobileView === "sessions" ? "flex" : "hidden",
          "min-h-0 flex-1 flex-col bg-muted/40 lg:flex lg:flex-1 lg:order-1 lg:border-r"
        )}
        aria-label="Session history"
        data-tour="history"
      >
        {isDesktop && historyCollapsed ? (
          <div className="flex flex-col items-center gap-2 px-2 py-4">
            <Tooltip>
              <TooltipTrigger asChild>
                <Button size="icon" variant="ghost" className="size-9" onClick={toggleHistory}>
                  <PanelLeftOpen />
                </Button>
              </TooltipTrigger>
              <TooltipContent side="right">Show history</TooltipContent>
            </Tooltip>
            <Tooltip>
              <TooltipTrigger asChild>
                <Button size="icon" variant="ghost" className="size-9" onClick={() => void startSession()}>
                  <Plus />
                </Button>
              </TooltipTrigger>
              <TooltipContent side="right">New session</TooltipContent>
            </Tooltip>
          </div>
        ) : (
          <>
            <div className="flex items-center justify-between gap-2 px-3 py-3.5">
              <div className="flex min-w-0 items-center gap-2.5">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img className="size-8 shrink-0 rounded-lg object-contain" src="/logo.png" alt="RELAI" />
                <div className="min-w-0">
                  <h1 className="truncate text-sm font-semibold leading-tight tracking-tight">RELAI Onboarding</h1>
                </div>
              </div>
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button
                    size="icon"
                    variant="ghost"
                    className="hidden size-8 shrink-0 text-muted-foreground lg:inline-flex"
                    onClick={toggleHistory}
                  >
                    <PanelLeftClose />
                  </Button>
                </TooltipTrigger>
                <TooltipContent>Collapse</TooltipContent>
              </Tooltip>
            </div>

            <div className="px-3 pb-2">
              <Button className="w-full justify-start gap-2" onClick={() => void startSession()}>
                <Plus className="size-4" />
                New session
              </Button>
            </div>

            <div className="flex items-center justify-between px-4 pt-2 pb-1">
              <span className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
                Sessions
              </span>
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button
                    size="icon"
                    variant="ghost"
                    className="size-6 text-muted-foreground"
                    onClick={() => void refreshSessions()}
                  >
                    <RefreshCw className="size-3.5" />
                  </Button>
                </TooltipTrigger>
                <TooltipContent>Refresh</TooltipContent>
              </Tooltip>
            </div>

            <ScrollArea className="flex-1">
              <div className="flex flex-col gap-0.5 px-2 pb-4">
                {sessions.map((session) => (
                  <div
                    key={session.id}
                    className={cn(
                      "group flex items-center rounded-md transition-colors",
                      session.id === sessionId ? "bg-accent" : "hover:bg-accent/60"
                    )}
                  >
                    <button
                      type="button"
                      onClick={() => void loadSession(session.id)}
                      title={session.preview || "New session"}
                      className={cn(
                        "min-w-0 flex-1 truncate py-2 pr-1 pl-2.5 text-left text-sm",
                        session.id === sessionId ? "font-medium text-accent-foreground" : "text-foreground"
                      )}
                    >
                      {session.preview || "New session"}
                    </button>
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <Button
                          size="icon"
                          variant="ghost"
                          className="mr-1 size-7 shrink-0 text-muted-foreground hover:bg-transparent hover:text-foreground"
                          aria-label="Session options"
                        >
                          <MoreVertical />
                        </Button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end">
                        <DropdownMenuItem variant="destructive" onClick={() => void deleteSession(session.id)}>
                          <Trash2 />
                          Delete
                        </DropdownMenuItem>
                      </DropdownMenuContent>
                    </DropdownMenu>
                  </div>
                ))}
                {sessions.length === 0 ? (
                  <p className="px-2.5 py-2 text-sm text-muted-foreground">No saved sessions yet.</p>
                ) : null}
              </div>
            </ScrollArea>
          </>
        )}
      </aside>

      <GuidedTour
        open={tourOpen}
        steps={TOUR_STEPS}
        onClose={closeTour}
        onStep={(selector) => {
          const tab = STEP_TO_TAB[selector];
          if (tab) {
            setMobileView(tab);
          }
        }}
      />

      {showGate && prereq ? (
        <SetupGate
          steps={prereq.steps}
          ready={prereq.ready}
          projectRoot={prereq.projectRoot}
          onContinue={continueFromGate}
          continueLabel={tourSeen ? "Get started" : "Start the tour"}
        />
      ) : null}

      {walkthrough ? (
        <TrackPicker
          tracks={walkthrough.tracks}
          selectedId={selectedTrackId}
          open={pickerOpen}
          onSelect={choosePicker}
          onClose={closePicker}
        />
      ) : null}
    </main>
  );
}

function StepChip({ done, current, number }: { done: boolean; current: boolean; number: number }) {
  return (
    <span
      className={cn(
        "flex size-6 shrink-0 items-center justify-center rounded-md text-xs font-semibold",
        done
          ? "bg-[color:var(--success)] text-background"
          : current
            ? "bg-primary text-primary-foreground"
            : "border border-border bg-muted text-muted-foreground"
      )}
    >
      {done ? <Check className="size-3.5" /> : number}
    </span>
  );
}

function VerifyStatus({
  state,
  kind
}: {
  state: "detected" | "checking" | "watching" | "failed" | "idle";
  kind: "command" | "chat";
}) {
  const base = "flex items-center gap-2 px-0.5 text-sm";
  if (state === "detected") {
    return (
      <div className={cn(base, "text-[color:var(--success)]")}>
        <Check className="size-4 shrink-0" />
        <span>Detected — this step ran successfully.</span>
      </div>
    );
  }
  if (state === "watching" || state === "checking") {
    return (
      <div className={cn(base, "text-muted-foreground")}>
        <Loader2 className="size-4 shrink-0 spin" />
        <span>Watching for {kind === "chat" ? "the scenario run" : "the command to run"}…</span>
      </div>
    );
  }
  if (state === "failed") {
    return (
      <div className={cn(base, "text-[color:var(--destructive)]")}>
        <AlertCircle className="size-4 shrink-0" />
        <span>Not detected yet. Run the {kind === "chat" ? "scenario" : "command"}, then we'll pick it up.</span>
      </div>
    );
  }
  return (
    <div className={cn(base, "text-muted-foreground")}>
      <ArrowRight className="size-4 shrink-0" />
      <span>{kind === "chat" ? "Run the scenario to capture a log." : "Copy and run the command to continue."}</span>
    </div>
  );
}
