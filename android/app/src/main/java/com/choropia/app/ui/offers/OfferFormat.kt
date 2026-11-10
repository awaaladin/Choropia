package com.choropia.app.ui.offers

import java.text.NumberFormat
import java.util.Locale

/** Money in the offer screens is always whole kobo (Long). These helpers never use floating point for amounts. */
object OfferFormat {
    private val grouping: NumberFormat = NumberFormat.getIntegerInstance(Locale.US)

    /** "₦185,000" or "₦185,000.50". */
    fun naira(kobo: Long): String {
        val sign = if (kobo < 0) "-" else ""
        val abs = kotlin.math.abs(kobo)
        val rest = abs % 100
        return "$sign₦${grouping.format(abs / 100)}" + if (rest != 0L) ".%02d".format(rest) else ""
    }

    /** What TalkBack should say: "185,000 naira". */
    fun spoken(kobo: Long): String {
        val abs = kotlin.math.abs(kobo)
        val rest = abs % 100
        return "${grouping.format(abs / 100)} naira" + if (rest != 0L) " $rest kobo" else ""
    }

    /** "185,000" for the amount field (the ₦ sits beside it). */
    fun input(kobo: Long): String {
        val rest = kobo % 100
        return grouping.format(kobo / 100) + if (rest != 0L) ".%02d".format(rest) else ""
    }

    /** Parses "185,000" / "185000.5" into kobo, or null if it isn't an amount. String maths only. */
    fun parse(text: String): Long? {
        val clean = text.replace(",", "").replace("₦", "").trim()
        if (!clean.matches(Regex("""\d{1,11}(\.\d{0,2})?"""))) return null
        val whole = clean.substringBefore('.').toLongOrNull() ?: return null
        val frac = (clean.substringAfter('.', "") + "00").take(2).toLong()
        return whole * 100 + frac
    }

    /** Keeps what the person types tidy: digits, one dot, two decimals, grouped thousands. */
    fun tidy(raw: String): String {
        val clean = raw.filter { it.isDigit() || it == '.' }
        val whole = clean.substringBefore('.').take(11).trimStart('0').ifEmpty { if (clean.startsWith("0")) "0" else "" }
        val grouped = whole.toLongOrNull()?.let { grouping.format(it) } ?: ""
        return if ('.' in clean) "$grouped.${clean.substringAfter('.').filter { it.isDigit() }.take(2)}" else grouped
    }

    /** Whole-percent discount from the listed price; 0 when not lower. */
    fun discountPercent(amount: Long, listed: Long): Int =
        if (listed <= 0 || amount >= listed) 0 else (((listed - amount) * 100 + listed / 2) / listed).toInt()

    /** "2:14:09" or "14:09". */
    fun clock(seconds: Long): String {
        val s = seconds.coerceAtLeast(0)
        val h = s / 3600
        val m = (s % 3600) / 60
        val sec = s % 60
        return if (h > 0) "%d:%02d:%02d".format(h, m, sec) else "%d:%02d".format(m, sec)
    }

    /** Listing prices arrive as naira strings ("200000.00"). */
    fun koboFromNairaString(price: String): Long = parse(price) ?: 0L
}
