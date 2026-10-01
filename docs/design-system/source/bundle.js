/* @ds-bundle: {"format":4,"namespace":"Klar","components":[{"name":"Button"},{"name":"SegmentedControl"},{"name":"GlassPanel"},{"name":"RiskPill"},{"name":"StatusPill"},{"name":"EvidenceTag"},{"name":"Icon"},{"name":"SidebarNav"},{"name":"Citation"},{"name":"FactCard"},{"name":"StepRow"},{"name":"StepCard"},{"name":"CheckProgress"},{"name":"ObligationItem"},{"name":"FillMarker"},{"name":"ResultSummary"},{"name":"InventoryTable"},{"name":"DescriptionField"},{"name":"FactQuestion"},{"name":"ChatMessage"},{"name":"VersionDiff"},{"name":"InterviewPanel"},{"name":"Timeline"},{"name":"Notice"},{"name":"Reveal"},{"name":"Typewriter"},{"name":"MistGround"},{"name":"Composer"},{"name":"ChangeBanner"},{"name":"LawDate"},{"name":"LawSwitch"},{"name":"LawNotice"}]} */
(function () {
  var React = window.React;
  var h = React.createElement;
  function cx() { var out = []; for (var i = 0; i < arguments.length; i++) { if (arguments[i]) out.push(arguments[i]); } return out.join(' '); }
  function omit(o, keys) { var r = {}; for (var k in o) { if (Object.prototype.hasOwnProperty.call(o, k) && keys.indexOf(k) < 0) r[k] = o[k]; } return r; }

  /* ---------- Icon: the 24 px line set, stroke in currentColor ---------- */
  var ICONS = {
    inventory: { w: 1.8, cap: 'round', join: 'round', d: [['rect', { x: 3.5, y: 3.5, width: 7, height: 7, rx: 2 }], ['rect', { x: 13.5, y: 3.5, width: 7, height: 7, rx: 2 }], ['rect', { x: 3.5, y: 13.5, width: 7, height: 7, rx: 2 }], ['rect', { x: 13.5, y: 13.5, width: 7, height: 7, rx: 2 }]] },
    classify: { w: 1.8, cap: 'round', d: [['circle', { cx: 12, cy: 12, r: 8.5 }], ['path', { d: 'M12 8v8M8 12h8' }]] },
    obligations: { w: 1.8, cap: 'round', join: 'round', d: [['path', { d: 'M10 6.5h10M10 12h10M10 17.5h10' }], ['path', { d: 'M3.5 6.5l1.4 1.4 2.3-2.4M3.5 12l1.4 1.4 2.3-2.4M3.5 17.5l1.4 1.4 2.3-2.4' }]] },
    documents: { w: 1.8, cap: 'round', join: 'round', d: [['path', { d: 'M7 3.5h7l4.5 4.5v12a1 1 0 0 1-1 1H7a1 1 0 0 1-1-1v-15a1 1 0 0 1 1-1z' }], ['path', { d: 'M14 3.5V8h4.5' }], ['path', { d: 'M9 13h6M9 16.5h6' }]] },
    ask: { w: 1.8, join: 'round', d: [['path', { d: 'M5 5.5h14a1.5 1.5 0 0 1 1.5 1.5v8a1.5 1.5 0 0 1-1.5 1.5H10l-4.5 3.5v-3.5H5A1.5 1.5 0 0 1 3.5 15V7A1.5 1.5 0 0 1 5 5.5z' }]] },
    add: { w: 2.2, cap: 'round', d: [['path', { d: 'M12 5v14M5 12h14' }]] },
    privacy: { w: 1.8, cap: 'round', join: 'round', d: [['path', { d: 'M12 3.5l7.5 3v5.5c0 4.4-3.2 7.6-7.5 8.5-4.3-.9-7.5-4.1-7.5-8.5V6.5z' }]] },
    check: { w: 2.8, cap: 'round', join: 'round', d: [['path', { d: 'M5 12.5l4.5 4.5L19 7.5' }]] },
    info: { w: 1.8, cap: 'round', join: 'round', d: [['circle', { cx: 12, cy: 12, r: 8.5 }], ['path', { d: 'M12 8v4.5M12 16h.01' }]] },
    'chevron-down': { w: 2, cap: 'round', join: 'round', d: [['path', { d: 'M6 9l6 6 6-6' }]] },
    send: { w: 2.2, cap: 'round', join: 'round', d: [['path', { d: 'M12 19V5M6 11l6-6 6 6' }]] },
    alert: { w: 2.6, cap: 'round', d: [['path', { d: 'M12 7v6' }], ['path', { d: 'M12 17h.01' }]] }
  };
  function Icon(p) {
    var def = ICONS[p.name] || ICONS.info; var size = p.size || 18;
    var kids = def.d.map(function (e, i) { return h(e[0], Object.assign({ key: i }, e[1])); });
    return h('svg', { width: size, height: size, viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', strokeWidth: p.strokeWidth || def.w, strokeLinecap: def.cap, strokeLinejoin: def.join, 'aria-hidden': p.title ? undefined : 'true', role: p.title ? 'img' : undefined, 'aria-label': p.title, className: p.className }, kids);
  }
  Icon.names = Object.keys(ICONS);

  /* ---------- Button ---------- */
  function Button(p) {
    var variant = p.variant || 'primary', size = p.size || 'md';
    var rest = omit(p, ['variant', 'size', 'icon', 'children', 'className', 'href', 'type']);
    var cls = cx('kl-btn', 'kl-btn-' + variant, size !== 'md' && 'kl-btn-' + size, p.className);
    var kids = [p.icon ? h(Icon, { key: 'i', name: p.icon, size: size === 'sm' ? 14 : 16 }) : null, p.children];
    if (p.href) return h('a', Object.assign({ className: cls, href: p.href }, rest), kids);
    return h('button', Object.assign({ className: cls, type: p.type || 'button' }, rest), kids);
  }

  /* ---------- SegmentedControl ---------- */
  var useIsoLayout = typeof window !== 'undefined' ? React.useLayoutEffect : React.useEffect;
  function reduceMotion() { return typeof window !== 'undefined' && window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches; }
  function SegmentedControl(p) {
    var st = React.useState(p.defaultValue != null ? p.defaultValue : (p.options[0] && p.options[0].value));
    var value = p.value != null ? p.value : st[0];
    var seg = React.useRef(null), thumb = React.useRef(null), prev = React.useRef(value), timer = React.useRef(0);
    var box = function (v) { var b = seg.current && seg.current.querySelector('[data-value="' + String(v) + '"]'); return b ? { l: b.offsetLeft, w: b.offsetWidth } : null; };
    var put = function (b, tr) { var t = thumb.current; if (!t || !b) return; t.style.transition = tr || 'none'; t.style.left = b.l + 'px'; t.style.width = b.w + 'px'; };
    useIsoLayout(function () {
      var to = box(value), from = box(prev.current);
      if (seg.current) seg.current.classList.add('is-live');
      if (!from || prev.current === value || reduceMotion()) put(to);
      else {
        var l = Math.min(from.l, to.l), r = Math.max(from.l + from.w, to.l + to.w);
        put({ l: l, w: r - l }, 'left var(--liquid-stretch) var(--ease-settle), width var(--liquid-stretch) var(--ease-settle)');
        clearTimeout(timer.current);
        timer.current = setTimeout(function () { put(to, 'left var(--liquid-settle) var(--ease-out), width var(--liquid-settle) var(--ease-out)'); }, 150);
      }
      prev.current = value;
    }, [value]);
    React.useEffect(function () {
      if (typeof document !== 'undefined' && document.fonts && document.fonts.ready) document.fonts.ready.then(function () { put(box(prev.current)); });
      return function () { clearTimeout(timer.current); };
    }, []);
    return h('div', { ref: seg, className: cx('kl-seg', p.className), role: 'group', 'aria-label': p.label },
      h('span', { ref: thumb, className: 'kl-seg-thumb', 'aria-hidden': 'true' }),
      p.options.map(function (o) {
        return h('button', { key: o.value, type: 'button', 'data-value': String(o.value), 'aria-pressed': String(o.value === value),
          onClick: function () { if (o.value === value) return; if (p.value == null) st[1](o.value); if (p.onChange) p.onChange(o.value); } }, o.label);
      }));
  }


  /* ---------- GlassPanel ---------- */
  function GlassPanel(p) {
    var tone = p.tone || 'glass', radius = p.radius || 'card';
    var rest = omit(p, ['tone', 'radius', 'as', 'padded', 'className', 'children', 'glint', 'lift', 'onPointerMove']);
    var cls = cx(tone === 'glass' ? 'kl-glass' : 'kl-glass-' + tone, 'kl-r-' + radius, p.padded !== false && 'kl-pad', p.glint && 'kl-glint', p.lift && 'kl-lift', p.className);
    var move = function (e) {
      if (p.glint) {
        var el = e.currentTarget, r = el.getBoundingClientRect(), s = el.offsetWidth ? r.width / el.offsetWidth : 1;
        el.style.setProperty('--mx', ((e.clientX - r.left) / s) + 'px'); el.style.setProperty('--my', ((e.clientY - r.top) / s) + 'px');
      }
      if (p.onPointerMove) p.onPointerMove(e);
    };
    return h(p.as || 'div', Object.assign({ className: cls, onPointerMove: move }, rest), p.children);
  }


  /* ---------- RiskPill / StatusPill / EvidenceTag ---------- */
  var RISK = { prohibited: 'Prohibited', high: 'High-risk', limited: 'Limited risk', minimal: 'Minimal risk', out: 'Out of scope' };
  function RiskPill(p) {
    var rc = p.riskClass || 'high';
    var label = p.children || (RISK[rc] + (p.assumed ? ', assumed' : ''));
    return h('span', { className: cx('kl-pill', 'kl-risk-' + rc, p.size === 'sm' && 'kl-pill-sm', p.className) }, h('span', { className: 'kl-dot', 'aria-hidden': 'true' }), label);
  }
  var STATUS = { decided: 'Decided', ambiguous: 'Legally ambiguous', 'needs-info': 'Needs more information', draft: 'DRAFT' };
  function StatusPill(p) {
    var s = p.status || 'decided';
    return h('span', { className: cx('kl-pill', 'kl-status-' + s, p.size === 'sm' && 'kl-pill-sm', p.className) }, p.children || STATUS[s]);
  }
  var EVIDENCE = { stated: 'Stated', inferred: 'Inferred', assumed: 'Assumed' };
  function EvidenceGlyph(kind) {
    if (kind === 'stated') return h('svg', { width: 10, height: 10, viewBox: '0 0 10 10', 'aria-hidden': 'true' }, h('circle', { cx: 5, cy: 5, r: 4, fill: 'currentColor' }));
    if (kind === 'inferred') return h('svg', { width: 10, height: 10, viewBox: '0 0 10 10', 'aria-hidden': 'true' }, h('circle', { cx: 5, cy: 5, r: 3.5, fill: 'none', stroke: 'currentColor', strokeWidth: 1.4 }), h('path', { d: 'M5 1.5a3.5 3.5 0 0 1 0 7z', fill: 'currentColor' }));
    return h('svg', { width: 10, height: 10, viewBox: '0 0 10 10', 'aria-hidden': 'true' }, h('circle', { cx: 5, cy: 5, r: 3.5, fill: 'none', stroke: 'currentColor', strokeWidth: 1.4 }));
  }
  function EvidenceTag(p) {
    var k = p.kind || 'stated';
    return h('span', { className: cx('kl-tag', p.className) }, EvidenceGlyph(k), p.children || EVIDENCE[k]);
  }

  /* ---------- SidebarNav ---------- */
  function SidebarNav(p) {
    return h('nav', { className: cx('kl-side', p.className), 'aria-label': p.label || 'App' },
      p.items.map(function (it) {
        return h('a', { key: it.label, href: it.href || '#', className: cx('kl-side-item', it.active && 'is-active'), 'aria-current': it.active ? 'page' : undefined },
          h(Icon, { name: it.icon, size: 18 }), it.label);
      }));
  }

  /* ---------- Citation ---------- */
  function Citation(p) {
    return h('blockquote', { className: cx('kl-citation', p.className) },
      h('p', { className: 'kl-citation-text' }, '\u201c', p.children, '\u201d'),
      p.source ? h('footer', { className: 'kl-citation-source' }, p.source) : null);
  }

  /* ---------- FactCard ---------- */
  function FactCard(p) {
    var ev = p.evidence || 'stated', assumed = ev === 'assumed';
    return h('div', { className: cx('kl-fact kl-glass-thin', assumed && 'is-assumed', p.className) },
      h('span', { className: 'kl-fact-text' }, p.fact),
      assumed
        ? h('div', { className: 'kl-fact-row' }, h(EvidenceTag, { kind: ev }, p.evidenceLabel),
            h('div', { className: 'kl-fact-actions' },
              h(Button, { variant: 'ghost', size: 'sm', onClick: p.onChange }, p.changeLabel || 'Change'),
              h(Button, { size: 'sm', onClick: p.onConfirm }, p.confirmLabel || 'Confirm')))
        : h(EvidenceTag, { kind: ev, className: 'kl-self-start' }, p.evidenceLabel));
  }

  /* ---------- StepRow / StepCard ---------- */
  function StepRow(p) {
    var st = React.useState(!!p.defaultExpanded); var open = p.expanded != null ? p.expanded : st[0];
    var style = p.columns ? { gridTemplateColumns: p.columns } : undefined;
    return h('button', { type: 'button', className: cx('kl-steprow', p.className), style: style, 'aria-expanded': String(open),
      onClick: function () { if (p.expanded == null) st[1](!open); if (p.onToggle) p.onToggle(!open); } },
      h('span', { className: 'kl-steprow-name' }, p.name),
      h('span', { className: 'kl-steprow-decision' }, p.decision),
      h('span', { className: 'kl-steprow-ref' }, p.reference),
      h(Icon, { name: 'chevron-down', size: 16 }));
  }
  function StepCard(p) {
    var rows = [];
    if (p.decision) rows.push(h('dt', { key: 'dl' }, p.decisionLabel || 'Decision'), h('dd', { key: 'dd' }, p.decision));
    if (p.fact) rows.push(h('dt', { key: 'fl' }, p.factLabel || 'Fact it rests on'), h('dd', { key: 'fd' }, p.fact, p.evidence ? h(EvidenceTag, { kind: p.evidence }, p.evidenceLabel) : null));
    return h('article', { className: cx('kl-glass kl-stepcard', p.highlight && 'is-highlight', p.className) },
      h('header', { className: 'kl-stepcard-head' },
        h('h3', { className: 'kl-stepcard-title' }, p.name, p.outcome || null),
        p.reference ? h('span', { className: 'kl-stepcard-ref' }, p.reference) : null),
      rows.length ? h('dl', { className: 'kl-stepcard-grid', style: { margin: 0 } }, rows) : null,
      p.quotes && p.quotes.length ? h('div', { className: 'kl-stepcard-quotes' }, p.quotes.map(function (q, i) { return h(Citation, { key: i, source: q.source }, q.text); })) : null,
      p.children);
  }

  /* ---------- CheckProgress ---------- */
  function CheckProgress(p) {
    return h('ol', { className: cx('kl-progress', p.className), 'aria-live': 'polite' },
      p.steps.map(function (s, i) {
        var state = s.state || 'waiting';
        var mark = state === 'done' ? h(Icon, { name: 'check', size: 13 }) : state === 'error' ? h(Icon, { name: 'alert', size: 13 }) : null;
        return h('li', { key: i, className: 'kl-progress-step is-' + state },
          h('span', { className: 'kl-progress-mark', 'aria-hidden': 'true' }, mark),
          h('span', { className: 'kl-progress-body' },
            h('span', { className: 'kl-progress-name' }, s.name),
            s.detail ? h('span', { className: 'kl-progress-detail' }, s.detail) : null,
            s.matches && s.matches.length ? h('span', { className: 'kl-progress-matches' }, s.matches.map(function (m, j) { return h('span', { key: j, className: 'kl-progress-match kl-glass-thin' }, m); })) : null));
      }));
  }


  /* ---------- ObligationItem ---------- */
  function ObligationItem(p) {
    return h('li', { className: cx('kl-obligation', p.className) },
      h('input', { type: 'checkbox', 'aria-label': typeof p.label === 'string' ? p.label : undefined, defaultChecked: p.defaultChecked, checked: p.checked, onChange: p.onChange }),
      h('span', { className: 'kl-obligation-label' }, p.label),
      p.docLabel ? h('a', { className: 'kl-obligation-doc', href: p.docHref || '#' }, p.docLabel) : null,
      h('span', { className: 'kl-obligation-ref', style: p.referenceWidth ? { minWidth: p.referenceWidth } : undefined }, p.reference));
  }

  /* ---------- FillMarker ---------- */
  function FillMarker(p) {
    return h('p', { className: cx('kl-fill', p.className) }, p.children || 'To fill in.');
  }


  /* ---------- ResultSummary ---------- */
  var DOT = { prohibited: '--risk-prohibited-dot', high: '--risk-high-dot', limited: '--risk-limited-dot', minimal: '--risk-minimal-dot', out: '--risk-out-dot' };
  function ResultSummary(p) {
    var rc = p.riskClass || 'high';
    var review = p.legalReview === undefined ? (rc === 'high' || rc === 'prohibited' || p.status === 'ambiguous') : p.legalReview;
    return h('section', { className: cx('kl-glass kl-result', rc === 'high' && 'is-high', p.className), 'aria-label': p.label || 'Result' },
      h('div', { className: 'kl-result-top' },
        h('div', { className: 'kl-result-main' },
          h('div', { className: 'kl-result-class' },
            h('span', { className: 'kl-result-dot', 'aria-hidden': 'true', style: { background: 'var(' + DOT[rc] + ')', boxShadow: rc === 'high' ? '0 0 0 5px rgba(229,122,30,.18)' : undefined } }),
            h('span', { className: 'kl-result-name' }, p.classLabel || RISK[rc]),
            h(StatusPill, { status: p.status || 'decided' }, p.statusLabel)),
          p.statement ? h('p', { className: 'kl-result-statement' }, p.statement) : null),
        p.dutiesFrom ? h('div', { className: 'kl-result-date kl-glass-thin' },
          h('span', { className: 'kl-result-date-label' }, p.dutiesFromLabel || 'Your duties apply from'),
          h('span', { className: 'kl-result-date-value' }, p.dutiesFrom),
          p.dutiesNote ? h('span', { className: 'kl-result-date-note' }, p.dutiesNote) : null) : null),
      review ? h('div', { className: 'kl-result-review' }, h(Icon, { name: 'info', size: 16 }),
        p.legalReviewText || 'For a high-risk result, we recommend a legal review before you rely on it.') : null);
  }

  /* ---------- InventoryTable ---------- */
  var INV_COLS = ['Tool', 'Your role', 'Class', 'Basis', 'Applies from', 'Status'];
  function InventoryTable(p) {
    var cols = p.columns || INV_COLS;
    return h('div', { className: cx('kl-glass kl-table', p.className), role: 'table', 'aria-label': p.label || 'AI inventory' },
      h('div', { className: 'kl-table-row kl-table-head', role: 'row' }, cols.map(function (c, i) { return h('span', { key: i, role: 'columnheader' }, c); })),
      p.rows.map(function (r, i) {
        var status = (r.status || 'decided') === 'decided'
          ? h('span', { className: 'kl-table-decided' }, r.statusLabel || STATUS.decided)
          : h(StatusPill, { status: r.status }, r.statusLabel);
        return h(r.href ? 'a' : 'div', { key: i, className: 'kl-table-row kl-table-body', role: 'row', href: r.href },
          h('span', { className: 'kl-table-tool', role: 'cell' }, h('span', { className: 'kl-table-name' }, r.name), r.what ? h('span', { className: 'kl-table-what' }, r.what) : null),
          h('span', { role: 'cell' }, r.role || '\u2013'),
          h('span', { role: 'cell' }, h(RiskPill, { riskClass: r.riskClass, assumed: r.assumed }, r.classLabel)),
          h('span', { role: 'cell' }, r.basis || '\u2013'),
          h('span', { role: 'cell' }, r.from || '\u2013'),
          h('span', { role: 'cell' }, status));
      }));
  }

  /* ---------- DescriptionField ---------- */
  var DESC_TIPS = ['what it decides or suggests', 'who it affects', 'bought or built', 'anything you changed'];
  function DescriptionField(p) {
    var id = p.id || 'kl-desc';
    return h('div', { className: cx('kl-desc', p.className) },
      h('label', { className: 'kl-desc-label', htmlFor: id }, p.label || 'In your own words'),
      h('textarea', { id: id, value: p.value, defaultValue: p.defaultValue, onChange: p.onChange, placeholder: p.placeholder }),
      h('div', { className: 'kl-desc-tips' }, h('span', { className: 'kl-muted' }, p.tipsLabel || 'Helpful to mention:'),
        (p.tips || DESC_TIPS).map(function (t, i) { return h('span', { key: i, className: 'kl-desc-tip kl-glass-thin' }, t); })),
      p.privacyNote === null ? null : h('div', { className: 'kl-desc-privacy' }, h(Icon, { name: 'privacy', size: 16 }),
        p.privacyNote || 'Leave out names and other personal details of applicants or staff.'));
  }

  /* ---------- FactQuestion ---------- */
  function FactQuestion(p) {
    var opts = p.options || [{ value: 'yes', label: 'Yes' }, { value: 'no', label: 'No' }, { value: 'unsure', label: 'Not sure' }];
    return h('div', { className: cx('kl-question', p.className) },
      h('div', { className: 'kl-question-text' },
        h('p', { className: 'kl-question-q' }, p.question),
        p.hint ? h('p', { className: 'kl-question-hint' }, p.hint) : null),
      h(SegmentedControl, { label: typeof p.question === 'string' ? p.question : 'Answer', options: opts, value: p.value, defaultValue: p.defaultValue, onChange: p.onChange }));
  }

  /* ---------- ChatMessage ---------- */
  function ChatMessage(p) {
    if ((p.from || 'klar') === 'user') return h('div', { className: cx('kl-msg kl-msg-user', p.className) }, p.children);
    return h('div', { className: cx('kl-msg kl-msg-klar kl-glass-thin', p.className) },
      h('p', null, p.children),
      p.citations && p.citations.length ? h('div', { className: 'kl-msg-cites' }, p.citations.map(function (c, i) {
        return h('a', { key: i, className: 'kl-cite-chip', href: c.href || '#' }, c.label);
      })) : null);
  }

  /* ---------- VersionDiff ---------- */
  function VersionDiff(p) {
    var head = p.columns || ['Original', 'Amended'];
    var cells = [h('span', { key: 'h0', className: 'kl-diff-head' }), h('span', { key: 'h1', className: 'kl-diff-head' }, head[0]), h('span', { key: 'h2', className: 'kl-diff-head' }, head[1])];
    p.rows.forEach(function (r, i) {
      var changed = r.before !== r.after;
      cells.push(h('span', { key: 'l' + i }, r.label), h('span', { key: 'b' + i, className: cx('kl-diff-before', changed && 'is-changed') }, r.before), h('span', { key: 'a' + i, className: cx('kl-diff-after', changed && 'is-changed') }, r.after));
    });
    return h('div', { className: p.className }, h('div', { className: 'kl-diff' }, cells), p.note ? h('p', { className: 'kl-diff-note' }, p.note) : null);
  }

  /* ---------- InterviewPanel ---------- */
  function InterviewPanel(p) {
    var answered = p.answered || [], upcoming = p.upcoming || [];
    var total = p.total || (answered.length + upcoming.length + (p.question ? 1 : 0));
    var id = p.inputId || 'kl-interview-input';
    return h('section', { className: cx('kl-interview', p.className), 'aria-label': p.title || 'Guided interview' },
      h('div', { className: 'kl-col', style: { gap: 10 } },
        h('div', { className: 'kl-interview-head' }, h('h2', { className: 'kl-interview-title' }, p.title || 'Guided interview'),
          h('span', { className: 'kl-interview-count' }, p.countLabel || (answered.length + ' of ' + total + ' answered'))),
        h('div', { className: 'kl-bar', role: 'progressbar', 'aria-valuemin': 0, 'aria-valuemax': total, 'aria-valuenow': answered.length },
          h('div', { className: 'kl-bar-fill', style: { width: (total ? 100 * answered.length / total : 0) + '%' } }))),
      answered.length ? h('ul', { className: 'kl-interview-list' }, answered.map(function (a, i) {
        return h('li', { key: i, className: 'kl-interview-item is-answered' }, h('span', { className: 'kl-interview-mark' }, h(Icon, { name: 'check', size: 11, strokeWidth: 3 })), a);
      })) : null,
      p.question ? h('div', { className: 'kl-interview-current kl-glass-thin' },
        h('label', { className: 'kl-interview-q', htmlFor: id }, p.question),
        h('input', { id: id, className: 'kl-input', type: 'text', placeholder: p.placeholder, value: p.value, defaultValue: p.defaultValue, onChange: p.onChange }),
        p.hint ? h('p', { className: 'kl-interview-hint' }, p.hint) : null,
        h('div', { className: 'kl-interview-actions' },
          h(Button, { variant: 'ghost', size: 'sm', onClick: p.onSkip }, p.skipLabel || 'Skip for now'),
          h(Button, { size: 'sm', onClick: p.onSave }, p.saveLabel || 'Save answer'))) : null,
      upcoming.length ? h('ul', { className: 'kl-interview-list' }, upcoming.map(function (u, i) {
        return h('li', { key: i, className: 'kl-interview-item is-upcoming' }, h('span', { className: 'kl-interview-mark' }), u);
      })) : null);
  }

  /* ---------- Timeline ---------- */
  function Timeline(p) {
    var today = p.todayAt != null ? p.todayAt : null;
    var line = today == null ? 'rgba(15,27,45,.18)' : 'linear-gradient(90deg, var(--lens-blue) 0%, var(--lens-blue) ' + today + '%, rgba(15,27,45,.18) ' + today + '%)';
    return h('div', { className: cx('kl-timeline', p.className) },
      h('div', { className: 'kl-timeline-line', style: { background: line }, 'aria-hidden': 'true' }),
      today == null ? null : h('span', { className: 'kl-timeline-today kl-glass-thin', style: { left: today + '%' } }, p.todayLabel || 'Today'),
      p.items.map(function (it, i) {
        return h('div', { key: i, className: cx('kl-timeline-item', it.past && 'is-past') },
          h('span', { className: 'kl-timeline-dot', 'aria-hidden': 'true' }),
          h('div', { className: 'kl-timeline-date' }, it.date),
          h('div', { className: 'kl-timeline-text' }, it.text));
      }));
  }

  /* ---------- Notice ---------- */
  function Notice(p) {
    return h('p', { className: cx('kl-notice', p.className) }, p.children || 'Guidance, not legal advice. Klar is an AI system.');
  }


  /* ---------- Reveal: arrives when scrolled into view, leaves in reverse when scrolled back ---------- */
  function Reveal(p) {
    var ref = React.useRef(null);
    React.useEffect(function () {
      var el = ref.current; if (!el || reduceMotion() || !('IntersectionObserver' in window)) return;
      var first = true, t = 0;
      var move = function (to) {
        el.classList.remove('is-entering', 'is-leaving');
        if (to === 'in') { el.classList.add('is-entering'); el.classList.remove('is-pending', 'is-above'); }
        else { el.classList.add('is-leaving', to); }
        clearTimeout(t); t = setTimeout(function () { el.classList.remove('is-entering', 'is-leaving'); }, to === 'in' ? 1900 + (p.delay || 0) : 700);
      };
      var io = new IntersectionObserver(function (es) {
        es.forEach(function (en) {
          var hidden = el.classList.contains('is-pending') || el.classList.contains('is-above');
          if (first) { first = false; if (!en.isIntersecting) el.classList.add('is-pending'); return; }
          if (en.isIntersecting && en.intersectionRatio >= 0.15) { if (hidden) move('in'); }
          else if (!en.isIntersecting && !hidden) {
            var mid = en.rootBounds ? en.rootBounds.top + en.rootBounds.height / 2 : window.innerHeight / 2;
            move(en.boundingClientRect.top > mid ? 'is-pending' : 'is-above');
          }
        });
      }, { threshold: [0, 0.15], rootMargin: '0px 0px -8% 0px' });
      io.observe(el);
      return function () { io.disconnect(); clearTimeout(t); };
    }, []);
    var style = Object.assign({}, p.style || {}, { '--kl-delay': (p.delay || 0) + 'ms' });
    return h(p.as || 'div', { ref: ref, className: cx('kl-reveal', p.variant === 'focus' && 'kl-reveal-focus', p.className), style: style }, p.children);
  }

  /* ---------- Typewriter: lines type themselves out when they come into view ---------- */
  function Typewriter(p) {
    var ref = React.useRef(null);
    var speed = p.speed || 11, pause = p.pause != null ? p.pause : 70;
    React.useEffect(function () {
      var el = ref.current; if (!el || reduceMotion()) return;
      var t = 0;
      var type = function () {
        var lines = el.children, at = p.startDelay != null ? p.startDelay : 300;
        Array.prototype.forEach.call(lines, function (ln, k) {
          var n = (ln.textContent || '').length;
          ln.style.setProperty('--n', n); ln.style.setProperty('--t', at + 'ms'); ln.style.setProperty('--dur', Math.max(1, n * speed) + 'ms');
          ln.classList.toggle('is-last', k === lines.length - 1); at += n * speed + pause;
        });
        el.classList.remove('is-typing', 'is-pending'); void el.offsetWidth; el.classList.add('is-typing');
        clearTimeout(t); t = setTimeout(function () { el.classList.remove('is-typing'); }, at + 2200);
      };
      if (!('IntersectionObserver' in window)) { type(); return; }
      var first = true;
      var io = new IntersectionObserver(function (es) {
        es.forEach(function (en) {
          if (en.isIntersecting && en.intersectionRatio >= 0.15) { first = false; type(); }
          else if (!en.isIntersecting) { if (first) { first = false; el.classList.add('is-pending'); } else if (p.replay !== false) { clearTimeout(t); el.classList.remove('is-typing'); el.classList.add('is-pending'); } }
        });
      }, { threshold: [0, 0.15] });
      io.observe(el);
      return function () { io.disconnect(); clearTimeout(t); };
    }, []);
    return h('div', { ref: ref, className: cx('kl-type', p.className), 'aria-label': p.label }, (p.lines || []).map(function (l, i) { return h('div', { key: i }, l); }));
  }

  /* ---------- MistGround: the page backdrop; lights drift as you scroll, one follows the cursor ---------- */
  function MistGround(p) {
    var ref = React.useRef(null), la = React.useRef(null), lb = React.useRef(null), lc = React.useRef(null);
    React.useEffect(function () {
      var el = ref.current; if (!el || reduceMotion()) return;
      var raf = 0, craf = 0, c = { x: 0, y: 0, tx: 0, ty: 0, on: false };
      var follow = function () {
        if (craf) return;
        var step = function () {
          c.x += (c.tx - c.x) * 0.09; c.y += (c.ty - c.y) * 0.09;
          if (lc.current) lc.current.style.transform = 'translate3d(' + (c.x - 380) + 'px,' + (c.y - 380) + 'px,0)';
          craf = (Math.abs(c.tx - c.x) > 0.5 || Math.abs(c.ty - c.y) > 0.5) ? requestAnimationFrame(step) : 0;
        };
        craf = requestAnimationFrame(step);
      };
      var onMove = function (e) {
        if (p.cursorLight === false) return;
        var r = el.getBoundingClientRect(), s = el.offsetWidth ? r.width / el.offsetWidth : 1;
        c.tx = (e.clientX - r.left) / s; c.ty = (e.clientY - r.top) / s;
        if (!c.on) { c.on = true; c.x = c.tx; c.y = c.ty; if (lc.current) lc.current.classList.add('is-on'); }
        follow();
      };
      var onLeave = function () { c.on = false; if (lc.current) lc.current.classList.remove('is-on'); };
      var onScroll = function () {
        if (p.drift === false || raf) return;
        raf = requestAnimationFrame(function () {
          raf = 0; var r = el.getBoundingClientRect(), s = el.offsetWidth ? r.width / el.offsetWidth : 1, off = Math.max(0, -r.top / s);
          if (la.current) la.current.style.transform = 'translateY(' + (off * 0.32) + 'px)';
          if (lb.current) lb.current.style.transform = 'translateY(' + (-off * 0.2) + 'px)';
        });
      };
      el.addEventListener('pointermove', onMove); el.addEventListener('pointerleave', onLeave);
      window.addEventListener('scroll', onScroll, { capture: true, passive: true });
      return function () { el.removeEventListener('pointermove', onMove); el.removeEventListener('pointerleave', onLeave); window.removeEventListener('scroll', onScroll, { capture: true }); cancelAnimationFrame(raf); cancelAnimationFrame(craf); };
    }, []);
    return h('div', { ref: ref, className: cx('kl-ground', p.className), style: p.style },
      h('div', { className: 'kl-ground-lights', 'aria-hidden': 'true' },
        p.drift === false ? null : h('div', { ref: la, className: 'kl-ground-light is-a' }),
        p.drift === false ? null : h('div', { ref: lb, className: 'kl-ground-light is-b' }),
        p.cursorLight === false ? null : h('div', { ref: lc, className: 'kl-ground-cursor' })),
      h('div', { className: 'kl-ground-content' }, p.children));
  }

  /* ---------- Composer: one field with the send arrow inside ---------- */
  function Composer(p) {
    var st = React.useState(p.defaultValue || ''), q = p.value != null ? p.value : st[0];
    var sending = React.useState(false), t = React.useRef(0);
    var ready = !!String(q).trim();
    var set = function (v) { if (p.value == null) st[1](v); if (p.onChange) p.onChange(v); };
    var send = function () {
      if (!String(q).trim()) return;
      if (p.onSend) p.onSend(q);
      set(''); sending[1](true); clearTimeout(t.current); t.current = setTimeout(function () { sending[1](false); }, 650);
    };
    React.useEffect(function () { return function () { clearTimeout(t.current); }; }, []);
    var id = p.id || 'kl-composer';
    return h('div', { className: cx('kl-composer', p.className) },
      h('label', { htmlFor: id, style: { position: 'absolute', width: 1, height: 1, overflow: 'hidden', clip: 'rect(0 0 0 0)' } }, p.label || 'Your question'),
      h('textarea', { id: id, rows: 1, placeholder: p.placeholder || 'Ask a question about the AI Act', value: q,
        onChange: function (e) { set(e.target.value); },
        onKeyDown: function (e) { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(); } } }),
      h('button', { type: 'button', className: cx('kl-send', (ready || sending[0]) && 'is-ready', sending[0] && 'is-sending'), 'aria-label': p.sendLabel || 'Ask', 'aria-disabled': String(!ready), onClick: send },
        h(Icon, { name: 'send', size: 18 })));
  }

  /* ---------- ChangeBanner: what a re-run changed ---------- */
  function ChangeBanner(p) {
    var arrow = h('svg', { width: 18, height: 18, viewBox: '0 0 24 24', fill: 'none', stroke: 'var(--lens-blue)', strokeWidth: 2, strokeLinecap: 'round', strokeLinejoin: 'round', 'aria-hidden': 'true' }, h('path', { d: 'M5 12h14M13 6l6 6-6 6' }));
    return h('section', { className: cx('kl-glass kl-change', p.className), 'aria-label': p.title || 'Your answer changed the result' },
      h('div', { className: 'kl-change-text' },
        h('div', { className: 'kl-row', style: { gap: 10 } }, h('h2', { className: 'kl-change-title' }, p.title || 'Your answer changed the result'), p.runLabel ? h(StatusPill, { status: 'decided', size: 'sm' }, p.runLabel) : null),
        p.children ? h('p', { className: 'kl-change-body' }, p.children) : null),
      h('div', { className: 'kl-change-move' }, p.before, arrow, p.after),
      p.onUndo ? h(Button, { variant: 'ghost', size: 'sm', onClick: p.onUndo }, p.undoLabel || 'Undo answer') : null);
  }

  /* ---------- Law version: dates that follow the switch ---------- */
  function LawDate(p) {
    return h('span', { className: p.className }, h('span', { className: 'kl-law-a' }, p.amended), h('span', { className: 'kl-law-o' }, p.original));
  }
  function LawNotice(p) {
    return h('div', { className: cx('kl-law-notice kl-glass-thin', p.className), role: 'status' }, h(Icon, { name: 'info', size: 16 }),
      h('span', null, p.children || 'You\u2019re viewing the original 2024 text. The Digital Omnibus moved the Annex III high-risk date to 2 December 2027; Klar uses the amended text by default.'));
  }
  function LawSwitch(p) {
    var ref = React.useRef(null);
    var apply = function (v) {
      var scope = (p.scope && p.scope.current) || (ref.current && ref.current.closest('.kl-law-scope')) || (typeof document !== 'undefined' && document.documentElement);
      if (scope) scope.classList.toggle('kl-law-original', v === 'original');
      if (p.onChange) p.onChange(v);
    };
    return h('span', { ref: ref, style: { display: 'inline-flex' } }, h(SegmentedControl, { label: p.label || 'Law version', defaultValue: p.defaultValue || 'amended', value: p.value,
      options: [{ value: 'amended', label: p.amendedLabel || 'As amended, 27 Jul 2026' }, { value: 'original', label: p.originalLabel || 'Original, 2024' }], onChange: apply }));
  }

  window.Klar = { Button: Button, SegmentedControl: SegmentedControl, GlassPanel: GlassPanel, RiskPill: RiskPill, StatusPill: StatusPill, EvidenceTag: EvidenceTag, Icon: Icon, SidebarNav: SidebarNav, Citation: Citation, FactCard: FactCard, StepRow: StepRow, StepCard: StepCard, CheckProgress: CheckProgress, ObligationItem: ObligationItem, FillMarker: FillMarker, ResultSummary: ResultSummary, InventoryTable: InventoryTable, DescriptionField: DescriptionField, FactQuestion: FactQuestion, ChatMessage: ChatMessage, VersionDiff: VersionDiff, InterviewPanel: InterviewPanel, Timeline: Timeline, Notice: Notice, Reveal: Reveal, Typewriter: Typewriter, MistGround: MistGround, Composer: Composer, ChangeBanner: ChangeBanner, LawDate: LawDate, LawSwitch: LawSwitch, LawNotice: LawNotice };
})();
