package com.choropia.app.ui.screens.profile

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.choropia.app.data.model.User
import com.choropia.app.data.repository.ChoropiaRepository
import kotlinx.coroutines.launch

@Composable
fun ProfileScreen(
    repository: ChoropiaRepository,
    onLoggedOut: () -> Unit = {},
    onApplyMerchant: () -> Unit = {},
) {
    var user by remember { mutableStateOf<User?>(null) }
    var error by remember { mutableStateOf<String?>(null) }
    var saveError by remember { mutableStateOf<String?>(null) }
    var saved by remember { mutableStateOf(false) }
    var saving by remember { mutableStateOf(false) }

    var firstName by remember { mutableStateOf("") }
    var lastName by remember { mutableStateOf("") }
    var phone by remember { mutableStateOf("") }
    var bio by remember { mutableStateOf("") }
    var location by remember { mutableStateOf("") }

    val scope = rememberCoroutineScope()

    LaunchedEffect(Unit) {
        try {
            val me = repository.me()
            user = me
            firstName = me.first_name
            lastName = me.last_name
            phone = me.phone_number ?: ""
            bio = me.profile?.bio ?: ""
            location = me.profile?.location ?: ""
        } catch (e: Exception) {
            error = e.message
        }
    }

    Column(modifier = Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(16.dp)) {
        Text("Your profile", style = MaterialTheme.typography.headlineSmall)

        error?.let { Text(it, color = MaterialTheme.colorScheme.error, modifier = Modifier.padding(top = 8.dp)) }

        if (user != null) {
            Text(user!!.email, style = MaterialTheme.typography.bodyMedium, modifier = Modifier.padding(top = 8.dp))

            OutlinedTextField(firstName, { firstName = it }, label = { Text("First name") }, modifier = Modifier.fillMaxWidth().padding(top = 12.dp))
            OutlinedTextField(lastName, { lastName = it }, label = { Text("Last name") }, modifier = Modifier.fillMaxWidth().padding(top = 8.dp))
            OutlinedTextField(phone, { phone = it }, label = { Text("Phone number") }, modifier = Modifier.fillMaxWidth().padding(top = 8.dp))
            OutlinedTextField(bio, { bio = it }, label = { Text("Bio") }, modifier = Modifier.fillMaxWidth().padding(top = 8.dp))
            OutlinedTextField(location, { location = it }, label = { Text("Location") }, modifier = Modifier.fillMaxWidth().padding(top = 8.dp))

            saveError?.let { Text(it, color = MaterialTheme.colorScheme.error, modifier = Modifier.padding(top = 8.dp)) }
            if (saved) Text("Saved.", color = MaterialTheme.colorScheme.primary, modifier = Modifier.padding(top = 8.dp))

            Button(
                enabled = !saving,
                onClick = {
                    saving = true
                    saved = false
                    scope.launch {
                        try {
                            val theme = user?.profile?.theme_preference ?: "light"
                            user = repository.updateProfile(firstName, lastName, phone.ifBlank { null }, bio, location, theme)
                            saved = true
                        } catch (e: Exception) {
                            saveError = e.message
                        } finally {
                            saving = false
                        }
                    }
                },
                modifier = Modifier.fillMaxWidth().padding(top = 16.dp),
            ) { Text(if (saving) "Saving…" else "Save changes") }

            Text(
                "Become a merchant →",
                color = MaterialTheme.colorScheme.primary,
                modifier = Modifier.padding(top = 20.dp).clickable(onClick = onApplyMerchant),
            )

            OutlinedButton(
                onClick = { scope.launch { repository.logout(); onLoggedOut() } },
                modifier = Modifier.fillMaxWidth().padding(top = 12.dp),
            ) { Text("Log out") }
        }
    }
}
