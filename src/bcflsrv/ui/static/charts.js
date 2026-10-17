/**
 * Pure Canvas Chart Engine for BC-FL-SRV Research Platform
 * Zero external CDN dependencies - 100% offline & reproducible.
 * Includes High-DPI Crisp Rendering, ResizeObserver, Overflow Prevention,
 * Interactive Crosshair Tooltips, and Fullscreen/Expanded View Modal Support.
 */

class MiniChart {
  constructor(canvasId, options = {}) {
    this.canvas = document.getElementById(canvasId);
    if (!this.canvas) return;
    this.ctx = this.canvas.getContext('2d');
    this.options = {
      type: options.type || 'line', // 'line' | 'bar' | 'area'
      title: options.title || '',
      color: options.color || '#a777ff',
      fillColor: options.fillColor || 'rgba(177, 133, 255, 0.16)',
      secondaryColor: options.secondaryColor || '#f43f5e',
      labels: [],
      data: [],
      secondaryData: null,
      yMin: options.yMin !== undefined ? options.yMin : null,
      yMax: options.yMax !== undefined ? options.yMax : null,
      isPercentage: options.isPercentage || false,
      unit: options.unit || '',
      padding: { top: 28, right: 30, bottom: 38, left: 55 },
      ...options,
    };

    // Strict inline layout styling directly on DOM element to decouple canvas buffer from CSS layout
    this.canvas.style.position = 'absolute';
    this.canvas.style.top = '0';
    this.canvas.style.left = '0';
    this.canvas.style.width = '100%';
    this.canvas.style.height = '100%';
    this.canvas.style.maxWidth = '100%';
    this.canvas.style.maxHeight = '100%';
    this.canvas.style.display = 'block';
    this.canvas.style.boxSizing = 'border-box';

    const container = this.canvas.parentElement;
    if (container) {
      container.style.position = 'relative';
      container.style.overflow = 'hidden';
      container.style.width = '100%';
      container.style.maxWidth = '100%';
      container.style.boxSizing = 'border-box';
    }

    this.width = 0;
    this.height = 0;
    this.hoverIndex = -1;
    this.mousePos = null;

    this._setupDPI();
    this._initResizeObserver();
    this._initInteractivity();
  }

  _initResizeObserver() {
    if (!this.canvas) return;
    const parent = this.canvas.parentElement;
    if (!parent) return;

    if (!window.ResizeObserver) {
      window.addEventListener('resize', () => {
        this._setupDPI();
        this.render();
      });
      return;
    }

    this.resizeObserver = new ResizeObserver((entries) => {
      for (const entry of entries) {
        const cr = entry.contentRect;
        if (cr.width > 0 && cr.height > 0) {
          const newW = Math.floor(cr.width);
          const newH = Math.floor(cr.height);
          if (newW !== this.width || newH !== this.height) {
            this._setupDPI(newW, newH);
            this.render();
          }
        }
      }
    });
    this.resizeObserver.observe(parent);
  }

  _setupDPI(forceW = null, forceH = null) {
    if (!this.canvas) return;
    const container = this.canvas.parentElement;
    if (!container) return;

    const dpr = Math.max(1, Math.min(3, window.devicePixelRatio || 1));

    // Floor measured dimensions to completely eliminate fractional subpixel accumulation
    let w = forceW !== null ? forceW : (container.clientWidth || Math.floor(container.getBoundingClientRect().width));
    let h = forceH !== null ? forceH : (container.clientHeight || Math.floor(container.getBoundingClientRect().height));

    if (!w || w <= 0) w = this.width || 400;
    if (!h || h <= 0) h = this.height || 220;

    w = Math.floor(w);
    h = Math.floor(h);

    this.width = w;
    this.height = h;

    const targetPxW = Math.round(w * dpr);
    const targetPxH = Math.round(h * dpr);

    // Only update pixel buffer when dimensions actually change to prevent layout thrashing
    if (this.canvas.width !== targetPxW || this.canvas.height !== targetPxH) {
      this.canvas.width = targetPxW;
      this.canvas.height = targetPxH;
    }

    // Use setTransform which resets matrix and scales in one atomic, idempotent call
    this.ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    this.ctx.imageSmoothingEnabled = true;
    this.ctx.imageSmoothingQuality = 'high';
  }

  destroy() {
    if (this.resizeObserver) {
      this.resizeObserver.disconnect();
      this.resizeObserver = null;
    }
  }

