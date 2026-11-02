import { useState } from "react";
import { Link, useNavigate } from "react-router";
import { api, saveToken } from "../api.js";

// One page for both logging in and signing up, because the forms are the same.
export default function AuthPage({ mode }) {
  const isSignup = mode === "signup";
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function handleSubmit(event) {
    event.preventDefault(); // Stop the browser from reloading the page.
    setError("");
    setBusy(true);
    try {
      if (isSignup) await api.register(email, password);
      // After signing up, log straight in so the user doesn't have to type it all again.
      const { access_token } = await api.login(email, password);
      saveToken(access_token);
      navigate("/");
    } catch (err) {
      setError(err.message);
      setBusy(false);
    }
  }

  return (
    <div className="card auth">
      <h1>{isSignup ? "Create your account" : "Log in"}</h1>

      <form onSubmit={handleSubmit} className="stack">
        <label>
          Email
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            autoComplete="email"
            required
          />
        </label>
        <label>
          Password
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete={isSignup ? "new-password" : "current-password"}
            minLength={isSignup ? 8 : undefined}
            required
          />
        </label>
        {isSignup && <p className="hint">At least 8 characters.</p>}
        {error && <p className="error">{error}</p>}
        <button type="submit" disabled={busy}>
          {isSignup ? "Sign up" : "Log in"}
        </button>
      </form>

      <p className="hint">
        {isSignup ? (
          <>Already have an account? <Link to="/login">Log in</Link></>
        ) : (
          <>New here? <Link to="/signup">Create an account</Link></>
        )}
      </p>
    </div>
  );
}
