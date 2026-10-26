package com.choropia.app.ui.screens

import android.net.Uri
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.PickVisualMediaRequest
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.outlined.ArrowBack
import androidx.compose.material.icons.outlined.AddPhotoAlternate
import androidx.compose.material.icons.outlined.Close
import androidx.compose.material.icons.outlined.ExpandMore
import androidx.compose.material.icons.outlined.LocationOn
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import coil.compose.AsyncImage
import com.choropia.app.data.model.Category
import com.choropia.app.data.network.ApiException
import com.choropia.app.data.repository.ChoropiaRepository
import com.choropia.app.ui.LocalRepository
import com.choropia.app.ui.LocalSession
import com.choropia.app.ui.components.BlockingLoader
import com.choropia.app.ui.components.ChoropiaField
import com.choropia.app.ui.components.Chip
import com.choropia.app.ui.components.ErrorBanner
import com.choropia.app.ui.components.PrimaryButton
import com.choropia.app.ui.components.SectionTitle
import com.choropia.app.ui.rememberVm
import kotlinx.coroutines.launch

class CreateListingViewModel(private val repo: ChoropiaRepository) : ViewModel() {
    var categories by mutableStateOf<List<Category>>(emptyList())
        private set
    var busy by mutableStateOf(false)
        private set
    var error by mutableStateOf<String?>(null)
        private set
    var fieldErrors by mutableStateOf<Map<String, String>>(emptyMap())
        private set

    var preview by mutableStateOf<com.choropia.app.data.model.CommissionPreview?>(null)
        private set
    private var previewJob: kotlinx.coroutines.Job? = null

    init {
        viewModelScope.launch {
            runCatching { repo.categories() }.onSuccess { categories = it.sortedBy { c -> c.name } }
        }
    }

    /** What the seller will receive for this price. The server owns the rates, so the app just asks. */
    fun previewFor(price: String) {
        previewJob?.cancel()
        val value = price.toBigDecimalOrNull()
        if (value == null || value <= java.math.BigDecimal.ZERO) {
            preview = null
            return
        }
        previewJob = viewModelScope.launch {
            kotlinx.coroutines.delay(350)  // wait for them to stop typing
            preview = runCatching { repo.commissionPreview(price) }.getOrNull()
        }
    }

    fun submit(
        title: String,
        description: String,
        price: String,
        condition: String,
        category: Category?,
        location: String,
        photos: List<Uri>,
        onCreated: (Int) -> Unit,
    ) {
        val local = mutableMapOf<String, String>()
        if (title.isBlank()) local["title"] = "Give your listing a title"
        val parsed = price.trim().toBigDecimalOrNull()
        if (parsed == null || parsed <= java.math.BigDecimal.ZERO) local["price"] = "Enter a price in naira"
        if (category == null) local["category"] = "Choose a category"
        if (local.isNotEmpty()) {
            fieldErrors = local
            error = "Please fix the highlighted fields."
            return
        }
        if (busy) return
        busy = true
        error = null
        fieldErrors = emptyMap()
        viewModelScope.launch {
            try {
                val created = repo.createListing(title, description, price, condition, category!!.id, location, photos)
                onCreated(created.id)
            } catch (e: ApiException) {
                error = e.message
                fieldErrors = e.fieldErrors
            } finally {
                busy = false
            }
        }
    }
}