  _initInteractivity() {
    if (!this.canvas) return;

    this.canvas.addEventListener('mousemove', (e) => {
      const rect = this.canvas.getBoundingClientRect();
      const mouseX = e.clientX - rect.left;
      const mouseY = e.clientY - rect.top;
      this.mousePos = { x: mouseX, y: mouseY };

      const { labels, data } = this.options;
      if (!data || data.length === 0) return;

      const p = this._calculateDynamicPadding();
      const plotW = this.width - p.left - p.right;
      if (mouseX < p.left || mouseX > p.left + plotW) {
        if (this.hoverIndex !== -1) {
          this.hoverIndex = -1;
          this.render();
        }
        return;
      }

      const xStep = plotW / Math.max(1, labels.length - (this.options.type === 'bar' ? 0 : 1));
      let closestIdx = 0;
      if (this.options.type === 'bar') {
        closestIdx = Math.floor((mouseX - p.left) / (plotW / labels.length));
      } else {
        closestIdx = Math.round((mouseX - p.left) / (xStep || 1));
      }
      closestIdx = Math.max(0, Math.min(data.length - 1, closestIdx));

      if (this.hoverIndex !== closestIdx) {
        this.hoverIndex = closestIdx;
        this.render();
      }
    });

    this.canvas.addEventListener('mouseleave', () => {
      if (this.hoverIndex !== -1) {
        this.hoverIndex = -1;
        this.mousePos = null;
        this.render();
      }
    });
  }

  _calculateDynamicPadding() {
    const p = { ...this.options.padding };
    const { data, secondaryData } = this.options;
    if (!data || data.length === 0) return p;

    let allVals = [...data];
    if (secondaryData && secondaryData.length) allVals.push(...secondaryData);
    let minVal = this.options.yMin !== null ? this.options.yMin : Math.min(...allVals);
    let maxVal = this.options.yMax !== null ? this.options.yMax : Math.max(...allVals);
    if (minVal === maxVal) {
      minVal -= 1;
      maxVal += 1;
    }
    const valRange = maxVal - minVal || 1;

    // Measure maximum tick text width
    let maxW = 0;
    this.ctx.font = '10.5px monospace';
    const ySteps = 4;
    for (let i = 0; i <= ySteps; i++) {
      const v = minVal + (valRange * i) / ySteps;
      let label = '';
      if (this.options.isPercentage) {
        label = `${(v * 100).toFixed(0)}%`;
      } else if (v >= 100) {
        label = v.toFixed(0);
      } else if (v >= 10) {
        label = v.toFixed(1);
      } else {
        label = v.toFixed(v < 1 ? 3 : 2);
      }
      const w = this.ctx.measureText(label).width;
      if (w > maxW) maxW = w;
    }

    p.left = Math.max(50, Math.ceil(maxW + 18));

    // Measure last label width to prevent overflow past right edge
    const lastLabel = this.options.labels[this.options.labels.length - 1] || '';
    const lastLabelW = this.ctx.measureText(lastLabel).width;
    p.right = Math.max(28, Math.ceil(lastLabelW / 2 + 14));

    return p;
  }

  update(labels, data, secondaryData = null) {
    this.options.labels = labels || [];
    this.options.data = data || [];
    this.options.secondaryData = secondaryData;
    // Only set up DPI if canvas dimensions have not been established yet
    if (!this.width || !this.height || this.canvas.width === 0) {
      this._setupDPI();
    }
    this.render();
  }

