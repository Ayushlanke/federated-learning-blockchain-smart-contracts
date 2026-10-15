/**
 * BC-FL-SRV Research Platform - Main Frontend Application Logic
 */

let charts = {};
let activeTab = 'dashboard';
let pollInterval = null;
let selectedSampleIndex = 0;
let cachedSamples = [];
let cachedClientTransparency = null;
let cachedUploads = [];
let currentExpandedChart = null;

document.addEventListener('DOMContentLoaded', () => {
  initNavigation();
  initCharts();
  initControls();
  initInference();
  initSecurityTests();
  initResearchPage();

  // Initial load & polling
  refreshAll();
  pollInterval = setInterval(refreshState, 1500);

  // Close modals on overlay backdrop click
  document.querySelectorAll('.modal-overlay').forEach(overlay => {
    overlay.addEventListener('click', (e) => {
      if (e.target === overlay) {
        overlay.classList.remove('active');
        if (overlay.id === 'chart-expand-modal') closeExpandModal();
      }
    });
  });
});

// ── Navigation ─────────────────────────────────────────────────────────────
function initNavigation() {
  const navItems = document.querySelectorAll('.nav-item');
  navItems.forEach(item => {
    item.addEventListener('click', () => {
      navItems.forEach(i => i.classList.remove('active'));
      item.classList.add('active');

      const target = item.getAttribute('data-tab');
      document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
      const activePage = document.getElementById(`page-${target}`);
      if (activePage) activePage.classList.add('active');

      activeTab = target;
      document.getElementById('top-page-title').innerText = item.querySelector('span:last-child').innerText;

      // Force sharp canvas resize/re-render when switching tabs
      window.requestAnimationFrame(() => {
        Object.values(charts).forEach(c => {
          if (c && typeof c.render === 'function') c.render();
        });
      });

      // Tab specific refresh
      if (target === 'dashboard') loadBlockchainUploads();
      if (target === 'model') loadModelSection();
      if (target === 'clients') loadClients();
      if (target === 'blockchain') loadBlockchain();
      if (target === 'experiments') loadExperiments();
      if (target === 'logs') loadLogs();
    });
  });
}

// ── Charts Initialization ──────────────────────────────────────────────────
function initCharts() {
  charts.accuracy = new MiniChart('chart-accuracy', {
    type: 'line',
    title: 'Accuracy vs FL Round',
    color: '#38bdf8',
    fillColor: 'rgba(56, 189, 248, 0.15)',
    yMin: 0,
    yMax: 1.0,
    unit: '%',
    isPercentage: true,
  });

  charts.loss = new MiniChart('chart-loss', {
    type: 'line',
    title: 'Loss vs FL Round',
    color: '#f59e0b',
    fillColor: 'rgba(245, 158, 11, 0.15)',
    yMin: 0,
    unit: '',
  });

  charts.participation = new MiniChart('chart-participation', {
    type: 'bar',
    title: 'Accepted Updates per Round',
    color: '#10b981',
    unit: ' clients',
    isInteger: true,
  });

  charts.blockchain = new MiniChart('chart-blockchain', {
    type: 'area',
    title: 'Cumulative Blocks Committed',
    color: '#6366f1',
    fillColor: 'rgba(99, 102, 241, 0.2)',
    unit: ' blocks',
    isInteger: true,
  });

  charts.trainingTime = new MiniChart('chart-time', {
    type: 'bar',
    title: 'Training Time per Round (s)',
    color: '#a855f7',
    unit: 's',
  });
}

// ── Refresh State ──────────────────────────────────────────────────────────
async function refreshState() {
  try {
    const res = await fetch('/api/dashboard');
    if (!res.ok) return;
    const d = await res.json();
    updateDashboardKPIs(d);

    // Refresh charts if experiment is running or in dashboard
    if (activeTab === 'dashboard' || activeTab === 'training') {
      const cRes = await fetch('/api/charts');
      if (cRes.ok) {
        const c = await cRes.json();
        updateChartsData(c);
      }
    }

    if (activeTab === 'dashboard') {
      loadBlockchainUploads();
    }
    if (activeTab === 'training') {
      updateTrainingProgress(d);
    }
    if (activeTab === 'logs') {
      loadLogs();
    }
  } catch (err) {
    console.error('State poll failed', err);
  }
}

async function refreshAll() {
  await refreshState();
  loadClients();
  loadBlockchain();
  loadBlockchainUploads();
  loadModelSection();
  loadExperiments();
  loadLogs();
}

function updateDashboardKPIs(d) {
  document.getElementById('kpi-round').innerText = `${d.current_round} / ${d.total_rounds}`;
  document.getElementById('kpi-clients').innerText = `${d.active_clients} / ${d.total_clients}`;
  document.getElementById('kpi-accuracy').innerText = `${(d.current_accuracy * 100).toFixed(1)}%`;
  document.getElementById('kpi-loss').innerText = d.current_loss.toFixed(4);
  document.getElementById('kpi-blocks').innerText = d.blocks_count;
  document.getElementById('kpi-updates').innerText = `${d.accepted_updates} acc / ${d.rejected_updates} rej`;

  // Status dot & text
  const statusDot = document.getElementById('global-status-dot');
  const statusText = document.getElementById('global-status-text');
  statusDot.className = `status-dot ${d.status}`;
  statusText.innerText = d.status.toUpperCase();

  // Header badges
  const headerStatus = document.getElementById('header-status-badge');
  if (headerStatus) {
    headerStatus.className = `badge ${d.status === 'running' ? 'badge-info' : (d.status === 'completed' ? 'badge-success' : 'badge-neutral')}`;
    headerStatus.innerText = d.status.toUpperCase();
  }
}

function updateChartsData(c) {
  charts.accuracy.update(c.rounds, c.accuracy);
  charts.loss.update(c.rounds, c.loss);
  charts.participation.update(c.rounds, c.accepted);
  charts.blockchain.update(c.rounds, c.cum_blocks);
  if (charts.trainingTime) charts.trainingTime.update(c.rounds, c.times);
}

