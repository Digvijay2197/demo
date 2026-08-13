"use client";

import { useEffect, useState } from "react";
import { RecipeCard } from "./RecipeCard";
import { RecipeDocument } from "./types";
import { apiUrl } from "../lib/api";

export function RecipePanel() {
  const [recipes, setRecipes] = useState<RecipeDocument[]>([]);

  useEffect(() => {
    fetch(apiUrl("/documents"))
      .then((r) => r.json())
      .then((data) => setRecipes(data.documents || []))
      .catch(() => setRecipes([]));
  }, []);

  return (
    <div className="flex h-full flex-col gap-3 overflow-y-auto p-4">
      <h2 className="text-sm font-semibold text-zinc-700 dark:text-zinc-300">
        Recipes &middot; {recipes.length} New Recipes
      </h2>
      {recipes.map((r) => (
        <RecipeCard key={r.recipe_id} recipe={r} />
      ))}
    </div>
  );
}
