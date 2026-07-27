let stocks = [];

const badgeMeta = {
  LIQ: { label: "LİKİDİTE", icon: "◆", className: "badge-liquidity" },
  FVG: { label: "FVG", icon: "ϟ", className: "badge-fvg" },
  MSS: { label: "MSS", icon: "↻", className: "badge-mss" },
  OB: { label: "OB TEPKİ", icon: "▰", className: "badge-ob" },
  CLIMAX: { label: "EMİLİM", icon: "▣", className: "badge-climax" },
  "EMA5-8-13": { label: "EMA 5-8-13", icon: "↗", className: "badge-ema" },
  VCP: { label: "VCP", icon: "◌", className: "badge-vcp" },
  TOBO: { label: "TOBO KIRILIM", icon: "📈", className: "badge-tobo" },
  "OBO-RİSK": { label: "OBO RİSK", icon: "⚠️", className: "badge-obo" }
};

const state = {
  selectedTicker: "",
  strategy: "Tümü",
  minimumPosition: 0,
  smcOnly: false,
  consensusOnly: false,
  recommendationFilter: "ALL",
  query: "",
  sortKey: "positionScore",
  sortDirection: "desc",
  chartRange: "1H",
  portfolio: [],
  watchlist: []
};

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>'"]/g, (char) => ({"&":"&amp;","<":"&lt;",">":"&gt;","'":"&#39;","\"":"&quot;"}[char]));
}

let marketPayload = null;
const backtestCache = new Map();
let backtestRequestSequence = 0;

const tableBody = document.getElementById("signalTableBody");
const tableSummary = document.getElementById("tableSummary");
const masterRange = document.getElementById("masterRange");
const masterRangeValue = document.getElementById("masterRangeValue");
const smcOnly = document.getElementById("smcOnly");
const consensusOnly = document.getElementById("consensusOnly");
const globalSearch = document.getElementById("globalSearch");
const filterDrawer = document.getElementById("filterDrawer");
const filterButton = document.getElementById("filterButton");
const activeFilterCount = document.getElementById("activeFilterCount");
const portfolioModal = document.getElementById("portfolioModal");
const capitalInput = document.getElementById("capitalInput");
const toast = document.getElementById("toast");

function formatNumber(value, digits = 2) {
  if (value === null || value === undefined || !Number.isFinite(Number(value))) return "—";
  return new Intl.NumberFormat("tr-TR", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits
  }).format(value);
}

function formatCurrency(value) {
  return `₺${formatNumber(value)}`;
}

function entryDistance(stock) {
  return ((stock.price - stock.entry) / stock.entry) * 100;
}

function average(values) {
  const validValues = values.filter((value) => Number.isFinite(Number(value)));
  return validValues.length
    ? validValues.reduce((total, value) => total + Number(value), 0) / validValues.length
    : 0;
}

function smcConfluence(stock) {
  const points = { LIQ: 22, FVG: 16, MSS: 26, OB: 16, CLIMAX: 22 };
  const raw = stock.badges.reduce((total, badge) => total + (points[badge] || 0), 0);
  const confluenceBonus = Math.max(0, stock.badges.length - 1) * 5;
  return Math.min(100, raw + confluenceBonus);
}

function rrQuality(rr) {
  if (rr < 1) return Math.max(0, rr * 45);
  if (rr < 1.5) return 60 + ((rr - 1) / 0.5) * 20;
  if (rr <= 3) return 80 + ((rr - 1.5) / 1.5) * 20;
  return 92;
}

function entryFreshness(stock) {
  const gain = entryDistance(stock);
  let score;
  if (gain < -2) score = 52;
  else if (gain < 0) score = 75;
  else if (gain <= 2.5) score = 100;
  else if (gain <= 5) score = 88;
  else if (gain <= 7.5) score = 70;
  else score = 45;

  if (stock.daily > 4) score -= 8;
  if (stock.warning) score = Math.min(score, 25);
  return Math.max(0, score);
}

function stopSafety(stock) {
  const distance = ((stock.price - stock.stop) / stock.price) * 100;
  let score;
  if (distance <= 0) score = 0;
  else if (distance < 1.5) score = 20;
  else if (distance < 3) score = 70;
  else if (distance <= 8) score = 100;
  else if (distance <= 12) score = 80;
  else score = 55;

  if (stock.protected) score = Math.max(score, 92);
  return score;
}

function positionAnalysis(stock) {
  if (stock.modelAnalysis) {
    return stock.modelAnalysis;
  }

  const technical = average([stock.sentiment, stock.momentum, stock.structure, stock.volume, stock.support]);
  const smc = smcConfluence(stock);
  const rr = rrQuality(stock.rr);
  const entry = entryFreshness(stock);
  const stop = stopSafety(stock);

  let score =
    technical * 0.62 +
    entry * 0.22 +
    stop * 0.10 +
    smc * 0.06;

  if (stock.warning) score -= 6;
  score = Math.max(0, Math.min(100, score));

  let grade = "C";
  let verdict = "Zayıf / Riskli";
  if (score >= 82) {
    grade = "A+";
    verdict = "Güçlü Aday";
  } else if (score >= 75) {
    grade = "A";
    verdict = "Olumlu Aday";
  } else if (score >= 66) {
    grade = "B";
    verdict = "Yakın İzle";
  } else if (score >= 58) {
    grade = "C+";
    verdict = "Teyit Bekle";
  }

  const completeness = 90 - (stock.badges.length === 0 ? 8 : 0) - (stock.warning ? 11 : 0);
  const confidence = Math.max(55, Math.min(92, Math.round(completeness)));

  return {
    score,
    grade,
    verdict,
    confidence,
    technical,
    financial: null,
    smc,
    rr,
    entry,
    stop
  };
}

function positionScore(stock) {
  return positionAnalysis(stock).score;
}

function modelConfidence(stock) {
  return Number(positionAnalysis(stock).confidence) || 0;
}

function confidenceMarkup(stock) {
  const confidence = modelConfidence(stock);
  const level = confidence >= 82 ? "high" : confidence >= 68 ? "medium" : "low";
  const label = confidence >= 82 ? "Yüksek" : confidence >= 68 ? "Orta" : "Düşük";
  const dailyClass = stock.daily >= 0 ? "positive" : "negative";
  const dailySign = stock.daily >= 0 ? "+" : "";
  return `
    <div style="display: flex; align-items: center; gap: 6px; justify-content: center;">
      <span class="confidence-pill ${level}" title="Model güveni: teknik veri bütünlüğü, giriş zamanlaması ve stop yapısının uyumu">%${formatNumber(confidence, 0)} <small>${label}</small></span>
      <span class="${dailyClass}" style="font-size: 10px; font-weight: 700; white-space: nowrap;">${dailySign}${formatNumber(stock.daily)}%</span>
    </div>
  `;
}

function rankedStocks() {
  const priority = { OPEN: 0, WATCH: 1, AVOID: 2 };
  return [...stocks].sort((a, b) => {
    const recommendationDifference = (priority[a.recommendation] ?? 1) - (priority[b.recommendation] ?? 1);
    return recommendationDifference || positionScore(b) - positionScore(a);
  });
}

function scoreClass(score) {
  if (score >= 70) return "score-strong";
  if (score >= 40) return "score-balanced";
  return "score-weak";
}

function scorePill(score) {
  if (score === null || score === undefined) {
    return `<span class="score-pill score-unavailable" title="Doğrulanmış KAP/temel veri bağlı değil">—</span>`;
  }
  return `<span class="score-pill ${scoreClass(score)}">${score}</span>`;
}

function badgesMarkup(badges, compact = true) {
  return (badges || []).map((badge) => {
    if (badge.startsWith("🔥 ÇAO") || badge.startsWith("🚀 SK")) {
      const className = compact ? "micro-badge" : "smc-badge";
      const isSK = badge.startsWith("🚀 SK");
      const badgeClass = isSK ? "badge-super-consensus" : "badge-double-algo";
      const icon = isSK ? "🚀" : "🔥";
      const cleanLabel = badge.replace(/^[🔥🚀]\s*/, "");
      return `<span class="${className} ${badgeClass}">${icon} ${cleanLabel}</span>`;
    }
    const meta = badgeMeta[badge] || { label: badge, icon: "•", className: "badge-generic" };
    const className = compact ? "micro-badge" : "smc-badge";
    return `<span class="${className} ${meta.className}">${meta.icon} ${meta.label}</span>`;
  }).join("");
}

function strategyColor(strategy) {
  const colors = {
    "Dipten Dönüş": "#56d8e7",
    "Derin Dönüş": "#a98cff",
    "Uzun Vade": "#6699ff",
    "Momentum": "#f2b95b",
    "CRSI Scalp": "#ec85b8",
    "Chartist MM Trend": "#28d7a1",
    "Momentum Kırılımı": "#f2b95b",
    "Money Dip": "#d9b44a",
    "Chartist Trender": "#27d997",
    "İzleme": "#81928e",
    "Wyckoff Spring": "#f26f73"
  };
  return colors[strategy] || "#28d7a1";
}

function strategyMarkup(stock) {
  return `<span class="strategy-pill"><i style="background:${strategyColor(stock.strategy)}"></i>${stock.strategy}</span>`;
}

function piotMarkup(values) {
  if (!values) return `<span class="indicator-pair neutral">—</span>`;
  return `<div class="piot-trend">${values.map((value) => `<span style="height:${12 + value}px">${value}</span>`).join("")}</div>`;
}

function indicatorMarkup(stock) {
  if (!stock.indicators) return piotMarkup(stock.piot);
  return `
    <div class="indicator-pair">
      <span>R ${formatNumber(stock.indicators.rsi, 0)}</span>
      <span>A ${formatNumber(stock.indicators.adx, 0)}</span>
    </div>
  `;
}

function recommendationMarkup(stock) {
  const labels = {
    OPEN: "GİRİŞ UYGUN",
    WATCH: "BEKLE",
    AVOID: "AÇMA"
  };
  const recommendation = stock.recommendation || "WATCH";
  return `<span class="recommendation-badge recommendation-${recommendation.toLowerCase()}">${labels[recommendation]}</span>`;
}

function targetsMarkup(stock) {
  if (stock.recommendation === "AVOID") return `<span class="indicator-pair neutral">—</span>`;
  return `<div class="target-stack">${stock.targets.map((target) => {
    const hit = stock.price >= target ? "hit" : "";
    return `<span class="${hit}">${formatNumber(target)}</span>`;
  }).join("")}</div>`;
}

function stopMarkup(stock) {
  const currentRisk = ((stock.price - stock.stop) / stock.price) * 100;
  const entryRisk = ((stock.entry - stock.stop) / stock.entry) * 100;
  const warning = stock.warning || currentRisk <= 1.5;
  const className = stock.protected ? "protected" : warning ? "warning" : "";
  const icon = stock.protected ? "🛡" : warning ? "⚠" : "";
  return `
    <div class="stop-cell-wrap ${className}">
      <strong class="negative">${icon} ${formatNumber(stock.stop)}</strong>
      <small class="stop-subtext">(Güncel: -${formatNumber(currentRisk, 1)}% / Giriş: -${formatNumber(entryRisk, 1)}%)</small>
    </div>
  `;
}

