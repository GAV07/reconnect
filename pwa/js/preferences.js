/* Preferences page — manage scoring preferences and view feedback history */

async function renderPreferences(container) {
  if (!db) {
    container.innerHTML = '<div class="empty-state"><p>Supabase not configured.</p></div>';
    return;
  }

  // Fetch user preferences
  const { data: prefs } = await db
    .from('user_preferences')
    .select('*')
    .eq('is_active', true)
    .order('pref_type');

  // Fetch recent feedback
  const { data: feedback } = await db
    .from('user_feedback')
    .select('*')
    .order('created_at', { ascending: false })
    .limit(20);

  // Fetch never/always contacts
  const { data: priorityContacts } = await db
    .from('connections')
    .select('id, name, current_company, user_priority')
    .in('user_priority', ['always', 'never'])
    .order('name');

  // Fetch user profile for goals
  const { data: userProfile } = await db
    .from('user_profile')
    .select('id, current_projects, updated_at')
    .eq('id', 1)
    .single();

  // Fetch weight history (last 30 entries)
  const { data: weightHistory } = await db
    .from('user_preferences')
    .select('pref_key, pref_value, created_at')
    .eq('pref_type', 'weight_history')
    .order('created_at', { ascending: false })
    .limit(30);

  let html = '';

  // Goals section (renders above scoring weights)
  html += `
    <div class="pref-group">
      <h3>Your Networking Goals</h3>
      <p style="font-size: 13px; color: var(--text-muted); margin-bottom: 12px;">
        What kind of reconnections are valuable to you right now? This text
        guides which contacts score as WARM_LEAD.
      </p>
      <textarea id="goals-input"
        style="width: 100%; min-height: 80px; padding: 8px; font-size: 14px; border: 1px solid var(--border); border-radius: 6px; resize: vertical; box-sizing: border-box;"
        placeholder="e.g. Exploring product leadership roles in fintech. Interested in AI/ML applications..."
      >${escapeHtml(userProfile?.current_projects || '')}</textarea>
      <button class="btn btn-primary" style="margin-top: 8px;" onclick="saveGoals(document.getElementById('goals-input').value)">
        Save Goals
      </button>
    </div>`;

  // Scoring Weight Overrides
  const scoringPrefs = (prefs || []).filter(p => p.pref_type === 'scoring_weight');
  html += `
    <div class="pref-group">
      <h3>Scoring Weights</h3>
      <p style="font-size: 13px; color: var(--text-muted); margin-bottom: 12px;">
        Learned from your approve/skip patterns. Values > 1.0 boost, < 1.0 reduce.
      </p>`;

  if (scoringPrefs.length === 0) {
    html += '<p style="font-size: 14px; color: var(--text-muted);">No adjustments yet. Keep reviewing your queue to train the system.</p>';
  } else {
    for (const pref of scoringPrefs) {
      html += `
        <div class="pref-item">
          <span style="font-size: 14px;">${escapeHtml(pref.pref_key)}</span>
          <span style="font-weight: 600;">${parseFloat(pref.pref_value).toFixed(2)}x</span>
        </div>`;
    }
  }
  html += '</div>';

  // Weight Adjustment History (collapsed by default)
  html += `
    <div class="pref-group">
      <h3 style="cursor: pointer;" onclick="this.nextElementSibling.style.display = this.nextElementSibling.style.display === 'none' ? 'block' : 'none'">
        Weight History <span style="font-size: 12px; color: var(--text-muted);">(click to expand)</span>
      </h3>
      <div style="display: none;">`;

  if (!weightHistory || weightHistory.length === 0) {
    html += '<p style="font-size: 14px; color: var(--text-muted);">No weight adjustments recorded yet. The system needs at least 25 actions over 14 days before making changes.</p>';
  } else {
    html += '<p style="font-size: 13px; color: var(--text-muted); margin-bottom: 8px;">Last ' + Math.min(weightHistory.length, 30) + ' adjustments. Multiplier range: 0.6x - 1.4x</p>';
    for (const entry of weightHistory) {
      const relDate = formatRelativeDate(entry.created_at);
      const val = parseFloat(entry.pref_value);
      const color = val > 1.0 ? 'var(--success, #22c55e)' : val < 1.0 ? 'var(--warning, #f59e0b)' : 'var(--text-secondary)';
      html += `
        <div class="pref-item">
          <span style="font-size: 13px;">${escapeHtml(entry.pref_key)}</span>
          <span style="font-weight: 600; color: ${color};">${val.toFixed(2)}x <span style="font-size: 11px; font-weight: 400; color: var(--text-muted);">${relDate}</span></span>
        </div>`;
    }
  }
  html += '</div></div>';

  // Priority Contacts
  const alwaysContacts = (priorityContacts || []).filter(c => c.user_priority === 'always');
  const neverContacts = (priorityContacts || []).filter(c => c.user_priority === 'never');

  html += `
    <div class="pref-group">
      <h3>Always Suggest (${alwaysContacts.length})</h3>`;
  if (alwaysContacts.length === 0) {
    html += '<p style="font-size: 14px; color: var(--text-muted);">No always-suggest contacts.</p>';
  } else {
    for (const c of alwaysContacts) {
      html += `
        <div class="pref-item">
          <a href="#/contact/${c.id}" style="font-size: 14px; color: var(--primary); text-decoration: none;">${escapeHtml(c.name)}</a>
          <button class="btn btn-outline" style="padding: 4px 12px; font-size: 12px;" onclick="clearPriority('${c.id}')">Remove</button>
        </div>`;
    }
  }
  html += '</div>';

  html += `
    <div class="pref-group">
      <h3>Never Suggest (${neverContacts.length})</h3>`;
  if (neverContacts.length === 0) {
    html += '<p style="font-size: 14px; color: var(--text-muted);">No blocked contacts.</p>';
  } else {
    for (const c of neverContacts) {
      html += `
        <div class="pref-item">
          <span style="font-size: 14px;">${escapeHtml(c.name)}</span>
          <button class="btn btn-outline" style="padding: 4px 12px; font-size: 12px;" onclick="clearPriority('${c.id}')">Unblock</button>
        </div>`;
    }
  }
  html += '</div>';

  // Feedback History
  const feedbackTypeLabels = {
    suggestion_quality: 'Suggestion',
    outcome: 'Outcome',
    preference: 'Preference',
    digest_rating: 'Digest Rating',
    never_suggest: 'Blocked',
    always_suggest: 'Prioritized',
  };

  function formatRelativeDate(dateStr) {
    const now = Date.now();
    const then = new Date(dateStr).getTime();
    const diffMs = now - then;
    const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));
    if (diffDays === 0) return 'Today';
    if (diffDays === 1) return '1d ago';
    if (diffDays < 30) return `${diffDays}d ago`;
    const diffMonths = Math.floor(diffDays / 30);
    if (diffMonths === 1) return '1mo ago';
    if (diffMonths < 12) return `${diffMonths}mo ago`;
    return new Date(dateStr).toLocaleDateString();
  }

  html += `
    <div class="pref-group">
      <h3>Feedback History</h3>`;
  if (!feedback || feedback.length === 0) {
    html += '<p style="font-size: 14px; color: var(--text-muted);">No feedback recorded yet.</p>';
  } else {
    html += `<p style="font-size: 13px; color: var(--text-muted); margin-bottom: 12px;">Showing last ${Math.min(feedback.length, 20)} feedback entries</p>`;
    for (const fb of feedback.slice(0, 20)) {
      const typeLabel = feedbackTypeLabels[fb.feedback_type] || escapeHtml(fb.feedback_type);
      const ratingStr = fb.rating ? ` — ${fb.rating}/5` : '';
      const relDate = formatRelativeDate(fb.created_at);
      html += `
        <div class="pref-item">
          <span style="font-size: 13px; color: var(--text-secondary);">${typeLabel}${ratingStr}</span>
          <span style="font-size: 12px; color: var(--text-muted);">${relDate}</span>
        </div>`;
    }
  }
  html += '</div>';

  container.innerHTML = html;
}

