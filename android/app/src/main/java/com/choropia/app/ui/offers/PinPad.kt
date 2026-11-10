package com.choropia.app.ui.offers

import androidx.compose.animation.AnimatedContent
import androidx.compose.animation.core.Animatable
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.keyframes
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.slideInHorizontally
import androidx.compose.animation.slideOutHorizontally
import androidx.compose.animation.togetherWith
import androidx.compose.foundation.LocalIndication
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.offset
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.outlined.Backspace
import androidx.compose.material.icons.outlined.Lock
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.produceState
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.hapticfeedback.HapticFeedbackType
import androidx.compose.ui.platform.LocalHapticFeedback
import androidx.compose.ui.semantics.LiveRegionMode
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.liveRegion
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.IntOffset
import androidx.compose.ui.unit.dp
import com.choropia.app.data.model.PinStatus
import com.choropia.app.data.network.ApiException
import com.choropia.app.ui.LocalRepository
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch

/** Seconds left, ticking down once a second from [seconds]; null when there is no lock. */
@Composable
fun rememberCountdown(seconds: Long?): Long? {
    val left by produceState<Long?>(initialValue = seconds, seconds) {
        value = seconds
        var s = seconds ?: return@produceState
        while (s > 0) {
            delay(1_000)
            s -= 1
            value = s
        }
    }
    return left
}

/**
 * PIN entry: dots plus a keypad. [errorTick] changes on every wrong PIN: the dots shake and the phone gives a firm
 * haptic (with animations off the dots just turn red and a lock icon shows). [lockedForSeconds] replaces the keypad
 * with a countdown.
 */
