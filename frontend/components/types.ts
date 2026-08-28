export interface Citation {
  chunk_id: string;
  source_file: string;
  page: number;
  snippet: string;
  score?: number;
}

export interface ChatMessageData {
  role: "user" | "assistant";
  content: string;
  citations?: Citation[];
  refused?: boolean;
}

export interface PdfDocument {
  source_file: string;
  size_kb: number | null;
  on_disk: boolean;
  chunks_indexed: number;
  pages_indexed: number;
  indexed: boolean;
}
