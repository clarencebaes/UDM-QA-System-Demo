import { useEffect, useState } from "react";

export default function NotificationCenter() {
  const [notices, setNotices] = useState([]);
  useEffect(() => {
    const timers = new Set();
    function receive(event) {
      const item = { ...event.detail, id: crypto.randomUUID() };
      setNotices(previous => [...previous.filter(n => n.message !== item.message), item].slice(-3));
      const timer = setTimeout(() => {
        setNotices(previous => previous.filter(n => n.id !== item.id));
        timers.delete(timer);
      }, 9000);
      timers.add(timer);
    }
    window.addEventListener("udm-notice", receive);
    return () => { window.removeEventListener("udm-notice", receive); timers.forEach(clearTimeout); };
  }, []);
  return <div className="notification-stack" aria-label="Notifications">{notices.map(n => <div key={n.id} className={`notification-toast notice-${n.tone}`} role={n.tone === "error" ? "alert" : "status"}><span>{n.message}</span><button type="button" aria-label="Dismiss notification" onClick={() => setNotices(previous => previous.filter(item => item.id !== n.id))}>×</button></div>)}</div>;
}
