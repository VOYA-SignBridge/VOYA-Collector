import js from '@eslint/js'
import globals from 'globals'
import reactHooks from 'eslint-plugin-react-hooks'
import reactRefresh from 'eslint-plugin-react-refresh'
import tsPlugin from '@typescript-eslint/eslint-plugin'
import tsParser from '@typescript-eslint/parser'

// Flat config that composes recommended rules to avoid nested 'extends' errors.
export default [
  { ignores: ['dist'] },
  {
    files: ['**/*.{ts,tsx,js,jsx}'],
    languageOptions: {
      parser: tsParser,
      parserOptions: {
        ecmaVersion: 2020,
        sourceType: 'module',
        ecmaFeatures: { jsx: true },
      },
      globals: {
        ...globals.browser,
        React: 'readonly',
      },
    },
    plugins: {
      '@typescript-eslint': tsPlugin,
      'react-hooks': reactHooks,
      'react-refresh': reactRefresh,
    },
    rules: {
      // base JS recommended rules
      ...js.configs.recommended.rules,
      // TypeScript recommended rules (spread explicit rules object)
      ...(tsPlugin.configs && tsPlugin.configs.recommended
        ? tsPlugin.configs.recommended.rules
        : {}),
      // react-hooks recommended rules (if available as configs)
      ...(reactHooks.configs && reactHooks.configs['recommended-latest']
        ? reactHooks.configs['recommended-latest'].rules
        : {}),
      // react-refresh typically doesn't export rules, so we skip it.
    },
  },
]
