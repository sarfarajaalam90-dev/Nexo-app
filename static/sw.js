/* ════════════════════════════════════════════════════════════════
   sw.js — Secret App Service Worker  (FIXED — all push bugs)
   ════════════════════════════════════════════════════════════════ */

const ORIGIN = 'https://secretapp-e3jr.onrender.com';

self.addEventListener('install', e => { self.skipWaiting(); });
self.addEventListener('activate', e => { e.waitUntil(clients.claim()); });

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
  if (data.icon && !data.icon.startsWith('http')) data.icon = ORIGIN + data.icon;
  if (data.badge && !data.badge.startsWith('http')) data.badge = ORIGIN + data.badge;

  // FIX: Always show notification. The old code "returned" (skipped) the
  // notification if ANY window was open and visible — but that means the
  // recipient never saw it if they had any tab open at all. Now we only
  // suppress if the EXACT app tab is in the foreground.
  e.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then(list => {
      const appVisible = list.some(
        c => c.url && c.url.startsWith(ORIGIN) && c.visibilityState === 'visible'
      );
      if (appVisible) {
        // App is open and in foreground — the page JS handles in-app display
        console.log('[SW] App in foreground — skipping push banner');
        return;
      }
      return showNotif(data);
    })
  );
});

function showNotif(data) {
  return self.registration.showNotification(data.title, {
    body              : data.body,
    icon              : data.icon,
    badge             : data.badge,
    tag               : data.tag || 'secret-msg',
    renotify          : true,
    requireInteraction: data.type === 'call',
    data              : data,
    actions           : data.type === 'call'
      ? [{ action: 'answer', title: '✅ Answer' }, { action: 'decline', title: '❌ Decline' }]
      : [{ action: 'open', title: '💬 Open' }]
  });
}

self.addEventListener('notificationclick', e => {
  e.notification.close();
  const action = e.action;
  const data   = e.notification.data || {};
  e.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then(list => {
      for (const c of list) {
        if (c.url && c.url.startsWith(ORIGIN) && 'focus' in c) {
          c.focus();
          if (action && action !== 'decline')
            c.postMessage({ type: 'NOTIFICATION_ACTION', action, callId: data.callId });
          return;
        }
      }
      if (action !== 'decline') return clients.openWindow(ORIGIN);
    })
  );
});

self.addEventListener('sync', e => {
  if (e.tag === 'send-queued-messages') {}
});
