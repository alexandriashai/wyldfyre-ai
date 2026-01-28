import { defineConfig, type PluginOption } from 'vite';
import { visualizer } from 'rollup-plugin-visualizer';
import purgeCss from 'vite-plugin-purgecss';
import fs from 'node:fs';
import path from 'node:path';

const pagesRoot = path.resolve(__dirname, 'resources/web/pages');
const entryFiles: string[] = [];
const vendorChunkPackages = new Set(['bootstrap', '@popperjs/core']);
const routeChunkPattern = /resources\/web\/pages\/([^/]+)\//;
const tinyMCEPattern = /node_modules\/tinymce/;

const collectEntries = (directory: string): void => {
  if (!fs.existsSync(directory)) {
    return;
  }

  const entries = fs.readdirSync(directory, { withFileTypes: true });

  for (const entry of entries) {
    const absolutePath = path.join(directory, entry.name);

    if (entry.isDirectory()) {
      collectEntries(absolutePath);
      continue;
    }

    if (entry.isFile() && entry.name.endsWith('.entry.ts')) {
      entryFiles.push(absolutePath);
    }
  }
};

collectEntries(pagesRoot);

const defaultEntry = path.resolve(__dirname, 'resources/web/pages/overview/overview.entry.ts');
const rollupInput = entryFiles.length > 0 ? entryFiles : [defaultEntry];
const shouldAnalyze = process.env.ANALYZE === '1' || process.env.ANALYZE === 'true';
const plugins: PluginOption[] = [];

const resolvePackageName = (id: string): string | null => {
  const match = id.match(/node_modules\/(?:\.pnpm\/)?(@[^/]+\/[^/]+|[^/]+)/);
  return match ? match[1] : null;
};

const manualChunkForId = (id: string): string | undefined => {
  // CRITICAL: Never allow entry points to be shared chunks
  // This prevents circular dependencies in the manifest
  if (id.includes('.entry.ts') || id.includes('.entry.js')) {
    return undefined;
  }

  // Inline all brand-guide dependencies to avoid sharing with about.entry
  if (id.includes('brand-guide')) {
    return undefined;
  }

  // CRITICAL FIX: Do NOT create separate chunks for content-moderation modules
  // This was causing Vite to put internal helpers (preload, module interop) into
  // the nsfw chunk, which then forced every chunk that needed those helpers to
  // import nsfw, triggering TensorFlow loading.
  // Instead, let Vite inline these where needed.
  if (id.includes('services/content-moderation')) {
    return undefined; // Let Vite inline or bundle naturally
  }

  // Only process node_modules for chunking
  if (id.includes('node_modules')) {
    // TensorFlow is marked as external, so skip any chunking for it
    if (id.includes('@tensorflow') || id.includes('nsfwjs') || id.includes('@tensorflow-models')) {
      return undefined; // External, not bundled
    }

    // Separate TinyMCE into granular chunks for lazy loading
    if (tinyMCEPattern.test(id)) {
      // Core editor
      if (id.includes('tinymce/tinymce')) {
        return 'tinymce-core';
      }
      // Themes and icons
      if (id.includes('/themes/') || id.includes('/icons/')) {
        return 'tinymce-theme';
      }
      // Plugins
      if (id.includes('/plugins/')) {
        const pluginMatch = id.match(/\/plugins\/([^/]+)/);
        const pluginName = pluginMatch ? pluginMatch[1] : 'unknown';
        return `tinymce-plugin-${pluginName}`;
      }
      // Skins and models
      if (id.includes('/skins/') || id.includes('/models/')) {
        return 'tinymce-assets';
      }
      // Default TinyMCE chunk for anything else
      return 'tinymce';
    }

    // Vendor packages get their own chunks for efficient caching
    const packageName = resolvePackageName(id);
    if (packageName && vendorChunkPackages.has(packageName)) {
      return `vendor-${packageName}`;
    }

    // Group smaller utilities together to avoid too many small chunks
    if (packageName && (
      packageName.includes('lodash') ||
      packageName.includes('date-fns') ||
      packageName.includes('validator') ||
      packageName.includes('uuid')
    )) {
      return 'vendor-utils';
    }

    // Default vendor chunk for other node_modules
    if (packageName) {
      return 'vendor';
    }
  }

  return undefined;
};