// ── FL Clients Page & Weights Transparency ─────────────────────────────────
async function loadClients() {
  try {
    const res = await fetch('/api/clients/transparency');
    if (!res.ok) return;
    const data = await res.json();
    cachedClientTransparency = data;
    const clients = data.clients || [];

    // 1. Overview Table
    const tbody = document.getElementById('clients-table-body');
    if (tbody) {
      tbody.innerHTML = '';
      clients.forEach((c, idx) => {
        const tr = document.createElement('tr');
        tr.style.cursor = 'pointer';
        tr.onclick = () => showClientWeightsModal(c.client_id);

        const statusBadge = c.status === 'accepted' ? 'badge-success'
          : (c.status === 'rejected' ? 'badge-danger'
          : (c.status === 'training' ? 'badge-info' : 'badge-neutral'));

        const cosSim = c.cosine_similarity !== undefined && c.cosine_similarity !== null ? c.cosine_similarity : 1.0;
        const alignClass = cosSim >= 0.75 ? 'align-high' : (cosSim >= 0.45 ? 'align-med' : 'align-divergent');

        tr.innerHTML = `
          <td><strong>#${idx + 1}</strong></td>
          <td><span class="mono" title="${c.client_id}">${c.short_id}</span></td>
          <td><span class="mono" title="${c.public_key_hex}">${c.short_pk}</span></td>
          <td>${c.sample_count.toLocaleString()}</td>
          <td><span class="badge ${statusBadge}">${c.status.toUpperCase()}</span></td>
          <td>${c.local_loss ? c.local_loss.toFixed(4) : '—'}</td>
          <td><strong>${c.weight_norm ? c.weight_norm.toFixed(4) : '0.0000'}</strong></td>
          <td><span class="align-pill ${alignClass}">cos(θ)=${cosSim.toFixed(3)}</span></td>
          <td><span class="mono" title="${c.commitment_hex || c.update_hash}">${(c.commitment_hex || c.update_hash || '—').slice(0, 16)}...</span></td>
          <td><button class="btn btn-secondary btn-sm" onclick="event.stopPropagation(); showClientWeightsModal('${c.client_id}')">🔬 Inspect</button></td>
        `;
        tbody.appendChild(tr);
      });
    }

    // 2. Weights & Gradient Delta Transparency Grid
    const grid = document.getElementById('clients-weights-grid');
    if (grid) {
      grid.innerHTML = '';
      clients.forEach(c => {
        const layers = c.layer_norms || {};
        const layerEntries = Object.entries(layers);
        const maxNorm = Math.max(...Object.values(layers), 0.001);

        let layerBars = '';
        layerEntries.forEach(([lName, val]) => {
          const pct = Math.min(100, Math.max(3, Math.round((val / maxNorm) * 100)));
          layerBars += `
            <div style="margin-bottom:6px;">
              <div style="display:flex; justify-content:space-between; font-size:11px; margin-bottom:2px;">
                <span class="mono" style="color:#94a3b8;">${lName}</span>
                <span class="mono" style="color:#38bdf8;">||w|| = ${val.toFixed(4)}</span>
              </div>
              <div class="progress-container" style="height:4px; background:#0f172a;">
                <div class="progress-bar" style="width:${pct}%; background:#38bdf8;"></div>
              </div>
            </div>
          `;
        });

        const cosSim = c.cosine_similarity !== undefined && c.cosine_similarity !== null ? c.cosine_similarity : 1.0;
        const alignClass = cosSim >= 0.75 ? 'align-high' : (cosSim >= 0.45 ? 'align-med' : 'align-divergent');
        const statusBadge = c.status === 'accepted' ? 'badge-success'
          : (c.status === 'rejected' ? 'badge-danger'
          : (c.status === 'training' ? 'badge-info' : 'badge-neutral'));

        const card = document.createElement('div');
        card.className = 'client-weight-card';
        card.innerHTML = `
          <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:10px;">
            <strong style="color:#f8fafc; font-size:14px;">${c.short_id}</strong>
            <span class="badge ${statusBadge}">${c.status.toUpperCase()}</span>
          </div>

          <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:10px;">
            <span class="align-pill ${alignClass}">Alignment: cos(θ)=${cosSim.toFixed(3)}</span>
            <span style="font-size:12px; color:#cbd5e1;">||Δw||: <strong style="color:#38bdf8;">${c.weight_norm ? c.weight_norm.toFixed(4) : '0.0000'}</strong></span>
          </div>

          <div style="font-size:11px; color:#94a3b8; display:grid; grid-template-columns:1fr 1fr; gap:6px; margin-bottom:12px; background:#070a10; padding:8px; border-radius:6px; border:1px solid #1e293b;">
            <div>Min: <span class="mono" style="color:#f1f5f9;">${c.weight_stats?.min !== undefined ? c.weight_stats.min.toFixed(4) : '—'}</span></div>
            <div>Max: <span class="mono" style="color:#f1f5f9;">${c.weight_stats?.max !== undefined ? c.weight_stats.max.toFixed(4) : '—'}</span></div>
            <div>Mean: <span class="mono" style="color:#f1f5f9;">${c.weight_stats?.mean !== undefined ? c.weight_stats.mean.toFixed(5) : '—'}</span></div>
            <div>Std: <span class="mono" style="color:#f1f5f9;">${c.weight_stats?.std !== undefined ? c.weight_stats.std.toFixed(4) : '—'}</span></div>
          </div>

          <div class="layer-breakdown" style="background:#070a10; padding:10px; border-radius:6px; border:1px solid #1e293b;">
            <div style="font-size:11px; font-weight:600; color:#cbd5e1; text-transform:uppercase; letter-spacing:0.5px; margin-bottom:8px;">
              Layer Parameter Norms (L2)
            </div>
            ${layerBars || '<div style="color:#64748b; font-size:12px;">No layer updates recorded yet</div>'}
          </div>

          <div style="margin-top:12px; display:flex; justify-content:space-between; align-items:center;">
            <span style="font-size:11.5px; color:#94a3b8;">${c.sample_count} Non-IID samples</span>
            <button class="btn btn-secondary btn-sm" onclick="showClientWeightsModal('${c.client_id}')">🔬 Deep Inspect</button>
          </div>
        `;
        grid.appendChild(card);
      });
    }

    // 3. Populate Client Selector for Logs
    const sel = document.getElementById('select-client-log');
    if (sel && sel.options.length <= 1) {
      clients.forEach(c => {
        const opt = document.createElement('option');
        opt.value = c.client_id;
        opt.innerText = `${c.short_id} (${c.sample_count} samples)`;
        sel.appendChild(opt);
      });
    }

    // 4. Render client training activity logs
    renderFilteredClientLogs();

  } catch (err) {
    console.error('Failed to load clients transparency', err);
  }
}

function renderFilteredClientLogs() {
  const terminal = document.getElementById('client-logs-terminal');
  if (!terminal) return;

  const sel = document.getElementById('select-client-log');
  const selectedCid = sel ? sel.value : 'all';

  if (!cachedClientTransparency || !cachedClientTransparency.logs) {
    terminal.innerHTML = '<div style="padding:12px; color:#64748b;">No client training activity logs available.</div>';
    return;
  }

  const logsObj = cachedClientTransparency.logs;
  let allLogs = [];

  if (selectedCid === 'all') {
    Object.keys(logsObj).forEach(cid => {
      (logsObj[cid] || []).forEach(entry => {
        allLogs.push({ cid, ...entry });
      });
    });
  } else {
    (logsObj[selectedCid] || []).forEach(entry => {
      allLogs.push({ cid: selectedCid, ...entry });
    });
  }

  // Sort by timestamp or round
  allLogs.sort((a, b) => (a.round - b.round) || (a.timestamp > b.timestamp ? 1 : -1));

  terminal.innerHTML = '';
  if (allLogs.length === 0) {
    terminal.innerHTML = '<div style="padding:12px; color:#64748b;">No logs recorded for the selected filter.</div>';
    return;
  }

  allLogs.forEach(l => {
    const row = document.createElement('div');
    row.className = 'log-entry';
    const shortCid = l.cid ? l.cid.slice(0, 14) + '...' : 'Client';
    const statusClass = l.accepted ? 'log-info' : (l.accepted === false ? 'log-error' : '');
    row.innerHTML = `
      <span class="log-time">[${l.timestamp}]</span>
      <span class="log-cat mono" style="color:#38bdf8;">[${shortCid}]</span>
      <span class="log-msg ${statusClass}">Round ${l.round}: loss=${l.loss !== undefined ? Number(l.loss).toFixed(4) : '—'} ||Δw||=${l.weight_norm !== undefined ? Number(l.weight_norm).toFixed(4) : '—'} [Commitment: ${l.commitment_hex ? l.commitment_hex.slice(0, 16) + '...' : 'none'}] [Sig: ${l.signature_valid ? '✓ Verified' : '✗ Failed'}]</span>
    `;
    terminal.appendChild(row);
  });
  terminal.scrollTop = terminal.scrollHeight;
}

