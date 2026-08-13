"use client";

import { useState } from "react";

export function ChatInput({
  onSend,
  disabled,
}: {
  onSend: (question: string) => void;
  disabled?: boolean;
}) {
  const [value, setValue] = useState("");

  function submit() {
    const trimmed = value.trim();
    if (!trimmed || disabled) return;
    onSend(trimmed);
    setValue("");
  }

  return (
    <div className="flex items-center gap-2 border-t border-zinc-200 p-3 dark:border-zinc-800">
      <input
        className="flex-1 rounded-full border border-zinc-300 bg-white px-4 py-2 text-sm outline-none focus:border-emerald-500 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-100"
        placeholder="Ask about recipes..."
        value={value}
        maxLength={500}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter") submit();
        }}
        disabled={disabled}
      />
      <button
        onClick={submit}
        disabled={disabled || !value.trim()}
        className="rounded-full bg-emerald-600 px-5 py-2 text-sm font-medium text-white disabled:opacity-40"
      >
        Send
      </button>
    </div>
  );
}
