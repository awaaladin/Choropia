package com.choropia.app.ui.screens.orders

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.Card
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.choropia.app.data.model.Order
import com.choropia.app.data.repository.ChoropiaRepository

@Composable
fun OrdersScreen(repository: ChoropiaRepository, onOpenOrder: (Int) -> Unit = {}) {
    var orders by remember { mutableStateOf<List<Order>>(emptyList()) }
    var error by remember { mutableStateOf<String?>(null) }

    LaunchedEffect(Unit) {
        try {
            orders = repository.listOrders()
        } catch (e: Exception) {
            error = e.message
        }
    }

    Column(modifier = Modifier.fillMaxSize().padding(16.dp)) {
        Text("Your orders", style = MaterialTheme.typography.headlineSmall)
        error?.let { Text(it, color = MaterialTheme.colorScheme.error) }
        LazyColumn {
            items(orders) { order ->
                Card(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(vertical = 6.dp)
                        .clickable { onOpenOrder(order.id) },
                ) {
                    Column(modifier = Modifier.padding(12.dp)) {
                        Text("Order #${order.id} · ₦${order.price}", style = MaterialTheme.typography.titleSmall)
                        Text(order.status, color = MaterialTheme.colorScheme.primary)
                    }
                }
            }
        }
    }
}
