module.exports = {
  testEnvironment: 'jsdom',
  roots: ['<rootDir>/tests/frontend'],
  testMatch: ['**/*.test.ts', '**/*.test.tsx'],
  transform: { '^.+\\.[tj]sx?$': ['babel-jest', {
    presets: [['@babel/preset-env', { targets: { node: 'current' } }],
      '@babel/preset-typescript', ['@babel/preset-react', { runtime: 'automatic' }]],
  }] },
  setupFilesAfterEnv: ['@testing-library/jest-dom'],
  // Jest has no bundler-style asset loader, so an `import x from "./y.svg"`
  // (e.g. Logo.tsx) is stubbed to a plain string instead of crashing on raw
  // SVG markup being parsed as JavaScript.
  moduleNameMapper: { '\\.svg$': '<rootDir>/tests/frontend/__mocks__/svgMock.js' },
  clearMocks: true,
  coverageDirectory: 'artifacts/frontend-coverage',
  coverageReporters: ['text', 'lcov', 'json-summary'],
};
