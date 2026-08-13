export interface Citation {
  chunk_id: string;
  recipe_id: string;
  source_file: string;
  section: string;
}

export interface ChatMessageData {
  role: "user" | "assistant";
  content: string;
  citations?: Citation[];
  refused?: boolean;
}

export interface RecipeDocument {
  recipe_id: string;
  title: string;
  cuisine: string;
  dietary_tags: string[];
  source_file: string;
  indexed: boolean;
}
