const THEME_KEY = "csv-sales-analyzer.theme";

export function readTheme() {
  try { return localStorage.getItem(THEME_KEY) === "dark" ? "dark" : "light"; }
  catch { return "light"; }
}

export function saveTheme(theme) {
  try { localStorage.setItem(THEME_KEY, theme); } catch { /* Theme still works for this tab. */ }
}
