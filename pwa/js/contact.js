/* Contact detail page — view enrichment data + generate drafts */

const SIGNAL_TONE_TOOLTIPS = {
  WARM_LEAD: 'Direct and specific — references your current goals',
  NURTURE: 'Warm and relationship-first — no ask, just reconnecting',
  VALUE_DROP: 'Value-led — grounded in their industry and work',
  SYNERGY: 'Collaborative — frames mutual benefit, references your goals',
  RECONNECT: 'Nostalgic — re-entry framing, references your shared history',
  FUTURE_PIVOT: 'Light touch — low-pressure, no ask',
};

function buildProfessionalContextSection(conn) {
  const enrichment = conn.raw_enrichment?.data || conn.raw_enrichment || {};
  const role = escapeHtml(conn.current_role || '');
  const company = escapeHtml(conn.current_company || '');
  const industry = escapeHtml(enrichment.company_industry || enrichment.companyIndustry || '');
  const headline = escapeHtml(enrichment.headline || '');
  const experiences = enrichment.experiences || enrichment.experience || [];
  const prevRoles = experiences.slice(1, 3).map(e =>
    escapeHtml(`${e.title || ''} at ${e.company || e.companyName || ''}`.trim())
  );

  let html = '<div class="detail-section"><h3>Professional Context</h3>';
  if (role) html += `<div class="info-row"><span class="info-label">Role</span><span class="info-value">${role}</span></div>`;
  if (company) html += `<div class="info-row"><span class="info-label">Company</span><span class="info-value">${company}</span></div>`;
  if (industry) html += `<div class="info-row"><span class="info-label">Industry</span><span class="info-value">${industry}</span></div>`;
  if (headline) html += `<div class="info-row"><span class="info-label">Headline</span><span class="info-value">${headline}</span></div>`;
  if (prevRoles.length > 0) {
    html += `<div class="info-row"><span class="info-label">Career Path</span><span class="info-value">${prevRoles.join(', ')}</span></div>`;
  }
  html += '</div>';
  return html;
}

function buildConnectionStrengthSection(conn) {
  const messageCount = conn.message_count || 0;
  const lastDate = conn.last_message_date
    ? new Date(conn.last_message_date).toLocaleDateString()
    : 'Never';
  const status = escapeHtml(conn.conversation_status || 'unknown');
  const engagementScore = conn.engagement_score != null ? Math.round(conn.engagement_score) : null;
  const endorsementCount = conn.endorsement_count || 0;
  const hasRecommendation = conn.has_recommendation || false;
  const summary = conn.conversation_summary
    ? escapeHtml(conn.conversation_summary.slice(0, 120))
    : null;

  let html = '<div class="detail-section"><h3>Connection Strength</h3>';
  html += `<div class="info-row"><span class="info-label">Messages</span><span class="info-value">${messageCount}</span></div>`;
  html += `<div class="info-row"><span class="info-label">Last Contact</span><span class="info-value">${lastDate}</span></div>`;
  html += `<div class="info-row"><span class="info-label">Conversation</span><span class="info-value">${status}</span></div>`;
  if (engagementScore != null) {
    html += `<div class="info-row"><span class="info-label">Engagement</span><span class="info-value">${engagementScore}</span></div>`;
  }
  if (endorsementCount > 0) {
    html += `<div class="info-row"><span class="info-label">Endorsements</span><span class="info-value">${endorsementCount}</span></div>`;
  }
  if (hasRecommendation) {
    html += `<div class="info-row"><span class="info-label">Recommendation</span><span class="info-value">Yes</span></div>`;
  }
  if (summary) {
    html += `<div class="info-row"><span class="info-label">Summary</span><span class="info-value">${summary}</span></div>`;
  }
  html += '</div>';
  return html;
}

