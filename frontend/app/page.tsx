import { ChatWindow } from "@/components/ChatWindow";
import { RecipePanel } from "@/components/RecipePanel";

export default function Home() {
  return (
    <div className="flex h-screen flex-col bg-zinc-50 dark:bg-black">
      <header className="border-b border-zinc-200 px-6 py-4 dark:border-zinc-800">
        <h1 className="text-lg font-semibold text-zinc-900 dark:text-zinc-100">
          🍴 Recipe RAG Assistant
        </h1>
        <p className="text-xs text-zinc-500 dark:text-zinc-400">
          Fermentation chapter &middot; grounded answers only, with citations
        </p>
      </header>
      <div className="flex flex-1 overflow-hidden">
        <aside className="hidden w-72 shrink-0 border-r border-zinc-200 dark:border-zinc-800 md:block">
          <RecipePanel />
        </aside>
        <main className="flex-1 bg-white dark:bg-zinc-950">
          <ChatWindow />
        </main>
      </div>
      <footer className="border-t border-zinc-200 px-6 py-2 text-center text-xs text-zinc-400 dark:border-zinc-800">
        <a href="/evaluation" className="hover:text-emerald-600">
          View retrieval evaluation dashboard →
        </a>
      </footer>
    </div>
  );
}
