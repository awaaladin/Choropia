package com.choropia.app.ui.offers

import androidx.compose.animation.AnimatedContent
import androidx.compose.animation.animateColorAsState
import androidx.compose.animation.animateContentSize
import androidx.compose.animation.core.Animatable
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.tween
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.scaleIn
import androidx.compose.animation.scaleOut
import androidx.compose.animation.togetherWith
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.Block
import androidx.compose.material.icons.outlined.CheckCircle
import androidx.compose.material.icons.outlined.ErrorOutline
import androidx.compose.material.icons.outlined.Gavel
import androidx.compose.material.icons.outlined.HighlightOff
import androidx.compose.material.icons.outlined.HourglassTop
import androidx.compose.material.icons.outlined.Lock
import androidx.compose.material.icons.outlined.Refresh
import androidx.compose.material.icons.outlined.Schedule
import androidx.compose.material.icons.outlined.Undo
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.rememberModalBottomSheetState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableLongStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.geometry.CornerRadius
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.drawscope.rotate
import androidx.compose.ui.graphics.drawscope.translate
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.hapticfeedback.HapticFeedbackType
import androidx.compose.ui.platform.LocalHapticFeedback
import androidx.compose.ui.semantics.LiveRegionMode
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.liveRegion
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.style.TextDecoration
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import coil.compose.AsyncImage
import com.choropia.app.data.model.ChatOffer
import com.choropia.app.data.model.HandoverCode
import com.choropia.app.data.network.ApiException
import com.choropia.app.data.network.OfferCheckoutResponse
import com.choropia.app.ui.LocalRepository
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import java.time.OffsetDateTime

private fun epochMs(iso: String): Long? = runCatching { OffsetDateTime.parse(iso).toInstant().toEpochMilli() }.getOrNull()

/** Milliseconds to add to this phone's clock to get the server's (from the offer's server_now). */
private fun skewMs(offer: ChatOffer): Long = epochMs(offer.server_now)?.let { it - System.currentTimeMillis() } ?: 0L

enum class OfferCardState {
    Pending, PaymentFailed, Processing, Held, HandedOver, Released,
    Declined, Cancelled, Expired, Superseded, RefundPending, Refunded, Disputed,
}

/** One visual state for everything the offer and its order can be (mirrors offerCardState on the web). */
fun offerCardState(offer: ChatOffer, nowMs: Long = System.currentTimeMillis()): OfferCardState {
    when (offer.order_stage) {
        "refund_pending" -> return OfferCardState.RefundPending
        "refunded" -> return OfferCardState.Refunded
        "disputed" -> return OfferCardState.Disputed
    }
    return when (offer.status) {
        "pending" -> {
            val expires = epochMs(offer.expires_at)
            if (expires != null && expires <= nowMs + skewMs(offer)) OfferCardState.Expired
            else if (offer.last_payment_failed) OfferCardState.PaymentFailed
            else OfferCardState.Pending
        }
        "payment_processing" -> OfferCardState.Processing
        "paid" -> when (offer.order_stage) {
            "released" -> OfferCardState.Released
            "handed_over" -> OfferCardState.HandedOver
            else -> OfferCardState.Held
        }
        "declined" -> OfferCardState.Declined
        "cancelled" -> OfferCardState.Cancelled
        "expired" -> OfferCardState.Expired
        else -> OfferCardState.Superseded
    }
}

private enum class Tone { Neutral, Tide, Ok, Caution, Danger, Closed }

private data class Meta(val label: String, val tone: Tone, val icon: ImageVector?)

