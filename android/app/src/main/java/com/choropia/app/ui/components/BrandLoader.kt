package com.choropia.app.ui.components

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.core.Animatable
import androidx.compose.animation.core.CubicBezierEasing
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.requiredHeight
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.wrapContentHeight
import androidx.compose.material3.MaterialTheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clipToBounds
import androidx.compose.ui.draw.drawWithContent
import androidx.compose.ui.graphics.BlendMode
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.CompositingStrategy
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.layout.layout
import kotlin.math.roundToInt
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import com.choropia.app.R
import com.choropia.app.ui.theme.LocalIsDark
import kotlinx.coroutines.delay

/**
 * The app's two loading states. These deliberately mirror the web app's `BrandLoader`
 * (frontend/src/components/BrandLoader.tsx + styles.css) so the products feel identical:
 *
 *  - [Full]  — launch, login, sign-up and anything that has to round-trip the backend. The real
 *              Choropia mark pulses (0.92 ↔ 1.07) with a soft mirrored reflection beneath it,
 *              while the "Choropia" wordmark slides out from the left, holds, and retreats the
 *              way it came, on a loop.
 *  - [Light] — ordinary in-app loading and refreshes: the mark alone, calmly expanding and
 *              contracting.
 */
enum class LoaderStyle { Full, Light }

/**
 * Where the "Choropia" wordmark sits in the Full loader.
 *  - [Below]  — under the mark, sliding in from the left (identical to the web app).
 *  - [Beside] — to the right of the mark, sliding out from behind it; the pair stays centred.
 * Change [DefaultWordmarkPlacement] to switch the whole app.
 */
enum class WordmarkPlacement { Below, Beside }

val DefaultWordmarkPlacement = WordmarkPlacement.Beside

private const val MARK_ASPECT = 452f / 364f   // brand_mark_*.png
private const val WORD_ASPECT = 463f / 104f   // brand_wordmark_*.png

// Same easing curves as the web keyframes.
private val PulseEasing = CubicBezierEasing(0.45f, 0f, 0.55f, 1f)
private val PeekEasing = CubicBezierEasing(0.32f, 0.72f, 0f, 1f)

@Composable
fun BrandLoader(
    modifier: Modifier = Modifier,
    style: LoaderStyle = LoaderStyle.Light,
    markSize: Dp = 72.dp,
    dark: Boolean = LocalIsDark.current,
    placement: WordmarkPlacement = DefaultWordmarkPlacement,
) {
    val transition = rememberInfiniteTransition(label = "brand-loader")
    val markRes = if (dark) R.drawable.brand_mark_white else R.drawable.brand_mark_navy

    // brand-pulse: 1.8s, scale 0.92 -> 1.07 -> 0.92.
    val pulse by transition.animateFloat(
        initialValue = 0.92f,
        targetValue = 1.07f,
        animationSpec = infiniteRepeatable(tween(900, easing = PulseEasing), RepeatMode.Reverse),
        label = "pulse",
    )

    when (style) {
        LoaderStyle.Light -> Box(modifier, contentAlignment = Alignment.Center) {
            Image(
                painter = painterResource(markRes),
                contentDescription = "Loading",
                modifier = Modifier
                    .width(markSize)
                    .aspectRatio(MARK_ASPECT)
                    .graphicsLayer {
                        scaleX = pulse
                        scaleY = pulse
                    },
            )
        }

        LoaderStyle.Full -> {
            // The wordmark plays exactly once per showing: it slides out of the logo, holds, and
            // tucks back in. After that the logo just keeps pulsing on its own.
            val peekAnim = remember { Animatable(0f) }
            LaunchedEffect(Unit) {
                peekAnim.animateTo(1f, tween(650, easing = PeekEasing))
                delay(1100)
                peekAnim.animateTo(0f, tween(650, easing = PeekEasing))
            }
            val peek = peekAnim.value
            if (placement == WordmarkPlacement.Beside) {
                BesideLockup(modifier, peek, markSize, pulse, dark)
                return
            }
            val markHeight = markSize / MARK_ASPECT
            val wordWidth = markSize * 1.55f
            val wordHeight = wordWidth / WORD_ASPECT
            val reflectionAlpha = 0.16f + 0.10f * ((pulse - 0.92f) / (1.07f - 0.92f))

            Column(modifier, horizontalAlignment = Alignment.CenterHorizontally) {
                // Mark.
                Image(
                    painter = painterResource(markRes),
                    contentDescription = "Loading Choropia",
                    modifier = Modifier
                        .width(markSize)
                        .aspectRatio(MARK_ASPECT)
                        .graphicsLayer {
                            scaleX = pulse
                            scaleY = pulse
                        },
                )
                // Reflection: the mark mirrored, fading to nothing.
                Box(
                    Modifier
                        .requiredHeight(markHeight * 0.62f)
                        .width(markSize)
                        .clipToBounds(),
                ) {
                    Image(
                        painter = painterResource(markRes),
                        contentDescription = null,
                        modifier = Modifier
                            .wrapContentHeight(Alignment.Top, unbounded = true)
                            .width(markSize)
                            .aspectRatio(MARK_ASPECT)
                            .graphicsLayer {
                                scaleX = pulse
                                scaleY = -pulse
                                alpha = reflectionAlpha
                                compositingStrategy = CompositingStrategy.Offscreen
                            }
                            .drawWithContent {
                                drawContent()
                                // After the flip, the layer's bottom is the edge nearest the mark.
                                drawRect(
                                    brush = Brush.verticalGradient(
                                        0f to Color.Transparent,
                                        0.25f to Color.Transparent,
                                        1f to Color.Black.copy(alpha = 0.55f),
                                    ),
                                    blendMode = BlendMode.DstIn,
                                )
                            },
                    )
                }
                // Wordmark: slides in from the left edge of its window and back out again.
                Box(
                    Modifier
                        .padding(top = 12.dp)
                        .width(wordWidth)
                        .height(wordHeight)
                        .clipToBounds(),
                ) {
                    Image(
                        painter = painterResource(if (dark) R.drawable.brand_wordmark_white else R.drawable.brand_wordmark_navy),
                        contentDescription = "Choropia",
                        contentScale = ContentScale.Fit,
                        modifier = Modifier
                            .width(wordWidth)
                            .height(wordHeight)
                            .graphicsLayer {
                                translationX = -(1f - peek) * size.width
                                alpha = peek
                            },
                    )
                }
            }
        }
    }
}

