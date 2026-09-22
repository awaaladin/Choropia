package com.choropia.app.navigation

import androidx.compose.runtime.Composable
import androidx.navigation.NavHostController
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import androidx.navigation.navArgument
import androidx.navigation.NavType
import com.choropia.app.data.repository.ChoropiaRepository
import com.choropia.app.ui.screens.applymerchant.ApplyMerchantScreen
import com.choropia.app.ui.screens.chat.ChatScreen
import com.choropia.app.ui.screens.createlisting.CreateListingScreen
import com.choropia.app.ui.screens.feed.FeedScreen
import com.choropia.app.ui.screens.listingdetail.ListingDetailScreen
import com.choropia.app.ui.screens.login.LoginScreen
import com.choropia.app.ui.screens.marketplace.MarketplaceScreen
import com.choropia.app.ui.screens.merchant.MerchantProfileScreen
import com.choropia.app.ui.screens.notifications.NotificationsScreen
import com.choropia.app.ui.screens.orderdetail.OrderDetailScreen
import com.choropia.app.ui.screens.orders.OrdersScreen
import com.choropia.app.ui.screens.profile.ProfileScreen
import com.choropia.app.ui.screens.register.RegisterScreen

object Routes {
    const val FEED = "feed"
    const val MARKETPLACE = "marketplace"
    const val LOGIN = "login"
    const val REGISTER = "register"
    const val ORDERS = "orders"
    const val PROFILE = "profile"
    const val NOTIFICATIONS = "notifications"
    const val CREATE_LISTING = "listing/create"
    const val LISTING_DETAIL = "listing/{listingId}"
    const val CHAT = "chat/{conversationId}"
    const val ORDER_DETAIL = "order/{orderId}"
    const val MERCHANT_PROFILE = "merchant/{merchantId}"
    const val APPLY_MERCHANT = "merchant/apply"

    fun listingDetail(id: Int) = "listing/$id"
    fun chat(conversationId: Int) = "chat/$conversationId"
    fun orderDetail(id: Int) = "order/$id"
    fun merchantProfile(id: Int) = "merchant/$id"
}

@Composable
fun ChoropiaNavHost(repository: ChoropiaRepository, navController: NavHostController = rememberNavController()) {
    NavHost(navController = navController, startDestination = Routes.FEED) {
        composable(Routes.FEED) {
            FeedScreen(
                repository = repository,
                onOpenListing = { navController.navigate(Routes.listingDetail(it)) },
                onNeedsLogin = { navController.navigate(Routes.LOGIN) },
                onOpenMarketplace = { navController.navigate(Routes.MARKETPLACE) },
                onOpenNotifications = { navController.navigate(Routes.NOTIFICATIONS) },
                onOpenOrders = { navController.navigate(Routes.ORDERS) },
                onOpenProfile = { navController.navigate(Routes.PROFILE) },
            )
        }
        composable(Routes.MARKETPLACE) {
            MarketplaceScreen(
                repository = repository,
                onOpenListing = { navController.navigate(Routes.listingDetail(it)) },
                onCreateListing = { navController.navigate(Routes.CREATE_LISTING) },
            )
        }
        composable(Routes.CREATE_LISTING) {
            CreateListingScreen(
                repository = repository,
                onCreated = { navController.navigate(Routes.listingDetail(it)) { popUpTo(Routes.MARKETPLACE) } },
            )
        }
        composable(Routes.NOTIFICATIONS) { NotificationsScreen(repository = repository) }
        composable(Routes.APPLY_MERCHANT) { ApplyMerchantScreen(repository = repository) }
        composable(
            Routes.MERCHANT_PROFILE,
            arguments = listOf(navArgument("merchantId") { type = NavType.IntType }),
        ) { backStackEntry ->
            val merchantId = backStackEntry.arguments?.getInt("merchantId") ?: return@composable
            MerchantProfileScreen(
                merchantId = merchantId,
                repository = repository,
                onOpenListing = { navController.navigate(Routes.listingDetail(it)) },
                onNeedsLogin = { navController.navigate(Routes.LOGIN) },
            )
        }
        composable(
            Routes.ORDER_DETAIL,
            arguments = listOf(navArgument("orderId") { type = NavType.IntType }),
        ) { backStackEntry ->
            val orderId = backStackEntry.arguments?.getInt("orderId") ?: return@composable
            OrderDetailScreen(orderId = orderId, repository = repository)
        }
        composable(Routes.LOGIN) {
            LoginScreen(
                repository = repository,
                onLoggedIn = { navController.popBackStack(Routes.FEED, inclusive = false) },
                onGoToRegister = { navController.navigate(Routes.REGISTER) },
            )
        }
        composable(Routes.REGISTER) {
            RegisterScreen(
                repository = repository,
                onRegistered = { navController.popBackStack(Routes.FEED, inclusive = false) },
            )
        }
        composable(
            Routes.LISTING_DETAIL,
            arguments = listOf(navArgument("listingId") { type = NavType.IntType }),
        ) { backStackEntry ->
            val listingId = backStackEntry.arguments?.getInt("listingId") ?: return@composable
            ListingDetailScreen(
                listingId = listingId,
                repository = repository,
                onOpenChat = { navController.navigate(Routes.chat(it)) },
                onNeedsLogin = { navController.navigate(Routes.LOGIN) },
                onBuyNow = { navController.navigate(Routes.orderDetail(it)) },
                onOpenMerchant = { navController.navigate(Routes.merchantProfile(it)) },
            )
        }
        composable(
            Routes.CHAT,
            arguments = listOf(navArgument("conversationId") { type = NavType.IntType }),
        ) { backStackEntry ->
            val conversationId = backStackEntry.arguments?.getInt("conversationId") ?: return@composable
            ChatScreen(conversationId = conversationId, repository = repository)
        }
        composable(Routes.ORDERS) {
            OrdersScreen(repository = repository, onOpenOrder = { navController.navigate(Routes.orderDetail(it)) })
        }
        composable(Routes.PROFILE) {
            ProfileScreen(
                repository = repository,
                onLoggedOut = { navController.navigate(Routes.FEED) { popUpTo(Routes.FEED) { inclusive = true } } },
                onApplyMerchant = { navController.navigate(Routes.APPLY_MERCHANT) },
            )
        }
    }
}
