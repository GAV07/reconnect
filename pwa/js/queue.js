/* Queue review page — mobile-first card interface */

const SIGNAL_ACTIONS = {
  WARM_LEAD:    { label: 'Warm Lead',    cadence: 7,    color: '#1a7f37', bg: '#dcfce7' },
  NURTURE:      { label: 'Nurture',      cadence: 21,   color: '#0369a1', bg: '#e0f2fe' },
  VALUE_DROP:   { label: 'Value Drop',   cadence: 14,   color: '#7c3aed', bg: '#ede9fe' },
  SYNERGY:      { label: 'Synergy',      cadence: 14,   color: '#0a66c2', bg: '#e8f4fd' },
  RECONNECT:    { label: 'Reconnect',    cadence: 14,   color: '#92400e', bg: '#fef3c7' },
  FUTURE_PIVOT: { label: 'Future Pivot', cadence: 60,   color: '#6b7280', bg: '#f3f4f6' },
  ARCHIVE:      { label: 'Archive',      cadence: null, color: '#dc3545', bg: '#fee2e2' },
};

const queueFilters = {
  sortAscending: false,        // default high-to-low
  statusFilter: null,          // null = no status filter (signal filter takes precedence)
  signalFilter: 'untriaged',   // 'untriaged' (default) | signal name | 'all'
  industryFilter: null,        // null = all industries
};

let _queueChannel = null;

