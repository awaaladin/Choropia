package com.choropia.app.ui.screens

import androidx.compose.foundation.lazy.LazyRow
import com.choropia.app.ui.components.QuietButton
import android.content.Intent
import android.net.Uri
import androidx.browser.customtabs.CustomTabsIntent
import androidx.compose.animation.animateColorAsState
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.outlined.ArrowBack
import androidx.compose.material.icons.filled.Star
import androidx.compose.material.icons.outlined.Check
import androidx.compose.material.icons.outlined.ChatBubbleOutline
import androidx.compose.material.icons.outlined.LocalShipping
import androidx.compose.material.icons.outlined.ReceiptLong
import androidx.compose.material.icons.outlined.StarBorder
import androidx.compose.material.icons.outlined.VerifiedUser
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleOwner
import androidx.lifecycle.ViewModel
import androidx.lifecycle.repeatOnLifecycle
import androidx.lifecycle.viewModelScope
import com.choropia.app.data.model.Order
import com.choropia.app.data.network.ApiException
import com.choropia.app.data.repository.ChoropiaRepository
import com.choropia.app.session.Session
import com.choropia.app.ui.LocalRepository
import com.choropia.app.ui.LocalSession
import com.choropia.app.ui.components.BlockingLoader
import com.choropia.app.ui.components.BrandPullToRefresh
import com.choropia.app.ui.components.Chip
import com.choropia.app.ui.components.EmptyState
import com.choropia.app.ui.components.ErrorState
import com.choropia.app.ui.components.ListingImage
import com.choropia.app.ui.components.PrimaryButton
import com.choropia.app.ui.components.ScreenLoader
import com.choropia.app.ui.components.SecondaryButton
import com.choropia.app.ui.components.SectionTitle
import com.choropia.app.ui.components.StatusPill
import com.choropia.app.ui.components.SurfaceCard
import com.choropia.app.ui.rememberVm
import com.choropia.app.ui.theme.LocalIsDark
import com.choropia.app.ui.theme.MoneyStyle
import com.choropia.app.ui.theme.SuccessGreen
import com.choropia.app.ui.theme.SuccessGreenContainerDark
import com.choropia.app.ui.theme.SuccessGreenContainerLight
import com.choropia.app.ui.theme.WarnAmber
import com.choropia.app.ui.theme.WarnAmberContainerDark
import com.choropia.app.ui.theme.WarnAmberContainerLight
import com.choropia.app.ui.util.formatNaira
import com.choropia.app.ui.util.shortDateTime
import com.choropia.app.ui.util.timeAgo
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

// --- status presentation --------------------------------------------------------------------

enum class Tone { Neutral, Warn, Success, Danger }

data class StatusUi(val label: String, val tone: Tone)

fun orderStatusUi(status: String): StatusUi = when (status) {
    "pending_payment" -> StatusUi("Awaiting payment", Tone.Warn)
    "paid_escrow" -> StatusUi("Paid · in escrow", Tone.Neutral)
    "courier_assigned" -> StatusUi("Courier assigned", Tone.Neutral)
    "in_transit" -> StatusUi("In transit", Tone.Neutral)
    "delivered" -> StatusUi("Delivered", Tone.Warn)
    "confirmed" -> StatusUi("Confirmed", Tone.Success)
    "completed" -> StatusUi("Completed", Tone.Success)
    "disputed" -> StatusUi("Disputed", Tone.Danger)
    "cancelled" -> StatusUi("Cancelled", Tone.Danger)
    "refunded" -> StatusUi("Refunded", Tone.Danger)
    else -> StatusUi(status.replace('_', ' ').replaceFirstChar { it.uppercase() }, Tone.Neutral)
}