function showClientWeightsModal(clientId) {
  if (!cachedClientTransparency || !cachedClientTransparency.clients) return;
  const client = cachedClientTransparency.clients.find(c => c.client_id === clientId);
  if (!client) return;

  const modal = document.getElementById('weights-modal');
  const title = document.getElementById('weights-modal-title');
  const body = document.getElementById('weights-modal-body');
  if (!modal || !title || !body) return;

  title.innerText = `Client Deep Transparency: ${client.short_id}`;

  const classNames = [
    "T-shirt/top", "Trouser", "Pullover", "Dress", "Coat",
    "Sandal", "Shirt", "Sneaker", "Bag", "Ankle boot"
  ];

  let distHtml = '<div style="display:grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap:8px; margin-top:8px;">';
  client.class_distribution.forEach((cnt, idx) => {
    const pct = ((cnt / client.sample_count) * 100).toFixed(1);
    distHtml += `
      <div style="background:#070a10; padding:6px 10px; border-radius:4px; border:1px solid #1e293b;">
        <div style="display:flex; justify-content:space-between; font-size:11px; margin-bottom:2px;">
          <span style="color:#cbd5e1;">${classNames[idx]}</span>
          <span style="color:#38bdf8;"><strong>${cnt}</strong> (${pct}%)</span>
        </div>
        <div class="progress-container" style="height:3px;">
          <div class="progress-bar" style="width:${pct}%; background:#38bdf8;"></div>
        </div>
      </div>
    `;
  });
  distHtml += '</div>';

  const layers = client.layer_norms || {};
  let layerTableRows = '';
  Object.entries(layers).forEach(([lName, norm]) => {
    layerTableRows += `
      <tr>
        <td class="mono" style="color:#f8fafc;">${lName}</td>
        <td><strong class="mono" style="color:#38bdf8;">${norm.toFixed(5)}</strong></td>
        <td><span class="badge badge-success">VALIDATED</span></td>
      </tr>
    `;
  });

  const cosSim = client.cosine_similarity !== undefined && client.cosine_similarity !== null ? client.cosine_similarity : 1.0;
  const alignClass = cosSim >= 0.75 ? 'align-high' : (cosSim >= 0.45 ? 'align-med' : 'align-divergent');

  body.innerHTML = `
    <div style="font-size:13px; line-height:1.7;">
      <!-- Key Identity Banner -->
      <div style="display:grid; grid-template-columns:1fr 1fr; gap:12px; margin-bottom:16px;">
        <div style="background:#070a10; padding:12px; border-radius:6px; border:1px solid #1e293b;">
          <div style="font-size:11px; text-transform:uppercase; color:#94a3b8; margin-bottom:4px;">Client Identity & Keypair</div>
          <p style="margin:2px 0;"><strong>Client ID:</strong> <span class="mono">${client.client_id}</span></p>
          <p style="margin:2px 0;"><strong>Ed25519 Public Key:</strong><br><span class="mono" style="word-break:break-all; font-size:11.5px; color:#38bdf8;">${client.public_key_hex}</span></p>
          <p style="margin:2px 0;"><strong>Signature Status:</strong> ${client.signature_valid ? '<span class="badge badge-success">ED25519 VERIFIED ✓</span>' : '<span class="badge badge-danger">SIGNATURE INVALID ✗</span>'}</p>
        </div>
        <div style="background:#070a10; padding:12px; border-radius:6px; border:1px solid #1e293b;">
          <div style="font-size:11px; text-transform:uppercase; color:#94a3b8; margin-bottom:4px;">Training & Convergence Metrics</div>
          <p style="margin:2px 0;"><strong>Dataset Samples:</strong> ${client.sample_count.toLocaleString()} (Dirichlet Non-IID)</p>
          <p style="margin:2px 0;"><strong>Local Loss:</strong> ${client.local_loss ? client.local_loss.toFixed(4) : '—'}</p>
          <p style="margin:2px 0;"><strong>Gradient Update L2 Norm:</strong> <strong class="mono" style="color:#38bdf8;">${client.weight_norm ? client.weight_norm.toFixed(4) : '0.0000'}</strong></p>
          <p style="margin:2px 0;"><strong>Consensus Alignment:</strong> <span class="align-pill ${alignClass}">cos(θ)=${cosSim.toFixed(4)}</span></p>
        </div>
      </div>

      <!-- Weight Statistics Grid -->
      <div style="background:#070a10; padding:12px; border-radius:6px; border:1px solid #1e293b; margin-bottom:16px;">
        <div style="font-size:11px; text-transform:uppercase; color:#94a3b8; margin-bottom:8px;">Global Parameter Weight Distribution Statistics</div>
        <div style="display:grid; grid-template-columns: repeat(4, 1fr); gap:8px; text-align:center;">
          <div style="background:#0a0e17; padding:8px; border-radius:4px;">
            <div style="font-size:11px; color:#94a3b8;">Min Value</div>
            <div class="mono" style="font-size:13px; color:#f8fafc; font-weight:600;">${client.weight_stats?.min !== undefined ? client.weight_stats.min.toFixed(5) : '—'}</div>
          </div>
          <div style="background:#0a0e17; padding:8px; border-radius:4px;">
            <div style="font-size:11px; color:#94a3b8;">Max Value</div>
            <div class="mono" style="font-size:13px; color:#f8fafc; font-weight:600;">${client.weight_stats?.max !== undefined ? client.weight_stats.max.toFixed(5) : '—'}</div>
          </div>
          <div style="background:#0a0e17; padding:8px; border-radius:4px;">
            <div style="font-size:11px; color:#94a3b8;">Mean</div>
            <div class="mono" style="font-size:13px; color:#f8fafc; font-weight:600;">${client.weight_stats?.mean !== undefined ? client.weight_stats.mean.toFixed(6) : '—'}</div>
          </div>
          <div style="background:#0a0e17; padding:8px; border-radius:4px;">
            <div style="font-size:11px; color:#94a3b8;">Std Dev</div>
            <div class="mono" style="font-size:13px; color:#f8fafc; font-weight:600;">${client.weight_stats?.std !== undefined ? client.weight_stats.std.toFixed(5) : '—'}</div>
          </div>
        </div>
      </div>

      <!-- Layer Breakdown Table -->
      <div style="margin-bottom:16px;">
        <div style="font-size:11px; text-transform:uppercase; color:#94a3b8; margin-bottom:6px;">Layer-by-Layer Gradient Norm Breakdown</div>
        <div class="table-responsive">
          <table>
            <thead>
              <tr>
                <th>Layer Name</th>
                <th>Weight L2 Norm (||w||)</th>
                <th>Consensus State</th>
              </tr>
            </thead>
            <tbody>
              ${layerTableRows || '<tr><td colspan="3" style="text-align:center; color:#64748b;">No layer weights available</td></tr>'}
            </tbody>
          </table>
        </div>
      </div>

      <!-- Non-IID Class Label Shard Distribution -->
      <div style="margin-bottom:16px;">
        <div style="font-size:11px; text-transform:uppercase; color:#94a3b8; margin-bottom:6px;">Local Non-IID Class Label Distribution (Fashion-MNIST)</div>
        ${distHtml}
      </div>

      <!-- Cryptographic Proof Commitments -->
      <div style="background:#070a10; padding:12px; border-radius:6px; border:1px solid #1e293b;">
        <div style="font-size:11px; text-transform:uppercase; color:#94a3b8; margin-bottom:6px;">Cryptographic Proof & Signature Commitment</div>
        <p style="margin:4px 0;"><strong>Domain Separated Commitment (SHA-256):</strong><br><span class="mono" style="word-break:break-all; font-size:11px; color:#38bdf8;">${client.commitment_hex || client.update_hash || '—'}</span></p>
        <p style="margin:4px 0;"><strong>Ed25519 Digital Signature:</strong><br><span class="mono" style="word-break:break-all; font-size:11px; color:#94a3b8;">${client.signature_hex || '—'}</span></p>
      </div>
    </div>
  `;

  modal.classList.add('active');
}

