jest.mock('../../src/lib/capstoneApi', () => ({}));

import fs from 'fs';
import path from 'path';
import { render, screen } from '@testing-library/react';
import AgentDashboard from '../../src/components/AgentDashboard';
import { createInitialCapstoneState } from '../../src/lib/capstoneFlow';
import { CAPSTONE_EXAMPLE_FILES, CAPSTONE_EXAMPLE_OPTIONS } from '../../src/lib/capstoneExamples';

const user = { id: 'u1', name: 'Asha Rao', email: 'asha@example.com', mobile: '9999999999', initial: 'A' };
const publicDir = path.resolve(__dirname, '../../public');

test('the dashboard always lists both example downloads, whatever the step', () => {
  render(<AgentDashboard user={user} state={createInitialCapstoneState(user)} onClose={jest.fn()} />);
  const report = screen.getByRole('link', { name: /Download example report/ });
  const project = screen.getByRole('link', { name: /Download example project/ });
  expect(report).toHaveAttribute('href', '/capstone-examples/capstone-example-report.docx');
  expect(report).toHaveAttribute('download', 'capstone-example-report.docx');
  expect(project).toHaveAttribute('href', '/capstone-examples/capstone-example-project.zip');
  expect(project).toHaveAttribute('download', 'capstone-example-project.zip');
});

test('chat options built from the examples are links, not buttons that message the agent', () => {
  expect(CAPSTONE_EXAMPLE_OPTIONS).toHaveLength(2);
  for (const option of CAPSTONE_EXAMPLE_OPTIONS) {
    expect(option.href).toMatch(/^\/capstone-examples\//);
    expect(option.download).toBeTruthy();
  }
});

test.each(CAPSTONE_EXAMPLE_FILES.map((file) => [file.download, file.href]))('%s is served from public/ and is a real archive', (name, href) => {
  const file = path.join(publicDir, href);
  expect(fs.existsSync(file)).toBe(true);
  const bytes = fs.readFileSync(file);
  expect(bytes.length).toBeGreaterThan(10_000);
  expect(bytes.subarray(0, 2).toString()).toBe('PK'); // .docx and .zip are both zip containers
  expect(name).toMatch(/\.(docx|zip)$/);
});
