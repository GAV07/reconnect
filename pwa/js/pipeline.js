/* Pipeline view — acquisition funnel tracking */

const PIPELINE_STAGES = {
  target:    { label: 'Target',    color: '#6b7280', bg: '#f3f4f6' },
  contacted: { label: 'Contacted', color: '#0369a1', bg: '#e0f2fe' },
  responded: { label: 'Responded', color: '#7c3aed', bg: '#ede9fe' },
  meeting:   { label: 'Meeting',   color: '#0a66c2', bg: '#e8f4fd' },
  proposal:  { label: 'Proposal',  color: '#92400e', bg: '#fef3c7' },
  won:       { label: 'Won',       color: '#1a7f37', bg: '#dcfce7' },
  lost:      { label: 'Lost',      color: '#dc3545', bg: '#fee2e2' },
};

const ACQUISITION_ROLES = {
  buyer:     { label: 'Buyer',     color: '#0a66c2', bg: '#e8f4fd' },
  activator: { label: 'Activator', color: '#7c3aed', bg: '#ede9fe' },
};

const pipelineFilters = {
  stageFilter: null,
  roleFilter: null,
};

async function renderPipeline(container) {
  if (!db) {
    container.innerHTML = '<div class="empty-state"><div class="icon">&#9888;</div><p>Supabase not configured.</p></div>';
    return;
  }

  const { data: contacts, error } = await db
    .from('connections')
    .select('id, name, current_role, current_company, enriched_industry, acquisition_role, pipeline_stage, pipeline_notes, pipeline_updated_at')
    .or('pipeline_stage.not.is.null,acquisition_role.not.is.null')
    .order('pipeline_updated_at', { ascending: false, nullsFirst: false });

  if (error) {
    console.error('Pipeline fetch error:', error);
    container.innerHTML = '<div class="empty-state"><div class="icon">&#9888;</div><p>Failed to load pipeline.</p></div>';
    return;
  }

  if (!contacts || contacts.length === 0) {
    container.innerHTML = '<div class="empty-state"><div class="icon">&#128200;</div><p>No contacts in pipeline yet. Open any contact and use the Pipeline section to add them.</p></div>';
    return;
  }

  // Stage counts for funnel
  const stageCounts = {};
  for (const key of Object.keys(PIPELINE_STAGES)) {
    stageCounts[key] = 0;
  }
  for (const c of contacts) {
    if (c.pipeline_stage && stageCounts[c.pipeline_stage] !== undefined) {
      stageCounts[c.pipeline_stage]++;
    }
  }
  const maxCount = Math.max(1, ...Object.values(stageCounts));

  let funnelHtml = '<div class="detail-section" style="margin-top:0;"><h3>Pipeline Funnel</h3>';
  for (const [key, info] of Object.entries(PIPELINE_STAGES)) {
    const count = stageCounts[key];
    const pct = Math.round((count / maxCount) * 100);
    funnelHtml += `
      <div class="funnel-stage">
        <span class="funnel-label">${info.label}</span>
        <div class="funnel-bar">
          <div class="funnel-fill" style="width:${pct}%;background:${info.color};"></div>
        </div>
        <span class="funnel-count">${count}</span>
      </div>`;
  }
  funnelHtml += '</div>';

  // Filter bar
  let stageOptions = '<option value="">All Stages</option>';
  for (const [key, info] of Object.entries(PIPELINE_STAGES)) {
    const sel = pipelineFilters.stageFilter === key ? ' selected' : '';
    stageOptions += `<option value="${key}"${sel}>${info.label}</option>`;
  }
  let roleOptions = '<option value="">All Roles</option>';
  for (const [key, info] of Object.entries(ACQUISITION_ROLES)) {
    const sel = pipelineFilters.roleFilter === key ? ' selected' : '';
    roleOptions += `<option value="${key}"${sel}>${info.label}</option>`;
  }

  const filterHtml = `
    <div class="contacts-filter-bar">
      <div class="contacts-filter-row">
        <div class="filter-group">
          <label>Stage</label>
          <select class="filter-input" onchange="pipelineFilters.stageFilter=this.value||null;renderPipeline(document.getElementById('app-content'));">
            ${stageOptions}
          </select>
        </div>
        <div class="filter-group">
          <label>Role</label>
          <select class="filter-input" onchange="pipelineFilters.roleFilter=this.value||null;renderPipeline(document.getElementById('app-content'));">
            ${roleOptions}
          </select>
        </div>
      </div>
    </div>`;

  // Apply client-side filters
  let filtered = contacts;
  if (pipelineFilters.stageFilter) {
    filtered = filtered.filter(c => c.pipeline_stage === pipelineFilters.stageFilter);
  }
  if (pipelineFilters.roleFilter) {
    filtered = filtered.filter(c => c.acquisition_role === pipelineFilters.roleFilter);
  }

  // Card list
  let cardsHtml = '';
  for (const c of filtered) {
    const name = escapeHtml(c.name || 'Unknown');
    const role = escapeHtml(c.current_role || '');
    const company = escapeHtml(c.current_company || '');
    const roleLine = company ? `${role} @ ${company}` : role;
    const industry = c.enriched_industry ? `<span class="industry-chip">${escapeHtml(c.enriched_industry)}</span>` : '';

    const stageInfo = c.pipeline_stage && PIPELINE_STAGES[c.pipeline_stage]
      ? PIPELINE_STAGES[c.pipeline_stage] : null;
    const stageBadge = stageInfo
      ? `<span class="signal-badge" style="background:${stageInfo.bg};color:${stageInfo.color};">${stageInfo.label}</span>`
      : '';

    const roleInfo = c.acquisition_role && ACQUISITION_ROLES[c.acquisition_role]
      ? ACQUISITION_ROLES[c.acquisition_role] : null;
    const roleBadge = roleInfo
      ? `<span class="signal-badge" style="background:${roleInfo.bg};color:${roleInfo.color};">${roleInfo.label}</span>`
      : '';

    const notesPreview = c.pipeline_notes
      ? `<div class="card-note-excerpt">${escapeHtml(c.pipeline_notes.length > 80 ? c.pipeline_notes.slice(0, 80) + '...' : c.pipeline_notes)}</div>`
      : '';

    // Stage advance dropdown
    let stageSelectOptions = '<option value="">-- Stage --</option>';
    for (const [key, info] of Object.entries(PIPELINE_STAGES)) {
      const sel = c.pipeline_stage === key ? ' selected' : '';
      stageSelectOptions += `<option value="${key}"${sel}>${info.label}</option>`;
    }

    cardsHtml += `
      <div class="queue-card" onclick="if(event.target.closest('.pipeline-card-actions'))return; navigate('#/contact/${c.id}')" style="cursor:pointer;">
        <div class="card-header">
          <div>
            <div class="name"><a href="#/contact/${c.id}" onclick="event.stopPropagation();">${name}</a></div>
            <div class="role">${roleLine}</div>
          </div>
          <div style="display:flex;gap:4px;flex-wrap:wrap;">${stageBadge}${roleBadge}</div>
        </div>
        <div class="card-meta">${industry}</div>
        ${notesPreview}
        <div class="pipeline-card-actions" style="margin-top:8px;" onclick="event.stopPropagation();">
          <select class="filter-input" style="width:auto;font-size:13px;padding:4px 8px;"
            onchange="advancePipelineStage('${c.id}', this.value)">
            ${stageSelectOptions}
          </select>
        </div>
      </div>`;
  }

  container.innerHTML = funnelHtml + filterHtml + cardsHtml;
}

async function advancePipelineStage(connectionId, newStage) {
  if (!db) return;
  try {
    const updateData = {
      pipeline_stage: newStage || null,
      pipeline_updated_at: new Date().toISOString(),
    };
    const { error } = await db
      .from('connections')
      .update(updateData)
      .eq('id', connectionId);
    if (error) throw error;
    // Re-render
    const content = document.getElementById('app-content');
    if (content) renderPipeline(content);
  } catch (err) {
    console.error('Pipeline stage update error:', err);
  }
}
