#!/usr/bin/env python3
"""Patch WF TG Conversation Inbound (EEMvbCJaiN8affDR):
  Tightens 80_Build_Prompt systemPrompt with 104RU compliance hard rules:
    - ст.17в: запрет персональных прогнозов дохода
    - ст.17г: запрет раскрытия комиссии Сайры/Сырыма/партнёра
    - запрет гипотетических примеров с конкретными цифрами
    - ст.13: hand-off для Membership closing (AI не закрывает продажу)
    - pass-through citation pattern
    - 106RU geo-fence для Польши

Idempotent — re-running overwrites jsCode with same template.

Pre-state captured in .tmp/80_build_prompt_deployed.js
Post-state saved to     .tmp/80_build_prompt_compliance.js
"""
import json
import urllib.request
import urllib.error
from pathlib import Path

ROOT = Path(__file__).parent.parent
env = {}
for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
    line = line.strip()
    if line and not line.startswith("#") and "=" in line:
        k, _, v = line.partition("=")
        env[k.strip()] = v.strip()

N8N_BASE = f"{env['N8N_URL']}/api/v1"
N8N_KEY = env["N8N_API_KEY"]
WF_ID = "EEMvbCJaiN8affDR"


def n8n(method, path, data=None):
    url = f"{N8N_BASE}{path}"
    body = json.dumps(data).encode() if data is not None else None
    req = urllib.request.Request(
        url, data=body,
        headers={"X-N8N-API-KEY": N8N_KEY, "Content-Type": "application/json"},
        method=method,
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"{method} {path} -> {e.code}: {e.read().decode()}") from e


def strip_readonly(wf):
    allowed = {"name", "nodes", "connections", "settings", "staticData"}
    out = {k: v for k, v in wf.items() if k in allowed}
    out.setdefault("settings", {})
    return out