@Composable
fun OrderStatusPill(status: String, modifier: Modifier = Modifier) {
    val ui = orderStatusUi(status)
    val dark = LocalIsDark.current
    val (bg, fg) = when (ui.tone) {
        Tone.Neutral -> MaterialTheme.colorScheme.secondaryContainer to MaterialTheme.colorScheme.onSecondaryContainer
        Tone.Warn -> (if (dark) WarnAmberContainerDark else WarnAmberContainerLight) to (if (dark) Color(0xFFFCD34D) else WarnAmber)
        Tone.Success -> (if (dark) SuccessGreenContainerDark else SuccessGreenContainerLight) to (if (dark) Color(0xFF86EFAC) else SuccessGreen)
        Tone.Danger -> MaterialTheme.colorScheme.errorContainer to MaterialTheme.colorScheme.error
    }
    StatusPill(ui.label, bg, fg, modifier)
}

// --- orders list ----------------------------------------------------------------------------

data class OrdersState(
    val items: List<Order> = emptyList(),
    val loading: Boolean = true,
    val refreshing: Boolean = false,
    val error: String? = null,
    val busyId: Int? = null,
    val message: String? = null,
)

class OrdersViewModel(private val repo: ChoropiaRepository) : ViewModel() {
    private val _state = MutableStateFlow(OrdersState())
    val state: StateFlow<OrdersState> = _state.asStateFlow()

    /** Seller shortcut from the list: hand the order to a courier without opening it. */
    fun dispatch(orderId: Int) {
        if (_state.value.busyId != null) return
        viewModelScope.launch {
            _state.update { it.copy(busyId = orderId) }
            try {
                val updated = repo.assignCourier(orderId)
                _state.update { s ->
                    s.copy(
                        items = s.items.map { if (it.id == orderId) updated else it },
                        busyId = null,
                        message = "Courier assigned. The buyer has been notified.",
                    )
                }
            } catch (e: ApiException) {
                _state.update { it.copy(busyId = null, message = e.message) }
            }
        }
    }

    fun messageShown() = _state.update { it.copy(message = null) }

    init {
        load(initial = true)
    }

    fun load(initial: Boolean = false) {
        viewModelScope.launch {
            _state.update { it.copy(loading = initial && it.items.isEmpty(), refreshing = !initial, error = null) }
            try {
                val list = repo.orders().sortedByDescending { it.created_at ?: "" }
                _state.update { it.copy(items = list, loading = false, refreshing = false) }
            } catch (e: ApiException) {
                _state.update { it.copy(loading = false, refreshing = false, error = e.message) }
            }
        }
    }
}

