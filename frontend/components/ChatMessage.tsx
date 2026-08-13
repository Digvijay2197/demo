import { ChatMessageData, Citation } from "./types";
import { SourceCitation } from "./SourceCitation";
import { RefusalMessage } from "./RefusalMessage";

export function ChatMessage({
  message,
  onCitationClick,
}: {
  message: ChatMessageData;
  onCitationClick: (citation: Citation) => void;
}) {
  const isUser = message.role === "user";

  return (
    <div className={`flex flex-col gap-1 ${isUser ? "items-end" : "items-start"}`}>
      <span className="text-xs font-medium text-zinc-400">{isUser ? "User" : "Assistant"}</span>
      {message.refused ? (
        <RefusalMessage text={message.content} />
      ) : (
        <div
          className={`max-w-xl rounded-lg px-4 py-2 text-sm ${
            isUser
              ? "bg-emerald-600 text-white"
              : "bg-zinc-100 text-zinc-900 dark:bg-zinc-800 dark:text-zinc-100"
          }`}
        >
          {message.content.replace(/\[chunk:[a-zA-Z0-9-]+\]/g, "").trim()}
        </div>
      )}
      {message.citations && message.citations.length > 0 && (
        <div className="mt-1 flex flex-col gap-1">
          <span className="text-xs font-medium text-zinc-400">Sources</span>
          <div className="flex flex-wrap gap-2">
            {message.citations.map((c) => (
              <SourceCitation key={c.chunk_id} citation={c} onClick={onCitationClick} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
