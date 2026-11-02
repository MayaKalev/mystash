// Small pieces shown on both the list and the detail page.

export const CONTENT_TYPES = [
  "article",
  "video",
  "repo",
  "tool",
  "shop",
  "restaurant",
  "course",
  "other",
];

export const STATUSES = ["pending", "processing", "done", "failed"];

// True while the worker hasn't finished with the item yet.
export function isWorking(item) {
  return item.status === "pending" || item.status === "processing";
}

export function StatusBadge({ status }) {
  const labels = {
    pending: "Waiting…",
    processing: "Reading the page…",
    done: "Done",
    failed: "Failed",
  };
  return <span className={`badge badge-${status}`}>{labels[status] || status}</span>;
}

export function TagList({ tags }) {
  if (tags.length === 0) return null;
  return (
    <ul className="tags">
      {tags.map((tag) => (
        <li key={tag.name} className="tag">
          {tag.name}
        </li>
      ))}
    </ul>
  );
}

// "https://www.example.com/a/b" → "example.com"
export function siteName(url) {
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return url;
  }
}
