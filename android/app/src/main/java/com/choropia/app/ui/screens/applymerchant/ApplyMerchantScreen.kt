package com.choropia.app.ui.screens.applymerchant

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.choropia.app.data.repository.ChoropiaRepository
import kotlinx.coroutines.launch

@Composable
fun ApplyMerchantScreen(repository: ChoropiaRepository) {
    var businessName by remember { mutableStateOf("") }
    var businessDescription by remember { mutableStateOf("") }
    var businessPhone by remember { mutableStateOf("") }
    var businessAddress by remember { mutableStateOf("") }
    var error by remember { mutableStateOf<String?>(null) }
    var submitting by remember { mutableStateOf(false) }
    var submitted by remember { mutableStateOf(false) }
    val scope = rememberCoroutineScope()

    Column(modifier = Modifier.fillMaxSize().padding(16.dp)) {
        Text("Open a storefront", style = MaterialTheme.typography.headlineSmall)
        Text(
            "Merchant storefronts get their own followers and listing feed. Applications are reviewed by a moderator.",
            style = MaterialTheme.typography.bodySmall,
            modifier = Modifier.padding(top = 4.dp, bottom = 12.dp),
        )

        if (submitted) {
            Text("Application submitted — you'll be notified once it's reviewed.", color = MaterialTheme.colorScheme.primary)
        } else {
            OutlinedTextField(businessName, { businessName = it }, label = { Text("Business name") }, modifier = Modifier.fillMaxWidth())
            OutlinedTextField(
                businessDescription, { businessDescription = it }, label = { Text("What do you sell?") },
                modifier = Modifier.fillMaxWidth().padding(top = 8.dp),
            )
            OutlinedTextField(
                businessPhone, { businessPhone = it }, label = { Text("Business phone") },
                modifier = Modifier.fillMaxWidth().padding(top = 8.dp),
            )
            OutlinedTextField(
                businessAddress, { businessAddress = it }, label = { Text("Business address") },
                modifier = Modifier.fillMaxWidth().padding(top = 8.dp),
            )

            error?.let { Text(it, color = MaterialTheme.colorScheme.error, modifier = Modifier.padding(top = 8.dp)) }

            Button(
                enabled = !submitting && businessName.isNotBlank() && businessPhone.isNotBlank() && businessAddress.isNotBlank(),
                onClick = {
                    submitting = true
                    scope.launch {
                        try {
                            repository.applyForMerchant(businessName, businessDescription, businessPhone, businessAddress)
                            submitted = true
                        } catch (e: Exception) {
                            error = e.message
                        } finally {
                            submitting = false
                        }
                    }
                },
                modifier = Modifier.fillMaxWidth().padding(top = 16.dp),
            ) { Text(if (submitting) "Submitting…" else "Submit application") }
        }
    }
}