async function renderQueue(container) {
  if (!db) {
    container.innerHTML = '<div class="empty-state"><div class="icon">&#9888;</div><p>Supabase not configured. Set your project URL and anon key in index.html.</p></div>';
    return;
  }

  // Fetch all pending_review items when in untriaged mode; all items otherwise
  // Client-side signal filter applied after fetch (PostgREST can't filter on embedded fields)
  let query = db
    .from('outreach_queue')
    .select('*, connections(*)');

  if (queueFilters.signalFilter === 'untriaged') {
    query = query.eq('status', 'pending_review');
  }
  // For 'all' and specific signal filters, fetch without status restriction

  const { data: items, error } = await query;

  if (error) {
    console.error('Queue fetch error:', error);
    container.innerHTML = '<div class="empty-state"><div class="icon">&#9888;</div><p>Failed to load queue.</p></div>';
    return;
  }

  // Sort by reconnect_score from the joined connection (matches what's displayed)
  if (items) {
    items.sort((a, b) => {
      const scoreA = a.connections?.reconnect_score || a.connections?.pre_score || 0;
      const scoreB = b.connections?.reconnect_score || b.connections?.pre_score || 0;
      return queueFilters.sortAscending ? scoreA - scoreB : scoreB - scoreA;
    });
  }

  // Client-side signal filter — PostgREST cannot filter on embedded resource fields
  let filtered = items || [];
  if (queueFilters.signalFilter === 'untriaged') {
    filtered = filtered.filter(item => {
      const conn = item.connections;
      if (!conn) return false;
      return !conn.latest_signal && conn.user_priority !== 'never';
    });
  } else if (queueFilters.signalFilter === 'all') {
    // Show everything except ARCHIVE contacts
    filtered = filtered.filter(item => {
      const conn = item.connections;
      if (!conn) return false;
      return conn.user_priority !== 'never';
    });
  } else if (queueFilters.signalFilter) {
    // Specific signal filter
    filtered = filtered.filter(item => {
      const conn = item.connections;
      if (!conn) return false;
      return conn.latest_signal === queueFilters.signalFilter;
    });
  }

  // Client-side industry filter on raw_enrichment (existing behavior preserved)
  if (queueFilters.industryFilter) {
    filtered = filtered.filter(item => {
      const conn = item.connections;
      if (!conn) return false;
      const enrichment = conn.raw_enrichment?.data || conn.raw_enrichment || {};
      const industry = (enrichment.company_industry || enrichment.companyIndustry || '').toLowerCase();
      return industry.includes(queueFilters.industryFilter.toLowerCase());
    });
  }

  // Extract unique industries from all fetched items (before signal filter) for the dropdown
  const industries = [...new Set((items || []).map(item => {
    const conn = item.connections;
    if (!conn) return '';
    const enrichment = conn.raw_enrichment?.data || conn.raw_enrichment || {};
    return enrichment.company_industry || enrichment.companyIndustry || '';
  }).filter(Boolean))].sort();

  // Update header subtitle to reflect current filter
  const headerSub = document.querySelector('.app-header .subtitle');
  if (headerSub) {
    if (queueFilters.signalFilter === 'untriaged') {
      headerSub.textContent = `${filtered.length} contacts to triage`;
    } else if (queueFilters.signalFilter === 'all') {
      headerSub.textContent = `${filtered.length} contacts (all)`;
    } else if (queueFilters.signalFilter && SIGNAL_ACTIONS[queueFilters.signalFilter]) {
      headerSub.textContent = `${filtered.length} ${SIGNAL_ACTIONS[queueFilters.signalFilter].label} contacts`;
    } else {
      headerSub.textContent = `${filtered.length} contacts`;
    }
  }

  // Build signal filter dropdown
  const signalFilterHtml = `
    <div class="filter-group">
      <label>View</label>
      <select onchange="setQueueSignalFilter(this.value)">
        <option value="untriaged" ${queueFilters.signalFilter === 'untriaged' ? 'selected' : ''}>Untriaged</option>
        <option value="all" ${queueFilters.signalFilter === 'all' ? 'selected' : ''}>All</option>
        ${Object.entries(SIGNAL_ACTIONS).map(([key, info]) =>
          `<option value="${key}" ${queueFilters.signalFilter === key ? 'selected' : ''}>${escapeHtml(info.label)}</option>`
        ).join('')}
      </select>
    </div>`;

  // Build filter bar HTML (Status dropdown replaced by Signal dropdown)
  const filterBarHtml = `
    <div class="queue-filters">
      <div class="filter-group">
        <label>Sort</label>
        <button class="btn btn-sm sort-toggle" onclick="toggleQueueSort()">
          Score ${queueFilters.sortAscending ? '&#9650;' : '&#9660;'}
        </button>
      </div>
      ${signalFilterHtml}
      <div class="filter-group">
        <label>Industry</label>
        <select onchange="setQueueIndustryFilter(this.value)">
          <option value="">All</option>
          ${industries.map(ind => `<option value="${escapeHtml(ind)}" ${queueFilters.industryFilter === ind ? 'selected' : ''}>${escapeHtml(ind)}</option>`).join('')}
        </select>
      </div>
    </div>`;

  // Contextual empty state based on active filter
  if (filtered.length === 0) {
    let emptyMessage;
    if (queueFilters.signalFilter === 'untriaged') {
      emptyMessage = 'All caught up! No untriaged contacts in queue.';
    } else if (queueFilters.signalFilter === 'all') {
      emptyMessage = 'Queue is empty. Check back after the pipeline runs.';
    } else if (queueFilters.signalFilter && SIGNAL_ACTIONS[queueFilters.signalFilter]) {
      emptyMessage = `No contacts with ${SIGNAL_ACTIONS[queueFilters.signalFilter].label} signal.`;
    } else {
      emptyMessage = 'No contacts match the current filters.';
    }
    container.innerHTML = filterBarHtml + `
      <div class="empty-state">
        <div class="icon">&#10004;</div>
        <p>${emptyMessage}</p>
      </div>`;
    setupQueueRealtime();
    return;
  }

  let html = filterBarHtml;
  for (const item of filtered) {
    const conn = item.connections;
    if (!conn) continue;

    const name = escapeHtml(conn.name || 'Unknown');
    const role = escapeHtml(conn.current_role || '');
    const company = escapeHtml(conn.current_company || '');
    const roleLine = company ? `${role} @ ${company}` : role;
    const score = Math.round(conn.reconnect_score || conn.pre_score || 0);
    const whyToday = escapeHtml(item.why_today || '');
    const linkedinUrl = conn.linkedin_url || '';

    const nameHtml = linkedinUrl
      ? `<a href="${escapeHtml(linkedinUrl)}" target="_blank">${name}</a>`
      : name;

    const whyHtml = whyToday
      ? `<div class="why-today"><strong>WHY:</strong> ${whyToday}</div>`
      : '';

    // Part D: Contextual card fields
    // 1. Industry chip
    const enrichment = conn.raw_enrichment?.data || conn.raw_enrichment || {};
    const industry = enrichment.company_industry || enrichment.companyIndustry || '';
    const industryChip = industry
      ? `<span class="industry-chip">${escapeHtml(industry)}</span>`
      : '';

    // 2. First key factor from mini_key_factors or score_reasoning
    let keyFactor = '';
    if (item.mini_key_factors) {
      const factors = item.mini_key_factors.split('\n').map(f => f.trim()).filter(Boolean);
      keyFactor = factors[0] || '';
    } else if (conn.score_reasoning) {
      try {
        const reasoning = typeof conn.score_reasoning === 'string'
          ? JSON.parse(conn.score_reasoning)
          : conn.score_reasoning;
        keyFactor = (reasoning.key_factors && reasoning.key_factors[0]) || '';
      } catch (e) {
        keyFactor = '';
      }
    }
    const keyFactorHtml = keyFactor
      ? `<div class="card-key-factor">${escapeHtml(keyFactor)}</div>`
      : '';

    // 3. Last interaction date
    let lastContactHtml = '';
    if (conn.last_message_date) {
      try {
        const lastDate = new Date(conn.last_message_date).toLocaleDateString('en-US', {
          month: 'short', day: 'numeric', year: 'numeric'
        });
        lastContactHtml = `<span class="card-last-contact">Last: ${escapeHtml(lastDate)}</span>`;
      } catch (e) {
        lastContactHtml = '';
      }
    }

    // 4. Notes excerpt from connections.notes (first 60 chars)
    let notesHtml = '';
    if (conn.notes) {
      const excerpt = conn.notes.length > 60 ? conn.notes.slice(0, 60) + '...' : conn.notes;
      notesHtml = `<div class="card-note-excerpt">${escapeHtml(excerpt)}</div>`;
    }

    // Wrap industry chip and last contact in a flex meta row
    const metaRowHtml = (industryChip || lastContactHtml)
      ? `<div class="card-meta">${industryChip}${lastContactHtml}</div>`
      : '';

    // Part B: Signal picker replacing 3-button triage
    // Determine if card already has a signal assigned
    const existingSignal = conn.latest_signal;
    const existingSignalInfo = existingSignal && SIGNAL_ACTIONS[existingSignal] ? SIGNAL_ACTIONS[existingSignal] : null;

    // Signal picker chips (all 7 signals)
    const signalChipsHtml = Object.entries(SIGNAL_ACTIONS).map(([key, info]) =>
      `<button class="signal-chip"
        style="background:${info.bg};color:${info.color};border-color:${info.color}20;"
        onclick="assignSignalFromCard(event, '${conn.id}', '${key}', ${item.id})"
        title="${escapeHtml(info.label)}${info.cadence ? ' — ' + info.cadence + '-day cadence' : ''}"
      >${escapeHtml(info.label)}</button>`
    ).join('');

    // Toggle area: show existing signal badge or "Assign Signal" CTA
    const toggleContent = existingSignalInfo
      ? `<span class="signal-badge"
           style="background:${existingSignalInfo.bg};color:${existingSignalInfo.color};"
         >${escapeHtml(existingSignalInfo.label)}</span> <span style="font-size:12px;color:var(--text-muted);">&#9660;</span>`
      : `<span class="assign-signal-cta">Assign Signal &#9660;</span>`;

    // For legacy non-pending cards without a signal, show a read-only status badge instead
    const isPending = item.status === 'pending_review';
    let actionsHtml;
    if (!isPending && !existingSignal) {
      // Legacy approved/sent/skipped without signal — read-only status badge
      actionsHtml = `<div class="card-actions card-status-wrapper">
        <div class="card-status-badge status-${item.status}">${item.status.replace(/_/g, ' ')}</div>
      </div>`;
    } else {
      // Pending cards or cards with existing signal — show signal picker
      actionsHtml = `<div class="card-actions signal-triage" id="signal-triage-${item.id}">
        <div class="signal-toggle" onclick="toggleSignalPicker(event, ${item.id})">
          ${toggleContent}
        </div>
        <div class="signal-picker hidden" id="signal-picker-${item.id}">
          ${signalChipsHtml}
        </div>
      </div>`;
    }

    html += `
      <div class="queue-card" data-item-id="${item.id}" data-connection-id="${conn.id}"
           onclick="if(event.target.closest('.card-actions'))return; navigate('#/contact/${conn.id}')" style="cursor:pointer;">
        <div class="card-header">
          <div>
            <div class="name">${nameHtml}</div>
            <div class="role">${roleLine}</div>
          </div>
          <div class="score-badge">${score}</div>
        </div>
        ${metaRowHtml}
        ${keyFactorHtml}
        ${whyHtml}
        ${notesHtml}
        ${actionsHtml}
      </div>`;
  }

  container.innerHTML = html;

  // Subscribe to realtime updates
  setupQueueRealtime();
}

