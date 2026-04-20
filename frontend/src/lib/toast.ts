type ToastType = "success" | "error" | "info" | "warn";

const EVENT = "reproute:toast";

export interface ToastPayload {
  id: string;
  type: ToastType;
  message: string;
}

function emit(type: ToastType, message: string) {
  const payload: ToastPayload = { id: `${Date.now()}-${Math.random()}`, type, message };
  window.dispatchEvent(new CustomEvent(EVENT, { detail: payload }));
}

export const toast = {
  success: (message: string) => emit("success", message),
  error:   (message: string) => emit("error",   message),
  info:    (message: string) => emit("info",     message),
  warn:    (message: string) => emit("warn",     message),
  EVENT,
};