private fun meta(state: OfferCardState): Meta = when (state) {
    OfferCardState.Pending -> Meta("Offer", Tone.Neutral, null)
    OfferCardState.PaymentFailed -> Meta("Payment didn't go through", Tone.Danger, Icons.Outlined.ErrorOutline)
    OfferCardState.Processing -> Meta("Payment processing", Tone.Tide, Icons.Outlined.HourglassTop)
    OfferCardState.Held -> Meta("Paid · held in escrow", Tone.Tide, null)
    OfferCardState.HandedOver -> Meta("Handed over", Tone.Tide, Icons.Outlined.HourglassTop)
    OfferCardState.Released -> Meta("Completed", Tone.Ok, Icons.Outlined.CheckCircle)
    OfferCardState.Declined -> Meta("Declined", Tone.Closed, Icons.Outlined.HighlightOff)
    OfferCardState.Cancelled -> Meta("Cancelled", Tone.Closed, Icons.Outlined.Block)
    OfferCardState.Expired -> Meta("Expired", Tone.Closed, Icons.Outlined.Schedule)
    OfferCardState.Superseded -> Meta("Replaced by a newer offer", Tone.Closed, Icons.Outlined.Refresh)
    OfferCardState.RefundPending -> Meta("Refund on its way", Tone.Caution, Icons.Outlined.Undo)
    OfferCardState.Refunded -> Meta("Refunded", Tone.Closed, Icons.Outlined.Undo)
    OfferCardState.Disputed -> Meta("Under review", Tone.Caution, Icons.Outlined.Gavel)
}

private fun announcement(state: OfferCardState, seller: Boolean, amount: String): String = when (state) {
    OfferCardState.Pending -> if (seller) "Offer of $amount sent." else "New offer: $amount."
    OfferCardState.PaymentFailed -> "The payment didn't go through. The offer is open again."
    OfferCardState.Processing -> if (seller) "The buyer is paying." else "Payment in progress."
    OfferCardState.Held -> if (seller) "Paid. $amount is held in escrow. Hand the item over." else "Paid. $amount is held safely in escrow."
    OfferCardState.HandedOver -> "Marked as handed over."
    OfferCardState.Released -> if (seller) "The buyer has the item. Your payout is on its way." else "Done. The seller has been paid."
    OfferCardState.Declined -> "The offer was declined."
    OfferCardState.Cancelled -> "The offer was cancelled."
    OfferCardState.Expired -> "The offer has expired."
    OfferCardState.Superseded -> "This offer was replaced by a newer one."
    OfferCardState.RefundPending -> "The payment is being refunded."
    OfferCardState.Refunded -> "The payment was refunded."
    OfferCardState.Disputed -> "This order is under review by Choropia."
}

/** What the chat screen does when someone acts on a card. */
class OfferCardActions(
    val onPay: (ChatOffer) -> Unit,
    val onDecline: suspend (ChatOffer) -> Unit,
    val onCancel: suspend (ChatOffer) -> Unit,
    val onCheckPayment: suspend (ChatOffer) -> Unit,
    val onReleased: (ChatOffer) -> Unit,
    val onOpenOrder: (Int) -> Unit,
)

