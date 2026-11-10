package com.choropia.app.ui.offers

import androidx.compose.animation.AnimatedContent
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.core.Animatable
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.scaleIn
import androidx.compose.animation.scaleOut
import androidx.compose.animation.slideInHorizontally
import androidx.compose.animation.slideOutHorizontally
import androidx.compose.animation.togetherWith
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.selection.selectable
import androidx.compose.foundation.selection.toggleable
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.BasicTextField
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.Check
import androidx.compose.material.icons.outlined.LocalShipping
import androidx.compose.material.icons.outlined.Place
import androidx.compose.material.icons.outlined.TwoWheeler
import androidx.compose.material.icons.outlined.Verified
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.rememberModalBottomSheetState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.SolidColor
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.semantics.LiveRegionMode
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.liveRegion
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.style.TextDecoration
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import com.choropia.app.data.model.ChatOffer
import com.choropia.app.data.model.FeePreview
import com.choropia.app.data.model.Listing
import com.choropia.app.data.model.PinStatus
import com.choropia.app.data.network.ApiException
import com.choropia.app.ui.LocalRepository
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch

data class DeliveryInfo(val label: String, val hint: String, val icon: ImageVector)

val DELIVERY: Map<String, DeliveryInfo> = linkedMapOf(
    "meetup" to DeliveryInfo("Meet up", "Hand it over in person", Icons.Outlined.Place),
    "seller_delivers" to DeliveryInfo("Seller delivers", "The seller brings it to you", Icons.Outlined.LocalShipping),
    "rider" to DeliveryInfo("Choropia rider", "A rider delivers it; delivery fee extra", Icons.Outlined.TwoWheeler),
)

/** The offer amount: ₦ prefix, grouping as you type, tabular digits, listed price struck through, "% off" chip. */
@Composable
fun AmountField(text: String, onTextChange: (String) -> Unit, listedKobo: Long, invalid: Boolean) {
    val c = offerColors()
    val kobo = OfferFormat.parse(text)
    val off = kobo?.let { OfferFormat.discountPercent(it, listedKobo) } ?: 0
    val tooHigh = kobo != null && kobo > listedKobo
    Column {
        Text("Your price", style = MaterialTheme.typography.labelLarge, color = c.text)
        Row(
            Modifier
                .padding(top = 6.dp)
                .fillMaxWidth()
                .clip(RoundedCornerShape(OfferRadius.md))
                .background(c.raised)
                .border(1.dp, if (invalid || tooHigh) c.danger else c.hairline, RoundedCornerShape(OfferRadius.md))
                .padding(horizontal = 16.dp, vertical = 14.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Text("₦", style = MaterialTheme.typography.headlineSmall, color = c.muted)
            Spacer(Modifier.width(8.dp))
            BasicTextField(
                value = text,
                onValueChange = { onTextChange(OfferFormat.tidy(it)) },
                singleLine = true,
                textStyle = MaterialTheme.typography.headlineSmall.copy(color = c.text, fontWeight = FontWeight.SemiBold, fontFeatureSettings = "tnum"),
                cursorBrush = SolidColor(c.accent),
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal),
                modifier = Modifier
                    .weight(1f)
                    .semantics { contentDescription = "Your price in naira. Listed at ${OfferFormat.spoken(listedKobo)}" },
            )
            AnimatedVisibility(visible = off > 0 && !tooHigh, enter = scaleIn(OfferMotion.snappy()) + fadeIn(), exit = scaleOut() + fadeOut()) {
                StatusChip("$off% off", fg = c.tideFg, bg = c.tide)
            }
        }
        Row(Modifier.padding(top = 6.dp)) {
            Text("Listed at ", style = MaterialTheme.typography.bodySmall, color = c.muted)
            Text(
                OfferFormat.naira(listedKobo),
                style = MaterialTheme.typography.bodySmall.copy(textDecoration = TextDecoration.LineThrough, fontFeatureSettings = "tnum"),
                color = c.muted,
            )
            Text(
                if (tooHigh) " · Can't be higher than the listed price." else " · You can lower it, never raise it.",
                style = MaterialTheme.typography.bodySmall,
                color = if (tooHigh) c.danger else c.muted,
            )
        }
    }
}

