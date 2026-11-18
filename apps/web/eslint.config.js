import importPlugin from 'eslint-plugin-import';
import reactPlugin from 'eslint-plugin-react';
import reactHooks from 'eslint-plugin-react-hooks';
import globals from 'globals';

export default [
  {
    files: ['src/**/*.{js,jsx}', 'tests/**/*.{js,jsx}'],
    languageOptions: {
      ecmaVersion: 'latest',
      sourceType: 'module',
      globals: globals.browser,
      parserOptions: { ecmaFeatures: { jsx: true } },
    },
    plugins: { import: importPlugin, react: reactPlugin, 'react-hooks': reactHooks },
    settings: { react: { version: 'detect' } },
    rules: {
      'import/no-restricted-paths': ['error', {
        basePath: './src',
        zones: [
          { target: './features', from: './app', message: '기능 코드는 앱 조립 계층을 가져올 수 없습니다.' },
          { target: './shared', from: './features', message: '공용 UI는 기능 코드에 의존할 수 없습니다.' },
        ],
      }],
      'react-hooks/rules-of-hooks': 'error',
      'react-hooks/exhaustive-deps': 'warn',
    },
  },
];