  render() {
    if (!this.ctx) return;
    const { width, height } = this;
    const ctx = this.ctx;
    const p = this._calculateDynamicPadding();
    const labels = this.options.labels;
    const data = this.options.data;
    const secData = this.options.secondaryData;

    ctx.clearRect(0, 0, width, height);

    if (!data || data.length === 0) {
      ctx.fillStyle = '#8e8e99';
      ctx.font = '600 13px "Montserrat", sans-serif';
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillText('Awaiting experiment data...', width / 2, height / 2);
      return;
    }

    const plotW = Math.max(10, width - p.left - p.right);
    const plotH = Math.max(10, height - p.top - p.bottom);

    // Determine Y range
    let allVals = [...data];
    if (secData && secData.length) allVals.push(...secData);
    let minVal = this.options.yMin !== null ? this.options.yMin : Math.min(...allVals);
    let maxVal = this.options.yMax !== null ? this.options.yMax : Math.max(...allVals);
    if (minVal === maxVal) {
      minVal -= 1;
      maxVal += 1;
    }
    const valRange = maxVal - minVal || 1;

    // Draw Subtle Grid & Y-Ticks
    ctx.strokeStyle = '#e6e6ed';
    ctx.lineWidth = 1;
    ctx.fillStyle = '#6e6e7d';
    ctx.font = '600 10.5px "Montserrat", monospace';
    ctx.textAlign = 'right';
    ctx.textBaseline = 'middle';

    const ySteps = 4;
    for (let i = 0; i <= ySteps; i++) {
      const v = minVal + (valRange * i) / ySteps;
      const y = Math.round(p.top + plotH - (i / ySteps) * plotH);

      ctx.beginPath();
      ctx.moveTo(p.left, y);
      ctx.lineTo(p.left + plotW, y);
      ctx.stroke();

      let label = '';
      if (this.options.isPercentage) {
        label = `${(v * 100).toFixed(0)}%`;
      } else if (v >= 100) {
        label = v.toFixed(0);
      } else if (v >= 10) {
        label = v.toFixed(1);
      } else {
        label = v.toFixed(v < 1 ? 3 : 2);
      }
      ctx.fillText(label, p.left - 8, y);
    }

    // Draw X-Ticks with Decimation to Prevent Overlapping / Overflow
    ctx.textAlign = 'center';
    ctx.textBaseline = 'top';
    ctx.font = '600 10.5px "Montserrat", sans-serif';
    const xStep = plotW / Math.max(1, labels.length - (this.options.type === 'bar' ? 0 : 1));

    const maxXTicks = Math.max(2, Math.floor(plotW / 55));
    const step = labels.length > maxXTicks ? Math.ceil(labels.length / maxXTicks) : 1;

    labels.forEach((lbl, i) => {
      if (i % step === 0 || i === labels.length - 1) {
        const x = this.options.type === 'bar'
          ? p.left + (i + 0.5) * (plotW / labels.length)
          : p.left + i * xStep;
        ctx.fillStyle = i === this.hoverIndex ? '#181820' : '#8e8e99';
        ctx.fillText(lbl, x, p.top + plotH + 8);
      }
    });

    const getY = (val) => p.top + plotH - ((val - minVal) / valRange) * plotH;

    // Set Clipping Path for Data Graphics
    ctx.save();
    ctx.beginPath();
    ctx.rect(p.left - 2, p.top - 2, plotW + 4, plotH + 4);
    ctx.clip();

    // Draw Data Series
    if (this.options.type === 'line' || this.options.type === 'area') {
      const getX = (i) => p.left + (labels.length === 1 ? plotW / 2 : i * xStep);

      // Area fill with smooth vertical gradient
      if (this.options.type === 'area' && data.length > 1) {
        const grad = ctx.createLinearGradient(0, p.top, 0, p.top + plotH);
        grad.addColorStop(0, this.options.fillColor || 'rgba(56, 189, 248, 0.35)');
        grad.addColorStop(1, 'rgba(56, 189, 248, 0.0)');

        ctx.beginPath();
        ctx.moveTo(getX(0), p.top + plotH);
        data.forEach((val, i) => ctx.lineTo(getX(i), getY(val)));
        ctx.lineTo(getX(data.length - 1), p.top + plotH);
        ctx.closePath();
        ctx.fillStyle = grad;
        ctx.fill();
      }

      // Main line
      ctx.beginPath();
      data.forEach((val, i) => {
        const x = getX(i);
        const y = getY(val);
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      });
      ctx.strokeStyle = this.options.color;
      ctx.lineWidth = 2.5;
      ctx.lineJoin = 'round';
      ctx.lineCap = 'round';
      ctx.stroke();

      // Points
      data.forEach((val, i) => {
        const x = getX(i);
        const y = getY(val);
        const isHovered = i === this.hoverIndex;

        ctx.beginPath();
        ctx.arc(x, y, isHovered ? 6 : 3.5, 0, Math.PI * 2);
        ctx.fillStyle = '#ffffff';
        ctx.fill();
        ctx.strokeStyle = this.options.color;
        ctx.lineWidth = isHovered ? 3.5 : 2;
        ctx.stroke();

        if (isHovered) {
          ctx.beginPath();
          ctx.arc(x, y, 9, 0, Math.PI * 2);
          ctx.strokeStyle = 'rgba(177, 133, 255, 0.4)';
          ctx.lineWidth = 2;
          ctx.stroke();
        }
      });

      // Secondary line (e.g. comparison or target)
      if (secData && secData.length) {
        ctx.beginPath();
        secData.forEach((val, i) => {
          const x = getX(i);
          const y = getY(val);
          if (i === 0) ctx.moveTo(x, y);
          else ctx.lineTo(x, y);
        });
        ctx.strokeStyle = this.options.secondaryColor;
        ctx.lineWidth = 1.8;
        ctx.setLineDash([4, 4]);
        ctx.stroke();
        ctx.setLineDash([]);
      }
    } else if (this.options.type === 'bar') {
      const barSlot = plotW / labels.length;
      const barW = Math.max(6, Math.min(36, barSlot * 0.6));

      data.forEach((val, i) => {
        const x = p.left + (i + 0.5) * barSlot - barW / 2;
        const y = getY(val);
        const barH = Math.max(2, p.top + plotH - y);
        const isHovered = i === this.hoverIndex;

        ctx.fillStyle = isHovered ? '#8142f5' : this.options.color;
        if (ctx.roundRect) {
          ctx.beginPath();
          ctx.roundRect(x, y, barW, barH, [Math.min(6, barW / 2), Math.min(6, barW / 2), 0, 0]);
          ctx.fill();
        } else {
          ctx.fillRect(x, y, barW, barH);
        }
      });
    }

    ctx.restore(); // Restore clipping path

    // Draw Crosshair & Tooltip if Hovered
    if (this.hoverIndex >= 0 && this.hoverIndex < data.length) {
      this._renderTooltip(p, plotW, plotH, minVal, valRange);
    }
  }

