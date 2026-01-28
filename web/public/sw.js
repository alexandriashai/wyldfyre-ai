// Wyld Fyre AI Service Worker
const CACHE_NAME = 'wyld-fyre-v17';
const OFFLINE_URL = '/offline';

// Detect platform (approximation from user agent in fetch requests)
let isIOS = false;
let isAndroid = false;

// Assets to cache immediately on install
const PRECACHE_ASSETS = [
  '/',
  '/offline',
  '/manifest.json',
  '/icons/icon.svg',
  '/icons/icon-192x192.png',
  '/icons/icon-512x512.png',
  '/icons/maskable-icon-192x192.png',
  '/icons/maskable-icon-512x512.png',
];

// iOS-specific splash screens to cache
const IOS_SPLASH_SCREENS = [
  '/splash/apple-splash-2048-2732.png',
  '/splash/apple-splash-1668-2388.png',
  '/splash/apple-splash-1536-2048.png',
  '/splash/apple-splash-1125-2436.png',
  '/splash/apple-splash-1242-2688.png',
  '/splash/apple-splash-828-1792.png',
  '/splash/apple-splash-1170-2532.png',
  '/splash/apple-splash-1179-2556.png',
  '/splash/apple-splash-1284-2778.png',
  '/splash/apple-splash-1290-2796.png',
];

// Install event - precache essential assets
self.addEventListener('install', (event) => {
  event.waitUntil(
    (async () => {
      const cache = await caches.open(CACHE_NAME);
      console.log('[SW] Precaching assets');

      // Cache essential assets first
      await cache.addAll(PRECACHE_ASSETS);

      // Cache iOS splash screens in the background (non-blocking)
      // These are optional - if they fail, the app still works
      try {
        await Promise.allSettled(
          IOS_SPLASH_SCREENS.map(url =>
            cache.add(url).catch(err => {
              console.log('[SW] Optional splash screen not found:', url);
            })
          )
        );
      } catch (e) {
        console.log('[SW] Some splash screens not cached (optional)');
      }
    })()
  );
  // Don't auto-activate - wait for SKIP_WAITING message
});

// Activate event - clean up old caches
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((cacheNames) => {
      return Promise.all(
        cacheNames
          .filter((name) => name.startsWith('wyld-fyre-') && name !== CACHE_NAME)
          .map((name) => {
            console.log('[SW] Deleting old cache:', name);
            return caches.delete(name);
          })
      );
    })
  );
  // Take control immediately
  self.clients.claim();
});

// Handle messages from the client
self.addEventListener('message', (event) => {
  if (!event.data) return;

  switch (event.data.type) {
    case 'SKIP_WAITING':
      self.skipWaiting();
      break;

    case 'SET_PLATFORM':
      // Client can inform us of the platform
      isIOS = event.data.isIOS || false;
      isAndroid = event.data.isAndroid || false;
      console.log('[SW] Platform set:', { isIOS, isAndroid });
      break;

    case 'CACHE_URLS':
      // Client can request specific URLs to be cached
      if (event.data.urls && Array.isArray(event.data.urls)) {
        event.waitUntil(
          caches.open(CACHE_NAME).then(cache => {
            return Promise.allSettled(
              event.data.urls.map(url => cache.add(url).catch(() => {}))
            );
          })
        );
      }
      break;

    case 'CLEAR_CACHE':
      // Client can request cache to be cleared
      event.waitUntil(
        caches.delete(CACHE_NAME).then(() => {
          console.log('[SW] Cache cleared');
        })
      );
      break;

    case 'GET_VERSION':
      // Client can request the current cache version
      event.ports[0]?.postMessage({ version: CACHE_NAME });
      break;

    case 'SHOW_NOTIFICATION':
      // Client can request a notification to be shown
      if (event.data.notification) {
        const { title, options } = event.data.notification;
        event.waitUntil(
          self.registration.showNotification(title, options)
        );
      }
      break;
  }
});

