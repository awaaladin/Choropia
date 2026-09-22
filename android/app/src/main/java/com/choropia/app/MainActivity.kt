package com.choropia.app

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.Surface
import androidx.compose.ui.Modifier
import com.choropia.app.navigation.ChoropiaNavHost
import com.choropia.app.ui.theme.ChoropiaTheme

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()

        val repository = (application as ChoropiaApp).repository

        setContent {
            ChoropiaTheme {
                Surface(modifier = Modifier.fillMaxSize()) {
                    ChoropiaNavHost(repository = repository)
                }
            }
        }
    }
}
