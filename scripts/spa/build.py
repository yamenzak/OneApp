"""Vite, Tailwind, PostCSS, package.json and ESLint.

The two apps cannot share an npm workspace — each is mirrored to its own
repository for Frappe Cloud and has to be self-contained — so the build is
generated into both from one definition instead. Everything here follows
frappe-ui's own conventions: `frappe-ui/vite` owns the dev proxy, build paths
and index.html; `frappe-ui/tailwind` owns the design tokens.
"""

import json
from .spec import BANNER, DEPENDENCIES, DEV_DEPENDENCIES


def vite_config(app: str, spec: dict) -> str:
    types = json.dumps(spec["types"], indent=2).replace('"', "'")
    html_name = spec["route"].lstrip("/")
    shells = json.dumps(spec.get("shells", []))
    # Vitest reads this same config. Only bundles that declare unit tests get
    # the block, so the other one has no reason to install a runner.
    unit = ""
    if spec.get("unit_tests"):
        unit = (
            "\n  test: {\n"
            "    globals: true,\n"
            f"    include: ['{spec['unit_tests']}'],\n"
            # `node`, matching upstream: nearly a thousand engine tests have no
            # use for a DOM, and the handful that do opt in per file with a
            # `// @vitest-environment happy-dom` header.
            "    environment: 'node',\n"
            "  },"
        )
    return BANNER + f"""
import {{ defineConfig }} from 'vite'
import vue from '@vitejs/plugin-vue'
import frappeui from 'frappe-ui/vite'
import fs from 'node:fs'
import path from 'node:path'

// Frappe serves one .html per website route. frappe-ui's plugin emits exactly
// one, so the additional surfaces are copies of it — same hashed asset tags,
// different <title>, and a sibling .py that decides who may load them. Copying
// after the build is what guarantees they can never reference stale assets.
const EXTRA_SHELLS = {shells}

function extraShells() {{
  return {{
    name: 'oneapp-extra-shells',
    closeBundle() {{
      if (!EXTRA_SHELLS.length) return
      const source = path.resolve(__dirname, '../{app}/www/{html_name}.html')
      if (!fs.existsSync(source)) {{
        // Silently skipping would ship a route that 404s with nothing to
        // explain why, so fail the build instead.
        throw new Error(`extraShells: ${{source}} was not emitted by frappe-ui`)
      }}
      const html = fs.readFileSync(source, 'utf8')
      for (const shell of EXTRA_SHELLS) {{
        fs.writeFileSync(
          path.resolve(__dirname, `../{app}/www/${{shell.name}}.html`),
          html.replace(/<title>[^<]*<\\/title>/, `<title>${{shell.title}}</title>`),
        )
      }}
    }},
  }}
}}

// frappe-ui's plugin owns the parts that are easy to get subtly wrong: it
// proxies /api, /app, /assets, /files and /private to the bench it detects from
// common_site_config.json, and it emits ../{app}/www/<route>.html so the SPA is
// served by Frappe itself. Hand-rolling any of that is how the two apps drift.
export default defineConfig({{
  plugins: [
    frappeui({{
      frontendRoute: '{spec["route"]}',
      // Given explicitly rather than inferred. frappe-ui derives these by
      // walking up for a bench layout (a directory with both sites/ and apps/),
      // which exists on Frappe Cloud but not in this monorepo — so inference
      // returns null here and the production build fails with
      // "indexHtmlPath is required". Stating them makes the build identical
      // everywhere: monorepo, bench, and CI.
      buildConfig: {{
        outDir: path.resolve(__dirname, '../{app}/public/frontend'),
        indexHtmlPath: '../{app}/www/{html_name}.html',
      }},
      frappeTypes: {{
        input: {types},
      }},
    }}),
    vue(),
    extraShells(),
  ],
  resolve: {{
    alias: {{ '@': path.resolve(__dirname, 'src') }},
  }},{unit}
}})
"""


def index_html(app: str, spec: dict) -> str:
    """Vite's entry document.

    The frappe-ui plugin transforms this into ../<app>/www/<route>.html at build
    time — it does not create it, so this file has to exist.

    The inline theme script runs before first paint. Without it the page flashes
    white before Tailwind loads, because `bg-surface-base` only resolves once the
    stylesheet arrives.
    """
    return f"""<!doctype html>
<html class="h-full" lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover" />
    <title>{spec["title"]}</title>
    <script>
      ;(function () {{
        try {{
          var stored = localStorage.getItem('theme')
          var theme = stored === 'light' || stored === 'dark' ? stored : null
          if (!theme) {{
            theme = window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
          }}
          document.documentElement.setAttribute('data-theme', theme)
          document.documentElement.style.backgroundColor =
            theme === 'dark' ? '#171717' : '#ffffff'
        }} catch (e) {{}}
      }})()
    </script>
    <link rel="icon" type="image/svg+xml" href="/assets/{app}/favicon.svg" />
    <meta name="theme-color" media="(prefers-color-scheme: light)" content="#ffffff" />
    <meta name="theme-color" media="(prefers-color-scheme: dark)" content="#171717" />
  </head>
  <body class="h-full bg-surface-base">
    <div id="app" class="h-full"></div>
    <script type="module" src="/src/main.js"></script>
  </body>
</html>
"""


