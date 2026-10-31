/* Shared helpers - team leader owns this file */
const $ = (s, r = document) => r.querySelector(s);
const esc = v => String(v ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const money = n => '₹' + Number(n || 0).toLocaleString('en-IN', {minimumFractionDigits: 2, maximumFractionDigits: 2});
const fd = d => d ? esc(String(d).slice(0, 10)) : '—';
const badge = s => `<span class="badge ${esc(s)}">${esc(s)}</span>`;
const C = (label, key) => [label, r => esc(r[key])];          // simple table column

function toast(msg, bad) {
  let t = $('#toast');
  if (!t) { t = document.createElement('div'); t.id = 'toast'; document.body.append(t); }
  t.textContent = msg; t.className = bad ? 'bad' : ''; t.style.display = 'block';
  clearTimeout(t._t); t._t = setTimeout(() => t.style.display = 'none', 3500);
}

async function api(path, method = 'GET', body) {
  const res = await fetch(path, {method, credentials: 'same-origin',
    headers: {'Content-Type': 'application/json'}, body: body ? JSON.stringify(body) : undefined});
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    if (res.status === 401 && !document.body.hasAttribute('data-public')) location.href = '/index.html';
    throw new Error(data.error || res.statusText);
  }
  return data;
}

/* Loads the logged-in user and draws the nav. staffOnly pages bounce customers away. */
async function init(staffOnly) {
  let me;
  try { me = await api('/auth/me'); } catch (e) { return new Promise(() => {}); }
  if (staffOnly && me.role === 'customer') { location.href = '/subscriptions.html'; return new Promise(() => {}); }
  const links = me.role === 'customer'
    ? [['subscriptions', 'Subscriptions'], ['billing', 'Invoices']]
    : [['dashboard', 'Dashboard'], ['customers', 'Customers'], ['products', 'Products'], ['subscriptions', 'Subscriptions'], ['billing', 'Billing']];
  $('#nav').innerHTML = '<b>SubscriptionHub</b>' +
    links.map(([p, t]) => `<a href="/${p}.html" ${location.pathname === '/' + p + '.html' ? 'class="on"' : ''}>${t}</a>`).join('') +
    `<span>${esc(me.name)} (${me.role}) <button class="sm" id="out">Logout</button></span>`;
  $('#out').onclick = async () => { await api('/auth/logout', 'POST'); location.href = '/index.html'; };
  return me;
}

/* ---- form + table builders ---- */
function field(f) {
  const a = `name="${f.name}" title="${esc(f.label)}" ${f.req ? 'required' : ''}`;
  if (f.options) return `<select ${a}>${f.req ? '' : `<option value="">${esc(f.label)}</option>`}` +
    f.options.map(([v, l]) => `<option value="${esc(v)}">${esc(l)}</option>`).join('') + '</select>';
  return `<input ${a} type="${f.type || 'text'}" placeholder="${esc(f.label)}" value="${esc(f.value ?? '')}" ${f.type === 'number' ? 'step="any"' : ''}>`;
}

function collect(form, fields) {
  const d = {};
  for (const f of fields) {
    const v = form.elements[f.name].value.trim();
    if (v !== '') d[f.name] = f.type === 'number' ? Number(v) : v;
  }
  return d;
}

function table(rows, cols, acts) {
  if (!rows.length) return '<p style="color:var(--mut)">Nothing here yet.</p>';
  const head = cols.map(c => `<th>${esc(c[0])}</th>`).join('') + (acts ? '<th></th>' : '');
  const body = rows.map((r, i) => '<tr>' + cols.map(c => `<td>${c[1](r)}</td>`).join('') +
    (acts ? '<td>' + acts.map((a, j) => !a.show || a.show(r)
      ? `<button class="sm ${a.cls || ''}" data-a="${j}" data-r="${i}">${a.label}</button>` : '').join('') + '</td>' : '') + '</tr>').join('');
  return `<table><tr>${head}</tr>${body}</table>`;
}

/* A card with an optional "add" form and a table with row actions.
   o: {title, list|load, create (url or fn(data)->url), fields, cols, edit:{url,fields}, actions, after} */
function section(host, o) {
  host.insertAdjacentHTML('beforeend', `<div class="card"><h2>${o.title}</h2>` +
    (o.fields ? `<form class="row">${o.fields.map(field).join('')}<button>Add</button></form>` : '') + '<div class="tw"></div></div>');
  const card = host.lastElementChild, form = $('form', card), tw = $('.tw', card);
  let rows = [];
  const acts = [...(o.edit ? [{label: 'Edit', cls: 'ghost', run: async r => {
    const d = {};
    for (const n of o.edit.fields) {
      const f = o.fields.find(x => x.name === n);
      const v = prompt(f.label, r[n] ?? '');
      if (v === null) return;
      if (v !== '') d[n] = f.type === 'number' ? Number(v) : v;
    }
    await api(o.edit.url(r), 'PUT', d); toast('Updated');
  }}] : []), ...(o.actions || [])];
  async function refresh() {
    rows = await (o.load ? o.load() : api(o.list));
    tw.innerHTML = table(rows, o.cols, acts.length ? acts : null);
  }
  tw.onclick = async e => {
    const b = e.target.closest('button[data-a]'); if (!b) return;
    try { await acts[b.dataset.a].run(rows[b.dataset.r]); await refresh(); o.after && o.after(); }
    catch (x) { toast(x.message, 1); }
  };
  if (form) form.onsubmit = async e => {
    e.preventDefault();
    try {
      const d = collect(form, o.fields);
      await api(typeof o.create === 'function' ? o.create(d) : o.create, 'POST', d);
      form.reset(); toast('Saved'); await refresh(); o.after && o.after();
    } catch (x) { toast(x.message, 1); }
  };
  refresh().catch(x => toast(x.message, 1));
  return {refresh};
}