function filteredStocks() {
  return stocks
    .filter((stock) => {
      const haystack = `${stock.ticker} ${stock.company} ${stock.strategy} ${(stock.badges || []).join(" ")}`.toLocaleLowerCase("tr-TR");
      if (state.query && !haystack.includes(state.query)) return false;
      const strategyMatch = stock.strategy === state.strategy
        || (Array.isArray(stock.strategyMatches) && stock.strategyMatches.includes(state.strategy));
      return (state.strategy === "Tümü" || strategyMatch)
        && (state.recommendationFilter === "ALL" || stock.recommendation === state.recommendationFilter)
        && positionScore(stock) >= state.minimumPosition
        && (!state.smcOnly || (stock.badges || []).some((badge) => ["LIQ", "FVG", "MSS", "OB", "CLIMAX"].includes(badge)))
        && (!state.consensusOnly || (stock.badges || []).some((badge) => badge.startsWith("🔥 ÇAO") || badge.startsWith("🚀 SK")));
    })
    .sort((a, b) => {
      const key = state.sortKey;
      const direction = state.sortDirection === "asc" ? 1 : -1;
      const aValue = key === "return" ? entryDistance(a) : key === "positionScore" ? positionScore(a) : key === "confidence" ? modelConfidence(a) : a[key];
      const bValue = key === "return" ? entryDistance(b) : key === "positionScore" ? positionScore(b) : key === "confidence" ? modelConfidence(b) : b[key];
      if (typeof aValue === "string" || typeof bValue === "string") return String(aValue ?? "").localeCompare(String(bValue ?? ""), "tr") * direction;
      const aNumber = Number.isFinite(Number(aValue)) ? Number(aValue) : -Infinity;
      const bNumber = Number.isFinite(Number(bValue)) ? Number(bValue) : -Infinity;
      return (aNumber - bNumber) * direction;
    });
}

function excelLevel(stock, key) {
  const note = (stock.analystNotes || []).find((item) => item[key] !== undefined);
  return note ? formatNumber(Number(note[key])) : "—";
}

function renderTable() {
  const visibleStocks = filteredStocks();
  const selectionChanged = Boolean(visibleStocks.length) && !visibleStocks.some((stock) => stock.ticker === state.selectedTicker);
  if (selectionChanged) state.selectedTicker = visibleStocks[0].ticker;
  const leaderTicker = rankedStocks()[0]?.ticker;

  tableBody.innerHTML = visibleStocks.map((stock) => {
    const currentReturn = entryDistance(stock);
    const analysis = positionAnalysis(stock);
    const canPlan = stock.recommendation === "OPEN";
    return `
      <tr data-ticker="${stock.ticker}" class="${state.selectedTicker === stock.ticker ? "selected" : ""}">
        <td>
          <button class="add-position" type="button" ${canPlan ? `data-add="${stock.ticker}"` : "disabled"} aria-label="${stock.ticker} sanal portföye ekle">＋</button>
        </td>
        <td>
          <div class="ticker-cell">
            <div class="ticker-title-row">
              <strong>${stock.ticker}</strong>
              <span class="direction-badge long">LONG</span>
            </div>
            <small>${stock.company}</small>
            <div class="row-badges">${badgesMarkup(stock.badges)}</div>
          </div>
        </td>
        <td>
          ${strategyMarkup(stock)}
          <div class="recommendation-row">${recommendationMarkup(stock)}</div>
        </td>
        <td>${scorePill(stock.fundamental)}</td>
        <td>${scorePill(stock.guru)}</td>
        <td>${indicatorMarkup(stock)}</td>
        <td>${scorePill(stock.sentiment)}</td>
        <td><span class="master-pill">${stock.master}</span></td>
        <td><span class="position-pill ${stock.ticker === leaderTicker ? "top-score" : ""}">${stock.ticker === leaderTicker ? "★ " : ""}${formatNumber(analysis.score, 1)}</span></td>
        <td>${confidenceMarkup(stock)}</td>
        <td>
          <div class="price-cell">
            <strong>${formatCurrency(stock.price)}</strong>
            <small class="${stock.daily >= 0 ? "positive" : "negative"}">${stock.daily >= 0 ? "+" : ""}${formatNumber(stock.daily)}%</small>
            ${stock.delayedQuote ? `<small class="delayed-quote">15dk: ${formatCurrency(stock.delayedQuote.price)}</small>` : ""}
          </div>
        </td>
        <td><span class="excel-level">${excelLevel(stock, "Destek Seviyesi (TL)")}</span></td>
        <td><span class="excel-level resistance">${excelLevel(stock, "Direnç Seviyesi (TL)")}</span></td>
        <td>
          <div class="return-cell">
            <strong class="${currentReturn >= 0 ? "positive" : "negative"}">${currentReturn >= 0 ? "+" : ""}${formatNumber(currentReturn)}%</strong>
            <small>Giriş ${formatNumber(stock.entry)}</small>
          </div>
        </td>
        <td>${targetsMarkup(stock)}</td>
        <td>${stopMarkup(stock)}</td>
        <td><button class="row-detail-button" type="button" aria-label="${stock.ticker} detayları">›</button></td>
      </tr>
    `;
  }).join("");

  tableSummary.textContent = `${stocks.length} sinyalden ${visibleStocks.length} tanesi gösteriliyor`;
  const filterCount = [state.strategy !== "Tümü", state.minimumPosition > 0, state.smcOnly, state.consensusOnly, state.recommendationFilter !== "ALL", Boolean(state.query)].filter(Boolean).length;
  activeFilterCount.textContent = filterCount;
  filterButton.classList.toggle("active", filterCount > 0 || filterDrawer.classList.contains("open"));
  const averagePosition = stocks.length ? average(stocks.map((stock) => positionScore(stock))) : 0;
  document.getElementById("averagePositionScore").textContent = formatNumber(averagePosition, 1);
  document.getElementById("averagePositionBar").style.width = `${averagePosition}%`;
  renderStrategyCounts();
  renderStrategyRibbon();
  renderSectorHeatmap();
  updatePortfolioMetric();

  tableBody.querySelectorAll("tr").forEach((row) => {
    row.addEventListener("click", (event) => {
      if (event.target.closest(".add-position")) return;
      state.selectedTicker = row.dataset.ticker;
      renderTable();
      renderDetail();
    });
  });

  tableBody.querySelectorAll("[data-add]").forEach((button) => {
    button.addEventListener("click", (event) => {
      event.stopPropagation();
      openPortfolioModal(button.dataset.add);
    });
  });

  renderDecision();
  if (selectionChanged) renderDetail();
  if (!visibleStocks.length) renderEmptyDetail();
}

function renderEmptyDetail() {
  state.selectedTicker = "";
  backtestRequestSequence += 1;
  document.getElementById("detailLogo").textContent = "—";
  document.getElementById("detailTicker").textContent = "SONUÇ YOK";
  document.getElementById("detailCompany").textContent = "Seçili filtrelere uyan hisse bulunamadı.";
  document.getElementById("detailPrice").textContent = "—";
  document.getElementById("detailDaily").textContent = "Filtreleri değiştirin";
  document.getElementById("chartLine").setAttribute("d", "");
  document.getElementById("chartArea").setAttribute("d", "");
  document.getElementById("chartPoint").style.display = "none";
  document.getElementById("entryLine").style.display = "none";
  document.getElementById("entryLabel").style.display = "none";
  document.getElementById("detailBadges").innerHTML = "";
  document.getElementById("analystNotes").innerHTML = "";
  document.getElementById("detailScoreBars").innerHTML = "";
  ["targetEntry", "targetTp1", "targetTp2", "targetTp3", "detailStop", "detailRR", "detailPosition", "detailMaster"].forEach((id) => { document.getElementById(id).textContent = "—"; });
  document.getElementById("railProgress").style.width = "0";
  document.querySelector(".orbit-value").style.strokeDashoffset = 220;
  document.getElementById("backtestResult").textContent = "Gösterilecek hisse seçilmedi.";
  ["chartPeriodReturn", "chartPeriodCompare", "chartPeriodDifference", "chartPeriodRange"].forEach((id) => {
    const element = document.getElementById(id);
    if (element) element.textContent = "—";
  });
  document.getElementById("backtestMetricStatus").textContent = "FİLTRE SONUCU YOK";
  document.getElementById("backtestMetricRate").textContent = "—";
  document.getElementById("backtestWins").style.width = "0";
  document.getElementById("backtestLosses").style.width = "0";
}

function renderStrategyCounts() {
  document.querySelectorAll(".strategy-card").forEach((card) => {
    const count = stocks.filter((stock) => stock.strategy === card.dataset.strategyFilter
      || (Array.isArray(stock.strategyMatches) && stock.strategyMatches.includes(card.dataset.strategyFilter))).length;
    const target = card.querySelector(".strategy-count");
    if (target) target.textContent = `${count} hisse`;
  });
}

function renderStrategyRibbon() {
  const ribbon = document.getElementById("strategyRibbon");
  if (!ribbon) return;
  const names = ["Tümü", "Dipten Dönüş", "Derin Dönüş", "Uzun Vade", "Momentum Kırılımı", "CRSI Scalp", "Chartist MM Trend", "Wyckoff Spring", "Money Dip", "Chartist Trender"];
  ribbon.innerHTML = names.map((name) => {
    const count = name === "Tümü" ? stocks.length : stocks.filter((stock) => stock.strategy === name || (stock.strategyMatches || []).includes(name)).length;
    return `<button type="button" class="ribbon-chip ${state.strategy === name ? "active" : ""}" data-ribbon-strategy="${escapeHtml(name)}"><span>${escapeHtml(name)}</span><b>${count}</b></button>`;
  }).join("");
  ribbon.querySelectorAll("[data-ribbon-strategy]").forEach((button) => button.addEventListener("click", () => {
    state.strategy = button.dataset.ribbonStrategy || "Tümü";
    state.recommendationFilter = "ALL";
    document.querySelectorAll(".filter-chip").forEach((chip) => chip.classList.toggle("active", chip.dataset.strategy === state.strategy));
    renderTable();
  }));
}

function renderSectorHeatmap() {
  const container = document.getElementById("sectorHeatmap");
  const groups = new Map();
  stocks.forEach((stock) => {
    const sector = stock.sector || "Diğer";
    const current = groups.get(sector) || { sector, count: 0, total: 0 };
    current.count += 1;
    current.total += stock.daily;
    groups.set(sector, current);
  });
  const sectors = [...groups.values()]
    .map((group) => ({ ...group, average: group.total / group.count }))
    .sort((a, b) => b.count - a.count || Math.abs(b.average) - Math.abs(a.average))
    .slice(0, 6);

  const heatClass = (value) => {
    if (value >= 2.5) return "heat-strong";
    if (value >= 0.75) return "heat-up";
    if (value > -0.25) return "heat-flat";
    if (value > -1.5) return "heat-down";
    return "heat-down-strong";
  };
  container.innerHTML = sectors.map((group) => `
    <div class="heat-cell ${heatClass(group.average)}" style="--size:${Math.min(1.55, 0.75 + group.count * 0.16)}">
      <strong>${group.sector.toLocaleUpperCase("tr-TR")}</strong>
      <span>${group.average >= 0 ? "+" : ""}${formatNumber(group.average)}%</span>
      <small>${group.count} BIST100 hissesi</small>
    </div>
  `).join("");
}

function updatePortfolioMetric() {
  const positions = state.portfolio
    .map((position) => {
      const stock = stocks.find((item) => item.ticker === position.ticker);
      return stock ? { ...position, currentPrice: stock.price } : null;
    })
    .filter(Boolean);
  const cost = positions.reduce((sum, position) => sum + position.entryPrice * position.lots, 0);
  const value = positions.reduce((sum, position) => sum + position.currentPrice * position.lots, 0);
  const pnl = value - cost;
  const pnlElement = document.getElementById("portfolioPnl");
  pnlElement.textContent = `${pnl > 0 ? "+" : pnl < 0 ? "−" : ""}${formatCurrency(Math.abs(pnl))}`;
  pnlElement.className = pnl > 0 ? "positive" : pnl < 0 ? "negative" : "";
  document.getElementById("portfolioValue").textContent = formatCurrency(value);
  document.getElementById("portfolioStatus").textContent = positions.length ? `${positions.length} pozisyon` : "Kayıt yok";
}

