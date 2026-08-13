"use client";

import { useEffect, useState } from "react";
import { apiUrl } from "../../lib/api";

interface PerQuestion {
  id: string;
  question: string;
  expected_recipe_id: string;
  expected_section: string;
  ingredient_dependent: boolean;
  baseline_hit: boolean;
  structure_aware_hit: boolean;
}

interface Summary {
  total_questions: number;
  baseline_hit_at_5: number;
  structure_aware_hit_at_5: number;
  per_question: PerQuestion[];
}

interface MetadataFilterResult {
  query: string;
  dietary_tag_filter: string;
  top1_changed: boolean;
  unfiltered: { recipe_id: string; score: number }[];
  filtered: { recipe_id: string; score: number }[];
}

export default function EvaluationPage() {
  const [summary, setSummary] = useState<Summary | null>(null);
  const [metadataFilter, setMetadataFilter] = useState<MetadataFilterResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch(apiUrl("/evaluation"))
      .then((r) => r.json())
      .then((data) => {
        if (data.error || data.detail) {
          setError(data.error || data.detail);
          return;
        }
        setSummary(data.summary);
        setMetadataFilter(data.metadataFilter);
      })
      .catch(() => setError("Failed to load evaluation results"));
  }, []);

  if (error) return <div className="p-8 text-sm text-red-600">{error}</div>;
  if (!summary) return <div className="p-8 text-sm text-zinc-400">Loading evaluation results...</div>;

  return (
    <div className="mx-auto max-w-4xl space-y-8 p-8">
      <h1 className="text-xl font-semibold text-zinc-900 dark:text-zinc-100">Retrieval Evaluation</h1>

      <section className="grid grid-cols-2 gap-4">
        <ScoreCard label="Baseline" value={`${summary.baseline_hit_at_5} / ${summary.total_questions}`} />
        <ScoreCard
          label="Structure-Aware"
          value={`${summary.structure_aware_hit_at_5} / ${summary.total_questions}`}
        />
      </section>

      <section>
        <h2 className="mb-2 text-sm font-semibold text-zinc-700 dark:text-zinc-300">Per-Question Results</h2>
        <table className="w-full border-collapse text-sm">
          <thead>
            <tr className="border-b border-zinc-200 text-left dark:border-zinc-800">
              <th className="py-2">Question</th>
              <th className="py-2">Baseline</th>
              <th className="py-2">Structure-Aware</th>
            </tr>
          </thead>
          <tbody>
            {summary.per_question.map((q) => (
              <tr key={q.id} className="border-b border-zinc-100 dark:border-zinc-900">
                <td className="py-2 pr-4">
                  {q.id}. {q.question}
                </td>
                <td className="py-2">{q.baseline_hit ? "✓" : "✗"}</td>
                <td className="py-2">{q.structure_aware_hit ? "✓" : "✗"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      {metadataFilter && (
        <section>
          <h2 className="mb-2 text-sm font-semibold text-zinc-700 dark:text-zinc-300">
            Metadata Filter Demo (dietary_tags = {metadataFilter.dietary_tag_filter})
          </h2>
          <p className="mb-2 text-xs text-zinc-500">Query: {metadataFilter.query}</p>
          <p className="mb-3 text-xs font-medium text-emerald-600">
            Top-1 changed: {metadataFilter.top1_changed ? "YES" : "NO"}
          </p>
          <div className="grid grid-cols-2 gap-4 text-xs">
            <div>
              <h3 className="mb-1 font-medium">Unfiltered</h3>
              <ol className="list-decimal pl-4">
                {metadataFilter.unfiltered.map((r, i) => (
                  <li key={i}>
                    {r.recipe_id} — {r.score.toFixed(3)}
                  </li>
                ))}
              </ol>
            </div>
            <div>
              <h3 className="mb-1 font-medium">Filtered</h3>
              <ol className="list-decimal pl-4">
                {metadataFilter.filtered.map((r, i) => (
                  <li key={i}>
                    {r.recipe_id} — {r.score.toFixed(3)}
                  </li>
                ))}
              </ol>
            </div>
          </div>
        </section>
      )}
    </div>
  );
}

function ScoreCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-zinc-200 p-4 text-center dark:border-zinc-800">
      <p className="text-xs text-zinc-500">{label}</p>
      <p className="text-2xl font-semibold text-zinc-900 dark:text-zinc-100">{value}</p>
    </div>
  );
}
