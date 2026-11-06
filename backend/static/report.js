(() => {
  const $ = (id) => document.getElementById(id);
  const JOB = window.JOB_ID, SIG = window.SIGNALS || [], VSIG = window.VOICE_SIGNALS || [];
  const S = {
    en: {
      back: "← Back to results", print: "Save as PDF", lang: "عربي", loading: "Preparing your report…",
      notfound: "This analysis doesn't exist or was deleted.", notready: "The analysis isn't finished yet. Come back to this page when it is.",
      failed: "This analysis failed, so there is no report.", title: "Practice report", tagline: "AI body language and voice coaching",
      date: "Date", dur: "Duration", scn: "Situation", vis: "Shoulders visible", goal: "Your goal",
      score: "Practice score", body: "Body", voice: "Voice", lost: "What lowered the score", none: "Nothing lowered the score.", pts: "points",
      prio: "Start with these", together: "Voice and body together", moments: "Advice by moment", strong: "What went well",
      said: "You said", stat: "{p}% of the time · {n}× · longest {l}s", tl: "Timeline", sigs: "Signals",
      c_sig: "Signal", c_time: "Share of time", c_times: "Times", c_long: "Longest", vo: "Voice and speech",
      level: "Loudness", pace: "Speaking pace", pitch: "Pitch variation", share: "Time speaking",
      wpm: "words/min", st: "semitones", ok: "Good level", low: "Low", loud: "Very loud", fast: "Too fast", slow: "Too slow", comf: "Comfortable",
      flat: "Fairly flat", expr: "Expressive", tr: "Transcript", note: "Kinara reports signals and patterns, not verdicts. Results are guidance for practice, not a diagnosis of feelings or honesty.",
      adj: "Measured relative to your typical posture in this video, so a posture you hold the whole time won't show up as a signal.",
      s: "s", novoice: "No voice analysis was available for this video.", nospeech: "No speech was detected in this video."
    },
    ar: {
      back: "→ رجوع للنتائج", print: "احفظ كـ PDF", lang: "EN", loading: "بنجهّز تقريرك…",
      notfound: "التحليل ده مش موجود أو اتمسح.", notready: "التحليل لسه ما خلصش. ارجع للصفحة دي لما يخلص.",
      failed: "التحليل ده فشل، فمفيش تقرير.", title: "تقرير التدريب", tagline: "كوتش ذكي للغة الجسد والصوت",
      date: "التاريخ", dur: "المدة", scn: "الموقف", vis: "الكتاف ظاهرة", goal: "هدفك",
      score: "درجة التدريب", body: "الجسم", voice: "الصوت", lost: "إيه اللي نزّل درجتك", none: "مفيش حاجة نزّلت درجتك.", pts: "نقطة",
      prio: "ابدأ بدول", together: "الصوت والجسم مع بعض", moments: "نصايح حسب اللحظة", strong: "اللي كان كويس",
      said: "كنت بتقول", stat: "{p}% من الوقت · {n}× · أطولها {l} ث", tl: "الخط الزمني", sigs: "الإشارات",
      c_sig: "الإشارة", c_time: "نسبة الوقت", c_times: "عدد المرات", c_long: "أطول مرة", vo: "الصوت والكلام",
      level: "قوة الصوت", pace: "سرعة الكلام", pitch: "تنوع النغمة", share: "وقت الكلام",
      wpm: "كلمة/دقيقة", st: "نصف نغمة", ok: "مستوى كويس", low: "واطي", loud: "عالي جداً", fast: "سريع", slow: "بطيء", comf: "مريح",
      flat: "رتيب شوية", expr: "معبّر", tr: "النص المكتوب", note: "كينارا بتعرض إشارات وأنماط، مش أحكام. النتايج إرشاد للتدريب، مش تشخيص للمشاعر أو للصدق.",
      adj: "القياس نسبةً لوضعك المعتاد في الفيديو ده، فوضع ثابت طول الفيديو مش هيظهر كإشارة.",
      s: "ث", novoice: "مفيش تحليل صوت للفيديو ده.", nospeech: "مفيش كلام اتكشف في الفيديو ده."
    }
  };
  let lang = "ar", job = null;
  const qp = new URLSearchParams(location.search);
  try { lang = localStorage.getItem("lang") || "ar"; } catch (e) {}
  if (qp.get("lang") === "en" || qp.get("lang") === "ar") lang = qp.get("lang");
  const T = (k, v) => { let s = S[lang][k]; if (s == null) s = k; for (const a in (v || {})) s = s.replace("{" + a + "}", v[a]); return s; };
  const pick = (o) => (o ? (o[lang] || o.en || "") : "");
  const el = (tag, cls, text) => { const e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; };
  const num = (txt) => { const b = el("bdi", null, txt); b.dir = "ltr"; return b; };
  const mmss = (s) => { s = Math.max(0, Math.round(s)); return Math.floor(s / 60) + ":" + String(s % 60).padStart(2, "0"); };
  const voice = () => { const v = job.result.voice; return v && !v.error ? v : null; };
  const sdata = (s) => job.result.signals[s.id] || (voice() && voice().signals && voice().signals[s.id]) || null;

  function chrome() {
    const d = document.documentElement; d.lang = lang; d.dir = lang === "ar" ? "rtl" : "ltr";
    $("back").textContent = T("back"); $("print").textContent = T("print"); $("lang").textContent = T("lang");
    document.title = "Kinara · " + T("title") + (job ? " · " + job.name : "");
  }

  const CIRC = 2 * Math.PI * 52;
  function dial(score, id) {
    const NS = "http://www.w3.org/2000/svg", svg = document.createElementNS(NS, "svg");
    svg.setAttribute("viewBox", "0 0 120 120"); svg.setAttribute("class", "dial " + id);
    const mk = (cls, extra) => { const c = document.createElementNS(NS, "circle"); c.setAttribute("cx", 60); c.setAttribute("cy", 60); c.setAttribute("r", 52); c.setAttribute("class", cls); Object.entries(extra || {}).forEach(([k, v]) => c.setAttribute(k, v)); return c; };
    svg.append(mk("d-bg"), mk("d-fg", { "stroke-dasharray": (CIRC * score / 100).toFixed(1) + " " + CIRC.toFixed(1), transform: "rotate(-90 60 60)" }));
    const t = document.createElementNS(NS, "text"); t.setAttribute("x", 60); t.setAttribute("y", 70); t.setAttribute("text-anchor", "middle"); t.setAttribute("class", "d-num"); t.textContent = String(score);
    svg.append(t); return svg;
  }

  function item(label, tip, kind, stat, said, time) {
    const r = el("div", "item" + (kind ? " " + kind : "")), h = el("div", "h");
    const st = el("strong"); if (time != null) st.append(num(mmss(time)), document.createTextNode("  ·  ")); st.append(document.createTextNode(label));
    h.append(st); if (stat) h.append(el("span", "st", stat));
    r.append(h, el("p", null, tip));
    if (said) { const q = el("p", "said"); q.append(document.createTextNode(T("said") + ": “" + said + "”")); r.append(q); }
    return r;
  }

  function section(box, title) { box.append(el("h2", null, title)); }

  function header(box) {
    const r = job.result, ctx = job.context || {};
    const head = el("div", "rhead"), l = el("div"), rt = el("div");
    l.append(el("div", "brand", "Kinara"), el("div", "rtitle", T("title") + " — " + job.name));
    const m = el("div", "rmeta");
    const add = (k, v) => { const s = el("span", null, k + ": "); s.append(el("b", null, "")); s.lastChild.append(v); m.append(s); };
    let when = ""; try { when = new Date(job.created).toLocaleDateString(lang === "ar" ? "ar-EG-u-nu-latn" : "en-GB", { year: "numeric", month: "short", day: "numeric" }); } catch (e) {}
    if (when) add(T("date"), document.createTextNode(when));
    add(T("dur"), num(mmss(r.total_seconds)));
    const vis = r.total_seconds ? Math.round(100 * r.visible_seconds / r.total_seconds) : 0;
    add(T("vis"), num(vis + "%"));
    if (r.score && r.score.scenario_label) add(T("scn"), document.createTextNode(pick(r.score.scenario_label)));
    else if (window.SCENARIOS && window.SCENARIOS[ctx.scenario]) add(T("scn"), document.createTextNode(pick(window.SCENARIOS[ctx.scenario])));
    l.append(m);
    rt.append(el("div", "tag", T("tagline")));
    head.append(l, rt); box.append(head);
    if (ctx.goal) { const g = el("div", "goalbox"); g.append(el("b", null, T("goal") + ": "), document.createTextNode(ctx.goal)); box.append(g); }
  }

  function score(box) {
    const sc = job.result.score; if (!sc) return;
    section(box, T("score"));
    const wrap = el("div", "sc"), left = el("div"), right = el("div");
    left.append(dial(sc.overall, sc.label.id), el("div", "sc-label " + sc.label.id, pick(sc.label)));
    const subs = el("div", "subs");
    [["body", sc.body], ["voice", sc.voice]].forEach(([k, v]) => { if (v != null) { const d = el("div", "sub"); d.append(el("span", null, T(k)), el("strong", null, String(v))); subs.append(d); } });
    right.append(subs);
    right.append(el("h3", null, T("lost")));
    if (!sc.lost.length) right.append(el("p", "fine", T("none")));
    else { const ul = el("ul", "lost"); sc.lost.forEach((x) => { const li = el("li"), p = el("strong"); p.append(num("−" + x.points), document.createTextNode(" " + T("pts"))); li.append(el("span", null, pick(x.label)), p); ul.append(li); }); right.append(ul); }
    wrap.append(left, right); box.append(wrap);
  }

  function coach(box) {
    const c = job.result.coach; if (!c) return;
    if (c.summary.length) {
      section(box, T("prio"));
      c.summary.forEach((s, i) => {
        const it = item(pick(s.label), pick(s.tip), s.kind, T("stat", { p: Math.round(s.percent), n: s.episodes, l: Math.round(s.longest) }), "", s.start);
        it.querySelector("strong").prepend(el("span", "num", String(i + 1))); box.append(it);
      });
    }
    if (c.combined.length) { section(box, T("together")); c.combined.forEach((x) => box.append(item(pick(x.label), pick(x.tip), "voice", "", x.said, x.start))); }
    if (c.items.length) { section(box, T("moments")); c.items.forEach((x) => box.append(item(pick(x.label), pick(x.tip), x.kind, "", x.said, x.start))); }
    if (c.strengths.length) { section(box, T("strong")); const ul = el("ul", "ul"); c.strengths.forEach((x) => ul.append(el("li", null, pick(x)))); box.append(ul); }
  }

  function timeline(box) {
    const total = Math.max(job.result.total_seconds, 1);
    section(box, T("tl"));
    const tl = el("div", "tl"), ax = el("div", "ax");
    [0, .25, .5, .75, 1].forEach((f) => ax.append(el("span", null, mmss(total * f))));
    tl.append(el("span"), ax);
    let group = null;
    for (const [s, g] of SIG.map((x) => [x, "body"]).concat(voice() ? VSIG.map((x) => [x, "voice"]) : [])) {
      const d = sdata(s); if (!d) continue;
      if (voice() && g !== group) { group = g; tl.append(el("div", "gn", T(g))); }
      const track = el("div", "tr");
      for (const [a, b] of d.spans) {
        const i = el("i", s.kind === "good" ? "good" : g === "voice" ? "v" : "");
        i.style.left = (a / total * 100) + "%"; i.style.width = Math.max((b - a) / total * 100, .4) + "%"; track.append(i);
      }
      tl.append(el("span", null, pick(s)), track);
    }
    box.append(tl);
  }

  function table(box) {
    section(box, T("sigs"));
    const t = el("table"), hr = el("tr");
    ["c_sig", "c_time", "c_times", "c_long"].forEach((k) => hr.append(el("th", null, T(k))));
    const th = el("thead"); th.append(hr); t.append(th);
    const tb = el("tbody"); let group = null;
    for (const [s, g] of SIG.map((x) => [x, "body"]).concat(voice() ? VSIG.map((x) => [x, "voice"]) : [])) {
      const d = sdata(s); if (!d) continue;
      if (voice() && g !== group) { group = g; const gr = el("tr", "grp"), c = el("td", null, T(g)); c.colSpan = 4; gr.append(c); tb.append(gr); }
      const tr = el("tr"), sh = el("td", "n"), bar = el("span", "bar2" + (s.kind === "good" ? " good" : "")), fill = el("i");
      fill.style.width = Math.min(d.percent, 100) + "%"; bar.append(fill);
      sh.append(bar, num(d.percent.toFixed(1) + "%"));
      const c3 = el("td", "n"); c3.append(num(String(d.episodes))); const c4 = el("td", "n"); c4.append(num(d.longest.toFixed(1) + T("s")));
      tr.append(el("td", null, pick(s)), sh, c3, c4); tb.append(tr);
    }
    t.append(tb); box.append(t);
  }

  function vcard(label, value, unit, note) {
    const c = el("div", "vc"), v = el("div", "v"); v.append(num(value)); if (unit) v.append(el("small", null, " " + unit));
    c.append(el("div", "l", label), v, el("div", "t", note)); return c;
  }

  function voiceSec(box) {
    const raw = job.result.voice; section(box, T("vo"));
    if (!raw || raw.error) { box.append(el("p", "fine", T("novoice"))); return; }
    const o = raw.overall;
    if (o.level_note === "no_speech") { box.append(el("p", "fine", T("nospeech"))); return; }
    const g = el("div", "vg"), lv = o.level_note;
    g.append(vcard(T("level"), String(o.level_db), "dB", T(lv === "ok" ? "ok" : lv === "loud" ? "loud" : "low")));
    const w = o.wpm, wk = w == null ? null : w > 250 ? "fast" : w < 110 ? "slow" : "comf";
    g.append(vcard(T("pace"), w == null ? "—" : String(Math.round(w)), w == null ? "" : T("wpm"), wk ? T(wk) : ""));
    const pr = o.pitch_range_st;
    g.append(vcard(T("pitch"), pr == null ? "—" : String(pr), pr == null ? "" : T("st"), pr == null ? "" : T(pr < 2.5 ? "flat" : "expr")));
    g.append(vcard(T("share"), Math.round(o.speech_ratio * 100) + "%", "", mmss(o.speech_seconds)));
    box.append(g);
    const t = raw.transcript;
    if (t && t.segments && t.segments.length) {
      box.append(el("h3", null, T("tr")));
      const ol = el("ol", "trn");
      t.segments.forEach((x) => { const li = el("li"); li.append(el("time", null, mmss(x.start)), el("span", null, x.text)); ol.append(li); });
      box.append(ol);
    }
  }

  function build() {
    const box = $("rep"); box.replaceChildren();
    header(box); score(box); coach(box); timeline(box); table(box); voiceSec(box);
    if (Object.keys(job.result.baseline_adjust || {}).length) box.append(el("p", "fine", T("adj")));
    box.append(el("p", "fine", T("note")));
    const f = el("div", "rfoot"); f.append(el("span", null, "Kinara · " + T("tagline")), el("span", null, new Date().toLocaleDateString("en-GB"))); box.append(f);
  }

  function show() {
    chrome();
    const st = $("state"), rep = $("rep");
    if (!job) { st.textContent = T("loading"); rep.hidden = true; return; }
    if (job.status === "error") { st.textContent = T("failed"); rep.hidden = true; return; }
    if (job.status !== "done") { st.textContent = T("notready"); rep.hidden = true; return; }
    st.textContent = ""; rep.hidden = false; build();
  }

  $("print").addEventListener("click", () => window.print());
  $("lang").addEventListener("click", () => { lang = lang === "ar" ? "en" : "ar"; try { localStorage.setItem("lang", lang); } catch (e) {} show(); });
  show();
  fetch("/api/jobs/" + JOB).then(async (r) => {
    if (r.status === 404) { $("state").textContent = T("notfound"); return; }
    job = await r.json(); show();
    if (job.status === "done" && qp.get("print") === "1") setTimeout(() => window.print(), 600);
  }).catch(() => { $("state").textContent = T("notfound"); });
})();
