/* Contact detail page — view enrichment data + generate drafts */

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

  // Key factors
  let factorsHtml = '';
  if (keyFactors.length > 0) {
    factorsHtml = '<div class="detail-section"><h3>Key Factors</h3><ul style="padding-left: 18px; font-size: 14px; color: var(--text-secondary);">';
    for (const f of keyFactors) {
      factorsHtml += `<li style="margin-bottom: 4px;">${escapeHtml(String(f))}</li>`;
    }
    factorsHtml += '</ul></div>';
  }

  // Hooks
  let hooksHtml = '';
  if (hooks.length > 0) {
    hooksHtml = '<div class="detail-section"><h3>Conversation Starters</h3>';
    for (const h of hooks) {
      hooksHtml += `<div class="alert-card"><div class="alert-detail">${escapeHtml(String(h))}</div></div>`;
    }
    hooksHtml += '</div>';
  }

  // Draft section
  let draftHtml = '';
  if (queueItemId) {
    draftHtml = `
      <div class="detail-section draft-area" id="draft-section">
        <h3>Draft Message</h3>
        <div style="text-align: center; margin: 16px 0;">
          <button class="btn btn-primary" onclick="generateDraft('${connectionId}', ${queueItemId})" id="generate-btn">
            Generate Draft
          </button>
        </div>
        <div id="draft-content" class="hidden">
          <div class="draft-box"><textarea id="draft-text" placeholder="Draft will appear here..."></textarea></div>
          <div class="draft-actions">
            <button class="btn btn-outline" onclick="copyDraft()">Copy</button>
            ${linkedinUrl ? `<a href="${escapeHtml(linkedinUrl.replace(/\/$/, ''))}/overlay/new-message/" target="_blank" class="btn btn-primary">Open LinkedIn DM</a>` : ''}
            ${email ? `<a href="mailto:${escapeHtml(email)}" class="btn btn-outline">Send Email</a>` : ''}
          </div>
        </div>
      </div>`;
  }

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
      ${draftHtml}
      ${linksHtml}

      <div style="text-align: center; margin-top: 20px;">
        <a href="#/queue" class="btn btn-outline">&larr; Back to Queue</a>
      </div>
    </div>`;
}

async function generateDraft(connectionId, queueItemId) {
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
