"use client";

import { ArrowLeft, ArrowRight, X } from "lucide-react";
import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export type TourStep = {
  selector: string;
  title: string;
  body: string;
  placement?: "left" | "right" | "top" | "bottom" | "center";
};

type Rect = { top: number; left: number; width: number; height: number };

const PAD = 8;
const GAP = 14;
const MARGIN = 16;
const CARD_WIDTH = 320;

function resolveRect(selector: string): Rect | null {
  const el = document.querySelector(selector);
  if (!el) {
    return null;
  }
  const r = el.getBoundingClientRect();
  if (r.width <= 0 || r.height <= 0) {
    return null;
  }
  return { top: r.top, left: r.left, width: r.width, height: r.height };
}

export function GuidedTour({
  steps,
  open,
  onClose,
  onStep
}: {
  steps: TourStep[];
  open: boolean;
  onClose: () => void;
  onStep?: (selector: string) => void;
}) {
  const [activeSteps, setActiveSteps] = useState<TourStep[]>([]);
  const [index, setIndex] = useState(0);
  const [rect, setRect] = useState<Rect | null>(null);
  const [cardSize, setCardSize] = useState<{ width: number; height: number }>({
    width: CARD_WIDTH,
    height: 180
  });
  const cardRef = useRef<HTMLDivElement | null>(null);

  // When the tour opens, keep steps whose target exists in the DOM (it may be behind an inactive
  // mobile tab — we reveal it per step below — so don't require a visible rect here).
  useEffect(() => {
    if (!open) {
      return;
    }
    setActiveSteps(steps.filter((step) => document.querySelector(step.selector)));
    setIndex(0);
  }, [open, steps]);

  const step = activeSteps[index];

  // Reveal the panel that holds this step (e.g. switch the mobile tab) so it's on-screen, then
  // re-measure once the reveal has laid out.
  useEffect(() => {
    if (!open || !step) {
      return;
    }
    onStep?.(step.selector);
    const timer = window.setTimeout(() => setRect(resolveRect(step.selector)), 90);
    return () => window.clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, step]);

  const updateRect = useCallback(() => {
    if (!step) {
      return;
    }
    setRect(resolveRect(step.selector));
  }, [step]);

  useLayoutEffect(() => {
    if (!open || !step) {
      return;
    }
    updateRect();
    window.addEventListener("resize", updateRect);
    window.addEventListener("scroll", updateRect, true);
    return () => {
      window.removeEventListener("resize", updateRect);
      window.removeEventListener("scroll", updateRect, true);
    };
  }, [open, step, updateRect]);

  useLayoutEffect(() => {
    if (cardRef.current) {
      const r = cardRef.current.getBoundingClientRect();
      setCardSize({ width: r.width, height: r.height });
    }
  }, [index, rect, open]);

  const close = useCallback(() => {
    onClose();
  }, [onClose]);

  useEffect(() => {
    if (!open) {
      return;
    }
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        close();
      } else if (event.key === "ArrowRight") {
        setIndex((current) => Math.min(current + 1, activeSteps.length - 1));
      } else if (event.key === "ArrowLeft") {
        setIndex((current) => Math.max(current - 1, 0));
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, activeSteps.length, close]);

  if (!open || !step || activeSteps.length === 0) {
    return null;
  }

  const isFirst = index === 0;
  const isLast = index === activeSteps.length - 1;

  // Compute card position relative to the highlighted rect, clamped to viewport.
  const vw = typeof window !== "undefined" ? window.innerWidth : 1280;
  const vh = typeof window !== "undefined" ? window.innerHeight : 800;
  const placement = step.placement ?? "bottom";

  let cardLeft = MARGIN;
  let cardTop = MARGIN;

  if (rect) {
    switch (placement) {
      case "left":
        cardLeft = rect.left - GAP - cardSize.width;
        cardTop = rect.top;
        break;
      case "right":
        cardLeft = rect.left + rect.width + GAP;
        cardTop = rect.top;
        break;
      case "top":
        cardLeft = rect.left + rect.width / 2 - cardSize.width / 2;
        cardTop = rect.top - GAP - cardSize.height;
        break;
      case "center":
        cardLeft = rect.left + rect.width / 2 - cardSize.width / 2;
        cardTop = rect.top + rect.height / 2 - cardSize.height / 2;
        break;
      case "bottom":
      default:
        cardLeft = rect.left + rect.width / 2 - cardSize.width / 2;
        cardTop = rect.top + rect.height + GAP;
        break;
    }
  }

  cardLeft = Math.min(Math.max(cardLeft, MARGIN), Math.max(MARGIN, vw - cardSize.width - MARGIN));
  cardTop = Math.min(Math.max(cardTop, MARGIN), Math.max(MARGIN, vh - cardSize.height - MARGIN));

  return (
    <div className="fixed inset-0 z-[100]" aria-modal="true" role="dialog">
      {/* Spotlight: dims everything except the highlighted rect */}
      {rect ? (
        <div
          className="pointer-events-none absolute rounded-lg ring-2 ring-primary transition-all duration-200"
          style={{
            top: rect.top - PAD,
            left: rect.left - PAD,
            width: rect.width + PAD * 2,
            height: rect.height + PAD * 2,
            boxShadow: "0 0 0 9999px rgba(0,0,0,0.62)"
          }}
        />
      ) : (
        <div className="absolute inset-0" style={{ background: "rgba(0,0,0,0.62)" }} />
      )}

      {/* Step card */}
      <div
        ref={cardRef}
        className="absolute w-80 rounded-xl border border-border bg-popover p-4 text-popover-foreground shadow-2xl transition-all duration-200"
        style={{ top: cardTop, left: cardLeft }}
      >
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <span className="flex size-6 items-center justify-center rounded-md bg-primary text-xs font-semibold text-primary-foreground">
              {index + 1}
            </span>
            <span className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
              Step {index + 1} of {activeSteps.length}
            </span>
          </div>
          <Button
            size="icon"
            variant="ghost"
            className="size-7 text-muted-foreground hover:text-foreground"
            onClick={close}
            aria-label="Close tour"
          >
            <X />
          </Button>
        </div>

        <h3 className="mt-3 text-sm font-semibold">{step.title}</h3>
        <p className="mt-1.5 text-[13px] leading-relaxed text-muted-foreground">{step.body}</p>

        <div className="mt-4 flex items-center justify-between gap-2">
          <Button variant="ghost" size="sm" className="text-muted-foreground" onClick={close}>
            Skip
          </Button>
          <div className="flex items-center gap-2">
            {!isFirst ? (
              <Button
                variant="outline"
                size="sm"
                onClick={() => setIndex((current) => Math.max(current - 1, 0))}
              >
                <ArrowLeft />
                Back
              </Button>
            ) : null}
            {isLast ? (
              <Button size="sm" onClick={close}>
                Done
              </Button>
            ) : (
              <Button size="sm" onClick={() => setIndex((current) => current + 1)}>
                Next
                <ArrowRight />
              </Button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
