// Every call to the MyStash API goes through this file.

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";
const TOKEN_KEY = "mystash-token";

export function getToken() {
  return localStorage.getItem(TOKEN_KEY);
}

export function saveToken(token) {
  localStorage.setItem(TOKEN_KEY, token);
}

export function logOut() {
  localStorage.removeItem(TOKEN_KEY);
}

// Sends a request and returns the JSON answer. Throws an Error with a readable message
// if the API says no.
async function request(method, path, body) {
  const headers = {};
  if (body !== undefined) headers["Content-Type"] = "application/json";
  const token = getToken();
  if (token) headers["Authorization"] = `Bearer ${token}`;

  let response;
  try {
    response = await fetch(API_URL + path, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch {
    throw new Error("Can't reach the MyStash API. Is it running?");
  }

  // The login has expired or is invalid: forget it and go back to the login page.
  if (response.status === 401 && token) {
    logOut();
    window.location.href = "/login";
    throw new Error("Please log in again");
  }

  if (response.status === 204) return null;
  const data = await response.json();
  if (!response.ok) throw new Error(errorMessage(data));
  return data;
}

// FastAPI sends errors as {"detail": "text"}, or as a list when the input is invalid.
function errorMessage(data) {
  if (typeof data.detail === "string") return data.detail;
  if (Array.isArray(data.detail)) return data.detail.map((error) => error.msg).join(". ");
  return "Something went wrong";
}

export const api = {
  register: (email, password) => request("POST", "/auth/register", { email, password }),
  login: (email, password) => request("POST", "/auth/login", { email, password }),
  listItems: (filters) => request("GET", "/items?" + new URLSearchParams(filters)),
  getItem: (id) => request("GET", `/items/${id}`),
  saveItem: (url) => request("POST", "/items", { url }),
  updateTags: (id, tags) => request("PUT", `/items/${id}/tags`, { tags }),
  deleteItem: (id) => request("DELETE", `/items/${id}`),
  listTags: () => request("GET", "/tags"),
};
