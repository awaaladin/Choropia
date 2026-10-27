package com.choropia.app.ui.screens

import android.net.Uri
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
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
import androidx.compose.material.icons.outlined.CameraAlt
import androidx.compose.material.icons.outlined.CheckCircle
import androidx.compose.material.icons.outlined.LocalShipping
import androidx.compose.material.icons.outlined.UploadFile
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Checkbox
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import androidx.core.content.FileProvider
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.choropia.app.data.model.Area
import com.choropia.app.data.model.DriverJobs
import com.choropia.app.data.model.DriverMe
import com.choropia.app.data.model.JobCard
import com.choropia.app.data.model.OrderDelivery
import com.choropia.app.data.model.RoutePrice
import com.choropia.app.data.network.ApiException
import com.choropia.app.data.network.DriverApplyRequest
import com.choropia.app.data.repository.ChoropiaRepository
import com.choropia.app.ui.LocalRepository
import com.choropia.app.ui.components.BlockingLoader
import com.choropia.app.ui.components.Chip
import com.choropia.app.ui.components.ChoropiaField
import com.choropia.app.ui.components.ErrorBanner
import com.choropia.app.ui.components.PrimaryButton
import com.choropia.app.ui.components.QuietButton
import com.choropia.app.ui.components.ScreenLoader
import com.choropia.app.ui.components.SecondaryButton
import com.choropia.app.ui.components.SectionTitle
import com.choropia.app.ui.components.SurfaceCard
import com.choropia.app.ui.rememberVm
import com.choropia.app.ui.util.formatNaira
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import java.io.File

class DriverViewModel(private val repo: ChoropiaRepository) : ViewModel() {
    var loading by mutableStateOf(true)
        private set
    var busy by mutableStateOf(false)
        private set
    var error by mutableStateOf<String?>(null)
        private set
    var message by mutableStateOf<String?>(null)
        private set
    var me by mutableStateOf<DriverMe?>(null)
        private set
    var areas by mutableStateOf<List<Area>>(emptyList())
        private set
    var routes by mutableStateOf<List<RoutePrice>>(emptyList())
        private set
    var jobs by mutableStateOf(DriverJobs())
        private set

    init {
        load()
    }

    fun load(quiet: Boolean = false) {
        viewModelScope.launch {
            try {
                me = repo.driverMe()
                if (areas.isEmpty()) areas = repo.areas()
                if (me?.status == "approved") {
                    routes = repo.driverRoutes()
                    jobs = repo.driverJobs()
                }
                if (!quiet) error = null
            } catch (e: ApiException) {
                if (!quiet) error = e.message
            } finally {
                loading = false
            }
        }
    }

    private fun run(success: String? = null, block: suspend () -> Unit) {
        if (busy) return
        busy = true
        error = null
        viewModelScope.launch {
            try {
                block()
                success?.let { message = it }
            } catch (e: ApiException) {
                error = e.message
            } finally {
                busy = false
            }
        }
    }

    fun messageShown() {
        message = null
    }

    fun apply(request: DriverApplyRequest) = run("Application sent. Now upload your documents.") { me = repo.driverApply(request) }

    fun upload(kind: String, uri: Uri) = run("Document uploaded securely.") { me = repo.uploadDriverDocument(kind, uri) }

    fun setAvailable(value: Boolean) = run { me = repo.driverAvailability(value) }

    suspend fun addArea(name: String): Area? = try {
        repo.addArea(name).also { areas = (areas + it).sortedBy { a -> a.name } }
    } catch (e: ApiException) {
        error = e.message
        null
    }

    fun addRoute(from: Area, to: Area, price: String) = run("Price saved.") {
        repo.addDriverRoute(from.id, to.id, price)
        routes = repo.driverRoutes()
    }

    fun deleteRoute(id: Int) = run {
        repo.deleteDriverRoute(id)
        routes = repo.driverRoutes()
    }

    fun accept(id: Int) = run("It's yours. Pick it up from the seller.") {
        repo.acceptJob(id)
        jobs = repo.driverJobs()
    }

    fun decline(id: Int) = run {
        repo.declineJob(id)
        jobs = repo.driverJobs()
    }

