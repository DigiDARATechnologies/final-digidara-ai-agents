/// <reference types="node" />

import fs from 'node:fs';
import path from 'node:path';


test('aptitude UI describes fixed difficulty and shows complete-test generation progress', () => {
  const panel = fs.readFileSync(
    path.resolve(process.cwd(), 'src/components/AptitudePracticePanel.tsx'),
    'utf8',
  );
  const dashboard = fs.readFileSync(
    path.resolve(process.cwd(), 'src/components/AptitudeDashboard.tsx'),
    'utf8',
  );
  const app = fs.readFileSync(path.resolve(process.cwd(), 'src/App.tsx'), 'utf8');

  expect(`${panel}\n${dashboard}`).not.toMatch(/adaptive difficulty|adaptive test/i);
  expect(panel).toContain('Easy + Medium + Hard');
  expect(app).toContain('Generating your complete aptitude test');
  expect(app).toMatch(/composerDisabled=\{[^}]*\bisAptitudeChat\b[^}]*typing/);
  expect(panel).toContain('hintPending');
  expect(panel).toContain('Generating hint');
  expect(app).toContain('hintPending={typing');
});
