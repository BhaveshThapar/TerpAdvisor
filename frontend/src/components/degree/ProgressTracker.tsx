import type { GroupResult } from "@/types";
import ProgressBar from "@/components/ui/ProgressBar";

interface ProgressTrackerProps {
  groups: GroupResult[];
}

const statusStyles: Record<string, { dot: string; text: string }> = {
  complete: { dot: "bg-green-500", text: "text-green-300" },
  in_progress: { dot: "bg-yellow-400", text: "text-yellow-300" },
  incomplete: { dot: "bg-gray-300", text: "text-[var(--text-muted)]" },
};

export default function ProgressTracker({ groups }: ProgressTrackerProps) {
  return (
    <div className="space-y-6">
      {groups.map((group) => (
        <div key={group.name}>
          <div className="mb-2 flex items-center justify-between">
            <h3 className="text-sm font-semibold text-[var(--text-primary)]">
              {group.name}
            </h3>
            <span className="text-xs text-[var(--text-muted)]">
              {group.completed_count}/{group.min_required ?? group.total_count} complete
            </span>
          </div>

          <ProgressBar value={group.progress_pct} />

          <ul className="mt-2 space-y-1">
            {group.requirements.map((req) => {
              const style =
                statusStyles[req.status] ?? statusStyles.incomplete;
              return (
                <li key={req.name} className="flex items-start gap-2 text-sm">
                  <span
                    className={`mt-1.5 h-2 w-2 flex-shrink-0 rounded-full ${style.dot}`}
                  />
                  <div>
                    <span className={`font-medium ${style.text}`}>
                      {req.name}
                    </span>
                    {req.credits_remaining > 0 && (
                      <span className="ml-1 text-xs text-white/40">
                        ({req.credits_remaining} cr remaining)
                      </span>
                    )}
                  </div>
                </li>
              );
            })}
          </ul>
        </div>
      ))}
    </div>
  );
}
