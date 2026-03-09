/* Push notification registration */

async function registerPushNotifications() {
  if (!('serviceWorker' in navigator) || !('PushManager' in window)) {
    console.log('Push notifications not supported');
    return;
  }

  try {
    const permission = await Notification.requestPermission();
    if (permission !== 'granted') {
      console.log('Push notification permission denied');
      return;
    }

    const reg = await navigator.serviceWorker.ready;
    let subscription = await reg.pushManager.getSubscription();

    if (!subscription) {
      // Subscribe (would need VAPID keys in production)
      // For now, just log that push is available
      console.log('Push notification registration ready');
    }

    // Store subscription in Supabase (when push Edge Function is deployed)
    if (subscription && supabase) {
      await supabase.from('push_subscriptions').upsert({
        endpoint: subscription.endpoint,
        subscription_data: subscription.toJSON(),
        updated_at: new Date().toISOString(),
      });
    }
  } catch (err) {
    console.error('Push registration error:', err);
  }
}