function showClientDetailModal(client) {
  showClientWeightsModal(client.client_id);
}

// ── Training Control & Live Monitor ────────────────────────────────────────
function initControls() {
  document.getElementById('btn-start-exp')?.addEventListener('click', async () => {
    const clients = parseInt(document.getElementById('input-clients').value, 10);
    const rounds = parseInt(document.getElementById('input-rounds').value, 10);
    const alpha = parseFloat(document.getElementById('input-alpha').value);
    const epochs = parseInt(document.getElementById('input-epochs').value, 10);
    const lr = parseFloat(document.getElementById('input-lr').value);
    const nodes = parseInt(document.getElementById('input-nodes').value, 10);
    const quorum = parseInt(document.getElementById('input-quorum').value, 10);
    const seed = parseInt(document.getElementById('input-seed').value, 10);

    try {
      const res = await fetch('/api/experiment/start', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          n_clients: clients,
          n_rounds: rounds,
          dirichlet_alpha: alpha,
          epochs: epochs,
          learning_rate: lr,
          n_ledger_nodes: nodes,
          ledger_quorum: quorum,
          seed: seed,
        }),
      });
      if (res.ok) {
        refreshState();
      } else {
        const err = await res.json();
        alert(`Error: ${err.detail || 'Could not start experiment'}`);
      }
    } catch (e) {
      alert(`Network error: ${e}`);
    }
  });

  document.getElementById('btn-pause-exp')?.addEventListener('click', async () => {
    await fetch('/api/experiment/pause', { method: 'POST' });
    refreshState();
  });

  document.getElementById('btn-resume-exp')?.addEventListener('click', async () => {
    await fetch('/api/experiment/resume', { method: 'POST' });
    refreshState();
  });

  document.getElementById('btn-stop-exp')?.addEventListener('click', async () => {
    await fetch('/api/experiment/stop', { method: 'POST' });
    refreshState();
  });

  document.getElementById('btn-reset-exp')?.addEventListener('click', async () => {
    await fetch('/api/experiment/reset', { method: 'POST' });
    refreshState();
  });

  // Verify chain button
  // Verify chain button
  document.getElementById('btn-verify-chain')?.addEventListener('click', async () => {
    const btn = document.getElementById('btn-verify-chain');
    if (btn) btn.disabled = true;
    try {
      const res = await fetch('/api/blockchain/verify', { method: 'POST' });
      if (res.ok) {
        const result = await res.json();
        const statusEl = document.getElementById('bc-kpi-status');
        if (statusEl) {
          statusEl.innerText = result.valid ? 'VALID ✓ (ALL NODES)' : 'FAILED ✗';
          statusEl.style.color = result.valid ? '#34d399' : '#fb7185';
        }
        showChainVerificationResult(result);
      }
    } catch (e) {
      console.error('Verify failed', e);
    } finally {
      if (btn) btn.disabled = false;
    }
  });
}

function updateTrainingProgress(d) {
  const stageEl = document.getElementById('training-stage-text');
  const progBar = document.getElementById('training-main-progress');
  const roundEl = document.getElementById('training-current-round');

  if (stageEl) stageEl.innerText = d.stage;
  if (roundEl) roundEl.innerText = `Round ${d.current_round} / ${d.total_rounds}`;

  if (progBar && d.total_rounds > 0) {
    const pct = Math.min(100, Math.round((d.current_round / d.total_rounds) * 100));
    progBar.style.width = `${pct}%`;
  }
}