function chartPath(values) {
  const width = 420;
  const height = 156;
  const padding = 8;
  const cleanValues = (Array.isArray(values) ? values : []).map(Number).filter(Number.isFinite);
  if (!cleanValues.length) cleanValues.push(0, 0);
  if (cleanValues.length === 1) cleanValues.push(cleanValues[0]);
  const min = Math.min(...cleanValues);
  const max = Math.max(...cleanValues);
  const spread = Math.max(max - min, 0.1);
  const points = cleanValues.map((value, index) => {
    const x = (index / (cleanValues.length - 1)) * (width - padding * 2) + padding;
    const y = height - padding - ((value - min) / spread) * (height - padding * 2);
    return [x, y];
  });
  const line = points.map(([x, y], index) => `${index === 0 ? "M" : "L"}${x.toFixed(1)} ${y.toFixed(1)}`).join(" ");
  const area = `${line} L${points.at(-1)[0].toFixed(1)} ${height} L${points[0][0].toFixed(1)} ${height} Z`;
  return { line, area, last: points.at(-1), min, max, height, padding };
}

function renderStockChart(stock) {
  const values = stock.chartRanges?.[state.chartRange] || stock.chart || [];
  const cleanValues = (Array.isArray(values) ? values : []).map(Number).filter(Number.isFinite);
  const chart = chartPath(values);
  document.getElementById("chartPoint").style.display = "";
  document.getElementById("entryLine").style.display = "";
  document.getElementById("entryLabel").style.display = "";
  const rawEntryY = chart.height - chart.padding - ((stock.entry - chart.min) / Math.max(chart.max - chart.min, 0.1)) * (chart.height - chart.padding * 2);
  const entryY = Math.max(chart.padding, Math.min(chart.height - chart.padding, rawEntryY));
  document.getElementById("chartLine").setAttribute("d", chart.line);
  document.getElementById("chartArea").setAttribute("d", chart.area);
  document.getElementById("chartPoint").setAttribute("cx", chart.last[0]);
  document.getElementById("chartPoint").setAttribute("cy", chart.last[1]);
  document.getElementById("entryLine").setAttribute("y1", entryY);
  document.getElementById("entryLine").setAttribute("y2", entryY);
  document.getElementById("entryLabel").setAttribute("y", Math.max(12, Math.min(chart.height - 4, entryY - 5)));
  const outsideMarker = rawEntryY < chart.padding ? " ↑" : rawEntryY > chart.height - chart.padding ? " ↓" : "";
  document.getElementById("entryLabel").textContent = `Giriş ${formatNumber(stock.entry)}${outsideMarker}`;
  const labels = { "1G": "15 dk gecikmeli gün içi", "1H": "Son 5 seans · 1 hafta", "1A": "Son 22 seans · 1 ay", "3A": "Son 66 seans · 3 ay" };
  const source = document.getElementById("chartSourceLabel");
  if (source) source.innerHTML = `<i></i> ${labels[state.chartRange]}`;

  const first = cleanValues[0];
  const last = cleanValues.at(-1);
  const low = cleanValues.length ? Math.min(...cleanValues) : null;
  const high = cleanValues.length ? Math.max(...cleanValues) : null;
  const difference = Number.isFinite(first) && Number.isFinite(last) ? last - first : null;
  const percentage = Number.isFinite(difference) && first ? (difference / first) * 100 : null;
  const periodNames = { "1G": "Gün içi değişim", "1H": "Haftalık değişim", "1A": "Aylık değişim", "3A": "3 aylık değişim" };
  const returnElement = document.getElementById("chartPeriodReturn");
  const comparisonElement = document.getElementById("chartPeriodCompare");
  const differenceElement = document.getElementById("chartPeriodDifference");
  const rangeElement = document.getElementById("chartPeriodRange");
  const labelElement = document.getElementById("chartPeriodLabel");
  if (labelElement) labelElement.textContent = periodNames[state.chartRange];
  if (returnElement) {
    returnElement.textContent = Number.isFinite(percentage) ? `${percentage >= 0 ? "+" : ""}${formatNumber(percentage)}%` : "—";
    returnElement.className = Number.isFinite(percentage) && percentage < 0 ? "negative" : "positive";
  }
  if (comparisonElement) comparisonElement.textContent = Number.isFinite(first) ? `${formatCurrency(first)} → ${formatCurrency(last)}` : "—";
  if (differenceElement) {
    differenceElement.textContent = Number.isFinite(difference) ? `${difference >= 0 ? "+" : ""}${formatCurrency(difference)} fark` : "—";
    differenceElement.className = Number.isFinite(difference) && difference < 0 ? "negative" : "positive";
  }
  if (rangeElement) rangeElement.textContent = Number.isFinite(low) ? `${formatCurrency(low)} → ${formatCurrency(high)}` : "—";
}

function riskModel(rr) {
  if (rr < 1) return "Muhafazakâr";
  if (rr < 1.5) return "Dengeli ve Güvenli";
  return "Trend Takip Eden";
}

function renderDecision() {
  const leaders = rankedStocks();
  if (!leaders.length) {
    document.getElementById("winnerTicker").textContent = "VERİ YOK";
    document.getElementById("winnerCompany").textContent = "Piyasa taraması tamamlanamadı";
    document.getElementById("winnerScore").textContent = "--";
    document.getElementById("winnerVerdict").textContent = "İşlem açma";
    document.getElementById("leaderboardList").innerHTML = "";
    const action = document.getElementById("winnerPortfolioButton");
    action.disabled = true;
    action.textContent = "Resmî veri bekleniyor";
    return;
  }
  const winner = leaders[0];
  const analysis = positionAnalysis(winner);
  const confidenceLabel = analysis.confidence >= 82 ? "Yüksek" : analysis.confidence >= 68 ? "Orta" : "Düşük";

  document.getElementById("winnerLogo").textContent = winner.ticker.slice(0, 1);
  document.getElementById("winnerTicker").textContent = winner.ticker;
  document.getElementById("winnerCompany").textContent = winner.company;
  document.getElementById("winnerGrade").textContent = analysis.grade;
  document.getElementById("winnerVerdict").textContent = analysis.verdict;
  document.getElementById("winnerScore").textContent = formatNumber(analysis.score, 1);
  document.getElementById("winnerConfidence").textContent = `${confidenceLabel} · %${analysis.confidence}`;
  document.getElementById("winnerConfidenceBar").style.width = `${analysis.confidence}%`;
  document.getElementById("winnerRiskModel").textContent = riskModel(winner.rr);
  document.getElementById("winnerPrice").textContent = formatCurrency(winner.price);
  document.getElementById("winnerEntry").textContent = winner.entryZoneLow
    ? `${formatCurrency(winner.entryZoneLow)}–${formatCurrency(winner.entryZoneHigh)}`
    : formatCurrency(winner.entry);
  document.getElementById("winnerTarget").textContent = formatCurrency(winner.targets[0]);
  document.getElementById("winnerStop").textContent = formatCurrency(winner.stop);
  document.getElementById("winnerUpdated").textContent = `${winner.dataDate} resmî kapanış`;

  const smcText = winner.badges.length >= 3
    ? `${winner.badges.length} kurumsal hareket onayı güçlü bir uyum oluşturuyor.`
    : winner.badges.length
      ? `${winner.badges.length} fiyat hareketi onayı teknik yapıyı destekliyor.`
      : "Ek fiyat hareketi onayı bulunmuyor.";
  document.getElementById("winnerSummary").textContent =
    `${winner.dataDate || "Son veri"} resmî kapanışına göre teknik kalite ${formatNumber(analysis.technical, 0)}. Finansal/KAP puanı doğrulanmadığı için sıralamaya katılmıyor. ${smcText}`;

  const reasons = [
    {
      icon: "⌁",
      title: "Teknik güç",
      detail: "Momentum, hacim, yapı ve destek birleşimi",
      value: analysis.technical
    },
    {
      icon: "✓",
      title: "Veri doğrulama",
      detail: `${winner.priceSource} · OHLC ve hacim doğrulandı`,
      value: 100
    },
    {
      icon: "◆",
      title: "SMC uyumu",
      detail: winner.badges.length ? winner.badges.map((badge) => (badgeMeta[badge] || { label: badge }).label).join(" · ") : "Aktif kurumsal onay yok",
      value: analysis.smc
    },
    {
      icon: "↗",
      title: "Risk / getiri",
      detail: `${formatNumber(winner.rr)} R/R · stop güvenliği ${formatNumber(analysis.stop, 0)}`,
      value: analysis.rr
    }
  ];

  document.getElementById("winnerReasons").innerHTML = reasons.map((reason) => `
    <div class="reason-item">
      <span class="reason-icon">${reason.icon}</span>
      <div>
        <strong>${reason.title}</strong>
        <small>${reason.detail}</small>
      </div>
      <span class="reason-value">${formatNumber(reason.value, 0)}</span>
    </div>
  `).join("");

  const timing = document.getElementById("winnerTiming");
  timing.classList.remove("good");
  if (winner.recommendation === "OPEN") {
    timing.classList.add("good");
    timing.innerHTML = `<span>✓</span><p><strong>Koşullu giriş uygun.</strong> Yalnızca ${formatCurrency(winner.entryZoneLow)}–${formatCurrency(winner.entryZoneHigh)} aralığında; fiyat aralığın üzerine taşarsa bekle.</p>`;
  } else if (winner.recommendation === "WATCH") {
    timing.innerHTML = `<span>⌖</span><p><strong>Henüz pozisyon açma.</strong> Model bu hisseyi izliyor; giriş bölgesi ve yön teyidi birlikte oluşmalı.</p>`;
  } else {
    timing.innerHTML = `<span>⚠</span><p><strong>Yeni giriş uygun değil.</strong> Teknik eşikler pozisyon açmak için yeterli değil.</p>`;
  }

  const action = document.getElementById("winnerPortfolioButton");
  action.disabled = winner.recommendation !== "OPEN";
  action.innerHTML = winner.recommendation === "OPEN"
    ? `Sanal Pozisyonu Planla <span>→</span>`
    : `Pozisyon için teyit bekle`;

  const leaderboard = document.getElementById("leaderboardList");
  leaderboard.innerHTML = leaders.slice(0, 3).map((stock, index) => {
    const stockAnalysis = positionAnalysis(stock);
    return `
      <div class="leaderboard-item" data-leader="${stock.ticker}">
        <span class="rank-number">0${index + 1}</span>
        <span class="leader-logo">${stock.ticker.slice(0, 1)}</span>
        <div class="leader-copy">
          <strong>${stock.ticker}</strong>
          <small>${stock.recommendation === "OPEN" ? "Giriş uygun" : stock.recommendation === "WATCH" ? "Bekle" : "Açma"} · ${stock.strategy}</small>
        </div>
        <div class="leader-score">
          <strong>${formatNumber(stockAnalysis.score, 1)}</strong>
          <small>${stockAnalysis.grade} derece</small>
        </div>
      </div>
    `;
  }).join("");

  leaderboard.querySelectorAll("[data-leader]").forEach((row) => {
    row.addEventListener("click", () => {
      state.selectedTicker = row.dataset.leader;
      renderTable();
      renderDetail();
      document.getElementById("signals").scrollIntoView({ behavior: "smooth", block: "start" });
    });
  });
}

