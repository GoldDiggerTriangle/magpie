export const PWA_NAVIGATION_FALLBACK_DENYLIST = [
  /^\/api(?:\/|$)/,
  /^\/admin(?:\/|$)/,
  /^\/media(?:\/|$)/,
  /^\/static(?:\/|$)/
];

export async function unregisterServiceWorkersForAdminRecovery(
  serviceWorker?: Pick<ServiceWorkerContainer, "getRegistrations">
) {
  if (!serviceWorker?.getRegistrations) return 0;

  const registrations = await serviceWorker.getRegistrations();
  await Promise.all(registrations.map((registration) => registration.unregister()));
  return registrations.length;
}
