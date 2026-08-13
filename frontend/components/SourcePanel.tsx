"use client";

import { useEffect, useState } from "react";
import { Citation } from "./types";
import { apiUrl } from "../lib/api";

interface ResolvedCitation extends Citation {
  recipe_title: string;
  cuisine: string;
  text: string;
}

export function SourcePanel({ citation, onClose }: { citation: Citation | null; onClose: () => void }) {
  const [resolved, setResolved] = useState<ResolvedCitation | null>(null);

  useEffect(() => {
    if (!citation) {
      setResolved(null);
      return;
    }
    fetch(apiUrl(`/citations?chunkId=${encodeURIComponent(citation.chunk_id)}`))
      .then((r) => r.json())
      .then((data) => setResolved(data))
      .catch(() => setResolved(null));
  }, [citation]);

  if (!citation) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4" onClick={onClose}>
      <div
        className="w-full max-w-lg rounded-xl bg-white p-5 shadow-xl dark:bg-zinc-900"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-3 flex items-center justify-between">
          <h3 className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">Source detail</h3>
          <button onClick={onClose} className="text-zinc-400 hover:text-zinc-700 dark:hover:text-zinc-200">
            close
          </button>
        </div>
        {!resolved ? (
          <p className="text-sm text-zinc-500">Loading...</p>
        ) : (
          <dl className="space-y-2 text-sm">
            <Row label="Recipe" value={resolved.recipe_title} />
            <Row label="Source file" value={resolved.source_file} />
            <Row label="Section" value={resolved.section} />
            <Row label="Chunk ID" value={resolved.chunk_id} mono />
            <div>
              <dt className="font-medium text-zinc-500 dark:text-zinc-400">Retrieved text</dt>
              <dd className="mt-1 whitespace-pre-wrap rounded bg-zinc-50 p-2 text-zinc-800 dark:bg-zinc-800 dark:text-zinc-200">
                {resolved.text}
              </dd>
            </div>
          </dl>
        )}
      </div>
    </div>
  );
}

function Row({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="flex justify-between gap-2">
      <dt className="font-medium text-zinc-500 dark:text-zinc-400">{label}</dt>
      <dd className={`text-right text-zinc-800 dark:text-zinc-200 ${mono ? "font-mono text-xs" : ""}`}>{value}</dd>
    </div>
  );
}
