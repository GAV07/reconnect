/* Queue review page — mobile-first card interface */

async function renderQueue(container) {
  if (!supabase) {
    container.innerHTML = '<div class="empty-state"><div class="icon">&#9888;</div><p>Supabase not configured. Set your project URL and anon key in index.html.</p></div>';
    return;
  }

  // Fetch pending queue items with connection data
  const { data: items, error } = await supabase
    .from('outreach_queue')
    .select('*, connections(*)')
    .eq('status', 'pending_review')
    .order('priority_score', { ascending: false });

  if (error) {
    console.error('Queue fetch error:', error);
    container.innerHTML = '<div class="empty-state"><div class="icon">&#9888;</div><p>Failed to load queue.</p></div>';
    return;
  }

  if (!items || items.length === 0) {
    container.innerHTML = `
      <div class="empty-state">
        <div class="icon">&#10004;</div>
        <p>Queue is clear! Check back tomorrow after the pipeline runs.</p>
      </div>`;
    return;
  }

  // Update header
  const headerSub = document.querySelector('.app-header .subtitle');
  if (headerSub) headerSub.textContent = `${items.length} contacts to review`;

  let html = '';
  for (const item of items) {
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

    html += `
      <div class="queue-card" data-item-id="${item.id}" data-connection-id="${conn.id}">
        <div class="card-header">
          <div>
            <div class="name">${nameHtml}</div>
            <div class="role">${roleLine}</div>
          </div>
          <div class="score-badge">${score}</div>
        </div>
        ${whyHtml}
        <div class="card-actions">
          <button class="btn btn-primary" onclick="queueAction(${item.id}, '${conn.id}', 'approve')">Reach Out &#9654;</button>
          <button class="btn btn-secondary" onclick="queueAction(${item.id}, '${conn.id}', 'skip')">Skip</button>
          <button class="btn btn-warning" onclick="queueAction(${item.id}, '${conn.id}', 'snooze')">Snooze</button>
        </div>
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
    if (supabase && navigator.onLine) {
      const updateData = {
        status: newStatus,
        reviewed_at: new Date().toISOString(),
      };
      if (skipReason) updateData.skip_reason = skipReason;

      const { error } = await supabase
        .from('outreach_queue')
        .update(updateData)
        .eq('id', itemId);

      if (error) throw error;
    } else {
      // Queue for offline sync
      queueOfflineAction({ itemId, connectionId, action, timestamp: Date.now() });
    }

    // Remove card from DOM
    card.style.transition = 'all 0.3s ease';
    card.style.maxHeight = '0';
    card.style.overflow = 'hidden';
    card.style.padding = '0';
    card.style.margin = '0';
    setTimeout(() => {
      card.remove();
      // Update count
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

    // If approve, navigate to contact detail for draft generation
    if (action === 'approve') {
      navigate(`#/contact/${connectionId}?queue_item=${itemId}`);
    }
  } catch (err) {
    console.error('Action error:', err);
    card.style.opacity = '1';
    card.style.pointerEvents = 'auto';
    // Queue offline
    queueOfflineAction({ itemId, connectionId, action, timestamp: Date.now() });
  }
}

function setupQueueRealtime() {
  if (!supabase) return;

  supabase
    .channel('queue-changes')
    .on('postgres_changes', { event: 'INSERT', schema: 'public', table: 'outreach_queue' }, () => {
      // Refresh queue when pipeline adds new items
      const content = document.getElementById('app-content');
      if (content && window.location.hash.includes('/queue')) {
        renderQueue(content);
      }
    })
    .subscribe();
}

function escapeHtml(str) {
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}
