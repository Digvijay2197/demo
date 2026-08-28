"use client";

import { useState } from "react";
import { ChatMessage } from "./ChatMessage";
import { ChatInput } from "./ChatInput";
import { LoadingIndicator } from "./LoadingIndicator";
import { SourcePanel } from "./SourcePanel";
import { ChatMessageData, Citation } from "./types";
import { apiUrl } from "../lib/api";

export function ChatWindow() {
  const [messages, setMessages] = useState<ChatMessageData[]>([]);
  const [loading, setLoading] = useState(false);
  const [activeCitation, setActiveCitation] = useState<Citation | null>(null);

  async function handleSend(question: string) {
    setMessages((prev) => [...prev, { role: "user", content: question }]);
    setLoading(true);
    try {
      const res = await fetch(apiUrl("/chat"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question }),
      });
      const data = await res.json();
      if (!res.ok) {
        setMessages((prev) => [
          ...prev,
          { role: "assistant", content: data.error || data.detail || "Something went wrong.", refused: true },
        ]);
        return;
      }
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: data.answer, citations: data.citations, refused: data.refused },
      ]);
    } catch {
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: "Network error contacting the assistant.", refused: true },
      ]);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex h-full flex-col">
      <div className="flex-1 space-y-4 overflow-y-auto p-4">
        {messages.length === 0 && (
          <p className="text-sm text-zinc-400">
            Ask about ingredients, quantities, method steps, cooking times, or temperatures from the recipe
            PDFs you have indexed. Answers are grounded in those documents only.
          </p>
        )}
        {messages.map((m, i) => (
          <ChatMessage key={i} message={m} onCitationClick={setActiveCitation} />
        ))}
        {loading && <LoadingIndicator />}
      </div>
      <ChatInput onSend={handleSend} disabled={loading} />
      <SourcePanel citation={activeCitation} onClose={() => setActiveCitation(null)} />
    </div>
  );
}
