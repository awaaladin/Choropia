package com.choropia.app.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.LocalShipping
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.RadioButton
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.choropia.app.data.model.Area
import com.choropia.app.data.model.ListingDeliveryInfo
import com.choropia.app.data.model.OrderDelivery
import com.choropia.app.data.network.ApiException
import com.choropia.app.data.repository.ChoropiaRepository
import com.choropia.app.ui.LocalRepository
import com.choropia.app.ui.components.ChoropiaField
import com.choropia.app.ui.components.PrimaryButton
import com.choropia.app.ui.components.SecondaryButton
import com.choropia.app.ui.components.SectionTitle
import com.choropia.app.ui.components.SurfaceCard
import com.choropia.app.ui.rememberVm
import com.choropia.app.ui.util.formatNaira
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch

class OrderDeliveryViewModel(
    private val orderId: Int,
    private val listingId: Int,
    private val repo: ChoropiaRepository,
) : ViewModel() {
    var delivery by mutableStateOf<OrderDelivery?>(null)
        private set
    var options by mutableStateOf<ListingDeliveryInfo?>(null)
        private set
    var areas by mutableStateOf<List<Area>>(emptyList())
        private set
    var dropoff by mutableStateOf<Area?>(null)
        private set
    var busy by mutableStateOf(false)
        private set
    var error by mutableStateOf<String?>(null)
        private set
    var loaded by mutableStateOf(false)
        private set

    fun load(buyerBeforePayment: Boolean) {
        viewModelScope.launch {
            try {
                delivery = repo.orderDelivery(orderId)
                if (delivery == null && buyerBeforePayment) {
                    val info = repo.listingDelivery(listingId, dropoff?.id)
                    options = info
                    if (info.enabled && areas.isEmpty()) areas = repo.areas()
                } else {
                    options = null
                }
                error = null
            } catch (e: ApiException) {
                error = e.message
            } finally {
                loaded = true
            }
        }
    }

    fun pickDropoff(area: Area) {
        dropoff = area
        viewModelScope.launch {
            try {
                options = repo.listingDelivery(listingId, area.id)
            } catch (e: ApiException) {
                error = e.message
            }
        }
    }

    suspend fun addArea(name: String): Area? = try {
        repo.addArea(name).also { areas = (areas + it).sortedBy { a -> a.name } }
    } catch (e: ApiException) {
        error = e.message
        null
    }

    private fun run(block: suspend () -> Unit) {
        if (busy) return
        busy = true
        error = null
        viewModelScope.launch {
            try {
                block()
            } catch (e: ApiException) {
                error = e.message
            } finally {
                busy = false
            }
        }
    }

    fun choose(driverId: Int, note: String) {
        val area = dropoff ?: return
        run { delivery = repo.chooseDelivery(orderId, area.id, driverId, note) }
    }

    fun remove() = run {
        repo.clearDelivery(orderId)
        delivery = null
        options = repo.listingDelivery(listingId, dropoff?.id)
    }

    fun reassign() = run { delivery = repo.reassignDelivery(orderId) }
}

/** True while a driver delivery is attached to the order and has not been cancelled. */
fun OrderDelivery?.isActive() = this != null && status != "cancelled"

/** The total a buyer is charged: the item price plus their share of the delivery fee. */
fun orderTotal(price: String, delivery: OrderDelivery?): String {
    val base = price.toBigDecimalOrNull() ?: return price
    val share = if (delivery.isActive()) delivery?.buyer_share?.toBigDecimalOrNull() else null
    return (base + (share ?: java.math.BigDecimal.ZERO)).toPlainString()
}

