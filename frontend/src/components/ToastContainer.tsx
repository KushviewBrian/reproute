import { useEffect, useState } from "react";
import { toast as toastLib, type ToastPayload } from "../lib/toast";

const MAX_VISIBLE = 3;
const AUTO_DISMISS_MS = 2500;

export function ToastContainer() {
  const [toasts, setToasts] = useState<ToastPayload[]>([]);
  const [dismissing, setDismissing] = useState<Set<string>>(new Set());

  useEffect(() => {
    function onToast(e: Event) {
      const payload = (e as CustomEvent<ToastPayload>).detail;
      setToasts((prev) => {
        const next = [payload, ...prev].slice(0, MAX_VISIBLE + 2);
        return next;
      });
      setTimeout(() => dismiss(payload.id), AUTO_DISMISS_MS);
    }
    window.addEventListener(toastLib.EVENT, onToast);
    return () => window.removeEventListener(toastLib.EVENT, onToast);
  }, []);

  function dismiss(id: string) {
    setDismissing((prev) => new Set([...prev, id]));
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
      setDismissing((prev) => {
        const next = new Set(prev);
        next.delete(id);
        return next;
      });
    }, 220);
  }

  const visible = toasts.slice(0, MAX_VISIBLE);

  return (
    <div id="toast-root" aria-live="polite" aria-atomic="false">
      {visible.map((t) => (
        <div
          key={t.id}
          className={`toast toast-${t.type}${dismissing.has(t.id) ? " toast-out" : ""}`}
          role="status"
        >
          <span>{t.message}</span>
          <button
            className="toast-dismiss"
            aria-label="Dismiss notification"
            onClick={() => dismiss(t.id)}
          >
            ×
          </button>
        </div>
      ))}
    </div>
  );
}
