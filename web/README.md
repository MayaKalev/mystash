# web

The MyStash website: React + Vite in plain JavaScript.

- `src/api.js`: every call to the API, and the saved login token
- `src/pages/AuthPage.jsx`: log in and sign up
- `src/pages/ItemsPage.jsx`: save a link, the list with live status, and the filters
- `src/pages/ItemPage.jsx`: one link's details, tag editing, and delete
- `src/components/ItemInfo.jsx`: status badge, tag list, and other shared pieces

Run it with `docker compose up --build` from the project root, or on its own with
`npm install && npm run dev` while the API is running. Then open http://localhost:5173.