// ── Blockchain Explorer ────────────────────────────────────────────────────
async function loadBlockchain() {
  try {
    const res = await fetch('/api/blockchain');
    if (!res.ok) return;
    const blocks = await res.json();
    const container = document.getElementById('blockchain-blocks-list');
    if (!container) return;

    // 1. Populate Explorer KPI Bar
    const kpiBlocks = document.getElementById('bc-kpi-blocks');
    const kpiUploads = document.getElementById('bc-kpi-uploads');
    const kpiRounds = document.getElementById('bc-kpi-rounds');
    const kpiStatus = document.getElementById('bc-kpi-status');

    if (kpiBlocks) kpiBlocks.innerText = blocks.length;

    let totalUploads = 0;
    let maxRound = 0;
    blocks.forEach(b => {
      if (b.fl_round > maxRound) maxRound = b.fl_round;
      if (b.accepted_count) totalUploads += b.accepted_count;
    });

    if (kpiUploads) kpiUploads.innerText = totalUploads > 0 ? totalUploads : (cachedUploads ? cachedUploads.length : '—');
    if (kpiRounds) kpiRounds.innerText = `${maxRound} Rounds`;
    if (kpiStatus && kpiStatus.innerText === 'UNVERIFIED' && blocks.length > 0) {
      kpiStatus.innerText = 'ONLINE (3 Nodes)';
      kpiStatus.style.color = '#38bdf8';
    }

    // 2. Render Modern Chain Blocks
    container.innerHTML = '';
    if (blocks.length === 0) {
      container.innerHTML = `
        <div class="card" style="text-align:center; padding:40px; color:#64748b;">
          <div style="font-size:32px; margin-bottom:10px;">⛓</div>
          <div style="font-size:14px; font-weight:600; color:#94a3b8;">No blocks committed to ledger yet</div>
          <div style="font-size:12px; margin-top:4px;">Start an FL experiment to record immutable cryptographically chained round transactions.</div>
        </div>
      `;
      return;
    }

    const timeline = document.createElement('div');
    timeline.className = 'chain-timeline';

    const eventConfig = {
      ROUND_START: { badge: 'badge-info', label: 'ROUND START', icon: '🔵', desc: 'Global model weights distributed to registered FL clients' },
      UPDATE_SUBMIT: { badge: 'badge-success', label: 'UPDATE SUBMIT', icon: '⚡', desc: 'Client local model updates committed with Ed25519 signatures' },
      AGGREGATION: { badge: 'badge-warning', label: 'FEDAVG AGGREGATION', icon: '⚖', desc: 'Secure parameter aggregation co-signed by quorum ledger nodes' },
      ROUND_END: { badge: 'badge-neutral', label: 'ROUND EVALUATION', icon: '🏁', desc: 'Global test accuracy and loss validated across non-IID test set' },
      TAMPERING_DETECTED: { badge: 'badge-danger', label: 'SECURITY ALERT', icon: '🚨', desc: 'Cryptographic hash mismatch or signature verification failure' },
    };

    blocks.forEach((b, idx) => {
      const card = document.createElement('div');
      card.className = 'block-card';

      const cfg = eventConfig[b.event_type] || { badge: 'badge-neutral', label: b.event_type, icon: '📦', desc: 'Ledger transaction event' };
      const isGenesis = b.index === 0;

      let metricsHtml = '';
      if (b.event_type === 'UPDATE_SUBMIT') {
        metricsHtml = `
          <div style="display:flex; gap:16px; font-size:12px; background:rgba(16, 185, 129, 0.08); padding:8px 12px; border-radius:6px; margin-top:10px; border:1px solid rgba(16, 185, 129, 0.2);">
            <div><span style="color:#94a3b8;">Verified Updates:</span> <strong style="color:#34d399;">${b.accepted_count}</strong></div>
            <div><span style="color:#94a3b8;">Consensus:</span> <strong style="color:#34d399;">2/3 Quorum Passed ✓</strong></div>
          </div>
        `;
      } else if (b.event_type === 'AGGREGATION' && b.aggregation_commitment) {
        metricsHtml = `
          <div style="display:flex; gap:16px; font-size:12px; background:rgba(245, 158, 11, 0.08); padding:8px 12px; border-radius:6px; margin-top:10px; border:1px solid rgba(245, 158, 11, 0.2);">
            <div style="overflow:hidden; text-overflow:ellipsis; white-space:nowrap;">
              <span style="color:#94a3b8;">Aggregated Model SHA-256:</span>
              <span class="mono" style="color:#fbbf24;">${b.aggregation_commitment.slice(0, 24)}...</span>
            </div>
          </div>
        `;
      } else if (b.event_type === 'ROUND_END' && b.global_model_accuracy !== null) {
        metricsHtml = `
          <div style="display:flex; gap:20px; font-size:12px; background:rgba(56, 189, 248, 0.08); padding:8px 12px; border-radius:6px; margin-top:10px; border:1px solid rgba(56, 189, 248, 0.2);">
            <div><span style="color:#94a3b8;">Global Accuracy:</span> <strong style="color:#38bdf8; font-size:13px;">${(b.global_model_accuracy * 100).toFixed(2)}%</strong></div>
            <div><span style="color:#94a3b8;">Global Loss:</span> <strong style="color:#f8fafc;">${b.global_model_loss.toFixed(4)}</strong></div>
            <div><span style="color:#94a3b8;">Ledger Quorum:</span> <span style="color:#34d399;">Multi-node Signed ✓</span></div>
          </div>
        `;
      }

      card.innerHTML = `
        <div class="block-card-header">
          <div style="display:flex; align-items:center; gap:10px;">
            <span class="block-idx-badge">Block #${b.index}</span>
            <span class="badge ${cfg.badge}">${cfg.icon} ${cfg.label}</span>
            ${isGenesis ? '<span class="badge" style="background:rgba(99, 102, 241, 0.25); color:#a5b4fc; border:1px solid rgba(99, 102, 241, 0.4);">GENESIS</span>' : ''}
          </div>
          <div style="font-size:12px; color:#94a3b8; display:flex; align-items:center; gap:12px;">
            <span>FL Round: <strong style="color:#f8fafc;">${b.fl_round}</strong></span>
            <span>🕒 ${b.timestamp}</span>
          </div>
        </div>

        <p style="font-size:12.5px; color:#cbd5e1; margin-bottom:10px;">${cfg.desc}</p>

        <div style="display:flex; flex-wrap:wrap; gap:12px; align-items:center;">
          <div class="hash-box" title="${b.block_hash}">
            <span class="hash-label">Block Hash:</span>
            <span>${b.short_hash}</span>
            <button class="copy-btn" onclick="event.stopPropagation(); navigator.clipboard.writeText('${b.block_hash}'); this.innerText='✓'; setTimeout(()=>this.innerText='📋', 1200);" title="Copy Full Hash">📋</button>
          </div>
          <div class="hash-box" title="${b.prev_hash}">
            <span class="hash-label">Prev Hash:</span>
            <span>${isGenesis ? '00000000... (Root)' : b.short_prev_hash}</span>
          </div>
          <button class="btn btn-secondary btn-sm" style="margin-left:auto;" onclick="showBlockModal(${JSON.stringify(b).replace(/"/g, '&quot;')})">
            🔬 View Payload JSON
          </button>
        </div>

        ${metricsHtml}
      `;

      timeline.appendChild(card);
    });

    container.appendChild(timeline);
  } catch (err) {
    console.error('Failed to load blockchain', err);
  }
}

function showBlockModal(block) {
  const modal = document.getElementById('client-modal');
  const title = document.getElementById('client-modal-title');
  const content = document.getElementById('client-modal-body');

  title.innerText = `Ledger Block #${block.index} [${block.event_type}]`;

  let clientTable = '';
  if (block.update_commitments && Object.keys(block.update_commitments).length > 0) {
    let rows = '';
    Object.entries(block.update_commitments).forEach(([cid, commit], i) => {
      const ver = block.verification_results?.[cid] || 'accepted';
      rows += `
        <tr>
          <td><strong>Client #${i + 1}</strong></td>
          <td><span class="mono" style="color:#38bdf8;">${cid.slice(0, 16)}...</span></td>
          <td><span class="mono" style="color:#cbd5e1;">${commit.slice(0, 20)}...</span></td>
          <td><span class="badge ${ver === 'accepted' ? 'badge-success' : 'badge-danger'}">${ver.toUpperCase()}</span></td>
        </tr>
      `;
    });
    clientTable = `
      <div style="margin-top:16px;">
        <h4 style="font-size:13px; margin-bottom:8px; color:#f8fafc;">Committed Client Updates & Quorum Verification:</h4>
        <div class="table-responsive">
          <table>
            <thead><tr><th>Index</th><th>Client ID</th><th>SHA-256 Commitment</th><th>Quorum Status</th></tr></thead>
            <tbody>${rows}</tbody>
          </table>
        </div>
      </div>
    `;
  }

  content.innerHTML = `
    <div style="font-size:13px; line-height:1.7;">
      <div style="display:flex; justify-content:space-between; align-items:center; padding:10px 14px; background:rgba(30, 41, 59, 0.4); border-radius:6px; margin-bottom:14px; border:1px solid rgba(148, 163, 184, 0.1);">
        <div>
          <span style="color:#94a3b8;">Block Index:</span> <strong style="color:#f8fafc; font-size:15px;">#${block.index}</strong>
          <span class="badge badge-info" style="margin-left:10px;">${block.event_type}</span>
        </div>
        <div>
          <span style="color:#94a3b8;">Round:</span> <strong>${block.fl_round}</strong> · 🕒 ${block.timestamp}
        </div>
      </div>

      <p><strong>Full Block Hash (SHA-256):</strong><br><span class="mono" style="word-break:break-all; color:#38bdf8; background:#05070d; padding:4px 8px; border-radius:4px; display:inline-block; margin-top:2px;">${block.block_hash}</span></p>
      <p style="margin-top:8px;"><strong>Previous Block Hash (prev_hash):</strong><br><span class="mono" style="word-break:break-all; color:#94a3b8; background:#05070d; padding:4px 8px; border-radius:4px; display:inline-block; margin-top:2px;">${block.prev_hash}</span></p>

      ${block.aggregation_commitment ? `<p style="margin-top:8px;"><strong>Global Model Parameters Commitment (SHA-256):</strong><br><span class="mono" style="word-break:break-all; color:#fbbf24; background:#05070d; padding:4px 8px; border-radius:4px; display:inline-block; margin-top:2px;">${block.aggregation_commitment}</span></p>` : ''}
      ${block.global_model_accuracy !== null ? `<p style="margin-top:8px;"><strong>Evaluated Test Accuracy:</strong> <span style="color:#34d399; font-weight:700;">${(block.global_model_accuracy * 100).toFixed(2)}%</span> &nbsp;|&nbsp; <strong>Loss:</strong> ${block.global_model_loss.toFixed(4)}</p>` : ''}

      ${clientTable}

      <div style="margin-top:16px;">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
          <strong style="color:#f8fafc;">Raw Block JSON Payload:</strong>
          <button class="btn btn-secondary btn-sm" onclick="navigator.clipboard.writeText(JSON.stringify(window._currentBlockModalData, null, 2)); this.innerText='Copied!'; setTimeout(()=>this.innerText='Copy JSON', 1200);">Copy JSON</button>
        </div>
        <pre class="terminal" style="height:190px; font-size:11px; margin:0;">${JSON.stringify(block, null, 2)}</pre>
      </div>
    </div>
  `;

  window._currentBlockModalData = block;
  modal.classList.add('active');
}