function buildEnrichmentSection(conn) {
  const enrichment = conn.raw_enrichment?.data || conn.raw_enrichment || {};
  const location = escapeHtml(conn.location || enrichment.location || '');
  const headline = escapeHtml(enrichment.headline || '');
  const emailStatus = conn.email ? 'Available' : 'Missing';
  const linkedinUrl = conn.linkedin_url || '';
  const completeness = conn.data_completeness_score;
  const missingFields = conn.missing_data_fields;
  const enrichedAt = conn.enriched_at
    ? new Date(conn.enriched_at).toLocaleDateString()
    : null;

  let chipHtml = '';
  if (completeness != null) {
    const pct = Math.round(completeness);
    let color;
    if (pct >= 80) color = 'var(--success)';
    else if (pct >= 50) color = 'var(--warning)';
    else color = 'var(--danger)';
    chipHtml = `<span class="enrichment-chip" style="background: ${color}20; color: ${color}">${pct}% Complete</span>`;
  }

  let html = '<div class="detail-section"><h3>Enrichment Status</h3>';
  if (chipHtml) html += `<div class="info-row"><span class="info-label">Completeness</span><span class="info-value">${chipHtml}</span></div>`;
  if (location) html += `<div class="info-row"><span class="info-label">Location</span><span class="info-value">${location}</span></div>`;
  if (headline) html += `<div class="info-row"><span class="info-label">Headline</span><span class="info-value">${headline}</span></div>`;
  html += `<div class="info-row"><span class="info-label">Email</span><span class="info-value">${emailStatus}</span></div>`;
  if (linkedinUrl) {
    html += `<div class="info-row"><span class="info-label">LinkedIn</span><span class="info-value"><a href="${escapeHtml(linkedinUrl)}" target="_blank">Connected</a></span></div>`;
  } else {
    html += `<div class="info-row"><span class="info-label">LinkedIn</span><span class="info-value">Not linked</span></div>`;
  }
  if (missingFields && missingFields.length > 0) {
    html += `<div class="info-row"><span class="info-label">Missing</span><span class="info-value">${escapeHtml(missingFields.join(', '))}</span></div>`;
  }
  if (enrichedAt) {
    html += `<div class="info-row"><span class="info-label">Enriched</span><span class="info-value">${enrichedAt}</span></div>`;
  }
  html += '</div>';
  return html;
}

