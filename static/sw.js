/* ════════════════════════════════════════════════════════════════
   sw.js — Secret App Service Worker  (FIXED v5)

   ROOT CAUSE FIXES:
   1. Removed skipWaiting() from install — it was killing an active
      SW mid-push, dropping the notification on closed-app scenarios.
   2. Unique notification tag per sender so Android never silently
      collapses/replaces an incoming notification.
   3. Added requireInteraction:false default so Android doesn't
      suppress non-call notifications.
   ════════════════════════════════════════════════════════════════ */

const ORIGIN = 'https://secretapp-e3jr.onrender.com';
const SW_VERSION = 'v5';

self.addEventListener('install', e => {
  console.log('[SW] Installing', SW_VERSION);
  // ⚠️ DO NOT call self.skipWaiting() here.
  // If a push arrives while a new SW is installing, skipWaiting()
  // destroys the old SW before it can show the notification.
  // The new SW takes over naturally on next page load.
});

self.addEventListener('activate', e => {
  console.log('[SW] Activating', SW_VERSION);
  // claim() is fine in activate — by this point any in-flight push
  // on the old SW has already been handled.
  e.waitUntil(clients.claim());
});

// ── Push event — ALWAYS show notification ────────────────────────
self.addEventListener('push', e => {
  console.log('[SW] Push received', SW_VERSION);

  let data = {
    title    : 'Secret',
    body     : 'New message',
    icon     : ORIGIN + '/static/icon-192.png',
    badge    : ORIGIN + '/static/icon-192.png',
    tag      : 'secret-msg-' + Date.now(),   // unique tag = never collapsed
    type     : 'message',
    callId   : '',
    senderUid: ''
  };

  if (e.data) {
    try {
      Object.assign(data, e.data.json());
    } catch (_) {
      data.body = e.data.text() || data.body;
    }
  }

  // Use sender-based tag so messages from the same person update
  // each other but don't suppress. Fall back to timestamp tag.
  if (data.senderUid) {
    data.tag = data.type === 'call'
      ? 'secret-call-' + data.senderUid
      : 'secret-msg-'  + data.senderUid;
  }

  // Ensure absolute URLs
  if (data.icon  && !data.icon.startsWith('http'))  data.icon  = ORIGIN + data.icon;
  if (data.badge && !data.badge.startsWith('http')) data.badge = ORIGIN + data.badge;

  const isCall = data.type === 'call';

  const notifOptions = {
    body              : data.body,
    icon              : data.icon,
    badge             : data.badge,
    tag               : data.tag,
    renotify          : true,
    requireInteraction: isCall,      // only calls stay persistent
    silent            : false,       // explicitly NOT silent
    vibrate           : isCall
                          ? [300, 100, 300, 100, 300]
                          : [200, 100, 200],
    data              : data,
    actions           : isCall
      ? [{ action: 'answer',  title: '✅ Answer'  },
         { action: 'decline', title: '❌ Decline' }]
      : [{ action: 'open',    title: '💬 Open'    }]
  };

  // e.waitUntil keeps the SW alive until the notification is shown
  e.waitUntil(
    self.registration.showNotification(data.title, notifOptions)
      .then(() => console.log('[SW] Notification shown:', data.tag))
      .catch(err => console.error('[SW] showNotification failed:', err))
  );
});

// ── Notification click ───────────────────────────────────────────
self.addEventListener('notificationclick', e => {
  e.notification.close();
  const action = e.action;
  const data   = e.notification.data || {};

  e.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then(list => {
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
      if (action !== 'decline') {
        return clients.openWindow(ORIGIN);
      }
    })
  );
});

// ── Background sync (reserved) ───────────────────────────────────
self.addEventListener('sync', e => {
  if (e.tag === 'send-queued-messages') { /* reserved */ }
});
