import { useEffect } from "react";

export function useNotice(message, tone = "success") {
  useEffect(() => {
    if (message) window.dispatchEvent(new CustomEvent("udm-notice", { detail: { message, tone } }));
  }, [message, tone]);
}
