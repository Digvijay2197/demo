export function RefusalMessage({ text }: { text: string }) {
  return (
    <div className="rounded-lg border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-900 dark:border-amber-700 dark:bg-amber-950 dark:text-amber-200">
      <span className="font-medium">Not found in recipes: </span>
      {text}
    </div>
  );
}
