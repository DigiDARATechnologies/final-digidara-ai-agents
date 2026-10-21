import { parseBossCommand } from '../../src/lib/bossCommands';

test.each([
  ['open aptitude', 'aptitude'],
  ['Switch to the mock interview agent please', 'mock-interview'],
  ['Hey Boss, go to coding practice', 'leetcode'],
  ['take me to the resume builder', 'resume-builder'],
  ['now open capstone project', 'capstone-project'],
  ['go back to Boss chat', 'boss'],
  ['show me my job readiness', 'readiness'],
  ['open AI certification', 'certificate-agent'],
  ['can you open the job agent', 'job-fetch'],
  ['switch to communication coach.', 'communication-coach'],
  ['aptitude open', 'aptitude'],
])('"%s" opens %s', (said, target) => {
  expect(parseBossCommand(said)).toMatchObject({ type: 'open', target });
});

test.each(['close the tab', 'Hey Boss close this', 'please close Boss'])('"%s" closes Boss', (said) => {
  expect(parseBossCommand(said)).toEqual({ type: 'close' });
});

test.each([
  'how do I open the resume tab?',
  'open my last aptitude chat',
  'give me my certificate link',
  'what is aptitude',
  'show me how to solve this',
  'how do I close my account',
])('"%s" is a question for Boss, not a command', (said) => {
  expect(parseBossCommand(said)).toBeNull();
});