  _renderTooltip(p, plotW, plotH, minVal, valRange) {
    const ctx = this.ctx;
    const i = this.hoverIndex;
    const lbl = this.options.labels[i] || `Point ${i + 1}`;
    const val = this.options.data[i];
    const xStep = plotW / Math.max(1, this.options.labels.length - (this.options.type === 'bar' ? 0 : 1));

    const getX = (idx) => this.options.type === 'bar'
      ? p.left + (idx + 0.5) * (plotW / this.options.labels.length)
      : p.left + (this.options.labels.length === 1 ? plotW / 2 : idx * xStep);
    const getY = (v) => p.top + plotH - ((v - minVal) / valRange) * plotH;

    const ptX = getX(i);
    const ptY = getY(val);

    // Crosshair line
    ctx.beginPath();
    ctx.strokeStyle = 'rgba(255, 255, 255, 0.2)';
    ctx.lineWidth = 1;
    ctx.setLineDash([3, 3]);
    ctx.moveTo(ptX, p.top);
    ctx.lineTo(ptX, p.top + plotH);
    ctx.stroke();
    ctx.setLineDash([]);

    // Format value text
    let valText = '';
    if (this.options.isPercentage) {
      valText = `${(val * 100).toFixed(2)}%`;
    } else if (Number.isInteger(val)) {
      valText = `${val}`;
    } else {
      valText = `${val.toFixed(4)}`;
    }
    if (this.options.unit) valText += ` ${this.options.unit}`;

    // Tooltip box
    const tipTitle = `${lbl}`;
    const tipVal = `${this.options.title || 'Value'}: ${valText}`;
    ctx.font = 'bold 11px -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif';
    const w1 = ctx.measureText(tipTitle).width;
    ctx.font = '11px monospace';
    const w2 = ctx.measureText(tipVal).width;
    const tipW = Math.max(w1, w2) + 20;
    const tipH = 42;

    let tipX = ptX + 12;
    if (tipX + tipW > this.width - 10) tipX = ptX - tipW - 12;
    let tipY = ptY - tipH / 2;
    if (tipY < p.top) tipY = p.top;
    if (tipY + tipH > p.top + plotH) tipY = p.top + plotH - tipH;

    ctx.fillStyle = '#181820';
    ctx.strokeStyle = '#181820';
    ctx.lineWidth = 1;

    // Rounded rectangle tooltip
    ctx.beginPath();
    ctx.roundRect ? ctx.roundRect(tipX, tipY, tipW, tipH, 8) : ctx.rect(tipX, tipY, tipW, tipH);
    ctx.fill();
    ctx.stroke();

    ctx.fillStyle = '#ffffff';
    ctx.font = 'bold 11px "Montserrat", sans-serif';
    ctx.textAlign = 'left';
    ctx.textBaseline = 'top';
    ctx.fillText(tipTitle, tipX + 10, tipY + 6);

    ctx.fillStyle = '#cbb0ff';
    ctx.font = '600 11px monospace';
    ctx.fillText(tipVal, tipX + 10, tipY + 22);
  }