function toggleSignalPicker(event, itemId) {
  event.stopPropagation();
  const picker = document.getElementById(`signal-picker-${itemId}`);
  if (picker) {
    picker.classList.toggle('hidden');
  }
}

async function assignSignalFromCard(event, connectionId, signal, itemId) {
  event.stopPropagation();

  const triageArea = document.getElementById(`signal-triage-${itemId}`);
  const picker = document.getElementById(`signal-picker-${itemId}`);
  const signalInfo = SIGNAL_ACTIONS[signal];
  if (!signalInfo) return;

  // Optimistic badge update — replace toggle area content immediately
  if (triageArea) {
    const toggle = triageArea.querySelector('.signal-toggle');
    if (toggle) {
      toggle.innerHTML = `<span class="signal-badge"
        style="background:${signalInfo.bg};color:${signalInfo.color};"
      >${escapeHtml(signalInfo.label)}</span> <span style="font-size:12px;color:var(--text-muted);">&#9660;</span>`;
    }
    // Close the picker
    if (picker) picker.classList.add('hidden');
  }

  try {
    if (!db) throw new Error('Supabase not available');

    // INSERT to contact_signals (reassign = new row, no UPDATE needed per schema grants)
    const { error: signalError } = await db
      .from('contact_signals')
      .insert({ connection_id: connectionId, signal, assigned_by: 'user' });

    if (signalError) throw signalError;

    // Compute cadence_due_at from SIGNAL_ACTIONS const
    const cadenceDays = signalInfo.cadence; // null for ARCHIVE
    const cadenceDueAt = (cadenceDays !== null && cadenceDays !== undefined)
      ? new Date(Date.now() + cadenceDays * 24 * 60 * 60 * 1000).toISOString()
      : null;

    // UPDATE connections.latest_signal (and user_priority for ARCHIVE, cadence_due_at for all)
    const updateData = { latest_signal: signal, cadence_due_at: cadenceDueAt };
    if (signal === 'ARCHIVE') {
      updateData.user_priority = 'never';
      // cadenceDueAt is null for ARCHIVE — explicitly clears any existing value
    }

    const { error: connError } = await db
      .from('connections')
      .update(updateData)
      .eq('id', connectionId);

    if (connError) throw connError;

    // UPDATE outreach_queue.signal so Edge Function draft receives it
    const { error: queueSignalError } = await db
      .from('outreach_queue')
      .update({ signal: signal, signal_context: null })
      .eq('id', itemId);

    if (queueSignalError) throw queueSignalError;

    // ARCHIVE: fade and remove the card from DOM — excluded from default + all views
    if (signal === 'ARCHIVE') {
      const card = document.querySelector(`[data-item-id="${itemId}"]`);
      if (card) {
        card.style.transition = 'opacity 0.4s ease, max-height 0.3s ease 0.4s';
        card.style.opacity = '0';
        setTimeout(() => {
          card.style.maxHeight = '0';
          card.style.overflow = 'hidden';
          card.style.padding = '0';
          card.style.margin = '0';
          setTimeout(() => card.remove(), 300);
        }, 400);
      }
    }
  } catch (err) {
    console.error('Signal assignment error:', err);
    // Revert: restore "Assign Signal" CTA on failure
    if (triageArea) {
      const toggle = triageArea.querySelector('.signal-toggle');
      if (toggle) {
        toggle.innerHTML = `<span class="assign-signal-cta">Assign Signal &#9660;</span>`;
      }
    }
  }
}

