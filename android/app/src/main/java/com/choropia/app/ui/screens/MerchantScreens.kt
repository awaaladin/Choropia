package com.choropia.app.ui.screens

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.lazy.grid.GridCells
import androidx.compose.foundation.lazy.grid.GridItemSpan
import androidx.compose.foundation.lazy.grid.LazyVerticalGrid
import androidx.compose.foundation.lazy.grid.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.outlined.ArrowBack
import androidx.compose.material.icons.outlined.Inventory2
import androidx.compose.material.icons.outlined.LocationOn
import androidx.compose.material.icons.outlined.MarkEmailRead
import androidx.compose.material.icons.outlined.Phone
import androidx.compose.material.icons.outlined.Storefront
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
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
import com.choropia.app.data.model.Merchant
import com.choropia.app.data.network.ApiException
import com.choropia.app.data.repository.ChoropiaRepository
import com.choropia.app.data.repository.ListingQuery
import com.choropia.app.session.Session
import com.choropia.app.ui.LocalRepository
import com.choropia.app.ui.LocalSession
import com.choropia.app.ui.components.Avatar
import com.choropia.app.ui.components.BlockingLoader
import com.choropia.app.ui.components.BrandPullToRefresh
import com.choropia.app.ui.components.ChoropiaField
import com.choropia.app.ui.components.EmptyState
import com.choropia.app.ui.components.ErrorBanner
import com.choropia.app.ui.components.ErrorState
import com.choropia.app.ui.components.GridListingCard
import com.choropia.app.ui.components.PrimaryButton
import com.choropia.app.ui.components.ScreenLoader
import com.choropia.app.ui.components.SecondaryButton
import com.choropia.app.ui.rememberVm
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

data class MerchantState(
    val merchant: Merchant? = null,
    val listings: List<Listing> = emptyList(),
    val following: Boolean = false,
    val loading: Boolean = true,
    val refreshing: Boolean = false,
    val error: String? = null,
    val message: String? = null,
)

class MerchantViewModel(
    private val merchantId: Int,
    private val repo: ChoropiaRepository,
    private val session: Session,
) : ViewModel() {
    private val _state = MutableStateFlow(MerchantState())
    val state: StateFlow<MerchantState> = _state.asStateFlow()

    init {
        load(initial = true)
    }

    fun load(initial: Boolean = false) {
        viewModelScope.launch {
            _state.update { it.copy(loading = initial && it.merchant == null, refreshing = !initial, error = null) }
            try {
                val merchant = repo.merchant(merchantId)
                val listings = repo.listings(ListingQuery(merchantId = merchantId)).items
                val following = if (session.loggedIn.value) runCatching { repo.isFollowing("merchant", merchantId) }.getOrDefault(false) else false
                _state.update { it.copy(merchant = merchant, listings = listings, following = following, loading = false, refreshing = false) }
            } catch (e: ApiException) {
                _state.update { it.copy(loading = false, refreshing = false, error = e.message) }
            }
        }
    }

    fun toggleFollow(onNeedsLogin: () -> Unit) {
        if (!session.loggedIn.value) return onNeedsLogin()
        val want = !_state.value.following
        _state.update { s ->
            s.copy(
                following = want,
                merchant = s.merchant?.let { it.copy(followers_count = (it.followers_count + if (want) 1 else -1).coerceAtLeast(0)) },
            )
        }
        viewModelScope.launch {
            try {
                repo.setFollowing("merchant", merchantId, want)
            } catch (e: ApiException) {
                _state.update { s ->
                    s.copy(
                        following = !want,
                        merchant = s.merchant?.let { it.copy(followers_count = (it.followers_count + if (want) -1 else 1).coerceAtLeast(0)) },
                        message = e.message,
                    )
                }
            }
        }
    }
}

