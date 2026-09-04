export default function CorrectionBlock({ title, children, empty }) {
  const content = children || empty;

  return (
    <div className="rounded-xl bg-slate-50 p-3">
      <p className="text-xs font-bold uppercase text-slate-500">{title}</p>
      <p className="mt-1 whitespace-pre-wrap text-sm text-slate-700">{content}</p>
    </div>
  );
}