@Composable
fun OrdersScreen(onOpenOrder: (Int) -> Unit, onBack: () -> Unit, showMessage: (String) -> Unit = {}) {
    val repo = LocalRepository.current
    val session = LocalSession.current
    val vm = rememberVm { OrdersViewModel(repo) }
    val state by vm.state.collectAsState()
    val me by session.user.collectAsState()
    var tab by remember { mutableIntStateOf(0) }   // 0 buying, 1 selling
    var group by remember { mutableIntStateOf(0) }  // index into the status groups below

    androidx.compose.runtime.LaunchedEffect(state.message) {
        state.message?.let { showMessage(it); vm.messageShown() }
    }

    Column(Modifier.fillMaxSize().statusBarsPadding()) {
        Row(Modifier.height(56.dp).padding(horizontal = 4.dp), verticalAlignment = Alignment.CenterVertically) {
            IconButton(onClick = onBack) { Icon(Icons.AutoMirrored.Outlined.ArrowBack, "Back") }
            Text("Orders", style = MaterialTheme.typography.titleLarge)
        }
        Row(Modifier.padding(horizontal = 16.dp, vertical = 6.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Chip("Buying", tab == 0, { tab = 0; group = 0 })
            Chip("Selling", tab == 1, { tab = 1; group = 0 })
        }
        // Status tabs, as on the seller "fulfillment" screen: the same order list, sliced by stage.
        val groups: List<Pair<String, Set<String>?>> = if (tab == 0) {
            listOf(
                "All" to null,
                "To pay" to setOf("pending_payment"),
                "In escrow" to setOf("paid_escrow"),
                "On the way" to setOf("courier_assigned", "in_transit"),
                "Delivered" to setOf("delivered"),
                "Done" to setOf("confirmed", "completed"),
                "Issues" to setOf("disputed", "refunded"),
            )
        } else {
            listOf(
                "All" to null,
                "Awaiting dispatch" to setOf("paid_escrow"),
                "In transit" to setOf("courier_assigned", "in_transit"),
                "Delivered" to setOf("delivered"),
                "Completed" to setOf("confirmed", "completed"),
                "Unpaid" to setOf("pending_payment"),
                "Issues" to setOf("disputed", "refunded"),
            )
        }
        val mine = state.items.filter { o -> if (tab == 0) o.buyer == me?.id else o.seller == me?.id }
        val selected = groups.getOrElse(group) { groups[0] }
        val visible = mine.filter { o -> selected.second == null || o.status in selected.second!! }
        LazyRow(
            contentPadding = PaddingValues(horizontal = 16.dp, vertical = 6.dp),
            horizontalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            items(groups.size) { index ->
                val (label, statuses) = groups[index]
                val count = if (statuses == null) mine.size else mine.count { it.status in statuses }
                Chip(if (index == 0) label else "$label ($count)", group == index, { group = index })
            }
        }
        when {
            state.loading -> ScreenLoader()
            state.error != null -> ErrorState(state.error ?: "", { vm.load(initial = true) }, Modifier.fillMaxSize())
            else -> BrandPullToRefresh(state.refreshing, { vm.load() }, Modifier.fillMaxSize()) {
                LazyColumn(
                    Modifier.fillMaxSize(),
                    contentPadding = PaddingValues(16.dp),
                    verticalArrangement = Arrangement.spacedBy(12.dp),
                ) {
                    if (visible.isEmpty()) {
                        item {
                            EmptyState(
                                icon = Icons.Outlined.ReceiptLong,
                                title = if (tab == 0) "No purchases yet" else "No sales yet",
                                message = if (tab == 0) "Orders you place will appear here with live escrow status." else "When someone buys your listing, you'll manage the order here.",
                            )
                        }
                    }
                    items(visible, key = { it.id }) { order ->
                        SurfaceCard(Modifier.fillMaxWidth(), padding = PaddingValues(12.dp), onClick = { onOpenOrder(order.id) }) {
                            Row(horizontalArrangement = Arrangement.spacedBy(12.dp), verticalAlignment = Alignment.CenterVertically) {
                                ListingImage(order.listing_cover_photo, Modifier.size(68.dp).clip(RoundedCornerShape(14.dp)))
                                Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                                    Text(
                                        order.listing_title.ifBlank { "Order #${order.id}" },
                                        style = MaterialTheme.typography.titleSmall,
                                        maxLines = 1,
                                        overflow = TextOverflow.Ellipsis,
                                    )
                                    Text(formatNaira(order.price), style = MoneyStyle.copy(fontSize = androidx.compose.ui.unit.TextUnit(16f, androidx.compose.ui.unit.TextUnitType.Sp)))
                                    Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                                        OrderStatusPill(order.status)
                                        Text(timeAgo(order.created_at), style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                                    }
                                    if (tab == 1 && order.status == "paid_escrow") {
                                        QuietButton(
                                            if (state.busyId == order.id) "Dispatching..." else "Dispatch courier",
                                            { vm.dispatch(order.id) },
                                        )
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}

// --- order detail ---------------------------------------------------------------------------

data class OrderDetailState(
    val order: Order? = null,
    val loading: Boolean = true,
    val busy: Boolean = false,
    val error: String? = null,
    val message: String? = null,
)

class OrderDetailViewModel(
    private val orderId: Int,
    private val repo: ChoropiaRepository,
    private val session: Session,
) : ViewModel() {
    private val _state = MutableStateFlow(OrderDetailState())
    val state: StateFlow<OrderDetailState> = _state.asStateFlow()

    init {
        load()
    }

    fun load() {
        viewModelScope.launch {
            _state.update { it.copy(loading = it.order == null, error = null) }
            try {
                val order = repo.order(orderId)
                _state.update { it.copy(order = order, loading = false) }
            } catch (e: ApiException) {
                _state.update { it.copy(loading = false, error = e.message) }
            }
        }
    }

    /** Silent refresh used while waiting for a payment to confirm. */
    suspend fun refreshQuietly() {
        if (_state.value.order?.status == "pending_payment") runCatching { repo.verifyPayment(orderId) }
        runCatching { repo.order(orderId) }.onSuccess { o -> _state.update { it.copy(order = o) } }
    }

    private fun act(success: String? = null, block: suspend () -> Order?) {
        if (_state.value.busy) return
        viewModelScope.launch {
            _state.update { it.copy(busy = true) }
            try {
                val updated = block()
                _state.update { it.copy(order = updated ?: it.order, message = success) }
            } catch (e: ApiException) {
                _state.update { it.copy(message = e.message) }
            } finally {
                _state.update { it.copy(busy = false) }
            }
        }
    }

    fun pay(openUrl: (String) -> Unit) = act {
        val init = repo.initializePayment(orderId)
        openUrl(init.authorization_url)
        null
    }

    fun dispatch() = act("Marked as dispatched. The buyer has been notified.") { repo.assignCourier(orderId) }
    fun inTransit() = act("Marked as on its way.") { repo.markInTransit(orderId) }
    fun delivered() = act("Marked as delivered. The buyer can now confirm or report a problem.") { repo.markDelivered(orderId) }
    fun confirm() = act("Receipt confirmed. The seller has been paid.") { repo.confirmReceipt(orderId) }
    fun dispute(reason: String) = act("Dispute opened. Our team will review it.") { repo.openDispute(orderId, reason) }

    fun review(rating: Int, comment: String) = act("Thanks for your review!") {
        repo.createReview(orderId, rating, comment)
        null
    }

    fun openChat(onOpenChat: (Int) -> Unit) {
        val order = _state.value.order ?: return
        if (_state.value.busy) return
        viewModelScope.launch {
            _state.update { it.copy(busy = true) }
            try {
                val myId = session.user.value?.id
                val conversationId = if (order.buyer == myId) {
                    repo.startConversation(order.listing).id
                } else {
                    repo.conversations().firstOrNull { it.order == order.id || it.listing == order.listing }?.id
                }
                if (conversationId != null) onOpenChat(conversationId)
                else _state.update { it.copy(message = "No conversation with the buyer yet.") }
            } catch (e: ApiException) {
                _state.update { it.copy(message = e.message) }
            } finally {
                _state.update { it.copy(busy = false) }
            }
        }
    }

    fun messageShown() = _state.update { it.copy(message = null) }
}

private val mainFlow = listOf(
    "pending_payment" to "Order placed",
    "paid_escrow" to "Payment held in escrow",
    "courier_assigned" to "Courier assigned",
    "in_transit" to "In transit",
    "delivered" to "Delivered",
    "confirmed" to "Receipt confirmed",
    "completed" to "Completed · seller paid",
)

@Composable
fun OrderDetailScreen(
    orderId: Int,
    onBack: () -> Unit,
    onOpenChat: (Int) -> Unit,
    showMessage: (String) -> Unit,
) {
    val repo = LocalRepository.current
    val session = LocalSession.current
    val vm = rememberVm(key = "order-$orderId") { OrderDetailViewModel(orderId, repo, session) }
    val state by vm.state.collectAsState()
    val me by session.user.collectAsState()
    val context = LocalContext.current

    LaunchedEffect(state.message) {
        state.message?.let { showMessage(it); vm.messageShown() }
    }

    // While payment is pending the user is probably in the browser; watch for it to land.
    val owner = context as? LifecycleOwner
    val status = state.order?.status
    LaunchedEffect(owner, status) {
        if (status == "pending_payment" || status == "paid_escrow" || status == "courier_assigned" || status == "in_transit") {
            owner?.repeatOnLifecycle(Lifecycle.State.RESUMED) {
                while (true) {
                    vm.refreshQuietly()
                    delay(5_000)
                }
            }
        }
    }

    var disputeOpen by remember { mutableStateOf(false) }
    var reviewOpen by remember { mutableStateOf(false) }
    var confirmReceipt by remember { mutableStateOf(false) }

    Box(Modifier.fillMaxSize()) {
        Column(Modifier.fillMaxSize().statusBarsPadding().navigationBarsPadding()) {
            Row(Modifier.height(56.dp).padding(horizontal = 4.dp), verticalAlignment = Alignment.CenterVertically) {
                IconButton(onClick = onBack) { Icon(Icons.AutoMirrored.Outlined.ArrowBack, "Back") }
                Text("Order #$orderId", style = MaterialTheme.typography.titleLarge)
            }
            val order = state.order
            when {
                state.loading -> ScreenLoader()
                order == null -> ErrorState(state.error ?: "Order not found.", vm::load, Modifier.fillMaxSize())
                else -> {
                    val isBuyer = me?.id == order.buyer
                    val isSeller = me?.id == order.seller
                    BrandPullToRefresh(false, { vm.load() }, Modifier.fillMaxSize()) {
                        Column(
                            Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(16.dp),
                            verticalArrangement = Arrangement.spacedBy(16.dp),
                        ) {
                            SurfaceCard(Modifier.fillMaxWidth(), padding = PaddingValues(12.dp)) {
                                Row(horizontalArrangement = Arrangement.spacedBy(12.dp), verticalAlignment = Alignment.CenterVertically) {
                                    ListingImage(order.listing_cover_photo, Modifier.size(76.dp).clip(RoundedCornerShape(14.dp)))
                                    Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                                        Text(order.listing_title.ifBlank { "Order #${order.id}" }, style = MaterialTheme.typography.titleSmall, maxLines = 2, overflow = TextOverflow.Ellipsis)
                                        Text(formatNaira(order.price), style = MoneyStyle)
                                        OrderStatusPill(order.status)
                                    }
                                }
                            }

                            Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                                PartyCard("Buyer", order.buyer_name, isBuyer, Modifier.weight(1f))
                                PartyCard("Seller", order.seller_name, isSeller, Modifier.weight(1f))
                            }

                            order.payout?.let { PayoutCard(it) }

                            SectionTitle("Escrow timeline")
                            Timeline(order)

                            order.dispute_reason.takeIf { it.isNotBlank() }?.let {
                                SurfaceCard(Modifier.fillMaxWidth()) {
                                    Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                                        Text("Dispute reason", style = MaterialTheme.typography.labelLarge, color = MaterialTheme.colorScheme.error)
                                        Text(it, style = MaterialTheme.typography.bodyMedium)
                                    }
                                }
                            }

                            // Role- and state-gated actions: mirror the backend's permission checks.
                            Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                                when (order.status) {
                                    "pending_payment" -> if (isBuyer) {
                                        PrimaryButton(
                                            "Pay ${formatNaira(order.price)} into escrow",
                                            {
                                                vm.pay { url -> openExternal(context, url) }
                                            },
                                            enabled = !state.busy,
                                            icon = Icons.Outlined.VerifiedUser,
                                        )
                                        Text(
                                            "Payment opens in a secure browser tab. This page updates automatically once it's confirmed.",
                                            style = MaterialTheme.typography.bodySmall,
                                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                                        )
                                    } else {
                                        InfoNote("Waiting for the buyer to pay into escrow.")
                                    }
                                    "paid_escrow" -> if (isSeller) {
                                        PrimaryButton("I've dispatched it", { vm.dispatch() }, enabled = !state.busy, icon = Icons.Outlined.LocalShipping)
                                        InfoNote("Dispatch within 7 days, or the buyer is refunded automatically. You're paid as soon as they confirm.")
                                    } else {
                                        // The buyer can confirm the moment they have the item, even before the seller ticks anything.
                                        PrimaryButton("I received it", { confirmReceipt = true }, enabled = !state.busy, icon = Icons.Outlined.Check)
                                        InfoNote("Your payment is safe in escrow. Only tap this once the item is in your hands. If the seller doesn't dispatch within 7 days, you're refunded automatically.")
                                    }
                                    "courier_assigned" -> if (isSeller) {
                                        PrimaryButton("It's on its way", { vm.inTransit() }, enabled = !state.busy, icon = Icons.Outlined.LocalShipping)
                                    } else {
                                        PrimaryButton("I received it", { confirmReceipt = true }, enabled = !state.busy, icon = Icons.Outlined.Check)
                                        SecondaryButton("It hasn't arrived. Report a problem", { disputeOpen = true }, enabled = !state.busy, destructive = true)
                                    }
                                    "in_transit" -> if (isSeller) {
                                        PrimaryButton("Mark as delivered", { vm.delivered() }, enabled = !state.busy, icon = Icons.Outlined.Check)
                                        InfoNote("Marking it delivered starts the buyer's window to confirm or report a problem. If they do neither, you're paid automatically after 3 days.")
                                    } else {
                                        PrimaryButton("I received it", { confirmReceipt = true }, enabled = !state.busy, icon = Icons.Outlined.Check)
                                        SecondaryButton("It hasn't arrived. Report a problem", { disputeOpen = true }, enabled = !state.busy, destructive = true)
                                    }
                                    "delivered" -> if (isBuyer) {
                                        PrimaryButton("Confirm I received it", { confirmReceipt = true }, enabled = !state.busy, icon = Icons.Outlined.Check)
                                        SecondaryButton("Something's wrong. Open a dispute", { disputeOpen = true }, enabled = !state.busy, destructive = true)
                                        InfoNote("If you do nothing, the seller is paid automatically 3 days after delivery.")
                                    } else {
                                        InfoNote("Delivered. Waiting for the buyer to confirm receipt. You're paid automatically 3 days after delivery if they don't respond.")
                                    }
                                    "cancelled" -> InfoNote("This order was cancelled. If you paid, your money is being refunded in full.")
                                    "refunded" -> InfoNote("This order was refunded to the buyer.")
                                    "completed" -> if (isBuyer || isSeller) {
                                        SecondaryButton("Leave a review", { reviewOpen = true }, enabled = !state.busy, icon = Icons.Outlined.StarBorder)
                                    }
                                    "disputed" -> InfoNote("A moderator is reviewing this dispute. Funds stay in escrow until it's resolved.")
                                }
                                SecondaryButton(
                                    "Message ${if (isBuyer) "seller" else "buyer"}",
                                    { vm.openChat(onOpenChat) },
                                    enabled = !state.busy,
                                    icon = Icons.Outlined.ChatBubbleOutline,
                                )
                            }
                            Spacer(Modifier.height(12.dp))
                        }
                    }
                }
            }
        }
        BlockingLoader(visible = state.busy)

        if (confirmReceipt) {
            AlertDialog(
                onDismissRequest = { confirmReceipt = false },
                title = { Text("Confirm receipt?") },
                text = { Text("This releases the payment to the seller and can't be undone.") },
                confirmButton = { TextButton(onClick = { confirmReceipt = false; vm.confirm() }) { Text("Yes, release payment") } },
                dismissButton = { TextButton(onClick = { confirmReceipt = false }) { Text("Not yet") } },
            )
        }
        if (disputeOpen) {
            TextEntryDialog(
                title = "Open a dispute",
                label = "What went wrong?",
                confirm = "Submit dispute",
                onDismiss = { disputeOpen = false },
                onSubmit = { disputeOpen = false; vm.dispute(it) },
            )
        }
        if (reviewOpen) {
            ReviewDialog(onDismiss = { reviewOpen = false }, onSubmit = { r, c -> reviewOpen = false; vm.review(r, c) })
        }
    }
}

private fun openExternal(context: android.content.Context, url: String) {
    val uri = Uri.parse(url)
    try {
        CustomTabsIntent.Builder().setShowTitle(true).build().launchUrl(context, uri)
    } catch (e: Exception) {
        runCatching { context.startActivity(Intent(Intent.ACTION_VIEW, uri).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)) }
    }
}

@Composable
private fun PartyCard(role: String, name: String, isMe: Boolean, modifier: Modifier = Modifier) {
    SurfaceCard(modifier, padding = PaddingValues(12.dp)) {
        Column(verticalArrangement = Arrangement.spacedBy(2.dp)) {
            Text(role.uppercase(), style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            Text(
                if (isMe) "You" else name.ifBlank { "—" },
                style = MaterialTheme.typography.titleSmall,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
            )
        }
    }
}

@Composable
private fun InfoNote(text: String) {
    Row(
        Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(14.dp))
            .background(MaterialTheme.colorScheme.surfaceContainer)
            .padding(14.dp),
        horizontalArrangement = Arrangement.spacedBy(10.dp),
    ) {
        Icon(Icons.Outlined.VerifiedUser, null, tint = MaterialTheme.colorScheme.secondary)
        Text(text, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
    }
}

@Composable
private fun Timeline(order: Order) {
    val whenReached = order.history.associate { it.to_status to it.created_at }.toMutableMap()
    order.created_at?.let { whenReached.putIfAbsent("pending_payment", it) }

    data class Step(val key: String, val title: String, val reached: Boolean, val current: Boolean, val danger: Boolean = false)

    val status = order.status
    val steps = mutableListOf<Step>()
    val flowIndex = mainFlow.indexOfFirst { it.first == status }
    val branched = status == "disputed" || status == "refunded"
    // Disputes can only start from "delivered", so a branched order has completed the flow up to there.
    val reachedUpTo = if (branched) mainFlow.indexOfFirst { it.first == "delivered" } else flowIndex
    mainFlow.forEachIndexed { index, (key, title) ->
        if (branched && index > reachedUpTo) return@forEachIndexed
        steps += Step(key, title, reached = index <= reachedUpTo, current = !branched && index == flowIndex)
    }
    if (branched) {
        steps += Step("disputed", "Dispute opened", reached = true, current = status == "disputed", danger = true)
        if (status == "refunded") steps += Step("refunded", "Refunded to buyer", reached = true, current = true, danger = true)
    }

    Column {
        steps.forEachIndexed { index, step ->
            val last = index == steps.lastIndex
            val dotColor by animateColorAsState(
                when {
                    step.danger -> MaterialTheme.colorScheme.error
                    step.reached -> MaterialTheme.colorScheme.primary
                    else -> MaterialTheme.colorScheme.outlineVariant
                },
                label = "dot",
            )
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(14.dp)) {
                Column(horizontalAlignment = Alignment.CenterHorizontally) {
                    Box(
                        Modifier.size(if (step.current) 26.dp else 22.dp).clip(CircleShape).background(dotColor),
                        contentAlignment = Alignment.Center,
                    ) {
                        if (step.reached) {
                            Icon(
                                Icons.Outlined.Check, null,
                                tint = if (step.danger) MaterialTheme.colorScheme.onError else MaterialTheme.colorScheme.onPrimary,
                                modifier = Modifier.size(14.dp),
                            )
                        }
                    }
                    if (!last) {
                        Box(
                            Modifier
                                .width(2.dp)
                                .height(30.dp)
                                .background(if (step.reached && !step.current) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.outlineVariant),
                        )
                    }
                }
                Column(Modifier.padding(bottom = if (last) 0.dp else 10.dp)) {
                    Text(
                        step.title,
                        style = MaterialTheme.typography.titleSmall,
                        color = if (step.reached) MaterialTheme.colorScheme.onSurface else MaterialTheme.colorScheme.outline,
                    )
                    whenReached[step.key]?.takeIf { step.reached }?.let {
                        Text(shortDateTime(it), style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                }
            }
        }
    }
}

@Composable
fun TextEntryDialog(
    title: String,
    label: String,
    confirm: String,
    onDismiss: () -> Unit,
    onSubmit: (String) -> Unit,
) {
    var text by remember { mutableStateOf("") }
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text(title) },
        text = { OutlinedTextField(text, { text = it }, label = { Text(label) }, minLines = 3) },
        confirmButton = { TextButton(onClick = { onSubmit(text) }, enabled = text.isNotBlank()) { Text(confirm) } },
        dismissButton = { TextButton(onClick = onDismiss) { Text("Cancel") } },
    )
}

@Composable
private fun ReviewDialog(onDismiss: () -> Unit, onSubmit: (Int, String) -> Unit) {
    var rating by remember { mutableIntStateOf(5) }
    var comment by remember { mutableStateOf("") }
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("Leave a review") },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                Row(horizontalArrangement = Arrangement.spacedBy(4.dp)) {
                    (1..5).forEach { star ->
                        Icon(
                            if (star <= rating) Icons.Filled.Star else Icons.Outlined.StarBorder,
                            contentDescription = "$star stars",
                            tint = if (star <= rating) WarnAmber else MaterialTheme.colorScheme.outline,
                            modifier = Modifier.size(36.dp).clickable { rating = star },
                        )
                    }
                }
                OutlinedTextField(comment, { comment = it }, label = { Text("Comment (optional)") }, minLines = 3)
            }
        },
        confirmButton = { TextButton(onClick = { onSubmit(rating, comment) }) { Text("Submit") } },
        dismissButton = { TextButton(onClick = onDismiss) { Text("Cancel") } },
    )
}


