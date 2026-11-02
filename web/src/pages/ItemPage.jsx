import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router";
import { api } from "../api.js";
import { StatusBadge, isWorking, siteName } from "../components/ItemInfo.jsx";

const REFRESH_MS = 2000;

export default function ItemPage() {
  const { id } = useParams(); // The number in /items/7
  const navigate = useNavigate();
  const [item, setItem] = useState(null);
  const [error, setError] = useState("");

  // Load the item, and keep loading it every 2 seconds until the worker has finished.
  useEffect(() => {
    let timer;
    let stopped = false;

    async function load() {
      try {
        const newItem = await api.getItem(id);
        if (stopped) return;
        setItem(newItem);
        if (isWorking(newItem)) timer = setTimeout(load, REFRESH_MS);
      } catch (err) {
        if (!stopped) setError(err.message);
      }
    }

    load();
    return () => {
      stopped = true;
      clearTimeout(timer);
    };
  }, [id]);

  async function handleDelete() {
    if (!window.confirm("Delete this link?")) return;
    try {
      await api.deleteItem(id);
      navigate("/");
    } catch (err) {
      setError(err.message);
    }
  }

  if (error && !item) {
    return (
      <div className="card">
        <p className="error">{error}</p>
        <Link to="/">← Back to my links</Link>
      </div>
    );
  }
  if (!item) return <p className="hint">Loading…</p>;

  return (
    <div className="card detail stack">
      <Link to="/" className="back">
        ← My links
      </Link>

      <div className="item-top">
        <span className="site">{siteName(item.url)}</span>
        {item.content_type && <span className="type">{item.content_type}</span>}
        <StatusBadge status={item.status} />
      </div>

      <h1>{item.title || item.url}</h1>
      <a href={item.url} target="_blank" rel="noreferrer" className="original">
        Open the original page ↗
      </a>

      {item.summary && <p className="summary">{item.summary}</p>}
      {item.status === "failed" && <p className="error">{item.error_message}</p>}
      {isWorking(item) && <p className="hint">MyStash is reading this page. This takes a few seconds.</p>}

      <TagEditor item={item} onChange={setItem} />

      <p className="hint">Saved {new Date(item.created_at).toLocaleString()}</p>
      {error && <p className="error">{error}</p>}

      <div>
        <button className="danger" onClick={handleDelete}>
          Delete
        </button>
      </div>
    </div>
  );
}

// Shows the item's tags with a × to remove each one, and a box to add a new one.
// Every change is saved right away.
function TagEditor({ item, onChange }) {
  const [newTag, setNewTag] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const names = item.tags.map((tag) => tag.name);
  // The API refuses tag changes until the worker has finished.
  const locked = isWorking(item);

  async function save(newNames) {
    setError("");
    setBusy(true);
    try {
      onChange(await api.updateTags(item.id, newNames));
      setNewTag("");
    } catch (err) {
      setError(err.message);
    }
    setBusy(false);
  }

  function handleAdd(event) {
    event.preventDefault();
    if (newTag.trim()) save([...names, newTag]);
  }

  return (
    <section className="stack">
      <h2>Tags</h2>
      {names.length === 0 && <p className="hint">No tags yet.</p>}
      <ul className="tags">
        {names.map((name) => (
          <li key={name} className="tag">
            {name}
            <button
              className="tag-remove"
              onClick={() => save(names.filter((other) => other !== name))}
              disabled={busy || locked}
              aria-label={`Remove tag ${name}`}
            >
              ×
            </button>
          </li>
        ))}
      </ul>
      <form onSubmit={handleAdd} className="row">
        <input
          value={newTag}
          onChange={(e) => setNewTag(e.target.value)}
          placeholder="Add a tag"
          aria-label="New tag"
          maxLength={64}
          disabled={locked}
        />
        <button type="submit" disabled={busy || locked || !newTag.trim()}>
          Add
        </button>
      </form>
      {error && <p className="error">{error}</p>}
    </section>
  );
}