@Composable
fun PinPad(
    value: String,
    onValueChange: (String) -> Unit,
    onComplete: (String) -> Unit,
    label: String,
    modifier: Modifier = Modifier,
    length: Int = 4,
    errorTick: Int = 0,
    error: Boolean = false,
    enabled: Boolean = true,
    lockedForSeconds: Long? = null,
) {
    val c = offerColors()
    val calm = rememberCalmMotion()
    val haptic = LocalHapticFeedback.current
    val shake = remember { Animatable(0f) }
    val locked = (lockedForSeconds ?: 0) > 0

    LaunchedEffect(errorTick) {
        if (errorTick == 0) return@LaunchedEffect
        haptic.performHapticFeedback(HapticFeedbackType.LongPress)
        if (!calm) {
            shake.snapTo(0f)
            shake.animateTo(0f, keyframes {
                durationMillis = 420
                -10f at 40
                9f at 100
                -6f at 170
                4f at 240
                -2f at 310
            })
        }
    }

    fun type(next: String) {
        val clean = next.filter { it.isDigit() }.take(length)
        if (clean == value) return
        if (clean.length > value.length) haptic.performHapticFeedback(HapticFeedbackType.TextHandleMove)
        onValueChange(clean)
        if (clean.length == length) onComplete(clean)
    }

    Column(modifier.fillMaxWidth(), horizontalAlignment = Alignment.CenterHorizontally) {
        Text(label, style = MaterialTheme.typography.titleSmall, color = c.text, modifier = Modifier.semantics { heading() })
        Row(
            Modifier
                .padding(top = 16.dp)
                .offset { IntOffset(shake.value.dp.roundToPx(), 0) }
                .semantics {
                    contentDescription = if (locked) "PIN locked" else "${value.length} of $length digits entered"
                    liveRegion = LiveRegionMode.Polite
                },
            horizontalArrangement = Arrangement.spacedBy(16.dp),
        ) {
            repeat(length) { i ->
                val filled = i < value.length
                val fill by animateFloatAsState(
                    targetValue = if (filled) 1f else 0f,
                    animationSpec = if (calm) androidx.compose.animation.core.snap() else androidx.compose.animation.core.spring(dampingRatio = 0.45f, stiffness = 700f),
                    label = "dot",
                )
                val ring = if (error) c.danger else c.accent
                Box(Modifier.size(14.dp).border(2.dp, ring, CircleShape), contentAlignment = Alignment.Center) {
                    Box(
                        Modifier
                            .size(14.dp)
                            .graphicsLayer { scaleX = fill; scaleY = fill }
                            .clip(CircleShape)
                            .background(ring),
                    )
                }
            }
        }
        if (error && calm) {
            Row(Modifier.padding(top = 10.dp), verticalAlignment = Alignment.CenterVertically) {
                Icon(Icons.Outlined.Lock, contentDescription = null, tint = c.danger, modifier = Modifier.size(14.dp))
                Text(" Not right", color = c.danger, style = MaterialTheme.typography.bodySmall)
            }
        }

        if (locked) {
            Column(
                Modifier
                    .padding(top = 24.dp)
                    .clip(RoundedCornerShape(OfferRadius.md))
                    .background(c.cautionBg)
                    .padding(horizontal = 20.dp, vertical = 16.dp)
                    .semantics(mergeDescendants = true) { liveRegion = LiveRegionMode.Polite },
                horizontalAlignment = Alignment.CenterHorizontally,
            ) {
                Icon(Icons.Outlined.Lock, contentDescription = null, tint = c.caution)
                Text("Too many wrong PINs", color = c.caution, style = MaterialTheme.typography.titleSmall, modifier = Modifier.padding(top = 6.dp))
                Text(
                    "Try again in ${OfferFormat.clock(lockedForSeconds ?: 0)}",
                    color = c.caution,
                    style = MaterialTheme.typography.bodyMedium.copy(fontFeatureSettings = "tnum"),
                )
            }
        } else {
            val keys = listOf("1", "2", "3", "4", "5", "6", "7", "8", "9", "", "0", "del")
            Column(
                Modifier.padding(top = 24.dp).widthIn(max = 280.dp),
                verticalArrangement = Arrangement.spacedBy(10.dp),
            ) {
                keys.chunked(3).forEach { row ->
                    Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                        row.forEach { key ->
                            if (key.isEmpty()) {
                                Spacer(Modifier.weight(1f).height(56.dp))
                            } else {
                                PinKey(
                                    key = key,
                                    enabled = enabled,
                                    modifier = Modifier.weight(1f),
                                    onTap = { if (key == "del") type(value.dropLast(1)) else type(value + key) },
                                )
                            }
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun PinKey(key: String, enabled: Boolean, modifier: Modifier, onTap: () -> Unit) {
    val c = offerColors()
    val calm = rememberCalmMotion()
    val interaction = remember { MutableInteractionSource() }
    val isDelete = key == "del"
    Box(
        modifier
            .pressScale(interaction, calm)
            .height(56.dp)
            .clip(RoundedCornerShape(OfferRadius.md))
            .background(if (isDelete) androidx.compose.ui.graphics.Color.Transparent else c.surface)
            .clickable(interaction, LocalIndication.current, enabled = enabled, role = Role.Button, onClick = onTap)
            .semantics { contentDescription = if (isDelete) "Delete last digit" else key },
        contentAlignment = Alignment.Center,
    ) {
        if (isDelete) {
            Icon(Icons.AutoMirrored.Outlined.Backspace, contentDescription = null, tint = c.muted)
        } else {
            Text(
                key,
                color = if (enabled) c.text else c.muted,
                style = MaterialTheme.typography.headlineSmall.copy(fontWeight = FontWeight.Medium, fontFeatureSettings = "tnum"),
            )
        }
    }
}

/**
 * Set a first transaction PIN ([reset] = false), or replace a forgotten one ([reset] = true) after proving it's you with
 * the account password or a code emailed to you (for Google sign-in accounts with no password).
 */
@Composable
fun PinSetupFlow(reset: Boolean, onDone: (PinStatus) -> Unit, length: Int = 4) {
    val c = offerColors()
    val calm = rememberCalmMotion()
    val repo = LocalRepository.current
    val scope = rememberCoroutineScope()
    var step by remember { mutableStateOf(if (reset) "proof" else "choose") }
    var useEmail by remember { mutableStateOf(false) }
    var proofText by remember { mutableStateOf("") }
    var codeSent by remember { mutableStateOf(false) }
    var first by remember { mutableStateOf("") }
    var second by remember { mutableStateOf("") }
    var error by remember { mutableStateOf<String?>(null) }
    var errorTick by remember { mutableIntStateOf(0) }
    var busy by remember { mutableStateOf(false) }

    fun fail(message: String) {
        error = message
        errorTick += 1
    }

    fun save(pin: String) = scope.launch {
        busy = true
        error = null
        try {
            val status = if (!reset) repo.setPin(pin)
            else if (useEmail) repo.setPin(pin, emailCode = proofText.trim())
            else repo.setPin(pin, password = proofText)
            onDone(status)
        } catch (e: ApiException) {
            first = ""
            second = ""
            step = if (reset && (e.message ?: "").contains(Regex("password|code", RegexOption.IGNORE_CASE))) "proof" else "choose"
            fail(e.message ?: "Couldn't save your PIN.")
        } finally {
            busy = false
        }
    }

    Column(Modifier.fillMaxWidth()) {
        AnimatedContent(
            targetState = step,
            transitionSpec = {
                if (calm) fadeIn() togetherWith fadeOut()
                else (slideInHorizontally(OfferMotion.standard()) { it / 6 } + fadeIn()) togetherWith
                    (slideOutHorizontally(OfferMotion.standard()) { -it / 6 } + fadeOut())
            },
            label = "pin-setup",
        ) { current ->
            when (current) {
                "proof" -> Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                    Text("To set a new PIN, first prove it's you.", color = c.muted, style = MaterialTheme.typography.bodyMedium)
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        listOf(false to "My password", true to "Email me a code").forEach { (email, text) ->
                            val selected = useEmail == email
                            Box(
                                Modifier
                                    .weight(1f)
                                    .heightIn(min = 48.dp)
                                    .clip(RoundedCornerShape(OfferRadius.sm))
                                    .background(if (selected) c.tide else c.raised)
                                    .border(1.dp, if (selected) c.accent else c.hairline, RoundedCornerShape(OfferRadius.sm))
                                    .clickable(role = Role.RadioButton) { useEmail = email; proofText = "" }
                                    .semantics { contentDescription = text + if (selected) ", selected" else "" },
                                contentAlignment = Alignment.Center,
                            ) { Text(text, color = if (selected) c.tideFg else c.muted, style = MaterialTheme.typography.labelLarge) }
                        }
                    }
                    if (useEmail && !codeSent) {
                        OfferButton("Send me a code", modifier = Modifier.fillMaxWidth(), loading = busy, onClick = {
                            scope.launch {
                                busy = true
                                try {
                                    repo.pinResetCode()
                                    codeSent = true
                                    error = null
                                } catch (e: ApiException) {
                                    error = e.message
                                } finally {
                                    busy = false
                                }
                            }
                        })
                    } else {
                        OutlinedTextField(
                            value = proofText,
                            onValueChange = { proofText = it },
                            label = { Text(if (useEmail) "6-digit code from your email" else "Password") },
                            singleLine = true,
                            visualTransformation = if (useEmail) androidx.compose.ui.text.input.VisualTransformation.None else PasswordVisualTransformation(),
                            keyboardOptions = KeyboardOptions(keyboardType = if (useEmail) KeyboardType.NumberPassword else KeyboardType.Password),
                            modifier = Modifier.fillMaxWidth(),
                        )
                        OfferButton("Continue", modifier = Modifier.fillMaxWidth(), enabled = proofText.isNotBlank(), onClick = {
                            error = null
                            step = "choose"
                        })
                    }
                }
                "choose" -> Column(horizontalAlignment = Alignment.CenterHorizontally) {
                    Text(
                        if (reset) "Choose a new PIN. Avoid 1234 or repeated digits."
                        else "You'll use this PIN to approve offers. Choropia never asks for it. Avoid 1234 or repeated digits.",
                        color = c.muted,
                        style = MaterialTheme.typography.bodySmall,
                        textAlign = TextAlign.Center,
                        modifier = Modifier.padding(bottom = 12.dp),
                    )
                    PinPad(
                        value = first,
                        onValueChange = { first = it; if (it.isNotEmpty()) error = null },
                        onComplete = { step = "confirm" },
                        label = "Choose a $length-digit PIN",
                        length = length,
                        errorTick = errorTick,
                        error = error != null,
                    )
                }
                else -> Column(horizontalAlignment = Alignment.CenterHorizontally) {
                    PinPad(
                        value = second,
                        onValueChange = { second = it },
                        onComplete = { entered ->
                            if (entered != first) {
                                first = ""
                                second = ""
                                step = "choose"
                                fail("Those PINs didn't match. Choose again.")
                            } else {
                                save(entered)
                            }
                        },
                        label = "Enter it again to confirm",
                        length = length,
                        enabled = !busy,
                        errorTick = errorTick,
                        error = error != null,
                    )
                    if (busy) Text("Saving your PIN…", color = c.muted, style = MaterialTheme.typography.bodySmall, modifier = Modifier.padding(top = 12.dp))
                }
            }
        }
        InlineError(error)
    }
}
