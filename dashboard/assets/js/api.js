/* ============================================
   SYSTEM V2 — DASHBOARD API
   Supabase REST wrapper + session/partner helpers
   Used by all dashboard tabs (leads, contacts, tasks, ...)
   ============================================ */

const SUPABASE_URL = 'https://njwraxmlzglmofxiwmxs.supabase.co';
const SUPABASE_ANON_KEY = 'sb_publishable_iATLaUgVdGL6VjuBLQhKDw_UgxxfQcs';

// ===== SESSION =====
function getAccessToken() {
  return sessionStorage.getItem('sb_access_token');
}
function getCurrentUser() {
  const raw = sessionStorage.getItem('sb_user');
  return raw ? JSON.parse(raw) : null;
}
function requireAuth() {
  if (!getAccessToken()) {
    window.location.href = '../login.html';
    throw new Error('auth required');
  }
}
function logout() {
  sessionStorage.clear();
  window.location.href = '../login.html';
}

// ===== PARTNER =====
let _partnerCache = null;
async function getCurrentPartner() {
  if (_partnerCache) return _partnerCache;

  const cached = sessionStorage.getItem('sb_partner');
  if (cached) {
    _partnerCache = JSON.parse(cached);
    return _partnerCache;
  }

  const user = getCurrentUser();
  if (!user?.id) return null;

  const rows = await sb('GET', `partners?user_id=eq.${user.id}&select=*`);
  if (Array.isArray(rows) && rows[0]) {
    _partnerCache = rows[0];
    sessionStorage.setItem('sb_partner', JSON.stringify(_partnerCache));
    return _partnerCache;
  }
  return null;
}

// ===== REST WRAPPER =====
async function sb(method, path, body = null, extraHeaders = {}) {
  const token = getAccessToken();
  const headers = {
    'apikey': SUPABASE_ANON_KEY,
    'Authorization': `Bearer ${token || SUPABASE_ANON_KEY}`,
    'Content-Type': 'application/json',
    'Prefer': method === 'GET' ? 'count=exact' : 'return=representation',
    ...extraHeaders,
  };
  const opts = { method, headers };
  if (body) opts.body = JSON.stringify(body);

  const resp = await fetch(`${SUPABASE_URL}/rest/v1/${path}`, opts);

  if (resp.status === 401) {
    logout();
    throw new Error('session expired');
  }
  if (!resp.ok) {
    let err;
    try { err = await resp.json(); } catch { err = { message: resp.statusText }; }
    const e = new Error(err.message || `HTTP ${resp.status}`);
    e.details = err;
    e.status = resp.status;
    throw e;
  }
  if (resp.status === 204) return null;
  return resp.json();
}

// ===== AUTH (GoTrue) =====
async function sbAuth(method, path, body = null) {
  const token = getAccessToken();
  const headers = {
    'apikey': SUPABASE_ANON_KEY,
    'Authorization': `Bearer ${token || SUPABASE_ANON_KEY}`,
    'Content-Type': 'application/json',
  };
  const opts = { method, headers };
  if (body) opts.body = JSON.stringify(body);

  const resp = await fetch(`${SUPABASE_URL}/auth/v1/${path}`, opts);
  if (!resp.ok) {
    let err;
    try { err = await resp.json(); } catch { err = { message: resp.statusText }; }
    const e = new Error(err.msg || err.message || `HTTP ${resp.status}`);
    e.status = resp.status;
    throw e;
  }
  if (resp.status === 204) return null;
  return resp.json();
}
