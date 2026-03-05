package com.tlex.tv.ui.navigation

import androidx.lifecycle.ViewModel
import com.tlex.tv.data.local.AppPreferences
import dagger.hilt.android.lifecycle.HiltViewModel
import javax.inject.Inject

@HiltViewModel
class NavViewModel @Inject constructor(val preferences: AppPreferences) : ViewModel()