function renderDetail() {
  const stock = stocks.find((item) => item.ticker === state.selectedTicker) || stocks[0];
  if (!stock) return;
  const currentReturn = entryDistance(stock);
  const analysis = positionAnalysis(stock);
  const targetSpread = Number(stock.targets?.[2]) - Number(stock.entry);
  const targetProgress = targetSpread > 0
    ? Math.max(0, Math.min(100, ((stock.price - stock.entry) / targetSpread) * 100))
    : 0;

  document.getElementById("detailLogo").textContent = stock.ticker.slice(0, 1);
  document.getElementById("detailTicker").textContent = stock.ticker;
  document.getElementById("detailPeriod").textContent = stock.period;
  document.getElementById("detailCompany").textContent = stock.company;
  document.getElementById("detailPrice").textContent = formatCurrency(stock.price);
  document.getElementById("detailDaily").textContent = `${stock.daily >= 0 ? "+" : ""}${formatNumber(stock.daily)}% bugün`;
  document.getElementById("detailDaily").className = stock.daily >= 0 ? "positive" : "negative";
  document.getElementById("detailMaster").textContent = formatNumber(analysis.score, 1);
  document.querySelector(".orbit-value").style.strokeDashoffset = 220 - (220 * analysis.score / 100);
  renderStockChart(stock);
  document.getElementById("detailBadges").innerHTML = badgesMarkup(stock.badges, false) || `<span class="smc-badge neutral">SMC onayı bekleniyor</span>`;
  const notesElement = document.getElementById("analystNotes");
  if (notesElement) {
    const notes = stock.analystNotes || [];
    const evidence = stock.strategyEvidence?.[stock.strategy] || [];
    const matches = Array.isArray(stock.strategyMatches) ? stock.strategyMatches : [];
    let patternNote = "";
    if (stock.patternInfo && stock.patternInfo.pattern) {
      const pat = stock.patternInfo;
      const isBreak = pat.breakoutConfirmed ? " (KIRILIM ONAYLI)" : " (Oluşumda)";
      patternNote = `<div class="analyst-note pattern-note"><span>FORMASYON · ${escapeHtml(pat.pattern)}${isBreak}</span><strong>Boyun Çizgisi: ${formatCurrency(pat.neckline)} · Hedef: ${formatCurrency(pat.patternTarget)} · Stop: ${formatCurrency(pat.patternStop)}</strong><small>Sol Omuz: ${formatNumber(pat.leftShoulder?.price)} TL · Baş: ${formatNumber(pat.head?.price)} TL · Sağ Omuz: ${formatNumber(pat.rightShoulder?.price)} TL · Güven: %${formatNumber(pat.patternConfidence, 0)} · Tarih: ${escapeHtml(pat.dateRange || "")}</small></div>`;
    }
    const algorithmNote = stock.strategy !== "İzleme"
      ? `<div class="analyst-note"><span>ALGORİTMA · ${escapeHtml(stock.strategy)}</span><strong>${evidence.map(escapeHtml).join(" · ")}</strong><small>Kalite: ${formatNumber(stock.strategyQuality, 1)}/100${matches.length > 1 ? ` · Diğer eşleşmeler: ${matches.slice(1).map(escapeHtml).join(" · ")}` : ""}</small></div>`
      : `<div class="analyst-note"><span>10 ALGORİTMA</span><strong>Bugün kesin strateji tetiklenmedi.</strong><small>Hisse yalnızca izleme durumunda.</small></div>`;
    const excelNotes = notes.length ? notes.slice(0, 4).map((note) => {
      const isAlarm = Boolean(note["Alarm Açıklaması / Talimatı"]);
      const levels = [note["Destek Seviyesi (TL)"], note["Direnç Seviyesi (TL)"], note["Hedef Fiyat / Oran"]].filter((value) => value !== undefined);
      const text = note["Özel Açıklamalar / Analiz Notları"] || note["Alarm Açıklaması / Talimatı"] || "Excel seviyesi";
      const levelLabel = isAlarm ? "Alarm seviyesi" : "Seviye";
      return `<div class="analyst-note"><span>EXCEL · ${isAlarm ? "ALARM" : "TAKİP"}</span><strong>${escapeHtml(text)}</strong>${levels.length ? `<small>${levelLabel}: ${levels.map(escapeHtml).join(" · ")} TL · Kaynak: ${escapeHtml(note.sheet || "Excel")}</small>` : ""}</div>`;
    }).join("") : "";
    notesElement.innerHTML = patternNote + algorithmNote + excelNotes;
  }
  document.getElementById("riskModel").textContent = riskModel(stock.rr);
  document.getElementById("targetEntry").textContent = formatNumber(stock.entry);
  document.getElementById("targetTp1").textContent = formatNumber(stock.targets[0]);
  document.getElementById("targetTp2").textContent = formatNumber(stock.targets[1]);
  document.getElementById("targetTp3").textContent = formatNumber(stock.targets[2]);
  document.getElementById("railProgress").style.width = `${targetProgress}%`;
  document.getElementById("detailStop").textContent = formatCurrency(stock.stop);
  document.getElementById("detailRR").textContent = formatNumber(stock.rr);
  document.getElementById("detailPosition").textContent =
    stock.recommendation === "OPEN" ? "GİRİŞ" : stock.recommendation === "WATCH" ? "BEKLE" : "AÇMA";
  const watchButton = document.getElementById("watchButton");
  if (watchButton) {
    const watched = state.watchlist.includes(stock.ticker);
    watchButton.classList.toggle("active", watched);
    watchButton.textContent = watched ? "★" : "☆";
    watchButton.setAttribute("aria-label", watched ? "Takip listesinden çıkar" : "Takip listesine ekle");
  }

  const scores = [
    ["Pozisyon", analysis.score],
    ["Algoritma", stock.strategyQuality || 0],
    ["Teknik Güç", analysis.technical],
    ["Trend", stock.guru],
    ["SMC Uyumu", analysis.smc],
    ["R/R Kalitesi", analysis.rr],
    ["Giriş Zamanı", analysis.entry]
  ];
  document.getElementById("detailScoreBars").innerHTML = scores.map(([label, value]) => `
    <div class="score-bar">
      <div class="score-bar-head"><span>${label}</span><strong>${formatNumber(value, 0)}</strong></div>
      <div class="score-bar-track"><span style="width:${value}%"></span></div>
    </div>
  `).join("");
  const explanation = document.getElementById("scorecardExplanation");
  if (explanation) explanation.innerHTML = `
    <p><strong>${escapeHtml(stock.strategy)}:</strong> ${((stock.strategyEvidence?.[stock.strategy]) || ["Bugün kesin tetik yok"]).map(escapeHtml).join(" · ")}.</p>
    <p><strong>Göstergeler:</strong> RSI ${formatNumber(stock.indicators?.rsi, 1)} · ADX ${formatNumber(stock.indicators?.adx, 1)} · SMI ${formatNumber(stock.indicators?.smi, 1)} · CCI ${formatNumber(stock.indicators?.cci, 1)} · MFI ${formatNumber(stock.indicators?.mfi, 1)} · CRSI ${formatNumber(stock.indicators?.connorsRsi, 1)}.</p>
    <p><strong>Teknik:</strong> trend, momentum, hacim ve fiyat yapısı.</p>
    <p><strong>Giriş zamanı:</strong> fiyatın hesaplanan giriş bölgesine uzaklığı.</p>
    <p><strong>Risk:</strong> stop mesafesi ve hedefe karşı risk/getiri dengesi.</p>
    <p><strong>Finansal:</strong> doğrulanmış KAP verisi bağlı olmadığı için puana katılmıyor.</p>
    <p><strong>Money Dip:</strong> gerçek takas değil, MFI/hacim vekili kullanır.</p>`;

  document.querySelectorAll(".rail-point").forEach((point, index) => {
    if (index === 0 || (index > 0 && stock.price >= stock.targets[index - 1])) point.classList.add("reached");
    else point.classList.remove("reached");
  });

  const detailPanel = document.getElementById("detailPanel");
  detailPanel.dataset.return = currentReturn.toFixed(2);
  loadBacktest(stock.ticker);
}

function renderPlanModal() {
  const stock = stocks.find((item) => item.ticker === state.selectedTicker) || stocks[0];
  if (!stock) return;
  const percentFrom = (level) => Number.isFinite(Number(level)) && Number(stock.price)
    ? ((Number(level) / Number(stock.price) - 1) * 100) : null;
  const currentVsEntry = entryDistance(stock);
  document.getElementById("planTickerLogo").textContent = stock.ticker.slice(0, 1);
  document.getElementById("planModalTitle").textContent = stock.ticker;
  document.getElementById("planModalCompany").textContent = stock.company;
  document.getElementById("planCurrentPrice").textContent = formatCurrency(stock.price);
  document.getElementById("planDailyChange").textContent = `${stock.daily >= 0 ? "+" : ""}${formatNumber(stock.daily)}% bugün · ${stock.priceTimestamp ? new Date(stock.priceTimestamp).toLocaleTimeString("tr-TR", { hour: "2-digit", minute: "2-digit" }) : "15 dk gecikmeli"}`;
  document.getElementById("planDailyChange").className = stock.daily >= 0 ? "positive" : "negative";
  document.getElementById("planEntry").textContent = `${formatCurrency(stock.entryZoneLow)} – ${formatCurrency(stock.entryZoneHigh)}`;
  document.getElementById("planEntryMessage").textContent = currentVsEntry <= 0 ? "Giriş bölgesinin altında" : currentVsEntry <= 2.5 ? "Giriş bölgesine yakın" : `Giriş üstü ${formatNumber(currentVsEntry)}%`;
  document.getElementById("planStop").textContent = formatCurrency(stock.stop);
  document.getElementById("planRisk").textContent = `Fiyata uzaklık ${formatNumber(Math.abs(percentFrom(stock.stop)))}%`;
  [0, 1, 2].forEach((index) => {
    const target = stock.targets?.[index];
    document.getElementById(`planTp${index + 1}`).textContent = formatCurrency(target);
    const gain = percentFrom(target);
    document.getElementById(`planTp${index + 1}Gain`).textContent = gain === null ? "—" : `Buradan ${gain >= 0 ? "+" : ""}${formatNumber(gain)}%`;
  });
  document.getElementById("planRr").textContent = `${formatNumber(stock.rr)} R/R`;
  document.getElementById("planVerdict").textContent = stock.recommendation === "OPEN" ? "Giriş koşulu uygun" : stock.recommendation === "WATCH" ? "Koşul bekleniyor" : "Yeni giriş uygun değil";
  document.getElementById("planModalNote").textContent = `Model kararı son resmî kapanışla doğrulanır. Ekrandaki fiyat ${stock.priceSource || "15 dk gecikmeli veri"}; otomatik emir gönderilmez.`;
}

async function loadBacktest(ticker) {
  const result = document.getElementById("backtestResult");
  if (!result || !ticker) return;
  const sequence = ++backtestRequestSequence;
  result.textContent = "2020’den beri test çalıştırılıyor…";
  document.getElementById("backtestMetricStatus").textContent = "HESAPLANIYOR";
  try {
    let payload = backtestCache.get(ticker);
    if (!payload) {
      const response = await fetch(`/api/backtest/${encodeURIComponent(ticker)}`, { cache: "no-store" });
      payload = await response.json();
      if (!response.ok || payload.status !== "ok") throw new Error(payload.message || "Backtest alınamadı");
      backtestCache.set(ticker, payload);
    }
    if (sequence !== backtestRequestSequence || ticker !== state.selectedTicker) return;
    const tactics = Array.isArray(payload.result?.tactics) ? payload.result.tactics : [];
    const rows = tactics.filter((item) => item.trades >= 10 && Number.isFinite(Number(item.positiveRate))).sort((a, b) => (b.positiveRate ?? -1) - (a.positiveRate ?? -1));
    result.innerHTML = rows.length
      ? `<div class="backtest-heading">${escapeHtml(payload.result.from)}–${escapeHtml(payload.result.to)} · en yüksek pozitif kapanış: <strong>${escapeHtml(rows[0].tactic)}</strong></div>${rows.map((item) => `<div><strong>${escapeHtml(item.tactic)}</strong> · %${formatNumber(item.positiveRate, 1)} pozitif · %${formatNumber(item.targetHitRate, 1)} TP · %${formatNumber(item.stopRate, 1)} stop · ${item.trades} işlem · ort. ${formatNumber(item.avgReturn, 2)}% · DD ${formatNumber(item.maxDrawdown, 1)}%</div>`).join("")}<small class="backtest-warning">Bu test pozisyon puanını değil bağımsız teknik taktikleri ölçer; yatırım getirisi garantisi değildir.</small>`
      : "Yeterli işlem örneği bulunamadı.";
    const best = rows[0];
    document.getElementById("backtestMetricStatus").textContent = best ? "MODEL İÇİ TEST" : "YETERSİZ ÖRNEK";
    document.getElementById("backtestMetricRate").textContent = best ? `%${formatNumber(best.positiveRate, 1)}` : "—";
    document.getElementById("backtestMetricTactic").textContent = best ? best.tactic : "2020–günümüz";
    document.getElementById("backtestMetricTrades").textContent = best ? `${best.trades} işlem` : "En az 10 işlem gerekli";
    document.getElementById("backtestWins").style.width = best ? `${best.positiveRate}%` : "0";
    document.getElementById("backtestLosses").style.width = best ? `${100 - best.positiveRate}%` : "0";
  } catch (error) {
    if (sequence !== backtestRequestSequence) return;
    result.textContent = `Backtest alınamadı: ${error.message}`;
    document.getElementById("backtestMetricStatus").textContent = "ALINAMADI";
    document.getElementById("backtestMetricRate").textContent = "—";
  }
}

