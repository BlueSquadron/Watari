// ESLint 9 flat config.
//
// The project declared eslint and @typescript-eslint in package.json but never
// committed a config, so `npm run lint` failed with "couldn't find a
// configuration file" — even though CONTRIBUTING and the Makefile both tell you
// to run it. This is the missing piece.
//
// Deliberately close to the recommended sets: the point is to catch real
// mistakes, not to impose a house style. Formatting belongs to Prettier.

import js from "@eslint/js";
import tsPlugin from "@typescript-eslint/eslint-plugin";
import tsParser from "@typescript-eslint/parser";
import globals from "globals";

export default [
  {
    ignores: ["dist/**", "build/**", "node_modules/**", "coverage/**"],
  },
  js.configs.recommended,
  {
    files: ["**/*.{ts,tsx}"],
    languageOptions: {
      parser: tsParser,
      ecmaVersion: "latest",
      sourceType: "module",
      parserOptions: {
        ecmaFeatures: { jsx: true },
      },
      globals: {
        ...globals.browser,
        ...globals.es2021,
      },
    },
    plugins: {
      "@typescript-eslint": tsPlugin,
    },
    rules: {
      ...tsPlugin.configs.recommended.rules,

      // TypeScript resolves identifiers itself, and no-undef does not
      // understand type-only names — it is noise on a TS codebase.
      "no-undef": "off",
      // Superseded by the TypeScript-aware version below.
      "no-unused-vars": "off",
      "@typescript-eslint/no-unused-vars": [
        "error",
        { argsIgnorePattern: "^_", varsIgnorePattern: "^_" },
      ],
    },
  },
  {
    // Config files run in Node.
    files: ["*.config.{js,ts}", "vite.config.ts"],
    languageOptions: {
      globals: { ...globals.node },
    },
  },
];