@Composable
fun MerchantProfileScreen(
    merchantId: Int,
    onBack: () -> Unit,
    onOpenListing: (Int) -> Unit,
    onNeedsLogin: () -> Unit,
) {
    val repo = LocalRepository.current
    val session = LocalSession.current
    val vm = rememberVm(key = "merchant-$merchantId") { MerchantViewModel(merchantId, repo, session) }
    val state by vm.state.collectAsState()

    Column(Modifier.fillMaxSize().statusBarsPadding()) {
        Row(Modifier.height(56.dp).padding(horizontal = 4.dp), verticalAlignment = Alignment.CenterVertically) {
            IconButton(onClick = onBack) { Icon(Icons.AutoMirrored.Outlined.ArrowBack, "Back") }
            Text("Storefront", style = MaterialTheme.typography.titleLarge)
        }
        val merchant = state.merchant
        when {
            state.loading -> ScreenLoader()
            merchant == null -> ErrorState(state.error ?: "Storefront not found.", { vm.load(initial = true) }, Modifier.fillMaxSize())
            else -> BrandPullToRefresh(state.refreshing, { vm.load() }, Modifier.fillMaxSize()) {
                LazyVerticalGrid(
                    columns = GridCells.Fixed(2),
                    modifier = Modifier.fillMaxSize(),
                    contentPadding = PaddingValues(16.dp),
                    horizontalArrangement = Arrangement.spacedBy(12.dp),
                    verticalArrangement = Arrangement.spacedBy(12.dp),
                ) {
                    item(span = { GridItemSpan(maxLineSpan) }) {
                        Column(Modifier.fillMaxWidth(), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                            Row(horizontalArrangement = Arrangement.spacedBy(16.dp), verticalAlignment = Alignment.CenterVertically) {
                                Avatar(merchant.business_name, merchant.logo, size = 76.dp)
                                Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(3.dp)) {
                                    Text(merchant.business_name, style = MaterialTheme.typography.titleLarge)
                                    if (merchant.location.isNotBlank()) {
                                        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(4.dp)) {
                                            Icon(Icons.Outlined.LocationOn, null, Modifier.size(15.dp), tint = MaterialTheme.colorScheme.onSurfaceVariant)
                                            Text(merchant.location, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                                        }
                                    }
                                    Text(
                                        "${merchant.followers_count} follower${if (merchant.followers_count == 1) "" else "s"} · ${state.listings.size} listing${if (state.listings.size == 1) "" else "s"}",
                                        style = MaterialTheme.typography.bodySmall,
                                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                                    )
                                }
                            }
                            if (merchant.description.isNotBlank()) {
                                Text(merchant.description, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                            }
                            if (session.user.value?.id != merchant.owner_id) {
                                if (state.following) {
                                    SecondaryButton("Following", { vm.toggleFollow(onNeedsLogin) })
                                } else {
                                    PrimaryButton("Follow storefront", { vm.toggleFollow(onNeedsLogin) })
                                }
                            }
                        }
                    }
                    if (state.listings.isEmpty()) {
                        item(span = { GridItemSpan(maxLineSpan) }) {
                            EmptyState(Icons.Outlined.Inventory2, "No listings yet", "This storefront hasn't posted anything.")
                        }
                    }
                    items(state.listings, key = { it.id }) { listing ->
                        GridListingCard(listing, onClick = { onOpenListing(listing.id) })
                    }
                }
            }
        }
    }
}

// --- apply for a storefront -----------------------------------------------------------------

class ApplyMerchantViewModel(private val repo: ChoropiaRepository) : ViewModel() {
    var busy by mutableStateOf(false)
        private set
    var error by mutableStateOf<String?>(null)
        private set
    var fieldErrors by mutableStateOf<Map<String, String>>(emptyMap())
        private set
    var submitted by mutableStateOf(false)
        private set

    fun submit(name: String, description: String, phone: String, address: String) {
        val local = mutableMapOf<String, String>()
        if (name.isBlank()) local["business_name"] = "Enter your business name"
        if (phone.isBlank()) local["business_phone"] = "Enter a contact phone number"
        if (address.isBlank()) local["business_address"] = "Enter your business address"
        if (local.isNotEmpty()) {
            fieldErrors = local
            error = "Please fill in the highlighted fields."
            return
        }
        if (busy) return
        busy = true
        error = null
        fieldErrors = emptyMap()
        viewModelScope.launch {
            try {
                repo.applyForMerchant(name, description, phone, address)
                submitted = true
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
fun ApplyMerchantScreen(onBack: () -> Unit) {
    val repo = LocalRepository.current
    val vm = rememberVm { ApplyMerchantViewModel(repo) }
    var name by remember { mutableStateOf("") }
    var description by remember { mutableStateOf("") }
    var phone by remember { mutableStateOf("") }
    var address by remember { mutableStateOf("") }

    Box(Modifier.fillMaxSize()) {
        Column(Modifier.fillMaxSize().statusBarsPadding().navigationBarsPadding().imePadding()) {
            Row(Modifier.height(56.dp).padding(horizontal = 4.dp), verticalAlignment = Alignment.CenterVertically) {
                IconButton(onClick = onBack) { Icon(Icons.AutoMirrored.Outlined.ArrowBack, "Back") }
                Text("Open a storefront", style = MaterialTheme.typography.titleLarge)
            }
            if (vm.submitted) {
                EmptyState(
                    icon = Icons.Outlined.MarkEmailRead,
                    title = "Application received",
                    message = "Our team will review your storefront application. You'll get a notification as soon as it's approved.",
                    actionLabel = "Done",
                    onAction = onBack,
                )
            } else {
                Column(
                    Modifier.weight(1f).verticalScroll(rememberScrollState()).padding(horizontal = 16.dp),
                    verticalArrangement = Arrangement.spacedBy(14.dp),
                ) {
                    Text(
                        "Verified storefronts get a public page, a follower base and a trusted badge on every listing.",
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                    vm.error?.let { ErrorBanner(it) }
                    ChoropiaField(name, { name = it }, "Business name", leadingIcon = Icons.Outlined.Storefront, error = vm.fieldErrors["business_name"])
                    ChoropiaField(description, { description = it }, "What do you sell?", singleLine = false, minLines = 3, error = vm.fieldErrors["business_description"])
                    ChoropiaField(phone, { phone = it }, "Business phone", keyboardType = KeyboardType.Phone, leadingIcon = Icons.Outlined.Phone, error = vm.fieldErrors["business_phone"])
                    ChoropiaField(address, { address = it }, "Business address", leadingIcon = Icons.Outlined.LocationOn, error = vm.fieldErrors["business_address"])
                }
                Box(Modifier.padding(16.dp)) {
                    PrimaryButton("Submit application", { vm.submit(name, description, phone, address) }, enabled = !vm.busy)
                }
            }
        }
        BlockingLoader(visible = vm.busy)
    }
}
