package com.choropia.app.ui

import androidx.compose.runtime.Composable
import androidx.compose.runtime.staticCompositionLocalOf
import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewmodel.compose.viewModel
import com.choropia.app.data.repository.ChoropiaRepository
import com.choropia.app.session.Session

val LocalRepository = staticCompositionLocalOf<ChoropiaRepository> { error("ChoropiaRepository not provided") }
val LocalSession = staticCompositionLocalOf<Session> { error("Session not provided") }

class VmFactory(private val builder: () -> ViewModel) : ViewModelProvider.Factory {
    @Suppress("UNCHECKED_CAST")
    override fun <T : ViewModel> create(modelClass: Class<T>): T = builder() as T
}

/** Creates (or restores) a screen ViewModel scoped to the current nav destination. */
@Composable
inline fun <reified VM : ViewModel> rememberVm(key: String? = null, noinline builder: () -> VM): VM =
    viewModel<VM>(key = key, factory = VmFactory(builder))
