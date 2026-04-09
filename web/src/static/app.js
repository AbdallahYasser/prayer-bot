'use strict';

// ── Constants ────────────────────────────────────────────────────────────────

const COLORS = {
  none: '#1e293b',   // no data / future
  0:    '#ef4444',   // 0/5  red
  1:    '#a16207',   // 1/5  brown
  2:    '#f97316',   // 2/5  orange
  3:    '#eab308',   // 3/5  yellow
  4:    '#3b82f6',   // 4/5  blue
  5:    '#22c55e',   // 5/5  green
};

const PRAYERS   = ['Fajr', 'Dhuhr', 'Asr', 'Maghrib', 'Isha'];
const DAYS_AR   = ['سب', 'أح', 'إث', 'ثلا', 'أرب', 'خم', 'جم'];
const DAYS_EN   = ['Sa', 'Su', 'Mo', 'Tu', 'We', 'Th', 'Fr'];
const MONTHS_EN = ['January','February','March','April','May','June',
                   'July','August','September','October','November','December'];
const MONTHS_AR = ['يناير','فبراير','مارس','أبريل','مايو','يونيو',
                   'يوليو','أغسطس','سبتمبر','أكتوبر','نوفمبر','ديسمبر'];

// ── State ────────────────────────────────────────────────────────────────────

let currentUser  = null;   // {user_id, first_name, timezone, language, isha_label, reminder_interval}
let currentYear  = new Date().getFullYear();
let cal          = null;   // cal-heatmap instance
let heatmapData  = {};     // { "YYYY-MM-DD": prayed_count }

// ── Boot ─────────────────────────────────────────────────────────────────────

(async function boot() {
  try {
    const res = await api('/api/me');
    currentUser = await res.json();
    showDashboard();
  } catch {
    showLogin();
  }
})();

// ── Auth ─────────────────────────────────────────────────────────────────────

function showLogin() {
  show('login-screen');
  hide('dashboard');

  // Inject Telegram Login Widget script dynamically
  const s = document.createElement('script');
  s.src           = 'https://telegram.org/js/telegram-widget.js?22';
  s.dataset.telegramLogin   = getTelegramBotUsername();
  s.dataset.size            = 'large';
  s.dataset.onauth          = 'onTelegramAuth(user)';
  s.dataset.requestAccess   = 'write';
  document.getElementById('telegram-login-widget').appendChild(s);
}

// Called by Telegram widget after user approves
window.onTelegramAuth = async function(tgUser) {
  try {
    const res = await fetch('/api/auth/telegram', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(tgUser),
    });
    if (!res.ok) {
      const err = await res.json();
      alert(err.detail || 'Login failed');
      return;
    }
    const meRes = await api('/api/me');
    currentUser = await meRes.json();
    showDashboard();
  } catch (e) {
    alert('Login error: ' + e.message);
  }
};

async function logout() {
  await fetch('/api/logout', { method: 'POST' });
  currentUser = null;
  if (cal) { cal.destroy(); cal = null; }
  showLogin();
}

// ── Dashboard ────────────────────────────────────────────────────────────────

async function showDashboard() {
  hide('login-screen');
  show('dashboard');

  // Header
  document.getElementById('user-name').textContent = currentUser.first_name;

  // Settings bar
  document.getElementById('setting-isha').textContent     = currentUser.isha_label;
  document.getElementById('setting-interval').textContent = currentUser.reminder_interval;

  // RTL if Arabic
  if (currentUser.language === 'ar') {
    document.body.setAttribute('dir', 'rtl');
    document.documentElement.setAttribute('lang', 'ar');
    setLabelsAr();
  }

  await loadStats();
  await loadHeatmap();
}

// ── Stats ────────────────────────────────────────────────────────────────────

async function loadStats() {
  const res   = await api('/api/stats');
  const stats = await res.json();
  const lang  = currentUser.language;
  const days  = lang === 'ar' ? 'يوم' : 'day(s)';

  setText('stat-streak', `${stats.current_streak} ${days}`);
  setText('stat-best',   `${stats.best_streak} ${days}`);
  setText('stat-week',   pct(stats.week_prayed, stats.week_total));
  setText('stat-month',  pct(stats.month_prayed, stats.month_total));
  setText('stat-total',  stats.total_prayed);
}

function pct(prayed, total) {
  if (!total) return '—';
  return `${Math.round(prayed / total * 100)}%`;
}

// ── Heatmap ──────────────────────────────────────────────────────────────────

async function loadHeatmap() {
  document.getElementById('year-label').textContent = currentYear;

  const res  = await api(`/api/heatmap?year=${currentYear}`);
  const data = await res.json();

  // Build lookup: date → prayed_count
  heatmapData = {};
  for (const d of data.days) {
    heatmapData[d.date] = d.prayed_count;
  }

  if (cal) { cal.destroy(); }

  // Build dataset for cal-heatmap: array of {date, value}
  const dataset = Object.entries(heatmapData).map(([date, value]) => ({
    date, value,
  }));

  cal = new CalHeatmap();
  cal.paint({
    data: {
      source: dataset,
      x: 'date',
      y: 'value',
      defaultValue: null,
    },
    date: {
      start: new Date(`${currentYear}-01-01`),
      locale: { weekStart: 6 },  // 6 = Saturday
    },
    range: 12,
    scale: {
      color: {
        type: 'threshold',
        range: [COLORS.none, COLORS[0], COLORS[1], COLORS[2], COLORS[3], COLORS[4], COLORS[5]],
        domain: [0, 1, 2, 3, 4, 5],
      },
    },
    domain: { type: 'month', label: { text: 'MMM', textAlign: 'start', position: 'top' } },
    subDomain: {
      type: 'day',
      radius: 2,
      width: 13,
      height: 13,
      gutter: 3,
    },
    itemSelector: '#cal',
  });
}

