import { Link, Navigate, Route, Routes, useNavigate } from "react-router";
import { getToken, logOut } from "./api.js";
import AuthPage from "./pages/AuthPage.jsx";
import ItemPage from "./pages/ItemPage.jsx";
import ItemsPage from "./pages/ItemsPage.jsx";

// Pages that need a login send logged-out visitors to the login page.
function LoggedIn({ children }) {
  return getToken() ? children : <Navigate to="/login" replace />;
}

export default function App() {
  const navigate = useNavigate();

  function handleLogOut() {
    logOut();
    navigate("/login");
  }

  return (
    <>
      <header className="header">
        <Link to="/" className="logo">
          MyStash
        </Link>
        {getToken() && (
          <button className="link-button" onClick={handleLogOut}>
            Log out
          </button>
        )}
      </header>

      <main className="main">
        <Routes>
          <Route path="/login" element={<AuthPage mode="login" />} />
          <Route path="/signup" element={<AuthPage mode="signup" />} />
          <Route path="/" element={<LoggedIn><ItemsPage /></LoggedIn>} />
          <Route path="/items/:id" element={<LoggedIn><ItemPage /></LoggedIn>} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>
    </>
  );
}