function updateModalCalculations() {
  const stock = stocks.find((item) => item.ticker === state.selectedTicker) || stocks[0];
  if (!stock) return;
  const capital = Math.max(0, Number(capitalInput.value) || 0);
  const lots = Math.floor(capital / stock.price);
  const usedCapital = lots * stock.price;
  const maxRisk = Math.max(0, (stock.price - stock.stop) * lots);
  document.getElementById("estimatedLots").textContent = new Intl.NumberFormat("tr-TR").format(lots);
  document.getElementById("usedCapital").textContent = formatCurrency(usedCapital);
  document.getElementById("maxRisk").textContent = `−${formatCurrency(maxRisk)}`;
}

function openPortfolioModal(ticker = state.selectedTicker) {
  const stock = stocks.find((item) => item.ticker === ticker) || stocks[0];
  if (!stock || stock.recommendation !== "OPEN") {
    toast.querySelector(".toast-icon").textContent = "!";
    toast.querySelector("strong").textContent = "Pozisyon planlanmadı";
    toast.querySelector("small").textContent = "Model yalnızca GİRİŞ UYGUN adaylarında plan oluşturmaya izin veriyor.";
    toast.classList.add("show");
    setTimeout(() => toast.classList.remove("show"), 3200);
    return;
  }
  const analysis = positionAnalysis(stock);
  state.selectedTicker = stock.ticker;
  renderTable();
  renderDetail();
  document.getElementById("modalTicker").textContent = stock.ticker;
  document.getElementById("modalPrice").textContent = formatCurrency(stock.price);
  document.getElementById("modalMaster").textContent = `${formatNumber(analysis.score, 1)} / 100`;
  document.getElementById("modalRisk").textContent = riskModel(stock.rr);
  capitalInput.value = 10000;
  document.querySelectorAll("[data-capital]").forEach((button) => {
    button.classList.toggle("active", button.dataset.capital === "10000");
  });
  updateModalCalculations();
  portfolioModal.classList.add("open");
  portfolioModal.setAttribute("aria-hidden", "false");
  setTimeout(() => capitalInput.focus(), 200);
}

function closePortfolioModal() {
  portfolioModal.classList.remove("open");
  portfolioModal.setAttribute("aria-hidden", "true");
}

filterButton.addEventListener("click", () => {
  filterDrawer.classList.toggle("open");
  filterButton.classList.toggle("active", filterDrawer.classList.contains("open") || Number(activeFilterCount.textContent) > 0);
});

document.querySelectorAll(".filter-chip").forEach((button) => {
  button.addEventListener("click", () => {
    state.strategy = button.dataset.strategy;
    document.querySelectorAll(".filter-chip").forEach((chip) => chip.classList.toggle("active", chip === button));
    document.querySelectorAll(".strategy-card").forEach((card) => card.classList.toggle("selected", card.dataset.strategyFilter === state.strategy));
    renderTable();
  });
});

masterRange.addEventListener("input", () => {
  state.minimumPosition = Number(masterRange.value);
  masterRangeValue.textContent = masterRange.value;
  renderTable();
});

smcOnly.addEventListener("change", () => {
  state.smcOnly = smcOnly.checked;
  renderTable();
});

if (consensusOnly) {
  consensusOnly.addEventListener("change", () => {
    state.consensusOnly = consensusOnly.checked;
    renderTable();
  });
}

globalSearch.addEventListener("input", () => {
  state.query = globalSearch.value.trim().toLocaleLowerCase("tr-TR");
  renderTable();
});

document.querySelectorAll(".signal-table th[data-sort]").forEach((header) => {
  header.addEventListener("click", () => {
    const key = header.dataset.sort;
    if (state.sortKey === key) {
      state.sortDirection = state.sortDirection === "asc" ? "desc" : "asc";
    } else {
      state.sortKey = key;
      state.sortDirection = key === "ticker" || key === "strategy" ? "asc" : "desc";
    }
    document.querySelectorAll(".signal-table th .sort-mark").forEach((mark) => {
      mark.textContent = "↕";
    });
    header.querySelector(".sort-mark").textContent = state.sortDirection === "asc" ? "↑" : "↓";
    renderTable();
  });
});

document.getElementById("quickPortfolio").addEventListener("click", () => {
  const candidate = rankedStocks().find((stock) => stock.recommendation === "OPEN");
  openPortfolioModal(candidate?.ticker);
});
function setRecommendationFilter(filter) {
  state.recommendationFilter = state.recommendationFilter === filter ? "ALL" : filter;
  document.querySelectorAll(".recommendation-filter").forEach((button) => button.classList.toggle("active", button.dataset.recommendation === state.recommendationFilter));
  renderTable();
}
document.getElementById("openOnlyButton")?.addEventListener("click", (event) => { event.currentTarget.dataset.recommendation = "OPEN"; setRecommendationFilter("OPEN"); });
document.getElementById("watchOnlyButton")?.addEventListener("click", (event) => { event.currentTarget.dataset.recommendation = "WATCH"; setRecommendationFilter("WATCH"); });
document.getElementById("winnerPortfolioButton").addEventListener("click", () => {
  const winner = rankedStocks()[0];
  if (winner?.recommendation === "OPEN") openPortfolioModal(winner.ticker);
});
document.getElementById("modalClose").addEventListener("click", closePortfolioModal);

document.getElementById("scoreInfoButton").addEventListener("click", () => {
  toast.querySelector(".toast-icon").textContent = "i";
  toast.querySelector("strong").textContent = "Pozisyon Puanı";
  toast.querySelector("small").textContent = "Teknik %78 · Giriş zamanlaması %14 · Stop güvenliği %8 · Finansal %0 (doğrulanana kadar kapalı)";
  toast.classList.add("show");
  setTimeout(() => {
    toast.classList.remove("show");
    toast.querySelector(".toast-icon").textContent = "✓";
  }, 5200);
});

portfolioModal.addEventListener("click", (event) => {
  if (event.target === portfolioModal) closePortfolioModal();
});

capitalInput.addEventListener("input", () => {
  document.querySelectorAll("[data-capital]").forEach((button) => button.classList.remove("active"));
  updateModalCalculations();
});

document.querySelectorAll("[data-capital]").forEach((button) => {
  button.addEventListener("click", () => {
    capitalInput.value = button.dataset.capital;
    document.querySelectorAll("[data-capital]").forEach((item) => item.classList.toggle("active", item === button));
    updateModalCalculations();
  });
});

document.getElementById("modalSubmit").addEventListener("click", () => {
  const stock = stocks.find((item) => item.ticker === state.selectedTicker);
  const capital = Math.max(0, Number(capitalInput.value) || 0);
  const lots = stock ? Math.floor(capital / stock.price) : 0;
  if (!stock || stock.recommendation !== "OPEN" || lots < 1) return;
  const existing = state.portfolio.find((position) => position.ticker === stock.ticker);
  if (existing) {
    existing.lots = lots;
    existing.entryPrice = stock.price;
  } else {
    state.portfolio.push({ ticker: stock.ticker, lots, entryPrice: stock.price });
  }
  localStorage.setItem("chartistVirtualPortfolio", JSON.stringify(state.portfolio));
  updatePortfolioMetric();
  closePortfolioModal();
  toast.querySelector(".toast-icon").textContent = "✓";
  toast.querySelector("strong").textContent = `${state.selectedTicker} pozisyonu eklendi`;
  toast.querySelector("small").textContent = "Sanal portföyünüz güncellendi.";
  toast.classList.add("show");
  setTimeout(() => toast.classList.remove("show"), 3200);
});

document.getElementById("exportButton").addEventListener("click", () => {
  if (!stocks.length) return;
  const headers = [
    "Hisse", "Şirket", "Karar", "Strateji", "Pozisyon Puanı", "Resmî Kapanış",
    "Günlük %", "Giriş Alt", "Giriş Üst", "Stop", "TP1", "Veri Tarihi", "Kaynak"
  ];
  const rows = filteredStocks().map((stock) => [
    stock.ticker,
    stock.company,
    stock.recommendation,
    stock.strategy,
    stock.modelScore,
    stock.price,
    stock.daily,
    stock.entryZoneLow,
    stock.entryZoneHigh,
    stock.stop,
    stock.targets[0],
    stock.dataDate,
    stock.priceSource
  ]);
  const csv = [headers, ...rows]
    .map((row) => row.map((value) => `"${String(value ?? "").replaceAll('"', '""')}"`).join(";"))
    .join("\r\n");
  const blob = new Blob([`\uFEFF${csv}`], { type: "text/csv;charset=utf-8" });
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = `chartist-bist100-${marketPayload?.dataDate || "tarama"}.csv`;
  link.click();
  URL.revokeObjectURL(link.href);
});

document.querySelectorAll(".strategy-card").forEach((card) => {
  card.addEventListener("click", () => {
    const strategy = card.dataset.strategyFilter;
    state.strategy = strategy;
    document.querySelectorAll(".strategy-card").forEach((item) => item.classList.toggle("selected", item === card));
    document.querySelectorAll(".filter-chip").forEach((chip) => chip.classList.toggle("active", chip.dataset.strategy === strategy));
    filterDrawer.classList.add("open");
    renderTable();
    document.getElementById("signals").scrollIntoView({ behavior: "smooth", block: "start" });
  });
});

document.querySelectorAll(".chart-toolbar button").forEach((button) => {
  button.addEventListener("click", () => {
    state.chartRange = button.dataset.chartRange || "1H";
    document.querySelectorAll(".chart-toolbar button").forEach((item) => item.classList.toggle("active", item === button));
    const stock = stocks.find((item) => item.ticker === state.selectedTicker) || stocks[0];
    if (stock) renderStockChart(stock);
  });
});

document.querySelectorAll(".segmented-control button").forEach((button) => {
  button.addEventListener("click", () => {
    document.querySelectorAll(".segmented-control button").forEach((item) => item.classList.toggle("active", item === button));
  });
});

document.getElementById("watchButton")?.addEventListener("click", (event) => {
  const ticker = state.selectedTicker;
  if (!ticker) return;
  state.watchlist = state.watchlist.includes(ticker)
    ? state.watchlist.filter((item) => item !== ticker)
    : [...state.watchlist, ticker];
  localStorage.setItem("chartistWatchlist", JSON.stringify(state.watchlist));
  const watched = state.watchlist.includes(ticker);
  event.currentTarget.classList.toggle("active", watched);
  event.currentTarget.textContent = watched ? "★" : "☆";
  event.currentTarget.setAttribute("aria-label", watched ? "Takip listesinden çıkar" : "Takip listesine ekle");
});