// Add PurgeCSS for production builds with proper error handling
try {
  if (process.env.NODE_ENV === 'production') {
    plugins.push(
      purgeCss({
        content: ['./resources/**/*.{html,ts,php}', './resources/**/*.blade.php'],
        defaultExtractor: (content: string): string[] => content.match(/[\w-/:]+(?<!:)/g) || [],
        safelist: {
          standard: [
            /^(.*-)?modal(-.*)?$/,
            /^(.*-)?dropdown(-.*)?$/,
            /^(.*-)?tooltip(-.*)?$/,
            /^(.*-)?popover(-.*)?$/,
            /^(.*-)?collapse(-.*)?$/,
            /^(.*-)?carousel(-.*)?$/,
            /^(.*-)?alert(-.*)?$/,
            /^(.*-)?toast(-.*)?$/,
          ],
          deep: [/modal/, /dropdown/, /tooltip/, /popover/],
          greedy: [/data-bs/, /aria-/]
        }
      })
    );
  }
} catch (error) {
  console.warn('PurgeCSS plugin could not be loaded:', error);
}

// Add bundle analyzer for development with error handling
try {
  if (shouldAnalyze) {
    plugins.push(
      visualizer({
        filename: 'dist/stats.html',
        open: true,
        gzipSize: true,
        brotliSize: true,
      }) as PluginOption
    );
  }
} catch (error) {
  console.warn('Bundle analyzer plugin could not be loaded:', error);
}

export default defineConfig({
  plugins,
  root: path.resolve(__dirname, 'resources'),
  publicDir: path.resolve(__dirname, 'public'),
  build: {
    outDir: path.resolve(__dirname, 'public/dist'),
    emptyOutDir: true,
    manifest: true,
    rollupOptions: {
      input: rollupInput,
      output: {
        manualChunks: manualChunkForId,
        chunkFileNames: (chunkInfo): string => {
          const facadeModuleId = chunkInfo.facadeModuleId;
          if (facadeModuleId && routeChunkPattern.test(facadeModuleId)) {
            const routeMatch = facadeModuleId.match(routeChunkPattern);
            const routeName = routeMatch ? routeMatch[1] : 'unknown';
            return `chunks/${routeName}-[hash].js`;
          }
          return 'chunks/[name]-[hash].js';
        },
        entryFileNames: (entryInfo): string => {
          const { facadeModuleId } = entryInfo;
          if (facadeModuleId && routeChunkPattern.test(facadeModuleId)) {
            const routeMatch = facadeModuleId.match(routeChunkPattern);
            const routeName = routeMatch ? routeMatch[1] : 'unknown';
            return `entries/${routeName}-[hash].js`;
          }
          return 'entries/[name]-[hash].js';
        },
        assetFileNames: (assetInfo): string => {
          const { name } = assetInfo;
          if (name && /\.(css)$/.test(name)) {
            return 'assets/css/[name]-[hash][extname]';
          }
          if (name && /\.(png|jpe?g|gif|svg|webp|avif)$/.test(name)) {
            return 'assets/images/[name]-[hash][extname]';
          }
          if (name && /\.(woff2?|eot|ttf|otf)$/.test(name)) {
            return 'assets/fonts/[name]-[hash][extname]';
          }
          return 'assets/[name]-[hash][extname]';
        }
      },
      external: ['@tensorflow/tfjs', '@tensorflow/tfjs-node', 'nsfwjs'],
    },
    target: 'es2020',
    minify: 'terser',
    terserOptions: {
      compress: {
        drop_console: process.env.NODE_ENV === 'production',
        drop_debugger: true,
      },
    },
    sourcemap: process.env.NODE_ENV === 'development',
    reportCompressedSize: false,
    chunkSizeWarningLimit: 1000,
  },
  resolve: {
    alias: {
      '@': path.resolve(__dirname, 'resources'),
      '~bootstrap': path.resolve(__dirname, 'node_modules/bootstrap'),
    },
  },
  css: {
    devSourcemap: true,
    preprocessorOptions: {
      scss: {
        api: 'modern-compiler',
      },
    },
  },
  server: {
    port: 5173,
    host: '0.0.0.0',
    strictPort: true,
    open: false,
  },
  preview: {
    port: 4173,
    host: '0.0.0.0',
    strictPort: true,
  },
  optimizeDeps: {
    include: ['bootstrap', '@popperjs/core'],
    exclude: ['@tensorflow/tfjs', '@tensorflow/tfjs-node', 'nsfwjs'],
  },
});