/** The offer as a card in the chat, drawn from the live offer. Changes of state morph in place. */
@Composable
fun OfferCard(offer: ChatOffer, actions: OfferCardActions, modifier: Modifier = Modifier) {
    val c = offerColors()
    val calm = rememberCalmMotion()
    val scope = rememberCoroutineScope()
    var tick by remember { mutableLongStateOf(0L) }
    val state = remember(offer, tick) { offerCardState(offer) }
    val m = meta(state)
    val seller = offer.viewer_role == "seller"
    val buyer = offer.viewer_role == "buyer"
    val escrow = state == OfferCardState.Held || state == OfferCardState.HandedOver || state == OfferCardState.Processing
    val closed = m.tone == Tone.Closed

    var previous by remember { mutableStateOf(state) }
    var playLock by remember { mutableStateOf(false) }
    var said by remember { mutableStateOf("") }
    var confirming by remember { mutableStateOf<String?>(null) }
    var busy by remember { mutableStateOf<String?>(null) }
    LaunchedEffect(state) {
        if (previous != state) {
            if (state == OfferCardState.Held && previous in setOf(OfferCardState.Processing, OfferCardState.Pending, OfferCardState.PaymentFailed)) playLock = true
            said = announcement(state, seller, OfferFormat.naira(offer.amount_kobo))
            confirming = null
            previous = state
        }
    }

    val bg by animateColorAsState(if (escrow) c.tide else c.raised, if (calm) tween(150) else tween(350), label = "card-bg")
    fun run(key: String, block: suspend () -> Unit) = scope.launch {
        busy = key
        try { block() } finally { busy = null; confirming = null }
    }

    Column(
        modifier
            .width(300.dp)
            .clip(RoundedCornerShape(OfferRadius.lg))
            .background(bg)
            .border(1.dp, c.hairline, RoundedCornerShape(OfferRadius.lg))
            .then(if (calm) Modifier else Modifier.animateContentSize(OfferMotion.standard()))
            .graphicsLayer { alpha = if (closed) 0.82f else 1f }
            .semantics(mergeDescendants = false) {
                contentDescription = "Offer: ${OfferFormat.spoken(offer.amount_kobo)} for ${offer.listing.title}. ${m.label}."
            }
            .padding(16.dp),
    ) {
        // Spoken when the state changes.
        Text(said, modifier = Modifier.size(0.dp).semantics { liveRegion = LiveRegionMode.Polite })

        Row(verticalAlignment = Alignment.Top) {
            if (offer.listing.photo != null) {
                AsyncImage(
                    model = offer.listing.photo,
                    contentDescription = null,
                    contentScale = androidx.compose.ui.layout.ContentScale.Crop,
                    modifier = Modifier.size(56.dp).clip(RoundedCornerShape(OfferRadius.sm)),
                )
            } else {
                Box(Modifier.size(56.dp).clip(RoundedCornerShape(OfferRadius.sm)).background(c.surface))
            }
            Column(Modifier.weight(1f).padding(horizontal = 12.dp)) {
                Text(offer.listing.title, style = MaterialTheme.typography.bodySmall, color = c.muted, maxLines = 1, overflow = TextOverflow.Ellipsis)
                AnimatedAmount(
                    offer.amount_kobo,
                    MaterialTheme.typography.headlineSmall.copy(
                        fontWeight = FontWeight.SemiBold,
                        textDecoration = if (closed) TextDecoration.LineThrough else TextDecoration.None,
                    ),
                    if (closed) c.muted else c.text,
                )
                val off = OfferFormat.discountPercent(offer.amount_kobo, offer.listing_price_kobo)
                if (off > 0) {
                    Row {
                        Text(
                            OfferFormat.naira(offer.listing_price_kobo),
                            style = MaterialTheme.typography.bodySmall.copy(textDecoration = TextDecoration.LineThrough),
                            color = c.muted,
                        )
                        Text(" · $off% off", style = MaterialTheme.typography.bodySmall, color = c.muted)
                    }
                }
            }
            Column(horizontalAlignment = Alignment.End, verticalArrangement = Arrangement.spacedBy(6.dp)) {
                AnimatedContent(
                    targetState = state,
                    transitionSpec = { if (calm) fadeIn() togetherWith fadeOut() else (scaleIn(OfferMotion.standard(), 0.9f) + fadeIn()) togetherWith (scaleOut(targetScale = 0.9f) + fadeOut()) },
                    label = "chip",
                ) { s ->
                    val mm = meta(s)
                    // On the tide-tinted card the tide chip sits on the raised colour so it stays visible.
                    val (fg, chipBg) = when (mm.tone) {
                        Tone.Tide -> c.tideFg to c.raised
                        Tone.Ok -> c.ok to c.okBg
                        Tone.Caution -> c.caution to c.cautionBg
                        Tone.Danger -> c.danger to c.dangerBg
                        else -> c.muted to c.surface
                    }
                    val icon = mm.icon
                    val leading: (@Composable () -> Unit)? = if (icon != null) {
                        { Icon(icon, contentDescription = null, tint = fg, modifier = Modifier.size(13.dp)) }
                    } else null
                    StatusChip(mm.label, fg = fg, bg = chipBg, leading = leading)
                }
                if (state == OfferCardState.Pending || state == OfferCardState.PaymentFailed) {
                    CountdownChip(offer) { tick += 1 }
                }
                if (state == OfferCardState.Held || state == OfferCardState.HandedOver || state == OfferCardState.Released) {
                    Padlock(locked = true, play = playLock, tint = if (state == OfferCardState.Released) c.ok else c.tideFg)
                }
            }
        }

        if (offer.note.isNotBlank()) {
            Text(
                offer.note,
                style = MaterialTheme.typography.bodyMedium,
                color = c.text,
                modifier = Modifier.padding(top = 12.dp).fillMaxWidth().clip(RoundedCornerShape(OfferRadius.sm)).background(c.surface).padding(10.dp),
            )
        }
        Text(
            "Handover: " + if (offer.delivery_method.isNotBlank()) DELIVERY[offer.delivery_method]?.label.orEmpty()
            else offer.allowed_delivery_methods.mapNotNull { DELIVERY[it]?.label }.joinToString(" · "),
            style = MaterialTheme.typography.bodySmall,
            color = c.muted,
            modifier = Modifier.padding(top = 10.dp),
        )
        if (seller && offer.seller_net_kobo != null && !closed && state != OfferCardState.RefundPending) {
            Text(
                "You receive ${OfferFormat.naira(offer.seller_net_kobo)} after the Choropia fee",
                style = MaterialTheme.typography.bodySmall,
                color = c.muted,
            )
        }

        val step = when (state) {
            OfferCardState.Pending, OfferCardState.PaymentFailed, OfferCardState.Processing -> 0
            OfferCardState.Held -> 1
            OfferCardState.HandedOver -> 2
            OfferCardState.Released -> 3
            else -> -1
        }
        if (step >= 0) OfferStatusTimeline(step)

        // Guidance for this state.
        when {
            state == OfferCardState.PaymentFailed -> Guidance(if (buyer) "Nothing was taken. You can try again." else "The buyer's payment failed. The offer is still open.", c.danger)
            state == OfferCardState.Processing && seller -> Guidance("The buyer is paying now. This updates by itself.", c.muted)
            state == OfferCardState.Held && seller && offer.delivery_method != "rider" && offer.order_id != null ->
                SellerHandoverEntry(offer.order_id) { actions.onReleased(offer) }
            state == OfferCardState.Held && seller && offer.delivery_method == "rider" ->
                Guidance("A Choropia rider will pick it up. They take the buyer's code at delivery.", c.muted)
            (state == OfferCardState.Held || state == OfferCardState.HandedOver) && buyer && offer.order_id != null -> BuyerHandoverCode(offer.order_id)
            state == OfferCardState.Released -> Guidance(if (seller) "The buyer has the item. Your payout is being sent." else "All done. The seller has been paid.", c.ok)
            state == OfferCardState.RefundPending -> Guidance(if (buyer) "This payment couldn't be used, so it's being refunded to you automatically." else "The buyer's payment is being refunded.", c.caution)
            state == OfferCardState.Disputed -> Guidance("Choropia is reviewing this order. The money stays safe in escrow.", c.caution)
        }

        // Actions.
        if (buyer && (state == OfferCardState.Pending || state == OfferCardState.PaymentFailed)) {
            Row(Modifier.padding(top = 14.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                if (confirming == "decline") {
                    OfferButton(if (busy == "decline") "Declining…" else "Yes, decline", kind = OfferButtonKind.Danger, modifier = Modifier.weight(1f), enabled = busy == null,
                        onClick = { run("decline") { actions.onDecline(offer) } })
                    OfferButton("Keep it", kind = OfferButtonKind.Quiet, onClick = { confirming = null })
                } else {
                    OfferButton("Pay ${OfferFormat.naira(offer.amount_kobo)}", modifier = Modifier.weight(1f), onClick = { actions.onPay(offer) })
                    OfferButton("Decline", kind = OfferButtonKind.Quiet, onClick = { confirming = "decline" })
                }
            }
        }
        if (buyer && state == OfferCardState.Processing) {
            Row(Modifier.padding(top = 14.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                OfferButton("Continue payment", modifier = Modifier.weight(1f), onClick = { actions.onPay(offer) })
                OfferButton(if (busy == "check") "Checking…" else "I've paid", kind = OfferButtonKind.Link, enabled = busy == null,
                    onClick = { run("check") { actions.onCheckPayment(offer) } })
            }
        }
        if (seller && (state == OfferCardState.Pending || state == OfferCardState.PaymentFailed)) {
            Row(Modifier.padding(top = 14.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                if (confirming == "cancel") {
                    OfferButton(if (busy == "cancel") "Cancelling…" else "Yes, cancel offer", kind = OfferButtonKind.Danger, modifier = Modifier.weight(1f), enabled = busy == null,
                        onClick = { run("cancel") { actions.onCancel(offer) } })
                    OfferButton("Keep it", kind = OfferButtonKind.Quiet, onClick = { confirming = null })
                } else {
                    OfferButton("Cancel offer", kind = OfferButtonKind.Quiet, onClick = { confirming = "cancel" })
                }
            }
        }
        val orderId = offer.order_id
        if (orderId != null && state != OfferCardState.Pending && state != OfferCardState.PaymentFailed) {
            OfferButton("View order #$orderId", kind = OfferButtonKind.Link, onClick = { actions.onOpenOrder(orderId) }, modifier = Modifier.padding(top = 6.dp))
        }
    }
}

@Composable
private fun Guidance(text: String, color: Color) {
    Text(text, style = MaterialTheme.typography.bodyMedium, color = color, modifier = Modifier.padding(top = 12.dp))
}

/** Offered → Paid into escrow → Handed over → Released. */
@Composable
fun OfferStatusTimeline(step: Int) {
    val c = offerColors()
    val calm = rememberCalmMotion()
    val labels = listOf("Offered", "Paid into escrow", "Handed over", "Released")
    Row(
        Modifier
            .fillMaxWidth()
            .padding(top = 14.dp)
            .semantics(mergeDescendants = true) { contentDescription = "Progress: ${labels[step]}, step ${step + 1} of 4" },
    ) {
        labels.forEachIndexed { i, label ->
            Column(Modifier.weight(1f), horizontalAlignment = Alignment.CenterHorizontally) {
                Box(Modifier.fillMaxWidth().height(18.dp), contentAlignment = Alignment.Center) {
                    if (i > 0) {
                        // Left half of the line into this step: grey track, accent fill that grows on progress.
                        val fill by animateFloatAsState(if (i <= step) 1f else 0f, if (calm) tween(0) else OfferMotion.standard(), label = "seg")
                        Box(Modifier.align(Alignment.CenterStart).fillMaxWidth(0.5f).height(2.dp).background(c.hairline))
                        Box(Modifier.align(Alignment.CenterStart).fillMaxWidth(0.5f * fill).height(2.dp).background(c.accent))
                    }
                    if (i < labels.lastIndex) {
                        Box(Modifier.align(Alignment.CenterEnd).fillMaxWidth(0.5f).height(2.dp).background(if (i < step) c.accent else c.hairline))
                    }
                    Box(
                        Modifier
                            .size(18.dp)
                            .clip(CircleShape)
                            .background(if (i < step) c.accent else c.raised)
                            .border(2.dp, if (i <= step) c.accent else c.hairline, CircleShape),
                        contentAlignment = Alignment.Center,
                    ) {
                        if (i == step) Box(Modifier.size(6.dp).clip(CircleShape).background(c.accent))
                    }
                }
                Text(
                    label,
                    style = MaterialTheme.typography.labelSmall.copy(fontWeight = if (i == step) FontWeight.SemiBold else FontWeight.Normal),
                    color = if (i == step) c.text else c.muted,
                    maxLines = 2,
                    modifier = Modifier.padding(top = 4.dp),
                )
            }
        }
    }
}

/** Time left, counted on the server's clock. Under an hour it turns to the caution colour and counts seconds. */
@Composable
fun CountdownChip(offer: ChatOffer, onExpire: () -> Unit) {
    val c = offerColors()
    val skew = remember(offer.server_now) { skewMs(offer) }
    val expires = remember(offer.expires_at) { epochMs(offer.expires_at) } ?: return
    var left by remember { mutableLongStateOf(((expires - (System.currentTimeMillis() + skew)) / 1000).coerceAtLeast(0)) }
    LaunchedEffect(expires, skew) {
        while (true) {
            left = ((expires - (System.currentTimeMillis() + skew)) / 1000).coerceAtLeast(0)
            if (left == 0L) { onExpire(); break }
            delay(1_000)
        }
    }
    val soon = left < 3600
    val text = when {
        left == 0L -> "Expired"
        soon -> OfferFormat.clock(left)
        left >= 7200 -> "${left / 3600}h left"
        else -> "${left / 60}m left"
    }
    val spoken = if (soon) "Expires in ${(left + 59) / 60} minutes" else "Expires in about ${(left + 1800) / 3600} hours"
    StatusChip(
        text,
        fg = if (soon) c.caution else c.muted,
        bg = if (soon) c.cautionBg else c.surface,
        modifier = Modifier.semantics { contentDescription = spoken },
        leading = { Icon(Icons.Outlined.Schedule, contentDescription = null, tint = if (soon) c.caution else c.muted, modifier = Modifier.size(12.dp)) },
    )
}

/**
 * The escrow padlock, drawn so the shackle can move: when [play] turns true the open shackle drops into the body and
 * the lock settles with a small spring dip. That's the moment money is held. No movement with animations off.
 */
@Composable
fun Padlock(locked: Boolean, play: Boolean, tint: Color, size: Dp = 26.dp) {
    val calm = rememberCalmMotion()
    val haptic = LocalHapticFeedback.current
    val shackle = remember { Animatable(if (locked && !play) 1f else 0f) } // 0 open, 1 closed
    val settle = remember { Animatable(1f) }
    LaunchedEffect(locked, play) {
        if (!locked) { shackle.snapTo(0f); return@LaunchedEffect }
        if (!play || calm) { shackle.snapTo(1f); return@LaunchedEffect }
        delay(120) // let the card morph first
        shackle.animateTo(1f, OfferMotion.settle())
        haptic.performHapticFeedback(HapticFeedbackType.LongPress)
        settle.animateTo(0.9f, tween(90))
        settle.animateTo(1f, OfferMotion.settle())
    }
    Canvas(
        Modifier
            .size(size)
            .graphicsLayer { scaleX = settle.value; scaleY = settle.value }
            .semantics { contentDescription = if (locked) "Money held in escrow" else "Not yet paid" },
    ) {
        val u = this.size.width / 24f
        val stroke = Stroke(width = 1.75f * u, cap = StrokeCap.Round)
        val open = 1f - shackle.value
        // shackle: raised and swung open, or seated
        translate(top = -2.5f * u * open) {
            rotate(degrees = -8f * open, pivot = Offset(16.5f * u, 11f * u)) {
                drawArc(tint, 180f, 180f, false, topLeft = Offset(7.5f * u, 3f * u), size = Size(9f * u, 9f * u), style = stroke)
                drawLine(tint, Offset(7.5f * u, 7.5f * u), Offset(7.5f * u, 11f * u), stroke.width, StrokeCap.Round)
                drawLine(tint, Offset(16.5f * u, 7.5f * u), Offset(16.5f * u, 11f * u), stroke.width, StrokeCap.Round)
            }
        }
        drawRoundRect(tint, topLeft = Offset(4.5f * u, 11f * u), size = Size(15f * u, 10f * u), cornerRadius = CornerRadius(2.5f * u), style = stroke)
        drawCircle(tint.copy(alpha = 0.35f + 0.65f * shackle.value), radius = 1.4f * u, center = Offset(12f * u, 16f * u))
    }
}

/** Buyer: the code to give the seller (or rider) once they hold the item. Hidden until revealed. */
@Composable
fun BuyerHandoverCode(orderId: Int) {
    val c = offerColors()
    val repo = LocalRepository.current
    var code by remember { mutableStateOf<HandoverCode?>(null) }
    var error by remember { mutableStateOf<String?>(null) }
    var shown by remember { mutableStateOf(false) }
    var attempt by remember { mutableStateOf(0) }
    LaunchedEffect(orderId, attempt) {
        error = null
        try { code = repo.handoverCode(orderId) } catch (e: ApiException) { error = e.message ?: "Your code couldn't be loaded." }
    }
    val box = Modifier
        .padding(top = 14.dp)
        .fillMaxWidth()
        .clip(RoundedCornerShape(OfferRadius.md))
        .background(c.surface)
        .border(1.dp, c.hairline, RoundedCornerShape(OfferRadius.md))
        .padding(14.dp)
    val current = code
    when {
        error != null -> Column(box) {
            Text(error.orEmpty(), color = c.muted, style = MaterialTheme.typography.bodySmall)
            OfferButton("Try again", kind = OfferButtonKind.Link, onClick = { attempt += 1 })
        }
        current == null -> Box(box.height(48.dp))
        current.used || current.code == null -> Unit
        else -> Column(box) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Icon(Icons.Outlined.Lock, contentDescription = null, tint = c.text, modifier = Modifier.size(16.dp))
                Text("  Your handover code", style = MaterialTheme.typography.labelLarge, color = c.text)
            }
            Text(
                "Only tell ${if (current.entered_by == "rider") "the rider" else "the seller"} this code once you have the item and you're happy with it. It releases the money.",
                style = MaterialTheme.typography.bodySmall,
                color = c.muted,
                modifier = Modifier.padding(top = 4.dp),
            )
            Row(Modifier.padding(top = 10.dp).fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                Text(
                    if (shown) current.code.toCharArray().joinToString(" ") else "• • • • • •",
                    style = MaterialTheme.typography.headlineSmall.copy(fontFamily = FontFamily.Monospace, fontWeight = FontWeight.SemiBold),
                    color = c.text,
                    modifier = Modifier.weight(1f).semantics {
                        contentDescription = if (shown) "Code: ${current.code.toCharArray().joinToString(" ")}" else "Code hidden"
                        liveRegion = LiveRegionMode.Polite
                    },
                )
                OfferButton(if (shown) "Hide" else "Show code", kind = OfferButtonKind.Link, onClick = { shown = !shown })
            }
        }
    }
}

/** Seller (meet-up / seller delivers): type the buyer's code after handing over. The right code releases escrow. */
@Composable
fun SellerHandoverEntry(orderId: Int, onReleased: () -> Unit) {
    val c = offerColors()
    val calm = rememberCalmMotion()
    val repo = LocalRepository.current
    val scope = rememberCoroutineScope()
    val haptic = LocalHapticFeedback.current
    var code by remember { mutableStateOf("") }
    var error by remember { mutableStateOf<String?>(null) }
    var busy by remember { mutableStateOf(false) }
    var locked by remember { mutableStateOf(false) }
    val shake = remember { Animatable(0f) }

    fun submit(entered: String) = scope.launch {
        busy = true
        error = null
        try {
            repo.confirmHandover(orderId, entered)
            haptic.performHapticFeedback(HapticFeedbackType.LongPress)
            onReleased()
        } catch (e: ApiException) {
            code = ""
            locked = e.code == "code_locked"
            error = e.message
            haptic.performHapticFeedback(HapticFeedbackType.LongPress)
            if (!calm) {
                shake.snapTo(0f)
                shake.animateTo(0f, androidx.compose.animation.core.keyframes { durationMillis = 380; -8f at 40; 7f at 100; -4f at 170; 2f at 240 })
            }
        } finally {
            busy = false
        }
    }

    Column(
        Modifier
            .padding(top = 14.dp)
            .fillMaxWidth()
            .clip(RoundedCornerShape(OfferRadius.md))
            .background(c.surface)
            .border(1.dp, c.hairline, RoundedCornerShape(OfferRadius.md))
            .padding(14.dp),
    ) {
        Text("Handed it over? Enter the buyer's code", style = MaterialTheme.typography.labelLarge, color = c.text)
        Text("The buyer sees a 6-digit code once they have the item. It releases your money.", style = MaterialTheme.typography.bodySmall, color = c.muted)
        OutlinedTextField(
            value = code,
            onValueChange = { raw ->
                val clean = raw.filter { it.isDigit() }.take(6)
                code = clean
                error = null
                if (clean.length == 6 && !busy) submit(clean)
            },
            enabled = !busy && !locked,
            singleLine = true,
            label = { Text("6-digit code") },
            textStyle = MaterialTheme.typography.titleLarge.copy(fontFamily = FontFamily.Monospace, fontWeight = FontWeight.SemiBold),
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.NumberPassword),
            modifier = Modifier
                .padding(top = 10.dp)
                .fillMaxWidth()
                .graphicsLayer { translationX = shake.value * density },
        )
        InlineError(error)
        if (busy) Text("Checking the code…", style = MaterialTheme.typography.bodySmall, color = c.muted, modifier = Modifier.padding(top = 6.dp))
    }
}

