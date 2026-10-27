package com.choropia.app.ui.screens

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
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
import androidx.compose.material3.RadioButton
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.choropia.app.data.model.Area
import com.choropia.app.data.model.PublicDriver
import com.choropia.app.data.network.ApiException
import com.choropia.app.data.repository.ChoropiaRepository
import com.choropia.app.ui.LocalRepository
import com.choropia.app.ui.components.BlockingLoader
import com.choropia.app.ui.components.ErrorBanner
import com.choropia.app.ui.components.PrimaryButton
import com.choropia.app.ui.components.ScreenLoader
import com.choropia.app.ui.components.SectionTitle
import com.choropia.app.ui.components.SurfaceCard
import com.choropia.app.ui.rememberVm
import com.choropia.app.ui.util.formatNaira
import kotlinx.coroutines.launch

class ListingDeliveryViewModel(private val listingId: Int, private val repo: ChoropiaRepository) : ViewModel() {
    var loading by mutableStateOf(true)
        private set
    var busy by mutableStateOf(false)
        private set
    var error by mutableStateOf<String?>(null)
        private set
    var saved by mutableStateOf(false)
        private set

    var areas by mutableStateOf<List<Area>>(emptyList())
        private set
    var enabled by mutableStateOf(false)
    var payer by mutableStateOf("buyer")
    var pickup by mutableStateOf<Area?>(null)
        private set
    var drivers by mutableStateOf<List<PublicDriver>>(emptyList())
        private set
    var chosen by mutableStateOf<Set<Int>>(emptySet())
        private set

    init {
        viewModelScope.launch {
            try {
                areas = repo.areas()
                val current = repo.listingDelivery(listingId)
                enabled = current.enabled
                payer = current.payer
                chosen = current.drivers.map { it.id }.toSet()
                current.pickup_area?.let { pickUp(it, keepChosen = true) }
            } catch (e: ApiException) {
                error = e.message
            } finally {
                loading = false
            }
        }
    }

    fun pickUp(area: Area, keepChosen: Boolean = false) {
        pickup = area
        if (!keepChosen) chosen = emptySet()
        viewModelScope.launch {
            try {
                drivers = repo.browseDrivers(area.id)
            } catch (e: ApiException) {
                error = e.message
            }
        }
    }

    fun toggle(driverId: Int) {
        chosen = if (driverId in chosen) chosen - driverId else chosen + driverId
    }

    suspend fun addArea(name: String): Area? = try {
        repo.addArea(name).also { areas = (areas + it).sortedBy { a -> a.name } }
    } catch (e: ApiException) {
        error = e.message
        null
    }

    fun save() {
        val area = pickup
        if (busy) return
        if (enabled && area == null) {
            error = "Choose where the item will be collected from."
            return
        }
        if (enabled && chosen.isEmpty()) {
            error = "Pick at least one driver. Picking more than one gets your item collected faster."
            return
        }
        busy = true
        error = null
        viewModelScope.launch {
            try {
                repo.saveListingDelivery(listingId, enabled, payer, area?.id ?: areas.firstOrNull()?.id ?: 0, chosen.toList())
                saved = true
            } catch (e: ApiException) {
                error = e.message
            } finally {
                busy = false
            }
        }
    }

    fun savedShown() {
        saved = false
    }
}

@Composable
fun ListingDeliveryScreen(listingId: Int, onBack: () -> Unit, showMessage: (String) -> Unit) {
    val repo = LocalRepository.current
    val vm = rememberVm(key = "listing-delivery-$listingId") { ListingDeliveryViewModel(listingId, repo) }

    LaunchedEffect(vm.saved) {
        if (vm.saved) {
            showMessage("Delivery settings saved")
            vm.savedShown()
        }
    }

    Box(Modifier.fillMaxSize()) {
        Column(Modifier.fillMaxSize().statusBarsPadding().navigationBarsPadding()) {
            Row(Modifier.height(56.dp).padding(horizontal = 4.dp), verticalAlignment = Alignment.CenterVertically) {
                IconButton(onClick = onBack) { Icon(Icons.AutoMirrored.Outlined.ArrowBack, "Back") }
                Text("Delivery", style = MaterialTheme.typography.titleLarge)
            }
            if (vm.loading) {
                ScreenLoader()
            } else {
                Column(
                    Modifier.weight(1f).verticalScroll(rememberScrollState()).padding(horizontal = 16.dp),
                    verticalArrangement = Arrangement.spacedBy(16.dp),
                ) {
                    Note(
                        "Delivery is optional. When it's on, buyers pick one of your drivers and see the exact price before they pay. " +
                            "Everything is paid on Choropia, so your money is protected and the driver is paid for you.",
                    )
                    vm.error?.let { ErrorBanner(it) }

                    Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                        Text("Offer delivery on this item", Modifier.weight(1f), style = MaterialTheme.typography.titleSmall)
                        Switch(checked = vm.enabled, onCheckedChange = { vm.enabled = it })
                    }

                    if (vm.enabled) {
                        SectionTitle("Who pays for delivery?")
                        listOf("buyer", "seller", "split").forEach { option ->
                            Row(
                                Modifier.fillMaxWidth().clickable { vm.payer = option },
                                verticalAlignment = Alignment.CenterVertically,
                            ) {
                                RadioButton(selected = vm.payer == option, onClick = { vm.payer = option })
                                Text(payerLabel(option), style = MaterialTheme.typography.bodyLarge)
                            }
                        }
                        if (vm.payer == "split") {
                            Text(
                                "Split is always exactly half each. Your half comes out of your payout.",
                                style = MaterialTheme.typography.bodySmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                            )
                        }
                        if (vm.payer != "buyer") {
                            Text(
                                "You can change the item's price if you'd like to cover the delivery cost.",
                                style = MaterialTheme.typography.bodySmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                            )
                        }

                        SectionTitle("Where will the driver collect it?")
                        AreaField("Pickup area", vm.areas, vm.pickup, { vm.pickUp(it) }, vm::addArea)

                        if (vm.pickup != null) {
                            SectionTitle("Pick your drivers")
                            Text(
                                "Choose more than one. When the buyer pays, all of them are told and the first to accept takes the job.",
                                style = MaterialTheme.typography.bodySmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                            )
                            if (vm.drivers.isEmpty()) {
                                Note("No approved drivers serve this area yet. Try another area, or check back soon.")
                            }
                            vm.drivers.forEach { driver ->
                                SurfaceCard(Modifier.fillMaxWidth().clickable { vm.toggle(driver.id) }) {
                                    Row(verticalAlignment = Alignment.Top, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                                        Checkbox(checked = driver.id in vm.chosen, onCheckedChange = { vm.toggle(driver.id) })
                                        Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                                            Text(driver.name, style = MaterialTheme.typography.titleSmall)
                                            Text(
                                                vehicleLabel(driver.vehicle_type),
                                                style = MaterialTheme.typography.bodySmall,
                                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                                            )
                                            driver.routes.forEach { r ->
                                                Text(
                                                    "To ${r.to_area.name}: ${formatNaira(r.price)}",
                                                    style = MaterialTheme.typography.bodyMedium,
                                                )
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                    PrimaryButton("Save delivery settings", { vm.save() }, enabled = !vm.busy)
                }
            }
        }
        BlockingLoader(visible = vm.busy)
    }
}