function showChainVerificationResult(res) {
  const modal = document.getElementById('client-modal');
  const title = document.getElementById('client-modal-title');
  const content = document.getElementById('client-modal-body');

  title.innerText = 'Distributed Blockchain Verification Report';

  let nodesHtml = '';
  res.nodes.forEach(n => {
    nodesHtml += `
      <div style="display:flex; justify-content:space-between; padding:8px 12px; background:#0a0e17; border-radius:6px; margin-bottom:6px; font-size:12px;">
        <span><strong>${n.node_id}</strong></span>
        <span>${n.valid ? '<span class="badge badge-success">VALID ✓</span>' : '<span class="badge badge-danger">FAILED ✗</span>'}</span>
      </div>
    `;
  });

  content.innerHTML = `
    <div>
      <div style="text-align:center; margin-bottom:16px;">
        <span class="badge ${res.valid ? 'badge-success' : 'badge-danger'}" style="font-size:14px; padding:6px 16px;">
          ${res.valid ? 'ALL NODES VERIFIED & IN HARMONY ✓' : 'CHAIN INTEGRITY VIOLATION DETECTED ✗'}
        </span>
      </div>
      <p style="font-size:13px; margin-bottom:12px;">
        Cryptographic verification walked all <strong>${res.total_blocks} blocks</strong> across <strong>${res.node_count} independent simulated ledger nodes</strong>.
        Every hash link (<code>prev_hash</code>) and internal block SHA-256 payload was computed and verified from scratch.
      </p>
      <strong>Node Integrity Status:</strong>
      <div style="margin-top:8px;">${nodesHtml}</div>
    </div>
  `;

  modal.classList.add('active');
}

// ── Blockchain Model Uploads (Transactions) ────────────────────────────────
async function loadBlockchainUploads() {
  try {
    const res = await fetch('/api/blockchain/uploads');
    if (!res.ok) return;
    const uploads = await res.json();
    cachedUploads = uploads;

    // 1. Populate Dashboard feed (latest 6 uploads)
    const dashTbody = document.getElementById('dashboard-uploads-table-body');
    if (dashTbody) {
      dashTbody.innerHTML = '';
      if (uploads.length === 0) {
        dashTbody.innerHTML = '<tr><td colspan="8" style="text-align:center; color:#64748b; padding:16px;">No model uploads committed yet.</td></tr>';
      } else {
        const recent = uploads.slice(-6).reverse();
        recent.forEach(u => {
          const tr = document.createElement('tr');
          const statusBadge = u.accepted ? 'badge-success' : 'badge-danger';
          tr.innerHTML = `
            <td><span class="mono" style="color:#38bdf8;">${u.tx_id}</span></td>
            <td><strong>Round ${u.fl_round}</strong></td>
            <td><span class="mono">#${u.block_index}</span></td>
            <td><span class="mono" title="${u.client_id}">${u.short_client_id}</span></td>
            <td>${u.payload_size_kb} KB (${u.param_count.toLocaleString()} params)</td>
            <td><span class="mono" title="${u.commitment}">${u.short_commitment}</span></td>
            <td><span class="badge ${statusBadge}">${u.status.toUpperCase()}</span></td>
            <td><span style="color:#34d399; font-size:11.5px;">✓ ${u.consensus}</span></td>
          `;
          dashTbody.appendChild(tr);
        });
      }
    }

    // 2. Populate Blockchain Explorer Uploads Table
    const bcTbody = document.getElementById('blockchain-uploads-table-body');
    if (bcTbody) {
      bcTbody.innerHTML = '';
      if (uploads.length === 0) {
        bcTbody.innerHTML = '<tr><td colspan="9" style="text-align:center; color:#64748b; padding:16px;">No client model weight uploads committed to ledger yet.</td></tr>';
      } else {
        uploads.slice().reverse().forEach(u => {
          const tr = document.createElement('tr');
          const statusBadge = u.accepted ? 'badge-success' : 'badge-danger';
          tr.innerHTML = `
            <td><span class="mono" style="color:#38bdf8;">${u.tx_id}</span></td>
            <td><strong>Round ${u.fl_round}</strong></td>
            <td><span class="mono">Block #${u.block_index}</span></td>
            <td><span class="mono" title="${u.client_id}">${u.short_client_id}</span></td>
            <td><span class="mono" title="${u.public_key_hex}">${u.short_pk}</span></td>
            <td>${u.payload_size_kb} KB</td>
            <td><span class="mono" title="${u.commitment}">${u.short_commitment}</span></td>
            <td><span class="badge ${statusBadge}">${u.status.toUpperCase()}</span></td>
            <td><span style="color:#34d399; font-size:11.5px;">✓ ${u.consensus}</span></td>
          `;
          bcTbody.appendChild(tr);
        });
      }
    }
  } catch (err) {
    console.error('Failed to load blockchain uploads', err);
  }
}

function switchBlockchainView(view) {
  const pillBlocks = document.getElementById('pill-all-blocks');
  const pillUploads = document.getElementById('pill-uploads');
  const blocksList = document.getElementById('blockchain-blocks-list');
  const uploadsCont = document.getElementById('blockchain-uploads-container');

  if (view === 'blocks') {
    pillBlocks?.classList.add('active');
    pillUploads?.classList.remove('active');
    if (blocksList) blocksList.style.display = 'block';
    if (uploadsCont) uploadsCont.style.display = 'none';
    loadBlockchain();
  } else {
    pillUploads?.classList.add('active');
    pillBlocks?.classList.remove('active');
    if (blocksList) blocksList.style.display = 'none';
    if (uploadsCont) uploadsCont.style.display = 'block';
    loadBlockchainUploads();
  }
}

// Chart expansion and modal view logic is centrally managed in charts.js (expandChart, closeExpandModal)

// ── Model & Live Inference ─────────────────────────────────────────────────
async function loadModelSection() {
  try {
    const res = await fetch('/api/model');
    if (!res.ok) return;
    const m = await res.json();

    document.getElementById('model-arch').innerText = m.architecture;
    document.getElementById('model-params-count').innerText = m.parameter_count.toLocaleString();
    document.getElementById('model-hash').innerText = m.current_model_hash;
    document.getElementById('model-rounds-trained').innerText = m.trained_rounds;
    document.getElementById('model-acc').innerText = `${(m.accuracy * 100).toFixed(2)}%`;
    document.getElementById('model-loss').innerText = m.loss.toFixed(4);

    // Load sample gallery
    await loadTestSamples();

    // Load Confusion Matrix
    loadConfusionMatrix();
  } catch (err) {
    console.error('Failed to load model info', err);
  }
}

