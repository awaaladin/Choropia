package com.choropia.app.ui.screens.createlisting

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.FilterChip
import androidx.compose.material3.MaterialTheme
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
import com.choropia.app.data.model.Category
import com.choropia.app.data.repository.ChoropiaRepository
import kotlinx.coroutines.launch

@Composable
fun CreateListingScreen(repository: ChoropiaRepository, onCreated: (Int) -> Unit) {
    var categories by remember { mutableStateOf<List<Category>>(emptyList()) }
    var selectedCategory by remember { mutableStateOf<Category?>(null) }
    var categoryMenuOpen by remember { mutableStateOf(false) }
    var title by remember { mutableStateOf("") }
    var description by remember { mutableStateOf("") }
    var price by remember { mutableStateOf("") }
    var location by remember { mutableStateOf("") }
    var condition by remember { mutableStateOf("used") }
    var error by remember { mutableStateOf<String?>(null) }
    var submitting by remember { mutableStateOf(false) }
    val scope = rememberCoroutineScope()

    LaunchedEffect(Unit) {
        categories = runCatching { repository.listCategories() }.getOrDefault(emptyList())
        selectedCategory = categories.firstOrNull()
    }

    Column(modifier = Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(16.dp)) {
        Text("Post a listing", style = MaterialTheme.typography.headlineSmall)

        OutlinedTextField(title, { title = it }, label = { Text("Title") }, modifier = Modifier.fillMaxWidth().padding(top = 12.dp))
        OutlinedTextField(
            description, { description = it }, label = { Text("Description") },
            modifier = Modifier.fillMaxWidth().padding(top = 8.dp),
        )
        OutlinedTextField(
            price, { price = it }, label = { Text("Price (₦)") },
            modifier = Modifier.fillMaxWidth().padding(top = 8.dp),
        )
        OutlinedTextField(
            location, { location = it }, label = { Text("Location") },
            modifier = Modifier.fillMaxWidth().padding(top = 8.dp),
        )

        Row(modifier = Modifier.padding(top = 12.dp)) {
            FilterChip(selected = condition == "used", onClick = { condition = "used" }, label = { Text("Used") })
            FilterChip(
                selected = condition == "new",
                onClick = { condition = "new" },
                label = { Text("New") },
                modifier = Modifier.padding(start = 8.dp),
            )
        }

        Text(
            "Category: ${selectedCategory?.name ?: "Select a category"} (tap to change)",
            modifier = Modifier.padding(top = 16.dp).clickable { categoryMenuOpen = true },
            color = MaterialTheme.colorScheme.primary,
        )
        DropdownMenu(expanded = categoryMenuOpen, onDismissRequest = { categoryMenuOpen = false }) {
            categories.forEach { category ->
                DropdownMenuItem(text = { Text(category.name) }, onClick = {
                    selectedCategory = category
                    categoryMenuOpen = false
                })
            }
        }

        error?.let { Text(it, color = MaterialTheme.colorScheme.error, modifier = Modifier.padding(top = 12.dp)) }

        Button(
            enabled = !submitting && title.isNotBlank() && price.isNotBlank() && selectedCategory != null,
            onClick = {
                val category = selectedCategory ?: return@Button
                submitting = true
                scope.launch {
                    try {
                        val listing = repository.createListing(title, description, price, condition, category.id, location)
                        onCreated(listing.id)
                    } catch (e: Exception) {
                        error = e.message
                    } finally {
                        submitting = false
                    }
                }
            },
            modifier = Modifier.fillMaxWidth().padding(top = 20.dp),
        ) { Text(if (submitting) "Posting…" else "Post listing") }

        Text(
            "Photos can be added from the web app for now.",
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.outline,
            modifier = Modifier.padding(top = 8.dp),
        )
    }
}
