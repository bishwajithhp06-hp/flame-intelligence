# FLAME INTELLIGENCE frontend

## Requirements

Use Node.js `^20.19.0` or `>=22.12.0`. Node.js 22.12.0 is pinned in `.nvmrc`; a newer compatible Node.js 22 release is recommended. Vite 8 and Oxlint 1.93 require this minimum.

With nvm-windows, switch to the pinned version from this directory:

```powershell
nvm install 22.12.0
nvm use 22.12.0
node --version
```

## Install and run (PowerShell)

```powershell
npm ci --include=optional
npm run dev
```

The Vite development server listens on port 5173 and proxies `/api` requests to `http://127.0.0.1:8000`, matching the FastAPI bind address. Start the backend separately from the repository's `backend` directory.

Run the production build and lint checks with:

```powershell
npm run build
npm run lint
```
