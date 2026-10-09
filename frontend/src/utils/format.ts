/**
 * Parse timestamps returned by the API.
 *
 * SQLite stores CURRENT_TIMESTAMP in UTC but drops the timezone marker when
 * it is read back. Treat timezone-less ISO timestamps as UTC so browsers do
 * not interpret them as local time.
 */
export function parseApiDate(value: string) {
  const hasTimezone = /(?:[zZ]|[+-]\d{2}:?\d{2})$/.test(value);
  return new Date(hasTimezone ? value : `${value}Z`);
}

export function formatRelativeDate(value: string) {
  const date = parseApiDate(value);
  const now = new Date();
  const diff = now.getTime() - date.getTime();
  const minutes = Math.floor(diff / 60000);
  const hours = Math.floor(diff / 3600000);
  const days = Math.floor(diff / 86400000);

  if (minutes < 1) return "刚刚";
  if (minutes < 60) return `${minutes} 分钟前`;
  if (hours < 24) return `${hours} 小时前`;
  if (days === 1) return "昨天";
  if (days < 7) return `${days} 天前`;
  return new Intl.DateTimeFormat("zh-CN", {
    month: "short",
    day: "numeric",
  }).format(date);
}

export function formatFullDate(value: string) {
  return new Intl.DateTimeFormat("zh-CN", {
    year: "numeric",
    month: "long",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(parseApiDate(value));
}

export function truncate(value: string, length = 120) {
  if (value.length <= length) return value;
  return `${value.slice(0, length).trim()}…`;
}

export const sourceMeta: Record<
  string,
  { label: string; className: string }
> = {
  text: { label: "文本", className: "source-text" },
  url: { label: "链接", className: "source-url" },
  image: { label: "图片", className: "source-image" },
};