async function loadTestSamples() {
  try {
    const res = await fetch('/api/model/samples?count=12');
    if (!res.ok) return;
    cachedSamples = await res.json();
    const container = document.getElementById('samples-gallery');
    if (!container) return;

    container.innerHTML = '';
    cachedSamples.forEach((sample, idx) => {
      const card = document.createElement('div');
      card.className = `sample-card ${idx === selectedSampleIndex ? 'selected' : ''}`;
      card.onclick = () => selectSample(idx);

      const canvas = document.createElement('canvas');
      canvas.width = 28;
      canvas.height = 28;
      canvas.className = 'sample-canvas';
      draw28x28(canvas, sample.pixels);

      card.appendChild(canvas);
      const lbl = document.createElement('div');
      lbl.className = 'sample-label';
      lbl.innerText = sample.true_label_name;
      card.appendChild(lbl);

      container.appendChild(card);
    });

    if (cachedSamples.length > 0) {
      runSampleInference(cachedSamples[selectedSampleIndex].index);
    }
  } catch (err) {
    console.error('Failed to load samples', err);
  }
}

function draw28x28(canvas, pixels) {
  const ctx = canvas.getContext('2d');
  const imgData = ctx.createImageData(28, 28);
  for (let r = 0; r < 28; r++) {
    for (let c = 0; c < 28; c++) {
      const val = pixels[r][c];
      const i = (r * 28 + c) * 4;
      imgData.data[i] = val;
      imgData.data[i + 1] = val;
      imgData.data[i + 2] = val;
      imgData.data[i + 3] = 255;
    }
  }
  ctx.putImageData(imgData, 0, 0);
}

function selectSample(idx) {
  selectedSampleIndex = idx;
  document.querySelectorAll('.sample-card').forEach((c, i) => {
    c.classList.toggle('selected', i === idx);
  });
  if (cachedSamples[idx]) {
    runSampleInference(cachedSamples[idx].index);
  }
}

async function runSampleInference(sampleIdx) {
  try {
    const res = await fetch('/api/model/inference', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ sample_index: sampleIdx }),
    });
    if (!res.ok) return;
    const inf = await res.json();

    document.getElementById('inf-true-label').innerText = inf.true_label_name;
    document.getElementById('inf-pred-label').innerText = inf.predicted_label_name;
    document.getElementById('inf-conf').innerText = `${(inf.confidence * 100).toFixed(1)}%`;

    const matchBadge = document.getElementById('inf-match-badge');
    if (matchBadge) {
      matchBadge.className = `badge ${inf.correct ? 'badge-success' : 'badge-danger'}`;
      matchBadge.innerText = inf.correct ? 'CORRECT PREDICTION ✓' : 'MISCLASSIFICATION ✗';
    }

    // Probability breakdown
    const probContainer = document.getElementById('inf-prob-bars');
    if (probContainer) {
      probContainer.innerHTML = '';
      inf.probabilities.slice(0, 5).forEach(p => {
        const row = document.createElement('div');
        row.style.marginBottom = '6px';
        row.innerHTML = `
          <div style="display:flex; justify-content:space-between; font-size:11.5px; margin-bottom:2px;">
            <span>${p.class_name}</span>
            <span><strong>${(p.probability * 100).toFixed(1)}%</strong></span>
          </div>
          <div class="progress-container" style="height:6px;">
            <div class="progress-bar" style="width:${p.probability * 100}%; background:${p.class_name === inf.predicted_label_name ? '#38bdf8' : '#64748b'};"></div>
          </div>
        `;
        probContainer.appendChild(row);
      });
    }
  } catch (err) {
    console.error('Inference error', err);
  }
}

async function loadConfusionMatrix() {
  try {
    const res = await fetch('/api/model/confusion_matrix');
    if (!res.ok) return;
    const data = await res.json();
    const container = document.getElementById('confusion-matrix-container');
    if (!container) return;

    let html = '<table class="cm-table"><thead><tr><th></th>';
    data.classes.forEach(c => html += `<th title="${c}">${c.substring(0, 3)}</th>`);
    html += '</tr></thead><tbody>';

    data.matrix.forEach((row, i) => {
      html += `<tr><th title="${data.classes[i]}">${data.classes[i].substring(0, 3)}</th>`;
      row.forEach((val, j) => {
        const isDiag = i === j;
        html += `<td class="${isDiag ? 'cm-diag' : ''}">${val}</td>`;
      });
      html += '</tr>';
    });
    html += '</tbody></table>';
    container.innerHTML = html;
  } catch (err) {
    console.error('CM load error', err);
  }
}

function initInference() {
  document.getElementById('btn-manual-infer')?.addEventListener('click', () => {
    const inputVal = parseInt(document.getElementById('input-sample-idx').value, 10);
    if (!isNaN(inputVal) && inputVal >= 0 && inputVal < 10000) {
      runSampleInference(inputVal);
    }
  });
}

// ── Security Attack Tests ──────────────────────────────────────────────────
function initSecurityTests() {
  const attacks = [
    { id: 'btn-attack-tamper', type: 'tampered_update' },
    { id: 'btn-attack-forgery', type: 'forged_commitment' },
    { id: 'btn-attack-unauth', type: 'unauthorized_client' },
    { id: 'btn-attack-block', type: 'block_tampering' },
  ];

  attacks.forEach(att => {
    document.getElementById(att.id)?.addEventListener('click', async () => {
      try {
        const res = await fetch('/api/security/test', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ attack_type: att.type }),
        });
        if (res.ok) {
          const result = await res.json();
          showSecurityAttackModal(result);
        }
      } catch (err) {
        alert(`Attack test error: ${err}`);
      }
    });
  });
}

function showSecurityAttackModal(res) {
  const modal = document.getElementById('client-modal');
  const title = document.getElementById('client-modal-title');
  const content = document.getElementById('client-modal-body');

  title.innerText = `Security Attack Test: ${res.name}`;

  content.innerHTML = `
    <div style="font-size:13px; line-height:1.7;">
      <div style="text-align:center; margin-bottom:14px;">
        <span class="badge ${res.defense_successful ? 'badge-success' : 'badge-danger'}" style="font-size:14px; padding:6px 16px;">
          ${res.defense_successful ? 'ATTACK CAUGHT & REJECTED ✓' : 'DEFENSE BREACHED ✗'}
        </span>
      </div>
      <p><strong>Scenario:</strong> ${res.description}</p>
      <p><strong>Defense Layer:</strong> <span style="color:#38bdf8;">${res.defense_layer}</span></p>
      <p><strong>Verification Status Code:</strong> <span class="badge badge-danger">${res.verification_status || 'tamper_detected'}</span></p>
      ${res.detail ? `<p><strong>Verification Detail:</strong> ${res.detail}</p>` : ''}

      ${res.original_commitment ? `
        <div style="margin-top:12px; padding:10px; background:#0a0e17; border-radius:6px;">
          <p><strong>Original Valid Commitment (SHA-256):</strong><br><span class="mono" style="word-break:break-all;">${res.original_commitment}</span></p>
          <p style="margin-top:6px;"><strong>Attacker's Tampered Commitment:</strong><br><span class="mono" style="color:#fb7185; word-break:break-all;">${res.tampered_commitment}</span></p>
        </div>
      ` : ''}

      <div style="margin-top:14px; padding:10px; background:rgba(56, 189, 248, 0.08); border-left:3px solid #38bdf8; font-size:12px;">
        <strong>Cryptographic Guarantee:</strong> Because the commitment binds the parameter bytes, client ID, and round number under domain separation, any modification to either the parameters or commitment causes an immediate hash or signature verification mismatch.
      </div>
    </div>
  `;

  modal.classList.add('active');
}

