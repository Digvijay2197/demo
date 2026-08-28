import { ChatWindow } from "@/components/ChatWindow";
import { DocumentsPanel } from "@/components/DocumentsPanel";

export default function Home() {
  return (
    <div className="flex h-screen flex-col bg-zinc-50 dark:bg-black">
      <header className="border-b border-zinc-200 px-6 py-4 dark:border-zinc-800">
        <h1 className="text-lg font-semibold text-zinc-900 dark:text-zinc-100">
          🍴 Recipe RAG Assistant
        </h1>
        <p className="text-xs text-zinc-500 dark:text-zinc-400">
          Ask about your recipe PDFs &middot; grounded answers only, with page citations
        </p>
      </header>
      <div className="flex flex-1 overflow-hidden">
        <aside className="hidden w-72 shrink-0 border-r border-zinc-200 dark:border-zinc-800 md:block">
          <DocumentsPanel />
        </aside>
        <main className="flex-1 bg-white dark:bg-zinc-950">
          <ChatWindow />
        </main>
      </div>
    </div>
  );
}
