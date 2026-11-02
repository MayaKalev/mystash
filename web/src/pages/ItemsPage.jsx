import { useEffect, useState } from "react";
import { Link } from "react-router";
import { api } from "../api.js";
import {
  CONTENT_TYPES,
  STATUSES,
  StatusBadge,
  TagList,
  isWorking,
  siteName,
} from "../components/ItemInfo.jsx";

const NO_FILTERS = { content_type: "", tag: "", status: "" };
const REFRESH_MS = 2000;

export default function ItemsPage() {
  const [items, setItems] = useState(null); // null until the first load finishes
  const [tags, setTags] = useState([]);
  const [filters, setFilters] = useState(NO_FILTERS);
  const [loadError, setLoadError] = useState("");
  // Changing this number makes the list load again, for example after saving a link.
  const [reloadKey, setReloadKey] = useState(0);

  // Load the list whenever the filters change. While any item is still being processed,
  // load it again every 2 seconds, so its title and tags appear by themselves.
  useEffect(() => {
    let timer;
    let stopped = false; // Set when the page closes or the filters change.

    async function load() {
      try {
        const chosen = Object.fromEntries(Object.entries(filters).filter(([, value]) => value));
        const [newItems, newTags] = await Promise.all([api.listItems(chosen), api.listTags()]);
        if (stopped) return;
        setItems(newItems);
        setTags(newTags);
        setLoadError("");
        if (newItems.some(isWorking)) timer = setTimeout(load, REFRESH_MS);
      } catch (err) {
        if (!stopped) setLoadError(err.message);
      }
    }

    load();
    return () => {
      stopped = true;
      clearTimeout(timer);
    };
  }, [filters, reloadKey]);

  function handleSaved() {
    // Show everything, so the new link is visible even if a filter would hide it.
    setFilters(NO_FILTERS);
    setReloadKey((key) => key + 1);
  }

  function setFilter(name, value) {
    setFilters({ ...filters, [name]: value });
  }

  const filtered = filters.content_type || filters.tag || filters.status;

  return (
    <>
      <SaveLinkForm onSaved={handleSaved} />

      <div className="filters">
        <select
          value={filters.content_type}
          onChange={(e) => setFilter("content_type", e.target.value)}
          aria-label="Filter by type"
        >
          <option value="">All types</option>
          {CONTENT_TYPES.map((type) => (
            <option key={type} value={type}>
              {type}
            </option>
          ))}
        </select>
        <select
          value={filters.tag}
          onChange={(e) => setFilter("tag", e.target.value)}
          aria-label="Filter by tag"
        >
          <option value="">All tags</option>
          {tags.map((tag) => (
            <option key={tag.name} value={tag.name}>
              {tag.name}
            </option>
          ))}
        </select>
        <select
          value={filters.status}
          onChange={(e) => setFilter("status", e.target.value)}
          aria-label="Filter by status"
        >
          <option value="">Any status</option>
          {STATUSES.map((status) => (
            <option key={status} value={status}>
              {status}
            </option>
          ))}
        </select>
        {filtered && (
          <button className="link-button" onClick={() => setFilters(NO_FILTERS)}>
            Clear filters
          </button>
        )}
      </div>

      {loadError && <p className="error">{loadError}</p>}
      {items === null && !loadError && <p className="hint">Loading…</p>}
      {items && items.length === 0 && (
        <p className="empty">
          {filtered ? "No links match these filters." : "Nothing saved yet. Paste a link above."}
        </p>
      )}

      <ul className="items">
        {items?.map((item) => (
          <li key={item.id}>
            <ItemCard item={item} />
          </li>
        ))}
      </ul>
    </>
  );
}

function SaveLinkForm({ onSaved }) {
  const [url, setUrl] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function handleSubmit(event) {
    event.preventDefault();
    setError("");
    setBusy(true);
    try {
      await api.saveItem(url.trim());
      setUrl("");
      onSaved();
    } catch (err) {
      setError(err.message);
    }
    setBusy(false);
  }

  return (
    <form onSubmit={handleSubmit} className="card save-form">
      <div className="row">
        <input
          type="url"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          placeholder="Paste a link, e.g. https://example.com/article"
          aria-label="Link to save"
          required
        />
        <button type="submit" disabled={busy}>
          Save
        </button>
      </div>
      {error && <p className="error">{error}</p>}
    </form>
  );
}

function ItemCard({ item }) {
  return (
    <Link to={`/items/${item.id}`} className="card item-card">
      <div className="item-top">
        <span className="site">{siteName(item.url)}</span>
        {item.content_type && <span className="type">{item.content_type}</span>}
        {item.status !== "done" && <StatusBadge status={item.status} />}
      </div>
      <h2>{item.title || item.url}</h2>
      {item.summary && <p className="summary">{item.summary}</p>}
      {item.status === "failed" && <p className="error">{item.error_message}</p>}
      <TagList tags={item.tags} />
    </Link>
  );
}
