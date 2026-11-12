import test from "node:test";
import assert from "node:assert/strict";
import { textToHtml, escapeHtml } from "../src/lib/markdown.js";
import { buildProfile, validateProfile, normalizeStoredProfile, EMPTY_PROFILE } from "../src/lib/profile.js";
import { trimHistory } from "../src/lib/api.js";
import { cleanMessages } from "../src/lib/messages.js";
import { safeUrl } from "../src/lib/url.js";
import { APP_NAME, APP_TAGLINE } from "../src/lib/brand.js";

test("escapeHtml neutralises HTML", () => {
  assert.equal(escapeHtml('<img src=x onerror="a()">'), "&lt;img src=x onerror=&quot;a()&quot;&gt;");
});

test("textToHtml lets no dangerous tags or attributes through", () => {
  const html = textToHtml('<script>alert(1)</script> [click](https://a.es" onmouseover="x)');
  assert.ok(!html.includes("<script"));
  assert.ok(!/onmouseover="/.test(html));
});

test("textToHtml does not link javascript:", () => {
  assert.ok(!textToHtml("[x](javascript:alert(1))").includes("<a "));
});

test("textToHtml renders bold, lists and links", () => {
  const html = textToHtml("**Resumen**\n- uno\n- dos\n\n1. paso\nMás en https://www.fega.gob.es/ ya.");
  assert.ok(html.includes("<strong>Resumen</strong>"));
  assert.ok(html.includes("<ul><li>uno</li><li>dos</li></ul>"));
  assert.ok(html.includes("<ol><li>paso"));
  assert.ok(html.includes('href="https://www.fega.gob.es/"'));
  assert.ok(html.includes('rel="noopener noreferrer"'));
});

test("buildProfile includes only filled fields and converts types", () => {
  const p = buildProfile({
    region: "Aragón", province: " ", municipality: "Alcañiz", livestock_type: ["sheep"], head_count: "300", production_system: "",
    holder_age: "29", pasture_hectares: "12,5", rega_registered: "yes", active_farmer: "", goal: "income",
  });
  assert.deepEqual(p, { region: "Aragón", municipality: "Alcañiz", livestock_type: ["sheep"], head_count: 300, holder_age: 29,
    pasture_hectares: 12.5, rega_registered: true, goal: "income" });
});

test("buildProfile supports crop-only and mixed agricultural holdings", () => {
  assert.deepEqual(buildProfile({ farm_activities: ["agriculture"], crop_types: "cereal, olives",
    agricultural_area_hectares: "18,5", irrigated_hectares: "2" }), {
    farm_activities: ["agriculture"], crop_types: ["cereal", "olives"], agricultural_area_hectares: 18.5,
    irrigated_hectares: 2,
  });
});

test("buildProfile tells 'no' apart from 'I do not know'", () => {
  assert.equal(buildProfile({ active_farmer: "no" }).active_farmer, false);
  assert.ok(!("active_farmer" in buildProfile({ active_farmer: "" })));
});

test("validateProfile detects out-of-range values", () => {
  const e = validateProfile({ holder_age: "12", years_active: "-1", head_count: "3,5", pasture_hectares: "abc" });
  assert.deepEqual(Object.keys(e).sort(), ["head_count", "holder_age", "pasture_hectares", "years_active"]);
  assert.deepEqual(validateProfile({ holder_age: "29", pasture_hectares: "10,5" }), {});
});

test("normalizeStoredProfile tolerates corrupt data and fills in the fields", () => {
  assert.deepEqual(normalizeStoredProfile(null), EMPTY_PROFILE);
  const p = normalizeStoredProfile({ region: "Aragón", holder_age: 29, livestock_type: "sheep", extra: "x" });
  assert.equal(p.region, "Aragón");
  assert.equal(p.holder_age, "29");
  assert.deepEqual(p.livestock_type, []);
  assert.ok(!("extra" in p));
});

test("trimHistory always starts with a user message", () => {
  const m = [{ role: "user", content: "a" }, { role: "assistant", content: "b" }, { role: "user", content: "c" }];
  assert.deepEqual(trimHistory(m, 2).map((x) => x.content), ["c"]);
  assert.equal(trimHistory(m, 20).length, 3);
});

test("cleanMessages drops invalid entries", () => {
  assert.deepEqual(cleanMessages("x"), []);
  const ok = { role: "user", content: "hola" };
  assert.deepEqual(cleanMessages([ok, { role: "system", content: "x" }, { role: "user" }, null, { role: "user", content: " " }]), [ok]);
});

test("safeUrl only accepts http(s)", () => {
  assert.equal(safeUrl("https://www.fega.gob.es/a"), "https://www.fega.gob.es/a");
  assert.equal(safeUrl("javascript:alert(1)"), null);
  assert.equal(safeUrl("not a url"), null);
});

test("the brand is defined", () => {
  assert.ok(APP_NAME.trim().length > 0 && APP_TAGLINE.trim().length > 0);
});

test("textToHtml links <https://...> autolinks without the closing bracket", () => {
  const html = textToHtml("Fuente: <https://www.fega.gob.es/es/ayuda>.");
  assert.ok(html.includes('href="https://www.fega.gob.es/es/ayuda"'));
  assert.ok(!html.includes("&gt;\""));
  assert.ok(!html.includes("%3E"));
});