// Fetch event - network first, fallback to cache
self.addEventListener('fetch', (event) => {
  // Skip non-GET requests
  if (event.request.method !== 'GET') {
    return;
  }

  // Skip API requests - always go to network
  if (event.request.url.includes('/api/')) {
    return;
  }

  // Skip WebSocket requests
  if (event.request.url.includes('ws://') || event.request.url.includes('wss://')) {
    return;
  }

  // Skip chrome-extension and other non-http(s) requests
  if (!event.request.url.startsWith('http')) {
    return;
  }

  event.respondWith(
    fetch(event.request)
      .then((response) => {
        // Clone the response before caching
        const responseClone = response.clone();

        // Only cache successful responses
        if (response.status === 200) {
          caches.open(CACHE_NAME).then((cache) => {
            cache.put(event.request, responseClone);
          });
        }

        return response;
      })
      .catch(async () => {
        // Network failed, try cache
        const cachedResponse = await caches.match(event.request);
        if (cachedResponse) {
          return cachedResponse;
        }

        // If it's a navigation request, return offline page
        if (event.request.mode === 'navigate') {
          const offlineResponse = await caches.match(OFFLINE_URL);
          if (offlineResponse) {
            return offlineResponse;
          }
          // Fallback to root if offline page not cached
          const rootResponse = await caches.match('/');
          if (rootResponse) {
            return rootResponse;
          }
        }

        // Return a simple offline response for other requests
        return new Response('Offline', {
          status: 503,
          statusText: 'Service Unavailable',
          headers: { 'Content-Type': 'text/plain' },
        });
      })
  );
});

// Handle push notifications
self.addEventListener('push', (event) => {
  if (!event.data) return;

  let data;
  try {
    data = event.data.json();
  } catch (e) {
    data = { body: event.data.text() };
  }

  // Base notification options
  const options = {
    body: data.body || 'New notification from Wyld',
    icon: '/icons/icon-192x192.png',
    badge: '/icons/icon-72x72.png',
    tag: data.tag || 'wyld-fyre-notification',
    renotify: data.renotify !== false,
    requireInteraction: data.requireInteraction || false,
    silent: data.silent || false,
    data: {
      url: data.url || '/',
      timestamp: Date.now(),
      type: data.type || 'general',
      conversationId: data.conversationId,
      agentName: data.agentName,
    },
  };

  // Platform-specific adjustments
  // iOS Safari doesn't support vibrate, actions, or images in the same way
  // Only add these for non-iOS platforms
  if (!isIOS) {
    options.vibrate = data.vibrate || [100, 50, 100];
    options.image = data.image;

    // Add notification actions for Android/desktop
    if (data.type === 'message') {
      options.actions = data.actions || [
        { action: 'reply', title: 'Reply', icon: '/icons/reply.png' },
        { action: 'dismiss', title: 'Dismiss', icon: '/icons/dismiss.png' },
      ];
    } else if (data.type === 'agent_status') {
      options.actions = data.actions || [
        { action: 'view', title: 'View Details', icon: '/icons/view.png' },
      ];
    } else if (data.type === 'task') {
      options.actions = data.actions || [
        { action: 'view', title: 'View Task', icon: '/icons/task.png' },
      ];
    }
  }

  event.waitUntil(
    self.registration.showNotification(data.title || 'Wyld Fyre AI', options)
  );
});

// Handle notification clicks
self.addEventListener('notificationclick', (event) => {
  event.notification.close();

  const notificationData = event.notification.data || {};
  let urlToOpen = notificationData.url || '/';

  // Handle specific actions
  if (event.action) {
    switch (event.action) {
      case 'reply':
        // Open conversation with reply focus
        if (notificationData.conversationId) {
          urlToOpen = `/chat/${notificationData.conversationId}?focus=reply`;
        }
        break;

      case 'view':
        // Already have the URL from notification data
        break;

      case 'dismiss':
        // Just close the notification (already done above)
        return;

      default:
        // Unknown action, use default URL
        break;
    }
  }

  event.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then((clientList) => {
      // Check if a window is already open
      for (const client of clientList) {
        const clientUrl = new URL(client.url);
        if (clientUrl.pathname === urlToOpen || clientUrl.pathname.startsWith(urlToOpen.split('?')[0])) {
          // Post message to existing client about the notification click
          client.postMessage({
            type: 'NOTIFICATION_CLICK',
            action: event.action,
            data: notificationData,
          });
          return client.focus();
        }
      }

      // Check if any window is open and navigate it
      if (clientList.length > 0) {
        const client = clientList[0];
        client.postMessage({
          type: 'NOTIFICATION_CLICK',
          action: event.action,
          data: notificationData,
          navigate: urlToOpen,
        });
        return client.focus();
      }

      // Otherwise open a new window
      if (clients.openWindow) {
        return clients.openWindow(urlToOpen);
      }
    })
  );
});

