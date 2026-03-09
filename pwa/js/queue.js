/* Queue review page — mobile-first card interface */

const queueFilters = {
  sortAscending: false,        // QUEUE-01: default high-to-low
  statusFilter: 'pending_review',  // QUEUE-02: default to pending (matches current behavior)
  industryFilter: null,        // QUEUE-03: null = all industries
};

let _queueChannel = null;

async function renderQueue(container) {
  if (!db) {
    container.innerHTML = '<div class="empty-state"><div class="icon">&#9888;</div><p>Supabase not configured. Set your project URL and anon key in index.html.</p></div>';
    return;
  }

  // Dynamic query builder — QUEUE-01/02: sort and status are server-side
  let query = db
    .from('outreach_queue')
    .select('*, connections(*)')
    .order('priority_score', { ascending: queueFilters.sortAscending });

  if (queueFilters.statusFilter) {
    query = query.eq('status', queueFilters.statusFilter);
  }
  // No status filter = show all statuses

  const { data: items, error } = await query;

  if (error) {
    console.error('Queue fetch error:', error);
    container.innerHTML = '<div class="empty-state"><div class="icon">&#9888;</div><p>Failed to load queue.</p></div>';
    return;
  }

  // QUEUE-03: Client-side industry filter on raw_enrichment
  let filtered = items || [];
  if (queueFilters.industryFilter) {
    filtered = filtered.filter(item => {
      const conn = item.connections;
      if (!conn) return false;
      const enrichment = conn.raw_enrichment?.data || conn.raw_enrichment || {};
      const industry = (enrichment.company_industry || enrichment.companyIndustry || '').toLowerCase();
      return industry.includes(queueFilters.industryFilter.toLowerCase());
    });
  }

  // Extract unique industries from all fetched items (before client-side filter) for the dropdown
  const industries = [...new Set((items || []).map(item => {
    const conn = item.connections;
    if (!conn) return '';
    const enrichment = conn.raw_enrichment?.data || conn.raw_enrichment || {};
    return enrichment.company_industry || enrichment.companyIndustry || '';
  }).filter(Boolean))].sort();

  // Update header with filtered count
  const headerSub = document.querySelector('.app-header .subtitle');
  if (headerSub) {
    headerSub.textContent = `${filtered.length} contacts${queueFilters.statusFilter ? '' : ' (all statuses)'}`;
  }

  // Build filter bar HTML
  const filterBarHtml = `
    <div class="queue-filters">
      <div class="filter-group">
        <label>Sort</label>
        <button class="btn btn-sm sort-toggle" onclick="toggleQueueSort()">
          Score ${queueFilters.sortAscending ? '&#9650;' : '&#9660;'}
        </button>
      </div>
      <div class="filter-group">
        <label>Status</label>
        <select onchange="setQueueStatusFilter(this.value)">
          <option value="">All</option>
          <option value="pending_review" ${queueFilters.statusFilter === 'pending_review' ? 'selected' : ''}>Pending</option>
          <option value="approved" ${queueFilters.statusFilter === 'approved' ? 'selected' : ''}>Approved</option>
          <option value="sent" ${queueFilters.statusFilter === 'sent' ? 'selected' : ''}>Sent</option>
          <option value="skipped" ${queueFilters.statusFilter === 'skipped' ? 'selected' : ''}>Skipped</option>
        </select>
      </div>
      <div class="filter-group">
        <label>Industry</label>
        <select onchange="setQueueIndustryFilter(this.value)">
          <option value="">All</option>
          ${industries.map(ind => `<option value="${escapeHtml(ind)}" ${queueFilters.industryFilter === ind ? 'selected' : ''}>${escapeHtml(ind)}</option>`).join('')}
        </select>
      </div>
    </div>`;

  if (filtered.length === 0) {
    container.innerHTML = filterBarHtml + `
      <div class="empty-state">
        <div class="icon">&#10004;</div>
        <p>${items && items.length > 0 ? 'No contacts match the current filters.' : 'Queue is clear! Check back tomorrow after the pipeline runs.'}</p>
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

    // Status-aware card rendering (pitfall 5 fix)
    // pending_review: show action buttons
    // approved/sent/skipped: show read-only status badge
    const isPending = item.status === 'pending_review';
    const actionsHtml = isPending
      ? `<div class="card-actions">
          <button class="btn btn-primary" onclick="queueAction(${item.id}, '${conn.id}', 'approve')">Reach Out &#9654;</button>
          <button class="btn btn-secondary" onclick="queueAction(${item.id}, '${conn.id}', 'skip')">Skip</button>
          <button class="btn btn-warning" onclick="queueAction(${item.id}, '${conn.id}', 'snooze')">Snooze</button>
        </div>`
      : `<div class="card-actions card-status-wrapper">
          <div class="card-status-badge status-${item.status}">${item.status.replace('_', ' ')}</div>
        </div>`;

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
        ${whyHtml}
        ${actionsHtml}
      </div>`;
  }

  container.innerHTML = html;

  // Subscribe to realtime updates
  setupQueueRealtime();
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
