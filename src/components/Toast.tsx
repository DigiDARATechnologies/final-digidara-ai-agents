interface ToastProps {
  message: string;
  show: boolean;
}

export default function Toast({ message, show }: ToastProps) {
  return <div className={`toast${show ? " show" : ""}`}>{message}</div>;
}
