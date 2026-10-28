/** Course helpers with no network: video embed links and file sizes. */
/** A YouTube or Vimeo page link as its embeddable player URL. */
export function embedUrl(link: string): string | null {
  const youtube = link.match(/(?:youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/embed\/)([\w-]{6,})/);
  if (youtube) return `https://www.youtube-nocookie.com/embed/${youtube[1]}`;
  const vimeo = link.match(/vimeo\.com\/(?:video\/)?(\d+)/);
  if (vimeo) return `https://player.vimeo.com/video/${vimeo[1]}`;
  return null;
}

export function fileSize(bytes: number): string {
  if (bytes >= 1024 ** 3) return `${(bytes / 1024 ** 3).toFixed(1)} GB`;
  if (bytes >= 1024 ** 2) return `${(bytes / 1024 ** 2).toFixed(1)} MB`;
  return `${Math.max(1, Math.round(bytes / 1024))} KB`;
}