    fun pickup(id: Int) = run("Marked as picked up.") {
        repo.pickupJob(id)
        jobs = repo.driverJobs()
    }

    fun deliver(id: Int, code: String, photo: Uri) = run("Delivered. Your pay is on its way.") {
        repo.deliverJob(id, code, photo)
        jobs = repo.driverJobs()
    }
}

@Composable
fun DriverScreen(onBack: () -> Unit, onPayoutAccount: () -> Unit, showMessage: (String) -> Unit) {
    val repo = LocalRepository.current
    val vm = rememberVm { DriverViewModel(repo) }

    LaunchedEffect(vm.message) {
        vm.message?.let { showMessage(it); vm.messageShown() }
    }
    // New jobs show up without the driver having to pull to refresh.
    LaunchedEffect(vm.me?.status) {
        while (vm.me?.status == "approved") {
            delay(15_000)
            vm.load(quiet = true)
        }
    }

    Box(Modifier.fillMaxSize()) {
        Column(Modifier.fillMaxSize().statusBarsPadding().navigationBarsPadding()) {
            Row(Modifier.height(56.dp).padding(horizontal = 4.dp), verticalAlignment = Alignment.CenterVertically) {
                IconButton(onClick = onBack) { Icon(Icons.AutoMirrored.Outlined.ArrowBack, "Back") }
                Text("Deliver with Choropia", style = MaterialTheme.typography.titleLarge)
            }
            val me = vm.me
            when {
                vm.loading -> ScreenLoader()
                me == null -> ApplyForm(vm)
                me.status == "approved" -> ApprovedHub(vm, me, onPayoutAccount)
                else -> ReviewStatus(vm, me)
            }
        }
        BlockingLoader(visible = vm.busy)
    }
}

// --- applying ---------------------------------------------------------------------------------

@Composable
private fun ApplyForm(vm: DriverViewModel) {
    val context = LocalContext.current
    var fullName by remember { mutableStateOf("") }
    var phone by remember { mutableStateOf("") }
    var whatsapp by remember { mutableStateOf("") }
    var vehicle by remember { mutableStateOf("bike") }
    var plate by remember { mutableStateOf("") }
    var guarantorName by remember { mutableStateOf("") }
    var guarantorPhone by remember { mutableStateOf("") }
    var accepted by remember { mutableStateOf(false) }

    Column(
        Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(horizontal = 16.dp),
        verticalArrangement = Arrangement.spacedBy(14.dp),
    ) {
        Note(
            "Earn by delivering items sold on Choropia. You set a fixed price for each trip. " +
                "We verify every driver first, so buyers and sellers can trust you. Individuals only for now.",
        )
        vm.error?.let { ErrorBanner(it) }
        ChoropiaField(fullName, { fullName = it }, "Full name (as on your ID)")
        ChoropiaField(phone, { phone = it.filter { c -> c.isDigit() || c == '+' } }, "Phone number", keyboardType = KeyboardType.Phone)
        ChoropiaField(whatsapp, { whatsapp = it.filter { c -> c.isDigit() || c == '+' } }, "WhatsApp number", keyboardType = KeyboardType.Phone)
        Text("Your vehicle", style = MaterialTheme.typography.titleSmall)
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            listOf("bike", "tricycle", "car", "van").forEach { v -> Chip(vehicleLabel(v).substringBefore(" ("), vehicle == v, { vehicle = v }) }
        }
        ChoropiaField(plate, { plate = it }, "Plate number (if any)")
        Text("Your guarantor", style = MaterialTheme.typography.titleSmall)
        Text(
            "Someone who knows you and can vouch for you. We may call them to confirm.",
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        ChoropiaField(guarantorName, { guarantorName = it }, "Guarantor's full name")
        ChoropiaField(guarantorPhone, { guarantorPhone = it.filter { c -> c.isDigit() || c == '+' } }, "Guarantor's phone number", keyboardType = KeyboardType.Phone)

        Row(verticalAlignment = Alignment.CenterVertically) {
            Checkbox(checked = accepted, onCheckedChange = { accepted = it })
            Text("I agree to the Driver Terms and the Privacy Policy, and I consent to my documents being checked.", style = MaterialTheme.typography.bodySmall, modifier = Modifier.weight(1f))
        }
        Row {
            QuietButton("Read Driver Terms", { openWebPage(context, legalUrl("driver_terms")) })
            QuietButton("Privacy Policy", { openWebPage(context, legalUrl("privacy")) })
        }
        PrimaryButton(
            "Apply",
            {
                vm.apply(DriverApplyRequest(fullName, phone, whatsapp, vehicle, plate, guarantorName, guarantorPhone, accepted))
            },
            enabled = accepted && fullName.isNotBlank() && phone.isNotBlank() && whatsapp.isNotBlank() &&
                guarantorName.isNotBlank() && guarantorPhone.isNotBlank() && !vm.busy,
        )
    }
}

