import { defineConfig } from 'vite';

// relative asset paths, so the site works at a domain root (Cloudflare Pages) or under /flat-finder/ (GitHub Pages)
export default defineConfig({ base: './' });