/** Seller only: offer price, Choropia's fee and "You receive", from the same server function that locks the fee. */
@Composable
fun FeeBreakdown(amountKobo: Long?, verified: Boolean) {
    val c = offerColors()
    val calm = rememberCalmMotion()
    val repo = LocalRepository.current
    var preview by remember { mutableStateOf<FeePreview?>(null) }
    var failed by remember { mutableStateOf(false) }

    LaunchedEffect(amountKobo, verified) {
        if (amountKobo == null || amountKobo <= 0) return@LaunchedEffect
        delay(250) // let typing settle
        try {
            preview = repo.feePreview(amountKobo, verified)
            failed = false
        } catch (e: ApiException) {
            failed = true
        }
    }
    if (amountKobo == null || amountKobo <= 0) return

    val p = preview
    Column(
        Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(OfferRadius.md))
            .background(c.surface)
            .padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        when {
            p == null && failed -> Text(
                "Couldn't load the fee just now. It's worked out when you send the offer.",
                color = c.muted, style = MaterialTheme.typography.bodyMedium,
            )
            p == null -> repeat(3) {
                Box(Modifier.fillMaxWidth().height(16.dp).clip(RoundedCornerShape(4.dp)).background(c.hairline))
            }
            else -> {
                FeeRow(0, calm, "Offer price") { AnimatedAmount(amountKobo, MaterialTheme.typography.bodyMedium, c.text) }
                FeeRow(1, calm, "Choropia fee", badge = verified) {
                    Row { Text("− ", color = c.text); AnimatedAmount(p.fee_kobo, MaterialTheme.typography.bodyMedium, c.text) }
                }
                HorizontalDivider(color = c.hairline)
                FeeRow(2, calm, "You receive", strong = true) {
                    AnimatedAmount(p.seller_net_kobo, MaterialTheme.typography.titleMedium.copy(fontWeight = FontWeight.SemiBold), c.text)
                }
                Text(
                    "You receive ${OfferFormat.spoken(p.seller_net_kobo)} after a ${OfferFormat.spoken(p.fee_kobo)} fee.",
                    modifier = Modifier.size(0.dp).semantics { liveRegion = LiveRegionMode.Polite },
                )
            }
        }
    }
}

@Composable
private fun FeeRow(index: Int, calm: Boolean, label: String, badge: Boolean = false, strong: Boolean = false, value: @Composable () -> Unit) {
    val c = offerColors()
    val appear = remember { Animatable(if (calm) 1f else 0f) }
    LaunchedEffect(Unit) {
        if (!calm) {
            delay(index * 40L) // staggered entrance
            appear.animateTo(1f, OfferMotion.standard())
        }
    }
    Row(
        Modifier.fillMaxWidth().graphicsLayer { alpha = appear.value; translationY = (1f - appear.value) * 12f },
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Text(
            label,
            color = if (strong) c.text else c.muted,
            style = if (strong) MaterialTheme.typography.titleSmall else MaterialTheme.typography.bodyMedium,
            modifier = Modifier.weight(1f),
        )
        if (badge) {
            StatusChip("Verified rate", fg = c.tideFg, bg = c.tide, leading = {
                Icon(Icons.Outlined.Verified, contentDescription = null, tint = c.tideFg, modifier = Modifier.size(12.dp))
            })
            Spacer(Modifier.width(8.dp))
        }
        value()
    }
}

