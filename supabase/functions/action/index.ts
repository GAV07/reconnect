// Edge Function: Email action handler
// GET: Returns a confirmation page with a POST form (prevents Gmail scanner token consumption).
// POST: Validates the token, executes the action, marks it used, and returns a success page.

import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
};

Deno.serve(async (req: Request) => {
  // Handle CORS preflight
  if (req.method === "OPTIONS") {
    return new Response("ok", { headers: corsHeaders });
  }

  const url = new URL(req.url);
  const token = url.searchParams.get("token");

  if (!token) {
    return htmlResponse("Missing token", "No action token was provided.", 400);
  }

  // Initialize Supabase client with service role key for full DB access
  const supabaseUrl = Deno.env.get("SUPABASE_URL")!;
  const supabaseKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
  const supabase = createClient(supabaseUrl, supabaseKey);

  // Look up the token (read-only — runs for both GET and POST)
  const { data: tokenRow, error: tokenError } = await supabase
    .from("action_tokens")
    .select("*")
    .eq("token", token)
    .single();

  if (tokenError || !tokenRow) {
    return htmlResponse("Invalid Token", "This action link is invalid or has already been used.", 404);
  }

  // Check if already used
  if (tokenRow.used) {
    return htmlResponse("Already Used", "This action was already completed.", 409);
  }

  // Check expiry
  if (new Date(tokenRow.expires_at) < new Date()) {
    return htmlResponse("Expired", "This action link has expired. Check your latest digest for fresh links.", 410);
  }

  // Fetch contact name (read-only — runs for both GET and POST)
  const action = tokenRow.action;
  const queueItemId = tokenRow.queue_item_id;
  const connectionId = tokenRow.connection_id;
  let contactName = "this contact";

  if (connectionId) {
    const { data: conn } = await supabase
      .from("connections")
      .select("name")
      .eq("id", connectionId)
      .single();
    if (conn?.name) {
      contactName = conn.name;
    }
  }

  // --- GET: Return confirmation page (no side effects) ---
  if (req.method === "GET") {
    return confirmationPageResponse(tokenRow, token, contactName);
  }

  // --- POST: Execute the action ---
  if (req.method === "POST") {
    let resultMessage = "";
    let viewContactLink: string | undefined;

    try {
      if (action === "approve" && queueItemId) {
        await supabase
          .from("outreach_queue")
          .update({
            status: "approved",
            reviewed_at: new Date().toISOString(),
          })
          .eq("id", queueItemId);
        resultMessage = `${contactName} queued for outreach!`;
        // Build deep link to contact page in PWA (using query params — hash fragments are stripped by Gmail)
        const pwaUrl = Deno.env.get("PWA_URL") || "";
        if (pwaUrl && connectionId) {
          viewContactLink = `${pwaUrl}/?view=contact&id=${connectionId}`;
        }

      } else if (action === "skip" && queueItemId) {
        await supabase
          .from("outreach_queue")
          .update({
            status: "skipped",
            skip_reason: "Skipped via email",
            reviewed_at: new Date().toISOString(),
          })
          .eq("id", queueItemId);
        resultMessage = `${contactName} skipped.`;

      } else if (action === "snooze" && queueItemId) {
        // Snooze = skip with a snooze reason (pipeline will re-queue after cooldown)
        await supabase
          .from("outreach_queue")
          .update({
            status: "skipped",
            skip_reason: "Snoozed via email (3 day cooldown)",
            reviewed_at: new Date().toISOString(),
          })
          .eq("id", queueItemId);
        resultMessage = `${contactName} snoozed for 3 days.`;

      } else if (action === "feedback") {
        // Insert feedback record
        const payload = tokenRow.payload || {};
        await supabase.from("user_feedback").insert({
          connection_id: connectionId,
          queue_item_id: queueItemId,
          feedback_type: payload.feedback_type || "digest_rating",
          rating: payload.rating || null,
          text: payload.text || null,
          metadata: payload,
        });
        const ratingStr = payload.rating ? ` (${payload.rating}/5)` : "";
        resultMessage = `Feedback recorded${ratingStr}. Thanks!`;

      } else {
        return htmlResponse("Unknown Action", `Action "${action}" is not recognized.`, 400);
      }

      // Mark token as used
      await supabase
        .from("action_tokens")
        .update({ used: true, used_at: new Date().toISOString() })
        .eq("token", token);

      return htmlResponse("Done!", resultMessage, 200, viewContactLink, contactName);

    } catch (err) {
      console.error("Action execution error:", err);
      return htmlResponse("Error", "Something went wrong. Please try again from your queue.", 500);
    }
  }

  // --- Any other method: 405 ---
  return new Response("Method Not Allowed", {
    status: 405,
    headers: { ...corsHeaders, "Allow": "GET, POST, OPTIONS" },
  });
});


