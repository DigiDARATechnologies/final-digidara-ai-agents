import { fireEvent, render, screen } from '@testing-library/react';
import AttachMenu from '../../src/components/AttachMenu';

function setup(props: Partial<React.ComponentProps<typeof AttachMenu>> = {}) {
  const onFiles = jest.fn();
  const onUnsupported = jest.fn();
  const utils = render(
    <AttachMenu enabled documentAccept=".pdf,.doc,.docx,.txt,.zip" onFiles={onFiles} onDisabled={jest.fn()}
      onUnsupported={onUnsupported} {...props} />,
  );
  fireEvent.click(screen.getByRole('button', { name: 'Attach file' }));
  return { ...utils, onFiles, onUnsupported };
}

test('the Resume Builder can pick a zip (its LinkedIn export)', () => {
  const { container, onUnsupported } = setup({ photoAllowed: false });
  const zipInput = container.querySelector('input[accept*=".zip"]') as HTMLInputElement;
  const clicked = jest.spyOn(zipInput, 'click').mockImplementation(() => undefined);
  fireEvent.click(screen.getByText('Upload Zip Folder'));
  expect(clicked).toHaveBeenCalled();
  expect(onUnsupported).not.toHaveBeenCalled();
});

test('a chat that cannot read photos says what it does accept', () => {
  const { onUnsupported } = setup({ photoAllowed: false });
  fireEvent.click(screen.getByText('Upload Photo'));
  expect(onUnsupported).toHaveBeenCalledWith("Photo uploads aren't supported in this chat. You can upload: PDF, DOC, DOCX, TXT, ZIP.");
});

test('a chosen file reaches the chat', () => {
  const { container, onFiles } = setup();
  const docInput = container.querySelector('input[accept=".pdf,.doc,.docx,.txt"]') as HTMLInputElement;
  const file = new File(['resume'], 'resume.pdf', { type: 'application/pdf' });
  fireEvent.change(docInput, { target: { files: [file] } });
  expect(onFiles).toHaveBeenCalledTimes(1);
  expect(onFiles.mock.calls[0][0][0].name).toBe('resume.pdf');
});

test('photos still open the picker where they are read (Capstone)', () => {
  const { container, onUnsupported } = setup({ documentAccept: '.docx,.zip' });
  const photoInput = container.querySelector('input[accept="image/*"]') as HTMLInputElement;
  const clicked = jest.spyOn(photoInput, 'click').mockImplementation(() => undefined);
  fireEvent.click(screen.getByText('Upload Photo'));
  expect(clicked).toHaveBeenCalled();
  expect(onUnsupported).not.toHaveBeenCalled();
});