// --- waiting for review / rejected -------------------------------------------------------------------

@Composable
private fun ReviewStatus(vm: DriverViewModel, me: DriverMe) {
    var pendingKind by remember { mutableStateOf<String?>(null) }
    val picker = rememberLauncherForActivityResult(ActivityResultContracts.GetContent()) { uri ->
        val kind = pendingKind
        if (uri != null && kind != null) vm.upload(kind, uri)
        pendingKind = null
    }

    Column(
        Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(horizontal = 16.dp),
        verticalArrangement = Arrangement.spacedBy(14.dp),
    ) {
        vm.error?.let { ErrorBanner(it) }
        SurfaceCard(Modifier.fillMaxWidth()) {
            Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
                Text(me.status_label.ifBlank { me.status }, style = MaterialTheme.typography.titleMedium)
                Text(
                    when (me.status) {
                        "rejected" -> me.review_note.ifBlank { "We couldn't verify your application. Fix the details and apply again." }
                        "suspended" -> me.review_note.ifBlank { "Your driver account is suspended. Contact support." }
                        else -> if (me.documents_complete) "We have everything. Our team is checking your documents. You'll get an email when you're approved."
                        else "Upload all four documents below so we can verify you."
                    },
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }
        if (me.status != "suspended") {
            SectionTitle("Your documents")
            Text(
                "These are encrypted on our servers. Only our verification team can open them, and every view is logged.",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            me.documents.forEach { doc ->
                SurfaceCard(Modifier.fillMaxWidth()) {
                    Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                        Icon(
                            if (doc.uploaded) Icons.Outlined.CheckCircle else Icons.Outlined.UploadFile,
                            null,
                            tint = if (doc.uploaded) MaterialTheme.colorScheme.secondary else MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                        Text(doc.label, Modifier.weight(1f), style = MaterialTheme.typography.bodyLarge)
                        TextButton(onClick = { pendingKind = doc.kind; picker.launch("image/*") }, enabled = !vm.busy) {
                            Text(if (doc.uploaded) "Replace" else "Upload")
                        }
                    }
                }
            }
        }
    }
}

// --- approved: jobs, prices, account ------------------------------------------------------------------

@Composable
private fun ApprovedHub(vm: DriverViewModel, me: DriverMe, onPayoutAccount: () -> Unit) {
    var tab by remember { mutableIntStateOf(0) }
    Row(Modifier.padding(horizontal = 16.dp, vertical = 6.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        Chip("Jobs (${vm.jobs.open.count { it.state != "already_accepted" } + vm.jobs.mine.count { it.status == "accepted" || it.status == "picked_up" }})", tab == 0, { tab = 0 })
        Chip("My prices", tab == 1, { tab = 1 })
        Chip("Account", tab == 2, { tab = 2 })
    }
    Column(
        Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(horizontal = 16.dp, vertical = 8.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        vm.error?.let { ErrorBanner(it) }
        when (tab) {
            0 -> JobsTab(vm)
            1 -> PricesTab(vm)
            else -> AccountTab(vm, me, onPayoutAccount)
        }
    }
}

@Composable
private fun JobsTab(vm: DriverViewModel) {
    val active = vm.jobs.mine.filter { it.status == "accepted" || it.status == "picked_up" }
    val done = vm.jobs.mine.filter { it.status == "delivered" }

    if (vm.routes.isEmpty()) {
        Note("Add the trips you do (and your prices) on the My prices tab. Sellers can only choose you once you have prices.")
    }
    if (active.isEmpty() && vm.jobs.open.isEmpty()) {
        Text(
            "No jobs right now. New delivery jobs appear here as soon as buyers pay.",
            style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
    }
    active.forEach { ActiveJob(vm, it) }
    if (vm.jobs.open.isNotEmpty()) SectionTitle("New jobs. First to accept gets it")
    vm.jobs.open.forEach { OpenJob(vm, it) }
    if (done.isNotEmpty()) {
        SectionTitle("Completed")
        done.take(10).forEach {
            Text("Order #${it.order}: ${it.pickup_area.name} to ${it.dropoff_area.name}, you earned ${formatNaira(it.you_earn)}", style = MaterialTheme.typography.bodyMedium)
        }
    }
}

@Composable
private fun OpenJob(vm: DriverViewModel, job: JobCard) {
    val taken = job.state == "already_accepted"
    SurfaceCard(Modifier.fillMaxWidth()) {
        Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text(job.listing_title.ifBlank { "Delivery job" }, style = MaterialTheme.typography.titleSmall)
            Text("${job.pickup_area.name} to ${job.dropoff_area.name}", style = MaterialTheme.typography.bodyLarge)
            Text("You earn ${formatNaira(job.you_earn)}", style = MaterialTheme.typography.titleMedium, color = MaterialTheme.colorScheme.secondary)
            if (taken) {
                Text("Already accepted by another driver", style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
            } else {
                Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                    PrimaryButton("Accept", { vm.accept(job.id) }, Modifier.weight(1f), enabled = !vm.busy)
                    SecondaryButton("Decline", { vm.decline(job.id) }, Modifier.weight(1f), enabled = !vm.busy)
                }
            }
        }
    }
}

@Composable
private fun ActiveJob(vm: DriverViewModel, job: OrderDelivery) {
    var deliverOpen by remember { mutableStateOf(false) }
    SurfaceCard(Modifier.fillMaxWidth()) {
        Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text(job.listing_title.ifBlank { "Order #${job.order}" }, style = MaterialTheme.typography.titleSmall)
            Text(job.status_label, style = MaterialTheme.typography.labelLarge, color = MaterialTheme.colorScheme.secondary)
            Text("You earn ${formatNaira(job.you_earn)}", style = MaterialTheme.typography.titleMedium)
            job.pickup?.let { Text("Collect from ${job.pickup_area.name}: ${it.name} ${it.phone}".trim(), style = MaterialTheme.typography.bodyMedium) }
            job.dropoff?.let {
                Text("Deliver to ${job.dropoff_area.name}: ${it.note}", style = MaterialTheme.typography.bodyMedium)
                Text("Buyer: ${it.name} ${it.phone}".trim(), style = MaterialTheme.typography.bodyMedium)
            }
            if (job.can_pick_up) PrimaryButton("I've picked it up", { vm.pickup(job.id) }, enabled = !vm.busy, icon = Icons.Outlined.LocalShipping)
            if (job.can_deliver) PrimaryButton("Confirm delivery", { deliverOpen = true }, enabled = !vm.busy, icon = Icons.Outlined.CheckCircle)
        }
    }
    if (deliverOpen) {
        DeliverDialog(
            onDismiss = { deliverOpen = false },
            onSubmit = { code, uri -> deliverOpen = false; vm.deliver(job.id, code, uri) },
        )
    }
}

/** Needs the buyer's six-digit code and a fresh photo of the item with the buyer. */
@Composable
private fun DeliverDialog(onDismiss: () -> Unit, onSubmit: (String, Uri) -> Unit) {
    val context = LocalContext.current
    var code by remember { mutableStateOf("") }
    var pending by remember { mutableStateOf<Uri?>(null) }
    var photo by remember { mutableStateOf<Uri?>(null) }
    val camera = rememberLauncherForActivityResult(ActivityResultContracts.TakePicture()) { ok ->
        photo = if (ok) pending else null
    }

    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("Confirm delivery") },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                Text("Ask the buyer for their 6-digit handover code, only once they are holding the item. Then take a photo as proof.", style = MaterialTheme.typography.bodyMedium)
                ChoropiaField(code, { code = it.filter { c -> c.isDigit() }.take(6) }, "Buyer's code", keyboardType = KeyboardType.Number)
                SecondaryButton(
                    if (photo == null) "Take a photo" else "Retake photo",
                    {
                        val dir = File(context.cacheDir, "proof").apply { mkdirs() }
                        val file = File(dir, "proof_${System.currentTimeMillis()}.jpg")
                        val uri = FileProvider.getUriForFile(context, "${context.packageName}.files", file)
                        pending = uri
                        camera.launch(uri)
                    },
                    icon = Icons.Outlined.CameraAlt,
                )
                if (photo != null) Text("Photo ready.", color = MaterialTheme.colorScheme.secondary)
            }
        },
        confirmButton = {
            TextButton(enabled = code.length == 6 && photo != null, onClick = { photo?.let { onSubmit(code, it) } }) { Text("Confirm") }
        },
        dismissButton = { TextButton(onClick = onDismiss) { Text("Cancel") } },
    )
}

