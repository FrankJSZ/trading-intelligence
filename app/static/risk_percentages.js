(() => {
  const originalRenderAnalysis = window.renderAnalysis;
  if (typeof originalRenderAnalysis !== 'function') return;

  const style = document.createElement('style');
  style.textContent = `
    .risk-price { display:block; }
    .risk-change {
      display:inline-flex;
      align-items:center;
      gap:4px;
      margin-top:6px;
      padding:3px 7px;
      border-radius:999px;
      font-size:11px;
      font-weight:800;
      line-height:1.35;
    }
    .risk-change.tp {
      color:#9df2c7;
      border:1px solid rgba(52,211,153,.30);
      background:rgba(52,211,153,.08);
    }
    .risk-change.sl {
      color:#ffb7c2;
      border:1px solid rgba(251,113,133,.30);
      background:rgba(251,113,133,.08);
    }
    .risk-change small {
      color:inherit;
      opacity:.82;
      font-size:10px;
      font-weight:700;
    }
  `;
  document.head.appendChild(style);

  function formatPercent(value) {
    if (value === null || value === undefined || Number.isNaN(Number(value))) return null;
    const number = Number(value);
    const sign = number > 0 ? '+' : '';
    return `${sign}${number.toLocaleString('es-CR', {minimumFractionDigits:2, maximumFractionDigits:2})}%`;
  }

  function enhanceCard(label, percent, kind) {
    const risk = document.getElementById('risk');
    if (!risk) return;
    const card = [...risk.querySelectorAll('.mini')].find(
      item => item.querySelector('.label')?.textContent?.trim() === label
    );
    if (!card) return;

    const value = card.querySelector('strong');
    if (!value || value.textContent.trim() === '—') return;

    const formatted = formatPercent(percent);
    if (!formatted) return;

    const price = value.textContent.trim();
    value.innerHTML = `<span class="risk-price">${price}</span><span class="risk-change ${kind}">${formatted} <small>desde entrada</small></span>`;
  }

  window.renderAnalysis = function renderAnalysisWithRiskPercentages(data) {
    originalRenderAnalysis(data);
    const risk = data?.risk || {};
    enhanceCard('Stop Loss', risk.stop_loss_percent, 'sl');
    enhanceCard('TP1', risk.take_profit_1_percent, 'tp');
    enhanceCard('TP2', risk.take_profit_2_percent, 'tp');
  };
})();
