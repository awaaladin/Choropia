package com.choropia.app.ui.components

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.layout.size
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.StrokeJoin
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import kotlin.math.PI
import kotlin.math.cos
import kotlin.math.sin

/**
 * Choropia's own verified mark: a rounded eight-point star seal with a check, the same size and feel as a social-app
 * verified badge but in the Choropia blue-to-teal. Shown only next to sellers and storefronts the team has verified.
 */
@Composable
fun VerifiedBadge(modifier: Modifier = Modifier, size: Dp = 20.dp, description: String = "Verified by Choropia") {
    Canvas(modifier.size(size).semantics { contentDescription = description }) {
        val unit = this.size.minDimension / 24f
        val points = 8
        val star = Path()
        for (i in 0 until points * 2) {
            val radius = if (i % 2 == 0) 11f else 8.6f
            val angle = (PI * i / points - PI / 2).toFloat()
            val x = (12f + radius * cos(angle)) * unit
            val y = (12f + radius * sin(angle)) * unit
            if (i == 0) star.moveTo(x, y) else star.lineTo(x, y)
        }
        star.close()
        val brush = Brush.linearGradient(
            colors = listOf(Color(0xFF2F6BD6), Color(0xFF12A58A)),
            start = Offset(3f * unit, 2f * unit),
            end = Offset(21f * unit, 22f * unit),
        )
        drawPath(star, brush)
        drawPath(star, brush, style = Stroke(width = 2.4f * unit, join = StrokeJoin.Round))
        val check = Path().apply {
            moveTo(8f * unit, 12.4f * unit)
            lineTo(10.7f * unit, 15.1f * unit)
            lineTo(16.2f * unit, 9.2f * unit)
        }
        drawPath(check, Color.White, style = Stroke(width = 2.1f * unit, cap = StrokeCap.Round, join = StrokeJoin.Round))
    }
}
