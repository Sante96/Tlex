package com.tlex.tv.ui.screens.setup

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.tlex.tv.data.local.AppPreferences
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject

@HiltViewModel
class ServerSetupViewModel @Inject constructor(
    private val preferences: AppPreferences
) : ViewModel() {

    private val _saved = MutableStateFlow(false)
    val saved: StateFlow<Boolean> = _saved

    fun saveServerUrl(url: String) {
        if (url.isBlank()) return
        viewModelScope.launch {
            preferences.setServerUrl(url)
            _saved.value = true
        }
    }
}