@Composable
fun CreateListingScreen(onBack: () -> Unit, onCreated: (Int) -> Unit) {
    val repo = LocalRepository.current
    val vm = rememberVm { CreateListingViewModel(repo) }

    var title by remember { mutableStateOf("") }
    var description by remember { mutableStateOf("") }
    var price by remember { mutableStateOf("") }
    var condition by remember { mutableStateOf("used") }
    var category by remember { mutableStateOf<Category?>(null) }
    var location by remember { mutableStateOf("") }
    var photos by remember { mutableStateOf<List<Uri>>(emptyList()) }
    var categoryMenu by remember { mutableStateOf(false) }

    val picker = rememberLauncherForActivityResult(ActivityResultContracts.PickMultipleVisualMedia(6)) { uris ->
        photos = (photos + uris).distinct().take(6)
    }
    // Default the location to the profile's, if the user has one.
    val me by LocalSession.current.user.collectAsState()
    LaunchedEffect(me?.id) {
        if (location.isBlank()) location = me?.profile?.location.orEmpty()
    }

    Box(Modifier.fillMaxSize()) {
        Column(Modifier.fillMaxSize().statusBarsPadding().navigationBarsPadding().imePadding()) {
            Row(Modifier.height(56.dp).padding(horizontal = 4.dp), verticalAlignment = Alignment.CenterVertically) {
                IconButton(onClick = onBack) { Icon(Icons.AutoMirrored.Outlined.ArrowBack, "Back") }
                Text("New listing", style = MaterialTheme.typography.titleLarge)
            }
            Column(
                Modifier.weight(1f).verticalScroll(rememberScrollState()).padding(horizontal = 16.dp),
                verticalArrangement = Arrangement.spacedBy(14.dp),
            ) {
                vm.error?.let { ErrorBanner(it) }

                SectionTitle("Photos")
                LazyRow(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                    item {
                        Box(
                            Modifier
                                .size(96.dp)
                                .clip(RoundedCornerShape(16.dp))
                                .border(1.5.dp, MaterialTheme.colorScheme.outline.copy(alpha = 0.6f), RoundedCornerShape(16.dp))
                                .clickable { picker.launch(PickVisualMediaRequest(ActivityResultContracts.PickVisualMedia.ImageOnly)) },
                            contentAlignment = Alignment.Center,
                        ) {
                            Column(horizontalAlignment = Alignment.CenterHorizontally) {
                                Icon(Icons.Outlined.AddPhotoAlternate, null, tint = MaterialTheme.colorScheme.onSurfaceVariant)
                                Text("${photos.size}/6", style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                            }
                        }
                    }
                    itemsIndexed(photos) { index, uri ->
                        Box(Modifier.size(96.dp).clip(RoundedCornerShape(16.dp))) {
                            AsyncImage(uri, null, contentScale = ContentScale.Crop, modifier = Modifier.fillMaxSize())
                            Box(
                                Modifier
                                    .align(Alignment.TopEnd)
                                    .padding(4.dp)
                                    .size(24.dp)
                                    .clip(CircleShape)
                                    .background(Color.Black.copy(alpha = 0.6f))
                                    .clickable { photos = photos.filterIndexed { i, _ -> i != index } },
                                contentAlignment = Alignment.Center,
                            ) { Icon(Icons.Outlined.Close, "Remove photo", tint = Color.White, modifier = Modifier.size(14.dp)) }
                        }
                    }
                }
                Text(
                    "Photos are optimised on your phone before upload.",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )

                ChoropiaField(title, { title = it }, "Title", error = vm.fieldErrors["title"])
                ChoropiaField(
                    description, { description = it }, "Description",
                    singleLine = false, minLines = 4, imeAction = ImeAction.Default,
                    error = vm.fieldErrors["description"],
                )
                ChoropiaField(
                    price, { price = it.filter { c -> c.isDigit() || c == '.' }; vm.previewFor(price) }, "Price (₦)",
                    keyboardType = KeyboardType.Decimal, error = vm.fieldErrors["price"],
                )
                vm.preview?.let { p ->
                    Text(
                        "You'll receive ${com.choropia.app.ui.util.formatNaira(p.you_receive)} after our ${p.commission_percent.removeSuffix(".00").removeSuffix(".0")}% fee. " +
                            "Buyers pay exactly the price you set. It's free to list; we only charge when you sell.",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }

                Text("Condition", style = MaterialTheme.typography.labelLarge, color = MaterialTheme.colorScheme.onSurfaceVariant)
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    Chip("New", condition == "new", { condition = "new" })
                    Chip("Used", condition == "used", { condition = "used" })
                }

                Box {
                    OutlinedTextField(
                        value = category?.name.orEmpty(),
                        onValueChange = {},
                        readOnly = true,
                        label = { Text("Category") },
                        isError = vm.fieldErrors["category"] != null,
                        supportingText = vm.fieldErrors["category"]?.let { { Text(it) } },
                        trailingIcon = { Icon(Icons.Outlined.ExpandMore, null) },
                        shape = RoundedCornerShape(14.dp),
                        modifier = Modifier.fillMaxWidth(),
                    )
                    Box(Modifier.matchParentSize().clickable { categoryMenu = true })
                    DropdownMenu(expanded = categoryMenu, onDismissRequest = { categoryMenu = false }) {
                        vm.categories.forEach { c ->
                            DropdownMenuItem(text = { Text(c.name) }, onClick = { category = c; categoryMenu = false })
                        }
                    }
                }

                ChoropiaField(
                    location, { location = it }, "Location (e.g. Uyo)",
                    leadingIcon = Icons.Outlined.LocationOn, imeAction = ImeAction.Done,
                )
                Spacer(Modifier.height(4.dp))
            }
            Box(Modifier.padding(16.dp)) {
                PrimaryButton(
                    "Post listing",
                    { vm.submit(title, description, price, condition, category, location, photos, onCreated) },
                    enabled = !vm.busy,
                )
            }
        }
        BlockingLoader(visible = vm.busy)
    }
}