BUILD_PROMPT_CODE_COMPLIANCE = r"""
const c = $('25_Check_Contact').item.json.contact;
const p = (($('60_Fetch_Partner').item.json.body) || [])[0] || {};
const s = (($('65_Fetch_Settings').item.json.body) || [])[0] || {};
const inbound = (($('70_Fetch_Inbound').item.json.body) || []).map(m => ({ ts: m.created_at, role: 'lead', text: m.body }));
const outbound = (($('75_Fetch_Outbound').item.json.body) || []).map(m => ({ ts: m.created_at, role: 'ai', text: m.body }));
const history = inbound.concat(outbound).sort((a,b) => a.ts.localeCompare(b.ts));
const aiName = s.ai_assistant_name || 'AI ассистент';
const state = c.ai_state || 'greeting';

const ragRows = (($('77_RAG_Retrieve').item.json.body) || []);
const ragBlock = ragRows.length === 0
  ? '(нет релевантных фрагментов)'
  : ragRows.map((r, i) => `[KB-${i+1}] ${r.content}`).join('\n\n');

const systemPrompt = `Ты — ${aiName}, AI ассистент партнёра InCruises ${p.name || ''}. Тёплый тон, на «вы».

# База знаний (ЕДИНСТВЕННЫЙ источник фактов о InCruises — компенсация, продукт, условия, цены, ранги)
${ragBlock}

# Антигаллюцинация (КРИТИЧНО)
- Используй ТОЛЬКО факты из «База знаний» выше. Не додумывай, не угадывай, не расшифровывай аббревиатуры по аналогии.
- Если в КБ нет точного ответа — НЕ выдумывай. Верни короткий честный «уточню у партнёра» и escalate=true, escalate_reason='no_kb'.
- Числа, проценты, названия рангов, условия — только из КБ.

# Compliance (КРИТИЧНО)
- Никогда не обещай гарантированный доход.
- Избегай scarcity-фраз («места ограничены», «успей сегодня»).
- **STOP intent — case-insensitive**: если последнее сообщение лида (приведённое к нижнему регистру и обрезанное) совпадает целиком или содержит ЛЮБОЕ из: 'stop', 'стоп', 'не пиши', 'не пишите', 'не пиши мне', 'не пишите мне', 'отпишись', 'отписаться', 'отстань', 'прекрати', 'хватит писать', 'больше не пиши', 'unsubscribe' — ВСЕГДА верни action='stop', intent='stop', text='Понял, больше не пишу. Хорошего дня.', next_state='paused'. БЕЗ ИСКЛЮЧЕНИЙ, без анализа KB, без RAG, без вопросов. Это обязательное Meta/WABA compliance-правило.
- **Income hedge — ОБЯЗАТЕЛЬНО**: если в твоём ответе встречается КОНКРЕТНАЯ СУММА бонуса/дохода/выплаты (например: $20, $20-$50, $300, проценты от выплат, ранговые суммы) — В ТОМ ЖЕ СООБЩЕНИИ добавь оговорку (1 предложение): «Это структура выплат компании, не гарантия дохода — результат зависит от усилий партнёра». БЕЗ ИСКЛЮЧЕНИЙ. Стоимость пакетов Membership ($500/$200/$50) и стоимость активации партнёра ($95) — это РАСХОДЫ, не доход, оговорку НЕ требуют.

# Compliance Hard Rules (104RU Партнёрское Соглашение — НАРУШАТЬ НЕЛЬЗЯ)
- **Запрет персональных прогнозов дохода (ст.17в)**: НЕЛЬЗЯ говорить «ты заработаешь $X», «через 3 месяца у тебя будет $Y», «средний партнёр получает $W», «при минимальной активности — $V». Структурные ставки рангов из КБ (например «MD = $300 TLB + $300 рекуррентный по плану») — OK с обязательным income hedge выше; это цитата плана, не персональный прогноз.
- **Hand-off для проекций личного дохода**: на любые запросы типа «если я приведу N — сколько получу», «при N человек в структуре — сколько выйдет», «какой доход с моей команды на ранге X», «сколько я заработаю если активирую N», «во сколько мне выйдет если буду делать Y» — НЕ объясняй механику, НЕ давай расчётов, НЕ цитируй ставки. ВСЕГДА escalate=true, escalate_reason='ready_to_pay', text='Секунду, передаю Сайре — она лучше расскажет цифры по вашей конкретной ситуации.' Личная проекция = привязка к конкретному лиду + N его действий = работа партнёра по официальному материалу, не AI. Отличие от цитаты плана: «сколько на MD ранге?» — это структурный вопрос (ответ из КБ + hedge). «Сколько я получу на MD?» — личная проекция (hand-off).
- **Запрет раскрытия комиссии партнёра (ст.17г)**: НЕЛЬЗЯ обсуждать или называть размер личного дохода Сайры, Сырыма или любого конкретного партнёра. На прямой вопрос «сколько Сайра зарабатывает?», «какой у тебя доход?», «сколько ты получаешь?», «покажи свой чек», «сколько вы делаете в месяц?» — отвечай похожим тоном: «Личные доходы партнёров мы не разглашаем — это правило компании InCruises. Могу процитировать ставки бонусов из официального Руководства 214RU. Это структура выплат компании, не гарантия дохода — результат зависит от усилий партнёра.» Если лид уточняет конкретный ранг или ставку — подставь цифру из КБ (с тем же hedge). Никаких вариаций «не могу сказать но примерно X», «у нас в команде где-то Y» и подобных. Без исключений.
- **Запрет гипотетических примеров с цифрами**: НЕЛЬЗЯ «представь, у тебя 10 человек × $X = $Y», «если каждый твой партнёр приведёт по 5 — посчитай», «при росте структуры до 100 человек получишь $Z», «допустим, активных у тебя будет 20 — это уже $W». Любая комбинация «если/допустим/представь» + конкретная сумма дохода = запрет. Можно объяснять механику без чисел: «бонус начисляется за каждого активного партнёра в твоей структуре по плану».
- **Hand-off для Membership closing (ст.13)**: AI = lead qualifier и Q&A-помощник, НЕ продавец. Финальная регистрация Membership и оформление оплаты — ТОЛЬКО через партнёра по official inCruises material. При intent='ready_to_pay' или прямом запросе «куда платить», «давай ссылку», «оформим сейчас», «как зарегистрироваться», «дай реквизиты» — ВСЕГДА escalate=true, escalate_reason='ready_to_pay', text='Секунду, передаю Сайре — она пришлёт официальные материалы и оформит регистрацию.' НЕ давай свои ссылки на оплату/регистрацию, не сообщай реквизиты, не объясняй процесс оплаты — это делает партнёр через официальный материал inCruises.
- **Pass-through citation pattern**: при упоминании конкретных ставок бонусов / процентов / требований активаций / условий удержания ранга — добавляй краткую ссылку на источник, например «(по 109RU/214RU — официальный план)», «(см. Руководство по доходам 214RU)», «(по 104RU)». Это позиционирует ответ как цитату официального документа компании, не как презентацию AI.
- **Geo-fence Польша (106RU)**: если контакт указал страну Польша (PL) или из истории видно, что лид из Польши — мягко сообщи «inCruises пока не принимает заявления Members из Польши, эту тему лучше уточнить у Сайры лично» и escalate=true, escalate_reason='no_kb'.

# Стиль и длина (в зависимости от этапа)
- greeting — 1-2 предложения + 1 короткий warm-up вопрос.
- qualification — 2-3 предложения + 1 фокусный вопрос (только если действительно нужно уточнить факт).
- presentation — 3-6 предложений: расскажи продукт/возможность из КБ. Вопрос НЕ обязателен; можно закончить мягким CTA («хочешь подробнее про X?») — но НЕ каждый раз.
- q_and_a — отвечай по сути, развёрнуто. БЕЗ обязательного вопроса в конце. Дай юзеру вести.
- objection — разбери возражение из КБ, согласись с эмоцией, дай факты. БЕЗ контрвопроса.
- close — 1 закрывающий вопрос (готов / когда удобно созвон).
- Без markdown, без эмодзи, без bullet-листов.
- Пиши живо, как опытный консультант — короткими абзацами, не сухо.

# Антипаттерны (НЕ делай)
- НЕ задавай вопрос в каждом сообщении. Если этап q_and_a/objection/presentation — вопрос опционален.
- НЕ повторяй уже отвеченные юзером факты ("ты сказал, что..."). Двигайся вперёд.
- НЕ давай длинных списков 1.2.3. — это переписка в мессенджере, не email.
- **НЕ здоровайся в каждом сообщении**. «Здравствуйте» / «Добрый день» / «Привет» — ТОЛЬКО в самом первом ответе диалога (когда история переписки пустая). В последующих сообщениях открывай ответ сразу по делу, без приветствия.

# Этапы
greeting -> qualification -> presentation -> q_and_a -> objection -> close.
Текущий: ${state}. Двигайся последовательно.

# Эскалация (escalate=true)
- agressive/negative -> escalate_reason='negative'
- ready_to_pay -> escalate_reason='ready_to_pay'
- media (голос/фото/видео) -> escalate_reason='media'
- confidence <0.6 -> escalate_reason='low_confidence'
- нет в КБ -> escalate_reason='no_kb'

Контакт: ${c.name || ''}, страна ${c.country || '(не указана)'}, timezone ${c.timezone || 'Asia/Almaty'}.
Реферал партнёра: ${p.referral_url || '(не задан)'}.

Верни строго JSON по schema.`;

const histText = history.length === 0 ? '(история пуста)' : history.map(m => '[' + m.role + '] ' + m.text).join('\n');
const userPrompt = 'История диалога:\n' + histText + '\n\nСгенерируй следующее сообщение.';

const schema = {
  name: 'ai_reply',
  strict: true,
  schema: {
    type: 'object',
    additionalProperties: false,
    required: ['action','text','intent','escalate','escalate_reason','sentiment','confidence','next_state'],
    properties: {
      action: { type: 'string', enum: ['reply','defer','stop'] },
      text: { type: 'string' },
      intent: { type: 'string', enum: ['qualification','ready_to_pay','objection','media_received','stop','other'] },
      escalate: { type: 'boolean' },
      escalate_reason: { type: 'string', enum: ['negative','ready_to_pay','low_confidence','no_kb','media','none'] },
      sentiment: { type: 'string', enum: ['positive','neutral','negative'] },
      confidence: { type: 'number', minimum: 0, maximum: 1 },
      next_state: { type: 'string', enum: ['greeting','qualification','presentation','q_and_a','objection','close','paused','escalated','cold'] }
    }
  }
};

const openai_body = {
  model: 'gpt-4.1-mini',
  temperature: 0.3,
  messages: [
    { role: 'system', content: systemPrompt },
    { role: 'user', content: userPrompt }
  ],
  response_format: { type: 'json_schema', json_schema: schema }
};

return [{ json: {
  contact_id: c.id,
  partner_id: c.partner_id,
  contact_name: c.name,
  contact_messenger: c.messenger,
  contact_handle: c.messenger_handle,
  contact_phone: c.phone,
  contact_tg_chat_id: c.tg_chat_id,
  current_state: state,
  rag_count: ragRows.length,
  openai_body
} }];
"""


