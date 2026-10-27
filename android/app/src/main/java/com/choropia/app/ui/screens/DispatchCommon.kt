package com.choropia.app.ui.screens

import android.content.Context
import android.content.Intent
import android.net.Uri
import androidx.browser.customtabs.CustomTabsIntent
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.ExpandMore
import androidx.compose.material.icons.outlined.Info
import androidx.compose.material.icons.outlined.Place
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.unit.dp
import com.choropia.app.BuildConfig
import com.choropia.app.data.model.Area
import com.choropia.app.ui.components.ChoropiaField
import kotlinx.coroutines.launch

/** A short grey note with an info icon. */
@Composable
fun Note(text: String, modifier: Modifier = Modifier) {
    Row(
        modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(14.dp))
            .background(MaterialTheme.colorScheme.surfaceContainer)
            .padding(14.dp),
        horizontalArrangement = Arrangement.spacedBy(10.dp),
    ) {
        Icon(Icons.Outlined.Info, null, tint = MaterialTheme.colorScheme.secondary)
        Text(text, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
    }
}

/** Opens a web page (the legal documents, a checkout) in a Custom Tab, falling back to the browser. */
fun openWebPage(context: Context, url: String) {
    val uri = Uri.parse(url)
    try {
        CustomTabsIntent.Builder().setShowTitle(true).build().launchUrl(context, uri)
    } catch (e: Exception) {
        runCatching { context.startActivity(Intent(Intent.ACTION_VIEW, uri).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)) }
    }
}

fun legalUrl(slug: String) = BuildConfig.API_ORIGIN.trimEnd('/') + "/legal/$slug/"

/**
 * Pick an area of Uyo. The list starts with common areas; anyone can add one that is missing, so
 * the last menu item opens a small "add an area" box.
 */
@Composable
fun AreaField(
    label: String,
    areas: List<Area>,
    selected: Area?,
    onSelect: (Area) -> Unit,
    onAddArea: suspend (String) -> Area?,
    modifier: Modifier = Modifier,
) {
    var open by remember { mutableStateOf(false) }
    var adding by remember { mutableStateOf(false) }
    var newName by remember { mutableStateOf("") }
    val scope = rememberCoroutineScope()

    Box(modifier.fillMaxWidth()) {
        OutlinedTextField(
            value = selected?.name.orEmpty(),
            onValueChange = {},
            readOnly = true,
            label = { Text(label) },
            leadingIcon = { Icon(Icons.Outlined.Place, null) },
            trailingIcon = { Icon(Icons.Outlined.ExpandMore, null) },
            shape = RoundedCornerShape(14.dp),
            modifier = Modifier.fillMaxWidth(),
        )
        Box(Modifier.matchParentSize().clickable { open = true })
        DropdownMenu(expanded = open, onDismissRequest = { open = false }) {
            areas.forEach { area ->
                DropdownMenuItem(text = { Text(area.name) }, onClick = { onSelect(area); open = false })
            }
            DropdownMenuItem(
                text = { Text("Add an area that's missing", color = MaterialTheme.colorScheme.secondary) },
                onClick = { open = false; adding = true },
            )
        }
    }

    if (adding) {
        AlertDialog(
            onDismissRequest = { adding = false },
            title = { Text("Add an area") },
            text = {
                ChoropiaField(newName, { newName = it }, "Area name (for example, Ikot Ishie)")
            },
            confirmButton = {
                TextButton(
                    enabled = newName.trim().length >= 3,
                    onClick = {
                        val name = newName
                        scope.launch {
                            onAddArea(name)?.let { onSelect(it) }
                            newName = ""
                            adding = false
                        }
                    },
                ) { Text("Add") }
            },
            dismissButton = { TextButton(onClick = { adding = false }) { Text("Cancel") } },
        )
    }
}

fun vehicleLabel(code: String) = when (code) {
    "bike" -> "Motorbike"
    "tricycle" -> "Tricycle (keke)"
    "car" -> "Car"
    "van" -> "Van / bus"
    else -> code.replaceFirstChar { it.uppercase() }
}

fun payerLabel(code: String) = when (code) {
    "buyer" -> "Buyer pays delivery"
    "seller" -> "I (the seller) pay delivery"
    "split" -> "Split 50/50"
    else -> code
}
