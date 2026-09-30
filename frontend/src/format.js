export const integer = (value) => new Intl.NumberFormat("en-IN").format(value ?? 0);
export const rupees = (value) => new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 2 }).format(Number(value ?? 0));
export const dateTime = (value) => value ? new Intl.DateTimeFormat("en-IN", { dateStyle: "medium", timeStyle: "short" }).format(new Date(value)) : "Not yet";
export const timeOnly = (value) => value ? new Intl.DateTimeFormat("en-IN", { timeStyle: "short" }).format(new Date(value)) : "Pending";
export const fileSize = (bytes) => bytes == null ? "Not yet" : bytes < 1024 * 1024 ? `${(bytes / 1024).toFixed(1)} KB` : `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
export const duration = (start, end) => start && end ? `${Math.max(0, Math.round((new Date(end) - new Date(start)) / 1000))} seconds` : "Not yet";

export function topProducts(products, metric) {
  const sorted = [...products].sort((a, b) => Number(b[metric]) - Number(a[metric]) || a.product.localeCompare(b.product));
  if (sorted.length <= 10) return sorted.map((item) => ({ ...item, value: Number(item[metric]) }));
  const top = sorted.slice(0, 9).map((item) => ({ ...item, value: Number(item[metric]) }));
  top.push({ product: "Other", value: sorted.slice(9).reduce((sum, item) => sum + Number(item[metric]), 0) });
  return top;
}

export function filterProducts(products, query) {
  const term = query.trim().toLocaleLowerCase();
  return products.filter((item) => item.product.toLocaleLowerCase().includes(term));
}