/** The seller's view of what they are paid for this order, after Choropia's commission. */
@Composable
private fun PayoutCard(payout: com.choropia.app.data.model.OrderPayout) {
    SurfaceCard(Modifier.fillMaxWidth()) {
        Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text("Your payout", style = MaterialTheme.typography.titleSmall, modifier = Modifier.weight(1f))
                StatusPill(
                    payout.status_label,
                    if (payout.status == "success") MaterialTheme.colorScheme.secondaryContainer else MaterialTheme.colorScheme.surfaceContainer,
                    if (payout.status == "success") MaterialTheme.colorScheme.onSecondaryContainer else MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            PayoutLine("Buyer paid", formatNaira(payout.gross_amount))
            PayoutLine("Choropia commission (${payout.commission_rate.removeSuffix(".00")}%)", "− " + formatNaira(payout.commission_amount))
            PayoutLine("You receive", formatNaira(payout.net_amount), bold = true)
            if (payout.bank_name.isNotBlank()) {
                Text(
                    "Sent to ${payout.bank_name} ••••${payout.account_last4}",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            } else if (payout.status == "awaiting_account") {
                Text(
                    "Add a bank account under Me → Payout account and this is sent automatically.",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.error,
                )
            }
        }
    }
}

@Composable
private fun PayoutLine(label: String, value: String, bold: Boolean = false) {
    Row(Modifier.fillMaxWidth()) {
        Text(label, style = if (bold) MaterialTheme.typography.titleSmall else MaterialTheme.typography.bodyMedium,
            color = if (bold) MaterialTheme.colorScheme.onSurface else MaterialTheme.colorScheme.onSurfaceVariant,
            modifier = Modifier.weight(1f))
        Text(value, style = if (bold) MoneyStyle else MaterialTheme.typography.bodyMedium)
    }
}
