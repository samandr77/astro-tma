import { lazy, Suspense, useEffect, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { AnimatePresence, motion, MotionConfig } from "framer-motion";
import { BottomNav } from "@/components/ui/BottomNav";
import { LoadingSpinner } from "@/components/ui/LoadingSpinner";
import { TrialEndingModal } from "@/components/ui/TrialEndingModal";
import { referralsApi, usersApi } from "@/services/api";
import { useAppStore } from "@/stores/app";
import { useStartParam, useTelegramReady } from "@/hooks/useTelegram";
import { LoadingScreenZodiac } from "@/components/screens/LoadingScreenZodiac";

const Onboarding = lazy(() =>
  import("@/components/screens/Onboarding").then((m) => ({
    default: m.Onboarding,
  })),
);
const Home = lazy(() =>
  import("@/components/screens/Home").then((m) => ({ default: m.Home })),
);
const Discover = lazy(() =>
  import("@/components/screens/Discover").then((m) => ({
    default: m.Discover,
  })),
);
const Horoscopes = lazy(() =>
  import("@/components/screens/Horoscopes").then((m) => ({
    default: m.Horoscopes,
  })),
);
const Premium = lazy(() =>
  import("@/components/screens/Premium").then((m) => ({
    default: m.Premium,
  })),
);
const Tarot = lazy(() =>
  import("@/components/screens/Tarot").then((m) => ({ default: m.Tarot })),
);
const Moon = lazy(() =>
  import("@/components/screens/Moon").then((m) => ({ default: m.Moon })),
);
const Natal = lazy(() =>
  import("@/components/screens/Natal").then((m) => ({ default: m.Natal })),
);
const Mac = lazy(() =>
  import("@/components/screens/Mac").then((m) => ({ default: m.Mac })),
);
const Profile = lazy(() =>
  import("@/components/screens/Profile").then((m) => ({ default: m.Profile })),
);
const Transits = lazy(() =>
  import("@/components/screens/Transits").then((m) => ({
    default: m.Transits,
  })),
);
const Synastry = lazy(() =>
  import("@/components/screens/Synastry").then((m) => ({
    default: m.Synastry,
  })),
);
const SynastryInvite = lazy(() =>
  import("@/components/screens/SynastryInvite").then((m) => ({
    default: m.SynastryInvite,
  })),
);
const Glossary = lazy(() =>
  import("@/components/screens/Glossary").then((m) => ({
    default: m.Glossary,
  })),
);
const GlossaryTerm = lazy(() =>
  import("@/components/screens/GlossaryTerm").then((m) => ({
    default: m.GlossaryTerm,
  })),
);
const News = lazy(() =>
  import("@/components/screens/News").then((m) => ({
    default: m.News,
  })),
);
const NewsDetail = lazy(() =>
  import("@/components/screens/NewsDetail").then((m) => ({
    default: m.NewsDetail,
  })),
);
const Referral = lazy(() =>
  import("@/components/screens/Referral").then((m) => ({
    default: m.Referral,
  })),
);
const Purchases = lazy(() =>
  import("@/components/screens/Purchases").then((m) => ({
    default: m.Purchases,
  })),
);
const DestinyMatrixInfo = lazy(() =>
  import("@/components/screens/DestinyMatrixInfo").then((m) => ({
    default: m.DestinyMatrixInfo,
  })),
);
const DestinyMatrixReading = lazy(() =>
  import("@/components/screens/DestinyMatrixReading").then((m) => ({
    default: m.DestinyMatrixReading,
  })),
);

function SplashScreen() {
  return (
    <motion.div
      style={{ position: "fixed", inset: 0, zIndex: 999 }}
      initial={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.6, ease: "easeInOut" }}
    >
      <LoadingScreenZodiac />
    </motion.div>
  );
}

function RouteFallback() {
  return (
    <div className="screen-container">
      <div className="screen route-fallback-screen">
        <LoadingSpinner message="Открываем раздел..." />
      </div>
    </div>
  );
}