/**
 * Buyer: choose how to receive the item, then pay the locked price into escrow through Paystack. The buyer never sees
 * Choropia's fee. A rider order continues on the order page to pick the rider and drop-off.
 */
@Composable
fun PaySheet(offer: ChatOffer, onDismiss: () -> Unit, onCheckout: (OfferCheckoutResponse) -> Unit) {
    val c = offerColors()
    val repo = LocalRepository.current
    val scope = rememberCoroutineScope()
    val sheetState = rememberModalBottomSheetState(skipPartiallyExpanded = true)
    val locked = offer.status == "payment_processing" && offer.delivery_method.isNotBlank()
    var method by remember { mutableStateOf(offer.delivery_method.ifBlank { offer.allowed_delivery_methods.firstOrNull() ?: "meetup" }) }
    var error by remember { mutableStateOf<String?>(null) }
    var busy by remember { mutableStateOf(false) }
    val rider = method == "rider"

    ModalBottomSheet(
        onDismissRequest = { if (!busy) onDismiss() },
        sheetState = sheetState,
        containerColor = c.raised,
        shape = RoundedCornerShape(topStart = OfferRadius.lg, topEnd = OfferRadius.lg),
    ) {
        Column(
            Modifier
                .fillMaxWidth()
                .verticalScroll(rememberScrollState())
                .padding(horizontal = 20.dp)
                .padding(bottom = 24.dp)
                .navigationBarsPadding(),
            verticalArrangement = Arrangement.spacedBy(16.dp),
        ) {
            Column {
                Text("Pay into escrow", style = MaterialTheme.typography.titleLarge, color = c.text)
                Text(offer.listing.title, style = MaterialTheme.typography.bodySmall, color = c.muted, maxLines = 1, overflow = TextOverflow.Ellipsis)
            }
            DeliveryMethodPicker(
                legend = if (locked) "Handover (chosen at checkout)" else "How do you want to receive it?",
                multiple = false,
                options = if (locked) listOf(offer.delivery_method) else offer.allowed_delivery_methods,
                selected = setOf(method),
                onChange = { picked -> picked.firstOrNull()?.let { method = it } },
            )
            Column(
                Modifier
                    .fillMaxWidth()
                    .clip(RoundedCornerShape(OfferRadius.md))
                    .background(c.surface)
                    .padding(16.dp),
                verticalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                Row {
                    Text("Price agreed with the seller", color = c.muted, style = MaterialTheme.typography.bodyMedium, modifier = Modifier.weight(1f))
                    Text(OfferFormat.naira(offer.amount_kobo), color = c.text, style = MaterialTheme.typography.bodyMedium.copy(fontFeatureSettings = "tnum"))
                }
                if (rider) {
                    Row {
                        Text("Rider delivery", color = c.muted, style = MaterialTheme.typography.bodyMedium, modifier = Modifier.weight(1f))
                        Text(if (offer.delivery_fee_kobo > 0) OfferFormat.naira(offer.delivery_fee_kobo) else "Chosen next", color = c.muted, style = MaterialTheme.typography.bodyMedium)
                    }
                }
                androidx.compose.material3.HorizontalDivider(color = c.hairline)
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text(if (rider && offer.delivery_fee_kobo == 0L) "To pay now (before delivery)" else "You pay", color = c.text, style = MaterialTheme.typography.titleSmall, modifier = Modifier.weight(1f))
                    Text(
                        OfferFormat.naira(offer.amount_kobo + if (rider) offer.delivery_fee_kobo else 0),
                        color = c.text,
                        style = MaterialTheme.typography.titleLarge.copy(fontWeight = FontWeight.SemiBold, fontFeatureSettings = "tnum"),
                    )
                }
            }
            Row(verticalAlignment = Alignment.Top) {
                Icon(Icons.Outlined.Lock, contentDescription = null, tint = c.muted, modifier = Modifier.size(14.dp).padding(top = 2.dp))
                Spacer(Modifier.width(6.dp))
                Text(
                    "Your money is held by Choropia and only released to the seller after you have the item. If the deal falls through before handover, you get a full refund.",
                    style = MaterialTheme.typography.bodySmall,
                    color = c.muted,
                )
            }
            InlineError(error)
            OfferButton(
                if (rider) "Continue to delivery" else "Pay ${OfferFormat.naira(offer.amount_kobo)} securely",
                modifier = Modifier.fillMaxWidth(),
                loading = busy,
                onClick = {
                    scope.launch {
                        busy = true
                        error = null
                        try {
                            onCheckout(repo.checkoutOffer(offer.id, method))
                        } catch (e: ApiException) {
                            error = if (e.code == "expired") "This offer has expired. Ask the seller for a new one." else e.message
                        } finally {
                            busy = false
                        }
                    }
                },
            )
            Text("Card, bank transfer or USSD via Paystack", style = MaterialTheme.typography.bodySmall, color = c.muted, modifier = Modifier.align(Alignment.CenterHorizontally))
        }
    }
}
