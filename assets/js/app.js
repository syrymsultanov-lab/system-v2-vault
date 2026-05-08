/* ============================================
   SYSTEM V2 — LANDING PAGE JS
   Supabase integration, ref code, i18n
   ============================================ */

const SUPABASE_URL = 'https://njwraxmlzglmofxiwmxs.supabase.co';
const SUPABASE_ANON_KEY = 'sb_publishable_iATLaUgVdGL6VjuBLQhKDw_UgxxfQcs';
const LEAD_INTAKE_WEBHOOK_URL = 'https://n8n.sairateam.com/webhook/system-v2/lead-intake';

let validatedPartnerId = null;
let validatedRefCode = null;
let currentLang = 'ru';

// ===== OWNER DEFAULT REF CODE =====
// Используется только если явно передан флаг ?owner=1
const OWNER_REF_CODE = 'SAIRA001';

// ===== HEADER SCROLL =====
window.addEventListener('scroll', () => {
  document.querySelector('.header')?.classList.toggle('scrolled', window.scrollY > 20);
});

// ===== LANGUAGE SWITCH =====
function setLang(lang) {
  currentLang = lang;
  document.querySelectorAll('[data-lang]').forEach(el => {
    el.style.display = el.getAttribute('data-lang') === lang ? 'inline' : 'none';
  });
  document.querySelectorAll('.lang-btn').forEach(btn => {
    btn.classList.toggle('active', btn.getAttribute('data-set-lang') === lang);
  });
}

document.addEventListener('click', (e) => {
  if (e.target.matches('[data-set-lang]')) {
    setLang(e.target.getAttribute('data-set-lang'));
  }
});

// ===== REF CODE FROM URL OR DEFAULT =====
// По умолчанию используется код Сайры (owner) — форма сразу доступна.
// Если в URL ?ref=XXX — используется этот код.
// Пользователь может вручную сменить партнёра через «Сменить код партнёра».
history.scrollRestoration = 'manual';

document.addEventListener('DOMContentLoaded', () => {
  window.scrollTo(0, 0);

  const params = new URLSearchParams(window.location.search);
  const refFromUrl = params.get('ref');
  const refCode = refFromUrl || OWNER_REF_CODE;

  const refInput = document.getElementById('ref-code-input');
  if (refInput) refInput.value = refCode.toUpperCase();

  validateRefCode(refCode, true);
});

// ===== SWITCH PARTNER =====
function switchPartner() {
  validatedPartnerId = null;
  validatedRefCode = null;

  const gate = document.getElementById('access-gate');
  const formSection = document.getElementById('form-section');
  const refInput = document.getElementById('ref-code-input');
  const errorEl = document.getElementById('ref-error');

  if (gate) gate.style.display = '';
  if (formSection) formSection.classList.remove('visible');
  if (refInput) { refInput.value = ''; refInput.focus(); }
  if (errorEl) errorEl.classList.remove('show');

  gate?.scrollIntoView({ behavior: 'smooth', block: 'center' });
}

// ===== VALIDATE REF CODE =====
async function validateRefCode(code, fromUrl = false) {
  if (!code) code = document.getElementById('ref-code-input')?.value?.trim();
  if (!code) return;

  const errorEl = document.getElementById('ref-error');
  const btnEl = document.getElementById('ref-check-btn');
  
  if (btnEl) btnEl.textContent = '...';
  if (errorEl) errorEl.classList.remove('show');

  try {
    const resp = await fetch(
      `${SUPABASE_URL}/rest/v1/partners?ref_code=eq.${encodeURIComponent(code.toUpperCase())}&select=id,ref_code`,
      {
        headers: {
          'apikey': SUPABASE_ANON_KEY,
          'Authorization': `Bearer ${SUPABASE_ANON_KEY}`
        }
      }
    );
    const data = await resp.json();

    if (data && data.length > 0) {
      validatedPartnerId = data[0].id;
      validatedRefCode = data[0].ref_code;
      // Show form
      document.getElementById('access-gate')?.style.setProperty('display', 'none');
      const formSection = document.getElementById('form-section');
      if (formSection) {
        formSection.classList.add('visible');
        if (!fromUrl) formSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }
      // Pre-fill ref code in form
      const formRef = document.getElementById('form-ref-code');
      if (formRef) formRef.value = validatedRefCode;
    } else {
      if (errorEl) {
        errorEl.classList.add('show');
        errorEl.textContent = getErrorText();
      }
    }
  } catch (err) {
    console.error('Ref validation error:', err);
    if (errorEl) {
      errorEl.classList.add('show');
      errorEl.textContent = 'Ошибка соединения. Попробуйте позже.';
    }
  } finally {
    if (btnEl) {
      btnEl.textContent = currentLang === 'en' ? 'Check' : currentLang === 'kz' ? 'Тексеру' : 'Проверить';
    }
  }
}

function getErrorText() {
  if (currentLang === 'en') return 'Code not found. Contact your partner.';
  if (currentLang === 'kz') return 'Код табылмады. Серіктесіңізге хабарласыңыз.';
  return 'Код не найден. Обратитесь к вашему партнёру.';
}

// ===== FORM SUBMIT =====
async function submitForm(e) {
  e.preventDefault();
  const btn = document.getElementById('form-submit-btn');
  if (btn) { btn.disabled = true; btn.textContent = '...'; }

  const consent = document.getElementById('f-consent')?.checked || false;
  const formData = {
    name: document.getElementById('f-first-name')?.value?.trim() || null,
    last_name: document.getElementById('f-last-name')?.value?.trim() || null,
    phone: document.getElementById('f-phone')?.value?.trim() || null,
    email: document.getElementById('f-email')?.value?.trim() || null,
    country: document.getElementById('f-country')?.value || null,
    city: document.getElementById('f-city')?.value?.trim() || null,
    messenger: document.getElementById('f-messenger')?.value || null,
    messenger_handle: document.getElementById('f-messenger-handle')?.value?.trim() || null,
    partner_id: validatedPartnerId || null,
    source: 'landing',
    channel: 'web',
    consent,
    consent_at: consent ? new Date().toISOString() : null
  };

  try {
    const resp = await fetch(LEAD_INTAKE_WEBHOOK_URL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(formData)
    });

    if (resp.ok || resp.status === 201) {
      showModal();
      document.getElementById('lead-form')?.reset();
    } else {
      const data = await resp.json().catch(() => ({}));
      console.error('Submit error:', data);
      alert('Ошибка отправки. Попробуйте ещё раз.');
    }
  } catch (err) {
    console.error('Network error:', err);
    alert('Ошибка соединения. Проверьте интернет и попробуйте ещё раз.');
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.textContent = currentLang === 'en' ? 'Submit request →' : currentLang === 'kz' ? 'Өтінім жіберу →' : 'Отправить заявку →';
    }
  }
}

// ===== MODAL =====
function showModal() {
  document.getElementById('success-modal')?.classList.add('show');
}
function closeModal() {
  document.getElementById('success-modal')?.classList.remove('show');
}

// ===== REF CHECK ENTER KEY =====
document.addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && document.activeElement?.id === 'ref-code-input') {
    e.preventDefault();
    validateRefCode();
  }
});
