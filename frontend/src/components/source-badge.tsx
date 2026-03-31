import type { Source } from "@/lib/types";
import { sourceLabel, sourceColor } from "@/lib/utils";

interface SourceBadgeProps {
  source: Source;
  className?: string;
}

export default function SourceBadge({ source, className = "" }: SourceBadgeProps) {
  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium text-white ${sourceColor(source)} ${className}`}
    >
      {sourceLabel(source)}
    </span>
  );
}
