"use client";

import { Check, GraduationCap, X } from "lucide-react";
import { useEffect } from "react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export type PickerTrack = {
  id: string;
  title: string;
  objective: string;
  summary: string;
  useCase: string;
};

export function TrackPicker({
  tracks,
  selectedId,
  open,
  onSelect,
  onClose
}: {
  tracks: PickerTrack[];
  selectedId: string;
  open: boolean;
  onSelect: (track: PickerTrack) => void;
  onClose: () => void;
}) {
  useEffect(() => {
    if (!open) {
      return;
    }
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        onClose();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) {
    return null;
  }

  return (
    <div
      className="fixed inset-0 z-[90] flex items-center justify-center overflow-y-auto p-4"
      style={{ background: "rgba(0,0,0,0.7)" }}
      role="dialog"
      aria-modal="true"
      onClick={onClose}
    >
      <div
        className="my-auto w-full max-w-2xl rounded-xl border border-border bg-popover p-6 text-popover-foreground shadow-2xl"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="flex items-start justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="flex size-9 items-center justify-center rounded-lg border border-border bg-muted text-muted-foreground">
              <GraduationCap className="size-4.5" />
            </div>
            <div>
              <h2 className="text-base font-semibold">Choose a learning track</h2>
              <p className="text-sm text-muted-foreground">
                Each track is a short, guided lesson for one RELAI feature.
              </p>
            </div>
          </div>
          <Button
            size="icon"
            variant="ghost"
            className="size-7 shrink-0 text-muted-foreground hover:text-foreground"
            onClick={onClose}
            aria-label="Close"
          >
            <X />
          </Button>
        </div>

        <div className="mt-5 grid gap-3 sm:grid-cols-2">
          {tracks.map((track) => {
            const isSelected = track.id === selectedId;
            return (
              <button
                key={track.id}
                type="button"
                onClick={() => onSelect(track)}
                className={cn(
                  "flex flex-col rounded-lg border p-4 text-left transition-colors",
                  isSelected
                    ? "border-primary/60 bg-primary/5 ring-1 ring-primary/40"
                    : "border-border bg-card hover:border-border hover:bg-accent/50"
                )}
              >
                <div className="flex items-center justify-between gap-2">
                  <h3 className="text-sm font-semibold">{track.title}</h3>
                  {isSelected ? (
                    <span className="flex items-center gap-1 rounded-full bg-primary/15 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-primary">
                      <Check className="size-3" />
                      Selected
                    </span>
                  ) : null}
                </div>
                <p className="mt-2 text-[13px] leading-relaxed text-muted-foreground">
                  {track.summary || track.objective}
                </p>
                {track.useCase ? (
                  <div className="mt-3 border-t border-border pt-3">
                    <p className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
                      When to use
                    </p>
                    <p className="mt-1 text-[13px] leading-relaxed text-foreground/90">{track.useCase}</p>
                  </div>
                ) : null}
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
}
