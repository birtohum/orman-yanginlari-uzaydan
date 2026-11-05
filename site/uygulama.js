"use strict";
const AYLAR = ["Oca", "Şub", "Mar", "Nis", "May", "Haz", "Tem", "Ağu", "Eyl", "Eki", "Kas", "Ara"];
const AY_TAM = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"];
const fmt = n => Math.round(n).toLocaleString("tr-TR");
const tarihYaz = t => { const [y, a, g] = t.split("-"); return `${+g} ${AY_TAM[+a - 1]} ${y}`; };
const renk = ad => getComputedStyle(document.documentElement).getPropertyValue(ad).trim();
const $ = s => document.querySelector(s);
const json = u => fetch(u).then(r => { if (!r.ok) throw new Error(u); return r.json(); });

let OZET, SINIR, ILLER, OLAYLAR = [];
const haritaOnbellek = {};

function eksikYil(y) {
  const a = OZET.yil_araligi[y];
  if (!a) return true;
  return a[0] > `${y}-02-01` || a[1] < `${y}-12-01`;
}

function kapsamYaz(y) {
  const a = OZET.yil_araligi[y];
  return a ? `${tarihYaz(a[0])} – ${tarihYaz(a[1])}` : "";
}

/* ---------- kancalar ---------- */
function kancalar() {
  const V = OZET.yillik.V;
  const yillar = Object.keys(V).filter(y => !eksikYil(y));
  const orman = y => (V[y] && V[y].orman) || 0;
  const enCok = yillar.reduce((a, b) => (orman(b) > orman(a) ? b : a));
  const digerleri = yillar.filter(y => y !== enCok);
  const ort = digerleri.reduce((s, y) => s + orman(y), 0) / digerleri.length;
  let top = 0, orm = 0;
  for (const y of yillar) { top += V[y].toplam; orm += orman(y); }
  const k = [];
  k.push(`<div class="kanca"><b>${fmt(orman(enCok))}</b><span>${enCok} yılında uydunun orman ve makilikte gördüğü yangın noktası. Diğer yılların ortalamasının ${(orman(enCok) / ort).toLocaleString("tr-TR", { maximumFractionDigits: 1 })} katı.</span></div>`);
  k.push(`<div class="kanca"><b>%${Math.round(orm / top * 100)}</b><span>Uydunun gördüğü noktaların yalnız bu kadarı orman ve makilikte. Çoğu tarlada yakılan anız.</span></div>`);
  if (OLAYLAR.length) {
    const b = OLAYLAR[0];
    k.push(`<div class="kanca"><b>${fmt(b.yanik_ha)} ha</b><span>${b.ilce} (${b.il}) yangınında Sentinel-2 ile ölçtüğümüz yanmış alan, ${b.bas.slice(0, 4)}. Yaklaşık ${fmt(b.yanik_ha / 0.714)} futbol sahası.</span></div>`);
  }
  $("#kancalar").innerHTML = k.join("");
}

/* ---------- harita ---------- */
const BATI = 25.6, DOGU = 44.9, GUNEY = 35.8, KUZEY = 42.2, KX = Math.cos(39 * Math.PI / 180);
let seciliAy = 0;

