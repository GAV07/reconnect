/* Dashboard page — network health, opportunities, data quality */

function buildFunnelSection(quality) {
  const stages = [
    { label: 'Imported', count: quality.total_contacts || 0 },
    { label: 'Scored', count: quality.scored || 0 },
    { label: 'Reviewed', count: quality.reviewed || 0 },
    { label: 'Reached Out', count: quality.reached_out || 0 },
    { label: 'Connected', count: quality.connected || 0 },
  ];
  const max = stages[0].count || 1;

  let html = '<div class="detail-section mt-4"><h3 style="font-size: 15px; font-weight: 600; color: var(--text-secondary); margin-bottom: 12px;">PIPELINE FUNNEL</h3>';
  for (const stage of stages) {
    const pct = Math.round((stage.count / max) * 100);
    html += `
      <div class="funnel-stage">
        <div class="funnel-label">${stage.label}</div>
        <div class="funnel-bar"><div class="funnel-fill" style="width:${pct}%"></div></div>
        <div class="funnel-count">${stage.count}</div>
      </div>`;
  }
  html += '</div>';
  return html;
}

function buildEnrichmentStatusSection(quality) {
  const enriched = quality.enriched || 0;
  const needEnrichment = quality.need_enrichment || 0;
  const total = quality.total_contacts || 0;
  const enrichedPct = quality.enriched_pct || 0;

  let html = '<div class="detail-section mt-4"><h3 style="font-size: 15px; font-weight: 600; color: var(--text-secondary); margin-bottom: 12px;">ENRICHMENT STATUS</h3>';
  html += '<div class="metric-grid">';
  html += `<div class="metric-card"><div class="metric-label">Enriched</div><div class="metric-value" style="color: var(--success);">${enriched}</div><div class="metric-sub">${enrichedPct}% of ${total}</div></div>`;
  html += `<div class="metric-card"><div class="metric-label">Need Enrichment</div><div class="metric-value" style="color: ${needEnrichment > 0 ? 'var(--warning)' : 'var(--success)'};">${needEnrichment}</div><div class="metric-sub">${total > 0 ? Math.round((needEnrichment / total) * 100) : 0}% of ${total}</div></div>`;
  html += '</div>';

  // Email coverage sub-section
  const hasEmail = quality.has_email || 0;
  const needEmail = quality.need_email || 0;
  html += '<div class="metric-grid" style="margin-top: 12px;">';
  html += `<div class="metric-card"><div class="metric-label">Have Email</div><div class="metric-value">${hasEmail}</div><div class="metric-sub">${quality.email_pct || 0}%</div></div>`;
  html += `<div class="metric-card"><div class="metric-label">Need Email</div><div class="metric-value">${needEmail}</div></div>`;
  html += '</div>';

  html += '</div>';
  return html;
}

async function renderDashboard(container) {
  if (!db) {
    container.innerHTML = '<div class="empty-state"><p>Supabase not configured.</p></div>';
    return;
  }

  // Fetch latest dashboard snapshot
  const { data: snapshots, error } = await db
    .from('dashboard_snapshots')
    .select('*')
    .eq('snapshot_type', 'daily')
    .order('created_at', { ascending: false })
    .limit(1);

  if (error || !snapshots || snapshots.length === 0) {
    container.innerHTML = `
      <div class="empty-state">
        <div class="icon">&#128200;</div>
        <p>No dashboard data yet. Run the pipeline to generate a snapshot.</p>
      </div>`;
    return;
  }

  const snapshot = snapshots[0].snapshot_data;
  const health = snapshot.network_health || {};
  const alerts = snapshot.opportunity_alerts || [];
  const quality = snapshot.data_quality || {};
  const feedback = snapshot.feedback_insights || {};

  // Network Health Score
  const healthScore = Math.round(health.score || 0);
  const healthColor = healthScore >= 70 ? 'var(--success)' : healthScore >= 40 ? 'var(--warning)' : 'var(--danger)';
  const components = health.components || {};

  let html = `
    <div class="metric-card" style="text-align: center;">
      <div class="metric-label">Network Health Score</div>
      <div class="metric-value" style="font-size: 48px; color: ${healthColor};">${healthScore}</div>
      <div class="metric-sub">out of 100</div>
    </div>

    <div class="metric-grid">
      <div class="metric-card">
        <div class="metric-label">Data Quality</div>
        <div class="metric-value">${Math.round(components.data_completeness || 0)}%</div>
      </div>
      <div class="metric-card">
        <div class="metric-label">Enriched</div>
        <div class="metric-value">${Math.round(components.enrichment_pct || 0)}%</div>
      </div>
      <div class="metric-card">
        <div class="metric-label">Email Coverage</div>
        <div class="metric-value">${Math.round(components.email_coverage_pct || 0)}%</div>
      </div>
      <div class="metric-card">
        <div class="metric-label">Activity</div>
        <div class="metric-value">${components.activity_score || 0}</div>
      </div>
    </div>`;

  // Data Quality
  html += `
    <div class="detail-section mt-4">
      <h3 style="font-size: 15px; font-weight: 600; color: var(--text-secondary); margin-bottom: 12px;">DATA QUALITY</h3>
      <div class="metric-grid">
        <div class="metric-card">
          <div class="metric-label">Total</div>
          <div class="metric-value">${quality.total_contacts || 0}</div>
        </div>
        <div class="metric-card">
          <div class="metric-label">Scored</div>
          <div class="metric-value">${quality.scored || 0}</div>
          <div class="metric-sub">${quality.scored_pct || 0}%</div>
        </div>
        <div class="metric-card">
          <div class="metric-label">Need Enrichment</div>
          <div class="metric-value">${quality.need_enrichment || 0}</div>
        </div>
        <div class="metric-card">
          <div class="metric-label">Need Email</div>
          <div class="metric-value">${quality.need_email || 0}</div>
        </div>
      </div>
    </div>`;

  // Pipeline Funnel (VIEW-01)
  html += buildFunnelSection(quality);

  // Enrichment Status (VIEW-02)
  html += buildEnrichmentStatusSection(quality);

  // Opportunity Alerts
  if (alerts.length > 0) {
    html += '<div class="detail-section mt-4"><h3 style="font-size: 15px; font-weight: 600; color: var(--text-secondary); margin-bottom: 12px;">OPPORTUNITIES</h3>';
    for (const alert of alerts.slice(0, 8)) {
      const alertClass = alert.type === 'job_change' ? 'alert-job-change' : alert.type === 'stale_high_value' ? 'alert-stale' : '';
      const typeLabel = alert.type === 'job_change' ? 'New Role' : alert.type === 'active_poster' ? 'Active' : 'Stale';
      html += `
        <a href="#/contact/${alert.connection_id}" style="text-decoration: none; color: inherit;">
          <div class="alert-card ${alertClass}">
            <div class="alert-title">${escapeHtml(alert.name)} <span style="font-weight: normal; color: var(--text-muted); font-size: 12px;">${typeLabel}</span></div>
            <div class="alert-detail">${escapeHtml(alert.detail)}</div>
          </div>
        </a>`;
    }
    html += '</div>';
  }

  // Feedback Insights
  if (feedback.avg_digest_rating !== null && feedback.avg_digest_rating !== undefined) {
    html += `
      <div class="detail-section mt-4">
        <h3 style="font-size: 15px; font-weight: 600; color: var(--text-secondary); margin-bottom: 12px;">FEEDBACK</h3>
        <div class="metric-card">
          <div class="metric-label">Avg Digest Rating</div>
          <div class="metric-value">${feedback.avg_digest_rating}/5</div>
        </div>
      </div>`;
  }

  container.innerHTML = html;
}