// ── Experiments Benchmark ──────────────────────────────────────────────────
async function loadExperiments() {
  try {
    const res = await fetch('/api/experiments');
    if (!res.ok) return;
    const exps = await res.json();
    const tbody = document.getElementById('experiments-table-body');
    if (!tbody) return;

    tbody.innerHTML = '';
    exps.forEach(e => {
      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td><strong>${e.id}</strong></td>
        <td>${e.timestamp || 'Initial'}</td>
        <td>${e.n_clients} clients</td>
        <td>${e.n_rounds} rounds</td>
        <td>α=${e.dirichlet_alpha}</td>
        <td><strong style="color:#38bdf8;">${(e.final_accuracy * 100).toFixed(2)}%</strong></td>
        <td>${e.final_loss ? e.final_loss.toFixed(4) : '—'}</td>
        <td>${e.blockchain_blocks} blocks</td>
        <td><span class="badge ${e.chain_integrity_ok ? 'badge-success' : 'badge-danger'}">${e.chain_integrity_ok ? 'Verified ✓' : 'Error'}</span></td>
      `;
      tbody.appendChild(tr);
    });
  } catch (err) {
    console.error('Failed to load experiments', err);
  }
}

// ── Live Logs ──────────────────────────────────────────────────────────────
let cachedLogs = [];
let activeLogCategory = 'all';

async function loadLogs() {
  try {
    const res = await fetch('/api/experiment/logs');
    if (!res.ok) return;
    const logs = await res.json();
    cachedLogs = logs || [];
    renderLogs();
  } catch (err) {
    console.error('Failed to load logs', err);
  }
}

function renderLogs() {
  const searchTerm = (document.getElementById('log-search-input')?.value || '').toLowerCase().trim();

  let filtered = cachedLogs.filter(l => {
    if (activeLogCategory !== 'all' && (l.category || 'system').toLowerCase() !== activeLogCategory.toLowerCase()) {
      return false;
    }
    if (searchTerm) {
      const line = `${l.timestamp} ${l.level} ${l.category} ${l.message} ${l.round}`.toLowerCase();
      if (!line.includes(searchTerm)) return false;
    }
    return true;
  });

  const LEVEL_BADGES = {
    SUCCESS: 'badge-success',
    ERROR: 'badge-danger',
    WARN: 'badge-warning',
    WARNING: 'badge-warning',
    INFO: 'badge-info',
    SECURITY: 'badge-danger',
    DEBUG: 'badge-neutral',
  };

  const LEVEL_COLORS = {
    SUCCESS: '#34d399',
    ERROR: '#fb7185',
    WARN: '#fbbf24',
    WARNING: '#fbbf24',
    INFO: '#e2e8f0',
    SECURITY: '#f43f5e',
    DEBUG: '#64748b',
  };

  function buildRows(targetEl, isMini = false) {
    if (!targetEl) return;
    targetEl.innerHTML = '';
    const displayLogs = isMini ? cachedLogs.slice(-30) : filtered;

    if (!displayLogs || displayLogs.length === 0) {
      targetEl.innerHTML = `
        <div style="display:flex; flex-direction:column; align-items:center; justify-content:center; height:100%; color:#475569;">
          <div style="font-size:28px; margin-bottom:8px;">📋</div>
          <div style="font-size:13px; font-weight:600; color:#64748b;">No log entries match your filter</div>
          <div style="font-size:11.5px; margin-top:4px; color:#475569;">${cachedLogs.length === 0 ? 'Start an experiment to stream real-time logs here.' : 'Try selecting \"All Events\" or clearing your search query.'}</div>
        </div>
      `;
      return;
    }

    displayLogs.forEach(l => {
      const row = document.createElement('div');
      row.className = 'log-entry';
      const badgeCls = LEVEL_BADGES[l.level] || 'badge-neutral';
      const color = LEVEL_COLORS[l.level] || '#cbd5e1';
      const cat = (l.category || 'SYS').toUpperCase();

      row.innerHTML = `
        <span class="log-time" style="color:#64748b; font-size:11px; flex-shrink:0;">${l.timestamp}</span>
        <span class="badge ${badgeCls}" style="font-size:10px; padding:1px 6px; flex-shrink:0;">${l.level}</span>
        <span class="log-cat" style="color:#818cf8; font-size:11px; flex-shrink:0; width:85px;">[${cat}]</span>
        <span class="mono" style="color:#38bdf8; font-size:11px; flex-shrink:0; margin-right:4px;">R${l.round}:</span>
        <span class="log-msg" style="color:${color}; font-size:12px;">${l.message}</span>
      `;
      targetEl.appendChild(row);
    });

    targetEl.scrollTop = targetEl.scrollHeight;
  }

  buildRows(document.getElementById('live-terminal'), true);
  buildRows(document.getElementById('live-terminal-full'), false);
}

function filterLogs() {
  renderLogs();
}

function setLogCategoryFilter(category) {
  activeLogCategory = category;
  ['all', 'security', 'blockchain', 'training', 'system'].forEach(c => {
    const el = document.getElementById(`log-filter-${c}`);
    if (el) {
      if (c === category) el.classList.add('active');
      else el.classList.remove('active');
    }
  });
  renderLogs();
}

function clearLogsView() {
  const full = document.getElementById('live-terminal-full');
  if (full) {
    full.innerHTML = '<div style="color:#64748b; padding:12px; font-style:italic;">Terminal view cleared. Click ⟳ Refresh Logs to reload.</div>';
  }
}


// ── Research Page ──────────────────────────────────────────────────────────
async function initResearchPage() {
  try {
    const res = await fetch('/api/research');
    if (!res.ok) return;
    const d = await res.json();
    const container = document.getElementById('research-exp-cards');
    if (!container) return;

    container.innerHTML = '';
    d.experiments.forEach(e => {
      const card = document.createElement('div');
      card.className = 'card';
      card.style.marginBottom = '14px';

      let findingsHtml = '<ul style="margin-left:18px; margin-top:8px; font-size:12.5px; color:#cbd5e1;">';
      e.key_findings.forEach(f => findingsHtml += `<li style="margin-bottom:4px;">${f}</li>`);
      findingsHtml += '</ul>';

      card.innerHTML = `
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
          <h4 style="color:#38bdf8; font-size:15px;">${e.id} — ${e.name}</h4>
          <span class="badge badge-info">EVALUATION</span>
        </div>
        <p style="font-size:13px; color:#94a3b8;">${e.description}</p>
        ${findingsHtml}
      `;
      container.appendChild(card);
    });
  } catch (err) {
    console.error('Failed to load research info', err);
  }
}

// Global window exports for HTML events
window.closeModal = function() {
  document.getElementById('client-modal')?.classList.remove('active');
};

window.closeExpandModal = function() {
  closeExpandModal();
};

window.closeWeightsModal = function() {
  document.getElementById('weights-modal')?.classList.remove('active');
};

window.expandChart = expandChart;
window.switchBlockchainView = switchBlockchainView;
window.showClientWeightsModal = showClientWeightsModal;
window.renderFilteredClientLogs = renderFilteredClientLogs;
window.loadBlockchainUploads = loadBlockchainUploads;
window.loadClients = loadClients;
window.loadLogs = loadLogs;
window.filterLogs = filterLogs;
window.setLogCategoryFilter = setLogCategoryFilter;
window.clearLogsView = clearLogsView;
window.refreshAll = refreshAll;
