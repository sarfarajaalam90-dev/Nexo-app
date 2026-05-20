/* ════════════════════════════════════════════════════════════════
   sw.js — Secret App Service Worker
   Served at: https://yourdomain.com/sw.js  (root, same origin)
   ════════════════════════════════════════════════════════════════ */

self.addEventListener('install', e => { self.skipWaiting(); });
self.addEventListener('activate', e => { e.waitUntil(clients.claim()); });

/* ── Push: receive and show notification ──────────────────────── */
self.addEventListener('push', e => {
  let data = {
    title : 'Secret',
    body  : 'New message',
    icon  : '/static/icon-192.png',
    badge : '/static/icon-192.png',
    tag   : 'secret-msg',
    type  : 'message'
  };
  if (e.data) {
    try { Object.assign(data, e.data.json()); } catch (_) {}
  }

  e.waitUntil(
    // Check if the app is open AND the user is already viewing that chat
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then(list => {
      for (const c of list) {
        // If the page is visible and focused, skip the notification
        // (the in-page message listener already shows the message live)
        if (c.visibilityState === 'visible') {
          console.log('[SW] App is in foreground — skipping notification');
          return; // don't show notification when app is open and visible
        }
      }
      // App is closed, minimized, or in background — show the notification
      return self.registration.showNotification(data.title, {
        body           : data.body,
        icon           : data.icon  || '/static/icon-192.png',
        badge          : data.badge || '/static/icon-192.png',
        tag            : data.tag   || 'secret-msg',
        renotify       : true,
        requireInteraction: data.type === 'call', // keep call notifications on screen
        data           : data,
        actions        : data.type === 'call'
          ? [
              { action: 'answer',  title: '✅ Answer' },
              { action: 'decline', title: '❌ Decline' }
            ]
          : [{ action: 'open', title: '💬 Open' }]
      });
    })
  );
});

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
        return clients.openWindow(self.location.origin);
      }
    })
  );
});

/* ── Background sync stub ─────────────────────────────────────── */
self.addEventListener('sync', e => {
  if (e.tag === 'send-queued-messages') {}
});