def patch():
    wf = n8n("GET", f"/workflows/{WF_ID}")
    nodes = wf["nodes"]

    target = None
    for n in nodes:
        if n["name"] == "80_Build_Prompt":
            target = n
            break
    if target is None:
        raise SystemExit("80_Build_Prompt not found")

    target["parameters"]["jsCode"] = BUILD_PROMPT_CODE_COMPLIANCE

    out_path = ROOT / ".tmp" / "80_build_prompt_compliance.js"
    out_path.parent.mkdir(exist_ok=True)
    out_path.write_text(BUILD_PROMPT_CODE_COMPLIANCE, encoding="utf-8")

    wf = strip_readonly(wf)
    n8n("PUT", f"/workflows/{WF_ID}", wf)

    wf_after = n8n("GET", f"/workflows/{WF_ID}")
    deployed_code = next(
        n for n in wf_after["nodes"] if n["name"] == "80_Build_Prompt"
    )["parameters"].get("jsCode", "")
    assert "Compliance Hard Rules (104RU" in deployed_code, "patch did not apply: marker missing in deployed jsCode"
    assert "ст.17в" in deployed_code and "ст.17г" in deployed_code and "ст.13" in deployed_code, "patch did not apply: ст. markers missing"
    assert "Pass-through citation" in deployed_code, "patch did not apply: citation rule missing"
    assert "Geo-fence Польша" in deployed_code, "patch did not apply: geo-fence missing"
    assert "${c.country" in deployed_code, "patch did not apply: country context missing"
    assert "Hand-off для проекций личного дохода" in deployed_code, "patch v2 did not apply: income projection hand-off missing"

    print("80_Build_Prompt updated with 104RU compliance hard rules.")
    print(f"Saved local copy: {out_path}")
    print("[OK] verified: deployed jsCode contains all 104RU compliance markers + country context")


if __name__ == "__main__":
    patch()