export default function App() {
  const {
    screen,
    setScreen,
    onboardingComplete,
    setOnboardingComplete,
    setUser,
    pendingInviteToken,
    setPendingInviteToken,
  } = useAppStore();
  const [ready, setReady] = useState(false);
  const [synced, setSynced] = useState(false);
  useTelegramReady();
  const startParam = useStartParam();
  const [inviteHandled, setInviteHandled] = useState(false);
  const [referralHandled, setReferralHandled] = useState(false);
  const queryClient = useQueryClient();

  const syncUser = useMutation({
    mutationFn: usersApi.upsertMe,
    onSuccess: (u) => {
      setUser(u);
      // If user has no gender/sign — they were deleted or never completed onboarding
      if (!u.gender && !u.sun_sign) {
        setOnboardingComplete(false);
      }
      setSynced(true);
    },
    onError: () => {
      setSynced(true);
    },
  });

  useEffect(() => {
    syncUser.mutate();
    const timer = setTimeout(() => setReady(true), 5000);
    return () => clearTimeout(timer);
  }, []);

  // Capture syn_<token> from start_param into the persisted store as soon as
  // we see it — before splash, before onboarding gate. The token survives a
  // mid-onboarding reload that way.
  useEffect(() => {
    if (startParam?.startsWith("syn_")) {
      const token = startParam.slice(4);
      if (token && token !== pendingInviteToken) {
        setPendingInviteToken(token);
      }
    }
  }, [startParam, pendingInviteToken, setPendingInviteToken]);

  // Referral deep-link: redeem the code once `users.me` has synced so the
  // user row already exists on the backend. Idempotent — backend silently
  // ignores a code that was already applied.
  useEffect(() => {
    if (referralHandled || !synced) return;
    if (!startParam?.startsWith("ref_")) return;
    const code = startParam.slice(4);
    if (!code) {
      setReferralHandled(true);
      return;
    }
    setReferralHandled(true);
    referralsApi
      .apply(code)
      .then((result) => {
        if (result.success) {
          queryClient.invalidateQueries({ queryKey: ["my-purchases"] });
          queryClient.invalidateQueries({ queryKey: ["referral-me"] });
        }
      })
      .catch(() => {
        /* silent — code may already be applied */
      });
  }, [startParam, synced, referralHandled, queryClient]);

  // After both splash timer and sync are done, route the onboarded user.
  // If they have a pending invite waiting, jump straight to the invite
  // landing page; otherwise the usual home screen.
  useEffect(() => {
    if (!ready || !synced || !onboardingComplete) return;
    if (screen !== "onboarding") return;
    setScreen(pendingInviteToken ? "synastry_invite" : "home");
  }, [
    ready,
    synced,
    onboardingComplete,
    screen,
    pendingInviteToken,
    setScreen,
  ]);

  // Already-onboarded user opening a fresh invite link: jump to the invite
  // page immediately. Non-onboarded users wait until onboarding finishes
  // (the effect above handles that branch).
  useEffect(() => {
    if (inviteHandled || !ready || !synced || !onboardingComplete) return;
    if (pendingInviteToken) {
      setScreen("synastry_invite");
      setInviteHandled(true);
    }
  }, [
    pendingInviteToken,
    ready,
    synced,
    onboardingComplete,
    inviteHandled,
    setScreen,
  ]);

  const showSplash = !ready || !synced;
  const showNav = !showSplash && screen !== "onboarding";

  if (showSplash) {
    return (
      <div className="app">
        <AnimatePresence mode="wait">
          <SplashScreen />
        </AnimatePresence>
      </div>
    );
  }

  return (
    <MotionConfig reducedMotion="user">
      <div className="app">
        <Suspense fallback={<RouteFallback />}>
          <motion.div
            key={screen}
            className="screen-container"
            initial={false}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.16, ease: "easeOut" }}
          >
            {screen === "onboarding" && <Onboarding />}
            {screen === "home" && <Home />}
            {screen === "horoscopes" && <Horoscopes />}
            {screen === "discover" && <Discover />}
            {screen === "premium" && <Premium />}
            {screen === "tarot" && <Tarot />}
            {screen === "moon" && <Moon />}
            {screen === "natal" && <Natal />}
            {screen === "mac" && <Mac />}
            {screen === "profile" && <Profile />}
            {screen === "transits" && <Transits />}
            {screen === "synastry" && <Synastry />}
            {screen === "synastry_invite" && <SynastryInvite />}
            {screen === "glossary" && <Glossary />}
            {screen === "glossary_term" && <GlossaryTerm />}
            {screen === "news" && <News />}
            {screen === "news_detail" && <NewsDetail />}
            {screen === "referral" && <Referral />}
            {screen === "purchases" && <Purchases />}
            {screen === "destiny_matrix_info" && <DestinyMatrixInfo />}
            {screen === "destiny_matrix_reading" && <DestinyMatrixReading />}
          </motion.div>
        </Suspense>

        {showNav && <BottomNav />}
        {synced && onboardingComplete && <TrialEndingModal />}
      </div>
    </MotionConfig>
  );
}
