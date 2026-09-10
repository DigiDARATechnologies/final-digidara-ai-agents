module.exports = {
  testEnvironment: 'jsdom',
  roots: ['<rootDir>/tests/frontend'],
  testMatch: ['**/*.test.ts', '**/*.test.tsx'],
  transform: { '^.+\\.[tj]sx?$': ['babel-jest', {
    presets: [['@babel/preset-env', { targets: { node: 'current' } }],
      '@babel/preset-typescript', ['@babel/preset-react', { runtime: 'automatic' }]],
  }] },
  setupFilesAfterEnv: ['@testing-library/jest-dom'],
  clearMocks: true,
  coverageDirectory: 'artifacts/frontend-coverage',
  coverageReporters: ['text', 'lcov', 'json-summary'],
};
