package com.choropia.app.ui.offers

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.core.Animatable
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.spring
import androidx.compose.animation.expandVertically
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.shrinkVertically
import androidx.compose.foundation.LocalIndication
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.interaction.collectIsPressedAsState
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.ErrorOutline
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.hapticfeedback.HapticFeedbackType
import androidx.compose.ui.platform.LocalHapticFeedback
import androidx.compose.ui.semantics.LiveRegionMode
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.liveRegion
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp

/** Press feedback: scales to 0.97 while pressed and springs back. Nothing moves when animations are off. */
@Composable
fun Modifier.pressScale(interaction: MutableInteractionSource, calm: Boolean): Modifier {
    val pressed by interaction.collectIsPressedAsState()
    val scale by animateFloatAsState(
        targetValue = if (pressed && !calm) 0.97f else 1f,
        animationSpec = OfferMotion.snappy(),
        label = "press",
    )
    return this.graphicsLayer {
        scaleX = scale
        scaleY = scale
    }
}

enum class OfferButtonKind { Primary, Quiet, Danger, Link }

/** The one button used across the offer screens: 48dp minimum, press spring, light haptic. */
@Composable
fun OfferButton(
    text: String,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
    kind: OfferButtonKind = OfferButtonKind.Primary,
    enabled: Boolean = true,
    loading: Boolean = false,
) {
    val c = offerColors()
    val calm = rememberCalmMotion()
    val haptic = LocalHapticFeedback.current
    val interaction = remember { MutableInteractionSource() }
    val (bg, fg) = when (kind) {
        OfferButtonKind.Primary -> c.accent to c.accentFg
        OfferButtonKind.Quiet -> Color.Transparent to c.muted
        OfferButtonKind.Danger -> c.dangerBg to c.danger
        OfferButtonKind.Link -> Color.Transparent to c.accent
    }
    Box(
        modifier
            .pressScale(interaction, calm)
            .heightIn(min = 48.dp)
            .clip(RoundedCornerShape(OfferRadius.sm))
            .background(if (enabled) bg else bg.copy(alpha = bg.alpha * 0.45f))
            .clickable(
                interactionSource = interaction,
                indication = LocalIndication.current,
                enabled = enabled && !loading,
                role = Role.Button,
            ) {
                haptic.performHapticFeedback(HapticFeedbackType.TextHandleMove)
                onClick()
            }
            .padding(horizontal = 16.dp),
        contentAlignment = Alignment.Center,
    ) {
        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.Center) {
            if (loading) {
                CircularProgressIndicator(Modifier.size(16.dp), color = fg, strokeWidth = 2.dp)
                Spacer(Modifier.width(8.dp))
            }
            Text(
                text,
                color = if (enabled) fg else fg.copy(alpha = 0.6f),
                style = MaterialTheme.typography.labelLarge.copy(fontWeight = FontWeight.SemiBold),
            )
        }
    }
}

/**
 * A naira amount that counts to its new value instead of jumping. Interpolates between whole-kobo Longs (never
 * floating-point money); TalkBack reads only the final value.
 */
@Composable
fun AnimatedAmount(kobo: Long, style: TextStyle, color: Color, modifier: Modifier = Modifier) {
    val calm = rememberCalmMotion()
    var from by remember { mutableStateOf(kobo) }
    var to by remember { mutableStateOf(kobo) }
    val progress = remember { Animatable(1f) }
    LaunchedEffect(kobo) {
        if (kobo == to) return@LaunchedEffect
        from += ((to - from) * progress.value).toLong()
        to = kobo
        if (calm) {
            progress.snapTo(1f)
        } else {
            progress.snapTo(0f)
            progress.animateTo(1f, spring(dampingRatio = 1f, stiffness = 160f))
        }
    }
    val shown = from + ((to - from) * progress.value).toLong()
    Text(
        OfferFormat.naira(shown),
        style = style.copy(fontFeatureSettings = "tnum"),
        color = color,
        modifier = modifier.semantics { contentDescription = OfferFormat.spoken(kobo) },
    )
}

/** An error shown where it happened; TalkBack announces it right away. */
@Composable
fun InlineError(message: String?, modifier: Modifier = Modifier) {
    val c = offerColors()
    AnimatedVisibility(
        visible = !message.isNullOrBlank(),
        enter = fadeIn() + expandVertically(),
        exit = fadeOut() + shrinkVertically(),
        modifier = modifier,
    ) {
        Row(
            Modifier
                .fillMaxWidth()
                .padding(top = 8.dp)
                .clip(RoundedCornerShape(OfferRadius.sm))
                .background(c.dangerBg)
                .padding(horizontal = 12.dp, vertical = 10.dp)
                .semantics { liveRegion = LiveRegionMode.Assertive },
            verticalAlignment = Alignment.Top,
        ) {
            Icon(Icons.Outlined.ErrorOutline, contentDescription = null, tint = c.danger, modifier = Modifier.size(18.dp))
            Spacer(Modifier.width(8.dp))
            Text(message.orEmpty(), color = c.danger, style = MaterialTheme.typography.bodyMedium)
        }
    }
}

/** A small rounded status label. */
@Composable
fun StatusChip(text: String, fg: Color, bg: Color, modifier: Modifier = Modifier, leading: (@Composable () -> Unit)? = null) {
    Row(
        modifier
            .clip(RoundedCornerShape(50))
            .background(bg)
            .padding(horizontal = 8.dp, vertical = 3.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        if (leading != null) {
            leading()
            Spacer(Modifier.width(4.dp))
        }
        Text(text, color = fg, style = MaterialTheme.typography.labelSmall.copy(fontWeight = FontWeight.Medium))
    }
}