@Composable
private fun PricesTab(vm: DriverViewModel) {
    var from by remember { mutableStateOf<Area?>(null) }
    var to by remember { mutableStateOf<Area?>(null) }
    var price by remember { mutableStateOf("") }

    Note("Set one fixed price for each trip you do, for example from Ewet Housing to Aka Road. Buyers see this exact price. Choropia keeps 2.5% of each delivery fee.")
    SectionTitle("Add a trip")
    AreaField("From", vm.areas, from, { from = it }, vm::addArea)
    AreaField("To", vm.areas, to, { to = it }, vm::addArea)
    ChoropiaField(price, { price = it.filter { c -> c.isDigit() }.take(6) }, "Price (₦)", keyboardType = KeyboardType.Number)
    PrimaryButton(
        "Save price",
        {
            val a = from
            val b = to
            if (a != null && b != null) { vm.addRoute(a, b, price); price = "" }
        },
        enabled = from != null && to != null && price.isNotBlank() && !vm.busy,
    )

    if (vm.routes.isNotEmpty()) SectionTitle("Your prices")
    vm.routes.filter { it.is_active }.forEach { r ->
        SurfaceCard(Modifier.fillMaxWidth()) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Column(Modifier.weight(1f)) {
                    Text("${r.from_area.name} to ${r.to_area.name}", style = MaterialTheme.typography.bodyLarge)
                    Text(formatNaira(r.price), style = MaterialTheme.typography.titleSmall, color = MaterialTheme.colorScheme.secondary)
                }
                TextButton(onClick = { vm.deleteRoute(r.id) }, enabled = !vm.busy) { Text("Remove") }
            }
        }
    }
}

@Composable
private fun AccountTab(vm: DriverViewModel, me: DriverMe, onPayoutAccount: () -> Unit) {
    val context = LocalContext.current
    SurfaceCard(Modifier.fillMaxWidth()) {
        Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
            Text(me.full_name, style = MaterialTheme.typography.titleMedium)
            Text("${vehicleLabel(me.vehicle_type)} ${me.plate_number}".trim(), style = MaterialTheme.typography.bodyMedium)
            Text("Phone ${me.phone} · WhatsApp ${me.whatsapp}", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
    }
    Row(verticalAlignment = Alignment.CenterVertically) {
        Column(Modifier.weight(1f)) {
            Text("Available for new jobs", style = MaterialTheme.typography.titleSmall)
            Text("Switch off to stop getting job alerts.", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
        Switch(checked = me.available, onCheckedChange = { vm.setAvailable(it) })
    }
    Note("You're paid by bank transfer after each delivery is confirmed. Add the account to receive it.")
    SecondaryButton("Payout account", onPayoutAccount)
    Row {
        QuietButton("Driver Terms", { openWebPage(context, legalUrl("driver_terms")) })
        QuietButton("Privacy Policy", { openWebPage(context, legalUrl("privacy")) })
    }
}