  exportImage(scale = 2) {
    if (!this.canvas) return;
    // Create an offscreen high-res canvas for crystal-clear export
    const exportCanvas = document.createElement('canvas');
    exportCanvas.width = this.width * scale;
    exportCanvas.height = this.height * scale;
    const expCtx = exportCanvas.getContext('2d');
    expCtx.scale(scale, scale);

    // Render cleanly onto offscreen canvas
    const tempChart = new MiniChart('dummy', { ...this.options });
    tempChart.canvas = exportCanvas;
    tempChart.ctx = expCtx;
    tempChart.width = this.width;
    tempChart.height = this.height;
    tempChart.hoverIndex = -1;
    tempChart.render();

    const link = document.createElement('a');
    link.download = `${(this.options.title || 'chart').toLowerCase().replace(/\s+/g, '_')}_hires.png`;
    link.href = exportCanvas.toDataURL('image/png');
    link.click();
  }
}

// Global modal expand helper for any chart
window.expandedChartInstance = null;

function expandChart(chartKey) {
  const chart = charts[chartKey];
  if (!chart) return;

  const modal = document.getElementById('chart-expand-modal');
  const titleEl = document.getElementById('chart-expand-title');
  const statsEl = document.getElementById('chart-expand-stats');
  if (!modal) return;

  titleEl.innerText = chart.options.title || 'Expanded Chart View';

  // Compute key metrics
  const data = chart.options.data || [];
  let statsHtml = '';
  if (data.length > 0) {
    const maxVal = Math.max(...data);
    const minVal = Math.min(...data);
    const latest = data[data.length - 1];
    const first = data[0];
    const diff = latest - first;
    const avg = data.reduce((a, b) => a + b, 0) / data.length;

    const fmt = (v) => chart.options.isPercentage ? `${(v * 100).toFixed(2)}%` : (Number.isInteger(v) ? v : v.toFixed(4));

    statsHtml = `
      <div style="display:flex; gap:16px; flex-wrap:wrap; margin-bottom:14px;">
        <div class="card kpi-card" style="padding:10px 14px; min-width:110px;">
          <span class="kpi-label">Peak Value</span>
          <span class="kpi-val" style="font-size:16px; color:var(--accent-emerald); font-weight:800;">${fmt(maxVal)}</span>
        </div>
        <div class="card kpi-card" style="padding:10px 14px; min-width:110px;">
          <span class="kpi-label">Minimum</span>
          <span class="kpi-val" style="font-size:16px; color:var(--accent-rose); font-weight:800;">${fmt(minVal)}</span>
        </div>
        <div class="card kpi-card" style="padding:10px 14px; min-width:110px;">
          <span class="kpi-label">Average</span>
          <span class="kpi-val" style="font-size:16px; color:var(--accent-cyan); font-weight:800;">${fmt(avg)}</span>
        </div>
        <div class="card kpi-card" style="padding:10px 14px; min-width:110px;">
          <span class="kpi-label">Latest</span>
          <span class="kpi-val" style="font-size:16px; color:var(--text-primary); font-weight:800;">${fmt(latest)}</span>
        </div>
        <div class="card kpi-card" style="padding:10px 14px; min-width:110px;">
          <span class="kpi-label">Net Change</span>
          <span class="kpi-val" style="font-size:16px; color:${diff >= 0 ? 'var(--accent-emerald)' : 'var(--accent-rose)'}; font-weight:800;">
            ${diff >= 0 ? '+' : ''}${fmt(diff)}
          </span>
        </div>
      </div>
    `;
  }
  statsEl.innerHTML = statsHtml;

  modal.classList.add('active');

  // Initialize or update the high-res modal canvas
  setTimeout(() => {
    if (!window.expandedChartInstance) {
      window.expandedChartInstance = new MiniChart('chart-expand-canvas', {
        type: chart.options.type,
        title: chart.options.title,
        color: chart.options.color,
        fillColor: chart.options.fillColor,
        isPercentage: chart.options.isPercentage,
        unit: chart.options.unit,
        padding: { top: 35, right: 35, bottom: 45, left: 60 },
      });
    } else {
      window.expandedChartInstance.options.type = chart.options.type;
      window.expandedChartInstance.options.title = chart.options.title;
      window.expandedChartInstance.options.color = chart.options.color;
      window.expandedChartInstance.options.fillColor = chart.options.fillColor;
      window.expandedChartInstance.options.isPercentage = chart.options.isPercentage;
      window.expandedChartInstance.options.unit = chart.options.unit;
    }
    window.expandedChartInstance.update(
      chart.options.labels,
      chart.options.data,
      chart.options.secondaryData
    );
  }, 50);
}

function closeExpandModal() {
  const modal = document.getElementById('chart-expand-modal');
  if (modal) modal.classList.remove('active');
}
