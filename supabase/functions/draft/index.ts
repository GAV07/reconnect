// Edge Function: On-demand draft generation
// Receives { queue_item_id, channel } POST body
// Fetches enrichment data, calls OpenAI, saves draft, returns it.

import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
};

interface DraftRequest {
  queue_item_id: number;
  channel?: string;
}

// Signal-aware tone configuration for buildDraftPrompt()
// Each signal produces a distinctly toned draft. ARCHIVE is blocked at the guard level.
const SIGNAL_TONE_CONFIG: Record<string, {
  toneDirective: string;
  includeUserGoals: boolean;
  emphasizeContactData: boolean;
}> = {
  WARM_LEAD: {
    toneDirective: "Write a direct, confident message with a specific ask. The sender has goals that align with this contact — reference one goal naturally. Be concrete, not generic.",
    includeUserGoals: true,
    emphasizeContactData: false,
  },
  NURTURE: {
    toneDirective: "Write a warm, low-pressure message focused on maintaining the relationship. No ask. No agenda. Just genuine reconnection. Keep it to 2-3 sentences.",
    includeUserGoals: false,
    emphasizeContactData: false,
  },
  VALUE_DROP: {
    toneDirective: "Lead the message with something specifically relevant to the recipient's industry or skills. Frame it as sharing something helpful, not selling. Ground it in their actual work.",
    includeUserGoals: false,
    emphasizeContactData: true,
  },
  SYNERGY: {
    toneDirective: "Write a collaborative message framing mutual benefit. The sender has goals that may intersect with this contact's work — weave one in naturally. Make the collaboration angle specific.",
    includeUserGoals: true,
    emphasizeContactData: false,
  },
  RECONNECT: {
    toneDirective: "Write a nostalgic but forward-looking message. If there's shared history (previous conversations, mutual connections), reference it. Frame as a warm re-entry, not a cold outreach.",
    includeUserGoals: false,
    emphasizeContactData: false,
  },
  FUTURE_PIVOT: {
    toneDirective: "Write a very brief, light-touch message. No pressure, no ask. Just planting a seed and keeping the door open. Keep it to 2-3 sentences maximum.",
    includeUserGoals: false,
    emphasizeContactData: false,
  },
  ARCHIVE: {
    toneDirective: "", // Should never reach here — rejected at ARCHIVE guard before reaching buildDraftPrompt()
    includeUserGoals: false,
    emphasizeContactData: false,
  },
};

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

  let body: DraftRequest;
  try {
    body = await req.json();
  } catch {
    return jsonResponse({ error: "Invalid JSON body" }, 400);
  }

  if (!body.queue_item_id) {
    return jsonResponse({ error: "queue_item_id is required" }, 400);
  }

  const supabaseUrl = Deno.env.get("SUPABASE_URL")!;
  const supabaseKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
  const supabase = createClient(supabaseUrl, supabaseKey);

  // Fetch queue item
  const { data: queueItem, error: qError } = await supabase
    .from("outreach_queue")
    .select("*")
    .eq("id", body.queue_item_id)
    .single();

  if (qError || !queueItem) {
    return jsonResponse({ error: "Queue item not found" }, 404);
  }

  // ARCHIVE guard: belt-and-suspenders server-side rejection before reaching OpenAI
  if (queueItem.signal === "ARCHIVE") {
    return jsonResponse({ error: "Draft not available for archived contacts" }, 400);
  }

  // Fetch connection with enrichment data
  const { data: connection, error: cError } = await supabase
    .from("connections")
    .select("*")
    .eq("id", queueItem.connection_id)
    .single();

  if (cError || !connection) {
    return jsonResponse({ error: "Connection not found" }, 404);
  }

  // Fetch user profile
  const { data: profile } = await supabase
    .from("user_profile")
    .select("*")
    .eq("id", 1)
    .single();

  const channel = body.channel || queueItem.channel || "linkedin";

  // Build the signal-aware prompt
  const prompt = buildDraftPrompt(
    connection,
    profile,
    channel,
    queueItem.signal || null,
    queueItem.signal_context || null,
  );

  try {
    // Call OpenAI
    const response = await fetch("https://api.openai.com/v1/chat/completions", {
      method: "POST",
      headers: {
        "Authorization": `Bearer ${openaiKey}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        model: "gpt-4o-mini",
        messages: [{ role: "user", content: prompt }],
        max_tokens: 300,
        temperature: 0.7,
      }),
    });

    if (!response.ok) {
      const errText = await response.text();
      console.error("OpenAI error:", errText);
      return jsonResponse({ error: "Draft generation failed" }, 502);
    }

    const result = await response.json();
    const draft = result.choices?.[0]?.message?.content?.trim() || "";

    if (!draft) {
      return jsonResponse({ error: "Empty draft generated" }, 502);
    }

    // Save draft to queue item
    await supabase
      .from("outreach_queue")
      .update({ draft_message: draft })
      .eq("id", body.queue_item_id);

    return jsonResponse({ draft });

  } catch (err) {
    console.error("Draft generation error:", err);
    return jsonResponse({ error: "Draft generation failed" }, 500);
  }
});


function buildDraftPrompt(
  connection: Record<string, unknown>,
  profile: Record<string, unknown> | null,
  channel: string,
  signal: string | null,
  signalContext: string | null,
): string {
  // Unwrap enrichment data (handles RapidAPI nested "data" key)
  let enrichment = (connection.raw_enrichment || {}) as Record<string, unknown>;
  if (enrichment.data && typeof enrichment.data === "object") {
    enrichment = enrichment.data as Record<string, unknown>;
  }

  // Extract career info
  const headline = enrichment.headline || "";
  const about = (enrichment.about || enrichment.summary || "") as string;
  const companyIndustry = enrichment.company_industry || enrichment.companyIndustry || "";

  // Extract skills
  let skills: string[] = [];
  const skillsRaw = enrichment.skills;
  if (Array.isArray(skillsRaw)) {
    skills = skillsRaw.slice(0, 5).map((s: unknown) => {
      if (typeof s === "object" && s !== null) {
        return (s as Record<string, string>).title || (s as Record<string, string>).name || "";
      }
      return String(s);
    }).filter(Boolean);
  }

  // Recent activity
  const activityLog = (connection.activity_log || []) as Array<Record<string, string>>;
  let activityContext = "";
  if (activityLog.length > 0) {
    const firstPost = activityLog[0]?.content || "";
    if (firstPost) {
      activityContext = `\nRecent activity: ${firstPost.slice(0, 150)}`;
    }
  }

  // Conversation context
  let convoContext = "";
  if (connection.conversation_summary) {
    convoContext = `\nPrevious conversation: ${connection.conversation_summary}`;
  } else if (connection.message_count && (connection.message_count as number) > 0) {
    convoContext = `\nHave exchanged ${connection.message_count} messages before.`;
  }

  const senderName = profile?.name || "Me";
  const senderRole = profile?.current_role || "Professional";
  const senderCompany = profile?.company || "N/A";

  const contactName = connection.name || "Contact";
  const contactRole = connection.current_role || enrichment.job_title || enrichment.title || "Unknown";
  const contactCompany = connection.current_company || enrichment.company || "Unknown";

  const channelLength = channel === "linkedin"
    ? "Keep it brief (3-4 sentences max for LinkedIn DM)"
    : "Keep it reasonably brief (4-5 sentences max for email)";

  // Look up signal tone config
  const toneConfig = signal ? SIGNAL_TONE_CONFIG[signal] : null;

  // Determine tone directive — fall back to generic if no signal or unrecognized signal
  const toneDirective = toneConfig?.toneDirective ||
    "Be genuine, not salesy. Include a soft call to action.";

  // User goals section — only for WARM_LEAD and SYNERGY
  let userGoalsSection = "";
  if (toneConfig?.includeUserGoals) {
    const goalsText = [profile?.current_projects, profile?.goals]
      .filter(Boolean)
      .join("\n")
      .trim() || "Professional network expansion";
    userGoalsSection = `\nSender's current focus:\n${goalsText}\nWeave one of these naturally into the message — don't list them as a preamble.`;
  }

  // Enrichment emphasis section — only for VALUE_DROP
  let enrichmentEmphasis = "";
  if (toneConfig?.emphasizeContactData) {
    const aboutSnippet = about ? about.slice(0, 200) : "";
    enrichmentEmphasis = `\nLead with something specific to their work:
- Industry: ${companyIndustry || "N/A"}
- Skills: ${skills.join(", ") || "N/A"}
- About: ${aboutSnippet || "N/A"}
Frame it as sharing something relevant to their field, not a generic "I thought of you."`;
  }

  // Additional context note from signal_context if provided
  const contextNote = signalContext
    ? `\nAdditional context for this outreach: ${signalContext}`
    : "";

  return `Generate a short, personalized ${channel} message to ${contactName}.

Tone: ${toneDirective}

Sender: ${senderName}
- Role: ${senderRole}
- Company: ${senderCompany}${userGoalsSection}

Recipient: ${contactName}
- Role: ${contactRole}
- Company: ${contactCompany}
- Industry: ${companyIndustry}
- Headline: ${headline}
- Skills: ${skills.join(", ") || "N/A"}${activityContext}${convoContext}
${enrichmentEmphasis}${contextNote}

Guidelines:
- ${channelLength}
- ${toneDirective}
- Reference something specific if possible
- Return ONLY the message text, no subject line or explanations.`;
}


function jsonResponse(data: unknown, status = 200): Response {
  return new Response(JSON.stringify(data), {
    status,
    headers: { ...corsHeaders, "Content-Type": "application/json" },
  });
}
