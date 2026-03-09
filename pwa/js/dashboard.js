/* Dashboard page — network health, opportunities, data quality */

async function renderDashboard(container) {
  if (!supabase) {
    container.innerHTML = '<div class="empty-state"><p>Supabase not configured.</p></div>';
    return;
  }

  // Fetch latest dashboard snapshot
  const { data: snapshots, error } = await supabase
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
