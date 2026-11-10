package com.choropia.app.ui.offers

import android.provider.Settings
import androidx.compose.animation.core.Spring
import androidx.compose.animation.core.SpringSpec
import androidx.compose.animation.core.spring
import androidx.compose.material3.MaterialTheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.Immutable
import androidx.compose.runtime.remember
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.luminance
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp

/**
 * Escrow-offer design tokens. Same names and values as the web tokens (`--o-*` in frontend/src/styles.css):
 * a navy ramp from deep ink (#070F22 → #0B1B3A → #14306B → pale tint), warm paper surfaces in light mode, a
 * steel-blue "tide" tint for money held in escrow, and muted status colours used only for state.
 */
@Immutable
data class OfferColors(
    val surface: Color,
    val raised: Color,
    val text: Color,
    val muted: Color,
    val accent: Color,
    val accentFg: Color,
    val hairline: Color,
    val tide: Color,
    val tideFg: Color,
    val ok: Color,
    val okBg: Color,
    val caution: Color,
    val cautionBg: Color,
    val danger: Color,
    val dangerBg: Color,
    val dark: Boolean,
)

private val Light = OfferColors(
    surface = Color(0xFFF7F5F0),
    raised = Color(0xFFFFFFFF),
    text = Color(0xFF070F22),
    muted = Color(0xFF4A5670),
    accent = Color(0xFF14306B),
    accentFg = Color(0xFFFFFFFF),
    hairline = Color(0x1F0B1B3A),
    tide = Color(0xFFE4EBF2),
    tideFg = Color(0xFF233F5C),
    ok = Color(0xFF2F6B4F),
    okBg = Color(0xFFE5EFE9),
    caution = Color(0xFF7D5310),
    cautionBg = Color(0xFFF5ECDA),
    danger = Color(0xFF9B2C2C),
    dangerBg = Color(0xFFF6E3E1),
    dark = false,
)

private val Dark = OfferColors(
    surface = Color(0xFF0B1630),
    raised = Color(0xFF101F3E),
    text = Color(0xFFEEF2F8),
    muted = Color(0xFFA7B3C9),
    accent = Color(0xFFA9C1F3),
    accentFg = Color(0xFF070F22),
    hairline = Color(0x1AFFFFFF),
    tide = Color(0xFF16304A),
    tideFg = Color(0xFFC3D6E7),
    ok = Color(0xFF93CDB0),
    okBg = Color(0x1F93CDB0),
    caution = Color(0xFFE6BE78),
    cautionBg = Color(0x1FE6BE78),
    danger = Color(0xFFEDA29A),
    dangerBg = Color(0x1FEDA29A),
    dark = true,
)

/** The offer colours for the app's current light or dark theme. */
@Composable
fun offerColors(): OfferColors = if (MaterialTheme.colorScheme.surface.luminance() < 0.5f) Dark else Light

object OfferRadius {
    val sm = 12.dp
    val md = 16.dp
    val lg = 24.dp
}

object OfferMotion {
    /** Standard spring (stiffness ~300, damping ~28): sheets, cards, layout changes. */
    fun <T> standard(): SpringSpec<T> = spring(dampingRatio = 0.81f, stiffness = 300f)

    /** Snappier spring for presses and small pops. */
    fun <T> snappy(): SpringSpec<T> = spring(dampingRatio = 0.72f, stiffness = 520f)

    /** Bouncier settle for the padlock closing. */
    fun <T> settle(): SpringSpec<T> = spring(dampingRatio = Spring.DampingRatioMediumBouncy, stiffness = 420f)
}

/** True when the person has turned animations off (Settings → Accessibility → Remove animations). */
@Composable
fun rememberCalmMotion(): Boolean {
    val context = LocalContext.current
    return remember {
        runCatching {
            Settings.Global.getFloat(context.contentResolver, Settings.Global.ANIMATOR_DURATION_SCALE, 1f) == 0f
        }.getOrDefault(false)
    }
}