/** Full-screen brand splash: used at launch and whenever the app must wait on the backend. */
@Composable
fun BrandSplash(modifier: Modifier = Modifier) {
    Box(
        modifier
            .fillMaxSize()
            .background(MaterialTheme.colorScheme.background),
        contentAlignment = Alignment.Center,
    ) {
        BrandLoader(style = LoaderStyle.Full, markSize = 84.dp)
    }
}

/**
 * Dim, touch-blocking overlay for actions that need the screen to wait a moment. The default is
 * just the logo calmly expanding and contracting; login and sign-up pass [LoaderStyle.Full] to
 * get the logo + reflection with "Choropia" sliding out beside it.
 */
@Composable
fun BlockingLoader(visible: Boolean, modifier: Modifier = Modifier, style: LoaderStyle = LoaderStyle.Light) {
    AnimatedVisibility(visible = visible, enter = fadeIn(tween(180)), exit = fadeOut(tween(220)), modifier = modifier) {
        val blocker = remember { MutableInteractionSource() }
        Box(
            Modifier
                .fillMaxSize()
                .background(MaterialTheme.colorScheme.background.copy(alpha = 0.92f))
                .clickable(interactionSource = blocker, indication = null) { },
            contentAlignment = Alignment.Center,
        ) {
            BrandLoader(style = style, markSize = if (style == LoaderStyle.Full) 80.dp else 64.dp)
        }
    }
}

/** Centered Light loader for a screen's first load. */
@Composable
fun ScreenLoader(modifier: Modifier = Modifier) {
    Box(modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
        BrandLoader(style = LoaderStyle.Light, markSize = 56.dp)
    }
}

/** "Beside" layout: mark + wordmark in a row; the wordmark's slot grows so the pair stays centred. */
@Composable
private fun BesideLockup(modifier: Modifier, reveal: Float, markSize: Dp, pulse: Float, dark: Boolean) {
    val lockupHeight = markSize / MARK_ASPECT

    @Composable
    fun Lockup() {
        val markRes = if (dark) R.drawable.brand_mark_white else R.drawable.brand_mark_navy
        val wordRes = if (dark) R.drawable.brand_wordmark_white else R.drawable.brand_wordmark_navy
        val wordHeight = lockupHeight * 0.34f
        val slidePx = with(androidx.compose.ui.platform.LocalDensity.current) { 28.dp.toPx() }
        androidx.compose.foundation.layout.Row(verticalAlignment = Alignment.CenterVertically) {
            Image(
                painter = painterResource(markRes),
                contentDescription = null,
                modifier = Modifier
                    .width(markSize)
                    .aspectRatio(MARK_ASPECT)
                    .graphicsLayer { scaleX = pulse; scaleY = pulse },
            )
            Box(
                Modifier
                    .layout { measurable, _ ->
                        val placeable = measurable.measure(androidx.compose.ui.unit.Constraints())
                        val width = (placeable.width * reveal).roundToInt()
                        layout(width, placeable.height) { placeable.placeRelative(0, 0) }
                    }
                    .clipToBounds(),
            ) {
                Image(
                    painter = painterResource(wordRes),
                    contentDescription = "Choropia",
                    contentScale = ContentScale.Fit,
                    modifier = Modifier
                        .padding(start = 14.dp)
                        .height(wordHeight)
                        .aspectRatio(WORD_ASPECT)
                        .graphicsLayer { translationX = -(1f - reveal) * slidePx; alpha = reveal },
                )
            }
        }
    }

    Column(modifier, horizontalAlignment = Alignment.CenterHorizontally) {
        Lockup()
        Box(Modifier.padding(top = 4.dp).requiredHeight(lockupHeight * 0.55f).clipToBounds()) {
            Box(
                Modifier
                    .wrapContentHeight(Alignment.Top, unbounded = true)
                    .graphicsLayer {
                        scaleY = -1f
                        alpha = 0.26f
                        compositingStrategy = CompositingStrategy.Offscreen
                    }
                    .drawWithContent {
                        drawContent()
                        drawRect(
                            brush = Brush.verticalGradient(listOf(Color.Transparent, Color.Black)),
                            blendMode = BlendMode.DstIn,
                        )
                    },
            ) { Lockup() }
        }
    }
}
