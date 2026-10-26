package com.choropia.app.ui.util

import java.math.BigDecimal
import java.text.NumberFormat
import java.time.Duration
import java.time.Instant
import java.time.OffsetDateTime
import java.time.ZoneId
import java.time.format.DateTimeFormatter
import java.util.Locale

private val naira: NumberFormat = NumberFormat.getIntegerInstance(Locale.US)

/** "15000.00" -> "₦15,000". Kobo are shown only when the price actually has them. */
fun formatNaira(raw: String?): String {
    val value = raw?.toBigDecimalOrNull() ?: return "₦0"
    val hasFraction = value.stripTrailingZeros().scale() > 0
    return if (hasFraction) {
        "₦" + NumberFormat.getNumberInstance(Locale.US).apply {
            minimumFractionDigits = 2
            maximumFractionDigits = 2
        }.format(value)
    } else {
        "₦" + naira.format(value)
    }
}

fun parseInstant(iso: String?): Instant? = iso?.let {
    runCatching { OffsetDateTime.parse(it).toInstant() }.getOrNull()
        ?: runCatching { Instant.parse(it) }.getOrNull()
}

/** "just now", "5m", "3h", "2d", then a short date. */
fun timeAgo(iso: String?): String {
    val then = parseInstant(iso) ?: return ""
    val seconds = Duration.between(then, Instant.now()).seconds
    return when {
        seconds < 45 -> "just now"
        seconds < 3600 -> "${(seconds / 60).coerceAtLeast(1)}m"
        seconds < 86_400 -> "${seconds / 3600}h"
        seconds < 7 * 86_400 -> "${seconds / 86_400}d"
        else -> DateTimeFormatter.ofPattern("d MMM", Locale.getDefault()).withZone(ZoneId.systemDefault()).format(then)
    }
}

fun shortDateTime(iso: String?): String {
    val then = parseInstant(iso) ?: return ""
    return DateTimeFormatter.ofPattern("d MMM, h:mm a", Locale.getDefault()).withZone(ZoneId.systemDefault()).format(then)
}

fun initialsOf(name: String): String {
    val parts = name.trim().split(Regex("\\s+")).filter { it.isNotBlank() }
    return when {
        parts.isEmpty() -> "?"
        parts.size == 1 -> parts[0].take(2).uppercase()
        else -> (parts[0].take(1) + parts[1].take(1)).uppercase()
    }
}

fun String.toBigDecimalOrNullSafe(): BigDecimal? = trim().toBigDecimalOrNull()