function renderMarketWindModal(report) {
  if (!report) return;
  document.getElementById("windIndexClose").textContent = formatNumber(report.indexClose);
  const changeElem = document.getElementById("windIndexChange");
  changeElem.textContent = `${report.changePercent >= 0 ? "+" : ""}${formatNumber(report.changePercent)}%`;
  changeElem.className = report.changePercent >= 0 ? "positive" : "negative";

  document.getElementById("windEma50").textContent = formatNumber(report.ema50);
  const ema50Dist = document.getElementById("windEma50Dist");
  ema50Dist.textContent = `Mesafe: ${report.ema50Distance >= 0 ? "+" : ""}${formatNumber(report.ema50Distance)}%`;
  ema50Dist.className = report.ema50Distance >= 0 ? "positive" : "negative";

  document.getElementById("windEma200").textContent = formatNumber(report.ema200);
  const ema200Dist = document.getElementById("windEma200Dist");
  ema200Dist.textContent = `Mesafe: ${report.ema200Distance >= 0 ? "+" : ""}${formatNumber(report.ema200Distance)}%`;
  ema200Dist.className = report.ema200Distance >= 0 ? "positive" : "negative";

  document.getElementById("windTrendStatus").textContent = report.trendStatus;
  document.getElementById("windTrendSummary").textContent =
    `BIST 100 Endeksi 45 İndikatörlü Konsensüs Analizi: 45 İndikatörün ${report.positiveCount}'i Pozitif (${report.positiveCount}/${report.totalCount} | Trende Mesafe: %${formatNumber(report.ema50Distance)}).`;

  document.getElementById("windCountsBadge").innerHTML =
    `🟢 ${report.positiveCount} Pozitif / 🔴 ${report.negativeCount} Negatif`;

  const grid = document.getElementById("windIndicatorGrid");
  if (grid && Array.isArray(report.indicators)) {
    grid.innerHTML = report.indicators.map((item) => `
      <div class="wind-indicator-card ${item.isPositive ? "pos" : "neg"}">
        <div class="wind-ind-header">
          <strong>${escapeHtml(item.name)}</strong>
          <span class="wind-ind-status ${item.isPositive ? "pos" : "neg"}">
            ${item.isPositive ? "🟢 POZİTİF (BOĞA)" : "🔴 NEGATİF (AYI)"}
          </span>
        </div>
        <small class="wind-ind-group">Grup: ${escapeHtml(item.group)}</small>
      </div>
    `).join("");
  }
}

async function openMarketWindModal() {
  const modal = document.getElementById("marketWindModal");
  if (!modal) return;
  modal.classList.add("open");
  modal.setAttribute("aria-hidden", "false");
  if (marketPayload && marketPayload.marketWind) {
    renderMarketWindModal(marketPayload.marketWind);
  } else {
    try {
      const response = await fetch("/api/market-wind", { cache: "no-store" });
      const data = await response.json();
      if (response.ok && data.status === "ok") {
        renderMarketWindModal(data);
      }
    } catch (err) {
      console.error("Market wind report failed", err);
    }
  }
}

document.getElementById("openMarketWindButton")?.addEventListener("click", openMarketWindModal);
document.getElementById("windModalClose")?.addEventListener("click", () => {
  const modal = document.getElementById("marketWindModal");
  modal?.classList.remove("open");
  modal?.setAttribute("aria-hidden", "true");
});
document.getElementById("windModalFooterClose")?.addEventListener("click", () => {
  const modal = document.getElementById("marketWindModal");
  modal?.classList.remove("open");
  modal?.setAttribute("aria-hidden", "true");
});
document.getElementById("marketWindModal")?.addEventListener("click", (event) => {
  if (event.target.id === "marketWindModal") {
    event.currentTarget.classList.remove("open");
    event.currentTarget.setAttribute("aria-hidden", "true");
  }
});

document.getElementById("notificationButton")?.addEventListener("click", () => {
  loadNotificationLog();
  document.getElementById("notificationsView")?.scrollIntoView({ behavior: "smooth", block: "start" });
});

document.getElementById("userMenuButton")?.addEventListener("click", () => {
  toast.querySelector(".toast-icon").textContent = "EK";
  toast.querySelector("strong").textContent = "Emirkan Kaya";
  toast.querySelector("small").textContent = "Sanal portföy ve takip listesi yalnızca bu tarayıcıda saklanıyor.";
  toast.classList.add("show");
  setTimeout(() => toast.classList.remove("show"), 3600);
});

document.querySelectorAll(".nav-link[data-view]").forEach((link) => {
  link.addEventListener("click", (event) => {
    event.preventDefault();
    document.querySelectorAll(".nav-link").forEach((item) => item.classList.remove("active"));
    link.classList.add("active");
    document.getElementById("sidebar").classList.remove("open");
    const target = document.getElementById(link.getAttribute("href").slice(1));
    if (target) target.scrollIntoView({ behavior: "smooth", block: "start" });
  });
});

document.getElementById("mobileMenu").addEventListener("click", () => {
  document.getElementById("sidebar").classList.toggle("open");
});

document.addEventListener("keydown", (event) => {
  if ((event.ctrlKey || event.metaKey) && event.key.toLocaleLowerCase("tr-TR") === "k") {
    event.preventDefault();
    globalSearch.focus();
  }
  if (event.key === "Escape") {
    closePortfolioModal();
    document.getElementById("sidebar").classList.remove("open");
  }
});

document.getElementById("backtestButton")?.addEventListener("click", async () => {
  const ticker = state.selectedTicker || stocks[0]?.ticker;
  loadBacktest(ticker);
});

document.getElementById("scorecardToggle")?.addEventListener("click", (event) => {
  const explanation = document.getElementById("scorecardExplanation");
  if (!explanation) return;
  explanation.hidden = !explanation.hidden;
  event.currentTarget.textContent = explanation.hidden ? "Açıklamaları gör →" : "Açıklamaları giz ↑";
});

function updateClocks() {
  const now = new Date();
  document.getElementById("sidebar-clock").textContent = now.toLocaleTimeString("tr-TR");

  const day = now.getDay();
  const minutes = now.getHours() * 60 + now.getMinutes();
  const isWeekday = day >= 1 && day <= 5;
  const isOpen = isWeekday && minutes >= 600 && minutes < 1090;
  const target = new Date(now);

  if (isOpen) {
    target.setHours(18, 10, 0, 0);
    document.getElementById("sessionStateText").textContent = "Seans Açık";
    document.getElementById("sidebarMarketState").textContent = "BIST seansı açık";
    document.getElementById("sessionCountdownLabel").textContent = "KAPANIŞA KALAN";
  } else {
    target.setHours(10, 0, 0, 0);
    if (!isWeekday || minutes >= 1090) target.setDate(target.getDate() + 1);
    while (target.getDay() === 0 || target.getDay() === 6) target.setDate(target.getDate() + 1);
    document.getElementById("sessionStateText").textContent = isWeekday ? "Seans Kapalı" : "Seans Kapalı (Hafta Sonu)";
    document.getElementById("sidebarMarketState").textContent = isWeekday ? "BIST seansı kapalı" : "BIST kapalı · Hafta Sonu";
    document.getElementById("sessionCountdownLabel").textContent = "SONRAKİ SEANS";
  }

  const diff = Math.max(0, target - now);
  const hours = Math.floor(diff / 3_600_000);
  const remainingMinutes = Math.floor((diff % 3_600_000) / 60_000);
  const seconds = Math.floor((diff % 60_000) / 1000);
  document.getElementById("sessionCountdown").textContent = [hours, remainingMinutes, seconds]
    .map((value) => String(value).padStart(2, "0"))
    .join(":");
}

function updateMarketMeta(payload) {
  marketPayload = payload;
  const index = payload.index;
  const summary = payload.summary;
  document.getElementById("signalDataBadge").innerHTML = payload.staleData
    ? `<i></i> SON BAŞARILI VERİ · ${payload.dataDate}`
    : `<i></i> RESMÎ KAPANIŞ · ${payload.dataDate}`;
  document.getElementById("signalDataBadge").title = `${payload.source} · ${payload.delayNotice}`;
  document.getElementById("sidebarDataState").textContent = payload.staleData
    ? "Son başarılı veri gösteriliyor"
    : payload.quoteMode === "15m-delayed-display" ? "Kapanış + 15dk izleme" : "Resmî kapanış doğrulandı";
  document.getElementById("sidebarDelay").textContent = payload.quoteMode === "15m-delayed-display" ? "15 dk gecikmeli" : "Gün sonu";
  document.getElementById("dashboardDate").textContent =
    `${new Date(`${payload.dataDate}T12:00:00`).toLocaleDateString("tr-TR", { day: "numeric", month: "long", year: "numeric", weekday: "long" }).toLocaleUpperCase("tr-TR")} · RESMÎ KAPANIŞ`;
  document.getElementById("activeSignalCount").textContent = summary.open;
  document.getElementById("openSignalCount").textContent = summary.open;
  document.getElementById("watchSignalCount").textContent = summary.watch;
  const openButton = document.getElementById("openOnlyButton");
  const watchButton = document.getElementById("watchOnlyButton");
  if (openButton) openButton.textContent = `${summary.open} Aday`;
  if (watchButton) watchButton.textContent = `${summary.watch} İzleniyor`;
  document.getElementById("navSignalCount").textContent = summary.open;
  const universe = document.getElementById("signalUniverse");
  universe.textContent = `${payload.universe} · ${summary.scanned}/${summary.officialUniverseSize} analiz`;
  universe.title = (payload.errors || []).length ? `Dışlanan: ${(payload.errors || []).join(" · ")}` : "Resmî evrenin tamamı analiz edildi";
  document.getElementById("officialSourceLink").href = payload.sourceUrl;
  const board = document.getElementById("marketMarqueeTrack");
  if (board) {
    const items = (payload.marketBoard || []).map((item) => {
      const hasDaily = Number.isFinite(Number(item.daily));
      const daily = hasDaily ? `<em class="${item.daily >= 0 ? "positive" : "negative"}">${item.daily >= 0 ? "+" : ""}${formatNumber(item.daily)}%</em>` : `<em>günlük değişim doğrulanmadı</em>`;
      return `<span class="marquee-item" title="${escapeHtml(item.source || "")} · ${escapeHtml(item.timestamp || "")}">${escapeHtml(item.label)} <b>${formatNumber(item.value, item.label.includes("TRY") ? 4 : 2)}</b> ${daily}</span>`;
    });
    board.innerHTML = items.length ? [...items, ...items].join("") : `<span class="marquee-item">Makro veri bekleniyor</span>`;
  }
}

function showMarketError(error) {
  stocks = [];
  document.getElementById("signalDataBadge").textContent = "";
  document.getElementById("sidebarDataState").textContent = "Piyasa verisi kesildi";
  document.getElementById("activeSignalCount").textContent = "0";
  tableBody.innerHTML = "";
  tableSummary.textContent = "";
  renderDecision();
}

async function fetchMarketPayload(url = "/api/scan", attempts = 3) {
  let lastError = new Error("Tarama alınamadı");
  for (let attempt = 0; attempt < attempts; attempt += 1) {
    try {
      const response = await fetch(url, { cache: "no-store" });
      const payload = await response.json();
      if (!response.ok || payload.status !== "ok" || !Array.isArray(payload.stocks) || !payload.stocks.length) {
        throw new Error(payload.message || `API ${response.status}`);
      }
      return payload;
    } catch (error) {
      lastError = error;
      if (attempt < attempts - 1) {
        await new Promise((resolve) => setTimeout(resolve, 1200 * (attempt + 1)));
      }
    }
  }
  throw lastError;
}