async function queueAction(itemId, connectionId, action) {
  const card = document.querySelector(`[data-item-id="${itemId}"]`);
  if (!card) return;

  // Optimistic UI — fade out the card
  card.style.opacity = '0.5';
  card.style.pointerEvents = 'none';

  const statusMap = {
    approve: 'approved',
    skip: 'skipped',
    snooze: 'skipped',
  };
  const newStatus = statusMap[action];
  const skipReason = action === 'snooze' ? 'Snoozed via PWA (3 day cooldown)' : (action === 'skip' ? 'Skipped via PWA' : null);

  try {
    // Try online update
    if (db && navigator.onLine) {
      const updateData = {
        status: newStatus,
        reviewed_at: new Date().toISOString(),
      };
      if (skipReason) updateData.skip_reason = skipReason;

      const { error } = await db
        .from('outreach_queue')
        .update(updateData)
        .eq('id', itemId);

      if (error) throw error;
    } else {
      // Queue for offline sync
      queueOfflineAction({ itemId, connectionId, action, timestamp: Date.now() });
    }

    // If approve, navigate to contact detail for draft generation
    if (action === 'approve') {
      navigate(`#/contact/${connectionId}?queue_item=${itemId}`);
      return;
    }

    // Remove card from DOM (only for skip/snooze — approve navigates away)
    card.style.transition = 'all 0.3s ease';
    card.style.maxHeight = '0';
    card.style.overflow = 'hidden';
    card.style.padding = '0';
    card.style.margin = '0';
    setTimeout(() => {
      card.remove();
      // Only update DOM if still on queue page
      if (!window.location.hash.includes('/queue') && window.location.hash !== '' && window.location.hash !== '#/queue') return;
      const remaining = document.querySelectorAll('.queue-card').length;
      const headerSub = document.querySelector('.app-header .subtitle');
      if (headerSub) headerSub.textContent = remaining > 0 ? `${remaining} contacts to review` : 'Queue cleared!';
      if (remaining === 0) {
        document.getElementById('app-content').innerHTML = `
          <div class="empty-state">
            <div class="icon">&#10004;</div>
            <p>Queue is clear! Check back tomorrow.</p>
          </div>`;
      }
    }, 300);
  } catch (err) {
    console.error('Action error:', err);
    card.style.opacity = '1';
    card.style.pointerEvents = 'auto';
    // Queue offline
    queueOfflineAction({ itemId, connectionId, action, timestamp: Date.now() });
  }
}

function setupQueueRealtime() {
  if (!db) return;
  if (_queueChannel) {
    _queueChannel.unsubscribe();
    _queueChannel = null;
  }
  _queueChannel = db.channel('queue-changes')
    .on('postgres_changes', { event: 'INSERT', schema: 'public', table: 'outreach_queue' }, () => {
      // Refresh queue when pipeline adds new items
      const content = document.getElementById('app-content');
      if (content && window.location.hash.includes('/queue')) {
        renderQueue(content);
      }
    })
    .subscribe();
}

function toggleQueueSort() {
  queueFilters.sortAscending = !queueFilters.sortAscending;
  const content = document.getElementById('app-content');
  if (content) renderQueue(content);
}

function setQueueSignalFilter(value) {
  queueFilters.signalFilter = value || 'untriaged';
  const content = document.getElementById('app-content');
  if (content) renderQueue(content);
}

function setQueueStatusFilter(value) {
  queueFilters.statusFilter = value || null;
  const content = document.getElementById('app-content');
  if (content) renderQueue(content);
}

function setQueueIndustryFilter(value) {
  queueFilters.industryFilter = value || null;
  const content = document.getElementById('app-content');
  if (content) renderQueue(content);
}

function escapeHtml(str) {
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}