def tailwind_config(app: str) -> str:
    return BANNER + """
import preset, { content as frappeUIContent } from 'frappe-ui/tailwind'

// Tailwind 3 does not merge `content` from a preset, so frappe-ui's own source
// globs have to be listed here or half the component styles are purged out.
export default {
  presets: [preset],
  content: [...frappeUIContent, './index.html', './src/**/*.{vue,js,ts,jsx,tsx}'],
  theme: {
    extend: {
      fontFamily: {
        // The one face that is not the interface face. `font-display` is for a
        // title somebody is meant to *look at* rather than read past — a
        // record's name over its own photograph, and whatever else earns it
        // later. Everything else in the product stays in the UI face, which is
        // the point: a display face used twice is a voice, used everywhere it
        // is a costume.
        //
        // The `@font-face` rules, the two files it is made of and the reason
        // it is self-hosted are in `src/index.css`.
        display: [
          'OneSpace Display',
          'ui-sans-serif',
          'system-ui',
          'sans-serif',
        ],
      },
    },
  },
}
"""


def postcss_config(app: str) -> str:
    return BANNER + """
export default {
  plugins: { tailwindcss: {}, autoprefixer: {} },
}
"""


def app_root_package_json(app: str, spec: dict) -> str:
    """Repo-root package.json.

    Frappe Cloud installs and builds an app by running yarn at its repository
    root, so this is what makes the SPA exist in a deployed bench at all.
    Without it the build silently does nothing and the www page 404s, because
    the HTML is emitted by the Vite build rather than committed.
    """
    return json.dumps(
        {
            "name": app.replace("_", "-"),
            "private": True,
            "type": "module",
            "_generated": "scripts/gen_frontend.py",
            "scripts": {
                "postinstall": "cd frontend && yarn install",
                "dev": "cd frontend && yarn dev",
                "build": "cd frontend && yarn build",
                "lint": "cd frontend && yarn lint",
            },
        },
        indent=2,
    ) + "\n"


def package_json(app: str, spec: dict) -> str:
    return json.dumps(
        {
            "name": f"{app.replace('_', '-')}-frontend",
            "private": True,
            "type": "module",
            "version": "0.0.1",
            "_generated": "scripts/gen_frontend.py",
            "scripts": {
                "dev": "vite",
                "build": "vite build",
                "preview": "vite preview",
                "lint": "eslint src",
                "e2e": "playwright test",
                # The loop to develop against: one project, four workers.
                # Four is unsafe for the whole suite — see the note in
                # playwright.config.js — and fine for the handful of specs you
                # are actually working on.
                "e2e:fast": (
                    "ONEAPP_E2E_WORKERS=4 playwright test --project=desktop"
                ),
                # Look at a screen without writing a script to look at it.
                # See the header of shot.mjs.
                "shot": "node shot.mjs",
                # Only where a bundle declares `unit_tests`. Seconds, not the
                # nine and a half minutes the browser pass costs, so this is
                # the one that belongs in an edit loop.
                **({"test": "vitest run"} if spec.get("unit_tests") else {}),
                **({"test:watch": "vitest"} if spec.get("unit_tests") else {}),
            },
            "dependencies": dict(sorted({**DEPENDENCIES, **spec.get("packages", {})}.items())),
            "devDependencies": dict(
                sorted({**DEV_DEPENDENCIES, **spec.get("dev_packages", {})}.items())
            ),
        },
        indent=2,
    ) + "\n"