async function initializeMarketData() {
  stocks = [];
  document.getElementById("winnerTicker").textContent = "TARANIYOR";
  document.getElementById("winnerCompany").textContent = "BIST100 verileri ve teknik göstergeler hesaplanıyor";
  document.getElementById("winnerScore").textContent = "--";
  tableBody.innerHTML = "";

  try {
    const payload = await fetchMarketPayload("/api/scan");
    stocks = payload.stocks;
    try {
      const savedPortfolio = JSON.parse(localStorage.getItem("chartistVirtualPortfolio") || "[]");
      state.portfolio = Array.isArray(savedPortfolio) ? savedPortfolio : [];
      const savedWatchlist = JSON.parse(localStorage.getItem("chartistWatchlist") || "[]");
      state.watchlist = Array.isArray(savedWatchlist) ? savedWatchlist.filter((item) => typeof item === "string") : [];
    } catch {
      state.portfolio = [];
    }
    state.selectedTicker = rankedStocks()[0].ticker;
    updateMarketMeta(payload);
    renderTable();
    renderDetail();
    loadAutoPortfolio();
  } catch (error) {
    stocks = [];
    showMarketError(error);
    console.error("Piyasa verisi yüklenemedi", error);
  }
}

async function loadAnalystBenchmark() {
  const rows = document.getElementById("analystRows");
  const summary = document.getElementById("analystSummary");
  if (!rows) return;
  try {
    const response = await fetch("/api/analyst-alerts", { cache: "no-store" });
    const payload = await response.json();
    if (payload.status !== "ok") throw new Error(payload.message || "okunamadı");
    const items = (payload.history || []).slice(0, 20);
    summary.textContent = `${payload.summary.triggered} gerçekleşen · ${payload.summary.active} aktif`;
    rows.innerHTML = items.length ? items.map((item) => `<tr><td><span class="tag">${escapeHtml(item.source)}</span></td><td><strong>${escapeHtml(item.ticker)}</strong></td><td>${escapeHtml(item.role)}</td><td>${item.level == null ? "—" : formatCurrency(item.level)}</td><td class="${Number(item.observedReturn) >= 0 ? "positive" : "negative"}">${item.observedReturn == null ? "—" : `${Number(item.observedReturn) >= 0 ? "+" : ""}${formatNumber(item.observedReturn)}%`}</td><td><span class="status-pill positive">TETİKLENDİ</span></td><td title="${escapeHtml(item.description)}">${escapeHtml(item.description)}</td></tr>`).join("") : `<tr><td colspan="7">Henüz gerçekleşmiş alarm kaydı yok.</td></tr>`;
  } catch (error) {
    summary.textContent = "VERİ YOK";
    rows.innerHTML = `<tr><td colspan="7">Analist alarm geçmişi okunamadı.</td></tr>`;
    console.warn("Analist geçmişi yüklenemedi", error);
  }
}

let excelNoteRows = [];

function displayExcelLevel(value) {
  if (value === null || value === undefined || value === "") return "—";
  const numeric = Number(value);
  return Number.isFinite(numeric) ? formatCurrency(numeric) : escapeHtml(value);
}

function renderExcelNotes() {
  const target = document.getElementById("excelNotesRows");
  if (!target) return;
  const query = (document.getElementById("analystNotesSearch")?.value || "").trim().toLocaleLowerCase("tr-TR");
  const source = document.getElementById("analystSourceFilter")?.value || "ALL";
  const filtered = excelNoteRows.filter((row) => {
    const haystack = [row.ticker, row.source, row.sheet, row.instruction, row.text, row.support, row.resistance, row.target].join(" ").toLocaleLowerCase("tr-TR");
    return (source === "ALL" || row.source === source) && (!query || haystack.includes(query));
  });
  target.innerHTML = filtered.length
    ? filtered.map((row) => `<tr><td><strong>${escapeHtml(row.ticker)}</strong><button class="track-note-button" type="button" data-track-note="${escapeHtml(row.ticker)}">Takibe al</button></td><td><span class="tag">${escapeHtml(row.source)}</span><small class="table-subtext">${escapeHtml(row.sheet || "")}</small></td><td class="positive">${displayExcelLevel(row.support)}</td><td class="resistance-text">${displayExcelLevel(row.resistance)}</td><td>${displayExcelLevel(row.target)}</td><td title="${escapeHtml(row.text || row.instruction || "")}">${escapeHtml(row.instruction || row.text || "Not açıklaması yok")}</td></tr>`).join("")
    : `<tr><td colspan="6">Bu filtreyle eşleşen Excel notu yok.</td></tr>`;
}

async function loadExcelNotes() {
  const target = document.getElementById("excelNotesRows");
  const summary = document.getElementById("excelNotesSummary");
  if (!target) return;
  try {
    const response = await fetch("/api/analyst-notes", { cache: "no-store" });
    const payload = await response.json();
    if (!response.ok || payload.status !== "ok") throw new Error(payload.message || "Excel okunamadı");
    excelNoteRows = Array.isArray(payload.rows) ? payload.rows : [];
    summary.textContent = `${payload.summary.notes} not · ${payload.summary.tickers} hisse`;
    const sourceFilter = document.getElementById("analystSourceFilter");
    const sources = [...new Set(excelNoteRows.map((row) => row.source).filter(Boolean))].sort((a, b) => a.localeCompare(b, "tr"));
    sourceFilter.innerHTML = `<option value="ALL">Tüm kaynaklar</option>${sources.map((item) => `<option value="${escapeHtml(item)}">${escapeHtml(item)}</option>`).join("")}`;
    renderExcelNotes();
  } catch (error) {
    summary.textContent = "VERİ YOK";
    target.innerHTML = `<tr><td colspan="6">Excel notları okunamadı: ${escapeHtml(error.message)}</td></tr>`;
  }
}

function openTradeEventModal(item) {
  const modal = document.getElementById("tradeEventModal");
  if (!modal || !item) return;

  const type = item.eventType || "TP1";
  const icon = type === "TP3" ? "🏆" : type === "TP2" ? "🔥" : type.includes("STOP") ? "🛡" : "🎯";
  const title = type === "TP3" ? "TP3 BAŞARILI KAPANİŞ!" : type === "TP2" ? "TP2 HEDEFi GÖRÜLDÜ!" : type === "TP1" ? "TP1 HEDEFİ GÖRÜLDÜ!" : "STOP OLAYI GERÇEKLEŞTİ!";
  
  document.getElementById("eventModalIcon").textContent = icon;
  document.getElementById("eventModalTitle").textContent = title;
  document.getElementById("eventModalSubtitle").textContent = `${item.ticker} hissesi (${item.strategy || "Model Sinyali"}) ${type} aşamasını tamamladı.`;
  document.getElementById("eventActionBox").innerHTML = item.action || "📢 Stop seviyenizi kar al noktasına kaydırarak taşıyabilirsiniz.";
  document.getElementById("eventModalStrategy").textContent = `🎯 ALGORİTMA / STRATEJİ: ${item.strategy || "Chartist Sinyal Motoru"}`;
  
  document.getElementById("eventModalTicker").textContent = item.ticker || "--";
  document.getElementById("eventModalEntry").textContent = formatCurrency(item.entryPrice);
  document.getElementById("eventModalTarget").textContent = formatCurrency(item.targetPrice ?? item.price);
  document.getElementById("eventModalSignalDate").textContent = item.signalAt || "--";
  document.getElementById("eventModalRealizedDate").textContent = item.realizedAt || item.timestamp || "--";

  const duration = Math.max(0, Number(item.elapsedSeconds) || 0);
  const days = Math.floor(duration / 86400), hours = Math.floor((duration % 86400) / 3600), minutes = Math.floor((duration % 3600) / 60);
  const elapsedText = days ? `${days} gün ${hours} saat ${minutes} dk` : hours ? `${hours} saat ${minutes} dk` : `${minutes} dk`;
  document.getElementById("eventModalElapsed").textContent = `⏱ ${elapsedText}`;

  const gain = Number(item.realizedReturn) || 0;
  const returnElem = document.getElementById("eventModalReturn");
  returnElem.textContent = `${gain >= 0 ? "+" : ""}${formatNumber(gain)}%`;
  returnElem.className = gain >= 0 ? "positive" : "negative";

  const maxReturn = Number(item.maxReturn) || 0;
  const maxElem = document.getElementById("eventModalMax");
  maxElem.textContent = `${maxReturn >= 0 ? "+" : ""}${formatNumber(maxReturn)}% (${formatCurrency(item.maxPrice)})`;

  const analyzeBtn = document.getElementById("eventModalAnalyze");
  if (analyzeBtn) {
    analyzeBtn.onclick = () => {
      modal.classList.remove("open");
      modal.setAttribute("aria-hidden", "true");
      if (item.ticker) {
        state.selectedTicker = item.ticker;
        renderTable();
        renderDetail();
        document.getElementById("signals")?.scrollIntoView({ behavior: "smooth" });
      }
    };
  }

  modal.classList.add("open");
  modal.setAttribute("aria-hidden", "false");
}

document.getElementById("eventModalClose")?.addEventListener("click", () => {
  const modal = document.getElementById("tradeEventModal");
  modal?.classList.remove("open");
  modal?.setAttribute("aria-hidden", "true");
});
document.getElementById("eventModalDismiss")?.addEventListener("click", () => {
  const modal = document.getElementById("tradeEventModal");
  modal?.classList.remove("open");
  modal?.setAttribute("aria-hidden", "true");
});
document.getElementById("tradeEventModal")?.addEventListener("click", (event) => {
  if (event.target.id === "tradeEventModal") {
    event.currentTarget.classList.remove("open");
    event.currentTarget.setAttribute("aria-hidden", "true");
  }
});