async function buildSignalHistorySection(connectionId) {
  if (!db) return '';
  try {
    const { data: signals, error } = await db
      .from('contact_signals')
      .select('*')
      .eq('connection_id', connectionId)
      .order('assigned_at', { ascending: false })
      .limit(20);

    if (error || !signals || signals.length === 0) return '';

    let itemsHtml = '';
    for (const sig of signals) {
      const info = (typeof SIGNAL_ACTIONS !== 'undefined' && SIGNAL_ACTIONS[sig.signal])
        ? SIGNAL_ACTIONS[sig.signal]
        : { label: sig.signal, color: '#666', bg: '#f3f4f6' };
      const dateStr = sig.assigned_at
        ? new Date(sig.assigned_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
        : '';
      const contextStr = sig.signal_context ? ` — ${escapeHtml(sig.signal_context)}` : '';
      const byStr = sig.assigned_by === 'user' ? '' : ` (${escapeHtml(sig.assigned_by)})`;
      itemsHtml += `
        <div style="display:flex;align-items:center;gap:8px;padding:6px 0;border-bottom:1px solid #f0f0f0;">
          <span class="signal-badge" style="background:${info.bg};color:${info.color};">${escapeHtml(info.label)}</span>
          <span style="font-size:12px;color:var(--text-muted);">${dateStr}${byStr}${contextStr}</span>
        </div>`;
    }

    return `<div class="detail-section"><h3>Signal History</h3>${itemsHtml}</div>`;
  } catch (err) {
    console.error('Signal history fetch error:', err);
    return '';
  }
}

async function buildNotesSection(connectionId, conn) {
  let notesHtml = '';
  if (db) {
    try {
      const { data: notes } = await db
        .from('contact_notes')
        .select('*')
        .eq('connection_id', connectionId)
        .order('created_at', { ascending: false })
        .limit(20);

      if (notes && notes.length > 0) {
        for (const note of notes) {
          const dateStr = note.created_at
            ? new Date(note.created_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
            : '';
          notesHtml += `
            <div style="padding:8px 0;border-bottom:1px solid #f0f0f0;">
              <div style="font-size:14px;color:var(--text);">${escapeHtml(note.note_text || '')}</div>
              <div style="font-size:11px;color:var(--text-muted);margin-top:2px;">${dateStr}</div>
            </div>`;
        }
      }
    } catch (err) {
      console.error('Notes fetch error:', err);
    }
  }

  const quickNote = conn.notes || '';

  return `
    <div class="detail-section">
      <h3>Notes</h3>
      <div style="margin-bottom:12px;">
        <textarea id="quick-note-input"
          placeholder="Add a quick note about this contact..."
          style="width:100%;min-height:60px;border:1px solid var(--border);border-radius:var(--radius-sm);padding:10px;font:inherit;font-size:14px;resize:vertical;"
        >${escapeHtml(quickNote)}</textarea>
        <div style="display:flex;gap:8px;margin-top:6px;">
          <button class="btn btn-outline" style="flex:0;padding:6px 14px;font-size:13px;"
            onclick="saveQuickNote('${connectionId}')">Save Note</button>
          <button class="btn btn-outline" style="flex:0;padding:6px 14px;font-size:13px;"
            onclick="addTimestampedNote('${connectionId}')">Add to History</button>
        </div>
      </div>
      ${notesHtml ? '<div style="margin-top:8px;">' + notesHtml + '</div>' : ''}
    </div>`;
}

async function saveQuickNote(connectionId) {
  const textarea = document.getElementById('quick-note-input');
  if (!textarea || !db) return;
  const noteText = textarea.value.trim();
  try {
    const { error } = await db
      .from('connections')
      .update({ notes: noteText })
      .eq('id', connectionId);
    if (error) throw error;
    textarea.style.borderColor = 'var(--success)';
    setTimeout(() => textarea.style.borderColor = '', 1500);
  } catch (err) {
    console.error('Save note error:', err);
    textarea.style.borderColor = 'var(--danger)';
    setTimeout(() => textarea.style.borderColor = '', 1500);
  }
}

async function addTimestampedNote(connectionId) {
  const textarea = document.getElementById('quick-note-input');
  if (!textarea || !db) return;
  const noteText = textarea.value.trim();
  if (!noteText) return;
  try {
    const { error } = await db
      .from('contact_notes')
      .insert({
        connection_id: connectionId,
        note_text: noteText,
      });
    if (error) throw error;
    textarea.value = '';
    const content = document.getElementById('app-content');
    if (content) renderContact(content, connectionId);
  } catch (err) {
    console.error('Add note error:', err);
  }
}

async function renderContact(container, connectionId) {
  if (!db || !connectionId) {
    container.innerHTML = '<div class="empty-state"><p>Contact not found.</p></div>';
    return;
  }

  const params = getQueryParams();
  const queueItemId = params.queue_item;

  // Fetch connection
  const { data: conn, error } = await db
    .from('connections')
    .select('*')
    .eq('id', connectionId)
    .single();

  if (error || !conn) {
    container.innerHTML = '<div class="empty-state"><p>Contact not found.</p></div>';
    return;
  }

  const name = escapeHtml(conn.name || 'Unknown');
  const role = escapeHtml(conn.current_role || '');
  const company = escapeHtml(conn.current_company || '');
  const roleLine = company ? `${role} @ ${company}` : role;
  const score = Math.round(conn.reconnect_score || conn.pre_score || 0);
  const email = conn.email || '';
  const linkedinUrl = conn.linkedin_url || '';

  // Parse score reasoning
  let dimensions = {};
  let hooks = [];
  let keyFactors = [];
  if (conn.score_reasoning) {
    try {
      const reasoning = JSON.parse(conn.score_reasoning);
      dimensions = reasoning.dimension_scores || {};
      hooks = reasoning.conversation_hooks || [];
      keyFactors = reasoning.key_factors || [];
    } catch (e) {}
  }

  // Dimension bars
  const dimConfig = {
    goal_alignment: { label: 'Goal Alignment', max: 25 },
    industry_overlap: { label: 'Industry Fit', max: 20 },
    mutual_value: { label: 'Mutual Value', max: 20 },
    conversation_hooks: { label: 'Conv. Hooks', max: 20 },
    network_reach: { label: 'Network Reach', max: 15 },
  };

  let dimensionHtml = '';
  for (const [key, config] of Object.entries(dimConfig)) {
    const val = dimensions[key] || 0;
    const pct = Math.round((val / config.max) * 100);
    dimensionHtml += `
      <div class="dimension-bar">
        <div class="label">${config.label}</div>
        <div class="bar"><div class="bar-fill" style="width: ${pct}%"></div></div>
        <div class="value">${val}/${config.max}</div>
      </div>`;
  }

  // Key factors — with fallback from enrichment when scoring data is sparse
  let factorsHtml = '';
  if (keyFactors.length > 0) {
    factorsHtml = '<div class="detail-section"><h3>Key Factors</h3><ul style="padding-left: 18px; font-size: 14px; color: var(--text-secondary);">';
    for (const f of keyFactors) {
      factorsHtml += `<li style="margin-bottom: 4px;">${escapeHtml(String(f))}</li>`;
    }
    factorsHtml += '</ul></div>';
  } else {
    // Fallback: synthesize from enrichment data
    const enrichment = conn.raw_enrichment?.data || conn.raw_enrichment || {};
    const fallbacks = [];
    if (enrichment.headline) {
      fallbacks.push(enrichment.headline);
    }
    const industry = enrichment.company_industry || enrichment.companyIndustry;
    if (industry) {
      fallbacks.push(`Works in ${industry}`);
    }
    const experiences = enrichment.experiences || enrichment.experience || [];
    if (experiences.length > 1) {
      const prev = experiences[1];
      const prevTitle = prev.title || '';
      const prevCompany = prev.company || prev.companyName || '';
      if (prevTitle || prevCompany) {
        fallbacks.push(`Previously: ${prevTitle}${prevCompany ? ' at ' + prevCompany : ''}`);
      }
    }
    if (conn.message_count > 0) {
      fallbacks.push(`${conn.message_count} messages exchanged`);
    }

    if (fallbacks.length > 0) {
      factorsHtml = '<div class="detail-section"><h3>Key Factors</h3><ul style="padding-left: 18px; font-size: 14px; color: var(--text-secondary);">';
      for (const f of fallbacks) {
        factorsHtml += `<li style="margin-bottom: 4px;">${escapeHtml(String(f))}</li>`;
      }
      factorsHtml += '</ul></div>';
    }
  }

  // Conversation starters — with fallback from enrichment when activity_log is empty
  let hooksHtml = '';
  if (hooks.length > 0) {
    hooksHtml = '<div class="detail-section"><h3>Conversation Starters</h3>';
    for (const h of hooks) {
      hooksHtml += `<div class="alert-card"><div class="alert-detail">${escapeHtml(String(h))}</div></div>`;
    }
    hooksHtml += '</div>';
  } else {
    // Fallback: construct starters from enrichment and connection data
    const enrichment = conn.raw_enrichment?.data || conn.raw_enrichment || {};
    const fallbackHooks = [];
    if (enrichment.headline) {
      fallbackHooks.push(`Ask about their work as: "${enrichment.headline}"`);
    }
    const experiences = enrichment.experiences || enrichment.experience || [];
    if (experiences.length > 0 && experiences[0]) {
      const current = experiences[0];
      const companyName = current.company || current.companyName;
      if (companyName) {
        fallbackHooks.push(`Discuss their role at ${companyName}`);
      }
    }
    if (conn.conversation_summary) {
      const summary = conn.conversation_summary.length > 80
        ? conn.conversation_summary.slice(0, 80) + '...'
        : conn.conversation_summary;
      fallbackHooks.push(`Last discussed: ${summary}`);
    }
    const industry = enrichment.company_industry || enrichment.companyIndustry;
    if (industry && !fallbackHooks.some(h => h.includes(industry))) {
      fallbackHooks.push(`Connect on ${industry} industry topics`);
    }

    if (fallbackHooks.length > 0) {
      hooksHtml = '<div class="detail-section"><h3>Conversation Starters</h3>';
      for (const h of fallbackHooks) {
        hooksHtml += `<div class="alert-card"><div class="alert-detail">${escapeHtml(String(h))}</div></div>`;
      }
      hooksHtml += '</div>';
    }
  }

  // Draft section — three-way signal gate
  let draftHtml = '';
  if (queueItemId) {
    const signal = conn.latest_signal;
    if (signal === 'ARCHIVE') {
      // ARCHIVE: hide draft section entirely — per CONTEXT.md decision
      draftHtml = '';
    } else if (!signal) {
      // No signal assigned: show nudge to assign signal first
      draftHtml = `
        <div class="detail-section" id="draft-section">
          <h3>Draft Message</h3>
          <div class="draft-no-signal">
            <p>Assign a signal for a tailored draft.</p>
          </div>
        </div>`;
    } else {
      // Valid signal: show generate button with signal-aware draft area
      draftHtml = `
        <div class="detail-section draft-area" id="draft-section">
          <h3>Draft Message</h3>
          <div style="text-align: center; margin: 16px 0;">
            <button class="btn btn-primary" onclick="generateDraft('${connectionId}', ${queueItemId}, '${escapeHtml(signal)}')" id="generate-btn">
              Generate Draft
            </button>
          </div>
          <div id="draft-content" class="hidden">
            <div id="draft-signal-badge-area"></div>
            <div class="draft-box"><textarea id="draft-text" placeholder="Draft will appear here..."></textarea></div>
            <div class="draft-actions">
              <button class="btn btn-outline" onclick="copyDraft()">Copy</button>
              ${linkedinUrl ? `<a href="${escapeHtml(linkedinUrl.replace(/\/$/, ''))}/overlay/new-message/" target="_blank" class="btn btn-primary">Open LinkedIn DM</a>` : ''}
              ${email ? `<a href="mailto:${escapeHtml(email)}" class="btn btn-outline">Send Email</a>` : ''}
            </div>
          </div>
        </div>`;
    }
  }

  // Async sections: signal history + notes
  const signalHistoryHtml = await buildSignalHistorySection(connectionId);
  const notesHtml = await buildNotesSection(connectionId, conn);

  // Contact links
  let linksHtml = '<div class="detail-section"><h3>Quick Actions</h3><div style="display: flex; gap: 8px; flex-wrap: wrap;">';
  if (linkedinUrl) {
    linksHtml += `<a href="${escapeHtml(linkedinUrl)}" target="_blank" class="btn btn-outline">View LinkedIn</a>`;
  }
  if (email) {
    linksHtml += `<a href="mailto:${escapeHtml(email)}" class="btn btn-outline">Email</a>`;
  }
  linksHtml += `
    <button class="btn btn-outline" style="color: var(--success); border-color: var(--success);" onclick="setContactPriority('${connectionId}', 'always')">Always Suggest</button>
    <button class="btn btn-outline" style="color: var(--danger); border-color: var(--danger);" onclick="setContactPriority('${connectionId}', 'never')">Never Suggest</button>
  </div></div>`;

  container.innerHTML = `
    <div class="contact-detail">
      <div style="display: flex; justify-content: space-between; align-items: flex-start;">
        <div>
          <div class="name">${name}</div>
          <div class="role">${roleLine}</div>
        </div>
        <div class="score-badge" style="font-size: 18px;">${score}</div>
      </div>

      <div class="detail-section">
        <h3>Score Breakdown</h3>
        ${dimensionHtml}
      </div>

      ${hooksHtml}
      ${factorsHtml}
      ${buildProfessionalContextSection(conn)}
      ${buildConnectionStrengthSection(conn)}
      ${buildEnrichmentSection(conn)}
      ${signalHistoryHtml}
      ${notesHtml}
      ${draftHtml}
      ${linksHtml}

      <div style="text-align: center; margin-top: 20px;">
        <a href="#/queue" class="btn btn-outline">&larr; Back to Queue</a>
      </div>
    </div>`;
}

async function generateDraft(connectionId, queueItemId, signal) {
  const btn = document.getElementById('generate-btn');
  const draftContent = document.getElementById('draft-content');
  const draftText = document.getElementById('draft-text');

  if (!btn || !draftContent || !draftText) return;

  btn.textContent = 'Generating...';
  btn.disabled = true;

  try {
    const response = await fetch(`${SUPABASE_URL}/functions/v1/draft`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${SUPABASE_ANON_KEY}`,
      },
      body: JSON.stringify({ queue_item_id: queueItemId }),
    });

    const result = await response.json();

    if (result.draft) {
      draftText.value = result.draft;
      draftContent.classList.remove('hidden');
      btn.textContent = 'Regenerate';
      btn.disabled = false;

      // Inject signal tone badge above textarea
      const badgeArea = document.getElementById('draft-signal-badge-area');
      if (badgeArea && signal && typeof SIGNAL_ACTIONS !== 'undefined' && SIGNAL_ACTIONS[signal]) {
        const info = SIGNAL_ACTIONS[signal];
        const tooltip = SIGNAL_TONE_TOOLTIPS[signal] || info.label;
        badgeArea.innerHTML = `
          <div class="draft-tone-badge" title="${escapeHtml(tooltip)}">
            <span class="signal-badge" style="background:${info.bg};color:${info.color};">
              ${escapeHtml(info.label)} tone
            </span>
          </div>`;
      }
    } else {
      btn.textContent = 'Failed — Try Again';
      btn.disabled = false;
    }
  } catch (err) {
    console.error('Draft generation error:', err);
    btn.textContent = 'Failed — Try Again';
    btn.disabled = false;
  }
}

function copyDraft() {
  const draftText = document.getElementById('draft-text');
  if (!draftText) return;

  navigator.clipboard.writeText(draftText.value).then(() => {
    const btn = event.target;
    const original = btn.textContent;
    btn.textContent = 'Copied!';
    setTimeout(() => btn.textContent = original, 2000);
  });
}

async function setContactPriority(connectionId, priority) {
  if (!db) return;

  try {
    // Use feedback Edge Function
    await fetch(`${SUPABASE_URL}/functions/v1/feedback`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${SUPABASE_ANON_KEY}`,
      },
      body: JSON.stringify({
        feedback_type: priority === 'never' ? 'never_suggest' : 'always_suggest',
        connection_id: connectionId,
      }),
    });

    alert(priority === 'never' ? 'This contact will never be suggested.' : 'This contact will always be prioritized.');
  } catch (err) {
    console.error('Priority update error:', err);
  }
}