def eslint_config(app: str) -> str:
    return BANNER + """
import globals from 'globals'
import pluginVue from 'eslint-plugin-vue'

// The guard. Every native control here has a frappe-ui equivalent, and using the
// raw element is how a design system quietly stops being one — a plain <button>
// looks close enough in isolation and wrong next to everything else.
//
// Escape hatch is a one-line eslint-disable with a reason, so bypassing it is a
// visible decision rather than an accident.
const BANNED = [
  { element: 'button', message: 'Use <Button> from @/ui instead of a raw <button>.' },
  { element: 'input', message: 'Use <TextInput>, <FormControl>, <Checkbox> or <Switch> from @/ui.' },
  { element: 'select', message: 'Use <Select> or <Autocomplete> from @/ui.' },
  { element: 'textarea', message: 'Use <Textarea> or <FormControl type="textarea"> from @/ui.' },
  { element: 'dialog', message: 'Use <Dialog> from @/ui.' },
  { element: 'table', message: 'Use <ListView> from frappe-ui/list.' },
]

export default [
  ...pluginVue.configs['flat/recommended'],
  {
    // What `no-undef` is allowed to already know about. Browser globals
    // because this is a browser, and Vue's compiler macros because they are
    // not imports — `defineProps` is compiled away, so to a linter reading the
    // source it is a name nothing defines.
    files: ['src/**/*.{js,vue}'],
    languageOptions: {
      globals: {
        ...globals.browser,
        defineProps: 'readonly',
        defineEmits: 'readonly',
        defineExpose: 'readonly',
        defineModel: 'readonly',
        defineOptions: 'readonly',
        defineSlots: 'readonly',
        withDefaults: 'readonly',
      },
    },
    rules: {
      // A name nothing defines. Off by default in flat config, which is how
      // `pages/Mail.vue` called `onDoctypeChange` for a whole batch without
      // importing it: `vite build` compiles an undefined identifier happily,
      // the SFC renders down to a `setup` that throws on its first line, and
      // the page is blank. Nothing but a browser saw it — 1939 Python tests
      // and a clean `yarn lint` both passed over it.
      'no-undef': 'error',

      // The other half of the same rule: a name nothing *uses*. An import left
      // behind by a refactor is dead weight the bundler still resolves and,
      // worse, reads as evidence that a file still does something it no longer
      // does. Arguments are exempt — a handler often takes what it ignores.
      'no-unused-vars': ['error', { args: 'none' }],

    },
  },
  {
    files: ['src/**/*.vue'],
    rules: {
      'vue/no-restricted-html-elements': ['error', ...BANNED],
      'vue/multi-word-component-names': 'off',
      'vue/no-v-html': 'error',

      // Formatting is a formatter's job. Left on, these produce dozens of
      // warnings per file and train everyone to ignore lint output — which is
      // where the rules that actually matter live.
      'vue/max-attributes-per-line': 'off',
      'vue/singleline-html-element-content-newline': 'off',
      'vue/html-self-closing': 'off',
      'vue/html-indent': 'off',
      'vue/html-closing-bracket-newline': 'off',
      'vue/attributes-order': 'off',
      'vue/first-attribute-linebreak': 'off',
    },
  },
  {
    // The shared runtime is exempt — it is what wraps frappe-ui.
    files: ['src/**/*.{js,vue}'],
    ignores: ['src/ui.js', 'src/lib/**'],
    rules: {
      'no-restricted-imports': ['error', {
        paths: [
          {
            name: 'frappe-ui',
            // Two separate reasons, both load-bearing:
            //  - components: '@/ui' is the one reviewable list of what is allowed
            //  - data/notify: '@/lib/resource' and '@/lib/notify' are what apply
            //    response unwrapping, Frappe error parsing, toasts and sound
            message:
              "Import components from '@/ui', data helpers from '@/lib/resource', " +
              "and toasts from '@/lib/notify'. Going direct skips error parsing, " +
              'response unwrapping and notification sound.',
          },
          {
            name: 'frappe-ui/list',
            message: \"Import list components from '@/ui' too — one import path \" +
              'for the whole sanctioned surface.',
          },
          {
            name: 'frappe-ui/editor',
            message: \"Import the editor from '@/ui' too — one import path for \" +
              'the whole sanctioned surface.',
          },
          {
            // The unstable entry point, so the one reviewable list matters
            // more here rather than less: a breaking change upstream should
            // show up in one file, not in however many reached for it.
            name: 'frappe-ui/experimental',
            message: \"Import experimental components from '@/ui' too. They \" +
              'carry no backward-compatibility promise, so the barrel is what ' +
              'keeps the blast radius to one file.',
          },
          {
            name: 'frappe-ui/charts',
            message: "Import charts from '@/ui' too. They pull echarts in, so " +
              'the one reviewable list is also the one place that decides ' +
              'what a page pays for.',
          },
          {
            name: 'socket.io-client',
            message: "Use onDoctypeChange from '@/lib/socket' — one shared, " +
              'reference-counted socket per app.',
          },
        ],
      }],
      // console.error is deliberate in the error normaliser; noise elsewhere.
      'no-console': ['warn', { allow: ['warn', 'error'] }],
    },
  },
  {
    // The layout primitives belong to AppShell and nothing else.
    //
    // DesktopShell and MobileShell are different components with different
    // slots, so every surface that composes them directly makes its own choice
    // about the breakpoint, about whether a rail appears, and about how a phone
    // reaches the app switcher. Two surfaces choosing differently is how one
    // account starts looking like two products on the same tablet — and the
    // mobile shell has no rail slot at all, so 'just use MobileShell' silently
    // drops app switching.
    files: ['src/**/*.vue'],
    ignores: ['src/components/AppShell.vue'],
    rules: {
      'no-restricted-imports': ['error', {
        paths: [{
          name: '@/ui',
          importNames: [
            'DesktopShell', 'MobileShell', 'MobileNav', 'MobileNavItem',
            'Rail', 'RailItem',
          ],
          message:
            'Compose <AppShell> instead. It owns the desktop/mobile split, the ' +
            'rail, and the bottom-bar app switcher, so every surface agrees.',
        }],
      }],
    },
  },
]
"""
