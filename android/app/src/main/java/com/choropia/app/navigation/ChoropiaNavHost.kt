package com.choropia.app.navigation

import com.choropia.app.ui.screens.DriverScreen
import com.choropia.app.ui.screens.ListingDeliveryScreen
import com.choropia.app.ui.screens.MyListingsScreen
import com.choropia.app.ui.screens.PayoutAccountScreen
import com.choropia.app.ui.screens.SecurityScreen
import com.choropia.app.ui.screens.WatchlistScreen
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.core.tween
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.slideInHorizontally
import androidx.compose.animation.slideInVertically
import androidx.compose.animation.slideOutHorizontally
import androidx.compose.animation.slideOutVertically
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.background
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.ChatBubble
import androidx.compose.material.icons.filled.PlayCircle
import androidx.compose.material.icons.outlined.PlayCircleOutline
import androidx.compose.material.icons.filled.Home
import androidx.compose.material.icons.filled.Person
import androidx.compose.material.icons.filled.Storefront
import androidx.compose.material.icons.outlined.ChatBubbleOutline
import androidx.compose.material.icons.outlined.Home
import androidx.compose.material.icons.outlined.PersonOutline
import androidx.compose.material.icons.outlined.Storefront
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.NavigationBarItemDefaults
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.unit.dp
import androidx.navigation.NavGraph.Companion.findStartDestination
import androidx.navigation.NavHostController
import androidx.navigation.NavType
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.currentBackStackEntryAsState
import androidx.navigation.compose.rememberNavController
import androidx.navigation.navArgument
import com.choropia.app.ui.LocalSession
import com.choropia.app.ui.screens.ApplyMerchantScreen
import com.choropia.app.ui.screens.ChatScreen
import com.choropia.app.ui.screens.CreateListingScreen
import com.choropia.app.ui.screens.EditProfileScreen
import com.choropia.app.ui.screens.FeedScreen
import com.choropia.app.ui.screens.ForgotPasswordScreen
import com.choropia.app.ui.screens.InboxScreen
import com.choropia.app.ui.screens.ListingDetailScreen
import com.choropia.app.ui.screens.LoginGate
import com.choropia.app.ui.screens.LoginScreen
import com.choropia.app.ui.screens.MarketplaceScreen
import com.choropia.app.ui.screens.MerchantProfileScreen
import com.choropia.app.ui.screens.NotificationsScreen
import com.choropia.app.ui.screens.OrderDetailScreen
import com.choropia.app.ui.screens.OrdersScreen
import com.choropia.app.ui.screens.ProfileScreen
import com.choropia.app.ui.screens.RegisterScreen
import com.choropia.app.ui.screens.ReelsScreen
import kotlinx.coroutines.launch

object Routes {
    const val FEED = "feed"
    const val MARKET = "market"
    const val REELS = "reels"
    const val INBOX = "inbox"
    const val ME = "me"
    const val LOGIN = "login"
    const val REGISTER = "register"
    const val FORGOT = "forgot"
    const val SELL = "sell"
    const val ORDERS = "orders"
    const val NOTIFICATIONS = "notifications"
    const val APPLY_MERCHANT = "merchant/apply"
    const val EDIT_PROFILE = "profile/edit"
    const val WATCHLIST = "watchlist"
    const val MY_LISTINGS = "my-listings"
    const val SECURITY = "security"
    const val PAYOUT_ACCOUNT = "payout-account"
    const val DRIVER = "driver"
    const val LISTING_DELIVERY = "listing/{id}/delivery"
    const val LISTING = "listing/{id}"
    const val CHAT = "chat/{id}"
    const val ORDER = "order/{id}"
    const val MERCHANT = "merchant/{id}"

    fun listing(id: Int) = "listing/$id"
    fun chat(id: Int) = "chat/$id"
    fun order(id: Int) = "order/$id"
    fun listingDelivery(id: Int) = "listing/$id/delivery"
    fun merchant(id: Int) = "merchant/$id"

    val tabs = setOf(FEED, REELS, MARKET, INBOX, ME)
}

private data class Tab(val route: String, val label: String, val icon: ImageVector, val selectedIcon: ImageVector)

