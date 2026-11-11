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
import { VerifyEmailPage } from "@/pages/VerifyEmail";
import { EditListingPage } from "@/pages/EditListing";
import { DriverPage } from "@/pages/Driver";
import { MyListingsPage } from "@/pages/MyListings";
import { ListingDeliveryPage } from "@/pages/ListingDelivery";
import { PayoutAccountPage } from "@/pages/PayoutAccount";
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
import { GetAppPage } from "@/pages/GetApp";
import { PrivacyPage } from "@/pages/Privacy";
import { ProfilePage } from "@/pages/Profile";
import { PublicProfilePage } from "@/pages/PublicProfile";
import { ReelsPage } from "@/pages/Reels";
import { RegisterPage } from "@/pages/Register";
import { ResetPasswordPage } from "@/pages/ResetPassword";
import { WalletPage } from "@/pages/Wallet";
import { RefRoute } from "@/lib/routeRef";

export const router = createBrowserRouter([
  // Public marketing pages — their own PublicShell, not the logged-in app chrome.
  { path: "/", element: <LandingPage /> },
  { path: "/about", element: <AboutPage /> },
  { path: "/how-it-works", element: <HowItWorksPage /> },
  { path: "/contact", element: <ContactPage /> },
  { path: "/privacy", element: <PrivacyPage /> },
  { path: "/get-app", element: <GetAppPage /> },

  {
    element: <AppShell />,
    children: [
      { path: "feed", element: <FeedPage /> },
      { path: "marketplace", element: <MarketplacePage /> },
      { path: "reels", element: <ReelsPage /> },
      { path: "listing/:id", element: <RefRoute kind="listing"><ListingDetailPage /></RefRoute> },
      { path: "listings/:id", element: <RefRoute kind="listing"><ListingDetailPage /></RefRoute> },
      { path: "users/:id", element: <PublicProfilePage /> },
      { path: "merchants/:id", element: <MerchantProfilePage /> },
      { path: "login", element: <LoginPage /> },
      { path: "register", element: <RegisterPage /> },
      { path: "forgot-password", element: <ForgotPasswordPage /> },
      { path: "reset-password", element: <ResetPasswordPage /> },
      {
        element: <RequireAuth />,
        children: [
          { path: "verify-email", element: <VerifyEmailPage /> },
          { path: "listings/:id/edit", element: <EditListingPage /> },
          { path: "listings/:id/delivery", element: <ListingDeliveryPage /> },
          { path: "driver", element: <DriverPage /> },
          { path: "my-listings", element: <MyListingsPage /> },
          { path: "payout-account", element: <PayoutAccountPage /> },
          { path: "listings/new", element: <CreateListingPage /> },
          { path: "reels/new", element: <CreateReelPage /> },
          { path: "orders", element: <OrdersPage /> },
          { path: "order/:id", element: <RefRoute kind="order"><OrderDetailPage /></RefRoute> },
          { path: "orders/:id", element: <RefRoute kind="order"><OrderDetailPage /></RefRoute> },
          { path: "wallet", element: <WalletPage /> },
          {
            path: "messages",
            element: <MessagesLayout />,
            children: [
              { index: true, element: <MessagesIndex /> },
              { path: ":id", element: <RefRoute kind="chat"><ChatPage /></RefRoute> },
            ],
          },
          {
            path: "chat",
            element: <MessagesLayout />,
            children: [{ path: ":id", element: <RefRoute kind="chat"><ChatPage /></RefRoute> }],
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
