import { Citation } from "./types";

export function SourceCitation({
  citation,
  onClick,
}: {
  citation: Citation;
  onClick: (citation: Citation) => void;
}) {
  return (
    <button
      onClick={() => onClick(citation)}
      className="rounded border border-zinc-200 bg-zinc-50 px-2 py-1 text-left text-xs text-zinc-700 hover:border-emerald-400 hover:bg-emerald-50 dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-300 dark:hover:border-emerald-600"
    >
      📄 {citation.source_file} &middot; p.{citation.page}
      {typeof citation.score === "number" && (
        <span className="ml-1 text-zinc-400">({citation.score.toFixed(2)})</span>
      )}
    </button>
  );
}
