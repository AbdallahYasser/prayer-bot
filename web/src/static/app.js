'use strict';

// ── Constants ────────────────────────────────────────────────────────────────

const COLORS = {
  none: '#334155',   // upcoming / no data (lighter gray)
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

let currentUser  = null;   // {user_id, first_name, timezone, language, isha_label, reminder_interval, city, country, calc_method_name}
let currentYear  = new Date().getFullYear();
let currentMonth = null;   // "YYYY-MM"
let monthData    = {};     // { "YYYY-MM-DD": entry }
let cal          = null;   // cal-heatmap instance

// ── Boot ─────────────────────────────────────────────────────────────────────

let botUsername = 'islamic_prayer_reminder_bot';  // fallback
let isDemoMode  = false;

(async function boot() {
  // Check if we should run in Demo Mode (e.g. opened via file://)
  if (!window.location.hostname || window.location.hostname === 'localhost' || window.location.protocol === 'file:') {
    isDemoMode = true;
    currentUser = { 
      first_name: "John", 
      language: "en", 
      isha_label: "Until Midnight", 
      reminder_interval: 5,
      city: "Cairo",
      country: "Egypt",
      calc_method_name: "Egyptian General Authority of Survey"
    };
    
    const now = new Date();
    currentMonth = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`;
    
    showDashboard();
    return;
  }

  try {
    const cfgRes = await fetch('/api/config');
    if (cfgRes.ok) {
      const cfg = await cfgRes.json();
      if (cfg.bot_username) botUsername = cfg.bot_username;
    }
  } catch { /* use fallback */ }

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

  const s = document.createElement('script');
  s.src           = 'https://telegram.org/js/telegram-widget.js?22';
  s.dataset.telegramLogin   = botUsername;
  s.dataset.size            = 'large';
  s.dataset.onauth          = 'onTelegramAuth(user)';
  s.dataset.requestAccess   = 'write';
  document.getElementById('telegram-login-widget').appendChild(s);
}

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

function toggleLanguage() {
  if (!currentUser) return;
  currentUser.language = currentUser.language === 'ar' ? 'en' : 'ar';
  showDashboard();
}

async function logout() {
  await fetch('/api/logout', { method: 'POST' });
  currentUser = null;
  showLogin();
}

// ── Dashboard ────────────────────────────────────────────────────────────────

async function showDashboard() {
  hide('login-screen');
  show('dashboard');

  // Reset defaults
  document.body.setAttribute('dir', 'ltr');
  document.documentElement.setAttribute('lang', 'en');

  // Header
  document.getElementById('user-name').textContent = currentUser.first_name;
  document.getElementById('user-location').textContent = `${currentUser.city}, ${currentUser.country}`;
  document.getElementById('lang-toggle').textContent = currentUser.language === 'ar' ? 'EN' : 'AR';
  document.getElementById('reminder-bell').textContent = currentUser.reminders_on ? '🔔' : '🔕';

  // RTL if Arabic
  if (currentUser.language === 'ar') {
    document.body.setAttribute('dir', 'rtl');
    document.documentElement.setAttribute('lang', 'ar');
    setLabelsAr();
  } else {
    setLabelsEn();
  }

  // Settings bar (after labels are set)
  document.getElementById('setting-calc').textContent     = t(currentUser.calc_method_name);
  document.getElementById('setting-isha').textContent     = t(currentUser.isha_label);
  document.getElementById('setting-interval').textContent = currentUser.reminder_interval;

  await loadStats();
  await loadToday();
  await loadHeatmap();

  if (!currentMonth) {
    currentMonth = localToday().slice(0, 7);  // "YYYY-MM"
  }
}

// ── Stats ────────────────────────────────────────────────────────────────────

async function loadStats() {
  const res   = await api('/api/stats');
  const stats = await res.json();
  const lang  = currentUser.language;
  const daysLabel = lang === 'ar' ? 'يوم' : 'day(s)';

  setText('stat-streak', `${stats.current_streak} ${daysLabel}`);
  setText('stat-best',   `${stats.best_streak} ${daysLabel}`);
  setText('stat-week',   pct(stats.week_prayed, stats.week_total));
  setText('stat-month',  pct(stats.month_prayed, stats.month_total));
  setText('stat-total',  stats.total_prayed);
}

function pct(prayed, total) {
  if (!total) return '—';
  return `${Math.round(prayed / total * 100)}%`;
}

// ── Today ─────────────────────────────────────────────────────────────────────

const PRAYER_NAMES_AR = {
  Fajr: 'الفجر', Dhuhr: 'الظهر', Asr: 'العصر', Maghrib: 'المغرب', Isha: 'العشاء',
};

async function loadToday() {
  const section = document.getElementById('today-section');
  try {
    const res  = await api('/api/today');
    const data = await res.json();

    const lang = currentUser.language;

    if (!data.has_times) {
      const title = lang === 'ar' ? 'اليوم' : 'Today';
      document.getElementById('today-title').textContent = title;
      const container = document.getElementById('today-prayers');
      container.innerHTML = '';
      const msg = document.createElement('p');
      msg.className = 'today-no-times';
      msg.textContent = lang === 'ar'
        ? 'لم يتم جلب أوقات الصلاة بعد. افتح التطبيق في تيليغرام أولاً.'
        : 'Prayer times not fetched yet. Open the bot in Telegram first.';
      container.appendChild(msg);
      return;
    }

    // /api/today returns prayers as an array [{name, time, status}]
    // Convert to the object format showDayData uses, and keep times separately
    const prayersObj = {};
    const timesObj   = {};
    for (const p of data.prayers) {
      prayersObj[p.name] = p.status;
      timesObj[p.name]   = p.time;
    }
    showDayData(data.date, { prayers: prayersObj, times: timesObj }, data.date_display);
  } catch {
    section.classList.add('hidden');
  }
}

// ── Heatmap ───────────────────────────────────────────────────────────────────

async function loadHeatmap() {
  document.getElementById('year-label').textContent = currentYear;

  const res  = await api(`/api/heatmap?year=${currentYear}`);
  const data = await res.json();

  const dataset = data.days.map(d => ({ date: d.date, value: d.prayed_count }));

  if (cal) { cal.destroy(); }

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
      locale: { weekStart: 6 },  // Saturday start
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
    subDomain: { type: 'day', radius: 2, width: 13, height: 13, gutter: 3 },
    itemSelector: '#cal',
  });
}

async function changeYear(delta) {
  currentYear += delta;
  await loadHeatmap();
}

// Click on a month label in the heatmap → open calendar modal for that month
document.addEventListener('click', e => {
  const label = e.target.closest('.ch-domain-text');
  if (!label) return;
  const domain = label.closest('[data-key]') || label.parentElement?.closest('[data-key]');
  if (!domain) return;
  const key = domain.dataset.key;
  if (!key) return;
  const d = new Date(isNaN(key) ? key : Number(key));
  const ym = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`;
  currentMonth = ym;
  show('calendar-modal');
  loadMonthDetail(ym);
});

// ── Modal & Calendar logic ────────────────────────────────────────────────────

function openCalendar() {
  show('calendar-modal');
  if (currentMonth) loadMonthDetail(currentMonth);
}

function closeCalendar() {
  hide('calendar-modal');
}

async function changeMonth(delta) {
  if (!currentMonth) return;
  const [y, m] = currentMonth.split('-').map(Number);
  const date = new Date(y, m - 1 + delta, 1);
  const ym = `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}`;
  await loadMonthDetail(ym);
}

async function loadMonthDetail(yearMonth) {
  currentMonth = yearMonth;

  const res  = await api(`/api/month?m=${yearMonth}`);
  const data = await res.json();

  const [y, m] = yearMonth.split('-').map(Number);
  const lang   = currentUser.language;
  const title  = lang === 'ar'
    ? `${MONTHS_AR[m - 1]} ${y}`
    : `${MONTHS_EN[m - 1]} ${y}`;

  document.getElementById('month-detail-title').textContent = title;

  monthData = {};
  for (const d of data.days) monthData[d.date] = d;

  const firstDow  = new Date(y, m - 1, 1).getDay(); // 0=Sun…6=Sat
  const satFirst  = (firstDow + 1) % 7;
  const daysInMonth = new Date(y, m, 0).getDate();
  const today     = localToday();

  const grid = document.getElementById('month-grid');
  grid.innerHTML = '';

  const headers = lang === 'ar' ? DAYS_AR : DAYS_EN;
  for (const h of headers) {
    const el = document.createElement('div');
    el.className = 'day-header';
    el.textContent = h;
    grid.appendChild(el);
  }

  for (let i = 0; i < satFirst; i++) {
    const el = document.createElement('div');
    el.className = 'day-cell empty';
    grid.appendChild(el);
  }

  for (let day = 1; day <= daysInMonth; day++) {
    const dateStr = `${y}-${String(m).padStart(2,'0')}-${String(day).padStart(2,'0')}`;
    const entry   = monthData[dateStr];
    const isFuture = dateStr > today;
    const isToday  = dateStr === today;

    const cell = document.createElement('div');
    cell.className = 'day-cell';
    if (isToday) cell.classList.add('is-today');

    if (isFuture) {
      cell.classList.add('future');
      cell.innerHTML = `<span class="day-num">${day}</span>`;
    } else if (!entry) {
      cell.style.background = COLORS.none;
      cell.innerHTML = `<span class="day-num">${day}</span>`;
    } else {
      const count = entry.prayed_count;
      cell.style.background = COLORS[count] || COLORS.none;
      cell.innerHTML = `<span class="day-num">${day}</span><span class="day-count">${count}/5</span>`;
    }

    cell.addEventListener('click', () => {
      if (isFuture) return;
      showDayData(dateStr, entry || { prayers: {} });
      closeCalendar();
    });
    grid.appendChild(cell);
  }
}

// dateDisplay is an optional pre-formatted string (passed from loadToday).
// For month-grid clicks, it is omitted and computed from dateStr.
// entry.prayers can be:
//   - object {Fajr: "prayed", ...}  (from /api/month grid click)
//   - already extracted to that format (from loadToday, which converts the array)
// entry.times is optional: {Fajr: "04:32", ...} (only present for today)
function showDayData(dateStr, entry, dateDisplay) {
  const lang = currentUser.language;
  const today = localToday();
  const isToday = dateStr === today;

  if (!dateDisplay) {
    const d = new Date(dateStr + 'T12:00:00');   // noon avoids timezone-day-shift
    dateDisplay = d.toLocaleDateString(lang === 'ar' ? 'ar-EG' : 'en-GB', {
      weekday: 'long', day: 'numeric', month: 'long', year: 'numeric',
    });
  }

  const title = isToday
    ? (lang === 'ar' ? 'اليوم — ' : 'Today — ') + dateDisplay
    : dateDisplay;
  document.getElementById('today-title').textContent = title;

  const container = document.getElementById('today-prayers');
  container.innerHTML = '';

  if (!entry || !entry.prayers) {
    const msg = document.createElement('p');
    msg.className = 'today-no-times';
    msg.textContent = lang === 'ar' ? 'لا توجد بيانات لهذا اليوم' : 'No data for this day';
    container.appendChild(msg);
    return;
  }

  const prayers = entry.prayers || {};
  const times   = entry.times   || {};

  for (const p of PRAYERS) {
    const status = prayers[p];
    const row = document.createElement('div');
    row.className = `prayer-row status-${status || 'pending'}`;

    const icon = status === 'prayed' ? '✅' : status === 'missed' ? '❌' : '⏳';
    const name = lang === 'ar' ? (PRAYER_NAMES_AR[p] || p) : p;
    const time = times[p];

    row.innerHTML = `
      <span class="prayer-row-status">${icon}</span>
      <span class="prayer-row-name">${name}</span>
      ${time ? `<span class="prayer-row-time">${time}</span>` : ''}
    `;
    container.appendChild(row);
  }
}

// ── Localisation helpers ─────────────────────────────────────────────────────

const TRANSLATIONS = {
  ar: {
    "Until Midnight": "حتى منتصف الليل",
    "One Third of Night": "ثلث الليل",
    "Until Fajr": "حتى الفجر",
    "Egyptian General Authority of Survey": "الهيئة المصرية العامة للمساحة",
    "University of Islamic Sciences, Karachi": "جامعة العلوم الإسلامية، كراتشي",
    "Islamic Society of North America (ISNA)": "الجمعية الإسلامية لأمريكا الشمالية",
    "Muslim World League": "رابطة العالم الإسلامي",
    "Umm al-Qura University, Makkah": "جامعة أم القرى، مكة",
    "Institute of Geophysics, University of Tehran": "معهد الجيوفيزياء، جامعة طهران",
    "Gulf Region": "منطقة الخليج",
    "Kuwait": "الكويت",
    "Qatar": "قطر",
    "Majlis Ugama Islam Singapura, Singapore": "المجلس الإسلامي السنغافوري",
    "Union Organization Islamic de France": "اتحاد المنظمات الإسلامية في فرنسا",
    "Diyanet İşleri Başkanlığı, Turkey": "رئاسة الشؤون الدينية، تركيا",
    "Spiritual Administration of Muslims of Russia": "الإدارة الدينية لمسلمي روسيا"
  }
};

function t(val) {
  if (!currentUser || currentUser.language !== 'ar') return val;
  return TRANSLATIONS.ar[val] || val;
}

function setLabelsAr() {
  setText('label-streak', 'السلسلة الحالية');
  setText('label-best',   'أفضل سلسلة');
  setText('label-week',   'هذا الأسبوع');
  setText('label-month',  'هذا الشهر');
  setText('label-total',  'إجمالي الصلوات');
  setText('label-reminders', 'كل');
  setText('label-mins', 'دقيقة');
  setText('desc-calc', 'طريقة حساب الأوقات');
  setText('desc-isha', 'نافذة تنبيهات صلاة العشاء');
  setText('desc-interval', 'تكرار التنبيهات لكل صلاة');
  setText('leg-none', 'لم يحن بعد');
  setText('leg-heatmap-none', 'لا بيانات');
}

function setLabelsEn() {
  setText('label-streak', 'Current streak');
  setText('label-best',   'Best streak');
  setText('label-week',   'This week');
  setText('label-month',  'This month');
  setText('label-total',  'All time');
  setText('label-reminders', 'Every');
  setText('label-mins', 'min');
  setText('desc-calc', 'Calculation method');
  setText('desc-isha', 'Isha reminder window');
  setText('desc-interval', 'Frequency of notifications');
  setText('leg-none', 'Upcoming');
  setText('leg-heatmap-none', 'No data');
}

// ── Utilities ────────────────────────────────────────────────────────────────

// Returns today as "YYYY-MM-DD" in the user's timezone (not UTC).
// Fixes the bug where UTC midnight ≠ local midnight for users in UTC+N zones.
function localToday() {
  try {
    const tz = (currentUser && currentUser.timezone) || 'UTC';
    // en-CA locale produces YYYY-MM-DD format which is exactly what we need
    return new Intl.DateTimeFormat('en-CA', { timeZone: tz }).format(new Date());
  } catch {
    return new Date().toISOString().slice(0, 10);
  }
}

async function api(url) {
  if (isDemoMode) return mockApi(url);
  const res = await fetch(url, { credentials: 'include' });
  if (res.status === 401) throw new Error('unauthenticated');
  if (!res.ok) throw new Error(`API error ${res.status}`);
  return res;
}

function mockApi(url) {
  let data = {};
  if (url.includes('/api/stats')) {
    data = { current_streak: 7, best_streak: 15, week_prayed: 18, week_total: 25, month_prayed: 87, month_total: 110, total_prayed: 432 };
  } else if (url.includes('/api/today')) {
    data = { date: "2026-04-12", date_display: "Sunday, 12 April 2026", has_times: true, prayers: [
      { name: "Fajr",    time: "04:28", status: "prayed"  },
      { name: "Dhuhr",   time: "12:02", status: "prayed"  },
      { name: "Asr",     time: "15:27", status: "missed"  },
      { name: "Maghrib", time: "18:49", status: "pending" },
      { name: "Isha",    time: "20:18", status: "pending" },
    ]};
  } else if (url.includes('/api/heatmap')) {
    const year = parseInt(url.split('year=')[1]) || 2026;
    const days = [];
    for (let m = 1; m <= 12; m++) {
      const daysInMonth = new Date(year, m, 0).getDate();
      for (let d = 1; d <= daysInMonth; d++) {
        const dateStr = `${year}-${String(m).padStart(2,'0')}-${String(d).padStart(2,'0')}`;
        if (dateStr > new Date().toISOString().slice(0,10)) break;
        days.push({ date: dateStr, prayed_count: Math.floor(Math.random() * 6), total: 5 });
      }
    }
    data = { year, days };
  } else if (url.includes('/api/month')) {
    const days = [];
    const ym = url.split('=')[1] || "2026-04";
    const [y, m] = ym.split('-');
    for (let i = 1; i <= 30; i++) {
      const dateStr = `${y}-${m}-${String(i).padStart(2, '0')}`;
      const count = Math.floor(Math.random() * 6);
      const prayers = {};
      PRAYERS.forEach((p, idx) => { prayers[p] = idx < count ? "prayed" : (idx < count + 1 ? "missed" : "pending"); });
      days.push({ date: dateStr, prayed_count: count, total: 5, prayers });
    }
    data = { month: ym, days };
  }
  return { ok: true, json: () => Promise.resolve(data) };
}

function show(id) { document.getElementById(id).classList.remove('hidden'); }
function hide(id) { document.getElementById(id).classList.add('hidden'); }
function setText(id, val) {
  const el = document.getElementById(id);
  if (el) el.textContent = val;
}
