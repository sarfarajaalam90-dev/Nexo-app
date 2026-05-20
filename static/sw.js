/* ════════════════════════════════════════════════════════════════
   sw.js — Secret App Service Worker
   Served at: https://secretapp-j41t.onrender.com/sw.js
   ════════════════════════════════════════════════════════════════ */

const ORIGIN = 'https://secretapp-j41t.onrender.com';

self.addEventListener('install', e => { self.skipWaiting(); });
self.addEventListener('activate', e => { e.waitUntil(clients.claim()); });

/* ── Push: receive and show notification ──────────────────────── */
self.addEventListener('push', e => {
  let data = {
    title : 'Secret',
    body  : 'New message',
    icon  : ORIGIN + '/static/icon-192.png',
    badge : ORIGIN + '/static/icon-192.png',
    tag   : 'secret-msg',
    type  : 'message'
  };
  if (e.data) {
    try { Object.assign(data, e.data.json()); } catch (_) {}
  }

  // Always use absolute URLs for icon/badge — required on Android/mobile Chrome
  if (data.icon && !data.icon.startsWith('http')) data.icon = ORIGIN + data.icon;
  if (data.badge && !data.badge.startsWith('http')) data.badge = ORIGIN + data.badge;

  e.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then(list => {

      // If app is fully closed — list is empty — always show notification
      if (list.length === 0) {
        return showNotif(data);
      }

      // If any window is visible (foreground) — skip notification
      // The live Firestore listener already shows the message in real time
      for (const c of list) {
        if (c.visibilityState === 'visible') {
          console.log('[SW] App in foreground — skipping notification');
          return;
        }
      }

      // App exists but is minimized/backgrounded — show notification
      return showNotif(data);
    })
  );
});

function showNotif(data) {
  return self.registration.showNotification(data.title, {
    body              : data.body,
    icon              : data.icon,
    badge             : data.badge,
    tag               : data.tag  || 'secret-msg',
    renotify          : true,
    requireInteraction: data.type === 'call',
    data              : data,
    actions           : data.type === 'call'
      ? [
          { action: 'answer',  title: '✅ Answer' },
          { action: 'decline', title: '❌ Decline' }
        ]
      : [{ action: 'open', title: '💬 Open' }]
  });
}

/* ── Notification click ───────────────────────────────────────── */
self.addEventListener('notificationclick', e => {
  e.notification.close();
  const action = e.action;
  const data   = e.notification.data || {};

  e.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then(list => {
      for (const c of list) {
        if (c.url && 'focus' in c) {
          c.focus();
          if (action && action !== 'decline') {
            c.postMessage({ type: 'NOTIFICATION_ACTION', action, callId: data.callId });
          }
          return;
        }
      }
      if (action !== 'decline') {
        return clients.openWindow(ORIGIN);
      }
    })
  );
});

self.addEventListener('sync', e => {
  if (e.tag === 'send-queued-messages') {}
});