private val leftTabs = listOf(
    Tab(Routes.FEED, "Home", Icons.Outlined.Home, Icons.Filled.Home),
    Tab(Routes.REELS, "Reels", Icons.Outlined.PlayCircleOutline, Icons.Filled.PlayCircle),
)
private val rightTabs = listOf(
    Tab(Routes.MARKET, "Market", Icons.Outlined.Storefront, Icons.Filled.Storefront),
    Tab(Routes.INBOX, "Inbox", Icons.Outlined.ChatBubbleOutline, Icons.Filled.ChatBubble),
)

@Composable
fun ChoropiaNavHost(navController: NavHostController = rememberNavController()) {
    val session = LocalSession.current
    val loggedIn by session.loggedIn.collectAsState()
    val backStack by navController.currentBackStackEntryAsState()
    val route = backStack?.destination?.route
    val snackbar = remember { SnackbarHostState() }
    val scope = rememberCoroutineScope()

    val showMessage: (String) -> Unit = { text -> scope.launch { snackbar.showSnackbar(text) } }
    val needsLogin: () -> Unit = { navController.navigate(Routes.LOGIN) }

    fun goTab(target: String) {
        navController.navigate(target) {
            popUpTo(navController.graph.findStartDestination().id) { saveState = true }
            launchSingleTop = true
            restoreState = true
        }
    }
    fun openSell() {
        if (loggedIn) navController.navigate(Routes.SELL) else needsLogin()
    }

    Scaffold(
        snackbarHost = { SnackbarHost(snackbar) },
        contentWindowInsets = WindowInsets(0, 0, 0, 0),
        containerColor = MaterialTheme.colorScheme.background,
        bottomBar = {
            AnimatedVisibility(
                visible = route in Routes.tabs,
                enter = slideInVertically(tween(220)) { it } + fadeIn(tween(220)),
                exit = slideOutVertically(tween(180)) { it } + fadeOut(tween(180)),
            ) {
                NavigationBar(containerColor = MaterialTheme.colorScheme.surfaceContainerLowest, tonalElevation = 0.dp) {
                    @Composable
                    fun item(tab: Tab) {
                        val selected = route == tab.route
                        NavigationBarItem(
                            selected = selected,
                            onClick = { goTab(tab.route) },
                            icon = { Icon(if (selected) tab.selectedIcon else tab.icon, contentDescription = tab.label) },
                            label = { Text(tab.label, style = MaterialTheme.typography.labelMedium) },
                            colors = NavigationBarItemDefaults.colors(
                                indicatorColor = MaterialTheme.colorScheme.secondaryContainer,
                                selectedIconColor = MaterialTheme.colorScheme.onSecondaryContainer,
                                selectedTextColor = MaterialTheme.colorScheme.onSurface,
                                unselectedIconColor = MaterialTheme.colorScheme.onSurfaceVariant,
                                unselectedTextColor = MaterialTheme.colorScheme.onSurfaceVariant,
                            ),
                        )
                    }
                    leftTabs.forEach { item(it) }
                    // Centre action: post a listing.
                    NavigationBarItem(
                        selected = false,
                        onClick = { openSell() },
                        icon = {
                            Box(
                                Modifier
                                    .size(44.dp)
                                    .clip(RoundedCornerShape(14.dp))
                                    .background(MaterialTheme.colorScheme.primary),
                                contentAlignment = Alignment.Center,
                            ) {
                                Icon(Icons.Filled.Add, contentDescription = "Post a listing", tint = MaterialTheme.colorScheme.onPrimary)
                            }
                        },
                        label = null,
                        alwaysShowLabel = false,
                        colors = NavigationBarItemDefaults.colors(indicatorColor = androidx.compose.ui.graphics.Color.Transparent),
                    )
                    rightTabs.forEach { item(it) }
                }
            }
        },
    ) { padding ->
        NavHost(
            navController = navController,
            startDestination = Routes.FEED,
            modifier = Modifier.fillMaxSize().padding(bottom = padding.calculateBottomPadding()),
            enterTransition = { fadeIn(tween(240)) + slideInHorizontally(tween(280)) { it / 12 } },
            exitTransition = { fadeOut(tween(160)) },
            popEnterTransition = { fadeIn(tween(240)) },
            popExitTransition = { fadeOut(tween(180)) + slideOutHorizontally(tween(260)) { it / 12 } },
        ) {
            // --- tabs ---
            composable(Routes.FEED) {
                FeedScreen(
                    onOpenListing = { navController.navigate(Routes.listing(it)) },
                    onOpenSeller = { listing ->
                        val merchantId = listing.merchantRef
                        if (merchantId != null) navController.navigate(Routes.merchant(merchantId))
                        else navController.navigate(Routes.listing(listing.id))
                    },
                    onSell = { openSell() },
                    onProfile = { if (loggedIn) navController.navigate(Routes.ME) else needsLogin() },
                    onNotifications = { if (loggedIn) navController.navigate(Routes.NOTIFICATIONS) else needsLogin() },
                    onNeedsLogin = needsLogin,
                    showMessage = showMessage,
                )
            }
            composable(Routes.REELS) {
                ReelsScreen(
                    onOpenListing = { navController.navigate(Routes.listing(it)) },
                    onNeedsLogin = needsLogin,
                )
            }
            composable(Routes.MARKET) {
                MarketplaceScreen(onOpenListing = { navController.navigate(Routes.listing(it)) })
            }
            composable(Routes.INBOX) {
                if (loggedIn) {
                    InboxScreen(onOpenChat = { navController.navigate(Routes.chat(it)) })
                } else {
                    LoginGate(
                        "Your messages live here",
                        "Log in to chat with buyers and sellers.",
                        onLogin = needsLogin,
                        onRegister = { navController.navigate(Routes.REGISTER) },
                    )
                }
            }
            composable(Routes.ME) {
                if (loggedIn) {
                    ProfileScreen(
                        onOrders = { navController.navigate(Routes.ORDERS) },
                        onWatchlist = { navController.navigate(Routes.WATCHLIST) },
                        onMyListings = { navController.navigate(Routes.MY_LISTINGS) },
                        onSecurity = { navController.navigate(Routes.SECURITY) },
                        onPayoutAccount = { navController.navigate(Routes.PAYOUT_ACCOUNT) },
                        onDriver = { navController.navigate(Routes.DRIVER) },
                        onEditProfile = { navController.navigate(Routes.EDIT_PROFILE) },
                        onApplyMerchant = { navController.navigate(Routes.APPLY_MERCHANT) },
                        showMessage = showMessage,
                    )
                } else {
                    LoginGate(
                        "Your Choropia account",
                        "Log in to see your orders, profile and settings.",
                        onLogin = needsLogin,
                        onRegister = { navController.navigate(Routes.REGISTER) },
                    )
                }
            }

            // --- auth ---
            composable(Routes.LOGIN) {
                LoginScreen(
                    onLoggedIn = { navController.popBackStack() },
                    onRegister = { navController.navigate(Routes.REGISTER) },
                    onForgot = { navController.navigate(Routes.FORGOT) },
                    onBack = { navController.popBackStack() },
                )
            }
            composable(Routes.REGISTER) {
                RegisterScreen(
                    onRegistered = { wantsStorefront ->
                        // Registered from the login screen? Drop it too.
                        if (!navController.popBackStack(Routes.LOGIN, inclusive = true)) navController.popBackStack()
                        if (wantsStorefront) navController.navigate(Routes.APPLY_MERCHANT)
                    },
                    onLogin = { if (!navController.popBackStack(Routes.LOGIN, inclusive = false)) navController.navigate(Routes.LOGIN) },
                    onBack = { navController.popBackStack() },
                )
            }
            composable(Routes.FORGOT) { ForgotPasswordScreen(onBack = { navController.popBackStack() }) }

            // --- content ---
            composable(Routes.LISTING, arguments = listOf(navArgument("id") { type = NavType.IntType })) { entry ->
                val id = entry.arguments?.getInt("id") ?: return@composable
                ListingDetailScreen(
                    listingId = id,
                    onBack = { navController.popBackStack() },
                    onOpenChat = { navController.navigate(Routes.chat(it)) },
                    onOpenOrder = { navController.navigate(Routes.order(it)) },
                    onOpenMerchant = { navController.navigate(Routes.merchant(it)) },
                    onNeedsLogin = needsLogin,
                    showMessage = showMessage,
                )
            }
            composable(Routes.SELL) {
                if (loggedIn) {
                    CreateListingScreen(
                        onBack = { navController.popBackStack() },
                        onCreated = { id ->
                            showMessage("Your listing is live")
                            navController.navigate(Routes.listing(id)) { popUpTo(Routes.SELL) { inclusive = true } }
                        },
                    )
                } else {
                    LoginGate("Log in to sell", "Create an account to post listings.", needsLogin) { navController.navigate(Routes.REGISTER) }
                }
            }
            composable(Routes.CHAT, arguments = listOf(navArgument("id") { type = NavType.IntType })) { entry ->
                val id = entry.arguments?.getInt("id") ?: return@composable
                ChatScreen(conversationId = id, onBack = { navController.popBackStack() })
            }
            composable(Routes.ORDERS) {
                OrdersScreen(
                    onOpenOrder = { navController.navigate(Routes.order(it)) },
                    onBack = { navController.popBackStack() },
                    showMessage = showMessage,
                )
            }
            composable(Routes.MY_LISTINGS) {
                MyListingsScreen(
                    onBack = { navController.popBackStack() },
                    onOpenListing = { navController.navigate(Routes.listing(it)) },
                    onSell = { openSell() },
                    onDelivery = { navController.navigate(Routes.listingDelivery(it)) },
                )
            }
            composable(Routes.DRIVER) {
                if (loggedIn) {
                    DriverScreen(
                        onBack = { navController.popBackStack() },
                        onPayoutAccount = { navController.navigate(Routes.PAYOUT_ACCOUNT) },
                        showMessage = showMessage,
                    )
                } else {
                    LoginGate("Deliver with Choropia", "Log in to apply as a delivery driver.", needsLogin) { navController.navigate(Routes.REGISTER) }
                }
            }
            composable(Routes.LISTING_DELIVERY, arguments = listOf(navArgument("id") { type = NavType.IntType })) { entry ->
                val id = entry.arguments?.getInt("id") ?: return@composable
                ListingDeliveryScreen(listingId = id, onBack = { navController.popBackStack() }, showMessage = showMessage)
            }
            composable(Routes.PAYOUT_ACCOUNT) { PayoutAccountScreen(onBack = { navController.popBackStack() }) }
            composable(Routes.SECURITY) {
                SecurityScreen(onBack = { navController.popBackStack() }, showMessage = showMessage)
            }
            composable(Routes.WATCHLIST) {
                WatchlistScreen(
                    onBack = { navController.popBackStack() },
                    onOpenListing = { navController.navigate(Routes.listing(it)) },
                )
            }
            composable(Routes.ORDER, arguments = listOf(navArgument("id") { type = NavType.IntType })) { entry ->
                val id = entry.arguments?.getInt("id") ?: return@composable
                OrderDetailScreen(
                    orderId = id,
                    onBack = { navController.popBackStack() },
                    onOpenChat = { navController.navigate(Routes.chat(it)) },
                    showMessage = showMessage,
                    onEditDelivery = { navController.navigate(Routes.listingDelivery(it)) },
                )
            }
            composable(Routes.NOTIFICATIONS) {
                NotificationsScreen(
                    onBack = { navController.popBackStack() },
                    onOpenOrder = { navController.navigate(Routes.order(it)) },
                    onOpenChat = { navController.navigate(Routes.chat(it)) },
                    onOpenMerchant = { navController.navigate(Routes.merchant(it)) },
                )
            }
            composable(Routes.MERCHANT, arguments = listOf(navArgument("id") { type = NavType.IntType })) { entry ->
                val id = entry.arguments?.getInt("id") ?: return@composable
                MerchantProfileScreen(
                    merchantId = id,
                    onBack = { navController.popBackStack() },
                    onOpenListing = { navController.navigate(Routes.listing(it)) },
                    onNeedsLogin = needsLogin,
                )
            }
            composable(Routes.APPLY_MERCHANT) { ApplyMerchantScreen(onBack = { navController.popBackStack() }) }
            composable(Routes.EDIT_PROFILE) {
                EditProfileScreen(
                    onBack = { navController.popBackStack() },
                    onSaved = { showMessage("Profile updated"); navController.popBackStack() },
                )
            }
        }
    }
}
