import js from "@eslint/js";
import tseslint from "typescript-eslint";
import { defineConfig, globalIgnores } from "eslint/config";

export default defineConfig([
  globalIgnores(["dist"]),
  {
    files: ["**/*.ts"],
    extends: [js.configs.recommended, tseslint.configs.recommended],
    languageOptions: {
      ecmaVersion: 2022,
    },
    rules: {
      // Allow console.log in cli.ts (CLI output), warn everywhere else
      "no-console": ["warn", { allow: ["warn", "error"] }],
      "eqeqeq": ["error", "always", { null: "ignore" }],
      "no-var": "error",
      "prefer-const": "error",
      "no-debugger": "error",
      "no-eval": "error",
      "no-implied-eval": "error",
      "@typescript-eslint/no-unused-vars": ["warn", { argsIgnorePattern: "^_" }],
      "no-useless-assignment": "warn",
      "no-empty": ["error", { allowEmptyCatch: false }],
      "no-useless-catch": "error",
    },
  },
  {
    // CLI output uses console.log intentionally
    files: ["**/cli.ts"],
    rules: {
      "no-console": "off",
    },
  },
]);
