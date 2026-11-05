package com.choropia.app.ui.screens

import android.net.Uri
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.PickVisualMediaRequest
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.TextButton
import androidx.compose.ui.draw.clip
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.graphics.Color
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.ui.unit.sp
import coil.compose.AsyncImage
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.outlined.ArrowBack
import androidx.compose.material3.Checkbox
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
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
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.choropia.app.data.model.Listing
import com.choropia.app.data.network.ApiException
import com.choropia.app.data.repository.ChoropiaRepository
import com.choropia.app.ui.LocalRepository
import com.choropia.app.ui.components.BlockingLoader
import com.choropia.app.ui.components.Chip
import com.choropia.app.ui.components.ChoropiaField
import com.choropia.app.ui.components.ErrorBanner
import com.choropia.app.ui.components.PrimaryButton
import com.choropia.app.ui.components.ScreenLoader
import com.choropia.app.ui.rememberVm
import com.choropia.app.ui.util.formatNaira
import kotlinx.coroutines.launch

class EditListingViewModel(private val listingId: Int, private val repo: ChoropiaRepository) : ViewModel() {
    var listing by mutableStateOf<Listing?>(null)
        private set
    var loading by mutableStateOf(true)
        private set
    var busy by mutableStateOf(false)
        private set
    var error by mutableStateOf<String?>(null)
        private set
    var saved by mutableStateOf(false)
        private set
    var deleted by mutableStateOf(false)
        private set
    var newPhotos by mutableStateOf<List<Uri>>(emptyList())
        private set

    fun addPhotos(uris: List<Uri>) { newPhotos = (newPhotos + uris).distinct().take(6) }

    fun dropNewPhoto(uri: Uri) { newPhotos = newPhotos - uri }

    fun removePhoto(photoId: Int) {
        if (busy) return
        busy = true
        viewModelScope.launch {
            try {
                listing = repo.removeListingPhoto(listingId, photoId)
            } catch (e: ApiException) {
                error = e.message
            } finally {
                busy = false
            }
        }
    }

    fun delete() {
        if (busy) return
        busy = true
        viewModelScope.launch {
            try {
                repo.deleteListing(listingId)
                deleted = true
            } catch (e: ApiException) {
                error = e.message
            } finally {
                busy = false
            }
        }
    }

    init {
        viewModelScope.launch {
            try {
                listing = repo.getListing(listingId)
            } catch (e: ApiException) {
                error = e.message
            } finally {
                loading = false
            }
        }
    }

    fun save(title: String, description: String, price: String, quantity: Int, condition: String, showChange: Boolean) {
        if (busy) return
        if (title.isBlank()) { error = "Give your listing a title."; return }
        val parsed = price.trim().toBigDecimalOrNull()
        if (parsed == null || parsed <= java.math.BigDecimal.ZERO) { error = "Enter a price in naira."; return }
        busy = true
        error = null
        viewModelScope.launch {
            try {
                repo.updateListing(listingId, title, description, price, quantity, condition, showChange)
                if (newPhotos.isNotEmpty()) repo.addListingPhotos(listingId, newPhotos)
                saved = true
            } catch (e: ApiException) {
                error = e.message
            } finally {
                busy = false
            }
        }
    }
}

