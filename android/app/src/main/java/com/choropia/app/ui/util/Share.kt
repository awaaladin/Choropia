package com.choropia.app.ui.util

import android.content.Context
import android.content.Intent
import com.choropia.app.BuildConfig
import com.choropia.app.data.model.Listing

/** Opens the Android share sheet with a link to the listing on the Choropia website. */
fun shareListing(context: Context, listing: Listing) {
    // The coded address: never the sequential number (see common/public_ids.py on the server).
    val link = if (listing.slug.isNotBlank()) "${BuildConfig.API_ORIGIN}/listing/${listing.slug}" else "${BuildConfig.API_ORIGIN}/listings/${listing.id}"
    val text = "${listing.title} - ${formatNaira(listing.price)} on Choropia\n$link"
    val send = Intent(Intent.ACTION_SEND).apply {
        type = "text/plain"
        putExtra(Intent.EXTRA_SUBJECT, listing.title)
        putExtra(Intent.EXTRA_TEXT, text)
    }
    context.startActivity(Intent.createChooser(send, "Share listing").addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
}
