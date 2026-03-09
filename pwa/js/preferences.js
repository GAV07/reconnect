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

  let html = '';

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

  // Recent Feedback
  html += `
    <div class="pref-group">
      <h3>Recent Feedback</h3>`;
  if (!feedback || feedback.length === 0) {
    html += '<p style="font-size: 14px; color: var(--text-muted);">No feedback recorded yet.</p>';
  } else {
    for (const fb of feedback.slice(0, 10)) {
      const date = new Date(fb.created_at).toLocaleDateString();
      const ratingStr = fb.rating ? ` — ${fb.rating}/5` : '';
      html += `
        <div class="pref-item">
          <span style="font-size: 13px; color: var(--text-secondary);">${escapeHtml(fb.feedback_type)}${ratingStr}</span>
          <span style="font-size: 12px; color: var(--text-muted);">${date}</span>
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
