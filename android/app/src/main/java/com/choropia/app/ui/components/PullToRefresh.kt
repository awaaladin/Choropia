package com.choropia.app.ui.components

import androidx.compose.animation.core.snap
import androidx.compose.animation.core.spring
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.foundation.Image
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxScope
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.offset
import androidx.compose.foundation.layout.width
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberUpdatedState
import androidx.compose.runtime.setValue
import androidx.compose.runtime.snapshotFlow
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clipToBounds
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.hapticfeedback.HapticFeedbackType
import androidx.compose.ui.input.nestedscroll.NestedScrollConnection
import androidx.compose.ui.input.nestedscroll.NestedScrollSource
import androidx.compose.ui.input.nestedscroll.nestedScroll
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.platform.LocalHapticFeedback
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.unit.IntOffset
import androidx.compose.ui.unit.Velocity
import androidx.compose.ui.unit.dp
import com.choropia.app.R
import com.choropia.app.ui.theme.LocalIsDark
import kotlin.math.roundToInt

/**
 * While refreshing, the pull gap shows just the small pulsing mark (the wordmark is reserved for
 * the launch and login/sign-up screens). Flip to true to put the full loader in the gap.
 */
private const val FULL_LOADER_IN_PULL_GAP = false


/**
 * Facebook-style pull to refresh: drag down hard at the top of a list and the content follows
 * your finger with rubber-band resistance; the Choropia mark grows in the gap, a light tap
 * confirms when you've pulled far enough, and on release the mark pulses (the Light loader
 * style) until [refreshing] goes false and everything springs back.
 *
 * The scrollable child must be able to report leftover drag, so use a LazyColumn/LazyGrid —
 * for empty/error states render a single scrollable item rather than a bare Box.
 */
@Composable
fun BrandPullToRefresh(
    refreshing: Boolean,
    onRefresh: () -> Unit,
    modifier: Modifier = Modifier,
    enabled: Boolean = true,
    content: @Composable BoxScope.() -> Unit,
) {
    val density = LocalDensity.current
    val thresholdPx = with(density) { 88.dp.toPx() }
    val maxPx = with(density) { 170.dp.toPx() }
    val holdPx = with(density) { (if (FULL_LOADER_IN_PULL_GAP) 92.dp else 72.dp).toPx() }
    val haptics = LocalHapticFeedback.current

    var dragPx by remember { mutableFloatStateOf(0f) }
    var dragging by remember { mutableStateOf(false) }

    val showRefreshing = refreshing
    val isRefreshing by rememberUpdatedState(showRefreshing)
    val latestOnRefresh by rememberUpdatedState(onRefresh)

    val connection = remember(enabled, thresholdPx, maxPx) {
        object : NestedScrollConnection {
            override fun onPreScroll(available: Offset, source: NestedScrollSource): Offset {
                if (!enabled || isRefreshing || source != NestedScrollSource.Drag) return Offset.Zero
                // Finger moving back up while the list is pulled down: shrink the pull first.
                if (dragPx > 0f && available.y < 0f) {
                    val used = maxOf(available.y, -dragPx)
                    dragPx += used
                    return Offset(0f, used)
                }
                return Offset.Zero
            }

            override fun onPostScroll(consumed: Offset, available: Offset, source: NestedScrollSource): Offset {
                if (!enabled || isRefreshing || source != NestedScrollSource.Drag) return Offset.Zero
                if (available.y > 0f) {
                    dragging = true
                    val resistance = 1f - (dragPx / maxPx).coerceIn(0f, 0.85f)
                    dragPx = (dragPx + available.y * 0.6f * resistance).coerceAtMost(maxPx)
                    return Offset(0f, available.y)
                }
                return Offset.Zero
            }

            override suspend fun onPreFling(available: Velocity): Velocity {
                val wasPulled = dragPx > 0f
                dragging = false
                if (dragPx >= thresholdPx && !isRefreshing) latestOnRefresh()
                dragPx = 0f
                return if (wasPulled) available else Velocity.Zero
            }
        }
    }

    // One light tap when the pull crosses the "release to refresh" line.
    LaunchedEffect(thresholdPx) {
        snapshotFlow { dragging && dragPx >= thresholdPx }.collect { armed ->
            if (armed) haptics.performHapticFeedback(HapticFeedbackType.LongPress)
        }
    }

    val target = when {
        dragging && dragPx > 0f -> dragPx
        showRefreshing -> holdPx
        else -> 0f
    }
    val offsetPx by animateFloatAsState(
        targetValue = target,
        animationSpec = if (dragging && dragPx > 0f) snap() else spring(dampingRatio = 0.78f, stiffness = 320f),
        label = "pull-offset",
    )

    Box(modifier.nestedScroll(connection).clipToBounds()) {
        // Indicator lives in the space opened up by the pull.
        val progress = (offsetPx / thresholdPx).coerceIn(0f, 1f)
        if (offsetPx > 1f) {
            // The indicator is centred in the gap the pull opens up, whatever its height.
            Box(
                Modifier
                    .align(Alignment.TopCenter)
                    .fillMaxWidth()
                    .height(with(density) { offsetPx.toDp() })
                    .clipToBounds(),
                contentAlignment = Alignment.Center,
            ) {
                if (showRefreshing) {
                    // Refreshing: the same loader as launch/login — mark + reflection, with the
                    // "Choropia" wordmark sliding in and out — but only in the gap, so the
                    // screen underneath stays put.
                    if (FULL_LOADER_IN_PULL_GAP) BrandLoader(style = LoaderStyle.Full, markSize = 48.dp)
                    else BrandLoader(style = LoaderStyle.Light, markSize = 44.dp)
                } else {
                    val dark = LocalIsDark.current
                    Image(
                        painter = painterResource(if (dark) R.drawable.brand_mark_white else R.drawable.brand_mark_navy),
                        contentDescription = null,
                        modifier = Modifier
                            .width(44.dp)
                            .aspectRatio(452f / 364f)
                            .graphicsLayer {
                                val s = 0.35f + 0.65f * progress
                                scaleX = s
                                scaleY = s
                                alpha = progress
                                // A gentle quarter-turn as you pull, settling upright at the line.
                                rotationZ = (1f - progress) * -35f
                            },
                    )
                }
            }
        }
        Box(
            Modifier
                .fillMaxSize()
                .offset { IntOffset(0, offsetPx.roundToInt()) },
        ) { content() }
    }
}
