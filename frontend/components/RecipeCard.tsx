import { RecipeDocument } from "./types";

export function RecipeCard({ recipe }: { recipe: RecipeDocument }) {
  return (
    <div className="rounded-lg border border-zinc-200 p-3 text-sm dark:border-zinc-800">
      <div className="flex items-center justify-between">
        <span className="font-medium text-zinc-900 dark:text-zinc-100">{recipe.title}</span>
        <span className={recipe.indexed ? "text-emerald-600" : "text-zinc-400"}>
          {recipe.indexed ? "✓" : "○"}
        </span>
      </div>
      <p className="mt-1 text-xs text-zinc-500 dark:text-zinc-400">{recipe.cuisine}</p>
      <div className="mt-2 flex flex-wrap gap-1">
        {recipe.dietary_tags.map((tag) => (
          <span
            key={tag}
            className="rounded-full bg-emerald-50 px-2 py-0.5 text-[10px] text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300"
          >
            {tag}
          </span>
        ))}
      </div>
      <p className="mt-2 truncate text-[11px] text-zinc-400">{recipe.source_file}</p>
    </div>
  );
}