function confirmationPageResponse(
  tokenRow: Record<string, unknown>,
  token: string,
  contactName: string,
): Response {
  const action = tokenRow.action as string;
  const pwaUrl = Deno.env.get("PWA_URL") || "";

  const buttonLabels: Record<string, string> = {
    approve: "Yes — Queue for Outreach",
    skip: "Skip this contact",
    snooze: "Snooze for 3 days",
    feedback: "Submit Feedback",
  };
  const buttonText = buttonLabels[action] || "Confirm";

  const html = `<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Reconnect — Confirm Action</title>
  <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body {
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      background: #f5f5f5;
      display: flex;
      justify-content: center;
      align-items: center;
      min-height: 100vh;
      padding: 20px;
    }
    .card {
      background: white;
      border-radius: 12px;
      padding: 32px;
      max-width: 420px;
      width: 100%;
      text-align: center;
      box-shadow: 0 2px 8px rgba(0,0,0,0.1);
    }
    .icon { font-size: 48px; margin-bottom: 16px; }
    h1 { font-size: 24px; color: #333; margin-bottom: 12px; }
    p { color: #666; font-size: 16px; line-height: 1.5; margin-bottom: 24px; }
    .btn-submit {
      display: block;
      width: 100%;
      background: #0a66c2;
      color: white;
      border: none;
      padding: 14px 24px;
      border-radius: 8px;
      font-size: 16px;
      font-weight: 600;
      cursor: pointer;
      min-height: 44px;
      margin-bottom: 16px;
    }
    .btn-submit:hover { background: #084e96; }
    .cancel-link {
      display: inline-block;
      color: #666;
      text-decoration: none;
      font-size: 14px;
      padding: 8px;
    }
    .cancel-link:hover { color: #333; text-decoration: underline; }
  </style>
</head>
<body>
  <div class="card">
    <div class="icon">&#10067;</div>
    <h1>Confirm Action</h1>
    <p>Confirm: ${action} ${contactName}?</p>
    <form method="POST" action="/functions/v1/action?token=${token}">
      <button type="submit" class="btn-submit">${buttonText}</button>
    </form>
    <a href="${pwaUrl}#/queue" class="cancel-link">Cancel</a>
  </div>
</body>
</html>`;

  return new Response(html, {
    status: 200,
    headers: { ...corsHeaders, "Content-Type": "text/html; charset=utf-8" },
  });
}


function htmlResponse(
  title: string,
  message: string,
  status: number,
  linkUrl?: string,
  linkLabel?: string,
): Response {
  const pwaUrl = Deno.env.get("PWA_URL") || `${Deno.env.get("SUPABASE_URL")}/storage/v1/object/public/pwa/index.html`;

  // For approve success, show "View Contact" link; otherwise show "Open Queue"
  const actionLink = linkUrl
    ? `<a href="${linkUrl}" class="btn">View ${linkLabel || "Contact"}</a>
    <br><br>
    <a href="${pwaUrl}#/queue" class="btn-secondary">Open Queue</a>`
    : `<a href="${pwaUrl}#/queue" class="btn">Open Queue</a>`;

  const html = `<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Reconnect - ${title}</title>
  <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body {
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      background: #f5f5f5;
      display: flex;
      justify-content: center;
      align-items: center;
      min-height: 100vh;
      padding: 20px;
    }
    .card {
      background: white;
      border-radius: 12px;
      padding: 32px;
      max-width: 420px;
      width: 100%;
      text-align: center;
      box-shadow: 0 2px 8px rgba(0,0,0,0.1);
    }
    .icon { font-size: 48px; margin-bottom: 16px; }
    h1 { font-size: 24px; color: #333; margin-bottom: 12px; }
    p { color: #666; font-size: 16px; line-height: 1.5; margin-bottom: 24px; }
    .btn {
      display: inline-block;
      background: #0a66c2;
      color: white;
      text-decoration: none;
      padding: 12px 24px;
      border-radius: 8px;
      font-size: 15px;
      font-weight: 600;
    }
    .btn:hover { background: #084e96; }
    .btn-secondary {
      display: inline-block;
      color: #0a66c2;
      text-decoration: none;
      padding: 8px 16px;
      font-size: 14px;
    }
    .btn-secondary:hover { text-decoration: underline; }
  </style>
</head>
<body>
  <div class="card">
    <div class="icon">${status === 200 ? "&#10003;" : "&#9888;"}</div>
    <h1>${title}</h1>
    <p>${message}</p>
    ${actionLink}
  </div>
</body>
</html>`;

  return new Response(html, {
    status,
    headers: { ...corsHeaders, "Content-Type": "text/html; charset=utf-8" },
  });
}
