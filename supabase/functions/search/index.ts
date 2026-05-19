// Edge Function: Semantic people search
// Receives { query, limit? } POST body
// Embeds the query via OpenAI, runs pgvector similarity search, returns ranked results.

import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers":
    "authorization, x-client-info, apikey, content-type",
};

interface SearchRequest {
  query: string;
  limit?: number;
}

Deno.serve(async (req: Request) => {
  if (req.method === "OPTIONS") {
    return new Response("ok", { headers: corsHeaders });
  }

  if (req.method !== "POST") {
    return jsonResponse({ error: "POST required" }, 405);
  }

  const openaiKey = Deno.env.get("OPENAI_API_KEY");
  if (!openaiKey) {
    return jsonResponse({ error: "OPENAI_API_KEY not configured" }, 500);
  }

  let body: SearchRequest;
  try {
    body = await req.json();
  } catch {
    return jsonResponse({ error: "Invalid JSON body" }, 400);
  }

  const query = (body.query || "").trim();
  if (!query) {
    return jsonResponse({ error: "query is required" }, 400);
  }

  const matchLimit = Math.min(body.limit || 20, 50);

  try {
    // 1. Embed the search query
    const embedding = await embedQuery(query, openaiKey);

    // 2. Run pgvector similarity search via Supabase RPC
    const supabaseUrl = Deno.env.get("SUPABASE_URL")!;
    const supabaseKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
    const supabase = createClient(supabaseUrl, supabaseKey);

    const { data, error } = await supabase.rpc("semantic_search", {
      query_embedding: JSON.stringify(embedding),
      match_limit: matchLimit,
      similarity_threshold: 0.25,
    });

    if (error) {
      console.error("Semantic search error:", error);
      return jsonResponse({ error: "Search failed: " + error.message }, 500);
    }

    return jsonResponse({
      results: data || [],
      query: query,
      count: (data || []).length,
    });
  } catch (err) {
    console.error("Search error:", err);
    return jsonResponse({ error: "Search failed" }, 500);
  }
});

async function embedQuery(
  text: string,
  apiKey: string
): Promise<number[]> {
  const response = await fetch("https://api.openai.com/v1/embeddings", {
    method: "POST",
    headers: {
      Authorization: `Bearer ${apiKey}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      model: "text-embedding-3-small",
      input: text,
    }),
  });

  if (!response.ok) {
    const errText = await response.text();
    throw new Error(`OpenAI embedding failed: ${errText}`);
  }

  const result = await response.json();
  return result.data[0].embedding;
}

function jsonResponse(data: unknown, status = 200): Response {
  return new Response(JSON.stringify(data), {
    status,
    headers: { ...corsHeaders, "Content-Type": "application/json" },
  });
}