@Composable
fun OrderDeliverySection(
    orderId: Int,
    listingId: Int,
    orderStatus: String,
    isBuyer: Boolean,
    isSeller: Boolean,
    onDelivery: (OrderDelivery?) -> Unit,
    onEditDrivers: (Int) -> Unit,
) {
    val repo = LocalRepository.current
    val vm = rememberVm(key = "order-delivery-$orderId") { OrderDeliveryViewModel(orderId, listingId, repo) }
    val buyerBeforePayment = isBuyer && orderStatus == "pending_payment"

    // Reload when the order moves on, and keep an eye on it while a driver is being found / is on the way.
    LaunchedEffect(orderStatus) {
        vm.load(buyerBeforePayment)
        while (orderStatus in setOf("paid_escrow", "courier_assigned", "in_transit")) {
            delay(8_000)
            vm.load(false)
        }
    }
    LaunchedEffect(vm.delivery) { onDelivery(vm.delivery) }

    val delivery = vm.delivery
    var confirmReassign by remember { mutableStateOf(false) }
    var note by remember { mutableStateOf("") }
    var driverChoice by remember { mutableStateOf<Int?>(null) }

    when {
        delivery != null && delivery.status != "cancelled" -> {
            SectionTitle("Delivery")
            SurfaceCard(Modifier.fillMaxWidth()) {
                Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                    Text(delivery.status_label, style = MaterialTheme.typography.titleSmall, color = MaterialTheme.colorScheme.secondary)
                    Text(
                        "${delivery.pickup_area.name} to ${delivery.dropoff_area.name}",
                        style = MaterialTheme.typography.bodyLarge,
                    )
                    Text(
                        "Delivery fee ${formatNaira(delivery.fee)}" + when (delivery.payer) {
                            "split" -> " (split 50/50)"
                            "seller" -> " (paid by the seller)"
                            else -> ""
                        },
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                    delivery.driver?.let { d ->
                        Text("Driver: ${d.name} · ${vehicleLabel(d.vehicle_type)}${if (d.plate_number.isNotBlank()) " · ${d.plate_number}" else ""}", style = MaterialTheme.typography.bodyMedium)
                        if (d.phone.isNotBlank()) Text("Phone ${d.phone} · WhatsApp ${d.whatsapp}", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                    if (isSeller && delivery.status == "offered") {
                        Text(
                            "${delivery.drivers_notified} driver(s) have been told. The first to accept gets the job.",
                            style = MaterialTheme.typography.bodyMedium,
                        )
                    }
                }
            }
            if (isBuyer && delivery.handover_code.isNotBlank()) {
                Column(
                    Modifier
                        .fillMaxWidth()
                        .clip(RoundedCornerShape(20.dp))
                        .background(MaterialTheme.colorScheme.secondaryContainer)
                        .padding(18.dp),
                    horizontalAlignment = Alignment.CenterHorizontally,
                    verticalArrangement = Arrangement.spacedBy(6.dp),
                ) {
                    Text("Your handover code", style = MaterialTheme.typography.labelLarge, color = MaterialTheme.colorScheme.onSecondaryContainer)
                    Text(
                        delivery.handover_code.chunked(3).joinToString(" "),
                        fontSize = 34.sp,
                        fontWeight = FontWeight.Bold,
                        color = MaterialTheme.colorScheme.onSecondaryContainer,
                    )
                    Text(
                        "Tell the driver this code only when the item is in your hands. It confirms delivery and releases your payment to the seller.",
                        style = MaterialTheme.typography.bodySmall,
                        textAlign = TextAlign.Center,
                        color = MaterialTheme.colorScheme.onSecondaryContainer,
                    )
                }
            }
            if (isSeller && delivery.can_reassign) {
                SecondaryButton("Change the driver", { confirmReassign = true }, enabled = !vm.busy, icon = Icons.Outlined.LocalShipping)
                SecondaryButton("Add more drivers to this listing", { onEditDrivers(listingId) })
            }
            if (isBuyer && delivery.can_cancel_choice) {
                SecondaryButton("Collect it myself instead", { vm.remove() }, enabled = !vm.busy)
            }
        }

        buyerBeforePayment && vm.options?.enabled == true -> {
            val info = vm.options!!
            SectionTitle("Delivery (optional)")
            SurfaceCard(Modifier.fillMaxWidth()) {
                Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                    Text(
                        "The seller can have this delivered by a Choropia driver. " + when (info.payer) {
                            "seller" -> "The seller covers the delivery."
                            "split" -> "You and the seller each pay half of the delivery fee."
                            else -> "You pay the delivery fee."
                        },
                        style = MaterialTheme.typography.bodyMedium,
                    )
                    AreaField("Deliver to", vm.areas, vm.dropoff, { vm.pickDropoff(it); driverChoice = null }, vm::addArea)
                    if (vm.dropoff != null) {
                        val choices = info.drivers.flatMap { d -> d.routes.map { r -> d to r } }
                        if (choices.isEmpty()) {
                            Text("None of the seller's drivers go to ${vm.dropoff?.name} yet.", style = MaterialTheme.typography.bodyMedium)
                        }
                        choices.forEach { (d, r) ->
                            Row(
                                Modifier.fillMaxWidth().clickable { driverChoice = d.id },
                                verticalAlignment = Alignment.CenterVertically,
                            ) {
                                RadioButton(selected = driverChoice == d.id, onClick = { driverChoice = d.id })
                                Column(Modifier.weight(1f)) {
                                    Text("${d.name} · ${vehicleLabel(d.vehicle_type)}", style = MaterialTheme.typography.bodyLarge)
                                    Text(
                                        "Fee ${formatNaira(r.price)}" + if (r.you_pay.isNotBlank() && info.payer != "buyer") " · you pay ${formatNaira(r.you_pay)}" else "",
                                        style = MaterialTheme.typography.bodySmall,
                                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                                    )
                                }
                            }
                        }
                        if (choices.isNotEmpty()) {
                            ChoropiaField(note, { note = it.take(300) }, "Exact address or landmark", singleLine = false, minLines = 2)
                            PrimaryButton(
                                "Add delivery",
                                { driverChoice?.let { vm.choose(it, note) } },
                                enabled = driverChoice != null && note.isNotBlank() && !vm.busy,
                                icon = Icons.Outlined.LocalShipping,
                            )
                        }
                    }
                    Text(
                        "Prefer to meet the seller? Skip this and just pay for the item. Your address and phone number stay private until a driver accepts.",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
            }
        }
    }

    vm.error?.let { Text(it, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodyMedium) }

    if (confirmReassign) {
        AlertDialog(
            onDismissRequest = { confirmReassign = false },
            title = { Text("Change the driver?") },
            text = { Text("The current driver is told they're no longer needed, and your other drivers are offered the job. The first to accept gets it.") },
            confirmButton = { TextButton(onClick = { confirmReassign = false; vm.reassign() }) { Text("Yes, change") } },
            dismissButton = { TextButton(onClick = { confirmReassign = false }) { Text("Keep") } },
        )
    }
}
