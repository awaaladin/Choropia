import { createBrowserRouter } from "react-router";
import { AppShell } from "@/components/AppShell";
import { RequireAuth } from "@/components/RequireAuth";
import { AboutPage } from "@/pages/About";
import { ApplyMerchantPage } from "@/pages/ApplyMerchant";
import { ChatPage } from "@/pages/Chat";
import { ContactPage } from "@/pages/Contact";
import { CreateListingPage } from "@/pages/CreateListing";
import { CreateReelPage } from "@/pages/CreateReel";
import { FeedPage } from "@/pages/Feed";
import { ForgotPasswordPage } from "@/pages/ForgotPassword";
import { HowItWorksPage } from "@/pages/HowItWorks";
import { LandingPage } from "@/pages/Landing";
import { ListingDetailPage } from "@/pages/ListingDetail";
import { LoginPage } from "@/pages/Login";
import { MarketplacePage } from "@/pages/Marketplace";
import { MerchantProfilePage } from "@/pages/MerchantProfile";
import { MessagesLayout, MessagesIndex } from "@/pages/Messages";
import { NotFoundPage } from "@/pages/NotFound";
import { NotificationsPage } from "@/pages/Notifications";
import { OrderDetailPage } from "@/pages/OrderDetail";
import { OrdersPage } from "@/pages/Orders";
import { PrivacyPage } from "@/pages/Privacy";
import { ProfilePage } from "@/pages/Profile";
import { ReelsPage } from "@/pages/Reels";
import { RegisterPage } from "@/pages/Register";
import { ResetPasswordPage } from "@/pages/ResetPassword";
import { WalletPage } from "@/pages/Wallet";

export const router = createBrowserRouter([
  // Public marketing pages — their own PublicShell, not the logged-in app chrome.
  { path: "/", element: <LandingPage /> },
  { path: "/about", element: <AboutPage /> },
  { path: "/how-it-works", element: <HowItWorksPage /> },
  { path: "/contact", element: <ContactPage /> },
  { path: "/privacy", element: <PrivacyPage /> },

  {
    element: <AppShell />,
    children: [
      { path: "feed", element: <FeedPage /> },
      { path: "marketplace", element: <MarketplacePage /> },
      { path: "reels", element: <ReelsPage /> },
      { path: "listings/:id", element: <ListingDetailPage /> },
      { path: "merchants/:id", element: <MerchantProfilePage /> },
      { path: "login", element: <LoginPage /> },
      { path: "register", element: <RegisterPage /> },
      { path: "forgot-password", element: <ForgotPasswordPage /> },
      { path: "reset-password", element: <ResetPasswordPage /> },
      {
        element: <RequireAuth />,
        children: [
          { path: "listings/new", element: <CreateListingPage /> },
          { path: "reels/new", element: <CreateReelPage /> },
          { path: "orders", element: <OrdersPage /> },
          { path: "orders/:id", element: <OrderDetailPage /> },
          { path: "wallet", element: <WalletPage /> },
          {
            path: "messages",
            element: <MessagesLayout />,
            children: [
              { index: true, element: <MessagesIndex /> },
              { path: ":id", element: <ChatPage /> },
            ],
          },
          { path: "notifications", element: <NotificationsPage /> },
          { path: "profile", element: <ProfilePage /> },
          { path: "merchants/apply", element: <ApplyMerchantPage /> },
        ],
      },
      { path: "*", element: <NotFoundPage /> },
    ],
  },
]);