async function loadNotificationLog() {
  const list = document.getElementById("notificationList");
  const trackingList = document.getElementById("trackingList");
  const eventList = document.getElementById("tradeEventList");
  const status = document.getElementById("notificationStatus");
  if (!list || !status) return;
  try {
    const response = await fetch("/api/notifications", { cache: "no-store" });
    const payload = await response.json();
    if (!response.ok || payload.status !== "ok") throw new Error("Bildirim kaydı okunamadı");
    const worker = payload.worker || {};
    status.innerHTML = !worker.running
      ? `Otonom arka plan taraması kapalı. Bildirimler yalnızca siz sistemi yeniden açıp izleme başlattığınızda üretilir.`
      : worker.notificationsEnabled
        ? `Telefon kanalı aktif · ${worker.opportunities?.length || 0} fırsat izleniyor.`
        : `İşlem olayları kaydediliyor. Telefon gönderimi için ntfy kanalı henüz bağlanmadı.`;
    const rows = Array.isArray(payload.notifications) ? payload.notifications : [];
    document.getElementById("navNotificationCount").textContent = rows.filter((item) => item.status === "sent" || item.eventType).length;
    const events = rows.filter((item) => item.eventType);
    if (eventList) {
      eventList.innerHTML = events.length ? events.map((item, idx) => {
        const duration = Math.max(0, Number(item.elapsedSeconds) || 0);
        const days = Math.floor(duration / 86400), hours = Math.floor((duration % 86400) / 3600), minutes = Math.floor((duration % 3600) / 60);
        const elapsed = days ? `${days} gün ${hours} saat` : hours ? `${hours} saat ${minutes} dk` : `${minutes} dk`;
        const gain = Number(item.realizedReturn) || 0;
        const targetLabel = item.eventType.startsWith("TP") ? `${item.eventType} hedefi` : item.eventType === "TRAILING_STOP" ? "Kârlı stop" : "Stop";
        return `<article class="trade-event-card ${escapeHtml(item.eventType.toLowerCase())}" data-event-index="${idx}" style="cursor:pointer;">
          <div class="trade-event-top"><span class="trade-event-icon">${item.eventType === "TP2" ? "🔥" : item.eventType.includes("STOP") ? "🛡" : "🎯"}</span><div><strong>${escapeHtml(item.eventTitle || targetLabel)}</strong><small>${escapeHtml(item.ticker || "—")} · ${escapeHtml(item.strategy || "Model")}</small></div></div>
          <p class="trade-event-action">${escapeHtml(item.action || "İşlem olayı kaydedildi.")}</p>
          <div class="trade-event-grid"><span>Giriş<b>${formatCurrency(item.entryPrice)}</b></span><span>${escapeHtml(targetLabel)}<b>${formatCurrency(item.targetPrice ?? item.price)}</b></span><span>Gerçekleşen getiri<b class="${gain >= 0 ? "positive" : "negative"}">${gain >= 0 ? "+" : ""}${formatNumber(gain)}%</b></span><span>Görülen maks.<b>${formatCurrency(item.maxPrice)} · ${Number(item.maxReturn) >= 0 ? "+" : ""}${formatNumber(item.maxReturn)}%</b></span></div>
          <footer>Sinyal: ${escapeHtml(item.signalAt || "—")} · Gerçekleşme: ${escapeHtml(item.realizedAt || item.timestamp || "—")} · ${elapsed}</footer>
        </article>`;
      }).join("") : `<p class="muted-note">Henüz doğrulanmış TP veya stop olayı yok. Takip başladıktan sonra 15 dk gecikmeli fiyatla oluşur.</p>`;
      
      eventList.querySelectorAll(".trade-event-card").forEach((card) => {
        card.addEventListener("click", () => {
          const idx = Number(card.dataset.eventIndex);
          if (events[idx]) openTradeEventModal(events[idx]);
        });
      });
    }
    const tracking = Array.isArray(payload.tracking) ? payload.tracking : [];
    if (trackingList) {
      trackingList.innerHTML = tracking.length ? tracking.map((item) => {
        const startAt = item.startedAt ? new Date(item.startedAt).toLocaleTimeString("tr-TR", { hour: "2-digit", minute: "2-digit" }) : "—";
        const lastAt = item.lastAt ? new Date(item.lastAt).toLocaleTimeString("tr-TR", { hour: "2-digit", minute: "2-digit" }) : "—";
        const change = Number(item.changePercent) || 0;
        return `<article class="tracking-item"><div class="notification-item-head"><strong>${escapeHtml(item.ticker)} · takip</strong><time>${startAt} → ${lastAt}</time></div>${item.analystMessage ? `<p class="tracking-note">${escapeHtml(item.analystMessage)}</p>` : ""}<p><b>${formatCurrency(item.startPrice)}</b> başlangıç → <b>${formatCurrency(item.lastPrice)}</b> son fiyat <span class="${change >= 0 ? "positive" : "negative"}">(${change >= 0 ? "+" : ""}${formatNumber(change)}%)</span></p><small>${item.updates?.length || 1} fiyat gözlemi · ${escapeHtml(item.strategy || "")}</small></article>`;
      }).join("") : `<p class="muted-note">Henüz takip başlatılan fırsat yok.</p>`;
    }
    const phoneHistory = rows.filter((item) => item.status === "sent" || item.status === "local" || item.eventType);
    list.innerHTML = phoneHistory.length ? phoneHistory.map((item) => {
      const delivery = item.status === "sent" ? "✓ Telefona gönderildi" : item.status === "local" ? "✓ İşlem merkezi kaydı" : "⚠ Telefon kanalına iletilemedi";
      return `<article class="notification-item ${item.status === "sent" || item.status === "local" ? "sent" : "not-sent"}"><div class="notification-item-head"><strong>${escapeHtml(item.ticker || "Piyasa")}</strong><time>${escapeHtml(item.timestamp || "")}</time></div><small>${delivery} · ${escapeHtml(item.strategy || "")}</small><pre>${escapeHtml(item.message || item.reason || "Mesaj içeriği yok")}</pre></article>`;
    }).join("") : `<p class="muted-note">Gösterilecek telefon veya işlem kaydı yok.</p>`;
  } catch (error) {
    status.textContent = `Bildirim geçmişi alınamadı: ${error.message}`;
  }
}

document.getElementById("analystNotesSearch")?.addEventListener("input", renderExcelNotes);
document.getElementById("analystSourceFilter")?.addEventListener("change", renderExcelNotes);
document.getElementById("notificationRefresh")?.addEventListener("click", loadNotificationLog);
document.getElementById("excelNotesRows")?.addEventListener("click", async (event) => {
  const button = event.target.closest("[data-track-note]");
  if (!button) return;
  button.disabled = true;
  try {
    const response = await fetch("/api/tracking/manual", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ ticker: button.dataset.trackNote }) });
    const payload = await response.json();
    button.textContent = response.ok && payload.status === "ok" ? "Takipte" : "Tekrar dene";
    if (response.ok) loadNotificationLog();
  } catch {
    button.textContent = "Tekrar dene";
  }
});

async function refreshMarketData() {
  try {
    // Background refresh is cache-first; a forced BIST100 download is only
    // requested explicitly so the interface never freezes for network work.
    const payload = await fetchMarketPayload("/api/scan", 1);
    stocks = payload.stocks;
    marketPayload = payload;
    if (!stocks.some((stock) => stock.ticker === state.selectedTicker)) {
      state.selectedTicker = rankedStocks()[0].ticker;
    }
    updateMarketMeta(payload);
    renderTable();
    renderDetail();
    loadAutoPortfolio();
  } catch (error) {
    console.error("Piyasa taraması yenilenemedi", error);
  }
}

updateClocks();
setInterval(updateClocks, 1000);
initializeMarketData();
loadAnalystBenchmark();
loadExcelNotes();
loadNotificationLog();
setInterval(refreshMarketData, 5 * 60 * 1000);

async function loadAutoPortfolio() {
  try {
    const response = await fetch("/api/auto-portfolio", { cache: "no-store" });
    const payload = await response.json();
    if (response.ok && payload.status === "ok") {
      renderAutoPortfolio(payload.portfolio);
    }
  } catch (error) {
    console.error("Auto portfolio load error:", error);
  }
}

function renderAutoPortfolio(portfolio) {
  if (!portfolio) return;
  const initial = Number(portfolio.initial_capital) || 10000;
  const cash = Number(portfolio.current_cash) || 0;
  const activePositions = Array.isArray(portfolio.positions) ? portfolio.positions : [];
  const history = Array.isArray(portfolio.history) ? portfolio.history : [];
  
  const equityValue = activePositions.reduce((sum, pos) => sum + (Number(pos.current_price) * Number(pos.qty)), 0);
  const totalBalance = cash + equityValue;
  const netPnl = totalBalance - initial;
  const netPnlPercent = (netPnl / initial) * 100;
  
  const closedCount = history.length;
  const wins = history.filter((trade) => Number(trade.pnl) > 0).length;
  const winRate = closedCount > 0 ? (wins / closedCount) * 100 : 0;
  
  const totalEl = document.getElementById("autoTotalBalance");
  if (totalEl) totalEl.textContent = formatCurrency(totalBalance);
  
  const cashEl = document.getElementById("autoCash");
  if (cashEl) cashEl.textContent = formatCurrency(cash);
  
  const equityEl = document.getElementById("autoEquityValue");
  if (equityEl) equityEl.textContent = formatCurrency(equityValue);
  
  const netPnlElement = document.getElementById("autoNetPnl");
  if (netPnlElement) {
    netPnlElement.textContent = `${netPnl >= 0 ? "+" : ""}${formatCurrency(netPnl)} (${netPnl >= 0 ? "+" : ""}${formatNumber(netPnlPercent)}%)`;
    netPnlElement.className = netPnl >= 0 ? "positive" : "negative";
  }
  
  const winRateEl = document.getElementById("autoWinRate");
  if (winRateEl) {
    winRateEl.textContent = closedCount > 0 
      ? `%${formatNumber(winRate, 1)} (${closedCount} işlem)` 
      : "—";
  }

  const activeBody = document.getElementById("autoActivePositionsRows");
  if (activeBody) {
    activeBody.innerHTML = activePositions.length ? activePositions.map((pos) => {
      const cost = Number(pos.cost) || (pos.entry_price * pos.qty);
      const currentVal = pos.current_price * pos.qty;
      const posPnl = currentVal - cost;
      const posPnlPercent = (posPnl / cost) * 100;
      return `
        <tr>
          <td><strong>${escapeHtml(pos.ticker)}</strong></td>
          <td>${escapeHtml(pos.entry_date)}</td>
          <td>${formatCurrency(pos.entry_price)}</td>
          <td>${formatCurrency(pos.current_price)}</td>
          <td>${pos.qty}</td>
          <td>${formatCurrency(cost)}</td>
          <td>${formatCurrency(currentVal)}</td>
          <td><span class="${posPnl >= 0 ? "positive" : "negative"}">${posPnl >= 0 ? "+" : ""}${formatNumber(posPnlPercent)}%</span></td>
          <td><span class="negative">${formatNumber(pos.stop_price)}</span></td>
          <td>${formatNumber(pos.tp1)} / ${formatNumber(pos.tp2)}</td>
          <td><span class="score-pill score-strong">${pos.model_score || 80}</span></td>
        </tr>
      `;
    }).join("") : `<tr><td colspan="11">Aktif pozisyon bulunmamaktadır. (Model >= 80 olan sinyaller otomatik alınır)</td></tr>`;
  }

  const closedBody = document.getElementById("autoClosedTradesRows");
  if (closedBody) {
    closedBody.innerHTML = history.length ? history.slice().reverse().map((trade) => {
      const pnl = Number(trade.pnl) || 0;
      const retPct = Number(trade.return_percent) || 0;
      return `
        <tr>
          <td><strong>${escapeHtml(trade.ticker)}</strong></td>
          <td>${escapeHtml(trade.entry_date)}</td>
          <td>${escapeHtml(trade.exit_date)}</td>
          <td>${formatCurrency(trade.entry_price)}</td>
          <td>${formatCurrency(trade.exit_price)}</td>
          <td>${trade.qty}</td>
          <td><span class="${pnl >= 0 ? "positive" : "negative"}">${pnl >= 0 ? "+" : ""}${formatCurrency(pnl)}</span></td>
          <td><span class="${pnl >= 0 ? "positive" : "negative"}">${pnl >= 0 ? "+" : ""}${formatNumber(retPct)}%</span></td>
          <td><span class="status-pill ${trade.outcome === "STOP" ? "negative" : "positive"}">${escapeHtml(trade.outcome)}</span></td>
        </tr>
      `;
    }).join("") : `<tr><td colspan="9">Gerçekleşen işlem kaydı bulunmamaktadır.</td></tr>`;
  }
}

document.getElementById("autoPortfolioReset")?.addEventListener("click", async () => {
  if (!confirm("Robot portföyü sıfırlamak ve 10K TL başlangıç bakiyesine dönmek istediğinizden emin misiniz?")) return;
  try {
    const response = await fetch("/api/auto-portfolio/reset", { method: "POST" });
    const payload = await response.json();
    if (response.ok && payload.status === "ok") {
      renderAutoPortfolio(payload.portfolio);
      toast.querySelector(".toast-icon").textContent = "↻";
      toast.querySelector("strong").textContent = "Portföy Sıfırlandı";
      toast.querySelector("small").textContent = "Robot portföy sıfırlandı, başlangıç bakiyesi 10.000 TL.";
      toast.classList.add("show");
      setTimeout(() => toast.classList.remove("show"), 3200);
    }
  } catch (error) {
    console.error("Auto portfolio reset error:", error);
  }
});
