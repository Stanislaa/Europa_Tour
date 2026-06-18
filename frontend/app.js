// ============================================================
//  Европа-Тур — клиентская логика (SPA без фреймворков)
// ============================================================

// ---------------- Конфиг ----------------
const API = window.API_BASE
  || ((location.origin.includes('localhost') || location.origin.includes('127.0.0.1'))
        ? 'http://localhost:8000' : '');

// ---------------- Утилиты ----------------
const $  = (sel, ctx = document) => ctx.querySelector(sel);
const $$ = (sel, ctx = document) => [...ctx.querySelectorAll(sel)];

const fmt = (n) => new Intl.NumberFormat('ru-RU').format(Math.round(n));

const BOARD = {
  RO: 'Без питания', BB: 'Завтраки', HB: 'Полупансион',
  FB: 'Полный пансион', AI: 'Всё включено', UAI: 'Ультра всё включено',
};
const STATUS = {
  created: 'Ожидает оплаты', paid: 'Оплачено',
  confirmed: 'Подтверждён', cancelled: 'Отменён',
};

function esc(s) {
  return String(s == null ? '' : s)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function starsHTML(n) {
  n = Math.max(0, Math.min(5, +n || 0));
  return `<span class="stars-on">${'★'.repeat(n)}</span>` +
         `<span class="stars-off">${'★'.repeat(5 - n)}</span>`;
}

const HEART_SVG = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
  <path d="M20.8 4.6a5.5 5.5 0 0 0-7.8 0L12 5.6l-1-1a5.5 5.5 0 1 0-7.8 7.8l1 1L12 21l7.8-7.6 1-1a5.5 5.5 0 0 0 0-7.8z"/></svg>`;

// ---------------- Тема ----------------
function applyTheme(theme) {
  document.documentElement.setAttribute('data-theme', theme);
  try { localStorage.setItem('theme', theme); } catch (e) {}
}
function toggleTheme() {
  const cur = document.documentElement.getAttribute('data-theme') || 'dark';
  applyTheme(cur === 'dark' ? 'light' : 'dark');
}

// ---------------- Авторизация / хранилище ----------------
function token() { return localStorage.getItem('token'); }
function userData() {
  try { return JSON.parse(localStorage.getItem('user') || 'null'); } catch { return null; }
}
function setAuth(t, u) {
  if (t) {
    localStorage.setItem('token', t);
    localStorage.setItem('user', JSON.stringify(u));
  } else {
    localStorage.removeItem('token');
    localStorage.removeItem('user');
    favIds = null;
  }
  renderAuth();
}

async function api(path, opts = {}) {
  const headers = { 'Content-Type': 'application/json', ...(opts.headers || {}) };
  if (token()) headers.Authorization = `Bearer ${token()}`;
  const resp = await fetch(API + path, { ...opts, headers });
  // Истёкшая сессия: разлогиниваем и уводим на вход только для запросов
  // с токеном. На странице входа токена нет, поэтому ответ 401 от
  // /api/auth/login пройдёт дальше и покажет реальную причину
  // («Неверный email или пароль»), а не общее «Требуется авторизация».
  if (resp.status === 401 && token()) {
    setAuth(null, null);
    location.hash = '#/login';
    throw new Error('Требуется авторизация');
  }
  const data = await resp.json().catch(() => ({}));
  if (!resp.ok) throw new Error(data.detail || 'Ошибка запроса');
  return data;
}

function toast(msg, type = '') {
  const t = $('#toast');
  const icon = type === 'success' ? '✓' : type === 'error' ? '✕' : 'ℹ';
  t.innerHTML = `<span>${icon}</span><span>${esc(msg)}</span>`;
  t.className = `toast show ${type}`;
  clearTimeout(t._timer);
  t._timer = setTimeout(() => t.classList.remove('show'), 3400);
}

function initials(u) {
  const a = (u?.first_name || u?.email || '?').trim()[0] || '?';
  const b = (u?.last_name || '').trim()[0] || '';
  return (a + b).toUpperCase();
}

// ---------------- Шапка: блок авторизации ----------------
function renderAuth() {
  const area = $('#auth-area');
  const u = userData();
  if (u) {
    area.innerHTML = `
      <a href="#/profile" class="user-chip" title="Личный кабинет">
        <span class="user-avatar">${esc(initials(u))}</span>
        <span class="user-name">${esc(u.first_name || u.email)}</span>
      </a>
      <button class="btn btn-ghost btn-sm" id="btn-logout">Выйти</button>
    `;
    $('#btn-logout').onclick = () => {
      setAuth(null, null);
      toast('Вы вышли из аккаунта');
      location.hash = '#/';
    };
  } else {
    area.innerHTML = `
      <a href="#/login" class="btn btn-ghost btn-sm">Войти</a>
      <a href="#/register" class="btn btn-primary btn-sm">Регистрация</a>
    `;
  }
}

// ---------------- Избранное: кеш id ----------------
let favIds = null;
async function loadFavIds(force = false) {
  if (!token()) { favIds = new Set(); return favIds; }
  if (favIds && !force) return favIds;
  try {
    const { ids } = await api('/api/favorites/ids');
    favIds = new Set(ids);
  } catch { favIds = new Set(); }
  return favIds;
}

async function toggleFavorite(tourId, btn) {
  if (!token()) {
    toast('Войдите, чтобы добавлять туры в избранное');
    location.hash = '#/login';
    return;
  }
  await loadFavIds();
  const isFav = favIds.has(tourId);
  try {
    if (isFav) {
      await api('/api/favorites/' + tourId, { method: 'DELETE' });
      favIds.delete(tourId);
      btn.classList.remove('is-active');
      btn.title = 'Добавить в избранное';
      toast('Тур убран из избранного');
    } else {
      await api('/api/favorites/' + tourId, { method: 'POST' });
      favIds.add(tourId);
      btn.classList.add('is-active');
      btn.title = 'Убрать из избранного';
      toast('Тур добавлен в избранное', 'success');
    }
  } catch (e) {
    toast(e.message, 'error');
  }
}

// ---------------- Роутер ----------------
const routes = {
  '/':            renderCatalog,
  '/login':       renderLogin,
  '/register':    renderRegister,
  '/profile':     renderProfile,
  '/profile/edit':renderProfileEdit,
  '/favorites':   renderFavorites,
};

// запоминаем, к какой секции скроллить после рендера главной
let pendingScroll = null;

async function router() {
  closeMenu();
  const hash = location.hash.slice(1) || '/';
  const [path, ...params] = hash.split('/').filter(Boolean);

  // активная ссылка в навигации
  $$('.nav a').forEach(a => {
    const h = a.getAttribute('href');
    a.classList.toggle('active', h === '#/' + (path || '') || (h === '#/' && !path));
  });

  const app = $('#app');
  app.innerHTML = '';

  if (!path) { window.scrollTo(0, 0); return renderCatalog(app); }
  window.scrollTo(0, 0);
  if (path === 'tour'    && params[0]) return renderTour(app, params[0]);
  if (path === 'book'    && params[0]) return renderBooking(app, params[0]);
  if (path === 'pay'     && params[0]) return renderPayment(app, params[0]);
  if (path === 'profile' && params[0] === 'edit') return renderProfileEdit(app);
  if (routes['/' + path])             return routes['/' + path](app);

  app.innerHTML = `<div class="container page-pad"><div class="empty">
    <span class="empty-icon">🧭</span>
    <strong>Страница не найдена</strong>
    <a href="#/">Вернуться на главную</a></div></div>`;
}

function navigate(hash) { location.hash = hash; }
window.addEventListener('hashchange', router);

// плавный скролл к секции на главной
function scrollToSection(id) {
  const el = document.getElementById(id);
  if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

// ---------------- Каталог ----------------
let countriesCache = null;
async function loadCountries() {
  if (!countriesCache) countriesCache = await api('/api/countries');
  return countriesCache;
}

function tourCardHTML(t) {
  const isFav = favIds && favIds.has(t.id);
  return `
    <article class="card">
      <div class="card-media">
        <img class="card-img" src="${esc(t.image_url || '')}" alt="${esc(t.title)}" loading="lazy"
             onerror="this.onerror=null;this.removeAttribute('src');">
        <div class="card-badge">${starsHTML(t.stars)}</div>
        <button class="fav-btn ${isFav ? 'is-active' : ''}" data-fav="${t.id}"
                title="${isFav ? 'Убрать из избранного' : 'Добавить в избранное'}"
                aria-label="В избранное">${HEART_SVG}</button>
      </div>
      <div class="card-body">
        <h3 class="card-title"><a href="#/tour/${t.id}">${esc(t.title)}</a></h3>
        <div class="card-hotel" title="${esc(t.hotel)}">
          <span class="pin">⌖</span>${esc(t.hotel)}
        </div>
        <div class="card-sub">${esc(t.city)}, ${esc(t.country)}</div>
        <div class="card-tags">
          <span class="tag tag-board">${esc(BOARD[t.board_type] || t.board_type)}</span>
          <span class="tag">${t.nights_min}–${t.nights_max} ночей</span>
        </div>
        <div class="card-foot">
          <div>
            <div class="price-value">${fmt(t.price_per_night)} ₽</div>
            <div class="price-label">за ночь / чел.</div>
          </div>
          <a class="btn btn-primary btn-sm" href="#/tour/${t.id}">Подробнее</a>
        </div>
      </div>
    </article>`;
}

function bindFavButtons(grid) {
  $$('.fav-btn', grid).forEach(btn => {
    btn.onclick = (e) => {
      e.preventDefault(); e.stopPropagation();
      toggleFavorite(+btn.dataset.fav, btn);
    };
  });
}

function renderTourGrid(grid, items) {
  if (!items.length) {
    grid.innerHTML = `<div class="empty"><span class="empty-icon">🔍</span>
      <strong>Туров не найдено</strong>
      Попробуйте изменить параметры поиска или сбросить фильтры.</div>`;
    return;
  }
  grid.innerHTML = items.map(tourCardHTML).join('');
  $$('.card', grid).forEach((c, i) => { c.style.animationDelay = (i * 0.05) + 's'; });
  bindFavButtons(grid);
}

function gridSkeleton(grid, count = 6) {
  grid.innerHTML = Array.from({ length: count }, () => '<div class="skeleton-card"></div>').join('');
}

async function renderCatalog(app) {
  app.appendChild($('#tpl-catalog').content.cloneNode(true));
  await loadFavIds();

  const countrySelect = $('#f-country');
  try {
    const countries = await loadCountries();
    countries.forEach(c => {
      const o = document.createElement('option');
      o.value = c.id; o.textContent = c.name;
      countrySelect.appendChild(o);
    });
  } catch (e) { /* каталог всё равно загрузится */ }

  ['#f-min', '#f-max'].forEach(sel => {
    $(sel).addEventListener('input', e => {
      e.target.value = e.target.value.replace(/[^\d]/g, '');
    });
  });

  const loadTours = async () => {
    const params = new URLSearchParams();
    const q = $('#f-query').value.trim();
    if (q) params.set('q', q);
    if ($('#f-country').value) params.set('country_id', $('#f-country').value);
    if ($('#f-stars').value)   params.set('stars', $('#f-stars').value);
    if ($('#f-board').value)   params.set('board_type', $('#f-board').value);
    if ($('#f-min').value)     params.set('min_price', $('#f-min').value);
    if ($('#f-max').value)     params.set('max_price', $('#f-max').value);
    if ($('#f-sort').value)    params.set('sort', $('#f-sort').value);
    params.set('size', 50);

    const grid = $('#tour-grid');
    gridSkeleton(grid);
    try {
      const { items } = await api('/api/tours?' + params);
      renderTourGrid(grid, items);
      $('#result-count').textContent = items.length
        ? `Найдено туров: ${items.length}`
        : 'Ничего не найдено';
    } catch (e) {
      grid.innerHTML = `<div class="empty"><span class="empty-icon">⚠️</span>
        <strong>Не удалось загрузить туры</strong>${esc(e.message)}</div>`;
      $('#result-count').textContent = '';
    }
  };

  $('#f-apply').onclick = loadTours;
  $('#f-sort').onchange = loadTours;
  $('#f-query').addEventListener('keydown', e => { if (e.key === 'Enter') loadTours(); });
  $('#f-reset').onclick = () => {
    ['#f-query', '#f-min', '#f-max'].forEach(s => $(s).value = '');
    ['#f-country', '#f-stars', '#f-board', '#f-sort'].forEach(s => $(s).value = '');
    loadTours();
  };

  $('#hero-cta').onclick = () => scrollToSection('catalog');
  const ctaReg = $('#cta-register');
  if (ctaReg && token()) {
    // если уже вошёл — ведём в каталог вместо регистрации
    ctaReg.textContent = 'Перейти к турам';
    ctaReg.setAttribute('href', '#/');
    ctaReg.onclick = (e) => { e.preventDefault(); scrollToSection('catalog'); };
  }

  // популярные направления — карточки стран с фото
  renderDestinations(loadTours);

  await loadTours();

  // отложенный скролл к секции (клик по «Туры»/«О нас»/«Контакты»)
  if (pendingScroll) {
    const target = pendingScroll;
    pendingScroll = null;
    setTimeout(() => scrollToSection(target), 60);
  }
}

// фото для популярных направлений (по названию страны)
const DEST_PHOTOS = {
  'Турция':   'https://images.unsplash.com/photo-1589561084283-930aa7b1ce50?w=600&q=80',
  'ОАЭ':      'https://images.unsplash.com/photo-1512453979798-5ea266f8880c?w=600&q=80',
  'Египет':   'https://images.unsplash.com/photo-1539768942893-daf53e448371?w=600&q=80',
  'Таиланд':  'https://images.unsplash.com/photo-1528181304800-259b08848526?w=600&q=80',
  'Греция':   'https://images.unsplash.com/photo-1503152394-c571994fd383?w=600&q=80',
  'Россия':   'https://images.unsplash.com/photo-1547448415-e9f5b28e570d?w=600&q=80',
  'Грузия':   'https://images.unsplash.com/photo-1565008576549-57569a49371d?w=600&q=80',
  'Кипр':     'https://images.unsplash.com/photo-1559574569-9f0a4b8c83e9?w=600&q=80',
};
const DEST_FALLBACK = 'https://images.unsplash.com/photo-1507525428034-b723cf961d3e?w=600&q=80';

// рисуем блок «Популярные направления»: топ-4 страны по числу туров
async function renderDestinations(loadTours) {
  const box = $('#destinations');
  if (!box) return;
  try {
    const { items } = await api('/api/tours?size=50');
    // считаем количество туров по странам
    const counts = {};
    items.forEach(t => { counts[t.country] = (counts[t.country] || 0) + 1; });
    const countries = await loadCountries();
    const byName = {};
    countries.forEach(c => { byName[c.name] = c.id; });

    const top = Object.keys(counts)
      .sort((a, b) => counts[b] - counts[a])
      .slice(0, 4);

    if (!top.length) { box.closest('.section').style.display = 'none'; return; }

    const wordTour = (n) => {
      const d = n % 10, dd = n % 100;
      if (d === 1 && dd !== 11) return 'тур';
      if (d >= 2 && d <= 4 && (dd < 10 || dd >= 20)) return 'тура';
      return 'туров';
    };

    box.innerHTML = top.map(name => `
      <div class="dest-card" data-country="${byName[name] || ''}" data-name="${esc(name)}">
        <img src="${DEST_PHOTOS[name] || DEST_FALLBACK}" alt="${esc(name)}" loading="lazy"
             onerror="this.onerror=null;this.src='${DEST_FALLBACK}';">
        <div class="dest-shade"></div>
        <div class="dest-info">
          <div class="dest-name">${esc(name)}</div>
          <div class="dest-count">${counts[name]} ${wordTour(counts[name])}</div>
        </div>
      </div>`).join('');

    // клик по направлению — фильтруем каталог по стране
    $$('.dest-card', box).forEach(card => {
      card.onclick = () => {
        const cid = card.dataset.country;
        if (cid) {
          $('#f-country').value = cid;
          loadTours();
        }
        scrollToSection('catalog');
      };
    });
  } catch (e) {
    const sec = box.closest('.section');
    if (sec) sec.style.display = 'none';
  }
}

// ---------------- Карточка тура ----------------

// что входит в стоимость — зависит от типа питания
function includedItems(t) {
  const meals = {
    RO: 'Проживание без питания',
    BB: 'Завтраки в отеле',
    HB: 'Завтраки и ужины (полупансион)',
    FB: 'Трёхразовое питание (полный пансион)',
    AI: 'Питание «всё включено»',
    UAI: 'Питание «ультра всё включено»',
  };
  return [
    'Авиаперелёт туда и обратно',
    `Проживание в отеле «${t.hotel}» ${t.stars}★`,
    meals[t.board_type] || 'Питание по программе тура',
    'Трансфер аэропорт — отель — аэропорт',
    'Медицинская страховка на весь период',
    'Сопровождение и поддержка 24/7',
  ];
}

// особенности тура — короткие пункты
function tourHighlights(t) {
  const items = [
    { ic: '✈', txt: `Направление: ${t.city}, ${t.country}` },
    { ic: '★', txt: `Категория отеля: ${t.stars} звёзд` },
    { ic: '☼', txt: BOARD[t.board_type] || 'Питание по программе' },
    { ic: '◷', txt: `Длительность: от ${t.nights_min} до ${t.nights_max} ночей` },
  ];
  return items;
}

async function renderTour(app, id) {
  app.appendChild($('#tpl-tour').content.cloneNode(true));
  const box = $('#tour-detail');
  box.innerHTML = '<div class="empty">Загрузка…</div>';
  await loadFavIds();

  try {
    const t = await api('/api/tours/' + id);
    const isFav = favIds && favIds.has(t.id);

    const included = includedItems(t).map(x =>
      `<li><span class="inc-check">✓</span>${esc(x)}</li>`).join('');
    const highlights = tourHighlights(t).map(h =>
      `<div class="hl"><span class="hl-ic">${h.ic}</span><span>${esc(h.txt)}</span></div>`).join('');

    box.innerHTML = `
      <img class="tour-detail-img" src="${esc(t.image_url || '')}" alt="${esc(t.title)}"
           onerror="this.onerror=null;this.removeAttribute('src');">
      <div class="tour-detail-body">
        <h1>${esc(t.title)}</h1>
        <div class="info-row">
          ${starsHTML(t.stars)}
          <strong>${esc(t.hotel)}</strong>
          <span>·</span><span>${esc(t.city)}, ${esc(t.country)}</span>
        </div>
        <div class="info-row">
          <span class="tag tag-board">${esc(BOARD[t.board_type] || t.board_type)}</span>
          <span class="tag">${t.nights_min}–${t.nights_max} ночей</span>
        </div>

        <div class="tour-section">
          <h3 class="tour-h3">О туре</h3>
          <p class="description">${esc(t.description || 'Описание тура будет добавлено в ближайшее время.')}</p>
        </div>

        <div class="tour-section">
          <h3 class="tour-h3">Кратко о направлении</h3>
          <div class="highlights">${highlights}</div>
        </div>

        <div class="tour-section">
          <h3 class="tour-h3">Что включено в стоимость</h3>
          <ul class="included">${included}</ul>
        </div>

        <div class="tour-section">
          <h3 class="tour-h3">Важно знать</h3>
          <ul class="notes-list">
            <li>Цена указана за одну ночь проживания на одного взрослого.</li>
            <li>Итоговая стоимость зависит от дат, количества ночей и числа туристов — рассчитывается при бронировании.</li>
            <li>Для поездки нужен загранпаспорт, действительный не менее 6 месяцев после возвращения.</li>
            <li>Точный список документов и условия визы менеджер сообщит после бронирования.</li>
          </ul>
        </div>

        <div class="price-block">
          <div>
            <div class="price-label">Цена</div>
            <div class="price-value">${fmt(t.price_per_night)} ₽ <span class="price-label">за ночь / чел.</span></div>
          </div>
          <div class="detail-actions">
            <button class="btn btn-outline ${isFav ? 'is-fav' : ''}" id="t-fav">
              ${isFav ? '♥ В избранном' : '♡ В избранное'}
            </button>
            <a href="#/book/${t.id}" class="btn btn-primary">Забронировать</a>
          </div>
        </div>
      </div>`;

    $('#t-fav').onclick = async () => {
      const btnEl = $('#t-fav');
      const fake = { classList: { add(){}, remove(){} } };
      await toggleFavorite(t.id, fake);
      await loadFavIds(true);
      const nowFav = favIds.has(t.id);
      btnEl.textContent = nowFav ? '♥ В избранном' : '♡ В избранное';
      btnEl.classList.toggle('is-fav', nowFav);
    };
  } catch (e) {
    box.innerHTML = `<div class="empty"><span class="empty-icon">⚠️</span>
      <strong>${esc(e.message)}</strong></div>`;
  }
}

// ---------------- Бронирование ----------------
async function renderBooking(app, tourId) {
  if (!token()) {
    toast('Войдите, чтобы забронировать тур');
    navigate('#/login');
    return;
  }
  app.appendChild($('#tpl-booking').content.cloneNode(true));
  $('#bk-back').onclick = (e) => { e.preventDefault(); history.back(); };

  let tour;
  try {
    tour = await api('/api/tours/' + tourId);
  } catch (e) { toast(e.message, 'error'); navigate('#/'); return; }

  $('#bk-tour-info').innerHTML = `
    <strong>${esc(tour.title)}</strong><br>
    ${esc(tour.hotel)}, ${esc(tour.city)} · ${esc(BOARD[tour.board_type])}<br>
    <span class="field-hint">Рекомендуемая длительность: ${tour.nights_min}–${tour.nights_max} ночей ·
    ${fmt(tour.price_per_night)} ₽/ночь за взрослого</span>`;

  const form = $('#booking-form');
  const totalBox = $('#bk-total');

  // Длительность выбирает пользователь — без привязки к минимуму тура.
  form.nights.min = 1;
  form.nights.max = 30;
  form.nights.value = 7;

  const tomorrow = new Date(); tomorrow.setDate(tomorrow.getDate() + 1);
  form.check_in.min = tomorrow.toISOString().split('T')[0];
  form.check_in.value = form.check_in.min;

  const recalc = () => {
    const nights = +form.nights.value || 1;
    const adults = +form.adults.value || 1;
    const children = +form.children.value || 0;
    const total = tour.price_per_night * nights * (adults + 0.5 * children);
    totalBox.textContent = `Итого: ${fmt(total)} ₽`;
  };
  form.addEventListener('input', recalc);
  recalc();

  form.onsubmit = async (e) => {
    e.preventDefault();
    const nights = +form.nights.value;
    if (nights < 1 || nights > 30) {
      toast('Количество ночей: от 1 до 30', 'error');
      return;
    }
    try {
      const b = await api('/api/bookings', {
        method: 'POST',
        body: JSON.stringify({
          tour_id: +tourId,
          check_in: form.check_in.value,
          nights,
          adults: +form.adults.value,
          children: +form.children.value,
        }),
      });
      toast(`Бронь №${b.id} создана. Перейдите к оплате.`, 'success');
      setTimeout(() => navigate('#/pay/' + b.id), 900);
    } catch (e) {
      toast(e.message, 'error');
    }
  };
}

// ---------------- Оплата ----------------
async function renderPayment(app, bookingId) {
  if (!token()) { navigate('#/login'); return; }
  app.appendChild($('#tpl-payment').content.cloneNode(true));

  let booking;
  try {
    const list = await api('/api/bookings/me');
    booking = list.find(b => b.id === +bookingId);
  } catch (e) { toast(e.message, 'error'); navigate('#/profile'); return; }

  if (!booking) {
    app.querySelector('.pay-box').innerHTML =
      `<h2 class="auth-title">Бронирование не найдено</h2>
       <a href="#/profile" class="btn btn-primary btn-block">В личный кабинет</a>`;
    return;
  }

  if (booking.status !== 'created') {
    app.querySelector('.pay-box').innerHTML = `
      <h2 class="auth-title">Оплата не требуется</h2>
      <p class="field-hint" style="margin:0 0 16px">
        Статус брони №${booking.id}: «${STATUS[booking.status] || booking.status}».</p>
      <a href="#/profile" class="btn btn-primary btn-block">В личный кабинет</a>`;
    return;
  }

  $('#pay-summary').innerHTML = `
    <div class="pay-row"><span>Тур</span><span>${esc(booking.tour_title)}</span></div>
    <div class="pay-row"><span>Бронь</span><span>№${booking.id}</span></div>
    <div class="pay-row"><span>Заезд</span>
      <span>${new Date(booking.check_in).toLocaleDateString('ru-RU')}</span></div>
    <div class="pay-row"><span>Ночей</span><span>${booking.nights}</span></div>
    <div class="pay-row"><span>Туристы</span>
      <span>${booking.adults} взр.${booking.children ? ' + ' + booking.children + ' дет.' : ''}</span></div>
    <div class="pay-total pay-row"><span>К оплате</span><span>${fmt(booking.total_price)} ₽</span></div>`;

  $$('.pay-method').forEach(m => {
    m.onclick = () => {
      $$('.pay-method').forEach(x => x.classList.remove('is-active'));
      m.classList.add('is-active');
    };
  });

  const payBtn = $('#pay-confirm');
  payBtn.textContent = `Оплатить ${fmt(booking.total_price)} ₽`;
  payBtn.onclick = async () => {
    payBtn.disabled = true;
    payBtn.textContent = 'Обработка платежа…';
    try {
      await api(`/api/bookings/${booking.id}/pay`, { method: 'POST' });
      toast('Оплата прошла успешно', 'success');
      setTimeout(() => navigate('#/profile'), 900);
    } catch (e) {
      toast(e.message, 'error');
      payBtn.disabled = false;
      payBtn.textContent = `Оплатить ${fmt(booking.total_price)} ₽`;
    }
  };
}

// ---------------- Вход ----------------
function renderLogin(app) {
  app.appendChild($('#tpl-login').content.cloneNode(true));
  const errBox = $('#login-error');
  $('#login-form').onsubmit = async (e) => {
    e.preventDefault();
    errBox.hidden = true;
    const fd = new FormData(e.target);
    try {
      const r = await api('/api/auth/login', {
        method: 'POST',
        body: JSON.stringify(Object.fromEntries(fd)),
      });
      setAuth(r.access_token, r.user);
      favIds = null;
      toast('Вы успешно вошли', 'success');
      navigate('#/');
    } catch (e) {
      const msg = e.message || 'Неверный email или пароль';
      errBox.textContent = msg;
      errBox.hidden = false;
      toast(msg, 'error');
    }
  };
}

// ---------------- Регистрация ----------------
function renderRegister(app) {
  app.appendChild($('#tpl-register').content.cloneNode(true));
  $('#register-form').onsubmit = async (e) => {
    e.preventDefault();
    const fd = new FormData(e.target);
    try {
      const r = await api('/api/auth/register', {
        method: 'POST',
        body: JSON.stringify(Object.fromEntries(fd)),
      });
      // регистрация сразу выполняет вход — без подтверждения почты
      setAuth(r.access_token, r.user);
      favIds = null;
      toast('Аккаунт создан. Добро пожаловать!', 'success');
      navigate('#/');
    } catch (e) { toast(e.message, 'error'); }
  };
}

// ---------------- Личный кабинет ----------------
async function renderProfile(app) {
  if (!token()) { navigate('#/login'); return; }
  app.appendChild($('#tpl-profile').content.cloneNode(true));

  try {
    const u = await api('/api/auth/me');
    setAuth(token(), { ...userData(), ...u });

    $('#profile-info').innerHTML = `
      <div class="profile-id">
        <span class="user-avatar">${esc(initials(u))}</span>
        <div>
          <div class="name">${esc((u.first_name || '') + ' ' + (u.last_name || '')).trim() || 'Без имени'}</div>
          <div class="email">${esc(u.email)}</div>
        </div>
      </div>
      <div class="profile-details">
        <div class="profile-row"><span class="lbl">Имя</span>
          <span class="val">${esc((u.first_name || '') + ' ' + (u.last_name || '')).trim() || '—'}</span></div>
        <div class="profile-row"><span class="lbl">Email</span>
          <span class="val">${esc(u.email)}</span></div>
        <div class="profile-row"><span class="lbl">Телефон</span>
          <span class="val">${esc(u.phone || 'не указан')}</span></div>
      </div>
      <a href="#/profile/edit" class="btn btn-outline btn-block">Редактировать данные</a>`;

    const bookings = await api('/api/bookings/me');

    const total = bookings.length;
    const active = bookings.filter(b => b.status !== 'cancelled').length;
    const spent = bookings
      .filter(b => b.status === 'paid' || b.status === 'confirmed')
      .reduce((s, b) => s + b.total_price, 0);
    const waiting = bookings.filter(b => b.status === 'created').length;

    $('#profile-stats').innerHTML = `
      <h4>Статистика</h4>
      <div class="stats-row">
        <div class="stat"><div class="stat-num">${total}</div>
          <div class="stat-lbl">всего броней</div></div>
        <div class="stat"><div class="stat-num">${active}</div>
          <div class="stat-lbl">активных</div></div>
        <div class="stat"><div class="stat-num">${waiting}</div>
          <div class="stat-lbl">ждут оплаты</div></div>
        <div class="stat"><div class="stat-num">${fmt(spent)}</div>
          <div class="stat-lbl">оплачено, ₽</div></div>
      </div>`;

    renderBookingsList($('#bookings-list'), bookings);

    // блок избранного в кабинете — до 3 туров
    const favGrid = $('#profile-favs');
    try {
      const favs = await api('/api/favorites');
      await loadFavIds(true);
      if (!favs.length) {
        favGrid.innerHTML = `<div class="empty"><span class="empty-icon">♡</span>
          <strong>В избранном пока пусто</strong>
          Нажимайте на сердечко в каталоге, чтобы сохранять туры.
          <div style="margin-top:12px"><a href="#/" class="btn btn-primary btn-sm">Открыть каталог</a></div></div>`;
      } else {
        renderTourGrid(favGrid, favs.slice(0, 3));
      }
    } catch (e) {
      favGrid.innerHTML = '';
    }
  } catch (e) {
    toast(e.message, 'error');
  }
}

function renderBookingsList(list, bookings) {
  if (!bookings.length) {
    list.innerHTML = `<div class="empty"><span class="empty-icon">🧳</span>
      <strong>Бронирований пока нет</strong>
      <a href="#/">Подобрать тур</a></div>`;
    return;
  }
  list.innerHTML = bookings.map(b => {
    let actions = '';
    if (b.status === 'created') {
      actions = `
        <a href="#/pay/${b.id}" class="btn btn-primary btn-sm">Оплатить</a>
        <button class="btn btn-danger btn-sm" data-cancel="${b.id}">Отменить</button>`;
    } else if (b.status === 'paid') {
      actions = `<button class="btn btn-danger btn-sm" data-cancel="${b.id}">Отменить</button>`;
    } else if (b.status === 'cancelled') {
      actions = `<span class="field-hint">Бронь отменена</span>`;
    } else {
      actions = `<span class="field-hint">Обратитесь к менеджеру</span>`;
    }
    return `
      <div class="booking-card">
        <div class="booking-main">
          <h4>${esc(b.tour_title)}</h4>
          <div class="booking-meta">Бронь №${b.id} ·
            заезд ${new Date(b.check_in).toLocaleDateString('ru-RU')} ·
            ${b.nights} ноч. · ${b.adults} взр.${b.children ? ' + ' + b.children + ' дет.' : ''}</div>
          <span class="status-badge status-${b.status}">${STATUS[b.status] || b.status}</span>
        </div>
        <div class="booking-side">
          <div class="price-value">${fmt(b.total_price)} ₽</div>
          <div class="booking-actions">${actions}</div>
        </div>
      </div>`;
  }).join('');

  $$('[data-cancel]', list).forEach(btn => {
    btn.onclick = async () => {
      if (!confirm('Отменить это бронирование?')) return;
      btn.disabled = true;
      try {
        await api(`/api/bookings/${btn.dataset.cancel}/cancel`, { method: 'POST' });
        toast('Бронирование отменено', 'success');
        const fresh = await api('/api/bookings/me');
        renderBookingsList(list, fresh);
      } catch (e) {
        toast(e.message, 'error');
        btn.disabled = false;
      }
    };
  });
}

// ---------------- Редактирование профиля ----------------
async function renderProfileEdit(app) {
  if (!token()) { navigate('#/login'); return; }
  app.appendChild($('#tpl-profile-edit').content.cloneNode(true));

  let u;
  try { u = await api('/api/auth/me'); }
  catch (e) { toast(e.message, 'error'); return; }

  const form = $('#profile-edit-form');
  form.first_name.value = u.first_name || '';
  form.last_name.value  = u.last_name || '';
  form.phone.value      = u.phone || '';
  form.email.value      = u.email || '';

  form.onsubmit = async (e) => {
    e.preventDefault();
    try {
      const updated = await api('/api/auth/me', {
        method: 'PATCH',
        body: JSON.stringify({
          first_name: form.first_name.value,
          last_name:  form.last_name.value,
          phone:      form.phone.value,
        }),
      });
      setAuth(token(), { ...userData(), ...updated });
      toast('Данные сохранены', 'success');
      navigate('#/profile');
    } catch (e) { toast(e.message, 'error'); }
  };

  // переключатели «показать пароль»
  $$('[data-eye]').forEach(btn => {
    btn.onclick = () => {
      const input = btn.parentElement.querySelector('input');
      const show = input.type === 'password';
      input.type = show ? 'text' : 'password';
      btn.classList.toggle('is-on', show);
      btn.setAttribute('aria-label', show ? 'Скрыть пароль' : 'Показать пароль');
    };
  });

  // смена пароля (форма перенесена сюда из личного кабинета)
  $('#password-form').onsubmit = async (e) => {
    e.preventDefault();
    const fd = Object.fromEntries(new FormData(e.target));
    try {
      await api('/api/auth/password', { method: 'POST', body: JSON.stringify(fd) });
      e.target.reset();
      $$('[data-eye]').forEach(b => {
        const inp = b.parentElement.querySelector('input');
        inp.type = 'password';
        b.classList.remove('is-on');
        b.setAttribute('aria-label', 'Показать пароль');
      });
      toast('Пароль успешно изменён', 'success');
    } catch (e) { toast(e.message, 'error'); }
  };
}

// ---------------- Избранное ----------------
async function renderFavorites(app) {
  if (!token()) { navigate('#/login'); return; }
  app.appendChild($('#tpl-favorites').content.cloneNode(true));
  const grid = $('#fav-grid');
  gridSkeleton(grid, 3);
  await loadFavIds(true);
  try {
    const items = await api('/api/favorites');
    if (!items.length) {
      grid.innerHTML = `<div class="empty"><span class="empty-icon">♡</span>
        <strong>В избранном пока пусто</strong>
        Нажимайте на сердечко в каталоге, чтобы сохранять туры сюда.
        <div style="margin-top:12px"><a href="#/" class="btn btn-primary btn-sm">Открыть каталог</a></div></div>`;
      return;
    }
    renderTourGrid(grid, items);
  } catch (e) {
    grid.innerHTML = `<div class="empty"><span class="empty-icon">⚠️</span>
      <strong>${esc(e.message)}</strong></div>`;
  }
}

// ---------------- Мобильное меню ----------------
function closeMenu() {
  $('#nav')?.classList.remove('open');
  $('#burger')?.setAttribute('aria-expanded', 'false');
}
function toggleMenu() {
  const nav = $('#nav');
  const open = nav.classList.toggle('open');
  $('#burger').setAttribute('aria-expanded', open ? 'true' : 'false');
}

// ---------------- Запуск ----------------
$('#theme-toggle').onclick = toggleTheme;
$('#burger').onclick = toggleMenu;

document.addEventListener('click', (e) => {
  if ($('#nav')?.classList.contains('open') &&
      !e.target.closest('#nav') && !e.target.closest('#burger')) {
    closeMenu();
  }
  // ссылки-якоря на секции главной (data-scroll)
  const link = e.target.closest('[data-scroll]');
  if (link) {
    e.preventDefault();
    const section = link.dataset.scroll;
    closeMenu();
    if ((location.hash.slice(1) || '/') === '/') {
      scrollToSection(section);
    } else {
      pendingScroll = section;
      navigate('#/');
    }
  }
});

// кнопка «наверх» + тень шапки при прокрутке
const toTop = $('#to-top');
toTop.onclick = () => window.scrollTo({ top: 0, behavior: 'smooth' });
window.addEventListener('scroll', () => {
  toTop.classList.toggle('show', window.scrollY > 480);
}, { passive: true });

renderAuth();
router();