/** The owner changes their own listing. A changed price can be shown to buyers (old price crossed out) or quietly replaced. */
@Composable
fun EditListingScreen(listingId: Int, onBack: () -> Unit, onSaved: () -> Unit, onDeleted: () -> Unit = onBack) {
    val repo = LocalRepository.current
    val vm = rememberVm(key = "edit-listing-$listingId") { EditListingViewModel(listingId, repo) }

    LaunchedEffect(vm.saved) { if (vm.saved) onSaved() }
    LaunchedEffect(vm.deleted) { if (vm.deleted) onDeleted() }
    var confirmDelete by remember { mutableStateOf(false) }
    val picker = rememberLauncherForActivityResult(ActivityResultContracts.PickMultipleVisualMedia(6)) { uris -> vm.addPhotos(uris) }
    if (confirmDelete) {
        AlertDialog(
            onDismissRequest = { confirmDelete = false },
            title = { Text("Delete this listing?") },
            text = { Text("It will be removed for good and buyers will no longer see it.") },
            confirmButton = { TextButton(onClick = { confirmDelete = false; vm.delete() }) { Text("Delete") } },
            dismissButton = { TextButton(onClick = { confirmDelete = false }) { Text("Keep it") } },
        )
    }

    Box(Modifier.fillMaxSize()) {
        Column(Modifier.fillMaxSize().statusBarsPadding().navigationBarsPadding().imePadding()) {
            Row(Modifier.height(56.dp).padding(horizontal = 4.dp), verticalAlignment = Alignment.CenterVertically) {
                IconButton(onClick = onBack) { Icon(Icons.AutoMirrored.Outlined.ArrowBack, "Back") }
                Text("Edit listing", style = MaterialTheme.typography.titleLarge)
            }
            val item = vm.listing
            when {
                vm.loading -> ScreenLoader()
                item == null -> Column(Modifier.padding(16.dp)) { ErrorBanner(vm.error ?: "We couldn't load this listing.") }
                else -> {
                    var title by remember { mutableStateOf(item.title) }
                    var description by remember { mutableStateOf(item.description) }
                    var price by remember { mutableStateOf(item.price.toBigDecimalOrNull()?.stripTrailingZeros()?.toPlainString() ?: item.price) }
                    var quantityText by remember { mutableStateOf(item.quantity.toString()) }
                    var condition by remember { mutableStateOf(item.condition) }
                    var showChange by remember { mutableStateOf(false) }
                    val priceChanged = price.toBigDecimalOrNull()?.compareTo(item.price.toBigDecimalOrNull() ?: java.math.BigDecimal.ZERO) != 0

                    Column(
                        Modifier.weight(1f).verticalScroll(rememberScrollState()).padding(horizontal = 16.dp),
                        verticalArrangement = Arrangement.spacedBy(14.dp),
                    ) {
                        vm.error?.let { ErrorBanner(it) }
                        Text(
                            "Changes apply straight away, wherever the listing appears.",
                            style = MaterialTheme.typography.bodyMedium,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                        Text("Photos", style = MaterialTheme.typography.titleSmall)
                        LazyRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                            items(item.photos, key = { it.id }) { photo ->
                                Box(Modifier.size(84.dp)) {
                                    AsyncImage(photo.image, null, Modifier.fillMaxSize().clip(RoundedCornerShape(12.dp)), contentScale = ContentScale.Crop)
                                    Box(
                                        Modifier.align(Alignment.TopEnd).size(24.dp).clip(RoundedCornerShape(12.dp)).background(Color(0xCC000000)).clickable { vm.removePhoto(photo.id) },
                                        contentAlignment = Alignment.Center,
                                    ) { Text("×", color = Color.White, fontSize = 16.sp) }
                                }
                            }
                            items(vm.newPhotos, key = { it.toString() }) { uri ->
                                Box(Modifier.size(84.dp)) {
                                    AsyncImage(uri, null, Modifier.fillMaxSize().clip(RoundedCornerShape(12.dp)), contentScale = ContentScale.Crop)
                                    Box(
                                        Modifier.align(Alignment.TopEnd).size(24.dp).clip(RoundedCornerShape(12.dp)).background(Color(0xCC000000)).clickable { vm.dropNewPhoto(uri) },
                                        contentAlignment = Alignment.Center,
                                    ) { Text("×", color = Color.White, fontSize = 16.sp) }
                                }
                            }
                            item {
                                OutlinedButton(
                                    onClick = { picker.launch(PickVisualMediaRequest(ActivityResultContracts.PickVisualMedia.ImageOnly)) },
                                    modifier = Modifier.size(84.dp),
                                ) { Text("+ Add", fontSize = 12.sp) }
                            }
                        }
                        ChoropiaField(title, { title = it }, "Title")
                        ChoropiaField(description, { description = it }, "Description", singleLine = false, minLines = 4)
                        ChoropiaField(price, { price = it.filter { c -> c.isDigit() || c == '.' } }, "Price (₦)", keyboardType = KeyboardType.Decimal)
                        if (priceChanged) {
                            Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.Top, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                                Checkbox(checked = showChange, onCheckedChange = { showChange = it })
                                Column(Modifier.weight(1f)) {
                                    Text("Show buyers that the price changed", style = MaterialTheme.typography.titleSmall)
                                    Text(
                                        "Ticked: buyers see ${formatNaira(item.price)} crossed out next to the new price. Not ticked: they only see the new price.",
                                        style = MaterialTheme.typography.bodySmall,
                                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                                    )
                                }
                            }
                        }
                        ChoropiaField(
                            quantityText, { quantityText = it.filter { c -> c.isDigit() }.take(3) }, "How many do you have?",
                            keyboardType = KeyboardType.Number,
                        )
                        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                            Chip("Used", condition == "used", { condition = "used" })
                            Chip("New", condition == "new", { condition = "new" })
                        }
                        PrimaryButton(
                            "Save changes",
                            { vm.save(title, description, price, (quantityText.toIntOrNull() ?: 1).coerceIn(1, 999), condition, priceChanged && showChange) },
                            enabled = !vm.busy,
                        )
                        TextButton(onClick = { confirmDelete = true }, enabled = !vm.busy, modifier = Modifier.fillMaxWidth()) {
                            Text("Delete listing", color = MaterialTheme.colorScheme.error)
                        }
                    }
                }
            }
        }
        BlockingLoader(visible = vm.busy)
    }
}