async function changeYear(delta) {
  currentYear += delta;
  hide('month-detail');
  await loadHeatmap();
}

// ── Month detail ─────────────────────────────────────────────────────────────

async function loadMonthDetail(yearMonth) {
  // yearMonth = "YYYY-MM"
  const res  = await api(`/api/month?m=${yearMonth}`);
  const data = await res.json();

  const [y, m] = yearMonth.split('-').map(Number);
  const lang   = currentUser.language;
  const title  = lang === 'ar'
    ? `${MONTHS_AR[m - 1]} ${y}`
    : `${MONTHS_EN[m - 1]} ${y}`;

  document.getElementById('month-detail-title').textContent = title;

  const byDate = {};
  for (const d of data.days) byDate[d.date] = d;

  // First day of month: 0=Mon…6=Sun → convert to Sat=0 grid
  const firstDow  = new Date(y, m - 1, 1).getDay(); // 0=Sun…6=Sat
  // convert to Sat=0: Sun=1, Mon=2…Fri=6
  const satFirst  = (firstDow + 1) % 7;
  const daysInMonth = new Date(y, m, 0).getDate();
  const today     = new Date().toISOString().slice(0, 10);

  const grid = document.getElementById('month-grid');
  grid.innerHTML = '';

  // Day-of-week headers
  const headers = lang === 'ar' ? DAYS_AR : DAYS_EN;
  for (const h of headers) {
    const el = document.createElement('div');
    el.className = 'day-header';
    el.textContent = h;
    grid.appendChild(el);
  }

  // Empty padding cells
  for (let i = 0; i < satFirst; i++) {
    const el = document.createElement('div');
    el.className = 'day-cell empty';
    grid.appendChild(el);
  }

  // Day cells
  for (let day = 1; day <= daysInMonth; day++) {
    const dateStr = `${y}-${String(m).padStart(2,'0')}-${String(day).padStart(2,'0')}`;
    const entry   = byDate[dateStr];
    const isFuture = dateStr > today;

    const cell = document.createElement('div');
    cell.className = 'day-cell';

    if (isFuture) {
      cell.classList.add('future');
      cell.innerHTML = `<span class="day-num">${day}</span>`;
    } else if (!entry) {
      cell.style.background = COLORS.none;
      cell.innerHTML = `<span class="day-num">${day}</span>`;
    } else {
      const count = entry.prayed_count;
      cell.style.background = COLORS[count] || COLORS.none;

      // Tooltip with individual prayer statuses
      const prayers  = entry.prayers || {};
      const tipLines = PRAYERS.map(p => {
        const status = prayers[p];
        const icon   = status === 'prayed' ? '✅' : status === 'missed' ? '❌' : '⏳';
        return `${icon} ${p}`;
      }).join('<br>');

      cell.innerHTML = `
        <span class="day-num">${day}</span>
        <span class="day-count">${count}/5</span>
        <div class="tooltip">${tipLines}</div>
      `;
    }

    cell.addEventListener('click', () => loadMonthDetail(yearMonth));
    grid.appendChild(cell);
  }

  show('month-detail');
  document.getElementById('month-detail').scrollIntoView({ behavior: 'smooth', block: 'start' });
}

// Hook cal-heatmap click → month detail
// cal-heatmap v4 emits a custom event on domain click
document.addEventListener('click', e => {
  const label = e.target.closest('.ch-domain-text');
  if (!label) return;
  // The label text is like "Apr" — find which year-month it represents
  // by reading the data-key attribute cal-heatmap sets on the parent domain
  const domain = label.closest('[data-key]') || label.parentElement?.closest('[data-key]');
  if (!domain) return;
  const key = domain.dataset.key;  // e.g. "2026-04-01T00:00:00.000Z" or unix ms
  if (!key) return;
  const d = new Date(isNaN(key) ? key : Number(key));
  const ym = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`;
  loadMonthDetail(ym);
});

// ── Localisation helpers ─────────────────────────────────────────────────────

function setLabelsAr() {
  setText('label-streak', 'السلسلة الحالية');
  setText('label-best',   'أفضل سلسلة');
  setText('label-week',   'هذا الأسبوع');
  setText('label-month',  'هذا الشهر');
  setText('label-total',  'إجمالي الصلوات');
  document.querySelector('.settings-bar span:last-child').innerHTML =
    '🔁 تكرار كل <span id="setting-interval">' +
    (currentUser.reminder_interval || '—') + '</span> دقيقة';
}

// ── Utilities ────────────────────────────────────────────────────────────────

async function api(url) {
  const res = await fetch(url, { credentials: 'include' });
  if (res.status === 401) throw new Error('unauthenticated');
  if (!res.ok) throw new Error(`API error ${res.status}`);
  return res;
}

function show(id) { document.getElementById(id).classList.remove('hidden'); }
function hide(id) { document.getElementById(id).classList.add('hidden'); }
function setText(id, val) {
  const el = document.getElementById(id);
  if (el) el.textContent = val;
}

function getTelegramBotUsername() {
  // Injected by the server as a meta tag
  const meta = document.querySelector('meta[name="bot-username"]');
  return meta ? meta.content : 'islamic_prayer_reminder_bot';
}
