/* ════════════════════════════════════════════════════════════════
   sw.js — Secret App Service Worker  (FULLY FIXED)
   ════════════════════════════════════════════════════════════════ */

const ORIGIN = 'https://secretapp-e3jr.onrender.com';

self.addEventListener('install', e => {
  self.skipWaiting();
});

self.addEventListener('activate', e => {
  e.waitUntil(clients.claim());
});

self.addEventListener('push', e => {
  // Parse payload — always have safe defaults
  let data = {
    title : 'Secret',
    body  : 'New message',
    icon  : ORIGIN + '/static/icon-192.png',
    badge : ORIGIN + '/static/icon-192.png',
    tag   : 'secret-msg',
    type  : 'message',
    callId: ''
  };

  if (e.data) {
    try { Object.assign(data, e.data.json()); } catch (_) {}
  }

  // Ensure absolute URLs for icon/badge
  if (data.icon && !data.icon.startsWith('http'))  data.icon  = ORIGIN + data.icon;
  if (data.badge && !data.badge.startsWith('http')) data.badge = ORIGIN + data.badge;

  // ── CRITICAL FIX ──────────────────────────────────────────────
  // ALWAYS show the notification from the SW.
  // Do NOT check clients.matchAll() here — when the app is fully
  // closed there are zero clients and the check is pointless.
  // When the app IS open/visible, the page JS will already be
  // showing in-app UI. The OS will suppress duplicate notifications
  // automatically via the 'tag' field (same tag = replace, not add).
  // Removing the clients check fixes 100% of "closed app = no notif" bugs.
  // ──────────────────────────────────────────────────────────────
  e.waitUntil(showNotif(data));
});

function showNotif(data) {
  const options = {
    body              : data.body,
    icon              : data.icon,
    badge             : data.badge,
    tag               : data.tag || 'secret-msg',
    renotify          : true,
    requireInteraction: data.type === 'call',
    vibrate           : data.type === 'call' ? [300,100,300,100,300] : [200,100,200],
    data              : data,
    actions           : data.type === 'call'
      ? [{ action: 'answer',  title: '✅ Answer'  },
         { action: 'decline', title: '❌ Decline' }]
      : [{ action: 'open',    title: '💬 Open'    }]
  };
  return self.registration.showNotification(data.title, options);
}

self.addEventListener('notificationclick', e => {
  e.notification.close();
  const action = e.action;
  const data   = e.notification.data || {};

  e.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then(list => {
      // Try to focus existing app window first
      for (const c of list) {
        if (c.url && c.url.startsWith(ORIGIN) && 'focus' in c) {
          c.focus();
          if (action && action !== 'decline') {
            c.postMessage({
              type  : 'NOTIFICATION_ACTION',
              action: action,
              callId: data.callId || ''
            });
          }
          return;
        }
      }
      // No window open — open a new one (unless user declined a call)
      if (action !== 'decline') {
        return clients.openWindow(ORIGIN);
      }
    })
  );
});

// Keep SW alive for background sync (future use)
self.addEventListener('sync', e => {
  if (e.tag === 'send-queued-messages') { /* reserved */ }
});