/** Handover methods: several (seller making the offer) or exactly one (buyer paying). */
@Composable
fun DeliveryMethodPicker(
    legend: String,
    multiple: Boolean,
    options: List<String>,
    selected: Set<String>,
    onChange: (Set<String>) -> Unit,
    unavailable: Set<String> = emptySet(),
) {
    val c = offerColors()
    val calm = rememberCalmMotion()
    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        Text(legend, style = MaterialTheme.typography.labelLarge, color = c.text)
        DELIVERY.keys.filter { it in options }.forEach { method ->
            val info = DELIVERY.getValue(method)
            val checked = method in selected
            val off = method in unavailable
            val interaction = remember { MutableInteractionSource() }
            val shape = RoundedCornerShape(OfferRadius.md)
            val base = Modifier
                .fillMaxWidth()
                .heightIn(min = 56.dp)
                .pressScale(interaction, calm)
                .clip(shape)
                .background(if (checked) c.tide else c.raised)
                .border(1.dp, if (checked) c.accent else c.hairline, shape)
            val clickable = if (multiple) {
                base.toggleable(value = checked, enabled = !off, role = Role.Checkbox, interactionSource = interaction, indication = androidx.compose.foundation.LocalIndication.current) {
                    onChange(if (it) selected + method else selected - method)
                }
            } else {
                base.selectable(selected = checked, enabled = !off, role = Role.RadioButton, interactionSource = interaction, indication = androidx.compose.foundation.LocalIndication.current) {
                    onChange(setOf(method))
                }
            }
            Row(
                clickable.graphicsLayer { alpha = if (off) 0.45f else 1f }.padding(horizontal = 16.dp, vertical = 12.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Icon(info.icon, contentDescription = null, tint = if (checked) c.tideFg else c.muted)
                Column(Modifier.weight(1f).padding(horizontal = 12.dp)) {
                    Text(info.label, style = MaterialTheme.typography.bodyMedium.copy(fontWeight = FontWeight.Medium), color = c.text)
                    Text(if (off) "Not set up for this listing" else info.hint, style = MaterialTheme.typography.bodySmall, color = c.muted)
                }
                Box(
                    Modifier
                        .size(20.dp)
                        .clip(if (multiple) RoundedCornerShape(6.dp) else CircleShape)
                        .background(if (checked) c.accent else c.raised)
                        .border(2.dp, if (checked) c.accent else c.hairline, if (multiple) RoundedCornerShape(6.dp) else CircleShape),
                    contentAlignment = Alignment.Center,
                ) {
                    if (checked) Icon(Icons.Outlined.Check, contentDescription = null, tint = c.accentFg, modifier = Modifier.size(14.dp))
                }
            }
        }
    }
}

/**
 * Seller: offer a listing at a lower, locked price, approved with the transaction PIN. With no PIN yet, setting one
 * comes first. Material's bottom sheet springs up and follows the finger when dragged down to dismiss.
 */
