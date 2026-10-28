jest.mock('../../src/lib/courseApi', () => ({
  mediaUrl: (src: string) => src, fetchCourses: jest.fn(), fetchCourse: jest.fn(), setLessonDone: jest.fn(),
}));

import { fireEvent, render, screen } from '@testing-library/react';
import Courses from '../../src/components/Courses';
import * as courseApi from '../../src/lib/courseApi';
import { embedUrl } from '../../src/lib/courseFormat';

const api = jest.mocked(courseApi);
const summary = { id: 'c1', title: 'Python basics', description: 'Start here', category: 'Programming', level: 'Beginner',
  published: true, position: 0, lessons: 2, completed: 0, videos: 2, notes: 1, updated_at: null };
const lesson = (id: string, extra: object = {}) => ({
  id, title: `Lesson ${id}`, description: '', position: Number(id), video_url: null, has_video: false, video_name: '',
  video_size: 0, has_notes: false, notes_name: '', notes_size: 0, completed: false, ...extra,
});

test('embed links become players', () => {
  expect(embedUrl('https://www.youtube.com/watch?v=abc123XYZ')).toBe('https://www.youtube-nocookie.com/embed/abc123XYZ');
  expect(embedUrl('https://vimeo.com/76979871')).toBe('https://player.vimeo.com/video/76979871');
  expect(embedUrl('https://evil.example/x')).toBeNull();
});

test('learners open a course, watch a lesson, read notes and mark it done', async () => {
  api.fetchCourses.mockResolvedValue({ courses: [summary] });
  api.fetchCourse.mockResolvedValue({ ...summary, lesson_list: [
    lesson('1', { has_video: true, video_src: '/course-media/v1', has_notes: true, notes_src: '/course-media/n1', notes_name: 'handbook.pdf', notes_size: 2048 }),
    lesson('2', { video_url: 'https://youtu.be/abc123XYZ' }),
  ] });
  api.setLessonDone.mockResolvedValue({ lesson_id: '1', completed: true });
  const { container } = render(<Courses />);
  fireEvent.click(await screen.findByRole('button', { name: /Python basics/ }));
  expect(await screen.findByRole('heading', { name: 'Lesson 1' })).toBeInTheDocument();
  expect(container.querySelector('video')?.getAttribute('src')).toMatch(/\/course-media\/v1$/);
  expect(screen.getByRole('link', { name: /handbook\.pdf/ }).getAttribute('href')).toMatch(/\/course-media\/n1$/);
  fireEvent.click(screen.getByRole('button', { name: 'Mark as done' }));
  expect(await screen.findByRole('button', { name: 'Mark as not done' })).toBeInTheDocument();
  expect(api.setLessonDone).toHaveBeenCalledWith('1', true);
  fireEvent.click(screen.getByRole('button', { name: /Lesson 2/ }));
  expect(container.querySelector('iframe')?.getAttribute('src')).toBe('https://www.youtube-nocookie.com/embed/abc123XYZ');
});
