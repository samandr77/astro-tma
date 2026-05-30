import { useEntitlementStatus } from "@/hooks/useEntitlement";

/**
 * Compact badge: `✨ Trial · 2д` while a granted trial is active,
 * `✦ Premium` for a paid subscription, nothing for free users.
 */
export function EntitlementBadge() {
  const status = useEntitlementStatus();
  if (!status.isPremium) return null;
  if (status.isTrial) {
    return (
      <span className="entitlement-badge entitlement-badge--trial">
        <span className="entitlement-badge__glyph" aria-hidden="true">✨</span>
        Trial · {status.daysRemaining}д
      </span>
    );
  }
  return (
    <span className="entitlement-badge entitlement-badge--paid">
      <span className="entitlement-badge__glyph" aria-hidden="true">✦</span>
      Premium
    </span>
  );
}