async function haritaCiz() {
  const y = $("#yil").value;
  const veri = haritaOnbellek[y] || (haritaOnbellek[y] = await json(`veri/harita/${y}.json`));
  const yalnizOrman = $("#yalniz-orman").checked;
  const cv = $("#harita");
  const W = cv.parentElement.clientWidth - 16;
  const olcek = W / ((DOGU - BATI) * KX);
  const H = Math.round((KUZEY - GUNEY) * olcek);
  const dpr = window.devicePixelRatio || 1;
  cv.width = W * dpr; cv.height = H * dpr; cv.style.height = H + "px";
  const c = cv.getContext("2d");
  c.scale(dpr, dpr);
  const px = lon => (lon - BATI) * KX * olcek, py = lat => (KUZEY - lat) * olcek;
  c.fillStyle = renk("--kara"); c.strokeStyle = renk("--sinir"); c.lineWidth = 0.6;
  for (const il of SINIR) for (const h of il.h) {
    c.beginPath();
    h.forEach(([x, yy], i) => (i ? c.lineTo(px(x), py(yy)) : c.moveTo(px(x), py(yy))));
    c.closePath(); c.fill(); c.stroke();
  }
  const r = Math.max(1.1, W / 650);
  const renkler = [renk("--vurgu"), renk("--tarim"), renk("--diger")];
  let say = [0, 0, 0];
  for (const s of [2, 1, 0]) {
    if (yalnizOrman && s !== 0) continue;
    c.fillStyle = renkler[s]; c.globalAlpha = s === 0 ? 0.9 : 0.55;
    const rr = s === 0 ? r * 1.25 : r;
    for (const [x, yy, ay, sn, n] of veri.n) {
      if (sn !== s || (seciliAy && ay !== seciliAy)) continue;
      say[s] += n;
      c.fillRect(px(x / 100) - rr, py(yy / 100) - rr, rr * 2, rr * 2);
    }
  }
  c.globalAlpha = 1;
  const uydu = veri.kaynak === "V" ? "VIIRS (375 m)" : "MODIS (1 km; VIIRS 2012'de başladı)";
  const donem = seciliAy ? `${AY_TAM[seciliAy - 1]} ${y}` : y;
  let not = `${donem}: ${fmt(say[0])} nokta orman ve makilikte` + (yalnizOrman ? "" : `, ${fmt(say[1])} tarlada, ${fmt(say[2])} başka yerde`) + `. Uydu: ${uydu}.`;
  if (eksikYil(y)) not += ` Bu yılın verisi eksik: yalnız ${kapsamYaz(y)} arası.`;
  $("#harita-not").textContent = not;
}

function haritaKur() {
  const sel = $("#yil");
  const yillar = OZET.harita_yillari.slice().reverse();
  sel.innerHTML = yillar.map(y => `<option value="${y}">${y}${eksikYil(y) ? " (eksik)" : ""}</option>`).join("");
  const enSonTam = yillar.find(y => !eksikYil(y));
  sel.value = OZET.yil_araligi["2021"] ? "2021" : enSonTam;
  const ay = $("#aylar");
  ay.innerHTML = `<button data-ay="0" class="secili">Tüm yıl</button>` + AYLAR.map((a, i) => `<button data-ay="${i + 1}">${a}</button>`).join("");
  ay.addEventListener("click", e => {
    const b = e.target.closest("button"); if (!b) return;
    seciliAy = +b.dataset.ay;
    ay.querySelectorAll("button").forEach(x => x.classList.toggle("secili", x === b));
    haritaCiz();
  });
  sel.addEventListener("change", haritaCiz);
  $("#yalniz-orman").addEventListener("change", haritaCiz);
  let t; window.addEventListener("resize", () => { clearTimeout(t); t = setTimeout(haritaCiz, 150); });
  haritaCiz();
}

/* ---------- yıllık grafik ---------- */
function yillikCiz(k) {
  const d = OZET.yillik[k];
  const yillar = Object.keys(d);
  const deg = yillar.map(y => d[y].orman || 0);
  const W = 720, H = 260, sol = 44, alt = 24, ust = 18;
  const maks = Math.max(...deg) * 1.08;
  const bw = (W - sol - 6) / yillar.length;
  const yk = v => H - alt - (v / maks) * (H - alt - ust);
  const adim = Math.pow(10, Math.floor(Math.log10(maks / 2)));
  const cizgi = [];
  for (let v = 0; v <= maks; v += adim * (maks / adim > 6 ? 2 : 1)) {
    cizgi.push(`<line x1="${sol}" x2="${W}" y1="${yk(v)}" y2="${yk(v)}" stroke="var(--cizgi)"/><text x="${sol - 6}" y="${yk(v) + 4}" text-anchor="end">${fmt(v)}</text>`);
  }
  const cub = yillar.map((y, i) => {
    const x = sol + i * bw + 2, h = H - alt - yk(deg[i]);
    const eksik = eksikYil(y);
    const g = Math.max(bw - 4, 2);
    const yaz = (i % (bw < 26 ? 2 : 1) === 0 || i === yillar.length - 1) ? `<text x="${x + g / 2}" y="${H - 8}" text-anchor="middle">${bw < 34 ? "’" + y.slice(2) : y}</text>` : "";
    const ust_ = deg[i] === Math.max(...deg) ? `<text class="etiket" x="${x + g / 2}" y="${yk(deg[i]) - 5}" text-anchor="middle">${fmt(deg[i])}</text>` : "";
    return `<rect x="${x}" y="${yk(deg[i])}" width="${g}" height="${Math.max(h, 0)}" rx="2" fill="var(--vurgu)" opacity="${eksik ? 0.3 : 0.9}"><title>${y}: ${fmt(deg[i])} nokta${eksik ? " (eksik yıl)" : ""}</title></rect>${yaz}${ust_}`;
  });
  $("#yillik").innerHTML = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Yıllara göre orman ve makilikteki yangın noktaları">${cizgi.join("")}${cub.join("")}</svg>`;
  const eks = yillar.filter(eksikYil);
  $("#yillik-not").textContent = (k === "V" ? "VIIRS 375 m'lik pikselle MODIS'ten daha küçük yangınları da görür; bu yüzden iki uydunun sayıları birbirine eklenmez." : "MODIS 2001'den beri aynı biçimde ölçtüğü için uzun dönem karşılaştırmasına uygundur; küçük yangınları kaçırır.")
    + (eks.length ? ` Soluk çubuk: eksik yıl (${eks.map(y => `${y}: ${kapsamYaz(y)}`).join("; ")}).` : "");
}