async function clearPriority(connectionId) {
  if (!db) return;

  const { error } = await db
    .from('connections')
    .update({ user_priority: null })
    .eq('id', connectionId);

  if (!error) {
    // Re-render
    const content = document.getElementById('app-content');
    if (content) renderPreferences(content);
  }
}

async function saveGoals(text) {
  if (!db) return;

  const { error } = await db
    .from('user_profile')
    .update({
      current_projects: text,
      updated_at: new Date().toISOString()
    })
    .eq('id', 1);

  if (error) return;

  // Write rescore trigger so pipeline knows to rescore existing contacts
  // Uses UserPreference row: pref_type="rescore_trigger", pref_key="goals_updated_at"
  // Pipeline will batch-clear scored_at on contacts where scored_at < this timestamp
  const now = new Date().toISOString();
  await db
    .from('user_preferences')
    .upsert({
      id: 'rescore-goals-trigger',
      pref_type: 'rescore_trigger',
      pref_key: 'goals_updated_at',
      pref_value: now,
      is_active: true,
      created_at: now
    }, { onConflict: 'id' });

  // Show brief confirmation
  const btn = document.querySelector('#goals-input + button') ||
              document.querySelector('.btn-primary');
  if (btn) {
    const original = btn.textContent;
    btn.textContent = 'Saved!';
    setTimeout(() => { btn.textContent = original; }, 1500);
  }
}