@Composable
fun OfferComposerSheet(
    conversationId: Int,
    listings: List<Listing>,
    defaultListingId: Int?,
    sellerVerified: Boolean,
    onDismiss: () -> Unit,
    onSent: (ChatOffer) -> Unit,
) {
    val c = offerColors()
    val calm = rememberCalmMotion()
    val repo = LocalRepository.current
    val scope = rememberCoroutineScope()
    val sheetState = rememberModalBottomSheetState(skipPartiallyExpanded = true)

    var pinStatus by remember { mutableStateOf<PinStatus?>(null) }
    var listing by remember { mutableStateOf(listings.firstOrNull { it.id == defaultListingId } ?: listings.firstOrNull()) }
    var listingMenu by remember { mutableStateOf(false) }
    var amountText by remember { mutableStateOf(listing?.let { OfferFormat.input(OfferFormat.koboFromNairaString(it.price)) } ?: "") }
    var methods by remember { mutableStateOf(setOf("meetup")) }
    var riderReady by remember { mutableStateOf(false) }
    var note by remember { mutableStateOf("") }
    var pin by remember { mutableStateOf("") }
    var step by remember { mutableStateOf("loading") }
    var error by remember { mutableStateOf<String?>(null) }
    var pinError by remember { mutableStateOf<String?>(null) }
    var errorTick by remember { mutableIntStateOf(0) }
    var lockSeconds by remember { mutableStateOf<Long?>(null) }
    var sending by remember { mutableStateOf(false) }
    val lockedFor = rememberCountdown(lockSeconds)

    LaunchedEffect(Unit) {
        try {
            val status = repo.pinStatus()
            pinStatus = status
            if (status.locked) lockSeconds = status.retry_after
            step = if (status.has_pin) "compose" else "setup"
        } catch (e: ApiException) {
            error = e.message
            step = "compose"
        }
    }
    LaunchedEffect(listing?.id) {
        val id = listing?.id ?: return@LaunchedEffect
        riderReady = runCatching { repo.listingDelivery(id).enabled }.getOrDefault(false)
        if (!riderReady) methods = methods - "rider"
    }

    val listedKobo = listing?.let { OfferFormat.koboFromNairaString(it.price) } ?: 0L
    val amountKobo = OfferFormat.parse(amountText)
    val amountValid = amountKobo != null && amountKobo > 0 && amountKobo <= listedKobo
    val pinLength = pinStatus?.length ?: 4

    fun send(entered: String) = scope.launch {
        val l = listing ?: return@launch
        val amount = amountKobo ?: return@launch
        sending = true
        pinError = null
        try {
            onSent(repo.createOffer(conversationId, l.id, amount, methods.toList(), note, entered))
        } catch (e: ApiException) {
            pin = ""
            when (e.code) {
                "pin_invalid" -> {
                    val left = e.numbers["attempts_left"]
                    pinError = if (left != null) "That PIN is not right. $left ${if (left == 1L) "try" else "tries"} left." else e.message
                    errorTick += 1
                }
                "pin_locked" -> {
                    lockSeconds = e.numbers["retry_after"] ?: 900
                    errorTick += 1
                }
                else -> {
                    step = "compose"
                    error = e.message
                }
            }
        } finally {
            sending = false
        }
    }

    val title = when (step) {
        "pin" -> "Approve with your PIN"
        "setup" -> "Set a transaction PIN"
        "reset" -> "Reset your PIN"
        else -> "Offer a different price"
    }

    ModalBottomSheet(
        onDismissRequest = { if (!sending) onDismiss() },
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
        ) {
            Text(title, style = MaterialTheme.typography.titleLarge, color = c.text, modifier = Modifier.semantics { liveRegion = LiveRegionMode.Polite })
            if (step == "compose") {
                Text("Only this buyer sees it. Your listing price doesn't change.", style = MaterialTheme.typography.bodySmall, color = c.muted)
            }
            Spacer(Modifier.height(16.dp))

            AnimatedContent(
                targetState = step,
                transitionSpec = {
                    if (calm) fadeIn() togetherWith fadeOut()
                    else (slideInHorizontally(OfferMotion.standard()) { it / 6 } + fadeIn()) togetherWith
                        (slideOutHorizontally(OfferMotion.standard()) { -it / 6 } + fadeOut())
                },
                label = "composer-step",
            ) { current ->
                when (current) {
                    "loading" -> Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                        repeat(3) { Box(Modifier.fillMaxWidth().height(56.dp).clip(RoundedCornerShape(OfferRadius.md)).background(c.surface)) }
                    }
                    "setup", "reset" -> PinSetupFlow(reset = current == "reset", length = pinLength, onDone = { status ->
                        pinStatus = status
                        lockSeconds = null
                        pin = ""
                        pinError = null
                        step = if (current == "reset") "pin" else "compose"
                    })
                    "compose" -> Column(verticalArrangement = Arrangement.spacedBy(18.dp)) {
                        if (listings.size > 1) {
                            Box {
                                OutlinedTextField(
                                    value = listing?.title.orEmpty(),
                                    onValueChange = {},
                                    readOnly = true,
                                    label = { Text("Listing") },
                                    modifier = Modifier.fillMaxWidth(),
                                )
                                Box(Modifier.matchParentSizeClickable { listingMenu = true })
                                DropdownMenu(expanded = listingMenu, onDismissRequest = { listingMenu = false }) {
                                    listings.forEach { l ->
                                        DropdownMenuItem(
                                            text = { Text(l.title, maxLines = 1, overflow = TextOverflow.Ellipsis) },
                                            onClick = {
                                                listing = l
                                                amountText = OfferFormat.input(OfferFormat.koboFromNairaString(l.price))
                                                listingMenu = false
                                            },
                                        )
                                    }
                                }
                            }
                        } else {
                            Text(listing?.title.orEmpty(), style = MaterialTheme.typography.titleSmall, color = c.text, maxLines = 1, overflow = TextOverflow.Ellipsis)
                        }
                        AmountField(amountText, { amountText = it; error = null }, listedKobo, invalid = error != null)
                        FeeBreakdown(if (amountValid) amountKobo else null, sellerVerified)
                        DeliveryMethodPicker(
                            legend = "How can it be handed over?",
                            multiple = true,
                            options = DELIVERY.keys.toList(),
                            selected = methods,
                            onChange = { methods = it; error = null },
                            unavailable = if (riderReady) emptySet() else setOf("rider"),
                        )
                        OutlinedTextField(
                            value = note,
                            onValueChange = { if (it.length <= 300) note = it },
                            label = { Text("Note (optional)") },
                            placeholder = { Text("e.g. Final price, comes with the charger") },
                            modifier = Modifier.fillMaxWidth(),
                        )
                        InlineError(error)
                        Text(
                            "The offer is valid for 24 hours. The buyer pays into Choropia escrow; you're paid once they confirm they have it.",
                            style = MaterialTheme.typography.bodySmall,
                            color = c.muted,
                        )
                        OfferButton("Continue", modifier = Modifier.fillMaxWidth(), onClick = {
                            error = when {
                                listing == null -> "Choose a listing."
                                methods.isEmpty() -> "Choose at least one way to hand the item over."
                                amountKobo != null && amountKobo > listedKobo -> "An offer can't be higher than ${OfferFormat.naira(listedKobo)}."
                                !amountValid -> "Enter the price you're offering."
                                else -> null
                            }
                            if (error == null) {
                                pin = ""
                                pinError = null
                                step = "pin"
                            }
                        })
                    }
                    else -> Column(horizontalAlignment = Alignment.CenterHorizontally) {
                        Row(Modifier.fillMaxWidth()) {
                            OfferButton("Edit offer", kind = OfferButtonKind.Quiet, enabled = !sending, onClick = { step = "compose" })
                        }
                        if (listing != null && amountKobo != null) {
                            Text(
                                "${OfferFormat.naira(amountKobo)} for ${listing?.title}",
                                style = MaterialTheme.typography.bodyMedium,
                                color = c.muted,
                                modifier = Modifier.padding(bottom = 12.dp),
                            )
                        }
                        PinPad(
                            value = pin,
                            onValueChange = { pin = it; if (it.isNotEmpty()) pinError = null },
                            onComplete = { send(it) },
                            label = "Enter your transaction PIN",
                            length = pinLength,
                            errorTick = errorTick,
                            error = pinError != null,
                            enabled = !sending,
                            lockedForSeconds = lockedFor,
                        )
                        InlineError(pinError)
                        if (sending) Text("Sending your offer…", color = c.muted, style = MaterialTheme.typography.bodySmall, modifier = Modifier.padding(top = 12.dp))
                        OfferButton("Forgot PIN?", kind = OfferButtonKind.Link, onClick = { step = "reset" }, modifier = Modifier.padding(top = 8.dp))
                    }
                }
            }
        }
    }
}

/** An invisible full-size click target laid over a read-only field (so the whole field opens the menu). */
@Composable
private fun Modifier.matchParentSizeClickable(onClick: () -> Unit): Modifier =
    this.then(Modifier.fillMaxWidth().height(64.dp)).then(
        Modifier.selectable(selected = false, role = Role.Button, onClick = onClick),
    )
