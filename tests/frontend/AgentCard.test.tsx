import { fireEvent, render, screen } from '@testing-library/react';
import AgentCard from '../../src/components/AgentCard';
import type { Agent } from '../../src/types';

const agent = { id: 'capstone', name: 'Project AI', desc: 'Build your project', icon: 'P', color: 'blue', rating: 4.5, author: 'DigiDARA' } as Agent;

test('shows the agent identity and description', () => {
  render(<AgentCard agent={agent} onClick={jest.fn()} />);
  expect(screen.getByRole('heading', { name: 'Project AI' })).toBeInTheDocument();
  expect(screen.getByText('Build your project')).toBeInTheDocument();
  expect(screen.getByText('By DigiDARA')).toBeInTheDocument();
});

test('opens the selected agent exactly once', () => {
  const open = jest.fn();
  render(<AgentCard agent={agent} onClick={open} />);
  fireEvent.click(screen.getByRole('heading', { name: 'Project AI' }));
  expect(open).toHaveBeenCalledTimes(1);
  expect(open).toHaveBeenCalledWith('capstone');
});