function yillikKur() {
  const s = document.querySelector(".sekme");
  s.addEventListener("click", e => {
    const b = e.target.closest("button"); if (!b) return;
    s.querySelectorAll("button").forEach(x => x.classList.toggle("secili", x === b));
    yillikCiz(b.dataset.k);
  });
  yillikCiz("V");
}

/* ---------- aylık grafik ---------- */
function aylikCiz() {
  const a = OZET.aylik_viirs;
  const W = 720, H = 240, sol = 50, alt = 24, ust = 12;
  const top = AYLAR.map((_, i) => a.orman[i] + a.tarim[i] + a.diger[i]);
  const maks = Math.max(...top) * 1.05;
  const bw = (W - sol) / 12;
  const yk = v => (v / maks) * (H - alt - ust);
  let s = "";
  for (let v = 0; v <= maks; v += 20000) s += `<line x1="${sol}" x2="${W}" y1="${H - alt - yk(v)}" y2="${H - alt - yk(v)}" stroke="var(--cizgi)"/><text x="${sol - 6}" y="${H - alt - yk(v) + 4}" text-anchor="end">${fmt(v)}</text>`;
  AYLAR.forEach((ad, i) => {
    const x = sol + i * bw + 3, g = bw - 6;
    let taban = H - alt;
    for (const [k, r] of [["orman", "var(--vurgu)"], ["tarim", "var(--tarim)"], ["diger", "var(--diger)"]]) {
      const h = yk(a[k][i]);
      s += `<rect x="${x}" y="${taban - h}" width="${g}" height="${h}" fill="${r}"><title>${AY_TAM[i]}: ${fmt(a[k][i])} (${k === "orman" ? "orman ve makilik" : k === "tarim" ? "tarla" : "diğer"})</title></rect>`;
      taban -= h;
    }
    s += `<text x="${x + g / 2}" y="${H - 8}" text-anchor="middle">${ad}</text>`;
  });
  $("#aylik").innerHTML = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Aylara göre yangın noktaları">${s}</svg>
  <p class="not" style="margin:4px 6px 6px"><span class="renk orman"></span> orman ve makilik &nbsp; <span class="renk tarim"></span> tarla &nbsp; <span class="renk diger"></span> diğer. Ormandaki noktalar Temmuz–Ağustos'ta, tarladakiler Haziran ve Eylül–Ekim'de yoğunlaşır.</p>`;
}

/* ---------- iller ---------- */
let ilSira = 1;
function illerCiz() {
  const y = $("#il-yil").value;
  const ara = $("#il-ara").value.trim().toLocaleLowerCase("tr");
  const satir = [];
  for (const [il, d] of Object.entries(ILLER)) {
    let t = 0, o = 0;
    if (y === "hepsi") {
      for (const [yy, v] of Object.entries(d.V || {})) { t += v[0]; o += v[1]; }
    } else {
      const k = +y >= 2012 ? "V" : "M";
      const v = (d[k] || {})[y]; if (v) { t = v[0]; o = v[1]; }
    }
    satir.push([il, t, o]);
  }
  satir.sort((a, b) => (ilSira === 1 ? b[2] - a[2] : b[1] - a[1]) || a[0].localeCompare(b[0], "tr"));
  const maks = Math.max(1, ...satir.map(s => s[2]));
  const sira = new Map(satir.map((s, i) => [s[0], i + 1]));
  $("#iller tbody").innerHTML = satir
    .filter(s => !ara || s[0].toLocaleLowerCase("tr").includes(ara))
    .map(s => `<tr><td>${sira.get(s[0])}. ${s[0]}</td><td class="sayi"><span class="cubuk" style="width:${Math.round(s[2] / maks * 60)}px"></span>${fmt(s[2])}</td><td class="sayi">${fmt(s[1])}</td></tr>`).join("");
  const k = y === "hepsi" ? `VIIRS, ${kapsamYaz(Object.keys(OZET.yillik.V)[0])} – ${tarihYaz(OZET.son_tespit)}` : (+y >= 2012 ? "VIIRS (375 m)" : "MODIS (1 km)");
  $("#il-not").textContent = `Sayılar uydu noktasıdır, yangın sayısı değildir. Kaynak: ${k}.${y !== "hepsi" && eksikYil(y) ? " Bu yılın verisi eksik." : ""}`;
}
function illerKur() {
  const s = $("#il-yil");
  const yillar = Object.keys(OZET.yillik.M).concat(Object.keys(OZET.yillik.V)).filter((v, i, a) => a.indexOf(v) === i).sort().reverse();
  s.innerHTML = `<option value="hepsi">Tüm yıllar (2012'den)</option>` + yillar.map(y => `<option value="${y}">${y}${eksikYil(y) ? " (eksik)" : ""}</option>`).join("");
  s.addEventListener("change", illerCiz);
  $("#il-ara").addEventListener("input", illerCiz);
  document.querySelectorAll("#iller th.sayi").forEach(th => th.addEventListener("click", () => { ilSira = +th.dataset.s; illerCiz(); }));
  illerCiz();
}

/* ---------- büyük yangınlar ---------- */
function egri(o) {
  const e = o.yesillenme || [];
  if (e.length < 3) return "";
  const W = 360, H = 150, sol = 30, alt = 20, ust = 10, sag = 8;
  const t = e.map(r => new Date(r.tarih).getTime());
  const t0 = Math.min(...t), t1 = Math.max(...t);
  const xk = v => sol + (v - t0) / (t1 - t0 || 1) * (W - sol - sag);
  const yk = v => H - alt - (v / 0.9) * (H - alt - ust);
  let s = "";
  for (const v of [0, 0.3, 0.6, 0.9]) s += `<line x1="${sol}" x2="${W - sag}" y1="${yk(v)}" y2="${yk(v)}" stroke="var(--cizgi)"/><text x="${sol - 4}" y="${yk(v) + 3}" text-anchor="end">${v.toLocaleString("tr-TR")}</text>`;
  const cizgi = (k, r) => `<polyline fill="none" stroke="${r}" stroke-width="2" points="${e.map((p, i) => `${xk(t[i])},${yk(p[k])}`).join(" ")}"/>` +
    e.map((p, i) => `<circle cx="${xk(t[i])}" cy="${yk(p[k])}" r="3" fill="${r}"><title>${tarihYaz(p.tarih)}: ${p[k].toLocaleString("tr-TR")}</title></circle>`).join("");
  s += cizgi("cevre", "var(--diger)") + cizgi("yanik", "var(--vurgu)");
  const yillar = [...new Set(e.map(p => p.tarih.slice(0, 4)))];
  for (const y of yillar) { const tt = new Date(`${y}-07-01`).getTime(); if (tt >= t0 && tt <= t1) s += `<text x="${xk(tt)}" y="${H - 5}" text-anchor="middle">’${y.slice(2)}</text>`; }
  const once = e.find(p => p.tarih < o.bas), son = e[e.length - 1];
  let ozet = "";
  if (once && son && son.tarih > o.son) {
    const oran = (son.yanik / son.cevre) / (once.yanik / once.cevre);
    ozet = `${son.tarih.slice(0, 4)} itibarıyla yanan alanın yeşilliği, çevresine göre yangın öncesinin yaklaşık %${Math.round(oran * 100)}'i.`;
  }
  return `<p class="egri-baslik">Yeşeriyor mu?</p>
  <svg class="egri" viewBox="0 0 ${W} ${H}" role="img" aria-label="Yıllara göre yeşillik">${s}</svg>
  <p class="egri-not"><span class="renk orman"></span> yanan alan &nbsp; <span class="renk diger"></span> yanmamış çevre. Yeşillik ölçüsü NDVI, her yıl aynı mevsimde. ${ozet}</p>`;
}

function olaylarCiz() {
  const k = $("#olaylar");
  if (!OLAYLAR.length) { k.innerHTML = `<p class="not">Ölçümler hazırlanıyor.</p>`; return; }
  k.innerHTML = OLAYLAR.map((o, i) => {
    const e = o.esik_ha;
    return `<article class="olay" data-i="${i}">
      <div class="olay-bas"><div><h3>${o.ilce}, ${o.il}</h3><div class="tarih">${tarihYaz(o.bas)}${o.son !== o.bas ? " – " + tarihYaz(o.son) : ""}</div></div>
      <div class="buyuk">${fmt(o.yanik_ha)} ha <small>yanmış alan</small></div></div>
      <div class="olay-govde">
        <div>
          <div class="olay-sekme" role="group" aria-label="Görüntü">
            <button data-g="once">Önce · ${tarihYaz(o.once_tarih)}</button>
            <button data-g="sonra" class="secili">Sonra · ${tarihYaz(o.sonra_tarih)}</button>
            <button data-g="yanik">Yanan alan</button>
          </div>
          <div class="gorsel"><img loading="lazy" width="${o.gorsel_boyut[0]}" height="${o.gorsel_boyut[1]}" src="gorsel/${o.id}_sonra.jpg" alt="${o.ilce} yangını sonrası uydu görüntüsü">
          <img class="katman" loading="lazy" src="gorsel/${o.id}_yanik.png" alt="" hidden></div>
        </div>
        <div>
          <dl>
            <dt>Yaklaşık</dt><dd>${fmt(o.yanik_ha / 0.714)} futbol sahası</dd>
            <dt>Eşik</dt><dd>dNBR ≥ 0,27</dd>
            <dt>Eşik değişirse</dt><dd>${fmt(e.genis)} ha (≥ 0,10) · ${fmt(e.orta_yuksek)} ha (≥ 0,44)</dd>
            <dt>Görülemeyen</dt><dd>arama alanının %${Math.round(o.gorunmez_oran * 100)}'i (bulut vb.)</dd>
            <dt>Uydu noktası</dt><dd>${fmt(o.tespit)} VIIRS tespiti</dd>
          </dl>
          ${egri(o)}
        </div>
      </div>
    </article>`;
  }).join("");
  k.addEventListener("click", ev => {
    const b = ev.target.closest(".olay-sekme button"); if (!b) return;
    const art = b.closest(".olay"); const o = OLAYLAR[+art.dataset.i];
    art.querySelectorAll(".olay-sekme button").forEach(x => x.classList.toggle("secili", x === b));
    const [img, kat] = art.querySelectorAll(".gorsel img");
    img.src = `gorsel/${o.id}_${b.dataset.g === "once" ? "once" : "sonra"}.jpg`;
    kat.hidden = b.dataset.g !== "yanik";
  });
}

/* ---------- başlat ---------- */
(async function () {
  [OZET, SINIR, ILLER] = await Promise.all([json("veri/ozet.json"), json("veri/sinirlar.json"), json("veri/iller.json")]);
  try { OLAYLAR = await json("veri/olaylar.json"); } catch (e) { OLAYLAR = []; }
  kancalar(); haritaKur(); yillikKur(); aylikCiz(); illerKur(); olaylarCiz();
  $("#guncelleme").textContent = `Son güncelleme: ${tarihYaz(OZET.guncelleme)}. En son uydu noktası: ${tarihYaz(OZET.son_tespit)}.`;
  matchMedia("(prefers-color-scheme: dark)").addEventListener("change", haritaCiz);
})();