// Handle notification close (user dismissed)
self.addEventListener('notificationclose', (event) => {
  // Track dismissed notifications for analytics
  const notificationData = event.notification.data || {};
  console.log('[SW] Notification dismissed:', notificationData.type);
});

// Background sync for offline actions (future use)
self.addEventListener('sync', (event) => {
  if (event.tag === 'sync-messages') {
    event.waitUntil(syncMessages());
  }
});

async function syncMessages() {
  // Future: Sync offline messages when back online
  console.log('[SW] Syncing messages...');
}

// Periodic background sync (future use)
self.addEventListener('periodicsync', (event) => {
  if (event.tag === 'check-updates') {
    event.waitUntil(checkForUpdates());
  }
});

async function checkForUpdates() {
  // Future: Check for app updates
  console.log('[SW] Checking for updates...');
}

// Handle share target (Android Web Share Target API)
// When content is shared to the PWA, this handles the incoming data
self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url);

  // Handle share target POST requests
  if (url.pathname === '/share-target' && event.request.method === 'POST') {
    event.respondWith(
      (async () => {
        const formData = await event.request.formData();
        const title = formData.get('title') || '';
        const text = formData.get('text') || '';
        const url = formData.get('url') || '';

        // Combine shared content into a message
        const sharedContent = [title, text, url].filter(Boolean).join('\n');

        // Store the shared content temporarily
        const cache = await caches.open(CACHE_NAME);
        await cache.put(
          new Request('/_shared-content'),
          new Response(JSON.stringify({
            content: sharedContent,
            timestamp: Date.now(),
          }), {
            headers: { 'Content-Type': 'application/json' }
          })
        );

        // Redirect to chat with share parameter
        return Response.redirect('/chat?shared=true', 303);
      })()
    );
    return;
  }
}, { passive: true });

// Handle protocol URLs (web+wyldfyre://)
// These are registered in the manifest and handled here
self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url);

  // Check if this is a protocol handler request
  if (url.searchParams.has('web+wyldfyre')) {
    const protocolUrl = url.searchParams.get('web+wyldfyre');

    if (protocolUrl) {
      try {
        const parsedUrl = new URL(protocolUrl);
        const path = parsedUrl.pathname;

        // Route based on the protocol path
        let redirectPath = '/';

        if (path.startsWith('/chat/')) {
          redirectPath = path;
        } else if (path.startsWith('/agent/')) {
          redirectPath = `/agents${path.replace('/agent', '')}`;
        } else if (path === '/new') {
          redirectPath = '/chat?new=true';
        }

        event.respondWith(Response.redirect(redirectPath, 303));
        return;
      } catch (e) {
        console.error('[SW] Invalid protocol URL:', protocolUrl);
      }
    }
  }
}, { passive: true });

// Utility: Get shared content (called by client)
async function getSharedContent() {
  try {
    const cache = await caches.open(CACHE_NAME);
    const response = await cache.match('/_shared-content');
    if (response) {
      const data = await response.json();
      // Clear the shared content after reading
      await cache.delete('/_shared-content');

      // Only return if less than 5 minutes old
      if (Date.now() - data.timestamp < 5 * 60 * 1000) {
        return data.content;
      }
    }
  } catch (e) {
    console.error('[SW] Error getting shared content:', e);
  }
  return null;
}

// Handle GET_SHARED_CONTENT message from client
self.addEventListener('message', (event) => {
  if (event.data && event.data.type === 'GET_SHARED_CONTENT') {
    event.waitUntil(
      getSharedContent().then(content => {
        event.ports[0]?.postMessage({ content });
      })
    );
  }
});

// Badge API support (show unread count on app icon)
async function updateBadge(count) {
  if ('setAppBadge' in navigator) {
    try {
      if (count > 0) {
        await navigator.setAppBadge(count);
      } else {
        await navigator.clearAppBadge();
      }
    } catch (e) {
      console.error('[SW] Error updating badge:', e);
    }
  }
}

// Listen for badge update messages
self.addEventListener('message', (event) => {
  if (event.data && event.data.type === 'UPDATE_BADGE') {
    updateBadge(event.data.count || 0);
  }
});

console.log('[SW] Wyld Fyre Service Worker loaded - version:', CACHE_NAME);
