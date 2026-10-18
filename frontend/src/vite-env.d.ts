/// <reference types="vite/client" />

// Declares the environment variables the frontend reads, so TypeScript knows their type.
interface ImportMetaEnv {
  readonly VITE_API_BASE_URL?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
